# RedBarSushiAI Project Context

This document provides essential context for the RedBarSushiAI project, explaining key architectural decisions, workflows, and components.

## Project Overview

RedBarSushiAI is an AI-powered voice ordering system for Red Bar Sushi that enables customers to place orders and get menu information over the phone. The system integrates with:

- **Twilio**: For phone/voice communication
- **OpenAI**: For natural language processing and voice recognition (using Assistants API)
- **Deliverect**: For order management and POS integration
- **PostgreSQL**: For data persistence
- **Redis**: For caching, session management, and as Celery broker
- **Celery**: For asynchronous task processing

## Core Architecture

### Database Architecture

The system uses PostgreSQL for data persistence with these key models that mirror the Deliverect data structure:

1. **Menu Models** (`app/models/menu.py`):
   - `MenuCategory`: `id`, `deliverect_category_id`, `name`, `description`
   - `MenuItem`: `id`, `category_id`, `name`, `description`, `price`, `plu` (critical link to POS), `deliverect_item_id`, `is_available`, `is_combo`, `is_variant`, `image_url`, `snoozed_until`
   - `MenuModifier`: `id`, `modifier_group_id`, `name`, `price_change`, `plu` (critical), `deliverect_modifier_id`, `is_available`, `snoozed_until`
   - `MenuModifierGroup`: `id`, `deliverect_group_id`, `name`, `min_selection`, `max_selection`, `multiMax`, `plu`, `is_variant_group`
   - `ItemModifierGroup`: Links `menu_items` to `modifier_groups`
   - `GroupModifier`: Links `modifier_groups` to `modifiers`
   - `MenuNameVariant`: `variant_phrase` (lowercase), `canonical_name`, `target_plu` - Essential for mapping natural language to specific PLUs

2. **Order Models** (`app/models/order.py`):
   - `Order`: `id`, `deliverect_channel_order_id` (critical link to Deliverect), `customer_phone`, `order_type`, `status`, `total_price`, `placed_at`, `estimated_time`, `delivery_address`
   - `OrderItem`: Links `orders` to `menu_items` via `menu_item_plu`, stores quantity
   - `OrderItemModifier`: Links `order_items` to `modifiers` via `modifier_plu`

3. **Location Model** (`app/models/location.py`):
   - `Location`: Stores location settings, Deliverect connection details, and business hours
   - Each location has its own `channelLinkId` for Deliverect integration

### Voice Handling

Voice interactions are managed through Twilio's programmable voice API:

1. **Call Flow** (`app/routes/voice.py`):
   - Takes customer name
   - Offers menu/order options
   - Handles silence with progressive fallbacks
   - Processes menu inquiries and orders

2. **Silence Handling**:
   - Progressive timeouts based on context
   - Fallback to DTMF (touch-tone) input
   - Session-based retry counters

### Menu Management

The menu system was migrated from file-based to database storage:

1. **Database Storage** (`app/utils/menu_db_store.py`):
   - PostgreSQL primary storage
   - Redis caching layer
   - Memory fallback if Redis unavailable

2. **Menu Matching** (`app/utils/menu_matcher_db.py`):
   - Multiple matching strategies:
     - Exact match (fastest)
     - Fuzzy matching (Levenshtein distance)
     - AI-powered matching (most accurate)

### Order Processing

Orders are processed through several components:

1. **Interactive Resolution** (`app/routes/order_ai.py`):
   - AI-powered order clarification
   - Step-by-step resolution of ambiguous orders
   - Session-based conversation tracking

2. **Order Validation**:
   - Checking item availability
   - Validating modifier constraints
   - Price calculation

## Key Workflows

### Voice Call Workflow

1. **Initial Greeting**: System answers call and asks for customer name
2. **Main Menu**: Customer chooses to order, ask about menu, or speak to staff
3. **Menu Inquiries**: System answers menu questions using AI
4. **Order Taking**: System takes order items, modifiers, and quantities
5. **Order Confirmation**: System summarizes order and confirms details
6. **Order Processing**: Order sent to Deliverect for restaurant fulfillment
7. **Order Status**: Customer receives updates on order progress

