#!/bin/bash
# Script to deploy the OpenAI Realtime client process_messages fix

set -e  # Exit on any error

echo "===== Deploying OpenAI Realtime process_messages Fix ====="

# Step 1: Check the current branch
echo "Step 1: Checking current branch..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
echo "✅ Current branch is '$current_branch'"

# Step 2: Add the changes
echo "Step 2: Adding changes to git..."
git add app/utils/realtime_audio_async.py
git status
echo "✅ Changes staged"

# Step 3: Commit the changes
echo "Step 3: Committing changes..."
git commit -m "Fix process_messages method in OpenAIRealtimeClient

Added process_messages() method to OpenAIRealtimeClient, which is
required by handlers.py. The method delegates to the existing
_process_events() implementation, ensuring compatibility with
the call in handle_media_stream().

This fixes the AttributeError: 'OpenAIRealtimeClient' object has 
no attribute 'process_messages' error in the WebSocket handler."
echo "✅ Changes committed"

# Step 4: Push to branch
echo "Step 4: Pushing to branch '$current_branch'..."
git push origin "$current_branch"
echo "✅ Changes pushed to '$current_branch'"

echo
echo "===== Deployment Complete ====="
echo "The process_messages fix has been deployed to the '$current_branch' branch."
echo "Render will automatically deploy these changes to the corresponding environment."
echo
echo "IMPORTANT: You MUST update the OPENAI_API_KEY in your environment:"
echo "1. Local Testing: Update .env.development with a valid API key"
echo "2. Render Deployment: Set OPENAI_API_KEY in the Render dashboard"
echo
echo "Your current API key 'sk-mytestapikey' is a placeholder that will not work with OpenAI."
echo "Get a valid key from: https://platform.openai.com/account/api-keys"
echo
echo "Don't forget to also set these environment variables:"
echo "- TWILIO_ACCOUNT_SID"
echo "- TWILIO_AUTH_TOKEN"
echo "- TWILIO_PHONE_NUMBER"
echo "- STRIPE_API_KEY"