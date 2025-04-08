# Stage 1: Base image with system dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYNPUT_HEADLESS=1 \
    DISPLAY=:99 \
    NO_X11=1 \
    HEADLESS=1 \
    OPENAI_REALTIME_AVAILABLE=1

# Install system dependencies and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
        libpq-dev \
        curl \
        portaudio19-dev \
        python3-pyaudio \
        ffmpeg \
        xvfb \
        x11-utils \
        dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Install dependencies
FROM base AS dependencies

WORKDIR /install

# Copy requirements files
COPY requirements.txt requirements.prod.txt requirements.docker.txt ./

# Install base Python packages with retries and timeouts
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Try docker requirements first, then production, then default
    if [ -f "requirements.docker.txt" ]; then \
        # Try to install with --no-deps first to avoid conflicts
        pip install --no-cache-dir -r requirements.docker.txt || \
        # If that fails, try with dependency resolution
        pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.docker.txt || \
        # If that still fails, fallback to regular install
        pip install --no-cache-dir -r requirements.txt; \
    elif [ -f "requirements.prod.txt" ]; then \
        pip install --no-cache-dir -r requirements.prod.txt || \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi && \
    # Ensure OpenAI and OpenAI Agents are properly installed (handling potential Git dependency)
    pip install --no-cache-dir openai>=1.68.2 && \
    pip install --no-cache-dir git+https://github.com/openai/openai-agents-python.git

# Install specific packages explicitly with version pinning
RUN pip install --no-cache-dir psycopg2-binary==2.9.9 \
                             gunicorn==21.2.0 \
                             gevent==23.9.1 \
                             flask-sock==0.7.0 \
                             gevent-websocket==0.10.1 \
                             simple-websocket==1.1.0 \
                             websockets==13.1 \
                             openai-realtime-client==0.1.0

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

# Use our updated entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command - using single worker with memory optimizations for stability
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120", "--worker-class", "gevent", "--worker-connections", "500", "--max-requests", "500", "--max-requests-jitter", "50", "--log-level", "debug", "--max-memory-per-child", "256000"]
