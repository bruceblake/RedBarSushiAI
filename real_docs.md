# Project Documentation: AI Restaurant Phone Agent

**Version:** 1.1
**Date:** 2025-04-17
**Primary Audience:** AI Development Assistants (e.g., Gemini, Claude, GPT-4) for code generation, feature implementation, updates, and debugging.
**Goal:** To provide a comprehensive, precise, and structured overview of the AI Restaurant Phone Agent system, enabling AI assistants to understand its components, interactions, APIs, and data models for effective codebase manipulation.

---

## 1. Project Overview

**Name:** AI Restaurant Phone Agent (Internal Codename: TBD)

**Purpose:** To handle inbound phone calls for restaurants, provide information about the restaurant and its menu, assist customers with placing orders conversationally, inject finalized orders into the restaurant's POS via Deliverect, and provide subsequent order status updates via SMS.

**Core Technologies:**

- **AI Conversation:** OpenAI Agents API
- **Telephony & SMS:** Twilio API
- **Order Injection:** Deliverect API
- **Backend:** Python (Framework: TBD - e.g., Flask, FastAPI) hosted on Render
- **Task Queue:** Celery
- **Database:** PostgreSQL on Render
- **Cache/State/Broker:** Redis on Render

**High-Level Goal:** Automate the phone ordering process, reduce staff workload, improve order accuracy, and enhance customer experience through conversational interaction and proactive status updates.

---

## 2. Core Features

- **Inbound Call Handling:** Answer incoming calls via a dedicated Twilio phone number.
- **Conversational AI:** Engage callers in natural language using OpenAI Agents API.
- **Restaurant Information:** Provide details like hours, address, and general info (sourced from Postgres).
- **Menu Interaction:** Discuss menu items, prices, descriptions, options, and availability (sourced from Postgres). Answer questions about the menu.
- **Order Taking:** Guide users through building an order (items, quantities, modifications, special requests). Maintain order state during the conversation (using Redis).
- **Order Placement:** Validate the completed order and submit it to the restaurant's POS system via the Deliverect API.
- **Order Confirmation:** Confirm order placement with the user verbally and potentially via SMS.
- **Status Updates:** Receive order status updates from Deliverect (via webhook) or poll Deliverect, update the order status in Postgres, and send SMS notifications to the customer via Twilio.
- **Store Status Awareness:** Handle store closures/busy modes communicated via Deliverect webhooks.
- **Menu Synchronization:** Receive menu updates from Deliverect (via webhook) and update the internal Postgres menu database.
- **Product Availability:** Handle item snoozing/unsnoozing based on Deliverect webhooks.

---

## 3. System Architecture

The system follows an **API-Driven Agent Architecture with Background Processing**.

1.  **Twilio (Voice Gateway & Comms):** Handles PSTN interaction. Receives calls, streams audio, performs STT/TTS based on TwiML instructions from the backend, and sends/receives SMS. Interacts with the Render Web Service via webhooks.
2.  **Render Web Service (Python Backend):** The central orchestrator.
    - Hosts API endpoints for Twilio webhooks (voice, status callbacks) and Deliverect webhooks (registration, status updates, menu updates, etc.).
    - Manages conversation state using Redis (keyed by Twilio `CallSid`).
    - Interacts with the OpenAI Agents API, providing context and user input, and crucially, implementing the **Tools (Functions)** the Agent can call.
    - Generates TwiML responses for Twilio.
    - Queries Postgres for menu data, restaurant info, and order history.
    - Writes order details and status updates to Postgres.
    - Calls the Deliverect API for order placement and potentially status polling.
    - Enqueues asynchronous tasks (e.g., SMS notifications, polling) to Celery.
3.  **OpenAI Agents API (AI Core):** Performs NLU, dialogue management, and decision-making. Uses the "Tools" provided by the Render Web Service to interact with the outside world (look up menu items, add to cart, place order).
4.  **PostgreSQL (Database):** Persistent storage for menu details (including PLUs), restaurant info, order history, and statuses.
5.  **Redis (Cache/State/Broker):** Stores active conversation state, temporary order data during calls, and serves as the Celery message broker and potentially backend.
6.  **Celery Workers (Render Background Worker):** Execute asynchronous tasks dequeued from Redis (e.g., sending SMS via Twilio, polling Deliverect API).
7.  **Deliverect API (Order/Menu Management):** External service for injecting orders into the POS and managing menu/store status synchronization. Interacts via direct API calls from the Render service and webhooks _to_ the Render service.

**Diagrammatic Flow (Conceptual):**
[Customer Phone] <--> [Twilio API (Voice/SMS)] <--> [Render Web Service (Python)]
^ | ^ | ^
| v | v |
[OpenAI Agents API] <-+ | +-> [Postgres DB]
| v |
+-> [Redis] <--> [Celery Worker]
| ^
v | (Polling)
[Deliverect API] <-----+--------------+
^ | (Webhooks)
+---+

---

## 4. Technology Stack

- **Cloud Platform:** Render.io
  - Web Service (Python Application)
  - Background Worker (Celery)
  - PostgreSQL Instance
  - Redis Instance
- **Programming Language:** Python (Version: TBD, e.g., 3.10+)
- **Web Framework:** TBD (e.g., Flask, FastAPI, Django)
- **Task Queue:** Celery (with Redis as broker/backend)
- **Database ORM:** TBD (e.g., SQLAlchemy, Django ORM)
- **External APIs:**
  - Twilio API (Programmable Voice, Programmable Messaging)
  - OpenAI Agents API
  - Deliverect API

---

## 5. Data Storage

**5.1. PostgreSQL Database Schema (Conceptual)**

