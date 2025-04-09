# RedBarSushiAI - Comprehensive Documentation

## Project Overview
RedBarSushiAI is a sophisticated AI-powered ordering system for Red Bar Sushi restaurant. It handles voice ordering via phone calls, SMS interactions, and integrates with the Deliverect point-of-sale system to manage the full order lifecycle including delivery tracking and status updates.

## System Architecture

### Core Components
1. **Flask Web Application** - Main backend server
2. **Celery Task Queue** - Background task processing
3. **Twilio Integration** - Voice and SMS communication
4. **OpenAI Integration** - Natural language processing and voice transcription
5. **Deliverect Integration** - POS system and order delivery management
6. **WebSocket Support** - Real-time audio processing
7. **SQLAlchemy** - Database ORM layer

### Key Features
- **Voice Ordering** - AI-powered natural language understanding for phone orders
- **Real-time Audio Processing** - Web-based voice interaction
- **Menu Management** - Dynamic menu with categories, items, and modifiers
- **Order Tracking** - Comprehensive status updates through the order lifecycle
- **Delivery Management** - Courier tracking, ETA updates, and delivery status
- **SMS Notifications** - Rich, contextual order updates to customers
- **Fallback Systems** - Graceful degradation when services are unavailable

## Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL
- Redis (for Celery)
- Twilio Account
- OpenAI API Key
- Deliverect Integration Credentials

### Environment Variables
The application uses the following environment variables:
```
OPENAI_API_KEY - OpenAI API authentication
TWILIO_ACCOUNT_SID - Twilio account identifier
TWILIO_AUTH_TOKEN - Twilio authentication
TWILIO_NUMBER - Outgoing SMS phone number
DELIVERECT_API_URL - Deliverect API endpoint
DELIVERECT_API_KEY - Deliverect authentication
STRIPE_PRODUCT_ID - Used for payment links
DATABASE_URL - Database connection string
REDIS_URL - Redis connection for Celery
USE_VIRTUAL_DISPLAY - Enable virtual X11 display (headless environments)
BASE_URL - Base URL for webhook callbacks
```

### Docker Deployment
The application can be deployed using Docker and Docker Compose:
```bash
# Build the image
docker-compose build

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f
```

### Render.com Deployment
Custom entrypoints are provided for Render.com deployment:
- `render_entrypoint.sh` - Main web service
- `docker-entrypoint.sh` - Worker service

## Core Services

### Voice Processing
Voice processing relies on Twilio for phone calls and OpenAI for transcription and understanding. The system follows this flow:
1. **Call Reception** - Initial greeting and name capture
2. **Menu Options** - Main menu offerings (order, inquiries, speak to a person)
3. **Order Taking** - AI-powered order extraction
4. **Confirmation** - Order verification and POS submission
5. **Notification** - SMS confirmation to customer

### SMS System
SMS processing enables:
1. **Status Inquiries** - Text "status" to check order status
2. **Menu Requests** - Text "menu" to get menu information
3. **Help Commands** - Text "help" for assistance options
4. **Location Info** - Text "location" for restaurant address
5. **Hours of Operation** - Text "hours" for business hours
6. **Specials** - Text "specials" for daily promotions

### Order Processing
1. **Order Submission** - Orders can be placed via voice or SMS
2. **Validation** - Items are verified against the current menu
3. **POS Integration** - Valid orders are sent to Deliverect
4. **Status Tracking** - Order progress is tracked through various stages
5. **Notification** - Customers receive SMS updates at key status points

## Code Structure

### Main Application Files
- `run.py` - Application entry point
- `wsgi.py` - WSGI server entry point
- `app/__init__.py` - App initialization
- `app/models.py` - Database models
- `celery_app.py` - Celery configuration
- `tasks.py` - Background task definitions

### Routes
- `app/routes/voice.py` - Voice call handling
- `app/routes/order.py` - Order processing
- `app/routes/menu.py` - Menu management
- `app/routes/location.py` - Location management

