#!/bin/bash
# Script to deploy the OpenAI Realtime API client fix to Render

set -e  # Exit on any error

echo "===== Deploying OpenAI Realtime API Client Fix ====="

# Step 1: Check the current branch
echo "Step 1: Checking current branch..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
echo "✅ Current branch is '$current_branch'"

# Step 2: Add the changes
echo "Step 2: Adding changes to git..."
git add app/api/voice/realtime.py
git status
echo "✅ Changes staged"

# Step 3: Commit the changes
echo "Step 3: Committing changes..."
git commit -m "Fix RealtimeEventProcessor initialization in OpenAI client

The RealtimeEventProcessor was being instantiated without the required client parameter.
This change ensures the processor is created after the OpenAIRealtimeClient and properly 
linked to it, fixing the TypeError when trying to establish a Realtime connection."
echo "✅ Changes committed"

# Step 4: Push to branch
echo "Step 4: Pushing to branch '$current_branch'..."
git push origin "$current_branch"
echo "✅ Changes pushed to '$current_branch'"

echo
echo "===== Deployment Complete ====="
echo "The fix has been deployed to the '$current_branch' branch."
echo "Render will automatically deploy these changes to the corresponding environment."
echo "Monitor the deployment in the Render dashboard."
echo
echo "IMPORTANT: Make sure your Render environment has these environment variables properly set:"
echo "- OPENAI_API_KEY: Required for OpenAI Realtime API"
echo "- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER: Required for Twilio integration"
echo
echo "You can view the application logs in the Render dashboard to verify the fix."
echo "Look for logs starting with '🔄 [CALL_SID] OpenAIRealtimeClient instance created and configured'"