### Order Processing Workflow

1. **Conversation to Order**:
   - Customer speaks their order via Twilio
   - OpenAI Assistant processes the text and uses tools
   - `lookup_menu_item` tool converts natural language to specific PLUs
   - `add_item_to_cart` adds items with modifiers to the Redis cart

2. **Order Submission**:
   - OpenAI Assistant confirms the order with customer
   - `place_order` tool is called with customer details
   - System generates unique `channelOrderId`
   - System formats order payload using PLUs for Deliverect
   - System makes POST request to Deliverect API
   - Order record is created in PostgreSQL
   - Celery task is queued to send confirmation SMS

3. **Order Status Tracking**:
   - System periodically polls Deliverect API for order status
   - When status changes, system updates order record in PostgreSQL
   - System queues Celery task to send SMS update
   - Twilio delivers SMS notification to customer

### Menu Management Workflow

1. **Menu Data Import**:
   - Menu data is imported from JSON file (`menu_data.json`)
   - System loads detailed menu structure during initialization
   - Manual updates to menu data are processed through admin interface
   
2. **Menu Data Processing**:
   - System parses categories, items, modifiers, and modifier groups
   - Each entity is identified by PLU and stored in PostgreSQL
   - System builds `menu_name_variants` table mapping natural language to PLUs
   
3. **Menu Data Access**:
   - Menu data is cached in Redis for quick access
   - If Redis fails, system falls back to PostgreSQL
   - If PostgreSQL fails, system falls back to in-memory cache

### Database Migration

The system was migrated from file-based to database storage:

1. **Migration Process** (`database_menu_integration.py`):
   - Initialize database tables
   - Transfer data from JSON to database
   - Verify migration success
   - Update configuration

2. **Storage Layer** (`app/utils/menu_db_store.py`):
   - Redis caching for performance
   - Memory fallback for reliability
   - Database as source of truth

## Real-time Features

The system includes real-time processing features:

1. **Real-time Audio** (`app/utils/realtime_audio.py`):
   - WebSocket-based audio streaming
   - Real-time speech-to-text processing
   - Real-time text-to-speech responses

2. **WebSocket Endpoints**:
   - `/api/ws/speech-to-text`: Real-time transcription
   - `/api/ws/text-to-speech`: Real-time audio generation
   - `/api/ws/conversation`: Full conversation processing

## Conversation Context

The system maintains conversation context using Redis:

1. **Conversation Store** (`app/utils/conversation_store.py`):
   - Redis-backed conversation history
   - Memory fallback if Redis unavailable
   - Automatic session expiration

2. **Menu Questions**:
   - Maintains context between questions
   - Remembers previous inquiries
   - Provides contextual responses

## Testing Approach

The project uses a comprehensive testing strategy:

1. **Unit Tests** (`tests/unit/`):
   - Test individual components in isolation
   - Fast execution with mocked dependencies

2. **Integration Tests** (`tests/integration/`):
   - Test interactions between components
   - Database integration testing

3. **E2E Tests** (`tests/e2e/`):
   - Full workflow testing
   - Simulated voice calls
   - Complete order processing

## Deployment

The application is deployed on Render with these features:

1. **Environment Configuration**:
   - Production vs. Staging environments
   - Automatic database initialization
   - Redis connection handling

2. **CI/CD Pipeline**:
   - Tests run on PR and push
   - Deploys to staging from `staging` branch
   - Deploys to production from `main` branch

## Development Guidelines

### Code Organization

- **Models**: Database models in `app/models/`
- **Routes**: API endpoints in `app/routes/`
- **Utils**: Helper functions in `app/utils/`
- **Tests**: Comprehensive tests in `tests/`

### Style Conventions

- Follow PEP 8 for Python code
- Use Black for code formatting
- Use Ruff for linting
- Use pytest for testing

