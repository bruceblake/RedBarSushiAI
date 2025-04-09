web: gunicorn --worker-class=gevent --workers=1 --threads=4 'run:app'
worker: celery -A celery_app worker --loglevel=INFO --max-memory-per-child=50000
beat: celery -A celery_app beat --loglevel=INFO
