#!/bin/bash
# Fix all import issues

echo "🔧 Fixing all import issues..."

# Fix calculate_bill_amount_async -> calculate_order_total_async
find app -name "*.py" -type f -exec sed -i 's/calculate_bill_amount_async/calculate_order_total_async/g' {} \;

# Fix build_order_description -> build_order_description_async (if needed)
find app -name "*.py" -type f -exec sed -i 's/from app.utils.order_utils_async import build_order_description$/from app.utils.order_utils_async import build_order_description_async/g' {} \;

echo "✅ Import fixes applied"

# Restart app
echo "🔄 Restarting app..."
docker-compose -f docker-compose.dev.yml restart app

# Wait and check
sleep 15
echo -e "\n📊 Checking if app is running..."
curl -s http://localhost:8000/health | python -m json.tool || echo "Still starting..."

echo -e "\n📋 Recent logs:"
docker-compose -f docker-compose.dev.yml logs --tail=20 app | grep -E "INFO.*startup complete|ERROR|ImportError|Uvicorn running|Application startup"