### Utils
- `app/utils/agent_utils.py` - OpenAI agent integration
- `app/utils/order_utils.py` - Order processing helpers
- `app/utils/menu_utils.py` - Menu management helpers
- `app/utils/realtime_audio.py` - WebSocket audio processing
- `app/utils/deliverect.py` - Deliverect API integration

## API Documentation

### Voice Endpoints
- `POST /` - Initial call handler
- `POST /take_name` - Caller name capture
- `POST /main_menu` - Main menu handler
- `POST /take_order` - Order handler
- `POST /handle_menu_questions` - Menu inquiry handler

### Order Endpoints
- `POST /order_status` - Deliverect order status webhook
- `POST /courierUpdate` - Deliverect courier update webhook
- `POST /register` - Deliverect channel registration
- `POST /sms` - SMS message handler

### WebSocket Endpoints
- `WS /api/ws/speech-to-text` - Real-time speech recognition
- `WS /api/ws/text-to-speech` - Real-time speech synthesis 
- `WS /api/ws/conversation` - Full-duplex conversation

## Database Schema

### Order Model
The `Order` model tracks the full lifecycle of an order:

```python
class Order(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    sender = db.Column(db.String(15), nullable=False)
    caller_name = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='NEW')
    status_code = db.Column(db.Integer, nullable=True)
    status_updated_at = db.Column(db.DateTime, nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    location_id = db.Column(db.String(36), nullable=True)
    sms_sid = db.Column(db.String(50), nullable=True)
    sms_status = db.Column(db.String(20), nullable=True)
    sms_error_code = db.Column(db.Integer, nullable=True)
    sms_error_message = db.Column(db.String(255), nullable=True)
    delivery_status = db.Column(db.String(30), nullable=True)
    delivery_status_code = db.Column(db.Integer, nullable=True)
    courier_name = db.Column(db.String(50), nullable=True)
    courier_phone = db.Column(db.String(20), nullable=True)
    estimated_delivery_time = db.Column(db.DateTime, nullable=True)
```

### Location Model
The `Location` model tracks restaurant locations:

```python
class Location(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='inactive')
    webhook_base = db.Column(db.String(255), nullable=True)
    api_key = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
```

## Status Code Reference

### POS Status Codes
- **10**: New - Received by restaurant
- **20**: Accepted - Order confirmed
- **40**: Printed - Ticket sent to kitchen
- **50**: Preparing - In preparation
- **60**: Prepared - Cooking completed
- **70**: Pickup Ready - Ready for collection
- **90**: Finalized - Order completed
- **95**: Auto-Finalized - Order handled
- **110**: Canceled - Order canceled
- **120**: Failed - Order failed

### Delivery Status Codes
- **76**: Delivery Created - Looking for courier
- **81**: Delivery Confirmed - Courier assigned
- **83**: En Route to Pickup - Courier approaching restaurant
- **85**: Arrived at Pickup - Courier at restaurant
- **87**: En Route To Dropoff - Courier heading to customer
- **89**: Arrived At Drop Off - Courier at customer location
- **115**: Delivery Canceled - Delivery was canceled

### System Status Codes
- **1**: Parsed - Order received by system
- **2**: Received by POS - Order sent to restaurant
- **25**: Scheduled - Order awaiting scheduled time

## Real-time Audio Integration

The system integrates with the OpenAI Realtime client for advanced audio processing. This integration supports:

1. **Speech-to-Text** - Real-time voice transcription
2. **Text-to-Speech** - Voice synthesis for AI responses
3. **Continuous Conversation** - Maintaining conversation context

The system handles environments with and without X11:
- Using Xvfb for virtual display in headless environments
- Providing a custom websockets-based implementation as fallback

## Deliverect Integration

The Deliverect integration manages the full restaurant order lifecycle:

