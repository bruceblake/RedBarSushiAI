#!/usr/bin/env python
"""
Red Bar Sushi AI - SMS Testing Tool

This script provides multiple tools for testing SMS functionality:
1. Send a test SMS to verify Twilio integration is working
2. Test SMS endpoint responses locally without sending actual messages
3. Simulate an order going through all status changes
4. Verify webhook response formats
"""

import os
import sys
import logging
import argparse
import random
import datetime
from app import create_app, twilio_client
from app.models import Order
from app import db
from twilio.base.exceptions import TwilioRestException

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get Twilio phone number from environment or config
try:
    from app.config import TWILIO_NUMBER
except ImportError:
    TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")


def send_test_sms(phone_number, app, message_type="basic"):
    """Send a test SMS to verify Twilio functionality

    Args:
        phone_number: Recipient's phone number
        app: Flask app context
        message_type: Type of test message to send (basic, order, status, all_commands)
    """
    try:
        # Validate phone number format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"

        # Log attempt
        logger.info(f"Attempting to send {message_type} test SMS to {phone_number}")

        # Create appropriate message based on type
        if message_type == "basic":
            body = "🍣 Hello from Red Bar Sushi AI! This is a test message to verify SMS notifications are working."
        elif message_type == "order":
            # Create a test order confirmation
            body = """🍣 RED BAR SUSHI ORDER CONFIRMATION 🍣

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
• Reply 'help' for more options"""
        elif message_type == "status":
            # Create a test status update
            body = """🍣 RED BAR SUSHI STATUS UPDATE 🍣

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
📱 Reply 'help' for more options"""
        elif message_type == "all_commands":
            # Send info about all available commands
            body = """🍣 RED BAR SUSHI SMS COMMANDS 🍣

Test our SMS system by replying with:

• 'status' - Check order status
• 'help' - See available commands
• 'menu' - View our menu
• 'hours' - Check business hours
• 'location' - Get our address
• 'contact' - Get contact info
• 'specials' - See today's specials

Try them out to see our enhanced SMS responses!"""

        # Create the message
        message = twilio_client.messages.create(
            body=body,
            from_=TWILIO_NUMBER,
            to=phone_number,
            status_callback=f"{os.environ.get('BASE_URL', 'https://redbarsushiai.onrender.com')}/sms_status_callback",
        )

        logger.info(f"Message sent successfully! SID: {message.sid}")
        logger.info(f"Status: {message.status}")

        # Store the message SID in the database for tracking
        with app.app_context():
            try:
                # Create a placeholder order for testing
                test_order = Order(
                    id=f"test-{message.sid[:8]}",
                    sender=phone_number,
                    caller_name="SMS Test",
                    message=body,
                    sms_sid=message.sid,
                    sms_status=message.status,
                    status="PREPARING" if message_type == "status" else "NEW",
                )
                db.session.add(test_order)
                db.session.commit()
                logger.info(f"Created test order record with ID: {test_order.id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating test order: {e}")

        return True, message.sid, body

    except TwilioRestException as e:
        logger.error(f"Twilio error: {e.msg}")
        logger.error(f"Error code: {e.code}")
        logger.error(
            f"More info: {e.details if hasattr(e, 'details') else 'No details available'}"
        )
        return False, str(e), None

    except Exception as e:
        logger.error(f"General error: {e}")
        return False, str(e), None


