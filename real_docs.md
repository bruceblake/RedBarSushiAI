# Project Documentation: AI Restaurant Phone Agent (Enhanced Integration Narrative)

**Version:** 1.1-enhanced
**Date:** 2025-04-18
**Primary Audience:** AI Development Assistants (e.g., Gemini, Claude, GPT-4) for code generation, feature implementation, updates, and debugging.
**Goal:** To provide a comprehensive, technically accurate, and contextually rich overview of the AI Restaurant Phone Agent system. This document details the architecture, component interactions, data flow, API specifications (including full Deliverect details), and menu structure to enable AI assistants to effectively understand, modify, and enhance the codebase.
**Note:** This document integrates detailed API specifications with descriptive context. Appendix A provides crucial menu structure examples.

---

## 1. Project Overview & Mission

**Name:** AI Restaurant Phone Agent (Internal Codename: TBD)

**Mission:** To create a seamless, intelligent, and efficient conversational AI bridge between restaurant customers calling in and the restaurant's operational workflow (via Deliverect). This system aims to provide a natural and helpful ordering experience for customers while offloading the cognitive burden of phone order management from restaurant staff, ultimately improving accuracy, efficiency, and customer satisfaction.

**Core Technologies:**

- **AI Conversation:** OpenAI Agents API (Assistants API) - The reasoning and dialogue engine.
- **Telephony & SMS:** Twilio API - The ears, mouth, and messenger to the outside world.
- **Order Injection:** Deliverect API - The crucial link into the restaurant's Point-of-Sale (POS) ecosystem.
- **Backend:** Python (Framework: TBD - e.g., Flask, FastAPI) hosted on Render - The central nervous system.
- **Task Queue:** Celery - The asynchronous workhorse.
- **Database:** PostgreSQL on Render - The long-term memory.
- **Cache/State/Broker:** Redis on Render - The short-term memory and message hub.

---

## 2. Core Features: The Agent's Capabilities

- **Warm Welcome & Call Management:** Gracefully answers incoming calls via Twilio, managing the audio stream and basic call lifecycle.
- **Intelligent Dialogue Engine:** Leverages the OpenAI Agents API to engage callers in natural, context-aware conversations, understanding intents beyond simple commands.
- **Restaurant Concierge:** Accesses stored information (Postgres) to answer questions about hours, location, policies, etc., acting as a knowledgeable virtual staff member.
- **Interactive Menu Guide:** Discusses menu items dynamically, referencing details (descriptions, prices, options, availability) stored in Postgres. Can answer questions like "Do you have vegetarian options?" or "What's in the cheeseburger?".
- **Effortless Order Building:** Guides users conversationally through constructing their order, handling item additions, quantities, modifications (like "extra cheese" or "no onions"), and special requests, while temporarily storing the in-progress order in Redis.
- **Seamless Order Placement:** Upon confirmation, validates the order details stored in Redis and translates them into the precise format required by the Deliverect API (using critical PLU identifiers), injecting the order directly into the restaurant's workflow.
- **Clear Confirmation:** Verbally confirms successful order placement via Twilio's TTS and triggers an SMS confirmation via Celery and Twilio for customer records.
- **Proactive Communication (Status Updates):** Listens for status change webhooks from Deliverect (e.g., "Accepted by Kitchen," "Ready for Pickup," "Out for Delivery"), updates the order record in Postgres, and triggers timely SMS notifications to the customer via Celery/Twilio.
- **Operational Awareness:** Responds intelligently to real-time store conditions by processing Deliverect webhooks for store closures (`busyModeURL`) or temporary item unavailability (`snoozeUnsnoozeURL`), preventing orders for unavailable items or closed stores.
- **Dynamic Menu Knowledge:** Keeps its internal menu representation (Postgres) up-to-date by processing menu update webhooks (`menuUpdateURL`) from Deliverect.

---

## 3. System Architecture: A Symphony of Services

The system operates as an **API-Driven Agent Architecture with Background Processing**, a carefully choreographed dance between specialized services:

1.  **The Voice Gateway (Twilio):** Acts as the system's interface to the phone network. It _listens_ for incoming calls, _translates_ spoken words to text (STT) based on instructions, _speaks_ the AI's responses (TTS) by following TwiML "scripts" provided by the backend, and _delivers_ SMS messages. It communicates events (like new calls or user speech) to the backend via webhooks.
2.  **The Central Conductor (Render Web Service - Python Backend):** This is the heart of the operation, orchestrating the entire process. It _fields_ incoming requests from Twilio and Deliverect (webhooks), _maintains_ the state of each ongoing conversation in Redis, _mediates_ the dialogue with the OpenAI Agent, _interprets_ the Agent's requests to use tools, _executes_ those tools (querying the database, modifying the Redis cart, calling Deliverect), _generates_ the TwiML scripts for Twilio, and _dispatches_ longer-running tasks (like SMS notifications) to the Celery workers.
3.  **The Brain (OpenAI Agents API):** This performs the heavy lifting of understanding natural language (NLU), managing the conversational flow, reasoning about the user's needs, and deciding on the next action. Crucially, it doesn't perform external actions directly; instead, it _requests_ the execution of specific **Tools (Functions)** implemented in the Render backend when it needs to interact with the outside world (like looking up a menu item or placing the final order).
4.  **The Long-Term Memory (PostgreSQL Database):** Reliably _remembers_ structured, persistent information: the detailed restaurant menu (items, modifiers, prices, **PLUs**), restaurant details (hours, address), historical order records (linked via **`deliverect_channel_order_id`**), and customer information if applicable. It's the source of truth for menu data and order history.
5.  **The Short-Term Memory & Message Hub (Redis):** Provides high-speed access to volatile data. It _tracks_ the state of each active conversation (what's currently in the user's cart, the last few things said), identified by the Twilio `CallSid`. It also acts as the _dispatch center_ (broker) for Celery, holding tasks waiting to be processed.
6.  **The Background Assistant (Celery Workers):** Runs as separate processes, diligently _working_ on tasks that don't require immediate user interaction. This includes sending SMS confirmations via Twilio or potentially polling external APIs if webhooks are unreliable, ensuring the main web service remains responsive.
7.  **The POS Bridge (Deliverect API):** _Connects_ the AI agent's finalized order to the restaurant's actual Point-of-Sale system. The Render service _translates_ the order into Deliverect's required format (using PLUs) and sends it via API call. Deliverect also communicates back via webhooks, informing the system about menu changes, order status updates from the POS, and store availability.

**Conceptual Flow:** A customer call initiates a flow where Twilio informs the Render Backend. The Backend manages state in Redis and converses with the OpenAI Agent. The Agent uses Tools (executed by the Backend, potentially accessing Postgres or Redis) to gather information or build the order. When ready, an Agent Tool triggers the Backend to call the Deliverect API (using PLUs). Status updates flow back from Deliverect via webhooks, triggering Backend logic, Celery tasks, and finally Twilio SMS notifications.

---

## 4. Technology Stack Summary

- **Cloud:** Render.io (Web Service, Background Worker, Postgres, Redis)
- **Language:** Python 3.10+ (TBD Framework: Flask/FastAPI/Django)
- **Tasks:** Celery
- **DB ORM:** SQLAlchemy/Django ORM (TBD)
- **APIs:** Twilio, OpenAI Agents, Deliverect

---

## 5. Data Storage: Remembering and Tracking

**5.1. The Long-Term Memory (PostgreSQL Schema Highlights)**

Stores the structured, persistent truth of the restaurant and its orders. Reflects the structure received from Deliverect (see Appendix A).

