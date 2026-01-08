"""
Summarization service layer.
"""
from typing import Dict, Any, Optional
from app.agents.summarize_agent import summarize_agent
from app.database.mysql_client import mysql_client, Summary
from app.database.redis_client import redis_client
from datetime import datetime


class SummarizeService:
    """Service for text and document summarization."""
    
    def __init__(self):
        """Initialize service."""
        self.agent = summarize_agent
        self.db_client = mysql_client
        self.cache_client = redis_client
        self.cache_ttl = 3600  # 1 hour cache
    
    async def summarize_text(
        self,
        text: str,
        max_length: Optional[int] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Summarize text with caching.
        
        Args:
            text: Text to summarize
            max_length: Optional maximum length for summary
            use_cache: Whether to use cache
            
        Returns:
            Dictionary with summary result
        """
        # Check cache
        if use_cache:
            cache_key = self.cache_client.get_cache_key("summary", text[:100], str(max_length))
            cached = self.cache_client.get(cache_key)
            if cached:
                return cached
        
        # Generate summary
        result = await self.agent.summarize_text(text, max_length)
        
        if result.get("success"):
            # Save to database
            session = self.db_client.get_session()
            try:
                summary_record = Summary(
                    source_type="text",
                    content=text[:1000],  # Store first 1000 chars
                    summary=result["summary"],
                    created_at=datetime.utcnow()
                )
                session.add(summary_record)
                session.commit()
                
                result["summary_id"] = summary_record.id
            except Exception as e:
                session.rollback()
                print(f"Failed to save summary to database: {e}")
            finally:
                session.close()
            
            # Cache result
            if use_cache:
                self.cache_client.set(cache_key, result, self.cache_ttl)
        
        return result
    
    async def summarize_document(
        self,
        document_id: int,
        content: str,
        filename: str,
        max_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Summarize document content.
        
        Args:
            document_id: Document ID
            content: Document content
            filename: Document filename
            max_length: Optional maximum length for summary
            
        Returns:
            Dictionary with summary result
        """
        # Check cache
        cache_key = self.cache_client.get_cache_key("doc_summary", str(document_id))
        cached = self.cache_client.get(cache_key)
        if cached:
            return cached
        
        # Generate summary
        result = await self.agent.summarize_document(content, filename, max_length)
        
        if result.get("success"):
            # Save to database
            session = self.db_client.get_session()
            try:
                summary_record = Summary(
                    source_type="document",
                    source_id=str(document_id),
                    content=content[:1000],
                    summary=result["summary"],
                    created_at=datetime.utcnow()
                )
                session.add(summary_record)
                session.commit()
                
                result["summary_id"] = summary_record.id
                result["document_id"] = document_id
            except Exception as e:
                session.rollback()
                print(f"Failed to save summary to database: {e}")
            finally:
                session.close()
            
            # Cache result
            self.cache_client.set(cache_key, result, self.cache_ttl)
        
        return result


# Global service instance
summarize_service = SummarizeService()
