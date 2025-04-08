# SMS Functionality Documentation

This document provides comprehensive information about the SMS functionality in the Red Bar Sushi AI system, including recent enhancements, configuration details, and testing procedures.

## Recent Updates

### 1. Phone Number Update

The system has been updated to use the correct restaurant phone number:
- **Old number (removed)**: (703) 297-2632
- **New number**: (833) 324-7207

This update was made across all relevant files:
- `tasks.py`: Updated `OWNER_PHONE_NUMBER` constant
- `app/routes/order.py`: Updated all SMS message templates and response text
- All references in status updates and customer communications

### 2. Help Command Fix

The SMS "help" command detection was improved to ensure it works consistently:
- Added more robust keyword matching to detect variations of the help command
- Added detailed debug logging to trace command detection
- Fixed pattern matching to ensure commands are properly recognized

### 3. Order Quantity Display

Improved the display of order quantities to use a consistent format:
- Updated `build_order_description` in `app/utils/order_utils.py` to use "×" symbol for quantities
- Added item quantity formatting in `tasks.py` for confirmation messages
- Improved status updates to display quantities properly
- Ensures multiple quantities of the same item show as "3× Item" instead of "3 Item"

## Quick Troubleshooting Tips

If SMS commands are not working:

1. Run the `test_sms_command.py` script to verify local command handling:
   ```bash
   python test_sms_command.py
   ```

2. Make sure your Twilio webhook URL is properly configured:
   * In Twilio console, go to Phone Numbers → Manage → Active Numbers
   * Select your Twilio phone number
   * Under Messaging, set the webhook URL to: `https://your-domain.com/sms`

3. Verify your environment variables are set properly:
   * `TWILIO_ACCOUNT_SID`: Your Twilio account SID
   * `TWILIO_AUTH_TOKEN`: Your Twilio authentication token  
   * `TWILIO_NUMBER`: Your Twilio phone number
   * `BASE_URL`: Your application's base URL

## Recent Enhancements

### 1. Improved SMS Message Formatting
- Added emojis and clear structure to all SMS messages
- Enhanced order confirmation messages with pickup time estimates and payment links
- Created visually distinguishable sections in SMS messages
- Added helpful information like restaurant location and contact details
- Implemented detailed status update messages with relevant action items

### 2. Enhanced SMS Command Handling
- Expanded command recognition with natural language understanding
- Added new commands for restaurant information, specials, and help
- Implemented flexible keyword matching for each command type
- Added dynamic content (e.g., day-specific specials based on current day)
- Created comprehensive response templates for each command type

### 3. Robust SMS Status Tracking
- Added SMS tracking fields to the Order model:
  - `sms_sid`: Stores the Twilio message SID for tracking
  - `sms_status`: Current status of the message (sent, delivered, failed, etc.)
  - `sms_error_code`: Error code if delivery failed
  - `sms_error_message`: Detailed error message if delivery failed
- Implemented a status callback endpoint that records message delivery status
- Added fallback mechanisms to find orders when SID matching fails

### 4. Improved Phone Number Handling
- Multiple formatting approaches for greater reliability
- E.164 standard compliance (e.g., "+12345678901")
- Better error handling and logging
- Fallback mechanisms for non-standard inputs

### 5. Comprehensive Testing Tools
- Created enhanced diagnostic tools in `test_sms.py`
- Added local testing capability without sending actual messages
- Implemented order status flow simulation for testing
- Added webhook configuration verification

## SMS Commands

The system now supports the following SMS commands:

| Command | Aliases | Description |
|---------|---------|-------------|
| status | stat, check, order | Check the status of your most recent order |
| help | command, info, option | View available SMS commands |
| menu | food, eat, dish, price | See popular menu items |
| hours | time, open, close | View restaurant hours |
| location | address, where, map, direction | Get address and directions |
| contact | phone, call, reach | Get contact information |
| specials | deal, offer, discount, promotion | View today's specials |

## SMS Message Types

### Order Confirmation
- Sent after a successful order is placed
- Includes order items, total amount, and estimated pickup time
- Provides payment link (via Stripe)
- Includes restaurant location and contact information
- Reminds customer how to check order status

Example:
```
🍣 RED BAR SUSHI ORDER CONFIRMATION 🍣

Thank you for ordering!

📋 YOUR ORDER:
- 1x Spicy Tuna Roll ($8.99)
- 1x California Roll ($6.99)
Your total is $15.98

🆔 Order ID: test-12345

⏱️ Estimated pickup time: 25 minutes (around 6:30 PM)
🕒 Order placed at: 6:05 PM

📍 Red Bar Sushi
📞 (555) 123-4567

💳 PAY NOW: https://example.com/pay
Securely pay online with credit card

📱 SMS COMMANDS:
• Reply 'status' to check your order status
• Reply 'help' for more options
```

