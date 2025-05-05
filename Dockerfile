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
        # Minimal dependencies for headless mode
        && rm -rf /var/lib/apt/lists/*

# Stage 2: Install dependencies
FROM base AS dependencies

WORKDIR /install

# Copy requirements files
COPY requirements.txt requirements.prod.txt requirements.docker.txt requirements_minimal.txt ./

# Install base Python packages with retries and timeouts
RUN pip install --no-cache-dir --upgrade pip setuptools wheel 

# Install the minimal requirements needed for WebSocket-based Realtime integration
# This ensures we have the core dependencies properly resolved
RUN pip install --no-cache-dir -r requirements_minimal.txt

# For completeness, try to install the full requirements, but we already have the core deps
# We use --no-deps to avoid conflicts with our minimal requirements
RUN if [ -f "requirements.docker.txt" ]; then \
        pip install --no-cache-dir --no-deps -r requirements.docker.txt || true; \
    elif [ -f "requirements.prod.txt" ]; then \
        pip install --no-cache-dir --no-deps -r requirements.prod.txt || true; \
    else \
        pip install --no-cache-dir --no-deps -r requirements.txt || true; \
    fi

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
