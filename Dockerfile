# Stage 1: Base image with system dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Install dependencies
FROM base AS dependencies

WORKDIR /install

# Copy requirements files
COPY requirements.txt requirements.prod.txt ./

# Install base Python packages with retries and timeouts
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Try production requirements first (more stable)
    if [ -f "requirements.prod.txt" ]; then \
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
                             flask-sock==0.6.0 \
                             gevent-websocket==0.10.1

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

# Default command
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120", "--worker-class", "gevent"]