- `restaurants`: Basic info.
- `menu_categories`: `id`, `deliverect_category_id`, `name`, `description`.
- `menu_items`: `id`, `category_id`, `name`, `description`, `price`, **`plu`** (UNIQUE, CRITICAL link to POS/Deliverect), `deliverect_item_id`, `is_available`, `is_combo`, `is_variant`, `image_url`, `snoozed_until`.
- `modifiers`: `id`, `modifier_group_id`, `name`, `price_change`, **`plu`** (UNIQUE, CRITICAL), `deliverect_modifier_id`, `is_available`, `snoozed_until`.
- `modifier_groups`: `id`, `deliverect_group_id`, `name`, `min_selection`, `max_selection`, `multiMax`, `plu`, `is_variant_group`.
- `item_modifier_groups`: Links `menu_items` to `modifier_groups`.
- `group_modifiers`: Links `modifier_groups` to `modifiers`.
- `orders`: `id`, **`deliverect_channel_order_id`** (UNIQUE, CRITICAL link to Deliverect order), `customer_phone`, `order_type`, `status`, `total_price`, `placed_at`, `estimated_time`, `delivery_address`.
- `order_items`: Links `orders` to `menu_items` via `menu_item_plu`, stores quantity.
- `order_item_modifiers`: Links `order_items` to `modifiers` via `modifier_plu`.
- `menu_name_variants`: `variant_phrase` (lowercase), `canonical_name`, `target_plu` (FK). **Essential for mapping natural language ("fries") to specific item PLUs ("P-FRS-L").** Populated from menu data and potentially synonyms.

**5.2. The Short-Term Memory & Message Hub (Redis)**

Handles fast-changing, temporary data for active interactions and task queuing.

- **Conversation State:** Keyed by Twilio `CallSid`. Stores JSON/Hash containing the _current_ state of an ongoing call:
  - Partially built order (items/modifiers identified by their **PLUs**, quantities).
  - User details gathered during the call.
  - Contextual flags or history needed for the OpenAI Agent.
  - _Must have a TTL (e.g., 1-2 hours) to automatically clear stale sessions._
- **Celery Broker/Backend:** Acts as the queue holding tasks for the background workers.
- **Optional Caching:** Can store frequently accessed menu data for faster lookups by the Agent Tools.

---

## 6. API Integrations: The System's Dialogue

**6.1. The Ears and Mouth (Twilio API)**

- **Purpose:** Connects to the phone network for voice calls and SMS.
- **Interaction:**
  - **Voice:** Twilio receives calls -> Sends webhook to `/webhook/voice`. Backend responds with TwiML (XML instructions telling Twilio what to `<Say>`, `<Gather>` speech for, `<Hangup>`, etc.). Twilio performs STT and includes transcription in subsequent webhooks.
  - **SMS:** Backend (via Celery) calls Twilio's REST API to send outbound messages.
- **Auth:** Account SID/Auth Token (Env Vars). Webhook validation using Twilio signatures is vital for security.
- **Key ID:** `CallSid` uniquely identifies an active call leg and is used as the key for conversation state in Redis.
- **Relevant Docs:** See Twilio Documentation.

**6.2. The Conversational Core (OpenAI Agents API - Assistants API)**

- **Purpose:** Provides the natural language understanding, reasoning, and dialogue management.
- **Interaction:** The Render backend acts as the client to the OpenAI API.
  - It manages the Assistant and Thread lifecycle.
  - Sends user transcriptions (from Twilio) as Messages to the Thread.
  - Runs the Assistant on the Thread.
  - **Tool Belt:** When the Agent needs external info or action, it responds with `requires_action`, specifying a **Tool (Function)** name and arguments. The backend _executes_ this tool (as a local Python function) and submits the results back to the Agent, allowing the conversation to proceed. This is how the Agent "looks up" menu items or "places" an order – by asking the backend to do it.
- **Auth:** OpenAI API Key (Env Var).
- **Key Concepts:** Assistant (the configured AI personality/capabilities), Thread (a single conversation), Message (user input or AI response), Run (an execution of the Assistant on the Thread), Tool/Function Calling (the mechanism for the Agent to request backend actions).
- **Required Tools (Python functions implemented in Render backend):**
  - `lookup_menu_item(item_name: str)`: **Translates user request** (e.g., "curly fries") into a specific item PLU using the `menu_name_variants` table, then fetches details (name, desc, price, PLU) from the `menu_items` table. Returns JSON details or "not found".
  - `get_restaurant_info(query: str)`: **Retrieves static info** (hours, address) from the `restaurants` table. Returns text.
  - `add_item_to_cart(plu: str, quantity: int, modifiers: List[str] = None)`: **Modifies the current order state** stored in Redis for the active `CallSid`. Uses PLUs for items and modifiers. Returns confirmation/summary.
  - `get_current_cart()`: **Reads the current order state** from Redis for the active `CallSid`. Returns JSON.
  - `place_order(customer_details: dict, delivery_details: dict = None, order_type: int)`: **Initiates the final order submission.** Retrieves the complete cart from Redis, generates a unique `channelOrderId`, formats the payload using PLUs, and calls the Deliverect Create Order API. Returns success/failure status and the `channelOrderId`.
  - _(Other tools like get_categories, remove_item, clear_cart as needed)_
- **Relevant Docs:** See OpenAI Assistants API Documentation.

**6.3. The POS Bridge (Deliverect API - Full Details)**

Connects the AI's understanding of the order to the restaurant's operational system via the POS. The Render backend acts as the translator, using PLUs.

- **Base URL (Staging):** `https://api.staging.deliverect.com`
- **Authentication:** API Key/OAuth (TBD, Env Vars). Associated with `channelName`.
- **Key IDs:** `channelName` (Scope), `channelLinkId` (Store instance), `channelOrderId` (App-generated unique order ID), `plu` (Item/Modifier ID from menu data - see Appendix A).

### Endpoints Used (Calls FROM Application TO Deliverect)

#### Create Order

- **Method:** `POST`
- **URL:** `https://api.staging.deliverect.com/{channelName}/order/{channelLinkId}`
- **Purpose:** Place a new order or process a cancellation of an existing order.
- **Channel 'Scope':** The `{channelname}` represents the Scope provided to create orders. If invalid or no access, request is unauthorised. Use lowercase letters.
- **Channel Link ID:** The `{channelLinkId}` is the unique identifier of the channel in the restaurant location. Obtained via `Register Channel` webhook. If invalid or not available, request is unauthorised.
- **Order Types:**
  - `1`: pick up
  - `2`: delivery
  - `3`: Eat-in
  - `4`: Curbside
- **Order Response:** All valid requests receive `201 Created`. This does **not** indicate POS success; reference `Order Status Update` webhook events for confirmation.
- **Path Parameters:**
  - `channelName` (string, required): 'scope' of the channel.
  - `channelLinkId` (string, required): Unique identifier of the channel link.
- **Body Parameters:**
  - `channelOrderId` (string, required): Unique ID generated by this application. Cannot be reused within 48hr after pickup time.
  - `channelOrderDisplayId` (string, required): User-friendly order ID.
  - `orderType` (int32, required): See Order Types above.
  - `pickupTime` (string, ISO 8601 format): Estimated pickup time.
  - `estimatedPickupTime` (string, ISO 8601 format): Alternative pickup time field.
  - `deliveryTime` (string, ISO 8601 format): Mandatory if `orderType` is 2 (delivery).
  - `deliveryIsAsap` (boolean, default: `true`): If delivery should be ASAP.
  - `courier` (string, required): If platform handles delivery, specify channel name here. Otherwise, use `"restaurant"` (lowercase) for self-delivery by the restaurant.
  - `customer` (object, required): Customer details (name, phoneNumber, email, companyName, deliveryArea, notes).
  - `deliveryAddress` (object, required if `orderType` is 2): Delivery address details (street, streetNumber, postcode, city, latitude, longitude, notes).
  - `orderIsAlreadyPaid` (boolean, required, default: `true`): Indicates if payment was handled.
  - `payment` (object, required): Payment details (amount, type [0=cash, 1=card, 2=voucher, 3=online], provider).
  - `note` (string): General order notes.
  - `items` (array of objects, required): List of order items.
    - `plu` (string, required): The Deliverect PLU for the item/modifier.
    - `name` (string, required): Item name.
    - `price` (int32, required): Price in cents.
    - `quantity` (int32, required): Quantity of this item.
    - `subItems` (array of objects): Modifiers attached to this item. Each subItem object has the same structure (`plu`, `name`, `price`, `quantity`, potentially nested `subItems`).
  - `decimalDigits` (int32, default: 2): Number of decimal digits for prices (usually 2).
  - `numberOfCustomers` (int32): Number of people this order is for.
  - `deliveryCost` (int32): Delivery cost in cents.
  - `serviceCharge` (int32): Service charge in cents.
  - `discountTotal` (int32): Total discount amount in cents.
  - `discounts` (array of objects): List of discounts applied (each with `name`, `type`, `amount`, `plu`, `discountId`).
  - `taxes` (array of objects): List of taxes applied (each with `name`, `amount`, `taxId`).
  - `table` (string): Table ID or name for eat-in orders.
  - `validationId` (string): ID from `ValidateDelivery` endpoint (if used). Valid for 10 mins.
  - `bagFee` (int32): Bag fee in cents.
  - `driverTip` (int32): Tip for the driver in cents.
  - `tip` (int32): General tip in cents.
