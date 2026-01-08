"""
Legacy database API endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    LegacyDataRequest,
    LegacyDataResponse,
    LegacySummaryResponse,
    ErrorResponse
)
from app.services.legacy_service import legacy_service
from datetime import datetime

router = APIRouter()


@router.post("/legacy/data", response_model=LegacyDataResponse)
async def get_legacy_data(request: LegacyDataRequest):
    """
    Retrieve legacy database data by type.
    
    Args:
        request: Legacy data request
        
    Returns:
        Legacy data records
    """
    try:
        result = await legacy_service.get_data(
            data_type=request.data_type,
            limit=request.limit,
            offset=request.offset
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to retrieve legacy data")
            )
        
        return LegacyDataResponse(
            data_type=request.data_type,
            records=result["records"],
            count=result["count"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/legacy/summary/{data_type}", response_model=LegacySummaryResponse)
async def get_legacy_summary(
    data_type: str,
    use_cache: bool = Query(True, description="Use cached summary if available")
):
    """
    Get summary of legacy data by type.
    
    Args:
        data_type: Type of legacy data (messages, chats, schedules, emails, projects)
        use_cache: Whether to use cached summary
        
    Returns:
        Summary of legacy data
    """
    try:
        # Validate data type
        valid_types = ["messages", "chats", "schedules", "emails", "projects"]
        if data_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid data_type. Must be one of: {', '.join(valid_types)}"
            )
        
        result = await legacy_service.get_summary(
            data_type=data_type,
            use_cache=use_cache
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to generate summary")
            )
        
        return LegacySummaryResponse(
            data_type=data_type,
            summary=result["summary"],
            record_count=result["record_count"],
            created_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/legacy/analyze")
async def analyze_legacy_data(request: LegacyDataRequest):
    """
    Analyze legacy database data and provide insights.
    
    Args:
        request: Legacy data request
        
    Returns:
        Analysis results with insights
    """
    try:
        result = await legacy_service.analyze_data(
            data_type=request.data_type,
            limit=request.limit
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to analyze legacy data")
            )
        
        return {
            "data_type": result["data_type"],
            "record_count": result["record_count"],
            "analysis": result["analysis"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/legacy/statistics")
async def get_legacy_statistics():
    """
    Get statistics for all legacy data types.
    
    Returns:
        Statistics for all data types
    """
    try:
        result = await legacy_service.get_data_statistics()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to retrieve statistics")
            )
        
        return {
            "statistics": result["statistics"],
            "total_records": result["total_records"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
