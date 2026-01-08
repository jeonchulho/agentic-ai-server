"""
Legacy database connector for reading historical data.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

settings = get_settings()


class LegacyDBConnector:
    """Legacy database connector wrapper."""
    
    def __init__(self):
        """Initialize Legacy DB connection."""
        self.engine = create_engine(
            settings.legacy_db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.DEBUG
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query and return results.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        session = self.get_session()
        try:
            result = session.execute(text(query), params or {})
            
            # Convert to list of dicts
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            
            return rows
        except Exception as e:
            print(f"Query execution error: {e}")
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
