"""
Legacy database connector for reading historical data with query optimization.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.config import get_settings
from app.database.redis_client import redis_client
from loguru import logger
import hashlib
import json

settings = get_settings()


class LegacyDBConnector:
    """Legacy database connector wrapper with query optimization and caching."""
    
    def __init__(self):
        """Initialize Legacy DB connection with optimized pool settings."""
        self.engine = create_engine(
            settings.legacy_db_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.DEBUG
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info("Legacy DB connector initialized with query optimization")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def _generate_cache_key(self, query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate cache key for query.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Cache key
        """
        query_string = f"{query}:{json.dumps(params or {}, sort_keys=True)}"
        return f"legacy_query:{hashlib.md5(query_string.encode()).hexdigest()}"
    
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query with caching support.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters
            use_cache: Whether to use cache (default: from settings)
            
        Returns:
            List of result rows as dictionaries
        """
        use_cache = use_cache if use_cache is not None else settings.ENABLE_QUERY_CACHE
        
        # Check cache first
        if use_cache:
            cache_key = self._generate_cache_key(query, params)
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"Query cache hit: {cache_key[:20]}...")
                return cached
        
        session = self.get_session()
        try:
            logger.debug(f"Executing query: {query[:100]}...")
            result = session.execute(text(query), params or {})
            
            # Convert to list of dicts
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            
            # Cache result
            if use_cache and rows:
                cache_key = self._generate_cache_key(query, params)
                redis_client.set(cache_key, rows, settings.QUERY_CACHE_TTL)
                logger.debug(f"Query result cached: {cache_key[:20]}...")
            
            return rows
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return []
        finally:
            session.close()
            return []
        finally:
            session.close()
    
    def get_messages(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get messages from legacy database.
        
        Args:
            limit: Maximum number of messages to retrieve
            offset: Offset for pagination
            
        Returns:
            List of message records
        """
        query = """
        SELECT id, sender_id, receiver_id, content, created_at
        FROM messages
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        return self.execute_query(query, {"limit": limit, "offset": offset})
    
    def get_chats(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get chat messages from legacy database.
        
        Args:
            limit: Maximum number of chats to retrieve
            offset: Offset for pagination
            
        Returns:
            List of chat records
        """
        query = """
        SELECT id, user_id, room_id, message, created_at
        FROM chats
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        return self.execute_query(query, {"limit": limit, "offset": offset})
    
    def get_schedules(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get schedules from legacy database.
        
        Args:
            limit: Maximum number of schedules to retrieve
            offset: Offset for pagination
            
        Returns:
            List of schedule records
        """
        query = """
        SELECT id, user_id, title, description, start_date, end_date, created_at
        FROM schedules
        ORDER BY start_date DESC
        LIMIT :limit OFFSET :offset
        """
        return self.execute_query(query, {"limit": limit, "offset": offset})
    
    def get_emails(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get emails from legacy database.
        
        Args:
            limit: Maximum number of emails to retrieve
            offset: Offset for pagination
            
        Returns:
            List of email records
        """
        query = """
        SELECT id, sender, recipient, subject, body, sent_at
        FROM emails
        ORDER BY sent_at DESC
        LIMIT :limit OFFSET :offset
        """
        return self.execute_query(query, {"limit": limit, "offset": offset})
    
    def get_projects(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get projects from legacy database.
        
        Args:
            limit: Maximum number of projects to retrieve
            offset: Offset for pagination
            
        Returns:
            List of project records
        """
        query = """
        SELECT id, name, description, status, start_date, end_date, created_at
        FROM projects
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        return self.execute_query(query, {"limit": limit, "offset": offset})
    
    def get_data_summary(self) -> Dict[str, int]:
        """
        Get summary statistics of legacy data.
        
        Returns:
            Dictionary with counts of each data type
        """
        summary = {}
        
        # Count messages
        try:
            result = self.execute_query("SELECT COUNT(*) as count FROM messages")
            summary["messages"] = result[0]["count"] if result else 0
        except:
            summary["messages"] = 0
        
        # Count chats
        try:
            result = self.execute_query("SELECT COUNT(*) as count FROM chats")
            summary["chats"] = result[0]["count"] if result else 0
        except:
            summary["chats"] = 0
        
        # Count schedules
        try:
            result = self.execute_query("SELECT COUNT(*) as count FROM schedules")
            summary["schedules"] = result[0]["count"] if result else 0
        except:
            summary["schedules"] = 0
        
        # Count emails
        try:
            result = self.execute_query("SELECT COUNT(*) as count FROM emails")
            summary["emails"] = result[0]["count"] if result else 0
        except:
            summary["emails"] = 0
        
        # Count projects
        try:
            result = self.execute_query("SELECT COUNT(*) as count FROM projects")
            summary["projects"] = result[0]["count"] if result else 0
        except:
            summary["projects"] = 0
        
        return summary
    
    def close(self):
        """Close database engine."""
        self.engine.dispose()


# Global client instance
legacy_db_connector = LegacyDBConnector()
