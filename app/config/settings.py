"""
Application configuration settings.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "agentic_ai"
    
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Milvus Configuration
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_NAME: str = "documents"
    
    # LLM Configuration
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Legacy Database Configuration
    LEGACY_DB_HOST: str = "localhost"
    LEGACY_DB_PORT: int = 3306
    LEGACY_DB_USER: str = "legacy_user"
    LEGACY_DB_PASSWORD: str = "legacy_password"
    LEGACY_DB_NAME: str = "legacy_db"
    
    # Application Settings
    API_VERSION: str = "v1"
    APP_NAME: str = "Agentic AI Server"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "/tmp/uploads"
    
    # Worker Settings
    MAX_WORKERS: int = 4
    ASYNC_QUEUE_SIZE: int = 100
    
    @property
    def mysql_url(self) -> str:
        """Generate MySQL connection URL."""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    @property
    def legacy_db_url(self) -> str:
        """Generate Legacy DB connection URL."""
        return f"mysql+pymysql://{self.LEGACY_DB_USER}:{self.LEGACY_DB_PASSWORD}@{self.LEGACY_DB_HOST}:{self.LEGACY_DB_PORT}/{self.LEGACY_DB_NAME}"
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
