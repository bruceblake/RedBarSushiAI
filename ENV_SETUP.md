# Environment Setup Guide for RedBarSushiAI

This guide explains how to set up and use environment files for the RedBarSushiAI Docker environment.

## Overview

Environment files contain configuration variables needed by the application. Using separate environment files for different environments (development, staging, production) allows for easier configuration management.

## Environment Files

The project supports multiple environment files:

- `.env.development` - For local development (default)
- `.env.staging` - For staging environment
- `.env.production` - For production environment

These files are **not** checked into Git (they're in `.gitignore`) because they contain sensitive information like API keys and passwords.

## Setting Up Your Environment

### 1. Create Your Environment File

We've already created a `.env.development` file with placeholder values. You should:

1. Edit the file and add your actual API keys and credentials:

```bash
# Open the file in your favorite editor
nano .env.development

# Replace placeholder values with your actual credentials
# For example:
# OPENAI_API_KEY=sk_your_actual_key_here
# TWILIO_ACCOUNT_SID=your_actual_sid_here
```

### 2. Using Environment Files with Docker

When starting the Docker environment, specify which environment file to use:

```bash
# Use development environment (default)
./start_docker.sh

# Or explicitly specify development
./start_docker.sh --env development
# Or shorthand
./start_docker.sh -e dev

# Use staging environment (if you've created .env.staging)
./start_docker.sh --env staging
```

The health check script also accepts the environment parameter:

```bash
./check_docker_health.sh --env development
```

## Required Variables

At minimum, your environment file should contain:

```
# Application Environment
FLASK_ENV=development
FLASK_DEBUG=1

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# API Keys (replace with your actual keys)
OPENAI_API_KEY=your_openai_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
```

## Creating Additional Environment Files

To create a staging or production environment file:

```bash
# Create a staging environment file
cp .env.development .env.staging
nano .env.staging

# Update the values for staging
# FLASK_ENV=staging
# FLASK_DEBUG=0
# etc.
```

## Environment Differences

Typical differences between environments:

### Development
- `FLASK_ENV=development`
- `FLASK_DEBUG=1`
- `LOG_LEVEL=DEBUG`
- Often uses local or development API endpoints

### Staging
- `FLASK_ENV=staging`
- `FLASK_DEBUG=0`
- `LOG_LEVEL=INFO`
- Uses staging/test API endpoints

### Production
- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `LOG_LEVEL=WARNING`
- Uses production API endpoints
- May have different database credentials

## Security Notes

1. **Never** commit environment files to Git
2. Keep your API keys and passwords secure
3. Use different credentials for different environments
4. Rotate credentials periodically for security

## Troubleshooting

If you encounter issues with your environment variables:

1. Check the application logs with:
   ```bash
   docker-compose --env-file .env.development logs app
   ```

2. Verify your environment is correctly loaded:
   ```bash
   ./check_docker_health.sh --env development
   ```

3. If you change environment variables, you may need to restart the containers:
   ```bash
   ./start_docker.sh -e development -r
   ```