# celery_app.py

import os
from celery import Celery, Task
from app import create_app  # Import the Flask app factory

# Create the Flask app using the factory
application = create_app()

def make_celery(app):
    # Get the Redis URL from the environment or use a default value
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Fix malformed Redis URLs that might be coming from Render
    if broker_url:
        # First, ensure the URL has the proper redis:// prefix
        if not broker_url.startswith('redis://'):
            broker_url = f"redis://{broker_url}"
        
        # Next, fix the DB number format if needed
        try:
            import redis.utils
            # This will validate the URL format or raise appropriate exceptions
            parsed = redis.utils.from_url(broker_url)
        except ValueError:
            # If there's an error parsing, it might be due to the DB format
            # Try to fix common issues with Render-provided Redis URLs
            parts = broker_url.split('/')
            if len(parts) >= 4:  # redis://hostname:port/db
                # Ensure the database is a simple number
                host_part = '/'.join(parts[:-1])
                db_part = parts[-1].split(':')[0]  # Remove any additional parameters
                try:
                    db_num = int(db_part)
                    broker_url = f"{host_part}/{db_num}"
                except ValueError:
                    # If we can't convert to int, default to DB 0
                    broker_url = f"{host_part}/0"
    
    # Apply the same fixes to result_backend
    if result_backend:
        # First, ensure the URL has the proper redis:// prefix
        if not result_backend.startswith('redis://'):
            result_backend = f"redis://{result_backend}"
        
        # Next, fix the DB number format if needed
        try:
            import redis.utils
            # This will validate the URL format or raise appropriate exceptions
            parsed = redis.utils.from_url(result_backend)
        except ValueError:
            # If there's an error parsing, it might be due to the DB format
            # Try to fix common issues with Render-provided Redis URLs
            parts = result_backend.split('/')
            if len(parts) >= 4:  # redis://hostname:port/db
                # Ensure the database is a simple number
                host_part = '/'.join(parts[:-1])
                db_part = parts[-1].split(':')[0]  # Remove any additional parameters
                try:
                    db_num = int(db_part)
                    result_backend = f"{host_part}/{db_num}"
                except ValueError:
                    # If we can't convert to int, default to DB 0
                    result_backend = f"{host_part}/0"

    celery = Celery(
        "tasks",
        broker=broker_url,
        backend=result_backend
    )

    # Update Celery configuration with Flask's config
    celery.conf.update(app.config)
    
    # Set task module name
    celery.conf.imports = ('tasks',)
    
    # Memory management settings
    celery.conf.worker_max_memory_per_child = 50000  # 50MB per worker
    celery.conf.worker_max_tasks_per_child = 10  # Restart worker after 10 tasks
    celery.conf.task_time_limit = 600  # 10 minute hard time limit
    celery.conf.task_soft_time_limit = 300  # 5 minute soft time limit
    
    # Set up periodic tasks
    celery.conf.beat_schedule = {
        'sync-menu-references-every-hour': {
            'task': 'tasks.sync_menu_references',
            'schedule': 3600.0,  # Run every hour
        }
    }

    # Create a custom Task base that pushes the Flask app context
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask
    return celery

# Initialize the Celery object with the Flask app
celery = make_celery(application)

