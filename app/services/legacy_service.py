"""
Legacy database service layer.
"""
from typing import Dict, Any, List
from app.agents.analysis_agent import analysis_agent
from app.database.legacy_db_connector import legacy_db_connector
from app.database.redis_client import redis_client


class LegacyService:
    """Service for legacy database operations."""
    
    def __init__(self):
        """Initialize service."""
        self.agent = analysis_agent
        self.db_connector = legacy_db_connector
        self.cache_client = redis_client
        self.cache_ttl = 1800  # 30 minutes cache
    
    async def get_data(
        self,
        data_type: str,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get legacy data by type.
        
        Args:
            data_type: Type of data (messages, chats, schedules, emails, projects)
            limit: Maximum number of records
            offset: Offset for pagination
            
        Returns:
            Dictionary with data records
        """
        try:
            # Map data type to connector method
            method_map = {
                "messages": self.db_connector.get_messages,
                "chats": self.db_connector.get_chats,
                "schedules": self.db_connector.get_schedules,
                "emails": self.db_connector.get_emails,
                "projects": self.db_connector.get_projects
            }
            
            method = method_map.get(data_type)
            if not method:
                return {
                    "error": f"Invalid data type: {data_type}",
                    "success": False
                }
            
            records = method(limit=limit, offset=offset)
            
            return {
                "data_type": data_type,
                "records": records,
                "count": len(records),
                "limit": limit,
                "offset": offset,
                "success": True
            }
        except Exception as e:
            return {
                "data_type": data_type,
                "error": str(e),
                "success": False
            }
    
    async def analyze_data(
        self,
        data_type: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Analyze legacy data and provide insights.
        
        Args:
            data_type: Type of data to analyze
            limit: Maximum number of records to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Get data
        data_result = await self.get_data(data_type, limit=limit)
        
        if not data_result.get("success"):
            return data_result
        
        records = data_result.get("records", [])
        
        # Analyze data
        analysis = await self.agent.analyze_data(data_type, records)
        
        return analysis
    
    async def get_summary(
        self,
        data_type: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get summary of legacy data.
        
        Args:
            data_type: Type of data to summarize
            use_cache: Whether to use cache
            
        Returns:
            Dictionary with summary
        """
        # Check cache
        if use_cache:
            cache_key = self.cache_client.get_cache_key("legacy_summary", data_type)
            cached = self.cache_client.get(cache_key)
            if cached:
                return cached
        
        # Get data (limited sample for summary)
        data_result = await self.get_data(data_type, limit=50)
        
        if not data_result.get("success"):
            return data_result
        
        records = data_result.get("records", [])
        
        # Generate summary
        summary = await self.agent.summarize_legacy_data(data_type, records)
        
        # Cache result
        if use_cache and summary.get("success"):
            cache_key = self.cache_client.get_cache_key("legacy_summary", data_type)
            self.cache_client.set(cache_key, summary, self.cache_ttl)
        
        return summary
    
    async def get_data_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all legacy data types.
        
        Returns:
            Dictionary with data statistics
        """
        try:
            # Check cache
            cache_key = "legacy:stats"
            cached = self.cache_client.get(cache_key)
            if cached:
                return cached
            
            stats = self.db_connector.get_data_summary()
            
            result = {
                "statistics": stats,
                "total_records": sum(stats.values()),
                "success": True
            }
            
            # Cache for 5 minutes
            self.cache_client.set(cache_key, result, 300)
            
            return result
        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }


# Global service instance
legacy_service = LegacyService()
