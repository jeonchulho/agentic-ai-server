"""
Async tasks for document processing.
"""
from typing import Dict, Any, List
from celery import Task
from app.celery_config import celery_app
from app.services.document_service import document_service
from loguru import logger


class DocumentTask(Task):
    """Base task class with error handling and retries."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=DocumentTask, name="app.tasks.document_tasks.process_document_async")
def process_document_async(self, document_id: int) -> Dict[str, Any]:
    """
    Process document asynchronously: parse, chunk, and generate embeddings.
    
    Args:
        document_id: Document ID to process
        
    Returns:
        Processing result
    """
    try:
        logger.info(f"Starting async document processing for document_id={document_id}")
        
        # Process document
        import asyncio
        result = asyncio.run(document_service.process_and_embed_document(document_id))
        
        if result.get("success"):
            logger.info(f"Successfully processed document_id={document_id}")
        else:
            logger.error(f"Failed to process document_id={document_id}: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error processing document_id={document_id}: {str(e)}")
        raise


@celery_app.task(bind=True, base=DocumentTask, name="app.tasks.document_tasks.parse_document_async")
def parse_document_async(self, document_id: int) -> Dict[str, Any]:
    """
    Parse document asynchronously.
    
    Args:
        document_id: Document ID to parse
        
    Returns:
        Parsing result
    """
    try:
        logger.info(f"Starting async document parsing for document_id={document_id}")
        
        import asyncio
        result = asyncio.run(document_service.parse_document(document_id))
        
        if result.get("success"):
            logger.info(f"Successfully parsed document_id={document_id}")
        else:
            logger.error(f"Failed to parse document_id={document_id}: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error parsing document_id={document_id}: {str(e)}")
        raise


@celery_app.task(name="app.tasks.document_tasks.batch_process_documents")
def batch_process_documents(document_ids: List[int]) -> Dict[str, Any]:
    """
    Process multiple documents in parallel.
    
    Args:
        document_ids: List of document IDs to process
        
    Returns:
        Batch processing results
    """
    try:
        logger.info(f"Starting batch processing for {len(document_ids)} documents")
        
        from celery import group
        
        # Create parallel tasks
        job = group(process_document_async.s(doc_id) for doc_id in document_ids)
        result = job.apply_async()
        
        # Wait for all tasks to complete
        results = result.get()
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        logger.info(f"Batch processing complete: {successful} succeeded, {failed} failed")
        
        return {
            "total": len(document_ids),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise
