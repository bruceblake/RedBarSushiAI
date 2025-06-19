# RedBarSushiAI Docker Debugging Guide

## Quick Status Check

### 1. Check Container Status
```bash
# See all containers and their status
docker ps -a

# Expected output:
# - redbarsushi-app (healthy/running)
# - redbarsushi-postgres (healthy)
# - redbarsushi-redis (healthy)
# - redbarsushi-celery (running)
```

### 2. Test Application Health
```bash
# Test if app is responding
curl http://localhost:8000/healthcheck

# Expected response:
# {"status":"ok","message":"RedBarSushiAI is running",...}
```

## Container Management

### Starting/Stopping Containers
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart app

# Rebuild specific service
docker-compose build app
docker-compose up app -d
```

### Accessing Container Shells
```bash
# Access app container
docker exec -it redbarsushi-app bash

# Access database
docker exec -it redbarsushi-postgres psql -U postgres -d redbarsushi

# Access Redis
docker exec -it redbarsushi-redis redis-cli
```

## Log Analysis

### Viewing Logs
```bash
# Follow app logs in real-time
docker logs -f redbarsushi-app

# View last 50 lines
docker logs redbarsushi-app --tail 50

# View logs with timestamps
docker logs -t redbarsushi-app

# View all container logs
docker-compose logs -f
```

### Key Log Messages to Look For

**✅ GOOD Signs:**
```
INFO:     Started server process [11]
INFO:     Application startup complete.
GET /healthcheck HTTP/1.1" 200 OK
Database initialized successfully
Settings loaded successfully
```

**❌ BAD Signs:**
```
ERROR connecting to database
greenlet_spawn has not been called
ModuleNotFoundError
ImportError
Connection refused
```

## Common Issues & Solutions

### 1. Database Connection Errors

**Symptoms:**
```
ERROR connecting to database: greenlet_spawn has not been called
```

**Solutions:**
```bash
# Check if postgres container is running
docker ps | grep postgres

# Check postgres logs
docker logs redbarsushi-postgres

# Restart database
docker-compose restart postgres

# Wait for postgres to be ready
docker-compose up postgres
# Wait for "database system is ready to accept connections"
```

### 2. Import/Module Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'pydantic_settings'
ImportError: cannot import name 'X'
```

**Solutions:**
```bash
# Check if requirements are installed
docker exec redbarsushi-app pip list | grep pydantic

# Rebuild container with clean cache
docker-compose build --no-cache app

# Check Python path
docker exec redbarsushi-app python -c "import sys; print(sys.path)"
```

### 3. App Won't Start

**Symptoms:**
```
Container exits immediately
No response on port 8000
```

**Debug Steps:**
```bash
# Check container status
docker ps -a

# View full logs
docker logs redbarsushi-app

# Check if port is bound
netstat -tulpn | grep 8000

# Try starting manually
docker exec -it redbarsushi-app uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Entrypoint Debugging

### Current Entrypoint Location
```bash
# View current entrypoint
docker exec redbarsushi-app cat /docker-entrypoint.sh
```

### Expected Entrypoint Content
The entrypoint should be simple and only:
1. Set PORT variable
2. Initialize database
3. Start uvicorn

### Manual Entrypoint Execution
```bash
# Run entrypoint steps manually
docker exec -it redbarsushi-app bash

# Inside container:
export PORT=8080
python -c "
import asyncio
from app.db_async import init_database
asyncio.run(init_database())
"
uvicorn app.main:app --host=0.0.0.0 --port=8080 --reload
```

### Entrypoint Troubleshooting
```bash
# Check file permissions
docker exec redbarsushi-app ls -la /docker-entrypoint.sh

# Should show: -rwxr-xr-x (executable)

# If not executable:
docker exec redbarsushi-app chmod +x /docker-entrypoint.sh
```

## Database Debugging

### Check Database Connection
```bash
# Test connection from app container
docker exec redbarsushi-app python -c "
import asyncio
from app.db_async import verify_connection
print(asyncio.run(verify_connection()))
"
```

### Database Operations
```bash
# Initialize database manually
docker exec redbarsushi-app python init_db.py

