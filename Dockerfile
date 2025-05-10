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

# Copy requirements files and install script
COPY requirements.strict.txt requirements.txt requirements.prod.txt requirements.docker.txt requirements_minimal.txt install_all_dependencies.sh ./

# Make install script executable
RUN chmod +x ./install_all_dependencies.sh

# Install base Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Try to install using the strict requirements first
RUN set -e; \
    if [ -f "requirements.strict.txt" ]; then \
        echo "Installing from strict requirements file..."; \
        if pip install --no-cache-dir -r requirements.strict.txt; then \
            echo "✅ Successfully installed all dependencies from strict requirements"; \
        else \
            echo "❌ Failed to install from strict requirements. Falling back to Docker requirements."; \
            # Try Docker-specific requirements
            if [ -f "requirements.docker.txt" ] && pip install --no-cache-dir -r requirements.docker.txt; then \
                echo "✅ Successfully installed Docker requirements"; \
            elif [ -f "requirements.prod.txt" ] && pip install --no-cache-dir -r requirements.prod.txt; then \
                echo "✅ Successfully installed production requirements"; \
            elif [ -f "requirements.txt" ] && pip install --no-cache-dir -r requirements.txt; then \
                echo "✅ Successfully installed standard requirements"; \
            else \
                echo "❌ All requirements files failed. Falling back to minimal requirements."; \
                pip install --no-cache-dir -r requirements_minimal.txt; \
                echo "⚠️ Only minimal WebSocket requirements installed. Some functionality may not work."; \
            fi; \
        fi; \
    else \
        # Fall back to previous approach if strict requirements file is missing
        if [ -f "requirements.docker.txt" ] && pip install --no-cache-dir -r requirements.docker.txt; then \
            echo "✅ Successfully installed Docker requirements"; \
        elif [ -f "requirements.prod.txt" ] && pip install --no-cache-dir -r requirements.prod.txt; then \
            echo "✅ Successfully installed production requirements"; \
        elif [ -f "requirements.txt" ] && pip install --no-cache-dir -r requirements.txt; then \
            echo "✅ Successfully installed standard requirements"; \
        else \
            echo "❌ All requirements files failed. Falling back to minimal requirements."; \
            pip install --no-cache-dir -r requirements_minimal.txt; \
            echo "⚠️ Only minimal WebSocket requirements installed. Some functionality may not work."; \
        fi; \
    fi;

# Ensure the critical FastAPI and ASGI packages are installed
# Use either pydantic v1 without pydantic-settings (recommended)
RUN pip install --no-cache-dir --upgrade fastapi==0.115.11 uvicorn==0.34.0 websocket-client==1.7.0 websockets==13.1 pydantic==1.10.8

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
COPY fastapi_render_entrypoint.sh /docker-entrypoint.sh
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

# Use Uvicorn for FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--log-level", "info"]