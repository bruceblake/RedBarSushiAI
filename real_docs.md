# Project Documentation: AI Restaurant Phone Agent (Condensed Core w/ Full Deliverect API)

**Version:** 1.1-full-deliverect
**Date:** 2025-04-18
**Purpose:** Provide essential technical details and complete Deliverect API specifications for AI assistants to understand and modify the AI Restaurant Phone Agent codebase. This system handles inbound calls, takes orders via conversational AI, integrates with Deliverect for POS submission, and sends SMS updates.
**Target Audience:** AI Development Assistants (e.g., Gemini, Claude, GPT-4).
**Note:** Core sections are condensed. Deliverect API section is comprehensive based on provided input. Appendix A provides detailed menu structure examples.

---

## 1. Project Overview

- **Goal:** Automate phone ordering using conversational AI, reducing staff load and improving accuracy.
- **Core Technologies:**
  - **AI:** OpenAI Agents API (Assistants API)
  - **Telephony/SMS:** Twilio API
  - **Order Injection:** Deliverect API
  - **Backend:** Python (Flask/FastAPI/Django TBD) on Render
  - **Tasks:** Celery
  - **DB:** PostgreSQL (Render)
  - **Cache/State:** Redis (Render)

---

## 2. Core Features Summary

- Handle inbound Twilio calls.
- Conversational order taking & menu queries using OpenAI Agents API.
- Access restaurant/menu info from Postgres.
- Maintain conversation/order state in Redis.
- Place orders via Deliverect API using PLUs.
- Send order status SMS updates via Twilio (triggered by Deliverect webhooks/Celery).
- Handle Deliverect webhooks for menu sync, store status (busy/open), and item availability (snooze).

---

## 3. System Architecture (API-Driven Agent w/ Background Processing)

1.  **Twilio:** Handles calls (PSTN), STT/TTS (via TwiML), SMS. Sends webhooks to Render backend.
2.  **Render Web Service (Python Backend):** Central orchestrator.
    - Hosts HTTP endpoints for Twilio & Deliverect webhooks.
    - Manages conversation state (Redis, keyed by `CallSid`).
    - Interacts with OpenAI Agents API (sending user input, handling tool calls).
    - Implements Python **Tools (Functions)** callable by the OpenAI Agent.
    * Generates TwiML for Twilio responses.
    * Queries/Writes Postgres DB (menu, orders).
    * Calls Deliverect API (order placement).
    * Enqueues Celery tasks.
3.  **OpenAI Agents API:** NLU, dialogue management, decision-making, tool triggering.
4.  **PostgreSQL:** Persistent storage (menu, orders, restaurant info). **PLU** is critical identifier. See Appendix A for menu structure details.
5.  **Redis:** Stores active conversation state (cart, context), Celery broker/backend.
6.  **Celery Workers:** Execute async tasks (SMS sending, polling).
7.  **Deliverect API:** External service for POS order injection & menu/status sync. Called by Render backend; sends webhooks to Render backend.

**Conceptual Flow:** Call -> Twilio -> Render Backend <-> OpenAI Agent (using Tools) -> Render Backend -> Twilio (TwiML). Order Placement: Agent Tool -> Render Backend -> Deliverect API. Status: Deliverect Webhook -> Render Backend -> Celery -> Twilio SMS.

---

## 4. Technology Stack Summary

- **Cloud:** Render.io (Web Service, Background Worker, Postgres, Redis)
- **Language:** Python 3.10+ (TBD Framework: Flask/FastAPI/Django)
- **Tasks:** Celery
- **DB ORM:** SQLAlchemy/Django ORM (TBD)
- **APIs:** Twilio, OpenAI Agents, Deliverect

---

## 5. Data Storage Essentials

**5.1. PostgreSQL Schema Highlights**

(Reflects structure seen in Appendix A)

