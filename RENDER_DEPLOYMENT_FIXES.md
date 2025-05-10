# Render Deployment Fixes for FastAPI Migration

This document details the fixes applied to make the FastAPI application deploy correctly on Render.

## Latest Fixes (May 9, 2025)

### Additional Fixes

1. **Missing BASE_URL Import in locations.py**:
   - The locations.py module was trying to import BASE_URL directly from app.config
   - Changed to import the settings object and access via settings.BASE_URL
   - Updated fix_render_deploy.sh to include this fix

2. **Missing DELIVERECT_API_URL in Settings Model**:
   - Added DELIVERECT_API_URL field to the Settings class
   - Set default value to 'https://api.staging.deliverect.com/v2/orders'
   - Added fallback value in settings initialization
   - Added to .env file with placeholder value

3. **Systematic Fix for Direct Imports from app.config**:
   - Created a `fix_config_imports.py` script to automatically fix all direct imports from app.config
   - The script finds and fixes any file with `from app.config import VARIABLE` patterns
   - Changes them to `from app.config import settings` and updates variable usage
   - Integrated this script into fix_render_deploy.sh to fix all similar issues

4. **Environment Variables Needed in Render**:
   - Added DELIVERECT_API_URL to the list of required variables
   - Updated fix_render_deploy.sh to include this in placeholder values
   - Ensured all necessary variables are covered in both settings class and fallback values

### Issues Fixed

1. **Function Name Mismatch in Database Initialization**:
   - `init_db()` was being imported from `app.db_async`, but the actual function name is `init_database()`
   - Fixed by updating imports and function calls in `main.py`

2. **Redis Async Module Syntax Error**:
   - `redis_async.py` had a syntax error with `global _memory_cache, _memory_cache_timestamps` being used after variables were already in use
   - Fixed by replacing with direct cache clearing method that avoids the global declaration

3. **Circular Import in Database Module**:
   - `app/db.py` was importing `from app import db as _db` which created a circular import
   - Fixed by directly instantiating SQLAlchemy with `from flask_sqlalchemy import SQLAlchemy; _db = SQLAlchemy()`

4. **SQLAlchemy Model Compatibility Issues**:
   - Models using Flask-SQLAlchemy style `db.Model`, `db.Column`, and `db.func` were incompatible with SQLAlchemy 2.0 async approach
   - Created a compatibility layer in `compat_models.py` that bridges Flask-SQLAlchemy syntax to SQLAlchemy 2.0
   - Updated model imports to use this compatibility layer instead of direct Flask-SQLAlchemy imports

5. **Syntax Error in voice_async.py**:
   - Found a mismatched parenthesis in the error handler causing a syntax error
   - Fixed by removing the extra closing brace on line 674

6. **JSONB Type Detection Issues**:
   - The `is_postgresql()` function in menu.py was trying to access `db.engine.dialect` which doesn't exist
   - Created a new helper module (`jsonb_helper.py`) that uses the DATABASE_URL to determine if PostgreSQL is being used
   - Updated menu.py to use this helper module for JSONB column detection

7. **Missing Environment Variables and Configuration Settings**:
   - Required environment variables were missing in the Render environment
   - Added placeholder values to `.env` file for critical values
   - Added missing Deliverect client credentials to the Pydantic Settings class
   - Added missing Stripe API key to the fallback settings
   - Environment variables that must be set in Render:
     - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` 
     - `DELIVERECT_API_KEY`, `DELIVERECT_API_URL`, `DELIVERECT_CLIENT_ID`, `DELIVERECT_CLIENT_SECRET`
     - `OPENAI_API_KEY`
     - `BASE_URL` (should be set to the Render deployment URL, e.g. 'https://redbarsushiai-staging.onrender.com')
     - `STRIPE_API_KEY` (if payment processing is needed)

8. **Incorrect Import Pattern in Deliverect Auth Module**:
   - The auth.py module was trying to import DELIVERECT_CLIENT_ID and DELIVERECT_CLIENT_SECRET directly from app.config
   - Changed to import the settings object and access the properties via settings.DELIVERECT_CLIENT_ID
   - This matches the standard Pydantic settings pattern and prevents ImportError

9. **Entrypoint Script Improvements**:
   - Modified database initialization check to be less strict during startup
   - Prevents failing startup due to configuration issues

### Deployment Automation

Created a `fix_render_deploy.sh` script that automatically applies all necessary fixes for Render deployment:

- Fixes environment variables
- Patches redis_async.py syntax error
- Updates function names in main.py
- Makes scripts executable

## Previous Issues Diagnosed

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