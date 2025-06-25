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

# Copy requirements file
COPY requirements.txt ./

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

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

# Make sure .env file exists (will be used for staging environment)
RUN touch /app/.env

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