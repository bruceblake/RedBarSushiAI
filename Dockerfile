# Base Image: Python 3.11 (matches your development environment)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Render sets PORT environment variable automatically
ENV PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (leverages Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PostgreSQL drivers and other dependencies for Docker environment
RUN pip install --no-cache-dir psycopg2-binary

# Install Gunicorn with websocket support
RUN pip install --no-cache-dir gunicorn flask-sock gevent-websocket

# Copy the application code
COPY . .

# Create directories for logs and data if they don't exist
RUN mkdir -p /app/logs /app/data /app/backups

# Make the entrypoint script executable
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port for documentation (Render still uses the PORT env var)
EXPOSE 8080

# Use entrypoint script to initialize and run the application
ENTRYPOINT ["/docker-entrypoint.sh"]
