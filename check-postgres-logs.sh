#!/bin/bash
# Script to check PostgreSQL logs and diagnose startup issues

echo "🔍 Checking PostgreSQL startup issues..."
echo "========================================"

# 1. Check current container status
echo -e "\n1. Current container status:"
docker-compose -f docker-compose.dev.yml ps

# 2. Get PostgreSQL logs
echo -e "\n2. PostgreSQL container logs:"
echo "----------------------------"
docker-compose -f docker-compose.dev.yml logs --tail=50 postgres

# 3. Check if port 5432 is in use
echo -e "\n3. Checking port 5432:"
echo "----------------------"
if command -v lsof &> /dev/null; then
    lsof -i :5432 2>/dev/null || echo "Port 5432 is free"
else
    netstat -an | grep 5432 || echo "Port 5432 appears to be free"
fi

# 4. Check Docker volumes
echo -e "\n4. Docker volumes:"
echo "------------------"
docker volume ls | grep postgres

# 5. Check if there are permission issues
echo -e "\n5. Checking file permissions:"
echo "-----------------------------"
ls -la db/init/ 2>/dev/null || echo "No db/init directory found"

# 6. Try to see the actual error
echo -e "\n6. Attempting to start PostgreSQL with verbose output:"
echo "------------------------------------------------------"
docker-compose -f docker-compose.dev.yml up postgres 2>&1 | head -50

# 7. Check Docker daemon logs if possible
echo -e "\n7. Recent Docker events:"
echo "------------------------"
docker events --since 5m --until 0s 2>&1 | grep -E "(postgres|die|kill)" | tail -10

echo -e "\n========================================"
echo "📋 Please share the output above to diagnose the issue"
echo "========================================"