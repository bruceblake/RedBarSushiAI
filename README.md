# RedBarSushiAI

![Build Status](https://img.shields.io/github/actions/workflow/status/yourusername/RedBarSushiAI/ci.yml?branch=main)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

**RedBarSushiAI** is an AI-powered voice ordering system for Red Bar Sushi, enabling customers to place orders and get menu information over the phone. It features seamless menu management, real-time order status, and multi-location support—all driven by state-of-the-art voice and messaging APIs.

---

## 🚀 Features
- Voice-based ordering (Twilio integration)
- Menu inquiries & recommendations
- Order validation & processing (Deliverect integration)
- Multi-location support
- Real-time order status & SMS confirmations
- WebSocket-based audio processing

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis (for Celery)
- OpenAI API key
- Twilio account
- Deliverect API credentials

### Installation
1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/RedBarSushiAI.git
   cd RedBarSushiAI
   ```
2. **Create and activate a virtual environment:**
   ```sh
   python -m venv venv
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Copy and edit environment file:**
   ```sh
   cp .env.example .env
   # Edit .env with your API keys and config
   ```
5. **Create the database:**
   ```sh
   createdb redbarsushi
   ```
6. **Run database migrations:**
   ```sh
   python migrate_db.py
   ```

---

## ▶️ Usage

- Start the Flask server:
  ```sh
  python run.py
  ```
- Start Celery worker (in another terminal):
  ```sh
  celery -A celery_app worker --loglevel=INFO
  ```
- For development with auto-reload:
  ```sh
  FLASK_DEBUG=1 FLASK_APP=run.py flask run
  ```

---

## 🧪 Testing

### Unit and Integration Tests
- Run all tests:
  ```sh
  pytest
  ```
- Run a specific test:
  ```sh
  pytest tests/test_file.py::test_function
  ```
- Run tests in CI mode (without external API dependencies):
  ```sh
  TESTING=True DISABLE_OPENAI=True pytest
  ```

### End-to-End Tests
- For most systems:
  ```sh
  ./run-full-e2e-tests.sh
  ```
- For Arch Linux:
  ```sh
  ./run-e2e-tests-arch.sh
  ```
- View test logs:
  ```sh
  ./view-test-logs.sh list
  ./view-test-logs.sh latest
  ```
- See [ARCH_LINUX_TESTING.md](ARCH_LINUX_TESTING.md) for Arch Linux testing
- See [GITHUB_ACTIONS_TESTING.md](GITHUB_ACTIONS_TESTING.md) for CI/CD testing

## 🧹 Code Quality

- Format Python code with Black:
  ```sh
  black app tests
  ```
- Check code formatting without making changes:
  ```sh
  black --check app tests
  ```
- Lint code with Ruff:
  ```sh
  ruff check app tests
  ```
- Fix auto-fixable linting issues:
  ```sh
  ruff check --fix app tests
  ```

---

## 🐳 Docker

- Build the Docker image:
  ```sh
  docker build -t redbarsushiai .
  ```
- Run the container:
  ```sh
  docker run -p 8080:8080 -e DOCKER_CONTAINER=true redbarsushiai
  ```

---

## 🚦 CI/CD Pipeline

- Automated tests and checks on every push and pull request
- E2E tests can be run manually via GitHub Actions workflow
- Deploys to staging from `staging` branch
- Deploys to production from `main` branch
- See `.github/workflows/` for details:
  - `run-tests.yml`: Regular unit and integration tests
  - `e2e-tests.yml`: End-to-end tests with real APIs (manual trigger)

---

## 📁 Menu Data

Both `menu_data.json` and `redbar_menu_data.json` are present for menu data. Keep both unless you are sure one is obsolete.

---

## 🧩 How It Works

### System Workflow

1. **Customer Call**: Customer calls the Red Bar Sushi phone number (Twilio).
2. **Voice Interaction**: Twilio forwards the call to the Flask backend, which uses OpenAI for speech recognition and intent parsing.
3. **Menu & Order**: The backend uses `menu_data.json`/`redbar_menu_data.json` to answer menu questions and take orders.
4. **Order Validation**: Orders are validated and processed via Deliverect API.
5. **Order Status**: Real-time order status is provided via SMS (Twilio) and WebSocket audio updates.
6. **Multi-location**: System supports multiple restaurant locations.

**Data Flow:**
- Customer → Twilio → Flask API → OpenAI/Deliverect → Customer (via SMS/voice)

### CI/CD & Deployment Workflow

1. **Push/PR to GitHub**: Code pushed to `development`, `staging`, or `main` branches triggers GitHub Actions workflows.
2. **CI Pipeline**:
   - Runs tests (pytest)
   - Lints code
   - Checks security
3. **CD Pipeline**:
   - Deploys to **staging** on push to `staging`
   - Deploys to **production** on push to `main`
   - Uses Render for hosting and deployment
4. **Secrets & Env Vars**: Managed via GitHub Secrets and `.env` files.

**External Services:**
- **Twilio**: Voice/SMS communication
- **OpenAI**: Natural language processing
- **Deliverect**: Order management
- **Render**: Hosting & deployment

---

## 📚 Documentation
- [docs/README.md](docs/README.md) — Project documentation index
- [.env.example](.env.example) — Environment variables reference

---

## 🤝 Contributing

Pull requests are welcome! Please:
- Fork the repo and create a feature branch
- Write tests for new features
- Follow the existing code style
- Open a PR to `development` or `staging`

---

## 📬 Support

For issues, open a GitHub issue or contact the maintainer.

---

## License

Proprietary - All Rights Reserved

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

### Testing GitHub Actions Locally

To test GitHub Actions workflows locally, you can use [nektos/act](https://github.com/nektos/act). We've provided a setup script:

1. Run the installation script:
```bash
./act-install.sh
```

2. Test a specific job in a workflow:
```bash
# Test the production verification job
act -j production-verification -W .github/workflows/promote-to-main.yml

# Test the CI workflow
act -j test -W .github/workflows/ci.yml
```

3. Test a workflow on a specific event:
```bash
# Test on push
act push

# Test on pull request
act pull_request
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