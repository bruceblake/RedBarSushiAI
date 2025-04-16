# RedBarSushiAI

An AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone.

## Features

- Voice-based ordering system using Twilio
- Menu inquiries and recommendations
- Order validation and processing via Deliverect
- Multi-location support
- Real-time order status updates
- SMS confirmation messages
- WebSocket-based real-time audio processing

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis (for Celery)
- OpenAI API key
- Twilio account
- Deliverect API credentials

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/RedBarSushiAI.git
   cd RedBarSushiAI
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create environment file:
   ```
   cp .env.example .env
   ```
   
5. Edit the `.env` file with your API keys and configuration.

6. Create the database:
   ```
   createdb redbarsushi  # If using PostgreSQL CLI
   ```
   
7. Run database migrations:
   ```
   python migrate_db.py
   ```

### Running the Application

#### Start the Flask server:
```
python run.py
```

#### Start Celery worker (in a separate terminal):
```
celery -A celery_app worker --loglevel=INFO
```

#### Run with debug:
```
FLASK_DEBUG=1 FLASK_APP=run.py flask run
```

## Development Workflow

### Branching Strategy

- `main`: Production-ready code
- `staging`: Pre-production for testing
- `development`: Active development

### Working with Branches

```bash
# Create a new feature branch
git checkout -b feature/my-new-feature

# Make changes, then commit
git add .
git commit -m "Add my new feature"

# Push to remote
git push -u origin feature/my-new-feature

# Create a PR to staging branch when ready
```

### CI/CD Pipeline

Our CI/CD pipeline automatically:

1. Runs tests on every push and PR
2. Checks code quality and security
3. Deploys to staging environment from staging branch
4. Deploys to production environment from main branch

## Testing

Run tests with:
```
pytest
```

Run a specific test:
```
pytest tests/test_file.py::test_function
```

## Docker Deployment

```bash
# Build the Docker image
docker build -t redbarsushiai .

# Run the container
docker run -p 8080:8080 -e DOCKER_CONTAINER=true redbarsushiai
```

## Deployment

The application is deployed on Render with separate environments:

- Production: https://redbarsushi-web.onrender.com
- Staging: https://redbarsushi-staging.onrender.com

To deploy:
1. Create a PR to the staging branch
2. After review and testing, PR to main
3. GitHub Actions will handle the deployment

## Location Management

To work with locations:

```bash
# List all registered locations
python manage_locations.py list --url https://redbarsushi-staging.onrender.com

# Register a new location
python manage_locations.py register new-location-id "New Location Name" --url https://redbarsushi-staging.onrender.com

# Get information about a location
python manage_locations.py info location-id --url https://redbarsushi-staging.onrender.com

# Test webhooks for a location
python manage_locations.py test-webhooks location-id --url https://redbarsushi-staging.onrender.com
```

## Environment Variables

See `.env.example` for all required environment variables.

## Documentation

Additional documentation:

- [Deliverect Integration](DELIVERECT_INTEGRATION.md)
- [Environment Variables](ENVIRONMENT_VARS.md)
- [Migration Guide](MIGRATION_GUIDE.md)
- [Real-time Audio Processing](REALTIME_AUDIO.md)

## License

Proprietary - All Rights Reserved