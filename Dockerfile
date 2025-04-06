# 1. Base Image: Use an official Python image. Choose a version you use.
FROM python:3.11-slim

# 2. Set Environment Variables (Good Practice - Corrected Syntax)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set Working Directory inside the container
WORKDIR /app

# 4. Install System Dependencies (Install git HERE)
#    Update package lists, install git, then clean up apt cache
RUN apt-get update && \
    apt-get install -y git --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 5. Copy requirements first (leverages Docker cache)
COPY requirements.txt .

# 6. Install Python Dependencies (Now git is available)
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy the rest of your application code
COPY . .

# 8. Expose the port Render will expect (Render sets the PORT env var)
# EXPOSE 10000 # Optional documentation

# 9. Command to run the application using a production server
#    IMPORTANT: Use the $PORT environment variable provided by Render.
#    Replace 'your_main_app_file:app' with your actual WSGI/ASGI object.
#
#    For Flask with Gunicorn: (Assuming your Flask app object is 'app' in 'main.py')
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "main:app"]
#
#    For FastAPI with Uvicorn/Gunicorn: (Assuming your FastAPI app object is 'app' in 'main.py')
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:$PORT", "main:app"]