- **Responses:**
  - `201 Created`: Order received by Deliverect.
  - `400 Bad Request`: Invalid request format or data.
  - `401 Unauthorized`: Invalid `channelName` or `channelLinkId`.
  - `404 Not Found`: Endpoint/resource not found.
  - `417 Expectation Failed`: Validation error (e.g., expired `validationId`).
  - `500 Internal Server Error`: Deliverect server error.

#### Cancel Order

- **Method:** `POST`
- **URL:** `https://api.staging.deliverect.com/{channelName}/order/{channelLinkId}` (Same endpoint as Create Order)
- **Purpose:** Request cancellation of a previously submitted order.
- **Process:** Send a _secondary_ order payload with the _same_ `channelOrderId` as the original order and set `"status": 100`.
- **POS Handling:** The POS receives this as a cancellation request and initiates its void/cancellation workflow.
- **Confirmation:** A successful POS cancellation results in an `Order Status Update` webhook with status `110` (CANCELED).
- **Warning:** Cancellation is often impossible once an order is `Accepted` (status 20) or higher by the POS. Advised not to attempt cancellation after acceptance. Deliverect does not validate this based on status.
- **Responses:**
  - `200 OK`: Cancellation request received by Deliverect.
  - `400 Bad Request`: Invalid format.

#### Menu Update Callback (Async)

- **Method:** `POST`
- **URL:** `https://api.staging.deliverect.com/{channelName}/menuStatus/{_id}` (URL provided in the async Menu Update webhook payload's `callback` field)
- **Purpose:** Notify Deliverect that an asynchronously received menu update has been fully processed by the application.
- **Path Parameters:**
  - `channelName` (string, required): Case-sensitive Scope.
  - `_id` (string, required): Unique identifier of the menu publish request (from the callback URL).
- **Body Parameters:**
  - `status` (string, required): `"ONLINE"` (Success) or `"FAILED"` (Failure).
  - `comment` (string, optional): Details if status is `"FAILED"`.
- **Response Time:** Must be called within 30 minutes of receiving the async menu update webhook, otherwise Deliverect classifies the operation as "Failed".
- **Responses:**
  - `200 OK`: Callback received.
  - `400 Bad Request`: Invalid request.

#### Update Store Status (open/closed)

- **Method:** `POST`
- **URL:** `https://api.staging.deliverect.com/{channelName}/updateStoreStatus/{channelLinkId}`
- **Purpose:** Allows the channel integration (this application) to inform Deliverect about the store's status (e.g., if the integration needs to temporarily stop orders). Corresponds to Deliverect's "Busy Mode" initiated _by the channel_.
- **Path Parameters:**
  - `channelName` (string, required): 'scope' of the channel.
  - `channelLinkId` (string, required): Unique identifier of the channel link.
- **Body Parameters:**
  - `status` (string, required): `"open"` or `"closed"`.
  - `reason` (string, required): Explanation for the status change.
- **Responses:**
  - `200 OK`: Status update received.
  - `400 Bad Request`: Invalid request.
  - `403 Forbidden`: Incorrect scope/permissions.
  - `404 Not Found`: Invalid `channelLinkId`.

### Endpoints Handled (Webhooks FROM Deliverect TO Application)

_These require dedicated HTTP endpoints on the Render Web Service._

#### Channel Registration

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/register` (Configured in Deliverect)
- **Purpose:** Called by Deliverect when a new store link is registered (`register`), activated (`active`), or deactivated (`inactive`). Establishes the link.
- **Request Body from Deliverect:**
  - `status` (string): "register", "active", or "inactive".
  - `channelLocationId` (string): Merchant's ID on the channel platform (if applicable).
  - `channelLinkId` (string): **CRITICAL ID linking Deliverect to this specific store instance. Store this in DB.**
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

#### Menu Update

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/menu_update`
- **Purpose:** Receives the full menu structure or updates from Deliverect when a customer publishes changes. This is the source of truth for the menu data. See **Appendix A** for detailed structure examples and the **Menu Glossary** (Appendix B) for field definitions.
- **Request Body from Deliverect (Async Example):**
  ```json
  {
      "body": {
          "menus": [ /* Array of menu objects - See Appendix A / Glossary */ ],
          "stores": [ "channelLinkId1", ... ],
          "callback": "https://api.staging.deliverect.com/{channelName}/menuStatus/{_id}" // URL for Menu Update Callback API
      }
  }
  ```
  _(Sync format differs: payload is directly the array of menu properties)_
- **Action:** Parse the complex menu structure (categories, items with PLUs, modifiers with PLUs, prices, availability, subProducts links, etc.). Update the PostgreSQL database accordingly (tables like `menu_items`, `modifiers`, `modifier_groups`, `menu_name_variants`). If async, store the `callback` URL and call the "Menu Update Callback" API endpoint once processing is complete.
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Order Status Update

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/order_status`
- **Purpose:** Receives status changes for orders previously submitted via the Create Order API. **This is the primary way to know if an order was accepted by the POS and its subsequent progress.** Critical for triggering customer SMS updates.
- **Request Body from Deliverect:**
  ```json
  {
      "orderId": "Deliverect internal order ID",
      "status": <int>, // Status code (e.g., 20=Accepted, 110=Canceled) - See Deliverect docs for full list
      "timeStamp": "ISO 8601 timestamp",
      "receiptId": "POS receipt ID (optional)",
      "reason": "Reason text (optional, e.g., for failure/cancellation)",
      "channelOrderId": "YOUR unique order ID submitted previously", // CRITICAL for matching
      "location": "Deliverect location ID",
      "channelLink": "channelLinkId"
  }
  ```
- **Action:** Find the order in Postgres using `channelOrderId`. Update its status field. If the status change warrants a customer notification (e.g., Accepted, Ready, Out for Delivery, Cancelled), enqueue a Celery task to send an SMS via Twilio.
- **Success Response Body:** `{"result": "OK"}`
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Snooze / Unsnooze Products

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/snooze`
- **Purpose:** Notifies when specific items (identified by PLU) should be marked as temporarily unavailable (snoozed) or available again (unsnoozed). Triggered only for items in active/published menus. Allows the AI to know item availability.
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
                     { "plu": "ITEM_PLU_1", "snoozeStart": "ISO8601_UTC", "snoozeEnd": "ISO8601_UTC" },
                     { "plu": "MODIFIER_PLU_2", ... }
                  ]
              }
          }
      ],
      "allSnoozedItems": [ /* Optional: Complete list of currently snoozed PLUs {plu, snoozeStart, snoozeEnd} */ ]
  }
  ```
- **Action:** Update the `is_available` status or `snoozed_until` timestamp for the specified items/modifiers (identified by `plu`) in the Postgres database. Use `allSnoozedItems` if present for a full sync. Deliverect sends a separate `unsnooze` event when the time expires or if manually unsnoozed.
- **Success Response Body:** `"ok"` (string)
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Busy mode

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/busy_mode`
- **Purpose:** Notifies when the restaurant enables/disables busy mode _from their POS/Deliverect_. Allows the AI to manage customer expectations or prevent orders.
- **Request Body from Deliverect:**
  ```json
  {
      "accountId": "...",
      "locationId": "...",
      "channelLinkId": "...",
      "status": "PAUSED" | "ONLINE" | "BUSY", // PAUSED=Closed, ONLINE=Open, BUSY=Busy (Orange)
      "delay": <int> // Minutes delay if status is BUSY (indicates increased prep time)
  }
  ```
