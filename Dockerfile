# Stage 1: Base image with system dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORCE_HEADLESS=true \
    REALTIME_ENABLED=true

# Install system dependencies and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
        libpq-dev \
        curl \
        ffmpeg \
        # Audio dependencies
        portaudio19-dev \
        libportaudio2 \
        libportaudiocpp0 \
        python3-dev \
        # Minimal dependencies for headless mode
        && rm -rf /var/lib/apt/lists/*

# Stage 2: Install dependencies
FROM base AS dependencies

WORKDIR /install

# Copy requirements files
COPY requirements.txt requirements.prod.txt requirements.docker.txt requirements_minimal.txt ./

# Install base Python packages with retries and timeouts
RUN pip install --no-cache-dir --upgrade pip setuptools wheel 

# Try to install the full requirements first
RUN set -e; \
    if [ -f "requirements.docker.txt" ]; then \
        echo "Attempting to install Docker-specific requirements..."; \
        if pip install --no-cache-dir -r requirements.docker.txt; then \
            echo "✅ Successfully installed Docker requirements"; \
        else \
            echo "❌ Failed to install Docker requirements. Falling back to minimal requirements."; \
            pip install --no-cache-dir -r requirements_minimal.txt; \
            echo "⚠️ Only minimal WebSocket requirements installed. Some functionality may not work."; \
        fi; \
    elif [ -f "requirements.prod.txt" ]; then \
        echo "Attempting to install production requirements..."; \
        if pip install --no-cache-dir -r requirements.prod.txt; then \
            echo "✅ Successfully installed production requirements"; \
        else \
            echo "❌ Failed to install production requirements. Falling back to minimal requirements."; \
            pip install --no-cache-dir -r requirements_minimal.txt; \
            echo "⚠️ Only minimal WebSocket requirements installed. Some functionality may not work."; \
        fi; \
    else \
        echo "Attempting to install standard requirements..."; \
        if pip install --no-cache-dir -r requirements.txt; then \
            echo "✅ Successfully installed standard requirements"; \
        else \
            echo "❌ Failed to install standard requirements. Falling back to minimal requirements."; \
            pip install --no-cache-dir -r requirements_minimal.txt; \
            echo "⚠️ Only minimal WebSocket requirements installed. Some functionality may not work."; \
        fi; \
    fi;

# Ensure the critical WebSocket packages are installed
RUN pip install --no-cache-dir --upgrade flask-sock==0.7.0 gevent-websocket==0.10.1

# Dependencies are already installed in previous step

# Stage 3: Final runtime image
FROM base AS final

WORKDIR /app

# Copy only installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/backups

# Copy application code
COPY . .

# Ensure entrypoint is executable
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Add wait-for-it script for database dependency management
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /usr/local/bin/wait-for-it.sh
RUN chmod +x /usr/local/bin/wait-for-it.sh

# Make directories writable
RUN chmod -R 755 /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/healthcheck || exit 1

# Expose port
EXPOSE 8080

# Use our entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]

# Use gevent-websocket worker for WebSocket support
CMD ["gunicorn", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "-w", "2", "--bind", "0.0.0.0:8080", "--timeout", "120", "--log-level", "info"]
