# Render Deployment Fixes for FastAPI Migration

This document details the fixes applied to make the FastAPI application deploy correctly on Render.

## Issues Diagnosed

### Issue 1: Pydantic BaseSettings Import Error

The first deployment was failing with a pydantic-related error:

```
ERROR: App initialization failed: `BaseSettings` has been moved to the `pydantic-settings` package. 
See https://docs.pydantic.dev/2.10/migration/#basesettings-has-moved-to-pydantic-settings for more details.
```

This was due to:
1. Using pydantic v2.x which moved `BaseSettings` to a separate package
2. Our code was still importing `BaseSettings` directly from `pydantic`

### Issue 2: Dependency Conflict

Attempting to use both pydantic v1 and pydantic-settings created a dependency conflict:

```
ERROR: Cannot install fastapi==0.115.11, pydantic-settings==2.0.3 and pydantic==1.10.8 because these package versions have conflicting dependencies.

The conflict is caused by:
    The user requested pydantic==1.10.8
    fastapi 0.115.11 depends on pydantic!=1.8, !=1.8.1, !=2.0.0, !=2.0.1, !=2.1.0, <3.0.0 and >=1.7.4
    pydantic-settings 2.0.3 depends on pydantic>=2.0.1
```

This was due to pydantic-settings requiring pydantic v2, which would break our BaseSettings imports.

## Changes Made

### 1. Standardized on Pydantic v1 for BaseSettings

Updated app/config.py to use pydantic v1 directly:

```python
# Import directly from pydantic v1
from pydantic import BaseSettings, Field, validator, AnyHttpUrl
```

This approach ensures consistent behavior without trying to use pydantic-settings compatibility layer.

### 2. Created a Root Dockerfile

Created a Dockerfile in the project root that Render can detect automatically, with:
- Multi-stage build for faster deployment
- Proper dependency installation with fallbacks
- Configuration for FastAPI and Uvicorn
- Specific pydantic v1.10.8 installation to ensure BaseSettings compatibility
- Explicit installation of required packages

### 3. Created a FastAPI-specific Render Entrypoint

Wrote `fastapi_render_entrypoint.sh` with:
- Proper environment variable setup
- Database initialization for FastAPI
- Dependency checks with auto-installation
- Error handling for pydantic version mismatches
- FastAPI app initialization testing
- Proper Uvicorn startup configuration

### 4. Created Requirements File for FastAPI

Added `requirements-fastapi.txt` with:
- FastAPI and ASGI server dependencies
- Pydantic v1.10.8 (compatible version that includes BaseSettings)
- Removed pydantic-settings to avoid dependency conflicts
- All other required dependencies with exact versions

### 5. Updated render.yaml Configuration

Modified `render.yaml` to:
- Use Docker runtime instead of Python runtime
- Add FASTAPI_ENV alongside FLASK_ENV
- Use the proper Dockerfile path
- Configure environment variables correctly

## How to Deploy

1. Push these changes to the staging branch
2. Render will automatically detect the Dockerfile and build using it
3. The entrypoint script handles dependency installation and app startup
4. Environment variables from Render are passed through to the application

## Testing the Deployment

1. Check the Render logs for successful startup
2. Visit the `/healthcheck` endpoint to verify all components are working
3. Test the voice endpoint to ensure TwiML generation works properly
4. Verify database connectivity with the menu-check endpoint