- **Action:** Update the store's status in the application (e.g., a flag in Redis or DB associated with the `channelLinkId`). The AI Agent should check this status before attempting to place an order. If "BUSY", potentially inform the user about delays or adjust estimated times. If "PAUSED", prevent new orders.
- **Success Response Body:** `{"status": "PAUSED"}` or `{"status": "ONLINE"}` or `{"status": "BUSY"}` (Echo the received status).
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Preparation time update

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/prep_time`
- **Purpose:** Notifies of an updated estimated pickup/preparation time from the POS for a specific order. Allows for more accurate customer updates.
- **Request Body from Deliverect:**
  ```json
  {
      "channelOrderId": "YOUR unique order ID",
      "orderId": "Deliverect internal order ID",
      "location": "Deliverect location ID",
      "status": <int>, // Current order status (e.g., 20)
      "pickupTime": "New estimated pickup time (ISO 8601 UTC)"
  }
  ```
- **Action:** Update the estimated time for the order in Postgres (identified by `channelOrderId`). Potentially enqueue a Celery task to notify the customer via SMS of the updated time.
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Payment update

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/payment_update`
- **Purpose:** Receives status updates for payments processed via Deliverect Pay. (Likely **Not Applicable** if payments are handled differently).
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

## 7. Internal Application Components: The Supporting Cast

**7.1. The Master Orchestrator (Render Web Service - Python)**

- **Responsibilities:**
  - Fielding incoming calls via Twilio webhooks.
  - Receiving and processing crucial updates via Deliverect webhooks.
  - Validating incoming requests.
  - Generating dynamic TwiML scripts to guide Twilio's actions.
  - Maintaining the dialogue flow by interacting with the OpenAI Agents API.
  - Executing Agent requests (Tools/Functions) by interacting with the database, Redis cache, and Deliverect API.
  - Managing the lifecycle of conversation state in Redis.
  - Dispatching non-blocking tasks to the Celery queue.
- **Key Modules/Packages:** Web framework (Flask/FastAPI/Django), Twilio Python Helper Library, OpenAI Python Library, Requests/HTTPX (for Deliverect API calls), Celery client, Database ORM (SQLAlchemy/Django ORM), Redis client.

**7.2. The Background Assistant (Celery Worker)**

- **Responsibilities:**
  - Executing tasks asynchronously, ensuring the web service remains responsive. Handles operations that don't require immediate feedback to the user or calling system.
- **Key Tasks:**
  - `send_sms_notification`: Composing and sending order confirmations/updates via the Twilio Messaging API.
  - `process_deliverect_menu_update`: Handling potentially large menu updates received via webhook, parsing, and updating the Postgres DB. Includes calling the Deliverect Menu Update Callback API upon completion if needed.
  - `poll_deliverect_order_status`: (Optional backup) Periodically checking the Deliverect API for status updates if webhooks are deemed unreliable.
  - `update_order_status_and_notify`: A task potentially triggered by the status webhook handler to decouple DB updates and notification logic.
- **Key Modules/Packages:** Celery, Twilio Python Helper Library, Requests/HTTPX, Database ORM, Redis client.

---

## 8. Key Workflows: Bringing It All Together

**8.1. Handling a Conversation Turn:**

1.  **Initiation:** Twilio receives user speech, performs STT, and sends a POST request to the Render backend's `/webhook/voice` endpoint, including the transcription and the unique `CallSid`.
2.  **State Retrieval:** The backend uses the `CallSid` to retrieve the current conversation state (e.g., existing cart items, context) from Redis. If no state exists, it initializes a new one.
3.  **Agent Invocation:** The backend adds the user's transcription as a new message to the appropriate OpenAI Agent Thread and initiates a Run.
4.  **Agent Processing:** The OpenAI Agent processes the input, considering history and available Tools. It formulates a response.
5.  **Response Handling:**
    - **Text Response:** If the Agent provides text, the backend updates the Redis state, generates TwiML containing `<Say>` and `<Gather>` tags, and sends this XML back to Twilio.
    - **Tool Call Required:** If the Agent responds with `requires_action`, the backend parses the requested tool name (e.g., `lookup_menu_item`) and arguments.
6.  **Tool Execution Cycle (If Required):**
    - The backend executes the corresponding local Python function (e.g., querying the DB using `menu_name_variants` and PLUs, updating the Redis cart).
    - The backend submits the tool's output back to the OpenAI Agent Run.
    - The Agent processes the tool's result and generates its final text response for this turn.
    - The backend receives this text, updates Redis state, generates TwiML (`<Say>`, `<Gather>`), and sends it to Twilio.
7.  **Continuation:** Twilio executes the TwiML (speaks the response, listens for the next user utterance), restarting the cycle from step 1.

**8.2. Placing an Order:**

1.  **Confirmation:** Through conversation, the user confirms they are ready to place the order.
2.  **Agent Decision:** The OpenAI Agent determines the intent is to finalize and calls the `place_order` tool, potentially passing gathered customer/delivery details.
3.  **Backend Execution (`place_order` function):**
    - Retrieves the complete, validated order details (items/modifiers identified by PLU) from Redis state using the `CallSid`.
    - Generates a unique `channelOrderId` for this transaction.
    - Formats the order payload meticulously according to Deliverect API specifications, ensuring correct PLUs are used for all items and modifiers.
    - Makes a `POST` request to the Deliverect `/order` endpoint.
4.  **Deliverect Acknowledgment:** Deliverect responds (e.g., `201 Created` if the format is valid).
5.  **Backend Post-Processing:**
    - **On Success (201):** Records the order (with `channelOrderId` and an initial status like 'pending_confirmation') in the Postgres database. Clears the temporary cart from Redis. Enqueues a Celery task (`send_sms_notification`) to inform the customer via Twilio SMS. Returns a success status (including the `channelOrderId`) back to the OpenAI Agent as the tool output.
    - **On Failure:** Logs the error details. Returns a failure status and message back to the OpenAI Agent.
6.  **Final Confirmation:** The OpenAI Agent receives the tool's result and formulates a final verbal confirmation or error message for the user.
7.  **Call Conclusion:** The backend sends the final TwiML response (e.g., "Okay, your order [ID] is placed! You'll receive SMS updates. Goodbye.") often including `<Hangup>` to Twilio.

**8.3. Handling Order Status Update (Webhook):**

1.  **External Trigger:** The restaurant's POS updates an order's status (e.g., accepts it, marks it ready).
2.  **Deliverect Notification:** Deliverect sends a POST request to the Render backend's `/webhook/deliverect/order_status` endpoint, containing the `channelOrderId` and the new integer `status` code.
3.  **Backend Processing:**
    - The endpoint handler parses the request.
    - It uses the `channelOrderId` to find the corresponding order record in the Postgres database.
    - It updates the `status` field in the database record.
    - It checks if this new status warrants notifying the customer (e.g., status 20 'Accepted', 70 'Ready for Pickup', 80 'Delivered', 110 'Cancelled').
    - If notification is needed, it enqueues a Celery task (`send_sms_notification`) with the customer's phone number and an appropriate message.
    - It responds immediately to Deliverect with `200 OK` and `{"result": "OK"}` to acknowledge receipt.
4.  **Notification Delivery:** The Celery worker picks up the task and uses the Twilio API to send the SMS update to the customer.

---

## 9. Configuration Management

- **Environment Variables:** The exclusive method for managing secrets (API Keys, Database URLs, Secret Keys) and environment-specific settings (e.g., `PYTHON_ENV`, `APP_BASE_URL`).
- **Platform:** Render.io provides secure environment variable management for Web Services and Background Workers.
- **Required Examples:** `DATABASE_URL`, `REDIS_URL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID`, `DELIVERECT_CHANNEL_NAME`, `DELIVERECT_API_KEY` / `DELIVERECT_AUTH_DETAILS`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.

---

## 10. Testing Strategy Summary

- **Staging Environment:** A mandatory, isolated replica of production on Render (separate services, DB, Redis) using dedicated test/staging API keys.
- **Unit Tests (`pytest`):** Focus on isolating and testing individual Python functions/classes (e.g., tool implementations, utility functions, webhook parsing logic). Mock external dependencies (DB, Redis, API calls) heavily using libraries like `unittest.mock` or `pytest-mock`.
- **Integration Tests (`pytest`):** Verify interactions between components within the staging environment. Examples: Test a Deliverect webhook handler correctly updates the staging DB; test if placing an order via a simulated tool call correctly interacts with Redis and (mocked or staging) Deliverect. Use HTTP clients (`requests`, `httpx`) and direct checks against staging DB/Redis.
- **End-to-End (E2E) / Simulation Tests:** Simulate complete user conversations against the _staging_ application.
  - Use scripts or test frameworks to send sequences of inputs (simulating user speech via text passed to the Agent).
  - Verify the conversational flow progresses as expected.
  - Assert that the correct Agent Tools are called with appropriate arguments (check logs or mock interactions).
  - Verify interactions with the staging Deliverect environment (if feasible and using test credentials) or a mocked Deliverect endpoint.
  - Check final state in staging Postgres (order created correctly) and Redis (state cleared).
  - Verify SMS tasks are queued in Celery (or check Twilio logs if hitting staging Twilio).