### Common Tasks

- **Run Tests**: `pytest`
- **Format Code**: `black app tests`
- **Lint Code**: `ruff check app tests`
- **Run Dev Server**: `FLASK_DEBUG=1 FLASK_APP=run.py flask run`
- **Run Celery**: `celery -A celery_app worker --loglevel=INFO`

## API Integrations

### Deliverect API Integration

The system integrates with Deliverect to manage menu data and process orders:

1. **Base URL**: `https://api.staging.deliverect.com`

2. **Key Identifiers**:
   - `channelName`: Scope identifier for API access
   - `channelLinkId`: Unique store instance identifier
   - `channelOrderId`: Application-generated unique order ID
   - `plu`: Product/modifier unique identifier (critical for order processing)

3. **Endpoints - Deliverect Integration**:
   - **Create Order**: `POST /{channelName}/order/{channelLinkId}` 
     - Places a new order with structured payload containing items identified by PLU
     - Order status is determined through manual polling rather than webhooks
     - Success response (201) only indicates the request was valid, not POS acceptance

4. **Menu Data Structure**:
   - Menu data is received as a hierarchical JSON structure with these key components:
     - **Categories**: Groups of menu items (e.g., "Steak & Burgers", "Sides")
       - Contains `_id`, `name`, `posCategoryId`, and array of `subProducts` (item IDs)
     - **Products**: Dictionary mapping product ID to details
       - Contains `_id`, `name`, `description`, `price` (in cents), `plu`, `productType`
       - May include `isVariant`, `isCombo` for special product types
       - Products reference `subProducts` array of attached Modifier Group IDs
     - **ModifierGroups**: Dictionary mapping group ID to details
       - Contains `_id`, `name`, `plu`, `min`, `max`, `multiMax` to control selection rules
       - References array of `subProducts` (modifier IDs)
       - May include `isVariantGroup` for product variants (e.g., sizes)
     - **Modifiers**: Dictionary mapping modifier ID to details
       - Contains `_id`, `name`, `price` (differential price), `plu`, `parentId`
   - **Variants System**: Supports different product versions (e.g., sizes)
     - Base product marked with `isVariant: true`
     - Variant group marked with `isVariantGroup: true`
     - Individual variants set price differentials (e.g., +$3 for large size)
   - **MenuNameVariants**: System builds table mapping natural language to PLUs
     - Maps common terms (e.g., "fries", "coke") to specific menu item PLUs
     - Essential for translating customer speech to specific order items

5. **Order Structure**:
   - Order payload to Deliverect must follow specific format:
     - `channelOrderId`: Unique ID generated by our system (cannot be reused within 48 hours)
     - `orderType`: Integer indicating pickup (1), delivery (2), eat-in (3), or curbside (4)
     - `customer`: Object with customer details (name, phoneNumber, email)
     - `deliveryAddress`: Required for delivery orders (street, postcode, city, etc.)
     - `orderIsAlreadyPaid`: Boolean indicating if payment was handled
     - `payment`: Object with amount (in cents), type (0=card, 1=cash, 2=voucher, 3=online)
     - `items`: Array of ordered items, each with:
       - `plu`: Exact PLU identifier from menu data
       - `name`: Item name
       - `price`: Price in cents
       - `quantity`: Quantity ordered
       - `subItems`: Array of modifiers attached to this item (each with plu, name, price, quantity)
   - Orders can include additional fields:
     - `pickupTime`/`deliveryTime`: Estimated times in ISO 8601 format
     - `note`: General order notes
     - `discountTotal`: Total discount in cents
     - `deliveryCost`: Delivery fee in cents
     - `serviceFee`: Service charge in cents
     - `driverTip`/`tip`: Tips in cents
     - `bagFee`: Bag fee in cents (mandatory in some regions)

