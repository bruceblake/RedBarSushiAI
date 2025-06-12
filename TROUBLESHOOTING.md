# Troubleshooting Guide

## PostgreSQL Container Won't Start

This is the most common issue. Here's how to fix it:

### Solution 1: Clean Start
```bash
# Stop everything and remove volumes
make clean

# Try starting just PostgreSQL to see errors
docker-compose -f docker-compose.dev.yml up postgres
```

### Solution 2: Port Conflict
```bash
# Check if PostgreSQL is already running locally
sudo lsof -i :5432

# If it is, either stop it:
sudo systemctl stop postgresql  # Linux
brew services stop postgresql   # Mac

# Or use a different port in .env:
echo "POSTGRES_PORT=5433" >> .env
```

### Solution 3: Use the Debug Script
```bash
# Run the automated fix script
./fix-postgres.sh

# Or use the step-by-step startup
./start-docker.sh
```

### Solution 4: Check Docker Resources
```bash
# Make sure Docker has enough resources
docker system df
docker system prune -a  # Warning: removes all unused images

# Check Docker Desktop settings:
# - Memory: At least 2GB
# - Disk: At least 10GB free
```

## ngrok Issues

### "NGROK_AUTHTOKEN not set"
1. Sign up at https://ngrok.com
2. Get your auth token from dashboard
3. Add to .env:
   ```
   NGROK_AUTHTOKEN=your_token_here
   ```

### ngrok URL not showing
```bash
# Check if ngrok is running
docker-compose -f docker-compose.dev.yml ps ngrok

# Check ngrok logs
docker-compose -f docker-compose.dev.yml logs ngrok

# Manually get URL
curl http://localhost:4040/api/tunnels
```

## App Won't Start

### Check logs
```bash
# See what's happening
docker-compose -f docker-compose.dev.yml logs app

# Follow logs in real-time
make logs-app
```

### Common fixes
```bash
# Rebuild the image
docker-compose -f docker-compose.dev.yml build app

# Check environment variables
docker-compose -f docker-compose.dev.yml exec app env | grep OPENAI
```

## Database Connection Issues

### "relation does not exist"
```bash
# Database not initialized, run:
docker-compose -f docker-compose.dev.yml exec app python init_db.py
docker-compose -f docker-compose.dev.yml exec app python seed_menu_db.py
```

### Connection refused
```bash
# Make sure PostgreSQL is running
docker-compose -f docker-compose.dev.yml ps postgres

# Test connection
docker-compose -f docker-compose.dev.yml exec postgres pg_isready
```

## Quick Reset Everything

When all else fails:
```bash
# Nuclear option - removes everything
docker-compose -f docker-compose.dev.yml down -v
docker system prune -a --volumes
rm -rf postgres-data redis-data

# Start fresh
make setup
```

## Manual Step-by-Step Start

If `make setup` fails, try starting services one by one:

```bash
# 1. Start PostgreSQL only
docker-compose -f docker-compose.dev.yml up -d postgres
# Watch logs
docker-compose -f docker-compose.dev.yml logs -f postgres

# 2. Once PostgreSQL is running, start Redis
docker-compose -f docker-compose.dev.yml up -d redis

# 3. Start the app
docker-compose -f docker-compose.dev.yml up -d app

# 4. Initialize database
docker-compose -f docker-compose.dev.yml exec app python init_db.py
docker-compose -f docker-compose.dev.yml exec app python seed_menu_db.py

# 5. Start ngrok
docker-compose -f docker-compose.dev.yml up -d ngrok
```

## Still Having Issues?

1. Check Docker Desktop is running
2. Ensure you have enough disk space
3. Try restarting Docker Desktop
4. Check the detailed logs:
   ```bash
   docker-compose -f docker-compose.dev.yml logs > debug.log
   ```
5. Look for specific error messages in debug.log