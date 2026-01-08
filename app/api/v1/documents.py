"""
Document processing API endpoints.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.models.schemas import (
    DocumentUploadResponse,
    DocumentParseResponse,
    ErrorResponse
)
from app.services.document_service import document_service
from app.services.summarize_service import summarize_service
from datetime import datetime

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document for processing.
    
    Args:
        file: Document file to upload
        
    Returns:
        Upload result with document ID
    """
    try:
        # Read file content
        content = await file.read()
        
        # Upload and save document
        result = await document_service.upload_document(
            file_content=content,
            filename=file.filename
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Document upload failed")
            )
        
        return DocumentUploadResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            file_type=result["file_type"],
            file_size=result["file_size"],
            status=result["status"],
            created_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/parse/{document_id}", response_model=DocumentParseResponse)
async def parse_document(document_id: int):
    """
    Parse an uploaded document to extract content.
    
    Args:
        document_id: ID of the document to parse
        
    Returns:
        Parsed document content and metadata
    """
    try:
        result = await document_service.parse_document(document_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Document parsing failed")
            )
        
        return DocumentParseResponse(
            document_id=document_id,
            filename=result["filename"],
            content=result["content"],
            metadata=result["metadata"],
            parser=result["parser"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/process/{document_id}")
async def process_document(document_id: int):
    """
    Process document: parse, chunk, and generate embeddings for vector search.
    
    Args:
        document_id: ID of the document to process
        
    Returns:
        Processing result
    """
    try:
        result = await document_service.process_and_embed_document(document_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Document processing failed")
            )
        
        return {
            "document_id": document_id,
            "filename": result["filename"],
            "num_chunks": result["num_chunks"],
            "num_embeddings": result["num_embeddings"],
            "vector_stored": result.get("vector_stored", False),
            "message": "Document processed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    """
    Delete a document and its associated data.
    
    Args:
        document_id: ID of the document to delete
        
    Returns:
        Deletion result
    """
    try:
        result = document_service.delete_document(document_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Document deletion failed")
            )
        
        return {
            "document_id": document_id,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
