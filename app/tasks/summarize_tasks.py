"""
Async tasks for summarization.
"""
from typing import Dict, Any, List
from celery import Task
from app.celery_config import celery_app
from app.services.summarize_service import summarize_service
from loguru import logger


class SummarizeTask(Task):
    """Base task class for summarization."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=SummarizeTask, name="app.tasks.summarize_tasks.summarize_text_async")
def summarize_text_async(self, text: str, max_length: int = None) -> Dict[str, Any]:
    """
    Summarize text asynchronously.
    
    Args:
        text: Text to summarize
        max_length: Optional maximum length
        
    Returns:
        Summarization result
    """
    try:
        logger.info(f"Starting async text summarization (length={len(text)})")
        
        import asyncio
        result = asyncio.run(summarize_service.summarize_text(text, max_length))
        
        if result.get("success"):
            logger.info("Successfully summarized text")
        else:
            logger.error(f"Failed to summarize text: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error summarizing text: {str(e)}")
        raise


@celery_app.task(bind=True, base=SummarizeTask, name="app.tasks.summarize_tasks.summarize_document_async")
def summarize_document_async(
    self,
    document_id: int,
    content: str,
    filename: str,
    max_length: int = None
) -> Dict[str, Any]:
    """
    Summarize document asynchronously.
    
    Args:
        document_id: Document ID
        content: Document content
        filename: Document filename
        max_length: Optional maximum length
        
    Returns:
        Summarization result
    """
    try:
        logger.info(f"Starting async document summarization for document_id={document_id}")
        
        import asyncio
        result = asyncio.run(
            summarize_service.summarize_document(document_id, content, filename, max_length)
        )
        
        if result.get("success"):
            logger.info(f"Successfully summarized document_id={document_id}")
        else:
            logger.error(f"Failed to summarize document_id={document_id}: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error summarizing document_id={document_id}: {str(e)}")
        raise


@celery_app.task(name="app.tasks.summarize_tasks.batch_summarize")
def batch_summarize(texts: List[str], max_length: int = None) -> Dict[str, Any]:
    """
    Summarize multiple texts in parallel.
    
    Args:
        texts: List of texts to summarize
        max_length: Optional maximum length for each summary
        
    Returns:
        Batch summarization results
    """
    try:
        logger.info(f"Starting batch summarization for {len(texts)} texts")
        
        from celery import group
        
        # Create parallel tasks
        job = group(summarize_text_async.s(text, max_length) for text in texts)
        result = job.apply_async()
        
        # Wait for all tasks to complete
        results = result.get()
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        logger.info(f"Batch summarization complete: {successful} succeeded, {failed} failed")
        
        return {
            "total": len(texts),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error in batch summarization: {str(e)}")
        raise