- `restaurants`: Basic info.
- `menu_categories`: `id`, `deliverect_category_id` (UNIQUE, e.g., "67209bfb174a0e5384d4db4f"), `name`, `description`.
- `menu_items`: `id`, `category_id` (FK), `name`, `description`, `price`, **`plu`** (UNIQUE, CRITICAL), `deliverect_item_id` (UNIQUE, e.g., "6721daafc33216a11b4e239d"), `is_available`, `is_combo`, `is_variant`, `image_url`, `snoozed_until`.
- `modifiers`: `id`, `modifier_group_id` (FK), `name`, `price_change`, **`plu`** (UNIQUE, CRITICAL), `deliverect_modifier_id` (UNIQUE, e.g., "67209bb4174a0e5384d4d9fd"), `is_available`, `snoozed_until`.
- `modifier_groups`: `id`, `deliverect_group_id` (UNIQUE, e.g., "67209bb4174a0e5384d4d9fb"), `name`, `min_selection`, `max_selection`, `multiMax`, `plu` (Group PLU), `is_variant_group`.
- `item_modifier_groups`: Links `menu_items` to `modifier_groups` (M2M).
- `group_modifiers`: Links `modifier_groups` to `modifiers` (M2M, representing `subProducts` in groups).
- `orders`: `id`, **`deliverect_channel_order_id`** (UNIQUE, CRITICAL), `customer_phone`, `order_type`, `status`, `total_price`, `placed_at`, `estimated_time`, `delivery_address` (JSON/structured), `notes`.
- `order_items`: Links `orders` to `menu_items` via `menu_item_plu`, stores quantity.
- `order_item_modifiers`: Links `order_items` to `modifiers` via `modifier_plu`.
- `menu_name_variants`: `variant_phrase` (lowercase), `canonical_name`, `target_plu` (FK to item/modifier PLU).

**5.2. Redis Usage**

- **Conversation State:** Key: Twilio `CallSid`. Stores JSON/Hash: current cart (items/modifiers by PLU), user info, conversation context. TTL ~1-2 hours.
- **Celery Broker/Backend.**
- **Optional Caching.**

---

## 6. API Integrations Essentials (Excluding Deliverect)

**6.1. Twilio API**

- **Purpose:** Voice I/O (STT/TTS via TwiML), SMS.
- **Interaction:** Inbound webhooks (`/webhook/voice`) from Twilio; Backend responds with TwiML. Outbound SMS API calls from Celery worker.
- **Auth:** Account SID/Auth Token (Env Vars). Recommend webhook signature validation.
- **Key ID:** `CallSid`.
- **Relevant Docs:** See Twilio Documentation.

**6.2. OpenAI Agents API (Assistants API)**

- **Purpose:** Conversation logic, Tool/Function Calling.
- **Interaction:** Backend makes REST API calls (Create/Run Thread/Assistant, Add Message, Submit Tool Outputs). Handles `requires_action` status to execute local Python tools.
- **Auth:** OpenAI API Key (Env Var).
- **Key Concepts:** Assistant, Thread, Message, Run, Tool Calling.
- **Required Tools (Python functions implemented in Render backend):**
  - `lookup_menu_item(item_name: str)`: Resolves `item_name` using `menu_name_variants` DB table (derived from Appendix A `name_variants`), returns item details (name, desc, price, PLU).
  - `get_restaurant_info(query: str)`: Returns text info (hours, etc.) from DB.
  - `add_item_to_cart(plu: str, quantity: int, modifiers: List[str] = None)`: Updates cart in Redis state (uses PLUs). Returns status/summary. Modifiers list contains PLUs.
  - `get_current_cart()`: Returns current cart JSON from Redis state.
  - `place_order(customer_details: dict, delivery_details: dict = None, order_type: int)`: Retrieves cart from Redis, calls Deliverect Create Order API using PLUs. Returns { success: bool, channelOrderId: str | None, message: str }.
  - _(Other tools like get_categories, remove_item, clear_cart as needed)_
- **Relevant Docs:** See OpenAI Assistants API Documentation.

---

## 6.3. Deliverect API (Full Details)