6. **Order Types and Status**:
   - Order Types:
     - `1`: Pick up
     - `2`: Delivery
     - `3`: Eat-in
     - `4`: Curbside
   
   - Order Status Codes:
     - `20`: Accepted (order confirmed by restaurant)
     - `70`: Ready for Pickup
     - `80`: Delivered
     - `100`: Cancellation Request
     - `110`: Canceled (successfully canceled)
     
   - Payment Types:
     - `0`: Credit card online
     - `1`: Cash
     - `2`: Voucher
     - `3`: Online payment

### OpenAI Assistants API Integration

The system uses OpenAI's Assistants API for conversation management:

1. **Key Components**:
   - **Assistant**: Configured AI personality with specific capabilities
   - **Thread**: Represents a single conversation
   - **Message**: User input or AI response
   - **Run**: Execution of the Assistant on a Thread

2. **Tool Integration**:
   - When the Assistant needs external data or actions, it requests specific tools with parameters
   - Backend executes these tools as local Python functions
   - Results are submitted back to the Assistant

3. **Essential Tools**:
   - `lookup_menu_item(item_name)`: Translates user requests to specific menu items by PLU
   - `get_restaurant_info(query)`: Retrieves static restaurant information
   - `add_item_to_cart(plu, quantity, modifiers)`: Updates the current order
   - `get_current_cart()`: Retrieves the current order state
   - `place_order(customer_details, delivery_details, order_type)`: Submits order to Deliverect

### Twilio API Integration

The system uses Twilio for voice communication:

1. **Voice Handling**:
   - Receives calls via webhooks to `/webhook/voice`
   - Generates TwiML with `<Say>`, `<Gather>`, and other commands
   - Uses callbacks with transcription results

2. **SMS Notifications**:
   - Sends order status updates via Twilio's REST API
   - Managed through Celery tasks for asynchronous processing

## System Configuration and Startup

### Environment Variables

The system relies on environment variables for configuration. Key variables include:

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/redbarsushi
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/redbarsushi_test

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ASSISTANT_ID=asst_...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Deliverect
DELIVERECT_CHANNEL_NAME=redbarsushi
DELIVERECT_API_KEY=...
DELIVERECT_BASE_URL=https://api.staging.deliverect.com

# Application Settings
FLASK_APP=run.py
FLASK_ENV=development  # or production
LOG_LEVEL=INFO
```

### Starting the Application

The application can be started with the following commands:

1. **Start the Flask server**:
   ```
   python run.py
   ```
   or in debug mode:
   ```
   FLASK_DEBUG=1 FLASK_APP=run.py flask run
   ```

2. **Start the Celery worker**:
   ```
   celery -A celery_app worker --loglevel=INFO
   ```

3. **Optional - Start Celery beat for scheduled tasks**:
   ```
   celery -A celery_app beat --loglevel=INFO
   ```

### Database Initialization

On first run, the database needs to be initialized:

1. Create the database: `createdb redbarsushi`
2. Run migrations: `python -m flask db upgrade`
3. Initialize menu data: `python -m flask seed-menu`

## Detailed API Specifications

### Deliverect API Details

#### Creating an Order

The system creates orders by posting to the Deliverect API:

```
POST /{channelName}/order/{channelLinkId}
```

**Request Body Example**:
```json
{
    "channelOrderId": "RBS-12345-ABCDE",
    "channelOrderDisplayId": "RBS-12345",
    "orderType": 1,
    "pickupTime": "2025-05-03T12:30:00Z",
    "courier": "restaurant",
    "customer": {
        "name": "John Doe",
        "phoneNumber": "+15551234567",
        "email": "john.doe@example.com"
    },
    "orderIsAlreadyPaid": true,
    "payment": {
        "amount": 2550,
        "type": 0
    },
    "note": "No soy sauce please",
    "items": [
        {
            "plu": "CALI-ROLL",
            "name": "California Roll",
            "price": 1200,
            "quantity": 1,
            "subItems": [
                {
                    "plu": "EXTRA-AVO",
                    "name": "Extra Avocado",
                    "price": 150,
                    "quantity": 1
                }
            ]
        },
        {
            "plu": "SPICY-TUNA",
            "name": "Spicy Tuna Roll",
            "price": 1200,
            "quantity": 1
        }
    ],
    "decimalDigits": 2
}
```

**Response**:
- `201 Created`: Order received by Deliverect (valid format)
- `400 Bad Request`: Invalid request format or data
- `401 Unauthorized`: Invalid authentication
- `404 Not Found`: Endpoint not found
- `500 Internal Server Error`: Deliverect server error

#### Polling for Order Status

Since webhooks are not used, the system polls for order status using:

```
GET /{channelName}/order/{channelLinkId}/{channelOrderId}
```

**Response Example**:
```json
{
    "orderId": "61e9c9f98e5e2b001c82eabc",
    "status": 20,
    "channelOrderId": "RBS-12345-ABCDE",
    "location": "61e9c9f98e5e2b001c82eabd",
    "channelLink": "61e9c9f98e5e2b001c82eabe"
}
```

**Status Codes**:
- `10`: Received (initial state)
- `20`: Accepted (confirmed by restaurant)
- `30`: In Preparation
- `40`: Prepared (ready for pickup/delivery)
- `70`: Ready for Pickup
- `80`: Delivered/Completed
- `90`: Rejected (order refused)
- `100`: Cancellation Request
- `110`: Canceled

### OpenAI Assistants API Integration

#### Creating a Thread

```python
thread = client.beta.threads.create()
```

#### Adding a Message to a Thread

```python
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="I want to order a California roll with extra avocado"
)
```

#### Running the Assistant

```python
run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant_id
)
```

#### Handling Tool Calls

```python
# Check if the run requires action
if run.status == "requires_action":
    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "lookup_menu_item":
            args = json.loads(tool_call.function.arguments)
            result = lookup_menu_item(args["item_name"])
            
            # Submit the tool output back to the Assistant
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=[
                    {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                    }
                ]
            )