---

## 11. Future Considerations / Roadmap (Placeholder)

- Implementing direct payment processing over the phone (requires significant security/PCI compliance effort).
- Scaling to support multiple restaurant locations (requires changes to configuration, potentially DB schema, and `channelLinkId` management).
- Enhancing NLU to handle more complex or ambiguous user requests gracefully.
- Integrating with third-party delivery fleet management APIs.
- Developing a web-based dashboard for restaurant staff to view incoming orders and statuses.
- Adding analytics to track usage patterns, common issues, and order success rates.
- Refining handling of nested modifiers and complex product configurations during order taking.

---

**Document Maintenance:** This document requires regular updates to reflect changes in architecture, features, API contracts (especially Deliverect), data models, or core workflows. Accuracy is paramount for effective AI-assisted development.

---

## Appendix A: Deliverect Menu Data Structure (Examples)

The following illustrates the structure of the JSON payload received via the Deliverect Menu Update webhook (`/webhook/deliverect/menu_update`). The application needs to parse this structure to populate its internal database. **PLU** is the critical identifier linking items/modifiers to Deliverect. IDs (`_id`) link components within the payload.

**(Note: This is a representative sample, not the complete menu.)**

```json
[ // The payload is typically an array containing one main menu object
  {
    "menu": "Menu Name",
    "menuId": "67209bfb174a0e5384d4db61", // Deliverect Menu ID
    "channelLinkId": "66b35566dc02e27b286fca60", // Specific store link ID
    "currency": 1, // Currency code (lookup needed)
    "menuType": 0, // 0 = Delivery & Pickup, etc.
    "availabilities": [ // Store opening hours
      { "dayOfWeek": 1, "startTime": "00:00", "endTime": "23:59" },
      // ... other days ...
    ],
    "categories": [ // Array of category objects
      {
        "_id": "67209bfb174a0e5384d4db4f", // Category's internal Deliverect ID
        "name": "Steak & Burgers",
        "posCategoryId": "STK", // Optional POS category ID
        "subProducts": [ // List of Deliverect Item IDs belonging to this category
          "6721daafc33216a11b4e239d", // -> "Deluxe Burger (Pick and Choose)"
          "6721daafc33216a11b4e23a2", // -> "Burger Combo (Drink not Included)"
          "66b35629a7eb47d479f1d31b", // -> "Chicken Burger"
          "66b35629a7eb47d479f1d339", // -> "Delicious Steak Frites"
          // ... other item IDs ...
        ],
        "availabilities": [] // Category-specific availability overrides
        // ... other category fields (description, image, etc.)
      },
      {
        "_id": "67209bfb174a0e5384d4db50",
        "name": "Sides",
        "posCategoryId": "SD",
        "subProducts": [
          "66b35629a7eb47d479f1d309", // -> "White Rice"
          "66b35629a7eb47d479f1d30b", // -> "Egg Noodles"
          // ... other side item IDs ...
        ],
        "availabilities": []
      }
      // ... other categories ...
    ],
    "products": { // Dictionary mapping Deliverect Item ID to Product details
      "66b35629a7eb47d479f1d339": { // Example: "Delicious Steak Frites"
        "_id": "66b35629a7eb47d479f1d339",
        "name": "Delicious Steak Frites",
        "description": "Basic Example Product with - Modifier groups...",
        "price": 1500, // Price in cents
        "plu": "STK-01", // CRITICAL ID for ordering
        "productType": 1, // 1 = Product
        "imageUrl": "https://...",
        "subProducts": [ // List of Modifier Group IDs attached to this item
          "66b35629a7eb47d479f1d33b", // -> Modifier Group "Cooking instructions"
          "66b35629a7eb47d479f1d2fb"  // -> Modifier Group "Add a side"
        ],
        "snoozed": false, // Current snooze status
        "deliveryTax": 9000, // Tax info (integer, 3 decimal places, e.g., 9000 = 9.000%)
        "takeawayTax": 9000,
        "eatInTax": 9000
        // ... other product fields (tags, nutritional info, etc.)
      },
      "66b35629a7eb47d479f1d335": { // Example: "Chicken Tenders" (Product with Variants)
        "_id": "66b35629a7eb47d479f1d335",
        "name": "Chicken Tenders",
        "description": "Variant prices for different sizes...",
        "price": 800, // Base price (often cheapest variant)
        "plu": "VAR-PROD-1",
        "productType": 1,
        "isVariant": true, // Indicates this product uses variants for pricing/options
        "subProducts": [
          "66b35629a7eb47d479f1d371" // -> Modifier Group "How many pieces?" (Variant Group)
        ],
        "snoozed": false
      },
      "6721daafc33216a11b4e23a3": { // Example: "3 Pieces" (A Variant Item itself)
        "_id": "6721daafc33216a11b4e23a3",
        "name": "3 Pieces",
        "price": 0, // Price difference relative to base product (VAR-PROD-1)
        "plu": "VAR-1-#V0#-", // Variant PLU
        "productType": 1, // Still a product type
        "parentId": "66b35629a7eb47d479f1d371", // Belongs to the "How many pieces?" group
        "snoozed": false
      },
      "6721daafc33216a11b4e23a4": { // Example: "6 Pieces" (Another Variant Item)
        "_id": "6721daafc33216a11b4e23a4",
        "name": "6 Pieces",
        "price": 300, // Price difference (adds 3.00 to base price)
        "plu": "VAR-2-#V300#-",
        "productType": 1,
        "parentId": "66b35629a7eb47d479f1d371",
        "snoozed": false
      },
      "66b35629a7eb47d479f1d309": { // Example: "White Rice" (Simple Product)
        "_id": "66b35629a7eb47d479f1d309",
        "name": "White Rice",
        "description": "White coloured rice",
        "price": 450,
        "plu": "RICE-01",
        "productType": 1,
        "subProducts": [ // Can still have modifier groups
             "66b35629a7eb47d479f1d345" // -> Modifier Group "Choose a sauce"
        ],
        "snoozed": false
      }
      // ... other products mapping ID to details ...
    },
    "modifierGroups": { // Dictionary mapping Deliverect Group ID to Modifier Group details
      "66b35629a7eb47d479f1d33b": { // Example: "Cooking instructions"
        "_id": "66b35629a7eb47d479f1d33b",
        "name": "Cooking instructions",
        "plu": "MOD-01", // Modifier Group PLU (optional, may exist)
        "productType": 3, // 3 = Modifier Group
        "min": 1, // Min required selections from this group
        "max": 3, // Max allowed selections from this group
        "multiMax": 1, // Max quantity of any *single* modifier within the group
        "subProducts": [ // List of Deliverect Modifier IDs belonging to this group
          "66b35629a7eb47d479f1d2fd", // -> Modifier "Rare"
          "66b35629a7eb47d479f1d2ff", // -> Modifier "Medium Rare"
          "66b35629a7eb47d479f1d33d"  // -> Modifier "Well Done"
        ],
        "snoozed": false
      },
      "66b35629a7eb47d479f1d371": { // Example: "How many pieces?" (Variant Group)
        "_id": "66b35629a7eb47d479f1d371",
        "name": "How many pieces?",
        "plu": "MG-VAR-1",
        "productType": 3,
        "isVariantGroup": true, // Indicates this group defines variants
        "min": 1,
        "max": 1,
        "subProducts": [ // List of Variant Item IDs
          "6721daafc33216a11b4e23a3", // -> "3 Pieces"
          "6721daafc33216a11b4e23a4", // -> "6 Pieces"
          "6721daafc33216a11b4e23a5"  // -> "9 Pieces"
        ],
        "snoozed": false
      }
      // ... other modifier groups ...
    },
    "modifiers": { // Dictionary mapping Deliverect Modifier ID to Modifier details
      "66b35629a7eb47d479f1d2fd": { // Example: "Rare"
        "_id": "66b35629a7eb47d479f1d2fd",
        "name": "Rare",
        "price": 0, // Price difference (adds 0.00)
        "plu": "COOK-01", // CRITICAL ID for ordering
        "productType": 2, // 2 = Modifier
        "parentId": "66b35629a7eb47d479f1d33b", // Belongs to "Cooking instructions" group
        "snoozed": false
      },
      "66b35629a7eb47d479f1d30f": { // Example: "Sate Sauce"
        "_id": "66b35629a7eb47d479f1d30f",
        "name": "Sate Sauce",
        "price": 50, // Price difference (adds 0.50)
        "plu": "SAUCE-01",
        "productType": 2,
        "parentId": "66b35629a7eb47d479f1d345", // Belongs to "Choose a sauce" group
        "snoozed": false
      }
      // ... other modifiers ...
    },
    "snoozedProducts": { // Dictionary of currently snoozed items by PLU
      // Example if "RICE-01" was snoozed:
      // "RICE-01": {
      //   "plu": "RICE-01",
      //   "name": "White Rice",
      //   "snoozeStart": "...",
      //   "snoozeEnd": "..."
      // }
    }
    // ... other top-level fields (translations, tags, etc.)
  }
]

// Derived Name Variants Mapping (Stored in DB `menu_name_variants` table)
// This structure helps the `lookup_menu_item` tool resolve user input.
// Key: lowercase user phrase, Value: { canonical_name: string, target_plu: string }
const name_variants_example = {
  "rare": { "canonical_name": "Rare", "target_plu": "COOK-01" }, // Maps to modifier
  "medium rare": { "canonical_name": "Medium Rare", "target_plu": "COOK-02" }, // Maps to modifier
  "medium": { "canonical_name": "Medium Rare", "target_plu": "COOK-02" },
  "fries": { "canonical_name": "Seasoned Fries", "target_plu": "P-FRS-L" }, // Example mapping to a specific fries type
  "salad": { "canonical_name": "Salad", "target_plu": "SI-02" }, // Maps to modifier
  "chicken tenders": { "canonical_name": "Chicken Tenders", "target_plu": "VAR-PROD-1" }, // Maps to base product
  "3 pieces": { "canonical_name": "3 Pieces", "target_plu": "VAR-1-#V0#-" }, // Maps to variant item
  "6 pieces": { "canonical_name": "6 Pieces", "target_plu": "VAR-2-#V300#-" },
  "coke": { "canonical_name": "Coca Cola", "target_plu": "DRNK-01" }, // Maps to product
  "diet coke": { "canonical_name": "Diet Coke", "target_plu": "DRNK-02" },
  // ... many more mappings derived from item/modifier names and potential synonyms ...
};


```

