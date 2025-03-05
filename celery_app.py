# celery_app.py

# Import your tasks so that Celery can discover them
import tasks
import os
from celery import Celery, Task
from app import create_app  # Import the Flask app factory

# Create the Flask app using the factory
application = create_app()

def make_celery(app):
    # Get the Redis URL from the environment or use a default value
    redis_url = "redis-13448.c280.us-central1-2.gce.redns.redis-cloud.com:13448"

    celery = Celery(
        'tasks',
        broker="redis://127.0.0.1:6379/0",   # Use Redis as the message broker
        backend="redis://127.0.0.1:6379/0",
        include=['tasks']   # Ensure Celery autodiscovers tasks in the tasks module
    )

    # Update Celery configuration with Flask's config
    celery.conf.update(app.config)
    celery.autodiscover_tasks(['tasks'])

    # Create a custom Task base that pushes the Flask app context
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask
    return celery

# Initialize the Celery object with the Flask app
celery = make_celery(application)

