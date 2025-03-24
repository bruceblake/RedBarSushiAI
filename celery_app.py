# celery_app.py

import os
from celery import Celery, Task
from app import create_app  # Import the Flask app factory

# Create the Flask app using the factory
application = create_app()

def make_celery(app):
    # Get the Redis URL from the environment or use a default value

    celery = Celery(
        "tasks" ,
        broker="amqps://mvfujzvj:qJH0m03hRpaG31WqfMoU4enFbI_z28z_@horse.lmq.cloudamqp.com/mvfujzvj",

    )

    # Update Celery configuration with Flask's config
    celery.conf.update(app.config)
    
    # Set task module name
    celery.conf.imports = ('tasks',)
    
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