- **Base URL (Staging):** `https://api.staging.deliverect.com`
- **Authentication:** Likely via API keys or OAuth tokens associated with the `channelName` (Scope). Store credentials securely as environment variables.
- **Key Identifiers:** `channelName` (Scope), `channelLinkId` (Specific store instance), `channelOrderId` (Unique order ID generated by _this_ application), `_id` (Deliverect's internal IDs), `plu` (Product/Modifier ID from menu data - see Appendix A).

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
- **Purpose:** Called by Deliverect when a new store link is registered (`register`), activated (`active`), or deactivated (`inactive`).
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
- **Purpose:** Receives the full menu structure or updates from Deliverect when a customer publishes changes. See **Appendix A** for detailed structure examples and the **Menu Glossary** below for field definitions.
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
- **Action:** Parse the menu structure (categories, items with PLUs, modifiers with PLUs, prices, availability, subProducts links, etc.). Update the PostgreSQL database accordingly (tables like `menu_items`, `modifiers`, `modifier_groups`, `menu_name_variants`). If async, store the `callback` URL and call the "Menu Update Callback" API endpoint once processing is complete.
- **Success Response Code:** `200 OK`.
- **Error Response Code:** `400`.

#### Order Status Update

- **Method:** `POST`
- **Your Endpoint URL:** `/webhook/deliverect/order_status`
- **Purpose:** Receives status changes for orders previously submitted via the Create Order API. **This is the primary way to know if an order was accepted by the POS and its subsequent progress.**
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
- **Purpose:** Notifies when specific items (identified by PLU) should be marked as temporarily unavailable (snoozed) or available again (unsnoozed). Triggered only for items in active/published menus.
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
- **Purpose:** Notifies when the restaurant enables/disables busy mode _from their POS/Deliverect_.
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
- **Purpose:** Notifies of an updated estimated pickup/preparation time from the POS for a specific order.
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

## 7. Internal Component Summary

- **Render Web Service (Python):** Handles webhooks (Twilio, Deliverect), orchestrates OpenAI API calls, implements Agent Tools, manages state (Redis), calls Deliverect API, queues Celery tasks.
- **Render Background Worker (Celery):** Executes async tasks: `send_sms_notification`, `process_deliverect_menu_update`, etc.

---

## 8. Key Workflow Summaries

- **Conversation Turn:** Twilio webhook -> Get state (Redis) -> Call OpenAI Agent -> Handle response (TwiML text or execute Tool) -> Update state (Redis) -> Respond TwiML to Twilio. Tool execution involves local Python function (DB/Redis/Deliverect interaction using PLUs/variants) and submitting result back to Agent.
- **Order Placement:** User confirms -> Agent calls `place_order` tool -> Backend function retrieves cart (Redis), generates `channelOrderId`, calls Deliverect `/order` API with PLUs -> On success, saves order (Postgres), clears cart (Redis), queues SMS task (Celery), returns success to Agent -> Agent confirms to user via TwiML.
- **Status Update:** Deliverect `/order_status` webhook received -> Backend finds order by `channelOrderId` (Postgres), updates status -> Queues SMS task (Celery) if needed -> Responds 200 OK to Deliverect.

---

## 9. Configuration Management

- **Environment Variables:** Used exclusively for secrets (API keys, DB URL) and settings. Render manages these.
- **Examples:** `DATABASE_URL`, `REDIS_URL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID`, `DELIVERECT_CHANNEL_NAME`, `DELIVERECT_API_KEY`.

---

## 10. Testing Strategy Summary

- **Staging Environment:** Essential on Render with test keys/DB/Redis.
- **Unit Tests:** Test functions/classes in isolation (mock dependencies).
- **Integration Tests:** Test component interactions within staging (e.g., webhook -> DB write).
- **E2E/Simulation:** Simulate conversations against staging env. Verify flow, tool execution (using PLUs/variants), mocked/real Deliverect interaction, state changes.

---

## 11. Future Considerations / Roadmap (Placeholder)

- Direct payment handling.
- Multi-location support.
- Advanced ambiguity handling.
- Delivery fleet integration.
- Web UI/Analytics.

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
Appendix B: Deliverect Menu Glossary (Selected Fields)
This glossary defines key fields found within the Deliverect Menu Update payload (referenced in Appendix A). Fields marked with * are always present.

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
products (object): Dictionary mapping item _id to product details.
modifierGroups (object): Dictionary mapping group _id to group details.
modifiers (object): Dictionary mapping modifier _id to modifier details.
snoozedProducts (object): Dictionary mapping PLU to details for currently snoozed items.
Categories:

_id (string): Deliverect category ID.
name (string): Category name.
subProducts (array[string]): List of item _ids belonging to this category.
Items (Products/Modifiers/Groups - Common Fields):

_id (string): Deliverect's internal ID for this specific item instance in the menu structure.
name (string): Item/Group/Modifier name.
description (string): Description text.
plu (string): CRITICAL unique identifier used for ordering.
price (integer): Price in cents (often 0 for modifiers/variants, representing a price difference).
productType (integer): 1=Product, 2=Modifier, 3=Modifier Group.
imageUrl (string): URL for an image.
subProducts (array[string]): For Products, lists associated Modifier Group _ids. For Groups, lists associated Modifier or Variant Item _ids.
snoozed (boolean): Whether the item is currently snoozed.
deliveryTax, takeawayTax, eatInTax (integer): Tax rates (e.g., 5000 = 5.000%).
parentId (string): The _id of the group or product this item belongs to within the subProducts list.
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
```