def test_sms_endpoint(command, app, phone_number="+15555555555"):
    """Test the SMS endpoint locally with a simulated command

    Args:
        command: The SMS command to test
        app: Flask app context
        phone_number: Simulated sender phone number
    """
    try:
        with app.test_client() as client:
            # Create the test order in the database if testing 'status'
            if command.lower() in ["status", "stat", "order", "check"]:
                with app.app_context():
                    existing = (
                        db.session.query(Order).filter_by(sender=phone_number).first()
                    )
                    if not existing:
                        test_order = Order(
                            id=f"test-{random.randint(10000, 99999)}",
                            sender=phone_number,
                            caller_name="Local Test",
                            message="""- 1x Spicy Tuna Roll ($8.99)
- 1x California Roll ($6.99)
Your total is $15.98""",
                            status="PREPARING",
                            timestamp=datetime.datetime.now()
                            - datetime.timedelta(minutes=45),
                        )
                        db.session.add(test_order)
                        db.session.commit()
                        logger.info(
                            f"Created test order for status check: {test_order.id}"
                        )

            # Make the request to the endpoint
            response = client.post("/sms", data={"From": phone_number, "Body": command})

            # Check response
            if response.status_code == 200:
                # Extract the message content from TwiML
                response_text = response.data.decode("utf-8")

                # Parse the response to extract the message body
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response_text)
                message_element = root.find(".//Message")
                message_body = (
                    message_element.text
                    if message_element is not None and message_element.text
                    else "No message body"
                )

                return True, message_body, response_text
            else:
                return (
                    False,
                    f"Error: HTTP {response.status_code}",
                    response.data.decode("utf-8"),
                )

    except Exception as e:
        logger.error(f"Error testing SMS endpoint: {e}")
        return False, f"Error: {str(e)}", None


def simulate_status_flow(phone_number, app):
    """Simulate an order going through all status changes

    Args:
        phone_number: Phone number to send updates to
        app: Flask app context
    """
    try:
        # Validate phone number format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"

        # Create a test order
        with app.app_context():
            order_id = f"test-{random.randint(10000, 99999)}"
            test_order = Order(
                id=order_id,
                sender=phone_number,
                caller_name="Status Flow Test",
                message="""- 1x Spicy Tuna Roll ($8.99)
- 1x California Roll ($6.99)
Your total is $15.98""",
                status="NEW",
                timestamp=datetime.datetime.now(),
            )
            db.session.add(test_order)
            db.session.commit()
            logger.info(f"Created test order for status flow: {order_id}")

            # Define status flow and messages
            statuses = [
                ("NEW", "Your order has been received and is being processed"),
                ("ACCEPTED", "Your order has been accepted by the restaurant"),
                ("PREPARING", "Your order is now being prepared in the kitchen"),
                ("READY", "Your order is ready for pickup!"),
                ("COMPLETED", "Your order has been completed. Thank you!"),
            ]

            messages_sent = []

            # Loop through each status
            for status, message in statuses:
                # Update the order status
                test_order = db.session.get(Order, order_id)
                test_order.status = status
                db.session.commit()
                logger.info(f"Updated order {order_id} to status: {status}")

                # Build status message
                from tasks import send_order_status_update_task

                # Execute the task directly (not async)
                result = send_order_status_update_task.run(order_id, message)
                logger.info(f"Status update result: {result}")
                messages_sent.append((status, message))

                # Wait for user confirmation before continuing
                if status != "COMPLETED":
                    proceed = input(
                        f"\nSent '{status}' update. Check your phone and press Enter to continue to next status (or 'q' to quit): "
                    )
                    if proceed.lower() == "q":
                        break

            return True, order_id, messages_sent

    except Exception as e:
        logger.error(f"Error in status flow simulation: {e}")
        return False, str(e), []


def verify_twilio_config():
    """Check if Twilio is properly configured"""
    required_vars = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER"]

    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            try:
                # Try to get from config
                import app.config

                if not hasattr(app.config, var):
                    missing_vars.append(var)
            except (ImportError, AttributeError):
                missing_vars.append(var)

    if missing_vars:
        logger.error(
            f"Missing required Twilio configuration: {', '.join(missing_vars)}"
        )
        return False

    return True


