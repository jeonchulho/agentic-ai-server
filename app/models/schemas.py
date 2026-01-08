"""
Pydantic models for API requests and responses.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SummarizeTextRequest(BaseModel):
    """Request model for text summarization."""
    text: str = Field(..., description="Text to summarize")
    max_length: Optional[int] = Field(None, description="Maximum length of summary")
    language: Optional[str] = Field("auto", description="Language of the text")


class SummarizeTextResponse(BaseModel):
    """Response model for text summarization."""
    original_text: str
    summary: str
    language: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TranslateRequest(BaseModel):
    """Request model for translation."""
    text: str = Field(..., description="Text to translate")
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'ko')")
    target_language: str = Field(..., description="Target language code (e.g., 'en', 'ko')")


class TranslateResponse(BaseModel):
    """Response model for translation."""
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime


class DocumentParseResponse(BaseModel):
    """Response model for document parsing."""
    document_id: int
    filename: str
    content: str
    metadata: Dict[str, Any]
    parser: str


class DocumentSummaryRequest(BaseModel):
    """Request model for document summarization."""
    document_id: Optional[int] = None
    max_length: Optional[int] = None


class DocumentSummaryResponse(BaseModel):
    """Response model for document summarization."""
    document_id: int
    filename: str
    summary: str
    created_at: datetime


class LegacyDataRequest(BaseModel):
    """Request model for legacy data analysis."""
    data_type: str = Field(..., description="Type of legacy data (messages, chats, schedules, emails, projects)")
    limit: Optional[int] = Field(100, description="Maximum number of records to retrieve")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class LegacyDataResponse(BaseModel):
    """Response model for legacy data retrieval."""
    data_type: str
    records: List[Dict[str, Any]]
    count: int


class LegacySummaryResponse(BaseModel):
    """Response model for legacy data summary."""
    data_type: str
    summary: str
    record_count: int
    created_at: datetime


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    services: Dict[str, bool]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
