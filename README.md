# Restaurant Order Processing System

This repository implements a restaurant order processing system that integrates several technologies to handle customer calls, process orders, and interact with external APIs. It combines:

- **Flask** for handling HTTP requests, WebSockets, and Twilio voice calls.
- **WebSockets** for real-time speech and audio processing.
- **SQLAlchemy** for interacting with a MySQL database.
- **Twilio** for traditional voice and SMS messaging.
- **OpenAI** (GPT-4o) for natural language processing and real-time audio streaming.
- **Stripe** for creating payment links.
- **Deliverect** for external order management.
- **Celery** for background task processing.

Below is a detailed explanation of how the program works and how its components interact.

## Local Development and Deployment

We have several tools to help test and deploy the application:

### Docker Deployment

The application is designed to run in Docker containers with proper menu handling:

```bash
# Build the Docker image
docker build -t redbarsushiai .

# Run the container
docker run -p 8080:8080 -e DOCKER_CONTAINER=true redbarsushiai
```

The application is configured to automatically:
- Detect it's running in a Docker environment
- Store and load the menu from `/app/menu_data.json`
- Create a default menu if none exists

### Menu Location

The menu file is stored at the following locations based on environment:
- In Docker: `/app/menu_data.json` (highest priority)
- In development: At the root of the repository
- On PythonAnywhere/Render: Managed automatically with environment detection

### Test Deliverect Menu Processing

```bash
python test_deliverect_local.py [path/to/menu_data.json]
```

This tool processes a Deliverect menu JSON file locally and saves the processed results. It's useful for debugging menu processing issues without having to deploy changes.

### Test Menu Endpoint

```bash
python test_menu_endpoint.py [path/to/menu_data.json] [server_url]
```

Sends a test menu to the menu update endpoint (either local or remote) and displays the result. This is helpful for testing the menu update process without going through Deliverect.

### Sample Test Files

Sample test files are located in the `test_data/` directory:

- `deliverect_sample.json` - A valid Deliverect menu format
- `deliverect_problematic.json` - A problematic menu with type issues for testing error handling

---

## 1. Configuration & Setup

### a. Imports and Logging

- **Imports:**  
  The program imports standard libraries (JSON, logging, time, threading, etc.) along with third-party modules: Flask, Twilio, OpenAI, SQLAlchemy, Stripe, and Requests.

- **Logging:**  
  Logging is configured to write to a file named `progress.log` using a format that includes timestamps, log levels, and messages. The Twilio logger is set to the `WARNING` level to reduce verbose debug output.

### b. Flask App, Routes, and Database Setup

- **Flask App:**  
  A Flask application is created with a secret key loaded from your credentials.

- **Database:**  
  SQLAlchemy is configured to connect to a MySQL database hosted on PythonAnywhere. The engine is set up with connection pool options (`pool_recycle` and `pool_pre_ping`) to prevent stale connections.

- **Order Model:**  
  The `Order` model is defined with fields such as `id`, `sender`, `caller_name`, `message`, and a timestamp. This model is used to store order details in the database.

---

## 2. Menu Data Storage and Parsing

### a. File-based Menu Data Storage

- **Menu JSON File:**  
  The menu data is stored in a JSON file (located at `MENU_FILE_PATH`).  
- **Read/Write Functions:**  
  - `write_menu_file(all_items_data)`: Saves updated menu data to the file.  
  - `load_menu_data(force_refresh=False)`: Loads (and caches) menu data to minimize disk reads.

### b. Menu Item Matching for Voice Orders

The system uses several strategies to match spoken menu items to the actual menu:

- **Name Variants Dictionary:**  
  During menu processing, common variations are automatically generated (e.g., "hamburger" → "Burger").

- **Multi-Strategy Matching:**  
  When a customer orders an item, the system tries to find it using:
  1. Direct lookup in name variants dictionary
  2. Exact case-insensitive matching
  3. Normalized Levenshtein distance for fuzzy matching
  4. Substring matching
  5. Word-level matching
  
