"""
Celery configuration for async task processing.
"""
from celery import Celery
from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "agentic_ai_tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    include=[
        "app.tasks.document_tasks",
        "app.tasks.summarize_tasks",
        "app.tasks.translate_tasks",
        "app.tasks.analysis_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,  # Results expire after 24 hours
    broker_connection_retry_on_startup=True,
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.document_tasks.*": {"queue": "documents"},
    "app.tasks.summarize_tasks.*": {"queue": "summarize"},
    "app.tasks.translate_tasks.*": {"queue": "translate"},
    "app.tasks.analysis_tasks.*": {"queue": "analysis"},
}

# Priority queues configuration
celery_app.conf.task_default_priority = 5
celery_app.conf.broker_transport_options = {
    "priority_steps": [0, 3, 6, 9],
}