# Seed menu data
docker exec redbarsushi-app python seed_menu_db.py

# Check tables exist
docker exec redbarsushi-postgres psql -U postgres -d redbarsushi -c "\dt"
```

### Database Connection Details
- **Host:** postgres (container name)
- **Port:** 5432
- **Database:** redbarsushi
- **User:** postgres
- **Password:** postgres

## Real-Time Development

### File Watching
```bash
# Check volume mounts
docker inspect redbarsushi-app | grep -A 5 "Mounts"

# Should show: ./app:/app/app
```

### Testing Auto-Reload
1. Edit a file in `./app/` directory
2. Watch logs: `docker logs -f redbarsushi-app`
3. Should see: "Reloading..." messages

### Manual Code Testing
```bash
# Test code changes manually
docker exec redbarsushi-app python -c "
from app.main import app
print('App imported successfully')
"
```

## Network Debugging

### Port Mapping
```bash
# Check port mappings
docker port redbarsushi-app

# Should show: 8080/tcp -> 0.0.0.0:8000
```

### Network Connectivity
```bash
# Test from host
curl -v http://localhost:8000/healthcheck

# Test from inside container
docker exec redbarsushi-app curl http://localhost:8080/healthcheck

# Check network
docker network ls
docker network inspect redbarsushiai_redbarsushi-network
```

## Performance Monitoring

### Container Resources
```bash
# Check resource usage
docker stats

# Check container processes
docker exec redbarsushi-app ps aux
```

### Application Metrics
```bash
# Check uvicorn processes
docker exec redbarsushi-app ps aux | grep uvicorn

# Check database connections
docker exec redbarsushi-postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"
```

## Emergency Recovery

### Full Reset
```bash
# Stop everything
docker-compose down

# Remove volumes (DESTRUCTIVE - loses data)
docker volume prune

# Rebuild everything
docker-compose build --no-cache
docker-compose up -d
```

### Backup Important Data
```bash
# Backup database
docker exec redbarsushi-postgres pg_dump -U postgres redbarsushi > backup.sql

# Backup logs
docker logs redbarsushi-app > app_logs.txt
```

## Configuration Files

### Key Files to Check
- `docker-compose.yml` - Service definitions
- `Dockerfile` - Image build instructions
- `requirements.txt` - Python dependencies
- `app/config.py` - Application configuration
- `app/main.py` - FastAPI application

### Environment Variables
```bash
# Check environment in container
docker exec redbarsushi-app env | grep -E "(DATABASE|REDIS|OPENAI|PORT)"

# Should include:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/redbarsushi
# REDIS_URL=redis://redis:6379/0
# OPENAI_API_KEY=sk-proj-...
# PORT=8080
```

## Step-by-Step Debugging Process

### When Things Break:

1. **Check Status**
   ```bash
   docker ps -a
   curl http://localhost:8000/healthcheck
   ```

2. **Check Logs**
   ```bash
   docker logs redbarsushi-app --tail 50
   ```

3. **Identify Issue Type**
   - Import errors → Rebuild container
   - Database errors → Check postgres container
   - Network errors → Check port mapping
   - App errors → Check application code

4. **Try Quick Fixes**
   ```bash
   docker-compose restart app
   ```

5. **If Still Broken**
   ```bash
   docker exec -it redbarsushi-app bash
   # Debug inside container
   ```

6. **Last Resort**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Getting Help

### Collect Debug Information
```bash
# System info
docker version
docker-compose version

# Container status
docker ps -a

# Recent logs
docker logs redbarsushi-app --tail 100

# Network info
docker network ls
docker port redbarsushi-app

# Environment
docker exec redbarsushi-app env
```

### Useful Commands Summary
```bash
# Quick health check
curl http://localhost:8000/healthcheck && echo "✅ App OK" || echo "❌ App Failed"

# Quick log check
docker logs redbarsushi-app --tail 20 | grep -E "(ERROR|CRITICAL|Started|INFO)"

# Quick restart
docker-compose restart app && sleep 10 && curl http://localhost:8000/healthcheck
```

This guide should help you systematically debug any issues that arise during development!