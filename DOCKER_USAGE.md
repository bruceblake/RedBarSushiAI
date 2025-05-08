# Docker Usage Guide for RedBarSushiAI

This document provides comprehensive instructions for running the RedBarSushiAI application using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Git repository cloned to your local machine

## Quick Start

The simplest way to get started is to use the provided scripts:

```bash
# Start the application with Docker
./start_docker.sh

# Check the health of the Docker containers
./check_docker_health.sh
```

## Manual Docker Commands

If you prefer to run commands manually, here are the essential Docker Compose commands:

### Starting the Application

```bash
# Start all services in the background
docker-compose up -d

# Start with rebuilding containers
docker-compose up -d --build

# Start with logs displayed in terminal
docker-compose up
```

### Stopping the Application

```bash
# Stop all services but keep volumes
docker-compose down

# Stop all services and remove volumes (resets all data)
docker-compose down -v
```

### Viewing Logs

```bash
# View logs from all services
docker-compose logs

# Follow logs (continuous output)
docker-compose logs -f

# View logs for a specific service
docker-compose logs app
docker-compose logs postgres
docker-compose logs redis
```

### Shell Access

```bash
# Access shell in the app container
docker-compose exec app bash

# Access PostgreSQL CLI
docker-compose exec postgres psql -U postgres -d redbarsushi

# Access Redis CLI
docker-compose exec redis redis-cli
```

## Container Configuration

The application is composed of the following services:

### Web Application (app)

- Flask application serving the RedBarSushiAI APIs
- Exposed on port 8080 (configurable with APP_PORT env var)
- Connected to both PostgreSQL and Redis
- Volumes:
  - `./app:/app/app` - For live code updates
  - `./logs:/app/logs` - For persistent logs

### PostgreSQL Database (postgres)

- Running PostgreSQL 14
- Credentials: 
  - User: `postgres`
  - Password: `postgres`
  - Database: `redbarsushi`
- Exposed on port 5432 (configurable with POSTGRES_PORT env var)
- Volumes:
  - `postgres-data` - Persistent database storage
  - `./db/init:/docker-entrypoint-initdb.d` - Initialization scripts

### Redis (redis)

- Running Redis 6
- Exposed on port 6379 (configurable with REDIS_PORT env var)
- Volume:
  - `redis-data` - Persistent Redis data

## Environment Configuration

### Using Environment Files

The application now supports different environment configurations using `.env` files:

- `.env.development` - For development environment (default)
- `.env.staging` - For staging environment
- `.env.production` - For production environment

To start the application with a specific environment:

```bash
# Start with development environment (default)
./start_docker.sh

# Start with staging environment
./start_docker.sh --env staging

# Start with production environment
./start_docker.sh --env production

# Or use short form
./start_docker.sh -e dev
./start_docker.sh -e prod
```

You can also specify the environment for health checks:

```bash
./check_docker_health.sh --env development
```

### Environment Variables

The environment files should contain these variables:

```bash
# Required Variables
FLASK_ENV=development      # Environment (development/staging/production)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/redbarsushi
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=sk_your_key_here
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here

# Optional Variables
APP_PORT=8080              # Web application port
POSTGRES_PORT=5432         # PostgreSQL port
REDIS_PORT=6379            # Redis port
VOICE_HANDLER=realtime     # Voice handler type
LOG_LEVEL=DEBUG            # Logging level
```

### Creating New Environment Files

To create a new environment file:

1. Copy the template: `cp .env.development .env.staging`
2. Edit the file: `nano .env.staging`
3. Update the environment variables for staging
4. Start with the new config: `./start_docker.sh --env staging`

## Troubleshooting

### PostgreSQL Authentication Issues

If you encounter PostgreSQL authentication errors:

1. First verify the container is running:

```bash
docker-compose ps
```

2. Check the PostgreSQL logs:

```bash
docker-compose logs postgres
```

3. Try connecting manually:

```bash
docker-compose exec postgres psql -U postgres -c "\l"
```

4. If problems persist, try resetting the database:

```bash
docker-compose down -v
docker-compose up -d
```

### Application Startup Issues

If the application container fails to start:

1. Check the application logs:

```bash
docker-compose logs app
```

2. Verify the database is properly initialized:

```bash
docker-compose exec postgres psql -U postgres -d redbarsushi -c "\dt"
```

3. Check the Redis connection:

```bash
docker-compose exec redis redis-cli ping
```

4. Run the health check script for a comprehensive diagnosis:

```bash
./check_docker_health.sh
```

## Data Management

### Backup Database

```bash
docker-compose exec postgres pg_dump -U postgres redbarsushi > backup.sql
```

### Restore Database

```bash
# Stop the containers
docker-compose down

# Remove the database volume
docker volume rm redbarsushi_postgres-data

# Start the containers again
docker-compose up -d

# Restore from backup
cat backup.sql | docker-compose exec -T postgres psql -U postgres redbarsushi
```

## Advanced Usage

### Running Tests in Docker

```bash
# Run unit tests
docker-compose exec app pytest tests/unit

# Run integration tests
docker-compose exec app pytest tests/integration

# Run E2E tests
docker-compose exec app pytest tests/e2e
```

### Rebuilding Specific Services

```bash
# Rebuild only the app service
docker-compose build app

# Rebuild and restart only the app service
docker-compose up -d --build app
```

### Monitoring Resource Usage

```bash
# View container resource usage
docker stats
```

## Docker Compose File Explanation

The `docker-compose.yml` file defines three services:

1. **app**: The main Flask application
2. **postgres**: The PostgreSQL database
3. **redis**: The Redis cache and message broker

Each service has:
- Dependencies on other services
- Volume mounts for persistent storage
- Health checks to ensure services are ready
- Environment variables for configuration
- Exposed ports for external access