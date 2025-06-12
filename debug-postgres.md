# PostgreSQL Container Startup Troubleshooting

Your PostgreSQL container is failing to start. Here's how to fix it:

## Quick Fix Commands

Run these commands in order:

```bash
# 1. Clean everything and start fresh
make clean

# 2. Check if port 5432 is in use
sudo lsof -i :5432

# If port is in use, either kill the process or change port in .env:
# echo "POSTGRES_PORT=5433" >> .env

# 3. Try starting PostgreSQL only
docker-compose -f docker-compose.dev.yml up postgres
```

## Common Issues and Solutions

### 1. Port Already in Use
```bash
# Check what's using port 5432
sudo lsof -i :5432

# Option A: Stop local PostgreSQL
sudo systemctl stop postgresql
# or on Mac:
brew services stop postgresql

# Option B: Use different port
# Edit .env file:
POSTGRES_PORT=5433
```

### 2. Permission Issues
```bash
# Fix permissions on init scripts
chmod -R 755 db/init/

# Remove old volumes
docker volume rm redbarsushiai_postgres-data
```

### 3. Check PostgreSQL Logs
```bash
# See what PostgreSQL is complaining about
docker-compose -f docker-compose.dev.yml logs postgres
```

### 4. Corrupted Volume
```bash
# Remove all volumes and start fresh
docker-compose -f docker-compose.dev.yml down -v
docker volume prune -f
```

## Step-by-Step Debug Process

1. **Stop everything**
   ```bash
   make down
   ```

2. **Check for conflicts**
   ```bash
   # Check if PostgreSQL is already running
   ps aux | grep postgres
   
   # Check port usage
   netstat -an | grep 5432
   ```

3. **Clean volumes**
   ```bash
   make clean
   ```

4. **Try PostgreSQL alone**
   ```bash
   # This will show errors in real-time
   docker-compose -f docker-compose.dev.yml up postgres
   ```

5. **If it works, start everything**
   ```bash
   # In another terminal
   make up
   ```

## Alternative: Skip Docker PostgreSQL

If you have PostgreSQL installed locally:

1. Edit `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/sushi_restaurant
   ```

2. Create database locally:
   ```bash
   createdb sushi_restaurant
   ```

3. Comment out postgres service in `docker-compose.dev.yml`

4. Run just the app:
   ```bash
   docker-compose -f docker-compose.dev.yml up app redis ngrok
   ```

## Still Having Issues?

Run this diagnostic command:
```bash
chmod +x fix-postgres.sh
./fix-postgres.sh
```

Then share the output to get more specific help.