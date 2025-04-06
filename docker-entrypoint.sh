#!/bin/bash
set -e

# Expand environment variables in the SQLALCHEMY_DATABASE_URI
if [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] && [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] && [ -n "$DB_NAME" ]; then
    export SQLALCHEMY_DATABASE_URI="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "Database URI set to postgresql connection string (credentials hidden)"
fi

# Initialize database if needed
echo "Creating database tables if they don't exist..."
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
"

# Determine which process to start based on the PROCESS environment variable
# This allows us to run the web server or Celery worker with the same Docker image
if [ "$PROCESS" = "celery" ]; then
    echo "Starting Celery worker..."
    exec celery -A celery_app worker --loglevel=INFO
elif [ "$PROCESS" = "celery-beat" ]; then
    echo "Starting Celery beat scheduler..."
    exec celery -A celery_app beat --loglevel=INFO
else
    # Default: start the web server
    echo "Starting web server on port $PORT..."
    # Use gunicorn with gevent worker for websocket support
    exec gunicorn --worker-class=gevent --workers=3 --threads=3 --bind="0.0.0.0:$PORT" --log-level=info "run:app"
fi