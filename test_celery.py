#!/usr/bin/env python
from celery_app import celery
from tasks import send_confirmation_sms_task

# Check registered tasks
print("Registered Tasks:")
print(celery.tasks.keys())

# Attempt to send a test task
result = send_confirmation_sms_task.delay(
    order_id="test_123",
    order_message="This is a test order",
    sender="+11234567890",
    caller_name="Test Caller",
    bill_amount=1000,
    order_items=["Test Item 1", "Test Item 2"],
    location_id="test_location"
)

print(f"Task ID: {result.id}")
print(f"Task Status: {result.status}")