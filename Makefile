# Makefile for RedBarSushiAI testing

.PHONY: help test test-unit test-integration test-e2e test-fast test-coverage test-parallel test-staging test-watch clean-test setup-test

# Default target
help:
	@echo "RedBarSushiAI Test Commands:"
	@echo "  make test              - Run all tests with mocks"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-e2e          - Run E2E tests only"
	@echo "  make test-fast         - Run fast tests only (no slow tests)"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-parallel     - Run tests in parallel"
	@echo "  make test-staging      - Run E2E tests with real services (staging)"
	@echo "  make test-watch        - Watch files and run tests on change"
	@echo "  make setup-test        - Setup test environment"
	@echo "  make clean-test        - Clean up test environment"

# Setup test environment
setup-test:
	@echo "Setting up test environment..."
	docker-compose -f docker-compose.test.yml up -d postgres-test redis-test
	@echo "Waiting for services..."
	@sleep 5
	@echo "Test environment ready!"

# Clean test environment
clean-test:
	@echo "Cleaning up test environment..."
	docker-compose -f docker-compose.test.yml down -v
	rm -rf htmlcov/
	rm -rf test-results/
	rm -rf .coverage
	rm -rf .pytest_cache/
	@echo "Cleanup complete!"

# Run all tests
test: setup-test
	python run_tests.py all

# Run unit tests
test-unit: setup-test
	python run_tests.py unit

# Run integration tests
test-integration: setup-test
	python run_tests.py integration

# Run E2E tests
test-e2e: setup-test
	python run_tests.py e2e

# Run fast tests only
test-fast: setup-test
	python run_tests.py fast

# Run tests with coverage
test-coverage: setup-test
	python run_tests.py coverage

# Run tests in parallel
test-parallel: setup-test
	python run_tests.py parallel

# Run staging tests with real services
test-staging:
	@echo "Running staging tests with real services..."
	@echo "Make sure you have set staging credentials!"
	FASTAPI_ENV=staging python run_tests.py staging

# Watch tests
test-watch: setup-test
	python run_tests.py watch

# Docker-based testing
docker-test:
	docker-compose -f docker-compose.test.yml run --rm test-runner

# Specific test file
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=test_agents.py"; \
		exit 1; \
	fi
	python run_tests.py unit --file $(FILE)

# Performance testing
test-performance: setup-test
	pytest tests/e2e/test_performance.py -v -s

# Generate test report
test-report: test-coverage
	@echo "Generating test report..."
	@echo "Coverage report: htmlcov/index.html"
	@if command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	fi

# CI/CD test command
test-ci:
	docker-compose -f docker-compose.test.yml run --rm test-runner pytest tests/unit tests/integration -v --junit-xml=test-results/junit.xml

# Development workflow
dev-test:
	@echo "Running development tests (fast feedback)..."
	python run_tests.py fast --no-cleanup

# Quick smoke test
smoke-test:
	pytest tests/unit/test_agents.py::TestAsyncFrontlineVoiceAgentAI::test_greeting_response -v