- `restaurants`: Basic info (id, name, address, phone, hours_description)
- `menu_categories`: (id, name, description)
- `menu_items`: (id, category_id, name, description, price, **plu** (Deliverect Product ID - CRITICAL, UNIQUE), is_available, image_url, snoozed_until (timestamp, nullable))
- `modifier_groups`: (id, name, min_selection, max_selection)
- `modifiers`: (id, group_id, name, price_change, **plu** (Deliverect Modifier ID - CRITICAL, UNIQUE), is_available, snoozed_until (timestamp, nullable))
- `item_modifier_groups`: Links items to modifier groups.
- `orders`: (id, **deliverect_channel_order_id** (UNIQUE), customer_phone, order_type (delivery/pickup), status (e.g., pending, confirmed, preparing, ready, delivered, cancelled), total_price, placed_at, estimated_time, delivery_address (JSON/structured), notes)
- `order_items`: (id, order_id, menu_item_plu, quantity, unit_price, item_name)
- `order_item_modifiers`: (id, order_item_id, modifier_plu, modifier_name, price_change)
- `menu_name_variants`: (id, variant_phrase (lowercase, indexed), canonical_name, target_plu (FK to menu_items.plu or modifiers.plu))
- _(Other tables as needed, e.g., for Deliverect channel links, locations)_

**Key Considerations:**

- The `plu` field in `menu_items` and `modifiers` is essential for mapping to Deliverect entities when creating orders and processing menu updates/snoozing. This corresponds directly to the `plu` field in the sample menu data (See **Appendix A**). Ensure PLUs are unique.
- `deliverect_channel_order_id` is the primary key for linking our order record to Deliverect's system.
- The `menu_name_variants` table should be populated based on the `name_variants` mapping provided in the sample menu data (See **Appendix A**). This allows efficient lookup of canonical item names and PLUs from various user inputs. The `target_plu` should reference the PLU of the item/modifier the variant phrase maps to.

**5.2. Redis Data Usage**

- **Conversation State:** Keyed by Twilio `CallSid`. Stores a JSON blob or hash containing:
  - Current step in the conversation flow.
  - Partially built order (items identified by PLU, quantities, modifiers identified by PLU).
  - User information gathered (e.g., name, phone for callback/updates if needed).
  - Last few interaction turns (for context).
  - Any flags or temporary data needed for the conversation.
  - _TTL should be set appropriately (e.g., 1-2 hours)._
- **Celery Broker/Backend:** Manages task queues and results.
- **Caching (Optional):** Frequently accessed menu data or restaurant info can be cached to reduce DB load.

---

## 6. API Integrations

**6.1. Twilio API**

- **Purpose:** Voice Interaction (Inbound Calls, STT, TTS), SMS Notifications.
- **Key Products Used:** Programmable Voice, Programmable Messaging.
- **Interaction Mode:**
  - **Voice:** Twilio receives calls, initiates webhook requests to `/webhook/voice` endpoint on Render Web Service. Backend responds with TwiML instructions (`<Say>`, `<Gather>`, `<Hangup>`, etc.). STT results are included in Twilio's webhook requests.
  - **SMS:** Render Service (via Celery worker) makes outbound API calls to Twilio's Messaging API to send SMS messages.
