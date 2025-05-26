# Deliverect Integration Setup Guide

This guide walks you through setting up Deliverect integration for Red Bar Sushi AI to receive menu updates and manage orders.

## Understanding Deliverect Integration

Deliverect uses a **push-based webhook system** where:
1. Deliverect calls YOUR registration endpoint to register a channel
2. You respond with webhook URLs for various events (menu updates, order status, etc.)
3. Deliverect then calls those webhooks when events occur

## Prerequisites

1. **Deliverect Account**: You need access to a Deliverect account (sandbox or production)
2. **API Credentials**: Obtain from Deliverect dashboard:
   - API Key
   - Client ID  
   - Client Secret
3. **Channel Setup in Deliverect**: Create a channel in Deliverect dashboard which will generate:
   - Channel Link ID
   - Location ID

## Step 1: Configure Environment Variables

Update your `.env.development` or Docker environment with:

```bash
# Deliverect Configuration
DELIVERECT_API_KEY=your_api_key_here
DELIVERECT_CLIENT_ID=your_client_id_here
DELIVERECT_CLIENT_SECRET=your_client_secret_here
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_BASE_URL=https://api.staging.deliverect.com  # or production URL
```

## Step 2: Start the Application

```bash
# Start the Docker environment
./start_docker.sh

# Verify it's running
curl http://localhost:8000/health
```

## Step 3: Test the Integration Locally

```bash
# Run the test script to simulate Deliverect flow
python test_deliverect_integration.py
```

This will:
- Simulate Deliverect calling your registration endpoint
- Show the webhook URLs that would be registered
- Test the menu update webhook with sample data
- Verify menu items are stored in the database

## Step 4: Expose Local Server for Webhooks

Deliverect needs to reach your local server. Choose one option:

### Option A: Using ngrok (Recommended)

```bash
# Install ngrok
# Visit: https://ngrok.com/download

# Create tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

### Option B: Using localtunnel

```bash
# Install localtunnel
npm install -g localtunnel

# Create tunnel
lt --port 8000

# Copy the URL provided
```

## Step 5: Register Webhook with Deliverect

### Method 1: Using Deliverect Dashboard (Recommended)

1. Log into Deliverect Dashboard
2. Navigate to: **Settings > Webhooks**
3. Click **Add Webhook**
4. Configure:
   - **URL**: `https://your-ngrok-url.ngrok.io/api/menu/webhook/deliverect/menu`
   - **Event Type**: Menu Update
   - **Active**: Yes
5. Save the webhook

### Method 2: Using Deliverect API

```bash
# Register webhook programmatically
python test_deliverect_menu.py --register --public-url https://your-ngrok-url.ngrok.io
```

## Step 6: Trigger a Menu Update

To test the integration:

1. Go to Deliverect Dashboard
2. Navigate to your menu
3. Make any change (e.g., update a price, add an item)
4. Save the changes
5. Deliverect will automatically send the update to your webhook

## Step 7: Verify Menu Updates

Check that menu updates are received:

```bash
# Check logs
docker logs redbarsushi-app-1 -f | grep "menu update"

# Query menu items via API
curl http://localhost:8000/api/menu/items
curl http://localhost:8000/api/menu/categories
```

## Webhook Endpoint Details

### Endpoint URL
```
POST /api/menu/webhook/deliverect/menu
```

### Expected Payload Structure
```json
{
  "menu": {
    "categories": [...],
    "products": [...]
  },
  "accountId": "...",
  "channelLinkId": "...",
  "menuId": "...",
  "locationId": "..."
}
```

### Response
```json
{
  "status": "success",
  "message": "Menu updated successfully",
  "stats": {
    "categories": 3,
    "items": 10,
    "modifier_groups": 5
  }
}
```

## Troubleshooting

### Webhook Not Receiving Updates

1. **Check ngrok is running**: Visit http://127.0.0.1:4040 to see ngrok inspector
2. **Verify webhook URL**: Ensure no typos in Deliverect dashboard
3. **Check logs**: `docker logs redbarsushi-app-1 -f`

### Menu Items Not Storing

1. **Check database connection**: `docker exec -it redbarsushi-postgres-1 psql -U redbarsushi`
2. **Verify tables exist**: `\dt` in psql
3. **Check for errors**: Look for SQL errors in logs

### Authentication Issues

1. **Verify API credentials**: Ensure they're correctly set in environment
2. **Check token expiry**: Some Deliverect tokens expire
3. **Test with curl**: Try manual API calls to verify credentials

## Production Deployment

For production:

1. Use a permanent webhook URL (not ngrok)
2. Set up SSL certificates
3. Configure webhook authentication/verification
4. Set up monitoring and alerts
5. Use production Deliverect API URL

## Next Steps

After menu integration is working:

1. Test order flow from Deliverect
2. Set up order status updates
3. Configure modifier handling
4. Test edge cases (unavailable items, price changes)
5. Set up automated menu sync schedules