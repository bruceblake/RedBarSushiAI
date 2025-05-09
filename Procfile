web: FLASK_SKIP_DOTENV=1 WEB_CONCURRENCY=4 gunicorn -k gevent -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 --graceful-timeout 60 --max-requests 200 --max-requests-jitter 50 'wsgi:app'
worker: celery -A celery_app worker --loglevel=INFO --max-memory-per-child=50000
beat: celery -A celery_app beat --loglevel=INFO
