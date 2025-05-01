# celery_app.py

import os
from celery import Celery, Task
from app import create_app  # Import the Flask app factory

# Create the Flask app using the factory
application = create_app()


def make_celery(app):
    # Get the Redis URL from the environment or use a default value
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # Fix malformed Redis URLs that might be coming from Render
    if broker_url:
        # Special handling for Render's format (red-cvp9ic3e5dus73cd1uq0:6379/0)
        if ":" in broker_url and not broker_url.startswith("redis://"):
            if broker_url.count(":") == 1 and "/" in broker_url:
                # Format appears to be hostname:port/db
                host_port, db = broker_url.rsplit("/", 1)
                host, port = host_port.split(":")
                # Make sure we have a valid DB number
                try:
                    db_num = int(db)
                except ValueError:
                    db_num = 0
                # Reconstruct proper Redis URL
                broker_url = f"redis://{host}:{port}/{db_num}"
            else:
                # Just prefix with redis://
                broker_url = f"redis://{broker_url}"

        # Ensure the URL has the proper redis:// prefix
        if not broker_url.startswith("redis://"):
            broker_url = f"redis://{broker_url}"

        try:
            # Print the broker URL for debugging
            print(f"Using broker URL: {broker_url}")

            # Import Redis for validation (but catch import errors)
            try:
                import redis.utils

                # This will validate the URL format or raise appropriate exceptions
                parsed = redis.utils.from_url(broker_url)
            except (ImportError, AttributeError):
                # If redis.utils doesn't exist or doesn't have from_url, continue anyway
                pass
        except Exception as e:
            # If there's any error, default to localhost
            print(f"Error parsing Redis URL: {e}")
            broker_url = "redis://localhost:6379/0"

    # Apply the same fixes to result_backend
    if result_backend:
        # Special handling for Render's format (red-cvp9ic3e5dus73cd1uq0:6379/0)
        if ":" in result_backend and not result_backend.startswith("redis://"):
            if result_backend.count(":") == 1 and "/" in result_backend:
                # Format appears to be hostname:port/db
                host_port, db = result_backend.rsplit("/", 1)
                host, port = host_port.split(":")
                # Make sure we have a valid DB number
                try:
                    db_num = int(db)
                except ValueError:
                    db_num = 0
                # Reconstruct proper Redis URL
                result_backend = f"redis://{host}:{port}/{db_num}"
            else:
                # Just prefix with redis://
                result_backend = f"redis://{result_backend}"

        # Ensure the URL has the proper redis:// prefix
        if not result_backend.startswith("redis://"):
            result_backend = f"redis://{result_backend}"

        try:
            # Print the result backend URL for debugging
            print(f"Using result backend URL: {result_backend}")

            # Import Redis for validation (but catch import errors)
            try:
                import redis.utils

                # This will validate the URL format or raise appropriate exceptions
                parsed = redis.utils.from_url(result_backend)
            except (ImportError, AttributeError):
                # If redis.utils doesn't exist or doesn't have from_url, continue anyway
                pass
        except Exception as e:
            # If there's any error, default to localhost
            print(f"Error parsing Redis URL: {e}")
            result_backend = "redis://localhost:6379/0"

    celery = Celery("tasks", broker=broker_url, backend=result_backend)

    # Update Celery configuration with Flask's config
    celery.conf.update(app.config)

    # Set task module name
    celery.conf.imports = ("tasks",)

    # Memory management settings
    celery.conf.worker_max_memory_per_child = 50000  # 50MB per worker
    celery.conf.worker_max_tasks_per_child = 10  # Restart worker after 10 tasks
    celery.conf.task_time_limit = 600  # 10 minute hard time limit
    celery.conf.task_soft_time_limit = 300  # 5 minute soft time limit

    # Set up periodic tasks
    celery.conf.beat_schedule = {
        "sync-menu-references-every-hour": {
            "task": "tasks.sync_menu_references",
            "schedule": 3600.0,  # Run every hour
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
