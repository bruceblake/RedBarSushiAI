# RedBarSushiAI Development Environment

This document explains how to use the dedicated development environment for RedBarSushiAI that aligns with the Render staging setup.

## Configuration Files

The development environment uses the following configuration files:

- `.env.development` - Environment variables for the development setup
- `docker-compose.development.yml` - Docker Compose configuration for development

## Key Features

- Single worker Uvicorn configuration (same as Render)
- Isolated network and volume configuration
- Headless mode with real-time audio processing support
- Hot-reload of application code for faster development
- Port configuration aligned with staging environment

## Getting Started

### Start the Development Environment

```bash
./restart_docker_dev.sh
```

This script will:
1. Check for required configuration files
2. Stop and remove any existing development containers
3. Start the containers with the development configuration
4. Wait for all containers to be healthy
5. Display container status and useful commands

### Clean Restart

To perform a clean restart (removing persistent database data):

```bash
./restart_docker_dev.sh --clean
```

### Accessing Services

- **API**: http://localhost:8080
- **WebSocket Test**: ws://localhost:8080/ws-test/test
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6380

### Managing the Environment

- **View logs**: `docker-compose -f docker-compose.development.yml logs -f`
- **Stop services**: `docker-compose -f docker-compose.development.yml down`
- **Connect to app shell**: `docker exec -it redbarsushi-app-dev bash`
- **Connect to database**: `docker exec -it redbarsushi-postgres-dev psql -U postgres -d redbarsushi`

## Differences from Production

The development environment differs from production in these ways:

1. Uses a single worker instead of multiple workers
2. Enables debug-level logging
3. Uses different port mappings to avoid conflicts
4. Mounts local code directories for hot-reload
5. Uses named containers with -dev suffix

## Troubleshooting

### Database Connection Issues

If you experience database connection issues, check:

```bash
docker logs redbarsushi-postgres-dev
```

You may need to clean the database volume:

```bash
./restart_docker_dev.sh --clean
```

### WebSocket Connection Issues

For WebSocket connection issues, check:

```bash
docker logs redbarsushi-app-dev | grep -E "WebSocket|ws-test"
```

### Redis Connection Issues

Verify Redis is running:

```bash
docker exec -it redbarsushi-redis-dev redis-cli ping
```

Should return "PONG"