- **Authentication:** Twilio Account SID and Auth Token (stored securely as environment variables). Request validation using Twilio signatures on incoming webhooks is recommended.
- **Key Identifiers:** `CallSid` (identifies a unique call leg, used for state management in Redis), `MessageSid` (for SMS).
- **Relevant Docs:**
  - Programmable Voice Quickstarts/API: [https://www.twilio.com/docs/voice](https://www.twilio.com/docs/voice)
  - TwiML for Voice: [https://www.twilio.com/docs/voice/twiml](https://www.twilio.com/docs/voice/twiml)
  - Programmable Messaging API: [https://www.twilio.com/docs/messaging/api](https://www.twilio.com/docs/messaging/api)
  - Securing Webhooks: [https://www.twilio.com/docs/usage/security#validating-requests](https://www.twilio.com/docs/usage/security#validating-requests)

**6.2. OpenAI Agents API (Assistants API)**

- **Purpose:** NLU, Dialogue Management, Tool/Function Calling.
- **Interaction Mode:** Render Web Service makes API calls to OpenAI.
  - Create/Retrieve Assistant (configured with instructions, model, and tool definitions).
  - Create Thread (represents a conversation).
  - Add Message to Thread (user input).
  - Run Assistant on Thread.
  - Handle `requires_action` status (execute defined Python functions/tools based on Agent request).
  - Submit Tool Outputs back to the Run.
  - Retrieve completed Assistant response.
- **Authentication:** OpenAI API Key (stored securely as environment variable).
- **Key Concepts:** Assistant, Thread, Message, Run, Tool/Function Calling.
- **Required Tools (Implemented in Render Python App):**
  - `lookup_menu_item(item_name: str, category: str = None)` -> JSON details or "not found". **This tool MUST leverage the `menu_name_variants` data (derived from Appendix A) stored in Postgres to resolve synonyms/variations (`item_name`) to canonical items and their PLUs before querying the main `menu_items` table.** Should return item details including name, description, price, and PLU.
  - `get_restaurant_info(query: str)` -> Text response (e.g., hours, address).
  - `get_menu_categories()` -> List[str].
  - `get_items_in_category(category_name: str)` -> List[JSON item details].
  - `add_item_to_cart(plu: str, quantity: int, modifiers: List[str] = None)` -> Success/Failure status, updated cart summary. **Requires the correct `plu` obtained via `lookup_menu_item`.** Modifiers should also be identified by their PLUs if applicable. Updates the order state in Redis.
  - `remove_item_from_cart(item_identifier: str)` -> Success/Failure status, updated cart summary. Identifier could be PLU or an index in the cart. Updates Redis state.
  - `get_current_cart()` -> JSON representation of the current order state in Redis.
  - `clear_cart()` -> Success status. Clears order state in Redis.
  - `place_order(customer_details: dict, delivery_details: dict = None, order_type: int)` -> JSON response { success: bool, channelOrderId: str | None, message: str }. _This tool internally calls the Deliverect Create Order API, using PLUs for items/modifiers retrieved from Redis state._
- **Relevant Docs:**
  - Assistants API Overview: [https://platform.openai.com/docs/assistants/overview](https://platform.openai.com/docs/assistants/overview)
  - How Assistants Work: [https://platform.openai.com/docs/assistants/how-it-works](https://platform.openai.com/docs/assistants/how-it-works)
  - Tools (Function Calling): [https://platform.openai.com/docs/assistants/tools](https://platform.openai.com/docs/assistants/tools)

**6.3. Deliverect API**

- **Base URL (Staging):** `https://api.staging.deliverect.com`
- **Authentication:** Likely via API keys or OAuth tokens associated with the `channelName` (Scope). Store credentials securely as environment variables.
- **Key Identifiers:** `channelName` (Scope), `channelLinkId` (Specific store instance), `channelOrderId` (Unique order ID generated by _this_ application), `_id` (Deliverect's internal IDs), `plu` (Product/Modifier ID - **Must match the PLUs provided in the menu data, see Appendix A**).

- **Endpoints Used (Calls FROM Application TO Deliverect):**

  - **Create Order / Cancel Order**

    - **Method:** `POST`
    - **URL:** `/{channelName}/order/{channelLinkId}`
    - **Purpose:** Submits a new order or cancels an existing one.
    - **Path Params:**
      - `channelName` (string, required): Scope provided to the integration. Lowercase.
      - `channelLinkId` (string, required): Unique ID for the specific restaurant location link.
    - **Body Params (Create Order - Key Fields):**
      - `channelOrderId` (string, required): **Unique ID generated by this application.** Cannot be reused within 48hrs.
      - `channelOrderDisplayId` (string, required): User-friendly order ID.
      - `orderType` (int32, required): 1 (pickup), 2 (delivery), 3 (eat-in), 4 (curbside).
      - `pickupTime` / `estimatedPickupTime` (string, ISO 8601 format): Required based on type.
      - `deliveryTime` (string, ISO 8601 format): Mandatory if `orderType` is 2.
      - `customer` (object, required): Customer details (name, phone, email).
      - `deliveryAddress` (object): Required if `orderType` is 2. Address details.
      - `orderIsAlreadyPaid` (boolean, required): Typically `true` if payment handled externally or `false` if pay on pickup/delivery.
      - `payment` (object, required): Payment details (e.g., amount, type).
      - `items` (array[object], required): List of order items.
        - `plu` (string, required): **The Deliverect PLU for the item (from Appendix A / DB).**
        - `name` (string, required)
        - `price` (int32, required): Price in cents.
        - `quantity` (int32, required)
        - `subItems` (array[object]): Modifiers associated with this item (containing their **`plu`**, `name`, `price`, `quantity`).
      - `decimalDigits` (int32): Usually `2`.
      - _(Other fields like `deliveryCost`, `discountTotal`, `tip`, etc. as applicable)_
    - **Body Params (Cancel Order):**
      - Send a _secondary_ request to the same endpoint.
      - `channelOrderId` (string, required): Must match the original order's ID.
      - `status` (int): `100` (Cancel request).
    - **Success Response:** `201 Created` (for new orders), `200 OK` (for cancellation requests). **Note:** This only confirms Deliverect received the request, not POS acceptance. Listen to Order Status Update webhook for confirmation.
    - **Error Responses:** `400` (Bad Request), `401` (Unauthorized), `404` (Not Found), `417` (Validation Failed), `500` (Server Error).

  - **Menu Update Callback (Async)**

    - **Method:** `POST`
    - **URL:** `/{channelName}/menuStatus/{_id}` (The `_id` comes from the `callback` URL provided in the Menu Update webhook payload).
    - **Purpose:** To notify Deliverect that an asynchronously received menu update has been processed.
    - **Path Params:**
      - `channelName` (string, required): Scope.
      - `_id` (string, required): Unique ID of the menu publish request.
    - **Body Params:**
      - `status` (string, required): "ONLINE" (Success) or "FAILED" (Failure).
      - `comment` (string, optional): Details if status is "FAILED".
    - **Success Response:** `200 OK`.
    - **Error Responses:** `400` (Bad Request).
    - **Timing:** Must respond within 30 minutes of receiving the menu update webhook.

  - **Update Store Status (open/closed)**
    - **Method:** `POST`
    - **URL:** `/{channelName}/updateStoreStatus/{channelLinkId}`
    - **Purpose:** To inform Deliverect if the channel (this application) needs to mark the store as open/closed (e.g., due to integration issues). Corresponds to Deliverect's "Busy Mode" initiated _by the channel_.
    - **Path Params:**
      - `channelName` (string, required): Scope.
      - `channelLinkId` (string, required): Store link ID.
    - **Body Params:**
      - `status` (string, required): "open" or "closed".
      - `reason` (string, required): Explanation for the status change.
    - **Success Response:** `200 OK`.
    - **Error Responses:** `400`, `403` (Forbidden), `404`.

- **Endpoints Handled (Webhooks FROM Deliverect TO Application):**
  _These require dedicated API endpoints on the Render Web Service._

  - **Channel Registration**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/register` (Configured in Deliverect)
    - **Purpose:** Called by Deliverect when a new store link is registered, activated, or deactivated.
    - **Request Body from Deliverect:**
      - `status` (string): "register", "active", or "inactive".
      - `channelLocationId` (string): Merchant's ID on the channel platform (if applicable).
      - `channelLinkId` (string): The crucial ID linking Deliverect to this specific store instance. **Store this in DB.**
      - `locationId` (string): Deliverect's internal location ID.
      - `channelLinkName` (string): Display name in Deliverect.
    - **Required Response Body (JSON, case-sensitive):** Provide the URLs of _your_ application's endpoints for Deliverect to call.
      ```json
      {
        "statusUpdateURL": "https://<your-app-domain>/webhook/deliverect/order_status",
        "menuUpdateURL": "https://<your-app-domain>/webhook/deliverect/menu_update",
        "snoozeUnsnoozeURL": "https://<your-app-domain>/webhook/deliverect/snooze",
        "busyModeURL": "https://<your-app-domain>/webhook/deliverect/busy_mode",
        "updatePrepTimeURL": "https://<your-app-domain>/webhook/deliverect/prep_time",
        "paymentUpdateURL": "https://<your-app-domain>/webhook/deliverect/payment_update",
        "courierUpdateURL": "https://<your-app-domain>/webhook/deliverect/courier_update",
        "menuUrl": "https://<your-restaurant-or-proxy-menu-url>"
      }
      ```
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400` (Bad Request).

  - **Menu Update**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/menu_update`
    - **Purpose:** Receives the full menu structure or updates from Deliverect when a customer publishes changes. The structure will resemble the data in **Appendix A**.
    - **Request Body from Deliverect (Async Example):**
      ```json
      {
          "body": {
              "menus": [ /* Array of menu objects - See Deliverect Menu Model */ ],
              "stores": [ "channelLinkId1", ... ],
              "callback": "https://api.staging.deliverect.com/{channelName}/menuStatus/{_id}"
          }
      }
      ```
      _(Sync format is different - handle both if necessary, see docs)_
    - **Action:** Parse the menu structure (categories, items with PLUs, modifiers with PLUs, prices, availability, etc.). Update the PostgreSQL `menu_items`, `modifiers`, `modifier_groups` tables accordingly. **Crucially, update or rebuild the `menu_name_variants` table based on the received item names and potentially inferred variations.** If async, store the `callback` URL and call it via the "Menu Update Callback" endpoint once processing is complete.
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400`.

  - **Order Status Update**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/order_status`
    - **Purpose:** Receives status changes for orders previously submitted. **This is the primary way to know if an order was accepted by the POS and its progress.**
    - **Request Body from Deliverect:**
      ```json
      {
          "orderId": "Deliverect internal order ID",
          "status": <int>, // See Deliverect Order Statuses doc
          "timeStamp": "ISO 8601 timestamp",
          "receiptId": "POS receipt ID (optional)",
          "reason": "Reason text (optional)",
          "channelOrderId": "YOUR unique order ID submitted previously", // CRITICAL for matching
          "location": "Deliverect location ID",
          "channelLink": "channelLinkId"
      }
      ```
    - **Action:** Find the order in Postgres using `channelOrderId`. Update its status. If the status change warrants a customer notification (e.g., Accepted, Ready, Out for Delivery, Cancelled), enqueue a Celery task to send an SMS via Twilio.
    - **Success Response Body:** `{"result": "OK"}`
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400`.

  - **Snooze / Unsnooze Products**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/snooze`
    - **Purpose:** Notifies when specific items (by PLU) should be marked as temporarily unavailable (snoozed) or available again (unsnoozed).
    - **Request Body from Deliverect:**
      ```json
      {
          "accountId":"...",
          "locationId":"...",
          "channelLinkId":"...",
          "operations":[
              {
                  "action":"snooze" or "unsnooze",
                  "data":{
                      "items":[
                         { "plu": "ITEM_PLU_1", "snoozeStart": "...", "snoozeEnd": "..." },
                         { "plu": "MODIFIER_PLU_2", ... }
                      ]
                  }
              }
          ],
          "allSnoozedItems": [ /* Optional: Complete list of currently snoozed PLUs */ ]
      }
      ```
    - **Action:** Update the `is_available` status or `snoozed_until` timestamp for the specified items/modifiers (identified by `plu` matching those in **Appendix A** / DB) in the Postgres database. Use `allSnoozedItems` if present for a full sync.
    - **Success Response Body:** `"ok"` (string)
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400`.

  - **Busy mode**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/busy_mode`
    - **Purpose:** Notifies when the restaurant enables/disables busy mode _from their POS/Deliverect_.
    - **Request Body from Deliverect:**
      ```json
      {
          "accountId": "...",
          "locationId": "...",
          "channelLinkId": "...",
          "status": "PAUSED" | "ONLINE" | "BUSY", // BUSY = Orange busy mode
          "delay": <int> // Minutes delay if status is BUSY
      }
      ```
    - **Action:** Update the store's status in the application (e.g., a flag in Redis or DB associated with the `channelLinkId`). The AI Agent should check this status before attempting to place an order. If "BUSY", potentially inform the user about delays.
    - **Success Response Body:** `{"status": "PAUSED"}` or `{"status": "ONLINE"}` or `{"status": "BUSY"}` (Echo the received status).
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400`.

  - **Preparation time update**

    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/prep_time`
    - **Purpose:** Notifies of an updated estimated pickup/preparation time from the POS.
    - **Request Body from Deliverect:**
      ```json
      {
          "channelOrderId": "YOUR unique order ID",
          "orderId": "Deliverect internal order ID",
          "location": "Deliverect location ID",
          "status": <int>, // Current order status
          "pickupTime": "New estimated pickup time (ISO 8601)"
      }
      ```
    - **Action:** Update the estimated time for the order in Postgres (identified by `channelOrderId`). Potentially enqueue a Celery task to notify the customer via SMS of the updated time.
    - **Success Response Code:** `200 OK`.
    - **Error Response Code:** `400`.

  - **Payment update**
    - **Method:** `POST`
    - **Your Endpoint URL:** `/webhook/deliverect/payment_update`
    - **Purpose:** Receives status updates for payments processed via Deliverect Pay (Likely **Not Applicable** if payments are handled differently, e.g., pay on pickup/delivery or via a separate system).
    - **Request Body from Deliverect:**
      ```json
      {
          "paymentId": "Deliverect Pay ID",
          "status": "authorized" | "refused" | "failed" | "pending"
      }
      ```
    - **Action:** If using Deliverect Pay, update payment status associated with the order.
    - **Success Response Body:** `"OK"` (string)
    - **Success Response Code:** `200 OK`.

---

## 7. Internal Application Components

**7.1. Render Web Service (Python Application)**

- **Responsibilities:**
  - API Endpoint Implementation (Twilio Webhooks, Deliverect Webhooks).
  - Request Handling & Validation.
  - TwiML Generation.
  - Conversation State Management (Interaction with Redis).
  - Orchestration of calls to OpenAI Agents API.
  - Implementation of OpenAI Agent Tools/Functions (interacting with DB, Redis, Deliverect API).
  - Direct calls to Deliverect API (Create Order, Menu Callback, Store Status Update).
  - Database Interaction (Reading menu/restaurant info, Writing order data).
  - Enqueueing tasks to Celery.
- **Key Modules/Packages:** Web framework (Flask/FastAPI/Django), Twilio Python Helper Library, OpenAI Python Library, Requests/HTTPX (for Deliverect API calls), Celery client, Database ORM (SQLAlchemy/Django ORM), Redis client.

**7.2. Render Background Worker (Celery)**

- **Responsibilities:**
  - Executing long-running or asynchronous tasks offloaded by the Web Service.
- **Key Tasks:**
  - `send_sms_notification(customer_phone, message_body)`: Calls Twilio Messaging API.
  - `process_deliverect_menu_update(menu_data, callback_url)`: Parses menu and updates DB (if async menu processing is complex). Calls Deliverect Menu Update Callback upon completion.
  - `poll_deliverect_order_status(channel_order_id)`: (If webhooks are unreliable or need backup) Periodically calls Deliverect API to check status.
  - `update_order_status_and_notify(channel_order_id, new_status, reason)`: Updates DB and potentially queues SMS task.
- **Key Modules/Packages:** Celery, Twilio Python Helper Library, Requests/HTTPX, Database ORM, Redis client.

---

## 8. Key Workflows

**8.1. Handling a Conversation Turn:**

1.  Twilio receives user speech -> Performs STT -> POSTs to `/webhook/voice` with transcription and `CallSid`.
2.  Render App:
    - Retrieves/Initializes conversation state from Redis using `CallSid`.
    - Adds user transcription to conversation history (in Redis state).
    - Calls OpenAI Agent API (`Add Message`, `Run Assistant`).
3.  OpenAI Agent: Processes input + history + tools -> Responds with text or `requires_action` (tool call).
4.  Render App:
    - **If Text Response:**
      - Updates conversation history in Redis.
      - Generates TwiML (`<Say>`, `<Gather>`).
      - Responds to Twilio with TwiML.
    - **If Tool Call (`requires_action`):**
      - Identifies requested tool and arguments.
      - Executes the corresponding Python function (e.g., `lookup_menu_item` uses name variants to find PLU, `add_item_to_cart` updates Redis using PLU).
      - Calls OpenAI Agent API (`Submit Tool Outputs`).
      - Waits for the Run to complete (Agent processes tool result).
      - Retrieves final text response from Agent.
      - Updates conversation history in Redis.
      - Generates TwiML (`<Say>`, `<Gather>`).
      - Responds to Twilio with TwiML.
5.  Twilio executes TwiML (Speaks response, listens for next input). Loop back to step 1.

**8.2. Placing an Order:**

1.  Conversation leads to user confirming the order.
2.  OpenAI Agent decides to call the `place_order` tool with gathered details.
3.  Render App executes the `place_order` Python function:
    - Retrieves final order details (items/modifiers identified by PLU) from Redis state using `CallSid`.
    - Retrieves customer details (phone, name) and delivery/pickup info from state.
    - Validates the order.
    - Generates a unique `channelOrderId`.
    - Formats the order payload according to Deliverect API specs (using PLUs).
    - Makes a `POST` request to Deliverect's `/order` endpoint.
4.  Deliverect API responds (`201 Created` on success).
5.  Render App (`place_order` function):
    - **On Success:**
      - Saves the order details (including `channelOrderId`, initial status 'pending_confirmation') to Postgres.
      - Clears the cart/order state in Redis.
      - Enqueues Celery task: `send_sms_notification(customer_phone, "Order received! We'll text updates.")`.
      - Returns success status and `channelOrderId` to the OpenAI Agent.
    - **On Failure:**
      - Logs the error.
      - Returns failure status and error message to the OpenAI Agent.
6.  OpenAI Agent receives the tool result and formulates a final response to the user (e.g., "Okay, your order [ID] is placed!" or "Sorry, there was an issue placing your order.").
7.  Render App sends the final TwiML response (likely including `<Hangup>`) to Twilio.

**8.3. Handling Order Status Update (Webhook):**

1.  POS updates order status -> Deliverect sends `POST` to `/webhook/deliverect/order_status`.
2.  Render App (`/webhook/deliverect/order_status` endpoint):
    - Parses request body, extracts `channelOrderId` and `status`.
    - Finds the corresponding order in Postgres using `channelOrderId`.
    - Updates the order's status field in Postgres.
    - Determines if the new status requires customer notification.
    - If notification needed: Enqueues Celery task `send_sms_notification(customer_phone, "Update: Your order is now [status_description]!")`.
    - Responds to Deliverect with `200 OK` and `{"result": "OK"}` body.
3.  Celery Worker picks up the `send_sms_notification` task and calls the Twilio Messaging API.

---

## 9. Configuration Management

- All sensitive information (API Keys, Database URLs, Secret Keys) and environment-specific settings MUST be configured using **Environment Variables**.
- Render provides a mechanism for setting environment variables for Web Services and Background Workers.
- **Required Environment Variables (Examples):**
  - `PYTHON_ENV` (e.g., `production`, `staging`)
  - `DATABASE_URL` (Postgres connection string)
  - `REDIS_URL` (Redis connection string)
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER` (The number used for calls/SMS)
  - `OPENAI_API_KEY`
  - `OPENAI_ASSISTANT_ID`
  - `DELIVERECT_CHANNEL_NAME` (The specific scope/channel name)
  - `DELIVERECT_API_KEY` / `DELIVERECT_AUTH_DETAILS` (Actual auth mechanism TBD)
  - `APP_BASE_URL` (e.g., `https://your-app-name.onrender.com`)
  - `CELERY_BROKER_URL` (Usually same as `REDIS_URL`)
  - `CELERY_RESULT_BACKEND` (Usually same as `REDIS_URL`)

---

## 10. Testing Strategy

- **Staging Environment:** A separate Render deployment mirroring production (separate Web Service, Background Worker, Postgres DB, Redis instance) using staging API keys.
- **Unit Tests:** Test individual Python functions/classes in isolation (using `pytest`, `unittest`). Mock external dependencies (DB, Redis, APIs).
- **Integration Tests:** Test interactions between components within the staging environment (e.g., API endpoint receives data -> writes to staging DB). Use `pytest` with HTTP clients (`requests`, `httpx`) and DB/Redis checks.
- **End-to-End (E2E) / Simulation Tests:** Simulate full conversations (text-based via API calls, potentially audio) against the staging environment. Verify conversation flow, tool execution (especially `lookup_menu_item` with variants and `place_order` with PLUs), order placement in staging Deliverect (if possible, or mock Deliverect endpoint), and DB/Redis state changes.

---

## 11. Future Considerations / Roadmap (Placeholder)

- Handling payments directly via phone (requires PCI compliance considerations).
- Support for multiple restaurant locations.
- More sophisticated handling of ambiguous user requests or complex modifications.
- Integration with delivery fleet management APIs.
- Web-based interface for viewing orders/status.
- Analytics dashboard.
- Handling modifier groups and nested modifiers during order taking.

---

**Document Maintenance:** This document should be updated whenever significant changes are made to the architecture, core features, API integrations, data models (including menu structure changes), or key workflows. Accurate documentation is crucial for effective AI-assisted development.

---

## Appendix A: Sample Menu Data (JSON Representation)

This JSON object represents the structure and content of the menu data the system needs to manage. This data is typically received via the Deliverect Menu Update webhook and stored/queried from the PostgreSQL database. The `plu` field is critical for identifying items/modifiers when interacting with Deliverect. The `name_variants` map is used to resolve user utterances to canonical item names and their corresponding PLUs.

```json
{
  "items": [
    {
      "name": "Rare",
      "reference_handler": "COOK-01",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0000",
      "plu": "COOK-01"
    },
    {
      "name": "Medium Rare",
      "reference_handler": "COOK-02",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0001",
      "plu": "COOK-02"
    },
    {
      "name": "Well Done",
      "reference_handler": "COOK-03",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0002",
      "plu": "COOK-03"
    },
    {
      "name": "Fries",
      "reference_handler": "SI-01",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0003",
      "plu": "SI-01"
    },
    {
      "name": "Salad",
      "reference_handler": "SI-02",
      "available": true,
      "price": 2.0,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0004",
      "plu": "SI-02"
    },
    {
      "name": "Mashed Potato",
      "reference_handler": "SI-03",
      "available": true,
      "price": 1.0,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0005",
      "plu": "SI-03"
    },
    {
      "name": "Sashimi",
      "reference_handler": "BXSBVZRHZPYS2",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0006",
      "plu": "BXSBVZRHZPYS2"
    },
    {
      "name": "Sate Sauce",
      "reference_handler": "SAUCE-01",
      "available": true,
      "price": 0.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0007",
      "plu": "SAUCE-01"
    },
    {
      "name": "Hot Sauce",
      "reference_handler": "SAUCE-02",
      "available": true,
      "price": 0.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0008",
      "plu": "SAUCE-02"
    },
    {
      "name": "Pepperoni",
      "reference_handler": "PEPP-#O0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0009",
      "plu": "PEPP-#O0#-"
    },
    {
      "name": "Bacon",
      "reference_handler": "BAC-#O0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0010",
      "plu": "BAC-#O0#-"
    },
    {
      "name": "Red Onion",
      "reference_handler": "RONION-#O0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0011",
      "plu": "RONION-#O0#-"
    },
    {
      "name": "Mushroom",
      "reference_handler": "MUSH-#O0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0012",
      "plu": "MUSH-#O0#-"
    },
    {
      "name": "Red Pepper",
      "reference_handler": "REDPEPP-#O0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0013",
      "plu": "REDPEPP-#O0#-"
    },
    {
      "name": "Chicken Burger",
      "reference_handler": "P-BURG-CHK###PRNT",
      "available": true,
      "price": 9.95,
      "description": "Crispy coated chicken thigh, iceberg lettuce, pickles, slice of cheese & mayo, all in a toasted brioche bun.",
      "snoozed": false,
      "id": "ITEM-0014",
      "plu": "P-BURG-CHK###PRNT"
    },
    {
      "name": "Cheeseburger",
      "reference_handler": "P-BURG-CHE###PRNT",
      "available": true,
      "price": 10.95,
      "description": "100% beef patty, cheddar, caramelized onions, mayonnaise, pickles in a Pretzel bun",
      "snoozed": false,
      "id": "ITEM-0015",
      "plu": "P-BURG-CHE###PRNT"
    },
    {
      "name": "Veggie Burger",
      "reference_handler": "P-BURG-VEG###PRNT",
      "available": true,
      "price": 9.95,
      "description": "Black bean burgers with sweet potato, mushrooms, quinoa, and pecans.",
      "snoozed": false,
      "id": "ITEM-0016",
      "plu": "P-BURG-VEG###PRNT"
    },
    {
      "name": "French Fries",
      "reference_handler": "P-FRS-S-#U#-",
      "available": true,
      "price": 2.0,
      "description": "Plain fries from France",
      "snoozed": false,
      "id": "ITEM-0017",
      "plu": "P-FRS-S-#U#-"
    },
    {
      "name": "Curly Fries",
      "reference_handler": "P-FRS-M-#U#-",
      "available": true,
      "price": 2.0,
      "description": "Spiralised potatoes, fried",
      "snoozed": false,
      "id": "ITEM-0018",
      "plu": "P-FRS-M-#U#-"
    },
    {
      "name": "Seasoned Fries",
      "reference_handler": "P-FRS-L-#U#-",
      "available": true,
      "price": 2.5,
      "description": "Plain fries, but a bit fancier",
      "snoozed": false,
      "id": "ITEM-0019",
      "plu": "P-FRS-L-#U#-"
    },
    {
      "name": "Coca Cola ",
      "reference_handler": "DRNK-01-#U#-",
      "available": true,
      "price": 4.0,
      "description": "Cola flavoured sugar and caffeine",
      "snoozed": false,
      "id": "ITEM-0020",
      "plu": "DRNK-01-#U#-"
    },
    {
      "name": "Diet Coke",
      "reference_handler": "DRNK-02-#U#-",
      "available": true,
      "price": 4.0,
      "description": "Cola flavoured aspartame and caffeine",
      "snoozed": false,
      "id": "ITEM-0021",
      "plu": "DRNK-02-#U#-"
    },
    {
      "name": "Ginger Beer",
      "reference_handler": "DRNK-03-#U#-",
      "available": true,
      "price": 4.0,
      "description": "Australia's favourite ginger beer!",
      "snoozed": false,
      "id": "ITEM-0022",
      "plu": "DRNK-03-#U#-"
    },
    {
      "name": "White Rice",
      "reference_handler": "RICE-01",
      "available": true,
      "price": 4.5,
      "description": "White coloured rice",
      "snoozed": false,
      "id": "ITEM-0023",
      "plu": "RICE-01"
    },
    {
      "name": "Yellow Rice",
      "reference_handler": "RICE-02",
      "available": true,
      "price": 4.5,
      "description": "White rice with Saffron",
      "snoozed": false,
      "id": "ITEM-0024",
      "plu": "RICE-02"
    },
    {
      "name": "Egg Noodles",
      "reference_handler": "NOOD-01",
      "available": true,
      "price": 4.5,
      "description": "Egg noodles and veggies fried and tossed with a delicious sauce",
      "snoozed": false,
      "id": "ITEM-0025",
      "plu": "NOOD-01"
    },
    {
      "name": "Ramen Noodles",
      "reference_handler": "NOOD-02",
      "available": true,
      "price": 4.5,
      "description": "Chinese-style wheat noodles",
      "snoozed": false,
      "id": "ITEM-0026",
      "plu": "NOOD-02"
    },
    {
      "name": "3 Pieces",
      "reference_handler": "VAR-1-#V0#-",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0027",
      "plu": "VAR-1-#V0#-"
    },
    {
      "name": "6 Pieces",
      "reference_handler": "VAR-2-#V300#-",
      "available": true,
      "price": 3.0,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0028",
      "plu": "VAR-2-#V300#-"
    },
    {
      "name": "9 Pieces",
      "reference_handler": "VAR-3-#V550#-",
      "available": true,
      "price": 5.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0029",
      "plu": "VAR-3-#V550#-"
    },
    {
      "name": "Yuzu Salmon",
      "reference_handler": "PRT-01###PRNT-#O0#-",
      "available": true,
      "price": 1.8,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0030",
      "plu": "PRT-01###PRNT-#O0#-"
    },
    {
      "name": "Spicy Tuna",
      "reference_handler": "PRT-02###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0031",
      "plu": "PRT-02###PRNT"
    },
    {
      "name": "Teriyaki Chicken",
      "reference_handler": "PRT-03###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0032",
      "plu": "PRT-03###PRNT"
    },
    {
      "name": "Mini Poke Bowl",
      "reference_handler": "SZ-01",
      "available": true,
      "price": 8.0,
      "description": "A little bowl of Poke",
      "snoozed": false,
      "id": "ITEM-0033",
      "plu": "SZ-01"
    },
    {
      "name": "Large Poke Bowl",
      "reference_handler": "SZ-02",
      "available": true,
      "price": 12.0,
      "description": "A big bowl of Poke",
      "snoozed": false,
      "id": "ITEM-0034",
      "plu": "SZ-02"
    },
    {
      "name": "Sushi Rice",
      "reference_handler": "BS-01###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0035",
      "plu": "BS-01###PRNT"
    },
    {
      "name": "Cruncy Cabbage Slaw",
      "reference_handler": "BS-02###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0036",
      "plu": "BS-02###PRNT"
    },
    {
      "name": "Spicy Tofu",
      "reference_handler": "XTRA-TOF###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0037",
      "plu": "XTRA-TOF###PRNT"
    },
    {
      "name": "Crispy Onions",
      "reference_handler": "XTRA-CONI###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0038",
      "plu": "XTRA-CONI###PRNT"
    },
    {
      "name": "Smashed Avocado",
      "reference_handler": "XTRA-AVO###PRNT",
      "available": true,
      "price": 7.5,
      "description": "",
      "snoozed": false,
      "id": "ITEM-0039",
      "plu": "XTRA-AVO###PRNT"
    },
    {
      "name": "Burger Combo (Drink not Included)",
      "reference_handler": "P-BRGR",
      "available": true,
      "price": 9.5,
      "description": "Combo with Bundles - Modifier Groups as Upsell",
      "snoozed": false,
      "id": "ITEM-0040",
      "plu": "P-BRGR"
    },
    {
      "name": "Delicious Steak Frites",
      "reference_handler": "STK-01",
      "available": true,
      "price": 15.0,
      "description": "Basic Example Product with - Modifier groups - min/max variables - default selection - translations",
      "snoozed": false,
      "id": "ITEM-0041",
      "plu": "STK-01"
    },
    {
      "name": "Chicken Sate",
      "reference_handler": "P-SATE",
      "available": true,
      "price": 4.5,
      "description": "Product with Nested Modifiers - Multimax variables - Allergens (tags)",
      "snoozed": false,
      "id": "ITEM-0042",
      "plu": "P-SATE"
    },
    {
      "name": "Chicken Tenders",
      "reference_handler": "VAR-PROD-1",
      "available": true,
      "price": 8.0,
      "description": "Variant prices for different sizes will show cheapaest on top level product",
      "snoozed": false,
      "id": "ITEM-0043",
      "plu": "VAR-PROD-1"
    },
    {
      "name": "Build your own Pizza",
      "reference_handler": "PIZZ-00",
      "available": true,
      "price": 8.0,
      "description": "Build your own pizza, first topping is free!",
      "snoozed": false,
      "id": "ITEM-0044",
      "plu": "PIZZ-00"
    },
    {
      "name": "The Hawaiian",
      "reference_handler": "PIZZ-01",
      "available": true,
      "price": 8.0,
      "description": "Italy's favourite Pizza!",
      "snoozed": false,
      "id": "ITEM-0045",
      "plu": "PIZZ-01"
    },
    {
      "name": "Build a Poke Bowl",
      "reference_handler": "P-PB-01",
      "available": true,
      "price": 10.0,
      "description": "Select a size then choose your ingredients",
      "snoozed": false,
      "id": "ITEM-0046",
      "plu": "P-PB-01"
    }
  ],
  "modifiers": [],
  "modifierGroups": [],
  "name_variants": {
    "rare": "Medium Rare",
    "medium rare": "Medium Rare",
    "medium": "Medium Rare",
    "well done": "Well Done",
    "well": "Well Done",
    "done": "Well Done",
    "fries": "Seasoned Fries",
    "salad": "Salad",
    "mashed potato": "Mashed Potato",
    "mashed": "Mashed Potato",
    "potato": "Mashed Potato",
    "sashimi": "Sashimi",
    "sate sauce": "Sate Sauce",
    "sate": "Chicken Sate",
    "sauce": "Hot Sauce",
    "hot sauce": "Hot Sauce",
    "pepperoni": "Pepperoni",
    "bacon": "Bacon",
    "red onion": "Red Onion",
    "onion": "Red Onion",
    "mushroom": "Mushroom",
    "red pepper": "Red Pepper",
    "pepper": "Red Pepper",
    "chicken burger": "Chicken Burger",
    "chicken": "Chicken Tenders",
    "burger": "Burger Combo (Drink not Included)",
    "cheeseburger": "Cheeseburger",
    "veggie burger": "Veggie Burger",
    "veggie": "Veggie Burger",
    "french fries": "French Fries",
    "french": "French Fries",
    "curly fries": "Curly Fries",
    "curly": "Curly Fries",
    "seasoned fries": "Seasoned Fries",
    "seasoned": "Seasoned Fries",
    "coca cola ": "Coca Cola ",
    "coca": "Coca Cola ",
    "cola": "Coca Cola ",
    "coca cola": "Coca Cola ",
    "diet coke": "Diet Coke",
    "diet": "Diet Coke",
    "coke": "Diet Coke",
    "ginger beer": "Ginger Beer",
    "ginger": "Ginger Beer",
    "beer": "Ginger Beer",
    "white rice": "White Rice",
    "white": "White Rice",
    "rice": "Sushi Rice",
    "yellow rice": "Yellow Rice",
    "yellow": "Yellow Rice",
    "egg noodles": "Egg Noodles",
    "noodles": "Ramen Noodles",
    "ramen noodles": "Ramen Noodles",
    "ramen": "Ramen Noodles",
    "3 pieces": "3 Pieces",
    "pieces": "9 Pieces",
    "6 pieces": "6 Pieces",
    "9 pieces": "9 Pieces",
    "yuzu salmon": "Yuzu Salmon",
    "yuzu": "Yuzu Salmon",
    "salmon": "Yuzu Salmon",
    "spicy tuna": "Spicy Tuna",
    "spicy": "Spicy Tofu",
    "tuna": "Spicy Tuna",
    "teriyaki chicken": "Teriyaki Chicken",
    "teriyaki": "Teriyaki Chicken",
    "mini poke bowl": "Mini Poke Bowl",
    "mini": "Mini Poke Bowl",
    "poke": "Build a Poke Bowl",
    "bowl": "Build a Poke Bowl",
    "mini poke": "Mini Poke Bowl",
    "poke bowl": "Build a Poke Bowl",
    "large poke bowl": "Large Poke Bowl",
    "large": "Large Poke Bowl",
    "large poke": "Large Poke Bowl",
    "sushi rice": "Sushi Rice",
    "sushi": "Sushi Rice",
    "cruncy cabbage slaw": "Cruncy Cabbage Slaw",
    "cruncy": "Cruncy Cabbage Slaw",
    "cabbage": "Cruncy Cabbage Slaw",
    "slaw": "Cruncy Cabbage Slaw",
    "cruncy cabbage": "Cruncy Cabbage Slaw",
    "cabbage slaw": "Cruncy Cabbage Slaw",
    "spicy tofu": "Spicy Tofu",
    "tofu": "Spicy Tofu",
    "crispy onions": "Crispy Onions",
    "crispy": "Crispy Onions",
    "onions": "Crispy Onions",
    "smashed avocado": "Smashed Avocado",
    "smashed": "Smashed Avocado",
    "avocado": "Smashed Avocado",
    "burger combo (drink not included)": "Burger Combo (Drink not Included)",
    "combo": "Burger Combo (Drink not Included)",
    "(drink": "Burger Combo (Drink not Included)",
    "included)": "Burger Combo (Drink not Included)",
    "burger combo": "Burger Combo (Drink not Included)",
    "combo (drink": "Burger Combo (Drink not Included)",
    "(drink not": "Burger Combo (Drink not Included)",
    "not included)": "Burger Combo (Drink not Included)",
    "delicious steak frites": "Delicious Steak Frites",
    "delicious": "Delicious Steak Frites",
    "steak": "Delicious Steak Frites",
    "frites": "Delicious Steak Frites",
    "delicious steak": "Delicious Steak Frites",
    "steak frites": "Delicious Steak Frites",
    "chicken sate": "Chicken Sate",
    "chicken tenders": "Chicken Tenders",
    "tenders": "Chicken Tenders",
    "build your own pizza": "Build your own Pizza",
    "build": "Build a Poke Bowl",
    "your": "Build your own Pizza",
    "pizza": "Build your own Pizza",
    "build your": "Build your own Pizza",
    "your own": "Build your own Pizza",
    "own pizza": "Build your own Pizza",
    "the hawaiian": "The Hawaiian",
    "hawaiian": "The Hawaiian",
    "build a poke bowl": "Build a Poke Bowl",
    "build a": "Build a Poke Bowl",
    "a poke": "Build a Poke Bowl"
  }
}
```
