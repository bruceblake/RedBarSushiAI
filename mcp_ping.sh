#!/bin/bash
# Quick MCP ping test

echo "Testing MCP ping with curl..."
curl -v "http://localhost:4244/sse?tool_call=%7B%22name%22%3A%20%22ping%22%2C%20%22arguments%22%3A%20%7B%7D%7D" --max-time 5

echo -e "\n\nTesting direct IP ping..."
curl -v "http://172.20.0.2:4244/sse?tool_call=%7B%22name%22%3A%20%22ping%22%2C%20%22arguments%22%3A%20%7B%7D%7D" --max-time 5