```

### Twilio API Integration

#### Receiving Calls

Twilio sends incoming call notifications to the `/webhook/voice` endpoint, which responds with TwiML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">Welcome to Red Bar Sushi! How can I help you today?</Say>
    <Gather input="speech" action="/webhook/voice/input" method="POST" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Amy-Neural">You can ask about our menu or place an order.</Say>
    </Gather>
</Response>
```

#### Sending SMS Notifications

```python
def send_sms_notification(to_number, message):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return message.sid
```

## Database Schema Details

### Menu Tables

#### menu_categories
```sql
CREATE TABLE menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_items
```sql
CREATE TABLE menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_modifier_groups
```sql
CREATE TABLE menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_modifiers
```sql
CREATE TABLE menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL,
    deliverect_modifier_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### item_modifier_groups
```sql
CREATE TABLE item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### menu_name_variants
```sql
CREATE TABLE menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);
```

### Order Tables

#### orders
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    deliverect_channel_order_id VARCHAR(255) UNIQUE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    order_type INTEGER NOT NULL,
    status INTEGER DEFAULT 10,
    total_price INTEGER NOT NULL,
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estimated_time TIMESTAMP WITH TIME ZONE,
    delivery_address TEXT,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### order_items
```sql
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    menu_item_plu VARCHAR(255) REFERENCES menu_items(plu),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### order_item_modifiers
```sql
CREATE TABLE order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255) REFERENCES menu_modifiers(plu),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Redis Data Structures

### Conversation Store

Conversations are stored in Redis using a hash with the Twilio `CallSid` as the key:

```
HSET conversation:{CallSid} 
    state "greeting" 
    customer_name "John" 
    last_utterance "I want to order sushi" 
    silence_count 0
    cart_json "{...}"
    last_activity_timestamp 1714521145
