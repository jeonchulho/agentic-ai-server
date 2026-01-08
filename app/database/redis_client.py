"""
Redis client for caching and session management.
"""
import json
from typing import Optional, Any
import redis
from app.config import get_settings

settings = get_settings()


class RedisClient:
    """Redis client wrapper for caching operations."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, expiration: int = 3600) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expiration: Expiration time in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            serialized = json.dumps(value)
            return self.client.setex(key, expiration, serialized)
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if exists, False otherwise
        """
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False
    
    def flush_db(self):
        """Flush all keys from current database."""
        try:
            self.client.flushdb()
        except Exception as e:
            print(f"Redis flush error: {e}")
    
    def ping(self) -> bool:
        """
        Check if Redis is available.
        
        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            return self.client.ping()
        except Exception as e:
            print(f"Redis ping error: {e}")
            return False
    
    def close(self):
        """Close Redis connection."""
        try:
            self.client.close()
        except Exception as e:
            print(f"Redis close error: {e}")
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """
        Generate cache key with prefix and arguments.
        
        Args:
            prefix: Cache key prefix
            *args: Additional key components
            
        Returns:
            Generated cache key
        """
        parts = [prefix] + [str(arg) for arg in args]
        return ":".join(parts)


# Global client instance
redis_client = RedisClient()
