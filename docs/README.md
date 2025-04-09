# RedBarSushiAI Documentation

This directory contains documentation for the RedBarSushiAI system.

## Main Documentation Files

- [DOCUMENTATION.md](../DOCUMENTATION.md) - Comprehensive system documentation
- [DELIVERECT_INTEGRATION.md](../DELIVERECT_INTEGRATION.md) - Deliverect integration details
- [OPTIMIZATIONS.md](../OPTIMIZATIONS.md) - Performance optimizations
- [REALTIME_AUDIO.md](../REALTIME_AUDIO.md) - Real-time audio processing documentation
- [SMS_FIX.md](../SMS_FIX.md) - SMS system fixes and improvements

## Development Workflow

1. The `main` branch is the production branch
2. The `development` branch is for ongoing development work
3. Feature branches should be created from `development`
4. Submit pull requests to merge features into `development`
5. Periodically, `development` will be merged into `main` for production releases

## Running in Development Mode

```bash
# Start the development server with debug enabled
FLASK_DEBUG=1 FLASK_APP=run.py flask run

# Run Celery worker
celery -A celery_app worker --loglevel=INFO
```

## Testing

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_file.py

# Run a specific test function
pytest tests/test_file.py::test_function
```

## Docker Deployment

```bash
# Build the Docker image
docker-compose build

# Start the services
docker-compose up -d

# View logs
docker-compose logs -f
```