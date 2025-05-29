#!/bin/bash
# Run tests in Docker environment

set -e

echo "🐳 Starting Docker services..."
docker-compose up -d postgres redis

echo "⏳ Waiting for services to be healthy..."
docker-compose run --rm app bash -c "
  until pg_isready -h postgres -U postgres; do
    echo 'Waiting for postgres...'
    sleep 1
  done
  until redis-cli -h redis ping; do
    echo 'Waiting for redis...'
    sleep 1
  done
"

echo "🗄️ Creating test database..."
docker-compose exec -T postgres psql -U postgres -c "CREATE DATABASE redbarsushi_test;" 2>/dev/null || true
docker-compose exec -T postgres psql -U postgres -d redbarsushi_test < db/init/01_schema.sql

echo "🧪 Running tests..."
case "${1:-all}" in
  unit)
    echo "Running unit tests..."
    docker-compose --profile test run --rm test pytest tests/unit -v
    ;;
  integration)
    echo "Running integration tests..."
    docker-compose --profile test run --rm test pytest tests/integration -v
    ;;
  e2e)
    echo "Running E2E tests..."
    docker-compose --profile test run --rm test pytest tests/e2e -v
    ;;
  specific)
    echo "Running specific test: ${2}"
    docker-compose --profile test run --rm test pytest "${2}" -v
    ;;
  *)
    echo "Running all tests..."
    docker-compose --profile test run --rm test
    ;;
esac

echo "✅ Tests completed!"

# Optional: Stop services
if [ "${KEEP_SERVICES:-false}" != "true" ]; then
  echo "🛑 Stopping Docker services..."
  docker-compose down
fi