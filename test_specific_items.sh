#!/bin/bash

echo "🔍 TESTING SPECIFIC MENU ITEMS"
echo "=================================================="

BASE_URL="https://redbarsushiai-staging.onrender.com"
CALL_SID="item_test_$(date +%s)"

echo ""
echo "📞 Starting conversation..."
curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"Hi, my name is ItemTester\", \"call_sid\": \"$CALL_SID\"}" \
  --silent > /dev/null

echo ""
echo "🍔 Testing: Classic Burger"
response1=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want a Classic Burger\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response1"

echo ""
echo "🥩 Testing: Delicious Steak Frites (the actual item)"
response2=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want Delicious Steak Frites\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response2"

echo ""
echo "🥩 Testing: Ribeye Steak (what customer asked for)"
response3=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want a ribeye steak\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response3"

echo ""
echo "🍕 Testing: Pizza"
response4=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want a pizza\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response4"

echo ""
echo "❌ Testing: Non-existent item"
response5=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"I want a unicorn burger\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response5"

echo ""
echo "📦 Checking cart contents..."
response6=$(curl -X POST "$BASE_URL/order/take_order" \
  -H "Content-Type: application/json" \
  -d "{\"speech_result\": \"What's in my cart?\", \"call_sid\": \"$CALL_SID\"}" \
  --silent)
echo "Response: $response6"

echo ""
echo "🎉 ITEM TESTING COMPLETE"