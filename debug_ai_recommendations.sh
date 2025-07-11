#!/bin/bash

echo "🔍 DEBUGGING AI MENU RECOMMENDATIONS"
echo "=================================================="

BASE_URL="https://redbarsushiai-staging.onrender.com"
CALL_SID="debug_ai_$(date +%s)"

echo ""
echo "📞 Starting conversation..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Hi, my name is AIDebugger\", \"call_sid\": \"$CALL_SID\"}" \
  --silent > /dev/null

echo ""
echo "🔍 Step 1: Ask AI to LIST ALL available steak items"
response1=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"List every single steak item you have available\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "AI Response: $response1"

echo ""
echo ""
echo "🔍 Step 2: Ask AI about ribeye specifically"
response2=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Do you have ribeye steak?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "AI Response: $response2"

echo ""
echo ""
echo "🔍 Step 3: Ask AI to show steak category items"
response3=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Show me all items in the steak category\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "AI Response: $response3"

echo ""
echo ""
echo "🔍 Step 4: Ask AI about 'Steak and Burgers' category"
response4=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What's in the Steak and Burgers category?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "AI Response: $response4"

echo ""
echo ""
echo "🔍 Step 5: Force AI to use lookup tool"
response5=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Use your database to show me what steak items exist\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "AI Response: $response5"

echo ""
echo ""
echo "🎉 AI RECOMMENDATION DEBUG COMPLETE"