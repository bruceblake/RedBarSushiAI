# celery_app_fastapi.py
"""
Celery configuration for FastAPI application
"""

import os
from celery import Celery

# Get Redis configuration from environment
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Create Celery instance
celery = Celery(
    "redbarsushi",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery configuration
celery.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Worker settings
    worker_max_memory_per_child=200000,  # 200MB
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    
    # Time limits
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=300,  # 5 minutes
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Beat schedule (if using celery beat)
    beat_schedule={
        # Add periodic tasks here if needed
        # 'example-task': {
        #     'task': 'app.tasks.example_task',
        #     'schedule': 300.0,  # Every 5 minutes
        # },
    }
)

# Auto-discover tasks from the app package
# Commented out for now - will enable when app structure is ready
# celery.autodiscover_tasks(['app'])

# Simple test task
@celery.task
def test_task():
    """Simple test task to verify Celery is working"""
    return "Celery is working!"

if __name__ == "__main__":
    celery.start()