This ensures that even if a customer uses different wording than what's in the menu (saying "burger" instead of "hamburger" or "fries" instead of "french fries"), the system can still find the correct item.

### c. Parsing Functions

- **Availability and Snooze Checks:**  
  Functions like `parse_utc_timestamp()`, `is_item_snoozed_timebased()`, and `is_item_currently_available_by_schedule()` ensure that each menu item is available based on its schedule and whether it has been "snoozed."

- **process_deliverect_menu():**  
  This function processes menu data from Deliverect, preserving exact PLUs (reference handlers) and creating name variants for common voice orders. It handles:
  
  - Standard menu items with prices and availability
  - Modifier groups with min/max constraints
  - Name variants for improved voice recognition
  - Availability schedules

---

## 3. External API Integration

### a. Deliverect Token Handling

- **get_deliverect_token():**  
  Authenticates with Deliverect using client credentials to retrieve an access token.
  
- **ensure_deliverect_token() & get_deliverect_headers():**  
  These functions ensure the token is valid (refreshing it if necessary) and build the HTTP headers for subsequent Deliverect API calls.

### b. Stripe Integration

- **Stripe Setup:**  
  The Stripe API key is set from credentials.  
- **Payment Link Generation:**  
  When an order is confirmed, the system calls Stripe's API to create a price and a payment link. This link is then appended to the confirmation SMS message for customer payment.

### c. Twilio Integration

- **Twilio Client:**  
  The Twilio client is configured using your account SID and auth token.
  
- **Voice and SMS:**  
  The application uses Twilio's `VoiceResponse` to build XML responses for phone calls and uses the Twilio messaging API to send SMS (and optionally WhatsApp) messages.

---

## 4. Order Processing and Workflow

### a. Order Calculation and Confirmation

- **analyze_user_input():**  
  This function sends the customer's spoken order to OpenAI's GPT-4.1-mini to extract intent and order details in a structured format.
  
- **Fuzzy Matching:**  
  Functions like `find_menu_item()` and `find_menu_item_any_status()` use Levenshtein distance to match spoken orders with menu items.
  
- **Order Summary and Totals:**  
  - `build_order_description()`: Creates a human-readable summary of the order.  
  - `calculate_bill_amount()`: Computes the total cost based on items and modifiers.  
  - `enforce_modifier_group_constraints()`: Validates that the selected modifiers meet the defined minimum and maximum constraints.

### b. Order Confirmation

- **/confirm_order_from_initial Route:**  
  Once the order is confirmed:
  1. Modifier group constraints are validated.
  2. The order is saved to the database using a retry logic (`commit_with_retry()`).
  3. A Celery task (`send_confirmation_sms_task`) is enqueued to send a confirmation SMS (with a Stripe payment link).
  4. The order is forwarded to Deliverect.
  5. The customer receives voice feedback confirming the order.

### c. Order Modification

Routes like `/new_modify_order`, `/handle_newly_snoozed_in_checkout`, and `/confirm_fuzzy_items` allow customers to modify their orders if necessary. These routes handle re-parsing the order and re-calculating the totals.

---

## 5. Celery Tasks and Background Processing

### a. Celery Task Separation

The system offloads long-running operations to background tasks using Celery. Two main tasks are defined:

- **send_confirmation_sms_task:**  
  - **Purpose:**  
    Generates a Stripe payment link, sends a confirmation SMS (and optionally a WhatsApp message), and saves the order to the database.
  - **Workflow:**  
    This task runs in the background, ensuring that generating payment links and sending messages does not delay the customer's call.

- **send_order_status_update_task:**  
  - **Purpose:**  
    Retrieves an order from the database, sends an SMS with the updated order status, and makes an API call to Deliverect to report a failed order status if necessary.
  - **Workflow:**  
    This task is triggered by the `/order_status` webhook and processes status updates asynchronously.

### b. Enqueuing Tasks

- In your Flask routes (e.g., `/order_status` and `/confirm_order_from_initial`), you import and call these tasks using the `.delay()` method. This enqueues them to be processed by a separate Celery worker.