Appendix B: Deliverect Menu Glossary (Selected Fields)
This glossary defines key fields found within the Deliverect Menu Update payload (referenced in Appendix A). Fields marked with \* are always present.

Top Level:

menu (string): Name of the menu.
menuId (string): Internal Deliverect menu ID.
channelLinkId (string): ID for the specific store link this menu applies to.
currency (integer): Currency code (e.g., 1 might be EUR, lookup needed).
menuType (integer): 0=Delivery/Pickup, 1=Delivery, 2=Pickup, 3=Eat-in, 4=Curbside.
availabilities (array[object]): Store opening times.
dayOfWeek (integer): 1=Monday to 7=Sunday.
startTime, endTime (string): "HH:MM" format, local time.
categories (array[object]): List of menu categories.
products (object): Dictionary mapping item \_id to product details.
modifierGroups (object): Dictionary mapping group \_id to group details.
modifiers (object): Dictionary mapping modifier \_id to modifier details.
snoozedProducts (object): Dictionary mapping PLU to details for currently snoozed items.
Categories:

\_id (string): Deliverect category ID.
name (string): Category name.
subProducts (array[string]): List of item \_ids belonging to this category.
Items (Products/Modifiers/Groups - Common Fields):

\_id (string): Deliverect's internal ID for this specific item instance in the menu structure.
name (string): Item/Group/Modifier name.
description (string): Description text.
plu (string): CRITICAL unique identifier used for ordering.
price (integer): Price in cents (often 0 for modifiers/variants, representing a price difference).
productType (integer): 1=Product, 2=Modifier, 3=Modifier Group.
imageUrl (string): URL for an image.
subProducts (array[string]): For Products, lists associated Modifier Group \_ids. For Groups, lists associated Modifier or Variant Item \_ids.
snoozed (boolean): Whether the item is currently snoozed.
deliveryTax, takeawayTax, eatInTax (integer): Tax rates (e.g., 5000 = 5.000%).
parentId (string): The \_id of the group or product this item belongs to within the subProducts list.
Modifier Groups Specific:

min (integer): Minimum number of selections required from the group.
max (integer): Maximum number of selections allowed (0 = unlimited).
multiMax (integer): Maximum quantity allowed for any single modifier within the group (0 = unlimited).
isVariantGroup (boolean): True if this group defines product variants (like sizes).
Products Specific:

isCombo (boolean): True if this is a meal deal/combo product.
isVariant (boolean): True if this product's price/options are determined by selecting from a Variant Group.
Modifiers Specific:

defaultQuantity (integer): If > 0, this modifier is pre-selected (usually 1).
(Note: Many other fields exist for translations, nutritional info, tags, POS IDs etc., but the above are most critical for core ordering and display logic).

```

```

