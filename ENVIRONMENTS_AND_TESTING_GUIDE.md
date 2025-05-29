# Environments and Testing Guide

## Overview

RedBarSushiAI uses a three-tier environment strategy with comprehensive testing at each level:

```
Development (Local) → Staging (Render) → Production (Render)
         ↓                    ↓                    ↓
    Unit Tests         Integration Tests      E2E Tests
```

## 1. Development Environment (Local)

### Purpose
- Active development and debugging
- Quick iteration and testing
- Direct access to logs and debugging tools

### Setup
```bash
# Using Docker (recommended)
docker-compose up -d

# Direct execution
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Configuration
- **Database**: `postgresql://postgres:postgres@localhost:5432/redbarsushi`
- **Redis**: `redis://localhost:6379/0`
- **Environment**: `FASTAPI_ENV=development`
- **Features**:
  - Hot reload enabled
  - Debug logging
  - Local file system access
  - Direct database access

### Testing in Development
```bash
# Run all tests locally
./run-docker-tests.sh

# Run specific test types
./run-docker-tests.sh unit        # Fast, mocked tests
./run-docker-tests.sh integration # With local services
./run-docker-tests.sh e2e         # Full system tests

# Run without Docker
pytest tests/unit -v              # Requires local services
```

### When to Use
- Writing new features
- Debugging issues
- Running unit tests during development
- Testing with local Twilio/ngrok setup

## 2. Staging Environment (Render)

### Purpose
- Pre-production testing
- Integration testing with real services
- Performance testing
- UAT (User Acceptance Testing)

### Deployment
```bash
# Automatic deployment on push to staging branch
git push origin staging

# Manual deployment
render deploy --service-name redbarsushi-staging
```

### Configuration
- **URL**: `https://redbarsushi-staging.onrender.com`
- **Database**: Render PostgreSQL (staging instance)
- **Redis**: Render Redis (staging instance)
- **Environment**: `FASTAPI_ENV=staging`
- **Features**:
  - Real Twilio integration
  - Real OpenAI API calls
  - Deliverect staging API
  - Full monitoring and logging

### Testing in Staging
```yaml
# Automated tests run on deployment
- Integration tests with real APIs
- E2E tests with real phone calls
- Load testing (optional)
- Security scanning
```

### When to Use
- Testing Twilio webhooks with real phone numbers
- Testing Deliverect integration with staging POS
- Performance testing
- Final validation before production

## 3. Production Environment (Render)

### Purpose
- Live customer-facing system
- Real orders and payments
- High availability and monitoring

### Deployment
```bash
# Automatic deployment on push to main branch
git push origin main

# Manual deployment (requires approval)
render deploy --service-name redbarsushi-production
```

### Configuration
- **URL**: `https://redbarsushi.onrender.com`
- **Database**: Render PostgreSQL (production instance)
- **Redis**: Render Redis (production instance)
- **Environment**: `FASTAPI_ENV=production`
- **Features**:
  - Production Twilio phone numbers
  - Production Deliverect API
  - Enhanced monitoring
  - Automated backups
  - Rate limiting

### Testing in Production
- **Smoke tests** after deployment
- **Synthetic monitoring** (scheduled test calls)
- **Real user monitoring**
- **A/B testing** for new features

## Testing Strategy by Environment

### 1. Unit Tests (Development)

**What**: Test individual components in isolation
**Where**: Local development environment
**When**: During development, before commits

```python
# Example: Testing FSM transitions
async def test_greeting_to_main_menu_transition(fsm):
    fsm.context["greeting_sent"] = True
    await fsm.process_event(ConversationEvent.USER_PROVIDES_NAME)
    assert fsm.current_state == ConversationState.MAIN_MENU
```

**Characteristics**:
- Fast execution (< 5 seconds total)
- Heavy mocking of external services
- Focus on business logic
- No real API calls

### 2. Integration Tests (Development + Staging)

**What**: Test component interactions with real services
**Where**: Local with Docker, CI/CD, Staging
**When**: Before merging PRs, in staging

