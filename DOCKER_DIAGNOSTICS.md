# Docker Diagnostics for RedBarSushiAI

This document describes tools and techniques to diagnose and fix issues with the Docker environment for RedBarSushiAI.

## Common Issues and Solutions

### Pydantic Version Compatibility Issues

The codebase works with Pydantic v1.x, but Docker environments might have Pydantic v2.x installed, which causes import errors related to `BaseSettings`.

**Symptoms:**
- Error messages about `BaseSettings` being moved to `pydantic-settings`
- Imports failing in `app/config.py` or `app/db_async.py`

**Solutions:**
1. **Pin Pydantic Version:** In the Docker container, install Pydantic v1.10.13:
   ```bash
   pip install pydantic==1.10.13
   ```

2. **Use Compatibility Layer:** The updated `app/config.py` now has a compatibility layer that tries to import from both Pydantic v1 and v2.

3. **Use Simplified Main:** For extreme cases, use the simplified diagnostic main.py:
   ```bash
   python docker/main_simplified.py
   ```

### Database Connection Issues

**Symptoms:**
- Errors related to database initialization
- Connection refused errors

**Solutions:**
1. **Check Database URL:** Ensure `DATABASE_URL` environment variable is correctly set.
2. **Verify Database Service:** Make sure PostgreSQL container is running and healthy.
3. **Use Fallback:** The updated `app/db_async.py` now has a fallback mechanism to use environment variables directly if the config import fails.

## Diagnostic Tools

### Simplified Main Application

`docker/main_simplified.py` is a minimal FastAPI application that:
- Sets up proper logging
- Tests key imports (FastAPI, Pydantic)
- Provides basic HTTP and WebSocket endpoints
- Doesn't require database initialization

It's useful for isolating whether the issue is with imports/dependencies or with database initialization.

### Development Dockerfile

`docker/images/Dockerfile.dev` includes:
- Pinned version of Pydantic (v1.10.13)
- Additional debugging tools
- Compatibility with both Pydantic v1 and v2

### Development Docker Compose

`docker-compose.development.yml` provides:
- Isolated development environment
- Better logging
- Simplified startup command

## Using the Diagnostic Tools

### Starting Diagnostics Mode

```bash
# Use the development docker-compose file
docker-compose -f docker-compose.development.yml up
```

### Checking Pydantic Version

```bash
docker exec -it redbarsushi-app-dev pip show pydantic
```

### Manually Installing Pydantic v1

```bash
docker exec -it redbarsushi-app-dev pip install pydantic==1.10.13
```

### Running the Simplified Main

```bash
docker exec -it redbarsushi-app-dev python docker/main_simplified.py
```

## Troubleshooting Steps

1. **Check Container Logs:**
   ```bash
   docker logs redbarsushi-app-dev
   ```

2. **Enter Container Shell:**
   ```bash
   docker exec -it redbarsushi-app-dev bash
   ```

3. **Check Python Environment:**
   ```bash
   pip list | grep pydantic
   python -c "import pydantic; print(pydantic.__version__)"
   ```

4. **Test Database Connection:**
   ```bash
   python -c "import psycopg2; conn = psycopg2.connect('postgresql://postgres:postgres@postgres:5432/redbarsushi'); print('Connected!')"
   ```

5. **Test Config Import:**
   ```python
   python -c "from app.config import settings; print(f'Database URL: {settings.DATABASE_URL}')"
   ```