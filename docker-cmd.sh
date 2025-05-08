#!/bin/bash
# Script to run commands inside the Docker environment

if [ $# -lt 1 ]; then
    echo "Usage: $0 <container> [command]"
    echo "Containers: app, mcp, postgres, redis"
    echo "Examples:"
    echo "  $0 app python -m flask routes"
    echo "  $0 mcp ls -la"
    echo "  $0 postgres psql -U redbarsushi_staging_db_user -d redbarsushi_staging_db"
    echo "  $0 redis redis-cli"
    exit 1
fi

CONTAINER=$1
shift

# If no command is provided, open a shell
if [ $# -eq 0 ]; then
    case $CONTAINER in
        app)
            # Default to bash for the app container
            docker exec -it redbarsushi_app bash
            ;;
        mcp)
            # Default to bash for the mcp container
            docker exec -it redbarsushi_mcp bash
            ;;
        postgres)
            # Default to psql for the postgres container
            docker exec -it redbarsushi_postgres psql -U redbarsushi_staging_db_user -d redbarsushi_staging_db
            ;;
        redis)
            # Default to redis-cli for the redis container
            docker exec -it redbarsushi_redis redis-cli
            ;;
        *)
            echo "Unknown container: $CONTAINER"
            echo "Available containers: app, mcp, postgres, redis"
            exit 1
            ;;
    esac
else
    # Execute the provided command
    case $CONTAINER in
        app|mcp|postgres|redis)
            docker exec -it redbarsushi_$CONTAINER "$@"
            ;;
        *)
            echo "Unknown container: $CONTAINER"
            echo "Available containers: app, mcp, postgres, redis"
            exit 1
            ;;
    esac
fi