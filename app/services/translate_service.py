"""
Translation service layer.
"""
from typing import Dict, Any
from app.agents.translate_agent import translate_agent
from app.database.mysql_client import mysql_client, Translation
from app.database.redis_client import redis_client
from datetime import datetime


class TranslateService:
    """Service for text translation."""
    
    def __init__(self):
        """Initialize service."""
        self.agent = translate_agent
        self.db_client = mysql_client
        self.cache_client = redis_client
        self.cache_ttl = 3600  # 1 hour cache
    
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Translate text with caching.
        
        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code
            use_cache: Whether to use cache
            
        Returns:
            Dictionary with translation result
        """
        # Check cache
        if use_cache:
            cache_key = self.cache_client.get_cache_key(
                "translation", text[:100], source_language, target_language
            )
            cached = self.cache_client.get(cache_key)
            if cached:
                return cached
        
        # Perform translation
        result = await self.agent.translate(text, source_language, target_language)
        
        if result.get("success"):
            # Save to database
            session = self.db_client.get_session()
            try:
                translation_record = Translation(
                    source_text=text,
                    source_language=source_language,
                    target_language=target_language,
                    translated_text=result["translated_text"],
                    created_at=datetime.utcnow()
                )
                session.add(translation_record)
                session.commit()
                
                result["translation_id"] = translation_record.id
            except Exception as e:
                session.rollback()
                print(f"Failed to save translation to database: {e}")
            finally:
                session.close()
            
            # Cache result
            if use_cache:
                self.cache_client.set(cache_key, result, self.cache_ttl)
        
        return result
    
    async def detect_and_translate(
        self,
        text: str,
        target_language: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Detect source language and translate.
        
        Args:
            text: Text to translate
            target_language: Target language code
            use_cache: Whether to use cache
            
        Returns:
            Dictionary with translation result
        """
        # Check cache
        if use_cache:
            cache_key = self.cache_client.get_cache_key(
                "auto_translation", text[:100], target_language
            )
            cached = self.cache_client.get(cache_key)
            if cached:
                return cached
        
        # Perform translation with auto-detection
        result = await self.agent.detect_and_translate(text, target_language)
        
        if result.get("success"):
            # Save to database
            session = self.db_client.get_session()
            try:
                translation_record = Translation(
                    source_text=text,
                    source_language=result.get("source_language", "auto"),
                    target_language=target_language,
                    translated_text=result["translated_text"],
                    created_at=datetime.utcnow()
                )
                session.add(translation_record)
                session.commit()
                
                result["translation_id"] = translation_record.id
            except Exception as e:
                session.rollback()
                print(f"Failed to save translation to database: {e}")
            finally:
                session.close()
            
            # Cache result
            if use_cache:
                self.cache_client.set(cache_key, result, self.cache_ttl)
        
        return result


# Global service instance
translate_service = TranslateService()
