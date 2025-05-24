web: uvicorn main:app --host 0.0.0.0 --port $PORT --workers 4 --log-level info
worker: celery -A celery_app worker --loglevel=INFO --max-memory-per-child=50000
beat: celery -A celery_app beat --loglevel=INFO