```

A TTL of 2 hours is set to automatically expire conversations:

```
EXPIRE conversation:{CallSid} 7200
```

### Cart Structure

Cart data stored in Redis:

```
HSET cart:{CallSid} 
    json "{
        'items': [
            {
                'plu': 'CALI-ROLL',
                'name': 'California Roll', 
                'price': 1200,
                'quantity': 1,
                'modifiers': [
                    {
                        'plu': 'EXTRA-AVO',
                        'name': 'Extra Avocado',
                        'price_change': 150,
                        'quantity': 1
                    }
                ]
            }
        ],
        'total_price': 1350,
        'order_type': 1
    }"
```

### Menu Cache

Menu cache with 1-day expiration:

```
HSET menu:items:{plu} name "California Roll" price 1200 description "..."
EXPIRE menu:items:{plu} 86400
```

## Error Handling Strategies

### Database Connection Issues

The system implements database retry logic with exponential backoff:

```python
@retry(
    retry=retry_if_exception_type(OperationalError),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def get_menu_items_with_retry():
    with Session() as session:
        return session.query(MenuItem).all()
```

### Twilio Call Failures

If a call encounters errors, the system will:

1. Log the error with call metadata
2. Attempt to gracefully disconnect with an apology message
3. Send an SMS notification if the error occurs after customer details are collected

### Speech Recognition Fallbacks

The system implements progressive fallbacks for speech recognition:

1. First attempt: Standard speech recognition
2. Second attempt: Enhanced speech recognition with longer timeout
3. Third attempt: Fallback to DTMF touch-tone input

## Celery Tasks

The system uses Celery for asynchronous processing:

```python
@celery_app.task
def send_order_confirmation(order_id, customer_phone):
    """Send SMS confirmation after order is placed"""
    try:
        # Get order details from database
        order = get_order_by_id(order_id)
        
        # Format message
        message = f"Thank you for ordering from Red Bar Sushi! Your order #{order.id} "
        message += f"has been received and will be ready around {order.estimated_time.strftime('%I:%M %p')}. "
        message += f"Total: ${order.total_price/100:.2f}"
        
        # Send SMS via Twilio
        send_sms_notification(customer_phone, message)
        
        # Update order record to indicate confirmation sent
        update_order_confirmation_sent(order_id)
        
    except Exception as e:
        logger.error(f"Failed to send order confirmation: {str(e)}")
        # Retry up to 3 times with exponential backoff
        self.retry(exc=e, countdown=2 ** self.request.retries * 60, max_retries=3)
```

```python
@celery_app.task
def poll_order_status(order_id, channel_order_id):
    """Poll Deliverect for order status updates"""
    try:
        # Check current status in our database
        current_status = get_order_status(order_id)
        
        # Skip polling if order is in a terminal state
        terminal_states = [80, 90, 110]  # Delivered, Rejected, Canceled
        if current_status in terminal_states:
            return
        
        # Poll Deliverect for status
        deliverect_status = get_deliverect_order_status(channel_order_id)
        
        # If status changed, update in our database
        if deliverect_status != current_status:
            update_order_status(order_id, deliverect_status)
            
            # If status warrants customer notification, send SMS
            if deliverect_status in [20, 70, 80, 110]:  # Accepted, Ready, Delivered, Canceled
                send_status_update_notification.delay(order_id)
                
        # Schedule next polling based on current status
        # Poll more frequently for active orders, less for orders near completion
        if deliverect_status < 40:  # Before preparation is completed
            poll_order_status.apply_async(args=[order_id, channel_order_id], countdown=60)  # Check again in 1 minute
        else:
            poll_order_status.apply_async(args=[order_id, channel_order_id], countdown=180)  # Check again in 3 minutes
            
    except Exception as e:
        logger.error(f"Failed to poll order status: {str(e)}")
        self.retry(exc=e, countdown=30, max_retries=5)
```

## Menu Matching Algorithm

The system uses a three-tier approach for menu matching:

### 1. Exact Match

```python
def find_exact_match(item_name):
    """Find exact match in menu_name_variants table"""
    normalized_name = item_name.lower().strip()
    
    # Query database for exact match
    variant = MenuNameVariant.query.filter_by(variant_phrase=normalized_name).first()
    if variant:
        return MenuItem.query.filter_by(plu=variant.target_plu).first()
    
    return None
```

### 2. Fuzzy Matching

```python
def find_fuzzy_match(item_name, threshold=80):
    """Find fuzzy match using Levenshtein distance"""
    normalized_name = item_name.lower().strip()
    
    # Get all menu name variants
    variants = MenuNameVariant.query.all()
    
    # Calculate similarity scores
    matches = []
    for variant in variants:
        ratio = fuzz.ratio(normalized_name, variant.variant_phrase)
        if ratio >= threshold:
            matches.append((variant, ratio))
    
    # Sort by similarity score
    matches.sort(key=lambda x: x[1], reverse=True)
    
    # Return best match if any
    if matches:
        best_match = matches[0][0]
        return MenuItem.query.filter_by(plu=best_match.target_plu).first()
    
    return None
```

### 3. AI-Powered Matching

```python
def find_ai_match(item_name, context=None):
    """Use OpenAI to match menu item based on contextual understanding"""
    # Create prompt for OpenAI
    prompt = f"The customer ordered: '{item_name}'\n\n"
    prompt += "Based on our menu items below, what is the most likely menu item they want?\n\n"
    
    # Add menu items for context
    menu_items = MenuItem.query.all()
    for item in menu_items:
        prompt += f"- {item.name}: {item.description}\n"
    
    # Add customer context if available
    if context:
        prompt += f"\nAdditional context: {context}\n"
    
    prompt += "\nReturn only the exact name of the menu item from the list above."
    
    # Query OpenAI
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=50,
        temperature=0.3
    )
    
    # Extract item name from response
    ai_item_name = response.choices[0].text.strip()
    
    # Find item in database
    return MenuItem.query.filter(
        func.lower(MenuItem.name) == func.lower(ai_item_name)
    ).first()
