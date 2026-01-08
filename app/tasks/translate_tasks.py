"""
Async tasks for translation.
"""
from typing import Dict, Any, List
from celery import Task
from app.celery_config import celery_app
from app.services.translate_service import translate_service
from loguru import logger


class TranslateTask(Task):
    """Base task class for translation."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=TranslateTask, name="app.tasks.translate_tasks.translate_text_async")
def translate_text_async(
    self,
    text: str,
    source_language: str,
    target_language: str
) -> Dict[str, Any]:
    """
    Translate text asynchronously.
    
    Args:
        text: Text to translate
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        Translation result
    """
    try:
        logger.info(f"Starting async translation ({source_language} -> {target_language})")
        
        import asyncio
        result = asyncio.run(
            translate_service.translate(text, source_language, target_language)
        )
        
        if result.get("success"):
            logger.info("Successfully translated text")
        else:
            logger.error(f"Failed to translate text: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        raise


@celery_app.task(name="app.tasks.translate_tasks.batch_translate")
def batch_translate(
    texts: List[str],
    source_language: str,
    target_language: str
) -> Dict[str, Any]:
    """
    Translate multiple texts in parallel.
    
    Args:
        texts: List of texts to translate
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        Batch translation results
    """
    try:
        logger.info(f"Starting batch translation for {len(texts)} texts")
        
        from celery import group
        
        # Create parallel tasks
        job = group(
            translate_text_async.s(text, source_language, target_language)
            for text in texts
        )
        result = job.apply_async()
        
        # Wait for all tasks to complete
        results = result.get()
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        logger.info(f"Batch translation complete: {successful} succeeded, {failed} failed")
        
        return {
            "total": len(texts),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error in batch translation: {str(e)}")
        raise