- **Celery Configuration:**  
  Your Celery instance (configured in `celery_app.py`) is set up to run tasks within the Flask application context, so that tasks have access to the database and other configurations.

---

## 6. Call Handling and User Interaction

### a. Incoming Call Flow

- **Root Route (/):**  
  When a call is received via Twilio, this route gathers the caller's name and sets up session variables.

- **/take_name and /main_menu Routes:**  
  These routes capture the caller's name and present options (e.g., to place an order, ask for the menu, or speak to a live person).

### b. Order Taking Flow

- **/take_order Route:**  
  Prompts the customer for their order. The spoken input is processed using OpenAI to extract order details, and fuzzy matching functions help map the order to menu items.
  
- **Confirmation and Modification:**  
  After summarizing the order, the customer is asked to confirm or modify. Depending on their response, the system either enqueues background tasks for confirmation or allows modifications.

---

## 7. Overall Workflow Summary

1. **Call Reception:**  
   A customer calls the restaurant. Twilio routes the call to the Flask app, which greets the customer and gathers their name.

2. **Order Input:**  
   The customer speaks their order. The spoken input is processed by OpenAI and fuzzy matching logic to convert it into a structured order.

3. **Order Confirmation:**  
   The customer confirms the order. The order is saved to the database (with retry logic for robust commits), and background tasks are enqueued:
   - A confirmation SMS with a Stripe payment link is sent.
   - The order details are sent to Deliverect.

4. **Background Processing:**  
   Celery workers, running separately, process tasks such as sending SMS messages and updating order statuses.

5. **User Feedback:**  
   Throughout the process, voice responses and SMS messages provide feedback to the customer, while logging ensures that each step is monitored for troubleshooting.

---

## 8. Audio Processing via WebSockets

The system implements audio processing with WebSocket transport:

### a. WebSocket Endpoints

- **/api/ws/speech-to-text:**  
  Receives audio and returns transcription results.
  
- **/api/ws/text-to-speech:**  
  Converts text to speech, streaming audio chunks back to the client.
  
- **/api/ws/conversation:**  
  Full-featured endpoint for the entire conversation flow with speech-to-text and text-to-speech.

### b. Key Features

- **Standard API with WebSocket Transport:** Uses OpenAI's standard API with WebSocket communication layer.
- **Streaming AI Responses:** Text responses streamed token-by-token for immediate feedback.
- **Voice Synthesis:** AI responses converted to speech using OpenAI's TTS.
- **Conversation Management:** Maintains conversation history for context-aware responses.
- **Headless Operation:** Works in headless environments without requiring X11 display server.
- **Robust Fallbacks:** Multiple processing options for maximum compatibility.

### c. Testing and Documentation

- **Interactive Demo:** Visit `/demo` endpoint to try the real-time audio interface.
- **Diagnostic Tool:** Run `python diagnose.py` to verify WebSocket functionality.
- **Integration Guide:** See [WEBSOCKET_IMPLEMENTATION.md](WEBSOCKET_IMPLEMENTATION.md) for complete setup and implementation details.

For information on the WebSocket protocol and API, see [REALTIME_AUDIO.md](REALTIME_AUDIO.md).

## 9. Final Thoughts

This program integrates multiple components into a cohesive order processing system:

- **Flask** handles HTTP requests, WebSockets, Twilio voice calls, and webhooks.
- **WebSockets** enable real-time audio streaming for a more interactive experience.
- **SQLAlchemy** manages persistent order storage.
- **Twilio** delivers traditional voice feedback and SMS notifications.
- **OpenAI** processes orders through both traditional APIs and real-time streaming.
- **Stripe** generates payment links for online payments.
- **Deliverect** interfaces with external order management systems.
- **Celery** offloads long-running tasks to background workers, ensuring responsiveness.

Each component is carefully integrated to create a robust, scalable system that manages orders from the moment a customer interacts until the order is confirmed and processed externally.

---

You can use this README as a comprehensive guide to how the system works. If you need to adjust or expand on any section, simply modify the Markdown file accordingly.