```

## MCP Integration for Testing

The project includes a Model Context Protocol (MCP) integration that enables:

1. Running E2E tests directly on the staging environment
2. Testing system functionality through Claude Code
3. Verifying code functionality in the staging environment

### MCP Components

1. **Simple Fixed MCP Server (`fixed_simple_mcp.py`)**: 
   - Implements JSON-RPC 2.0 protocol with the correct protocol version (2024-11-05)
   - Provides tools for Claude to interact with the project:
     - `run_test`: Run end-to-end tests against the staging environment
     - `echo`: Simple echo tool for testing connectivity
   - Most reliable MCP server implementation

2. **Test Runner Script (`test_staging_e2e.sh`)**:
   - Runs different types of tests against the staging environment
   - Supports test types: basic, voice, menu, order, all
   - Sets proper environment variables for testing
   - Provides colored output for test results

3. **Run Script (`run_fixed_simple_mcp.sh`)**:
   - Registers and starts the MCP server
   - Kills any competing server instances
   - Sets execute permissions
   - Provides usage instructions

4. **Staging Environment**:
   - Base URL: `https://redbarsushiai-staging.onrender.com`
   - E2E tests are configured to run against this environment
   - Tests automatically use this URL as the default BASE_URL

### MCP Protocol Requirements

The MCP server adheres to specific protocol requirements to work with Claude Code:

1. **Protocol Version**: Uses `"2024-11-05"` (required for compatibility)
2. **Tool Schema Format**: Uses `"inputSchema"` instead of `"schema"`
3. **JSON-RPC 2.0**: Implements the JSON-RPC 2.0 specification
4. **Response Format**: Tools return results with a "content" array containing "type" and "text" fields

Example initialize response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "StagingTestMCP",
      "version": "1.0.0"
    }
  }
}
```

Example tools/list response:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "run_test",
        "description": "Run tests on the staging environment",
        "inputSchema": {
          "type": "object",
          "properties": {
            "test_type": {
              "type": "string",
              "description": "Type of test to run (basic, voice, menu, order, all)"
            }
          },
          "required": ["test_type"]
        }
      },
      {
        "name": "echo",
        "description": "Echo a message back",
        "inputSchema": {
          "type": "object",
          "properties": {
            "message": {
              "type": "string",
              "description": "Message to echo back"
            }
          },
          "required": ["message"]
        }
      }
    ]
  }
}
```

