web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 4 --bind 0.0.0.0:$PORT --timeout 300 --keep-alive 10 'run:app'
worker: celery -A celery_app worker --loglevel=INFO --max-memory-per-child=50000
beat: celery -A celery_app beat --loglevel=INFO
