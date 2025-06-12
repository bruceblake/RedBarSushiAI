#!/bin/bash
# Script to check app logs and diagnose issues

echo "🔍 Checking RedBarSushiAI App Logs..."
echo "========================================"

# 1. Check container status
echo -e "\n1. Container status:"
docker-compose -f docker-compose.dev.yml ps

# 2. Get app logs (last 100 lines)
echo -e "\n2. App container logs (last 100 lines):"
echo "----------------------------------------"
docker-compose -f docker-compose.dev.yml logs --tail=100 app

# 3. Check if app is running
echo -e "\n3. Checking if app is responding:"
echo "----------------------------------"
curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "❌ App not responding on port 8000"

# 4. Check for common startup errors
echo -e "\n4. Checking for common errors:"
echo "------------------------------"
docker-compose -f docker-compose.dev.yml logs app 2>&1 | grep -E "(ERROR|CRITICAL|Exception|Failed|Error)" | tail -20

# 5. Check environment variables
echo -e "\n5. Checking if environment variables are loaded:"
echo "------------------------------------------------"
docker-compose -f docker-compose.dev.yml exec app env | grep -E "(OPENAI|TWILIO|DATABASE_URL|REDIS_URL)" | sed 's/=.*/=***/'

# 6. Real-time logs (last 10 seconds)
echo -e "\n6. Following app logs (press Ctrl+C to stop):"
echo "---------------------------------------------"
docker-compose -f docker-compose.dev.yml logs -f --tail=50 app