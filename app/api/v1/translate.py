"""
Translation API endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    TranslateRequest,
    TranslateResponse,
    ErrorResponse
)
from app.services.translate_service import translate_service
from datetime import datetime

router = APIRouter()


@router.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    """
    Translate text from source language to target language.
    
    Args:
        request: Translation request
        
    Returns:
        Translation result
    """
    try:
        result = await translate_service.translate(
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Translation failed")
            )
        
        return TranslateResponse(
            source_text=request.text,
            translated_text=result["translated_text"],
            source_language=request.source_language,
            target_language=request.target_language,
            created_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