def test_webhook_config(app):
    """Test the webhook configuration endpoint"""
    try:
        with app.test_client() as client:
            response = client.get("/webhook-test")

            if response.status_code == 200:
                data = response.json

                # Pretty print the webhook configuration
                print("\n=== WEBHOOK CONFIGURATION ===")
                print(f"Base URL: {data.get('base_url', 'Not set')}")
                print("\nWebhook URLs:")
                for name, url in data.get("webhook_urls", {}).items():
                    print(f"  {name}: {url}")

                print("\nEnvironment:")
                for key, value in data.get("configuration", {}).items():
                    print(f"  {key}: {value}")

                print("\nDatabase:")
                db_status = data.get("database", {})
                if db_status.get("connection") == "ok":
                    print("  Connection: ✅ OK")
                    print(
                        f"  Registered locations: {db_status.get('registered_locations', 0)}"
                    )
                else:
                    print("  Connection: ❌ ERROR")
                    print(f"  Error: {db_status.get('error', 'Unknown error')}")

                return True, data
            else:
                return False, f"Error: HTTP {response.status_code}"

    except Exception as e:
        logger.error(f"Error testing webhook config: {e}")
        return False, str(e)


def test_migration():
    """Test the database migration script without actually running migrations"""
    try:
        # Import the migration module
        import migrate_sms_tracking

        # Get the database URL (without actually connecting)
        db_url = migrate_sms_tracking.get_database_url()

        # Parse the URL (without connecting)
        db_params = migrate_sms_tracking.parse_db_url(db_url)

        # Print configuration details
        print("\n=== DATABASE MIGRATION TEST ===")
        print(f"Database URL: {db_url}")
        print(f"Database name: {db_params['dbname']}")
        print(f"Database host: {db_params['host']}")
        print(f"Database port: {db_params['port']}")
        print(f"Database user: {db_params['user']}")

        # Describe the columns that would be added
        print("\nColumns that would be added (if they don't exist):")
        for column_name, column_type in [
            ("sms_sid", "VARCHAR(50)"),
            ("sms_status", "VARCHAR(20)"),
            ("sms_error_code", "INTEGER"),
            ("sms_error_message", "VARCHAR(255)"),
        ]:
            print(f"  - {column_name}: {column_type}")

        print("\n✅ Migration script configuration test passed!")
        print("\nTo perform the actual migration, run:")
        print("  python migrate_sms_tracking.py")

        return True, "Migration script configuration test passed"

    except Exception as e:
        logger.error(f"Error testing migration script: {e}")
        return False, str(e)


def print_help():
    """Print help information about this script"""
    print("\n🍣 RED BAR SUSHI SMS TESTING TOOL 🍣")
    print("\nThis script provides several ways to test the SMS functionality:")
    print("\n1. Send test messages:")
    print("   python test_sms.py send +1XXXXXXXXXX [basic|order|status|all_commands]")
    print("\n2. Test SMS commands locally:")
    print("   python test_sms.py test status")
    print("   python test_sms.py test menu")
    print("   python test_sms.py test help")
    print("\n3. Simulate an order going through all status changes:")
    print("   python test_sms.py flow +1XXXXXXXXXX")
    print("\n4. Check Twilio configuration:")
    print("   python test_sms.py check")
    print("\n5. Test webhook configuration:")
    print("   python test_sms.py webhook")
    print("\n6. Test database migration script:")
    print("   python test_sms.py migration")
    print("\n7. Display this help message:")
    print("   python test_sms.py help")


