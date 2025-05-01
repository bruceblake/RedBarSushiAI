#!/usr/bin/env python
"""
Test script for database connection reliability with retry logic.
This script can be used to simulate database connection issues and verify that
our retry mechanism works properly.
"""

import os
import time
import random
import logging
from flask import Flask
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main test function to verify database connection reliability."""
    logger.info("Starting database connection reliability test")

    # Create a minimal Flask app context
    app = Flask(__name__)
    app.config.from_object("app.config")

    # Import after app creation to avoid circular imports
    from app import db
    from app.db_init import execute_with_retry, verify_connection

    # Initialize the app with database support
    db.init_app(app)

    with app.app_context():
        # Test basic connection verification
        logger.info("Testing basic database connection verification")
        if verify_connection():
            logger.info("✅ Basic connection verification successful")
        else:
            logger.error("❌ Basic connection verification failed")
            return

        # Test query execution with retry
        def execute_test_query():
            """Execute a simple test query."""
            logger.info("Executing test query...")
            with db.session.connection() as conn:
                result = conn.execute(text("SELECT 1 as test_value"))
                value = result.scalar()
                logger.info(f"Query result: {value}")
                return value == 1

        logger.info("Testing query execution with retry mechanism")
        result = execute_with_retry(execute_test_query)
        if result:
            logger.info("✅ Query execution with retry successful")
        else:
            logger.error("❌ Query execution with retry failed")

        # Optional: Test TCP keepalive by sleeping and then reconnecting
        logger.info("Testing connection persistence after idle period...")
        time.sleep(10)  # Sleep for 10 seconds

        if verify_connection():
            logger.info("✅ Connection persisted after idle period")
        else:
            logger.error("❌ Connection lost after idle period")

        # Optional: Simulate a temporary network issue with retries
        class TemporaryConnectionSimulator:
            def __init__(self, success_after=2):
                self.attempts = 0
                self.success_after = success_after

            def execute(self):
                """Simulate a function that fails initially but succeeds after N attempts."""
                self.attempts += 1
                logger.info(f"Simulated operation attempt #{self.attempts}")

                if self.attempts <= self.success_after:
                    # Simulate different types of database errors
                    errors = [
                        "connection timed out",
                        "Connection refused",
                        "terminating connection due to administrator command",
                        "This Connection is closed",
                    ]
                    error_msg = random.choice(errors)
                    logger.info(f"Simulating error: {error_msg}")
                    from sqlalchemy.exc import OperationalError

                    raise OperationalError(f"({error_msg})", None, None)

                logger.info("Simulated operation succeeded!")
                return True

        logger.info("Testing retry logic with simulated connection failures...")
        simulator = TemporaryConnectionSimulator(success_after=3)
        result = execute_with_retry(simulator.execute)

        if result:
            logger.info("✅ Retry mechanism handled simulated failures successfully")
        else:
            logger.error("❌ Retry mechanism failed to handle simulated failures")

        logger.info("Database connection reliability test completed")


if __name__ == "__main__":
    main()
