"""
Async tasks for legacy data analysis.
"""
from typing import Dict, Any
from celery import Task
from app.celery_config import celery_app
from app.services.legacy_service import legacy_service
from loguru import logger


class AnalysisTask(Task):
    """Base task class for analysis."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=AnalysisTask, name="app.tasks.analysis_tasks.analyze_legacy_data_async")
def analyze_legacy_data_async(self, data_type: str, limit: int = 100) -> Dict[str, Any]:
    """
    Analyze legacy data asynchronously.
    
    Args:
        data_type: Type of data to analyze
        limit: Maximum number of records to analyze
        
    Returns:
        Analysis result
    """
    try:
        logger.info(f"Starting async analysis for data_type={data_type}")
        
        import asyncio
        result = asyncio.run(legacy_service.analyze_data(data_type, limit))
        
        if result.get("success"):
            logger.info(f"Successfully analyzed {data_type} data")
        else:
            logger.error(f"Failed to analyze {data_type} data: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing {data_type} data: {str(e)}")
        raise
