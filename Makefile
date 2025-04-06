# Makefile for RedBarSushiAI

# Configuration
PYTHON = python3
PORT = 8080
HOST = 0.0.0.0
APP = run:app
WORKERS = 1
TIMEOUT = 120

# Environment variables for headless operation
export PYNPUT_HEADLESS = 1
export NO_X11 = 1
export HEADLESS = 1
export DISPLAY = :99
export OPENAI_REALTIME_AVAILABLE = 1

# Default target
.PHONY: all
all: help

# Help target
.PHONY: help
help:
	@echo "RedBarSushiAI Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make run             Run the application in development mode"
	@echo "  make run-prod        Run the application in production mode with Gunicorn"
	@echo "  make worker          Run Celery worker"
	@echo "  make test            Run all tests"
	@echo "  make test-websocket  Test WebSocket functionality"
	@echo "  make diagnose        Run diagnostics"
	@echo "  make install         Install dependencies"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-run      Run Docker container"
	@echo "  make clean           Clean temporary files"
	@echo ""

# Application targets
.PHONY: run
run:
	FLASK_DEBUG=1 FLASK_APP=$(APP) $(PYTHON) run.py

.PHONY: run-prod
run-prod:
	gunicorn --worker-class=gevent --workers=$(WORKERS) --threads=4 --timeout=$(TIMEOUT) --bind=$(HOST):$(PORT) $(APP)

.PHONY: worker
worker:
	celery -A celery_app worker --loglevel=INFO

# Testing targets
.PHONY: test
test:
	pytest

.PHONY: test-websocket
test-websocket:
	$(PYTHON) test_websocket.py --server http://$(HOST):$(PORT) --test all

.PHONY: diagnose
diagnose:
	$(PYTHON) diagnose.py

# Installation targets
.PHONY: install
install:
	pip install -r requirements.txt
	pip install websockets==13.1 flask-sock==0.7.0 simple-websocket==1.1.0
	pip install openai-realtime-client==0.1.0 python-socketio==5.8.0 eventlet==0.33.3

# Docker targets
.PHONY: docker-build
docker-build:
	docker build -t redbarsushiai .

.PHONY: docker-run
docker-run:
	docker run -p $(PORT):$(PORT) -e DOCKER_CONTAINER=true redbarsushiai

# Cleanup target
.PHONY: clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .cache/