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
    
    # Connection pool settings
    broker_pool_limit=10,  # Broker connection pool size
    broker_connection_timeout=30,  # Broker connection timeout
    broker_connection_retry=True,  # Retry on connection failure
    broker_connection_max_retries=3,  # Max retries
    result_backend_pool_limit=10,  # Result backend pool size
)

# Configure beat schedule separately after basic configuration
celery.conf.beat_schedule = {
    'daily-menu-reconciliation': {
        'task': 'app.tasks.menu_reconciliation.daily_menu_reconciliation',
        'schedule': 86400.0,  # Every 24 hours (daily) at startup time
    },
    'weekly-menu-health-check': {
        'task': 'app.tasks.menu_reconciliation.weekly_menu_health_check', 
        'schedule': 604800.0,  # Every 7 days (weekly)
    },
}

print(f"✅ Celery beat schedule configured: {list(celery.conf.beat_schedule.keys())}")

# Auto-discover tasks from the app package
celery.autodiscover_tasks(['app.tasks'])

# Simple test task
@celery.task
def test_task():
    """Simple test task to verify Celery is working"""
    return "Celery is working!"

if __name__ == "__main__":
    celery.start()