1. **Order Submission** - Sending orders to the POS
2. **Status Updates** - Tracking order status in the kitchen
3. **Delivery Management** - Courier assignment and tracking
4. **Channel Registration** - Restaurant location registration

## AI Agent System

The AI system utilizes OpenAI's tools:

1. **Order Parsing** - Extracting items and quantities from natural language
2. **Order Modification** - Understanding requested changes to orders
3. **Menu Navigation** - Answering questions about the menu
4. **Name Extraction** - Identifying customer names from speech

## Testing & Development

### Running Tests
```bash
python -m pytest tests/
python -m pytest tests/integration/
python -m pytest tests/test_specific_file.py::test_specific_function
```

### Development Server
```bash
FLASK_DEBUG=1 FLASK_APP=run.py flask run
```

### Celery Worker
```bash
celery -A celery_app worker --loglogs=INFO
```

## Code Style Guidelines

### Imports
Group imports in the following order:
1. Standard library imports
2. Third-party imports
3. Local application imports

Within each group, imports should be alphabetized.

### Naming Conventions
- `snake_case` for variables, functions, and modules
- `CamelCase` for classes
- `ALL_CAPS` for constants

### Formatting
- 4-space indentation
- 100 character line limit
- Docstrings with """triple quotes"""

### Type Hints
Use when appropriate for function parameters and returns:
```python
def calculate_total(items: List[Dict[str, Any]]) -> float:
    """Calculate the total price of all items."""
    return sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
```

### Error Handling
Use try/except blocks with specific exceptions:
```python
try:
    # Code that might raise an exception
    result = process_data(data)
except ValueError as e:
    # Handle specific exception
    logger.error(f"Invalid data: {e}")
except Exception as e:
    # Last resort catch-all
    logger.error(f"Unexpected error: {e}")
```

### Logging
Use structlog with context:
```python
logger.info("Processing order", order_id=order.id, status=order.status)
```

Use appropriate log levels:
- DEBUG - Detailed debugging information
- INFO - Confirmation that things are working as expected
- WARNING - Something unexpected happened, but the process continues
- ERROR - More serious problem, process might not complete task
- CRITICAL - Very serious error, program might not be able to continue

### Comments
- Add comments for complex logic, not for obvious code
- Use inline comments sparingly
- Comment functions and classes with descriptive docstrings

### Code Organization
- Group related functionality
- Use helper functions for reusable logic
- Keep functions focused on a single task

## Troubleshooting

### Common Issues

#### OpenAI Realtime Client Errors
If encountering X11 errors with the OpenAI Realtime client:
1. Set `USE_VIRTUAL_DISPLAY=1` in the environment
2. The system will use Xvfb as a virtual display
3. If issues persist, the system will use the fallback websockets implementation

#### SMS Delivery Failures
If SMS messages fail to deliver:
1. Check the Twilio console for error details
2. Verify phone number formatting (should be E.164 format)
3. Inspect order.sms_error_code and order.sms_error_message in the database

#### Deliverect Integration Issues
1. Verify API credentials are correct
2. Check webhook URLs are accessible from the internet
3. Ensure all required endpoints are implemented

#### Database Connection Issues
1. Verify DATABASE_URL environment variable
2. Check database server is running
3. Ensure network connectivity between app and database

## Future Enhancements

1. **Payment Processing** - Expanded payment options and integration
2. **Voice Authentication** - Customer recognition by voice
3. **Order History** - Personalized recommendations based on past orders
4. **Advanced Analytics** - Order patterns and inventory optimization
5. **Multi-language Support** - Support for additional languages
6. **Advanced Status Predictions** - ML models for more accurate delivery time estimates

## Security Considerations

1. **API Keys** - Store securely, never in code
2. **PII Protection** - Minimize and encrypt personal information
3. **Input Validation** - Verify all inputs to prevent injection attacks
4. **Rate Limiting** - Prevent abuse of SMS and voice systems
5. **Access Control** - Restrict admin functions to authorized users
6. **Audit Logging** - Track all order modifications