Example tool result response format (critical for proper Claude Code integration):
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{
      "type": "text",
      "text": "This is the tool's output text"
    }]
  }
}
```

### Setting Up MCP

#### Using the Run Script (Recommended)

The easiest way to set up the MCP server is to use the provided script:

```bash
./run_fixed_simple_mcp.sh
```

This script will:
- Kill any existing MCP server instances
- Set all necessary execute permissions
- Register the MCP server with Claude as "staging-test"
- Start the MCP server in the background

You can verify the MCP server is running with:
```bash
claude /mcp
```

You should see `staging-test: connected` in the output.

#### Testing the MCP Connection

Once the MCP server is running, you can test it with:

1. **Basic Echo Test**:
   ```
   /mcp echo message="Hello from MCP"
   ```
   This should return the exact message back to you.

2. **Run Basic Tests**:
   ```
   /mcp run_test test_type="basic"
   ```
   This will run basic connectivity tests against the staging environment.

3. **Run Specific Test Types**:
   ```
   /mcp run_test test_type="voice"
   /mcp run_test test_type="menu"
   /mcp run_test test_type="order"
   /mcp run_test test_type="all"
   ```

#### Troubleshooting MCP

Common issues and solutions:

1. **Protocol Version Error**: 
   - Error: `Server's protocol version is not supported`
   - Solution: Check that `fixed_simple_mcp.py` includes `"protocolVersion": "2024-11-05"`

2. **Schema Validation Error**:
   - Error: `Failed to fetch tools: invalid_type, expected "object", received "undefined", path ["tools", 0, "inputSchema"]`
   - Solution: Ensure tools use `inputSchema` instead of `schema`

3. **Tool Result Format Error**:
   - Error: Claude Code displays "Error handling tool result" or similar
   - Solution: Ensure tool results include a "content" array with "type" and "text" fields

4. **Connection Failed**:
   - Error: MCP server shows as `failed` in the `/mcp` output
   - Solution: 
     - Check that the MCP server is running with `ps aux | grep fixed_simple_mcp`
     - Check the log file at `fixed_simple_mcp.log`
     - Restart the server with `./run_fixed_simple_mcp.sh`

5. **Multiple Servers Running**:
   - Error: Competing servers causing connection issues
   - Solution: Kill all MCP servers with `pkill -f "python.*mcp.*py"` and start only the one you need

### MCP Server Implementation Details

The MCP server implementation follows these key principles:

1. **JSON-RPC 2.0 Protocol**: 
   - All requests and responses follow the JSON-RPC 2.0 specification
   - Each request has a unique ID that is included in the response
   - Errors are properly formatted with code and message

2. **Tool Response Format**:
   - All tool responses include a "content" array with text data
   - This format is required for Claude Code to properly display results

3. **Error Handling**:
   - Comprehensive error handling with appropriate error codes
   - All errors are logged to the log file for debugging
   - User-friendly error messages are returned when possible

4. **Logging**:
   - All requests, responses, and errors are logged to `fixed_simple_mcp.log`
   - Log includes timestamps for easier debugging
   - Log is cleared on server restart

5. **Process Isolation**:
   - MCP server runs as a separate process
   - Communication happens via stdin/stdout
   - Server can be stopped and started independently of Claude

## Important Notes

- The system has been migrated from file-based to database storage
- Redis is used for caching and conversation store
- OpenAI Assistants API is used for NLP and voice processing
- Twilio is used for phone communication and SMS notifications
- Deliverect is used for order management and POS integration
- PLU identifiers are critical for mapping between system and Deliverect
- The system maintains parallel data structures in PostgreSQL that mirror Deliverect's menu format
- Order status polling is used instead of webhooks for integration with Deliverect