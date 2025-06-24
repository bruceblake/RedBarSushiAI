#!/bin/bash

# Run tests in Docker with proper setup

# Build test image if needed
if [[ "$1" == "--build" ]]; then
    echo "Building test Docker image..."
    docker build -f docker/tests/Dockerfile.test -t redbarsushi-test .
    shift
fi

# Default to running all tests if no args provided
if [ $# -eq 0 ]; then
    TEST_ARGS="tests/"
else
    TEST_ARGS="$@"
fi

# Run tests in a dedicated container
docker run --rm \
    --network redbarsushi-network \
    -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@redbarsushi-postgres:5432/redbarsushi \
    -e REDIS_URL=redis://redbarsushi-redis:6379/0 \
    -e TESTING=true \
    -e PYTHONPATH=/app \
    -e LOG_LEVEL=WARNING \
    -v $(pwd)/tests:/app/tests \
    -v $(pwd)/app:/app/app \
    redbarsushi-test \
    pytest $TEST_ARGS