```
POS Product Configuration
Product types
When pushing products to us, you need to specify the relevant value which represents the product type used

Product Type	Integer Value	Integer Value
Product	A 'top level' item on a menu (can also be grouped within a modifier group or bundle)	1
Modifier	Options selectable when ordering a product, typically modifications of the product	2
Modifier Group	A grouping of modifiers (can also group products)	3
Bundle	Can only contain products which are offered as part of a 'Meal Deal' and which Deliverect will set to zero value. Exception to this is where ## Overloads are set, see example 'Bundles (Product price overloads)' on the right hand side.	4
PLU
The PLU is typically something that's easier for the customer to use, and it should be the same across all locations for the same product. The PLU is what will be used for mapping orders coming from the channels to your integrated POS.

Price
Price is stored as an int with 2 decimal digits, for example, 5 euros is stored as 500.

Price Levels
Products will have a base price field, where 'Price Levels' are optional variations to set for this price, e.g. apply a different price per channel or delivery type.

See the snippet below of a product set with a priceLevels object where the unique identifier (the posId) is the key, set along with a price integer value.

The library of priceLevels would then be defined giving a descriptive name to each posId used

After syncing products with priceLevels , they can be selected in the channel link settings. When previewing or pushing menus for these channel links, the selected pricelevel will be applied. See guide here for further information on testing this function.

Ensure the same "posId" values are used across different locations in the same account

📘 When no data is available on a product for a selected price level, the base price is applied.

Example
After defining a Burger price level on your burgers, sync products and apply the price level to a single (or any) channel to run the BurgerDeal on.

Example product

{
    "name": "Burger",
    "price": 1000,
    "priceLevels": {
        "channel_A": 1000,
        "channel_B":  900,
        "channel_C":  500
    }
}
Example price level

{
    "name":  "Channel Awesome",
    "posId": "channel_A"
}
🚧
Null values

To prevent potential failures in product synchronization, please avoid sending null values. Instead, if the data type allows, utilize empty strings. Additionally, when dealing with prices, ensure that only integers are sent.

Tax
It is important to specify the sales tax rate which applies to any item. The sales tax which applies can be differentiated between the order types of;

Delivery (deliveryTax)
Takeaway (takeawayTax)
Eat-in (eatInTax)
Tax rates should be stored as an int with 3 decimal digits e.g. 5% would be 5000

It's acceptable to have a 0% tax

TAX

{
  "productType": 1,
  "plu": "GB-02",
  "name": "Ginger Beer",
...
  "deliveryTax": 5000,
  "takeawayTax": 5000,
  "eatInTax": 0,
Bag Fee
In certain regions, ordering platforms are required to process a specific payment for a bag fee. Deliverect will by default included this fee within the serviceCharge. It is also an option for the POS to sync a bag fee product with a unique PLU, this would need manually set per channel but will ensure the POS receives the bag fee as seperate item in the orders payload.

See guide on setting a bag fee PLU here

Overloads
Certain product structures can contain "overloads" which are effectively like surcharges which can be applied dependant on which grouping the product is offered in.

In the example below and also in samples 4 and 5 in the Insert/update products page, you can see both a product and modifier price being set this way.

The "overloads" array contains "scopes" which specify the group(s) in which either a"bundlePrice"(if a bundle group) or "price"(if not a bundle group) can be set differently.

In the first example below, an Avocado with base price 50, can be set to 0 if included in a group "FREE-TOP" and set to 100 if set in a group "XTRA-TOP"

The second example shows the same format for an Ice Cream with a base price 500, which can be set to 0 if included in a group "FREE-DESS" and 450 if set in a group "ADD-ON"it used the bundlePrice attribute as the group is not a modifier group (type:3) but bundle (type:4)

Overload in Modifier Group
Overload in Bundle

{
    "productType": 2,
    "plu": "AVO",
    "price": 50,
    "name": "Avocado",
    "overloads": [
        {
            "scopes": [
               "FREE-TOP"
            ],
            "price": 0
        },
        {
            "scopes": [
               "XTRA-TOP"
            ],
            "price": 100
        }
    ]
}
Images
The image URL you provide here is cached and put behind a CDN. Images are cached on access for 24 hours. Channels will download the images and also cache them. Depending on the channel, images can/will be resized. Deliverect supports images of up to 16.8 megapixels in size.

Categories
A category is a way to organise products into a section to be referenced when building a menu. Products can be in one or more categories denoted by an array of posCategoryIds. It's important to have at least one category per product.

Overrides
Customers are able to overwrite certain details of products within the menu builder in Deliverect, including;

Names
Descriptions
Prices
Images
*Everything that is not overwritten in Deliverect can be updated via this endpoint

Modifier Groups
The first example below represents a simple Product (productType:1) with three modifier groups attached (productType:3) where each modifier group contains an amount of modifiers (productType:2)

Typical use case: This structure would support standard modifications to a product e.g. required modifiers of 'Rare', 'Medium' or 'Well Done' would be applied to a Steak product.



Product with Modifier Group (+modifiers)

{

  "products": [
    {
      "productType": 1,
      "plu": "STK-01",
      "price": 1500,
      "name": "Delicious Steak Frites",
      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000,
      "posCategoryIds": [
        "STK"
      ],

      "description": "Delicious Steak Frites",
      "subProducts": [
        "MOD"

      ]
    },

    {
      "productType": 3,
      "plu": "MOD",
      "name": "Add a side",
      "imageUrl": "",
      "description": "Pizza made for cheese fanatics",

      "subProducts": [
        "SI-01",
        "SI-02",
        "SI-03"
      ],
      "min": 0,
      "max": 0,
      "multiMax": 3
    },

    {
      "productType": 2,
      "plu": "SI-01",
      "price": 0,
      "name": "Fries",
      "posCategoryIds": [
        "SD"
      ],
      "imageUrl": "",
      "description": "Fries",
      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    },
    {
      "productType": 2,
      "plu": "SI-02",
      "price": 200,
      "name": "Salad",
      "kitchenName": "",
      "posCategoryIds": [
        "SD"
      ],
      "imageUrl": "",
      "description": "Salad",

      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    },
    {
      "productType": 2,
      "plu": "SI-03",
      "price": 100,
      "name": "Mashed Potato",
      "kitchenName": "Mash",
      "posProductId": "POS-ID-014",
      "posCategoryIds": [
        "SD"
      ],
      "imageUrl": "",
      "description": "Mashed Potato",

      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    }
  ],
  "categories": [
    {
      "name": "Steaks",
      "posCategoryId": "STK"
    },
    {
      "name": "Sides",
      "posCategoryId": "SD"
    }
  ]
}

This same structure can also be applied to group together products (productType:1) within modifier groups (productType:3)

Typical use case: This structure is often applied as an "Upsell" where additional optional priced items are offered alongside a product.


Product with Modifier group (+products)

    {
      "productType": 1,
      "plu": "STK-01",
      "price": 1500,
      "name": "Delicious Steak Frites",
      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000,
      "posCategoryIds": [
        "STK"
      ],

      "description": "Delicious Steak Frites",
      "subProducts": [
        "Drink"

      ]
    },

    {
      "productType": 3,
      "plu": "Drink",
      "name": "Add a Drink",
      "imageUrl": "",
      "description": "Select a drink with your meal",

      "subProducts": [
        "DR-01",
        "DR-02",
        "DR-03"
      ],
      "min": 0,
      "max": 0,
      "multiMax": 3
    },

    {
      "productType": 1,
      "plu": "DR-01",
      "price": 0,
      "name": "Coke",
      "posCategoryIds": [
        "DR"
      ],
      "imageUrl": "",
      "description": "Fries",
      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    },
    {
      "productType": 1,
      "plu": "DR-02",
      "price": 200,
      "name": "Ginger Beer",

      "posCategoryIds": [
        "DR"
      ],
      "imageUrl": "",
      "description": "Salad",

      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    },
    {
      "productType": 1,
      "plu": "DR-03",
      "price": 100,
      "name": "Fanta",

      "posProductId": "POS-ID-014",
      "posCategoryIds": [
        "DR"
      ],
      "imageUrl": "",
      "description": "Fanta ",

      "deliveryTax": 9000,
      "takeawayTax": 9000,
      "eatInTax": 9000
    }
  ],
  "categories": [
    {
      "name": "Steaks",
      "posCategoryId": "STK"
    },
    {
      "name": "Drinks",
      "posCategoryId": "DR"
    }
  ]
}

Item Rules
Individual items can have rules set against them to control how they can be ordered online

Rule	Purpose	Type
multiMax	To restrict the number of products that can be sold within one order e.g. pharmaceuticals. You can achieve this by adding the attribute "multiMax" e.g. "multiMax": 1, prevents more than one of the items being added to the basket.	Integer
defaultQuantity	This attribute makes a modifier preselected by default, where a value of 1 is equivalent to a pre-selected item. Most channels can handle a pre-selection, but not with a pre-selected quantity of more than 1	Integer
Item Group Rules
Both Modifier Groups and Bundles allow certain ordering "rules" to be applied as follows;

Rule	Purpose	Type
min	Setting a minimum value to a group of options e.g. 0would be equivalent to 'optional'and1or more would be 'required'	Integer
max	Setting a maximum value limits how many items in a group can be ordered	Integer
multiMax	Setting the attribute multiMax allows control over the maximum quantity of any single item in a group.

A value of '2' for example, means that each item in a group can be selected at most 2 times. The selection of a single item will still be limited by the overall max value allowed in a group	Integer
Meal Deals
In the payload examples on this page, shown on the right hand side, various product structures are depicted including combos and meal deals.

These examples use the structure below, where products are linked together using the subProducts field.

Meal Deal / Combo Structure
A meal deal or combo will typically have a set price, where a grouping of a 'Bundle' can contain products which normally have a price, but as part of a bundle will be zero-priced.

The diagram below shows that it is possible to contain the zero-priced 'Bundle' options as well as 'Modifier Groups' containing priced items.

❗️
Important Attribute for Combos/Meal Deals

Please ensure the attribute "isCombo": true is set on the main product "productType": 1 and linked to a Bundle groups"productType": 4, as certain channels need this flag and Bundle groups to display these options correctly

Bundles cannot be nested under a sub-product and must be at the top level of options.


The structure to form bundles could be as follows:

Combo product Type:1
Bundle Type:4
Product Type:1
Modifier group Type:3
Modifier Type:2
Nested Modifiers
A product configuration can include a sub-group of options to be selected. These options themselves can also contain their own sub-groups, this is reffered to as 'Nested Modifiers'.


Meal Deal with 'Upsell'
In the Meal Deal with upsell (example 3) we have a modifier group in addition to the bundles. This allows for Fries to be ordered which are not included as part of the deal and the customer will be charged accordingly. This is referred to as an 'upsell', which can be modifier groups containing products or modifiers.

It is also possible to construct combo products as follows:

Combo product Type:1
Modifier group Type:3
Modifier Type:2
Modifier group Type:3
Modifier Type:2
Click here to see examples of how orders with these meal deal examples are sent to your POS in an order.

Variants
A variant in a menu allows customers to choose from different versions of a product, such as pizza sizes or beverage flavors. The variant product displays the lowest price, then allows the customer to choose from a list of variations of the product by showing additional costs for selecting larger sizes, ensuring clear and transparent pricing for customization.

Variant

"products": [
    {
      "productType": 1,
      "plu": "VAR-PROD-1",
      "price": 0,
     ...
      "isVariant": true,
    ...
      "subProducts": [
        "MG-VAR-1"
      ]
    },
{
      "productType": 3,
      "plu": "MG-VAR-1",
      "name": "How many pieces?",
      "posProductId": "POS-002",
      "isVariantGroup": true,
      "subProducts": [
        "VAR-1",
        "VAR-2",
        "VAR-3"
      ]
Follow the "Example 6 - Variant products" on the insert/update products endpoint.

Chicken tenders: €8

3 pieces: + €0
6 pieces: + €3
9 pieces: + €5.50


For example, Chicken Tenders start at €8. If a customer selects 3 pieces, the price remains €8. If they choose 6 pieces, an additional €3 is added, making the total €11. For 9 pieces, an extra €5.50 is added, bringing the total to €13.50.


Auto Apply
There can be a use case where products ordered online should be received with a pre-defined set of sub products applied. This is not the same as items being pre-selected in the menu interface via defaultQuantity, but is a mechanism for specific items to be auto-applied (by Deliverect) following a completed order.

This is shown in the example below, where the Parsley Garnish and Melted Butter are within a modifier group 'Garnishes' which is set to apply these items automatically when the Steak Frites is ordered.

Note that "defaultQuantity": 3 is shown below and defines how many of the item should be auto-applied to the order. The "sortOrder" attribute allows a 'stepped' order of the auto-applied items to appear, where 0 is the first item to be listed.

'NB: Neither the channel platform or end-consumer will see the auto-applied items, and as such there can be no price associated with them. If de-selection of pre-set items or charging for them is a requirement,"defaultQuantity" can be used without "autoApply" (See 'Item Rules').

Auto Apply

"autoApply": [
    {
        "plu": "PR1"
    },
    {
        "plu": "PR2"
    }
],
Set default quantity of auto-applied item

{
    "productType": 2,
    "plu": "PR1",
    "price": 0,
    "name": "Parsley",
    "posProductId": "PA_POS-0023",
    "posCategoryIds": "",
    "imageUrl": "",
    "description": "",
    "deliveryTax": 0,
    "takeawayTax": 0,
    "subProducts": [],
    "defaultQuantity": 3,
    "sortOrder": 1
}
Translations
Translations are supported for all product types and both the name and description can be set with a translated value. Additionally, category names and descriptions can be translated. can be provided in the JSON. A base name is always required but translations are optional.

See examples of the nested object for translations below, where the property key is the language tag and the value is the translation itself.

See all language tags supported via the link below;

▶ Language Tags
Translation Examples
Product Translation
Category Translation

{
    "productType": 1,
    "plu": "MEAT-02",
    "price": 200,
    "name": "Chicken",
    "nameTranslations": {
        "ar": "دجاج",
        "en": "Chicken",
        "es": "Pollo",
        "nl": "Kip"
    },
    "description": "Grilled chicken",
    "descriptionTranslations": {
        "ar": "دجاج مشوي",
        "en": "Grilled chicken.",
        "es": "Pollo asado.",
        "nl": "Gegrilde kip."
    }
}
Product visibility
A product can be marked as invisible (disabled) by setting visible property to false. After this action the product will be hidden all menus where it was used and will not be pushed to channels until it marked as visible again.

JSON

{
    "productType": 1,
    "plu": "SI-01",
    "price": 100,
    "name": "Fries",
    "visible": false
}
Product tags: consumable types and allergens
A product can have one or more product tags. These are are contained inside productTags

In below example snippet, 104 and 109 are values representing 'eggs' and 'peanuts'

JSON

{
  "productType": 1,
  "plu": "P-SATE",
  "price": 450,
  "name": "Chicken Sate",
...
  "productTags": [
    104,
    110
  ]
},
See link below for a complete list of tags available;

▶ Product Tags
Nutritional Information and Supplemental Info
A product can be set with nutritional and supplemental information e.g. packaging, additives etc and certain attributes shown in the link below will be legally required in some regions;

▶ Nutritional & Supplemental Info
Calories
Calories can be sent as in the example shown below;

Parameter	Meaning
calories	This is the base calorie amount, where a maximum calories is set, this should be interpreted as the 'minimum'
caloriesRangeHigh	The maximum calorie amount of an item
JSON

"products": [
          {
               "productType": 1,
               "plu": "PR03",
               "price": 900,
               "name": "Cheese Lovers Pizza",
               ...
               "calories": 500,
               "caloriesRangeHigh": 750
               },
               ...
               ]
          },
```

