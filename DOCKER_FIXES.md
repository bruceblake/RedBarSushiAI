# Docker Fixes for RedBarSushiAI

This document outlines the fixes implemented to resolve PostgreSQL authentication issues and improve Docker setup for the RedBarSushiAI project.

## PostgreSQL Authentication Issues

### Problem

The application was encountering PostgreSQL authentication errors when running in Docker:

```
psycopg2.OperationalError: connection to server at "postgres" (172.18.0.3), port 5432 failed: FATAL: password authentication failed for user "postgres"
```

### Root Causes

1. Inconsistent password configuration between the app and PostgreSQL services
2. Missing database initialization scripts
3. Lack of proper health checks and diagnostics tools

### Implemented Fixes

1. **Consistent Password Configuration:**
   - Updated `docker-compose.yml` to use consistent password values
   - Set the same password in both the app and PostgreSQL containers

2. **Database Initialization:**
   - Created proper database schema initialization scripts
   - Added a script to initialize the database with required tables
   - Ensured volumes are correctly mounted

3. **Enhanced Health Checks:**
   - Added robust health checks for PostgreSQL and Redis
   - Created proper dependency ordering with service_healthy condition
   - Added retry logic to handle startup timing issues

## Added Tools and Scripts

### Database Tools

1. **Database Schema Initialization Script (`db/init/01_schema.sql`):**
   - Creates all required database tables if they don't exist
   - Sets up proper indexes and constraints
   - Adds minimal seed data for locations

2. **Database Connection Fix Script (`fix_db_connection.py`):**
   - Tests PostgreSQL connection with retry logic
   - Tests Redis connection with retry logic
   - Provides detailed error information
   - Can update environment variables with working configuration

### Docker Health and Management

1. **Docker Health Check Script (`check_docker_health.sh`):**
   - Verifies container status
   - Tests PostgreSQL connection directly
   - Tests Redis connection directly
   - Shows container logs for troubleshooting
   - Provides environment variable information
   - Shows network configuration

2. **Docker Startup Script (`start_docker.sh`):**
   - Simplified startup process
   - Options for rebuilding and cleaning volumes
   - Handles log directory creation
   - Runs health check automatically
   - Shows useful commands for management

### Documentation

1. **Docker Usage Guide (`DOCKER_USAGE.md`):**
   - Comprehensive instructions for using Docker with the project
   - Manual Docker Compose command reference
   - Troubleshooting guidance
   - Container configuration details
   - Environment variable documentation
   - Advanced usage scenarios

2. **Updated README.md:**
   - Enhanced Docker section with simplified instructions
   - Links to the new Docker documentation

## Using the Fixed Docker Setup

1. **Starting the Application:**
   ```bash
   ./start_docker.sh
   ```

2. **Checking Container Health:**
   ```bash
   ./check_docker_health.sh
   ```

3. **Fixing Database Connection Issues:**
   ```bash
   python fix_db_connection.py
   ```

4. **Complete Reset (if needed):**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

## Verification Steps

To verify the fixes are working correctly:

1. Start the containers with `./start_docker.sh`
2. Run `./check_docker_health.sh` to confirm services are healthy
3. Access the application at http://localhost:8080/healthcheck
4. Check container logs with `docker-compose logs -f`