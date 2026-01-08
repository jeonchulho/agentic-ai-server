"""
Summarization API endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    SummarizeTextRequest,
    SummarizeTextResponse,
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    ErrorResponse
)
from app.services.summarize_service import summarize_service
from datetime import datetime

router = APIRouter()


@router.post("/summarize/text", response_model=SummarizeTextResponse)
async def summarize_text(request: SummarizeTextRequest):
    """
    Summarize plain text.
    
    Args:
        request: Text summarization request
        
    Returns:
        Summarization result
    """
    try:
        result = await summarize_service.summarize_text(
            text=request.text,
            max_length=request.max_length
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Summarization failed")
            )
        
        return SummarizeTextResponse(
            original_text=request.text,
            summary=result["summary"],
            language=request.language,
            created_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize/document", response_model=DocumentSummaryResponse)
async def summarize_document(request: DocumentSummaryRequest):
    """
    Summarize an uploaded document.
    
    Args:
        request: Document summarization request
        
    Returns:
        Document summarization result
    """
    try:
        if not request.document_id:
            raise HTTPException(status_code=400, detail="document_id is required")
        
        # Get document from database
        from app.database.mysql_client import mysql_client, Document as DocumentModel
        
        session = mysql_client.get_session()
        try:
            doc_record = session.query(DocumentModel).filter(
                DocumentModel.id == request.document_id
            ).first()
            
            if not doc_record:
                raise HTTPException(status_code=404, detail="Document not found")
            
            content = doc_record.parsed_content
            if not content:
                raise HTTPException(
                    status_code=400,
                    detail="Document has not been parsed yet"
                )
            
            # Summarize document
            result = await summarize_service.summarize_document(
                document_id=request.document_id,
                content=content,
                filename=doc_record.filename,
                max_length=request.max_length
            )
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Document summarization failed")
                )
            
            return DocumentSummaryResponse(
                document_id=request.document_id,
                filename=doc_record.filename,
                summary=result["summary"],
                created_at=datetime.utcnow()
            )
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