``
Payments and Additional Charges
Payments
Depending on the method of payment, the relevant payment types should be sent with one of two following values (as an integer)

Further details on processing additional payment parameters below;

Payment Type Integer Value
credit card online 0
cash 1
Payment Type

"payment": {
"amount": 1455,
"type": 0,
"due": 0,
"rebate": 0,
"commissionType": ""
},
Tax Exclusive Orders
For customers in tax exclusive regions, you should ensure you handle tax accordingly, see details below;

▶ Processing Tax Exclusive Orders
Paid/Unpaid Orders
In some ordering platforms, users can checkout without processing a payment. A typical scenario would be for pickup orders where cash will be paid on collection. If allowing for this option at checkout, it is important to set the flag "orderIsAlreadyPaid": false,

Where payment is processed online during checkout, then set this as "orderIsAlreadyPaid": true,

📘
Payment amount

Note, you should always pass the payment amount, whether the order is already paid or not.

📘
Payment format

Payment amounts should be sent as an integer with 2 decimal digits, for example, 5 euros would be sent as 500.

Discounts
Ordering platforms may offer multiple forms of discount e.g. special offers on selected items, % discounts etc

We can support one single overall order discount only and it should be specified as a minus value e.g. "discountTotal": -100

This should only be applied where the restaurant is absorbing the cost of the discount.

The paid 'amount' should factor in any discount deducted from the total payment.

Additionally, you can further specify information regarding the discount applied, as an array within the order payload.

Discounts Array

"discounts": [
{
"type": "order_flat_off",
"provider": "restaurant",
"name": "FLATOFF",
"channelDiscountCode": "",
"referenceId": 1,
"value": 800,
"amount": 800,
"amountRestaurant": 400,
"amountChannel": 400
}
],
You can learn more about what is the meaning of each parameter in the table below:

Parameter Meaning Data Tye
type Mapped channel discount type from the list of Discount Types in Deliverect. string
provider The issuer of the discount i.e. the one who bears the discounted amount. string
name The name was given to the discount. string
channelDiscountCode The unique discount code used by the channel string
referenceId A unique number assigned to the discount and used to reference the discount on individual items on the order. integer
value It is the flat amount of money or percentage covered by the discount which is stored with precision 2, so $1.50 -> 150,# 25.1% -> 2510 integer
amount Actual amount discounted e.g. For 10% off on $50 bill, the value will be 1000 and amount will be 500. integer
amountRestaurant The amount of the restaurant's contribution to the discount integer
amountChannel The amount of the channel's contribution to the discount integer
Rebate
A rebate refers to a discount where the cost is covered by the channel, not the restaurant. It is essential for restaurants to clearly distinguish these rebates from discounts they absorb within their POS system.

When a rebate is applied, the full payment amount, prior to the rebate deduction, should be specified, as this is the amount the restaurant will receive.

Payment Type - Credit Card Online

"payment": {
"amount": 400,
"type": 3,
"due": 0,
"rebate": 100,
"commissionType": ""
},
Commission Type
This relates to the type of commission charged by the channel for its services.

Each type will correspond to an agreed percentage of the order value taken as commission but is information provided by some channels only.

Tips
To send a tip through with an order, there are two possible parameters allowing a channel to distinguish between the intended recipient of tips. i.e

If a tip is intended for the restaurant;

"tip": 500,.

If intended for the driver;

"driverTip": 500,.

Please be aware that not all POS partners will handle this addition to an order, in which case we have a toggle setting to not include these.

Bag Fee
In certain regions it is mandatory to apply a charge against the packaging used. For this, we have the attribute "bagFee"

When included within an order it will be processed accordingly and will appear as a line item on the integrated POS.

A bag fee of $1.20 would then be sent as the below example;

"bagFee": 120,
``
