#!/bin/bash
# Script to fix PostgreSQL startup issues

echo "🔧 Fixing PostgreSQL startup issues..."

# 1. Stop all services
echo "Stopping all services..."
docker-compose -f docker-compose.dev.yml down

# 2. Check if port 5432 is in use
echo -e "\nChecking if port 5432 is already in use..."
if lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Port 5432 is already in use!"
    echo "You can either:"
    echo "  1. Stop the service using port 5432:"
    echo "     sudo lsof -i :5432  # Find the process"
    echo "     sudo kill -9 <PID>  # Kill it"
    echo "  2. Change PostgreSQL port in .env:"
    echo "     POSTGRES_PORT=5433"
else
    echo "✅ Port 5432 is available"
fi

# 3. Clean up old volumes
echo -e "\nCleaning up old volumes..."
docker volume prune -f

# 4. Check PostgreSQL logs
echo -e "\nChecking PostgreSQL logs..."
docker-compose -f docker-compose.dev.yml logs postgres | tail -20

# 5. Try starting just PostgreSQL
echo -e "\nTrying to start PostgreSQL only..."
docker-compose -f docker-compose.dev.yml up -d postgres

# Wait a bit
sleep 5

# Check status
echo -e "\nChecking PostgreSQL status..."
docker-compose -f docker-compose.dev.yml ps postgres

# Show logs again
echo -e "\nPostgreSQL logs:"
docker-compose -f docker-compose.dev.yml logs postgres | tail -30