```python
# Example: Testing agent orchestration with database
async def test_menu_agent_with_real_db(orchestrator, test_db):
    # Uses real database but mocks external APIs
    response = await orchestrator.process_voice_input(
        transcript="What sushi rolls do you have?"
    )
    assert "California Roll" in response
```

**Characteristics**:
- Moderate execution time (30-60 seconds)
- Real database and Redis
- Selective mocking (e.g., mock Twilio, real DB)
- Tests data flow between components

### 3. E2E Tests (Staging + Limited Production)

**What**: Test complete user journeys
**Where**: Staging environment, production smoke tests
**When**: Before production deployment, after deployment

```python
# Example: Complete order flow
async def test_complete_phone_order(test_phone_client):
    # Makes real phone call in staging
    call = await test_phone_client.make_call("+15551234567")
    await call.say("My name is John")
    await call.say("I'd like to order two California rolls")
    await call.say("That's all")
    await call.say("Pickup please")
    
    order = await get_latest_order()
    assert order.status == "confirmed"
    assert order.total_items == 2
```

**Characteristics**:
- Longer execution (2-5 minutes)
- Real services end-to-end
- Actual phone calls in staging
- Validates business workflows

## Environment-Specific Features

### Development Only
- Hot reload
- Debug endpoints (`/debug/*`)
- Verbose logging
- Local file uploads
- Direct database access

### Staging Only
- Test phone numbers
- Webhook testing endpoints
- Performance profiling
- Test payment processing
- Load testing capabilities

### Production Only
- Rate limiting
- Enhanced security headers
- Automated backups
- PCI compliance (if payments enabled)
- Real-time monitoring alerts

## Testing Flow Example

1. **Developer writes feature**:
   ```bash
   # Development environment
   ./run-docker-tests.sh unit  # Quick validation
   ```

2. **Before creating PR**:
   ```bash
   # Development environment
   ./run-docker-tests.sh      # All tests locally
   ```

3. **PR created**:
   ```yaml
   # CI/CD automatically runs
   - Unit tests (mocked)
   - Integration tests (Docker)
   - Code quality checks
   ```

4. **Merged to staging**:
   ```yaml
   # Staging deployment
   - Deploy to staging
   - Run integration tests
   - Run E2E tests
   - Manual QA testing
   ```

5. **Merged to production**:
   ```yaml
   # Production deployment
   - Deploy to production
   - Run smoke tests
   - Monitor error rates
   - Check business metrics
   ```

## Environment Variables by Environment

### Common (All Environments)
```bash
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
DELIVERECT_API_KEY=...
```

### Development
```bash
FASTAPI_ENV=development
DATABASE_URL=postgresql://localhost:5432/redbarsushi
LOG_LEVEL=DEBUG
RELOAD=true
```

### Staging
```bash
FASTAPI_ENV=staging
DATABASE_URL=<Render staging DB URL>
BASE_URL=https://redbarsushi-staging.onrender.com
LOG_LEVEL=INFO
DELIVERECT_BASE_URL=https://api.staging.deliverect.com
```

### Production
```bash
FASTAPI_ENV=production
DATABASE_URL=<Render production DB URL>
BASE_URL=https://redbarsushi.onrender.com
LOG_LEVEL=WARNING
DELIVERECT_BASE_URL=https://api.deliverect.com
RATE_LIMIT_ENABLED=true
```

## Best Practices

1. **Development**:
   - Run unit tests frequently
   - Use Docker for consistency
   - Test with ngrok for webhooks

2. **Staging**:
   - Mirror production as closely as possible
   - Test with real phone calls
   - Validate Deliverect integration

3. **Production**:
   - Never test directly in production
   - Use feature flags for gradual rollouts
   - Monitor all deployments

## Troubleshooting

### Development Issues
- **Port conflicts**: Change `APP_PORT` in `.env`
- **Database errors**: Check Docker containers are running
- **Import errors**: Ensure `PYTHONPATH=/app`

### Staging Issues
- **Webhook failures**: Check BASE_URL is correct
- **API errors**: Verify API keys are set in Render
- **Database issues**: Check Render database status

### Production Issues
- **High error rate**: Roll back immediately
- **Performance degradation**: Check Render metrics
- **Integration failures**: Verify third-party service status