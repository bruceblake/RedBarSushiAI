#!/bin/bash
# Simple test runner for local development

set -e

echo "🧪 Running tests locally with Docker..."

# Run unit tests
echo "📦 Running unit tests..."
docker-compose -f docker-compose.test.yml run --rm app-test pytest tests/unit -v

# Clean up
docker-compose -f docker-compose.test.yml down

echo "✅ Tests complete!"