def main():
    """Process command line arguments and run the requested test"""
    # Only parse arguments when running as a script, not when imported by pytest
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Red Bar Sushi SMS Testing Tool")
        subparsers = parser.add_subparsers(dest="command", help="Command to run")

        # Send command
        send_parser = subparsers.add_parser("send", help="Send a test SMS")
        send_parser.add_argument(
            "phone_number",
            help="Phone number to send test SMS (with or without country code)",
        )
        send_parser.add_argument(
            "type",
            nargs="?",
            default="basic",
            choices=["basic", "order", "status", "all_commands"],
            help="Type of test message to send",
        )

        # Test command
        test_parser = subparsers.add_parser("test", help="Test SMS commands locally")
        test_parser.add_argument(
            "message", help="Message to test (e.g., status, help, menu)"
        )

        # Flow command
        flow_parser = subparsers.add_parser(
            "flow", help="Simulate an order going through all status changes"
        )
        flow_parser.add_argument("phone_number", help="Phone number to send updates to")

        # Check command
        subparsers.add_parser("check", help="Check Twilio configuration")

        # Webhook command
        subparsers.add_parser("webhook", help="Test webhook configuration")

        # Migration command
        subparsers.add_parser(
            "migration", help="Test database migration script configuration"
        )

        # Help command
        subparsers.add_parser("help", help="Show help information")

        args = parser.parse_args()

        # If no args or help command, show help
        if not args.command or args.command == "help":
            print_help()
            return True
    else:
        # Define a dummy args object for when imported by pytest
        class Args:
            command = None
            phone_number = "+15555555555"
            type = "basic"
            message = "help"

        args = Args()

    # Create app context
    app = create_app()

    # Process command
    if args.command == "send":
        # Check Twilio configuration
        if not verify_twilio_config():
            logger.error(
                "Twilio is not properly configured. Please check your environment variables."
            )

            # Print troubleshooting information
            print("\nTroubleshooting steps:")
            print("1. Check your Twilio account SID and auth token")
            print("2. Verify your Twilio phone number is active")
            print("3. Make sure the BASE_URL environment variable is set correctly")
            return False

        # Send the test message
        success, result, message = send_test_sms(args.phone_number, app, args.type)

        if success:
            print(f"\n✅ Message sent successfully! SID: {result}")
            print("\nMessage content:")
            print("-" * 50)
            print(message)
            print("-" * 50)
            print(
                "\nCheck your phone for the message and monitor the app logs for status callbacks"
            )
            return True
        else:
            print(f"\n❌ Failed to send SMS: {result}")

            # Provide troubleshooting information
            print("\nTroubleshooting steps:")
            print("1. Check your Twilio account SID and auth token")
            print("2. Verify your Twilio phone number is active")
            print(
                "3. Make sure the recipient number is in a valid format (+1XXXXXXXXXX)"
            )
            print("4. Check if your Twilio account has sufficient credits")
            print("5. Verify your BASE_URL environment variable is set correctly")
            return False

    elif args.command == "test":
        # Test SMS command locally
        success, result, raw_response = test_sms_endpoint(args.message, app)

        if success:
            print("\n✅ SMS endpoint test successful!")
            print("\nResponse to command '{args.message}':")
            print("-" * 50)
            print(result)
            print("-" * 50)
            print("\nRaw TwiML Response:")
            print(raw_response)
            return True
        else:
            print(f"\n❌ SMS endpoint test failed: {result}")
            if raw_response:
                print("\nRaw response:")
                print(raw_response)
            return False

    elif args.command == "flow":
        # Simulate order status flow
        success, result, messages = simulate_status_flow(args.phone_number, app)

        if success:
            print("\n✅ Status flow simulation completed successfully!")
            print(f"\nTest order ID: {result}")
            print("\nStatus messages sent:")
            for status, message in messages:
                print(f"- {status}: {message}")
            return True
        else:
            print(f"\n❌ Status flow simulation failed: {result}")
            return False

    elif args.command == "check":
        # Check Twilio configuration
        if verify_twilio_config():
            print("\n✅ Twilio configuration looks good!")
            # Show the configured Twilio number
            print(f"\nConfigured Twilio phone number: {TWILIO_NUMBER}")
            return True
        else:
            print(
                "\n❌ Twilio configuration has issues. Please check your environment variables."
            )
            return False

    elif args.command == "webhook":
        # Test webhook configuration
        success, result = test_webhook_config(app)

        if success:
            print("\n✅ Webhook configuration retrieved successfully!")
            return True
        else:
            print(f"\n❌ Failed to retrieve webhook configuration: {result}")
            return False

    elif args.command == "migration":
        # Test migration script configuration
        success, result = test_migration()

        if success:
            return True
        else:
            print(f"\n❌ Migration script test failed: {result}")

            # Provide troubleshooting information
            print("\nTroubleshooting steps:")
            print("1. Check your database connection settings")
            print(
                "2. Make sure the SQLALCHEMY_DATABASE_URI or DATABASE_URL is set correctly"
            )
            print("3. Verify the database user has ALTER TABLE permissions")
            return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
