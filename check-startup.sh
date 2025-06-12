#!/bin/bash
# Quick startup diagnostic script

echo "🔍 Checking RedBarSushiAI startup status..."
echo "=========================================="

# 1. Check container status
echo -e "\n📦 Container Status:"
docker-compose -f docker-compose.dev.yml ps

# 2. Check app logs for errors
echo -e "\n🚨 Recent App Errors:"
docker-compose -f docker-compose.dev.yml logs --tail=20 app | grep -E "(ERROR|CRITICAL|Exception|ModuleNotFoundError|ImportError)" || echo "No obvious errors found"

# 3. Check if app is responding
echo -e "\n🌐 API Health Check:"
for i in {1..5}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is responding!"
        curl -s http://localhost:8000/health | python -m json.tool
        break
    else
        echo "⏳ Attempt $i/5 - API not ready yet..."
        sleep 2
    fi
done

# 4. Check ngrok
echo -e "\n🌐 Ngrok Status:"
if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
    python get_ngrok_url.py 2>/dev/null || echo "Ngrok running but no tunnel yet"
else
    echo "❌ Ngrok not responding"
fi

# 5. Follow app logs
echo -e "\n📋 Following app logs (Ctrl+C to stop):"
docker-compose -f docker-compose.dev.yml logs -f --tail=50 app