### Status Update
- Sent when order status changes or when customer requests status
- Shows current order status with user-friendly explanation
- Provides relevant info based on status (e.g., pickup instructions when ready)
- Includes original order summary for reference

Example:
```
🍣 RED BAR SUSHI STATUS UPDATE 🍣

🆔 Order #test-1234
📍 Red Bar Sushi
🕒 Placed at: 6:05 PM

- 1x Spicy Tuna Roll ($8.99)
- 1x California Roll ($6.99)
Your total is $15.98

📋 CURRENT STATUS: PREPARING
Your order is now being prepared in the kitchen

⏱️ Estimated to be ready in: 10 minutes

📱 Reply 'status' for the latest updates
📱 Reply 'help' for more options
```

## Configuration

### Twilio Setup
To configure SMS functionality, the following environment variables are required:
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio authentication token
- `TWILIO_NUMBER`: Your Twilio phone number for sending SMS
- `BASE_URL`: Your application's base URL for callbacks

### Webhook Configuration
The system uses the following webhook endpoints:
- `/sms`: Handles incoming SMS messages
- `/sms_status_callback`: Receives delivery status updates

Configure your Twilio phone number to use these webhooks:
1. In the Twilio console, go to Phone Numbers > Manage > Active Numbers
2. Select your phone number
3. Under Messaging, set:
   - A MESSAGE COMES IN: `https://your-base-url.com/sms`
   - PRIMARY HANDLER FAILS: `https://your-base-url.com/webhook-test`

## Testing Tools

The enhanced `test_sms.py` script provides multiple testing functions:

```bash
# Send a test SMS
python test_sms.py send +1XXXXXXXXXX [basic|order|status|all_commands]

# Test SMS commands locally (no actual SMS sent)
python test_sms.py test status
python test_sms.py test menu
python test_sms.py test help

# Simulate an order going through all status changes
python test_sms.py flow +1XXXXXXXXXX

# Check Twilio configuration
python test_sms.py check

# Test webhook configuration
python test_sms.py webhook

# Display help information
python test_sms.py help
```

## Database Migration

To add SMS tracking columns to your database:

```bash
python migrate_sms_tracking.py
```

This creates the following columns in the `order` table:
- `sms_sid`: VARCHAR (stores Twilio message ID)
- `sms_status`: VARCHAR (message delivery status)
- `sms_error_code`: VARCHAR (error code if delivery failed)
- `sms_error_message`: VARCHAR (detailed error message)

## Troubleshooting

### SMS Command Issue Fixes

1. **"Help" Command Issue**
   - Problem: The "help" command was not responding correctly or contained outdated information
   - Fix: Enhanced the command detection logic in `app/routes/order.py` using both exact matching and keyword matching:
     ```python
     # First, try exact match for common commands
     command_type = message_body.strip().lower()
     
     # Then use keyword matching for flexibility
     elif command_type == "help" or any(keyword in message_body for keyword in ['help', 'command', 'info', 'option']):
         # Process help command
     ```
   - Updated all phone numbers in the help text and other responses to use (833) 324-7207
   - Added more helpful content to the response templates

### Common SMS Delivery Issues

1. **Message Status Shows "Undelivered"**
   - Check the `sms_error_code` and `sms_error_message` in the database
   - Verify the recipient's phone number is valid and can receive SMS
   - Ensure your Twilio account has sufficient credits

2. **No Status Callback Received**
   - Verify your `BASE_URL` is publicly accessible
   - Check that your webhook endpoint is correctly configured in Twilio
   - Ensure your server is accepting POST requests to the callback URL

3. **Message Shows "Queued" For Too Long**
   - Check your Twilio account status (possible suspension)
   - Verify the recipient's phone format is correct (E.164 format)
   - Ensure the destination country is supported by your Twilio account

### Debugging Tools

- Use `python test_sms.py webhook` to verify webhook configuration
- Check application logs for delivery status updates
- Query the database directly to see SMS status:
  ```sql
  SELECT id, sms_sid, sms_status, sms_error_code, sms_error_message 
  FROM "order" 
  WHERE sender = '+1XXXXXXXXXX' 
  ORDER BY timestamp DESC 
  LIMIT 5;
  ```

## Status Codes and Meanings

The system tracks the following Twilio message statuses:

| Status | Description |
|--------|-------------|
| queued | Message is waiting to be sent |
| sending | Message is in the process of being sent |
| sent | Message has been sent to the carrier |
| delivered | Message was successfully delivered to the recipient |
| undelivered | Message could not be delivered to the recipient |
| failed | Message could not be sent or delivered |

Common error codes:
- `30001`: Queue overflow
- `30002`: Account suspended
- `30003`: Unreachable destination handset
- `30004`: Message blocked
- `30005`: Unknown destination handset
- `30006`: Landline or unreachable carrier
- `30007`: Carrier violation