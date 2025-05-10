# Testing RedBarSushiAI with Docker and ngrok

This document provides instructions on how to run RedBarSushiAI in a Docker environment with ngrok for easy testing of Twilio webhook integrations.

## Prerequisites

1. **Docker and Docker Compose**: Install from [docker.com](https://www.docker.com/get-started)
2. **ngrok**: Install from [ngrok.com](https://ngrok.com/download)
3. **ngrok account**: Sign up at [ngrok.com](https://ngrok.com/signup) (free tier is sufficient)

## Setup Steps

### 1. Install and Configure ngrok

Run the setup script to check your ngrok installation and configuration:

```bash
./setup_ngrok.sh
```

This script will:
- Check if ngrok is installed and help you install it if it's not
- Verify your ngrok authtoken is configured
- Add your ngrok authtoken to `.env.development` if it's not already there
- Test that ngrok is working correctly

### 2. Configure Environment Variables

Copy the environment template to create your configuration file:

```bash
cp .env.development.template .env.development
```

Edit `.env.development` and update the following required values:
- `OPENAI_API_KEY`: Your OpenAI API key for voice processing
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio auth token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number in E.164 format (e.g., +1234567890)

You can leave the other values as their defaults for testing purposes.

### 3. Start the Docker Environment with ngrok

Run the start script:

```bash
./start_docker_with_ngrok.sh
```

This script will:
1. Stop and remove existing containers
2. Create a Docker network
3. Start Redis and PostgreSQL containers
4. Initialize the database schema
5. Build and start the RedBarSushiAI application container
6. Apply necessary fixes from `fix_render_deploy.sh`
7. Start an ngrok container to expose your application
8. Display the ngrok URL you can use to access your application

### 4. Configure Twilio to Use the ngrok URL

After the script runs, you'll see instructions for configuring Twilio:

1. Go to [Twilio TwiML Apps](https://www.twilio.com/console/voice/twiml/apps)
2. Update your TwiML app's Voice 'REQUEST URL' to: `<NGROK_URL>/voice/incoming`
3. Update your TwiML app's Voice 'STATUS CALLBACK URL' to: `<NGROK_URL>/voice/status-callback`

This enables Twilio to connect to your local development environment via the ngrok tunnel.

## Testing Your Application

### Test Voice Calling

1. Call your Twilio phone number
2. The call will be routed through Twilio to your local RedBarSushiAI instance via ngrok
3. You should hear the AI respond and be able to interact with it

### Monitor Logs

View application logs:
```bash
docker logs -f redbarsushi-app
```

View ngrok traffic:
```bash
# Access the ngrok web interface at:
http://localhost:4040
```

### Testing WebSockets

You can test the WebSocket connection using the provided test client:
```bash
python websocket_test_client.py --url ws://localhost:8080/ws/media
```

Or test with the public ngrok WebSocket URL:
```bash
python websocket_test_client.py --url <NGROK_WS_URL>/ws/media
```

## Stopping the Environment

Stop all containers:
```bash
docker stop redbarsushi-app redis postgres ngrok-container
```

Or simply run the start script again to restart everything from scratch.

## Troubleshooting

### ngrok URLs Changing

Free ngrok accounts get dynamic URLs that change each time you restart ngrok. For persistent URLs, upgrade to a paid ngrok plan.

### Twilio Webhook Issues

1. Check the ngrok web interface (http://localhost:4040) to see if requests from Twilio are arriving
2. Verify that your Twilio webhook URLs are configured correctly with the current ngrok URL
3. Ensure your Twilio phone number is configured to use your TwiML app for voice calls

### Redis or PostgreSQL Connection Issues

If the application has trouble connecting to Redis or PostgreSQL, try:
1. Check container logs: `docker logs redis` or `docker logs postgres`
2. Verify network connectivity: `docker network inspect redbarsushi-network`
3. Restart the containers: `./start_docker_with_ngrok.sh`

### Application Errors

For application-specific errors, check the logs:
```bash
docker logs -f redbarsushi-app
```

You can also access the container's shell for debugging:
```bash
docker exec -it redbarsushi-app bash
```