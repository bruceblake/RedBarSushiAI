#!/bin/bash

echo "🔍 STAGING ENVIRONMENT MENU CHECK"
echo "=================================================="

BASE_URL="https://3b93-149-22-84-146.ngrok-free.app"
CALL_SID="staging_test_$(date +%s)"

echo ""
echo "📞 Step 1: Starting conversation..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Hi, my name is MenuChecker\", \"call_sid\": \"$CALL_SID\"}" \
  --silent | jq -r '.message' | head -c 100
echo "..."

echo ""
echo ""
echo "📋 Step 2: Getting complete menu..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Show me everything you have on the menu\", \"call_sid\": \"$CALL_SID\"}" \
  --silent | jq -r '.message'

echo ""
echo ""
echo "🍔 Step 3: Getting burger items..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What burgers do you have?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent | jq -r '.message'

echo ""
echo ""
echo "🥩 Step 4: Getting steak items..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What steak dishes do you have?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent | jq -r '.message'

echo ""
echo ""
echo "🧪 Step 5: Testing exact item ordering..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want the Delicious Steak Frites\", \"call_sid\": \"$CALL_SID\"}" \
  --silent | jq -r '.message'

echo ""
echo ""
echo "🎉 STAGING MENU CHECK COMPLETE"