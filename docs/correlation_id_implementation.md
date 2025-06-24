# Correlation ID Logging Implementation

## Overview
This document describes the implementation of correlation ID logging for improved observability in the RedBarSushiAI system.

## Implementation Details

### 1. Core Components

#### Correlation ID Utilities (`app/utils/correlation_id.py`)
- Uses Python's `contextvars` for async-safe correlation ID storage
- Provides functions to generate, set, and retrieve correlation IDs
- Ensures correlation IDs are propagated through async contexts

#### Correlation ID Middleware (`app/middleware/correlation_id.py`)
- FastAPI middleware that ensures every HTTP request has a correlation ID
- Checks incoming headers for existing correlation IDs (X-Correlation-ID, X-Request-ID, X-Trace-ID)
- Generates new IDs if none provided
- Adds correlation ID to response headers

#### Enhanced Logging (`app/utils/enhanced_logging.py`)
- Custom logging filter that adds correlation IDs to all log records
- Structured JSON formatter for machine-readable logs
- Enhanced logger class that automatically includes correlation IDs and other context
- Configurable to use either JSON or human-readable format

#### HTTP Utilities (`app/utils/http_utils.py`)
- Provides correlated HTTP clients (sync and async) using httpx
- Automatically adds correlation ID headers to outgoing requests
- Ensures correlation IDs are propagated to external services

### 2. Integration Points

#### Main Application (`app/main.py`)
- Configures enhanced logging on startup
- Adds correlation ID middleware to FastAPI app
- Uses enhanced logger throughout

#### Voice Handlers
- **TwiML Handler** (`app/api/voice/twiml.py`): Sets correlation ID from Twilio call_sid
- **ConversationRelay Handler** (`app/api/conversation_relay/handler.py`): Propagates correlation ID through WebSocket sessions

#### Agent Orchestration (`app/utils/agent_orchestration_async.py`)
- Sets correlation ID when starting new conversations
- Logs with correlation ID context throughout orchestration

#### External Service Calls
- **DeliverectService** (`app/services/deliverect_service.py`): Uses CorrelatedAsyncClient for API calls
- **AI Mixin** (`app/agents/ai_mixin.py`): Uses enhanced logging for AI operations

### 3. Usage Patterns

#### Logging with Correlation ID
```python
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)

# Logs automatically include correlation ID
logger.info("Processing order", order_id=order_id)
```

#### Setting Correlation ID
```python
from app.utils.correlation_id import set_correlation_id

# Usually set from call_sid or session_id
set_correlation_id(call_sid)
```

#### Making HTTP Requests with Correlation ID
```python
from app.utils.http_utils import CorrelatedAsyncClient

async with CorrelatedAsyncClient() as client:
    # Correlation ID automatically added to headers
    response = await client.post(url, json=data)
```

### 4. Log Format

#### JSON Format (Production)
```json
{
  "timestamp": "2025-01-22T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.agents.menu_async",
  "message": "Processing menu query",
  "correlation_id": "CA123456789",
  "call_sid": "CA123456789",
  "order_id": "ORD-12345"
}
```

#### Human-Readable Format (Development)
```
[2025-01-22 10:30:45] [CA123456789] [INFO] [app.agents.menu_async] Processing menu query
```

### 5. Benefits

1. **Request Tracing**: Track requests across multiple services and async operations
2. **Debugging**: Easily filter logs for a specific call or session
3. **Performance Analysis**: Correlate logs to identify bottlenecks
4. **Error Investigation**: Track error propagation through the system
5. **External Service Integration**: Correlation IDs passed to Deliverect, OpenAI, etc.

### 6. Configuration

Environment variables:
- `LOG_LEVEL`: Set logging level (default: INFO)
- `USE_JSON_LOGS`: Use JSON format for logs (default: true)

### 7. Future Enhancements

1. Add correlation ID to database queries
2. Include correlation ID in error responses
3. Add distributed tracing support (OpenTelemetry)
4. Create log aggregation queries for correlation ID filtering
5. Add correlation ID to background tasks (Celery)