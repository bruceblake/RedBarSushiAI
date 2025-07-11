#!/bin/bash

echo "🔍 STAGING ENVIRONMENT MENU CHECK"
echo "=================================================="

BASE_URL="https://redbarsushiai-staging.onrender.com"
CALL_SID="staging_test_$(date +%s)"

echo ""
echo "📞 Step 1: Starting conversation..."
response1=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Hi, my name is MenuChecker\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response1"

echo ""
echo ""
echo "📋 Step 2: Getting complete menu..."
response2=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Show me everything you have on the menu\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response2"

echo ""
echo ""
echo "🍔 Step 3: Getting burger items..."
response3=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What burgers do you have?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response3"

echo ""
echo ""
echo "🥩 Step 4: Getting steak items..."
response4=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What steak dishes do you have?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response4"

echo ""
echo ""
echo "🧪 Step 5: Testing ribeye steak order (the problematic one)..."
response5=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want a ribeye steak\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response5"

echo ""
echo ""
echo "🎉 STAGING MENU CHECK COMPLETE"