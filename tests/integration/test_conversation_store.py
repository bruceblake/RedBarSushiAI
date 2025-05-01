"""
Tests for the Redis-based conversation store functionality.
"""

import pytest
import time
import uuid
from app.utils.conversation_store import conversation_store


@pytest.mark.integration
def test_conversation_store_basic_operations():
    """Test basic operations of the conversation store."""
    # Generate a unique session ID for testing
    session_id = str(uuid.uuid4())

    # Test saving a new conversation
    initial_data = {
        "id": session_id,
        "created_at": time.time(),
        "updated_at": time.time(),
        "messages": [
            {
                "role": "user",
                "content": "Tell me about your menu",
                "timestamp": time.time(),
            }
        ],
        "context": {},
        "resolved": False,
        "items": [],
    }

    # Save the conversation
    result = conversation_store.save_conversation(session_id, initial_data)
    assert result is True, "Failed to save conversation"

    # Retrieve the conversation
    retrieved = conversation_store.get_conversation(session_id)
    assert retrieved is not None, "Failed to retrieve conversation"
    assert retrieved["id"] == session_id, "Session ID mismatch"
    assert len(retrieved["messages"]) == 1, "Messages count mismatch"
    assert retrieved["messages"][0]["role"] == "user", "Message role mismatch"

    # Add a message
    result = conversation_store.add_message(
        session_id, "assistant", "We have sushi and more!"
    )
    assert result is True, "Failed to add message"

    # Retrieve updated conversation
    updated = conversation_store.get_conversation(session_id)
    assert len(updated["messages"]) == 2, "Updated messages count mismatch"
    assert updated["messages"][1]["role"] == "assistant", "Added message role mismatch"
    assert "sushi" in updated["messages"][1]["content"], "Message content mismatch"

    # Update conversation metadata
    result = conversation_store.update_conversation(session_id, {"resolved": True})
    assert result is True, "Failed to update conversation"

    # Verify the update
    final = conversation_store.get_conversation(session_id)
    assert final["resolved"] is True, "Resolved flag not updated"

    # Delete the conversation
    result = conversation_store.delete_conversation(session_id)
    assert result is True, "Failed to delete conversation"

    # Verify deletion
    empty = conversation_store.get_conversation(session_id)
    assert (
        empty["id"] == session_id
    ), "Should return a new empty conversation with the same ID"
    assert len(empty["messages"]) == 0, "New conversation should have empty messages"


@pytest.mark.integration
def test_conversation_context_preservation():
    """Test that conversation context is properly preserved across interactions."""
    # Generate a unique session ID for testing
    session_id = str(uuid.uuid4())

    # Initial conversation creation with user query
    conversation_store.save_conversation(
        session_id,
        {
            "id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
            "context": {"caller_name": "Test User"},
            "resolved": False,
            "items": [],
        },
    )

    # Add user message
    conversation_store.add_message(session_id, "user", "What sushi do you have?")

    # Add assistant response
    conversation_store.add_message(
        session_id,
        "assistant",
        "We have California Roll, Spicy Tuna Roll, and many others. What would you like to know about?",
    )

    # Add follow-up question
    conversation_store.add_message(
        session_id, "user", "Tell me about the Spicy Tuna Roll"
    )

    # Add assistant response
    conversation_store.add_message(
        session_id,
        "assistant",
        "The Spicy Tuna Roll is made with fresh tuna, spicy mayo, and cucumber. It costs $12.99.",
    )

    # Retrieve the conversation
    conversation = conversation_store.get_conversation(session_id)

    # Verify that all messages are in the conversation
    assert (
        len(conversation["messages"]) == 4
    ), "Should have 4 messages in the conversation"

    # Verify the conversation flow makes sense
    assert (
        "sushi" in conversation["messages"][0]["content"]
    ), "First message should be about sushi"
    assert (
        "California" in conversation["messages"][1]["content"]
    ), "Second message should mention California Roll"
    assert (
        "Spicy Tuna" in conversation["messages"][2]["content"]
    ), "Third message should be about Spicy Tuna"
    assert (
        "$12.99" in conversation["messages"][3]["content"]
    ), "Fourth message should include price"

    # Verify context is preserved
    assert (
        conversation["context"].get("caller_name") == "Test User"
    ), "Context should be preserved"

    # Clean up
    conversation_store.delete_conversation(session_id)


@pytest.mark.integration
def test_fallback_to_memory_when_redis_unavailable():
    """Test that the conversation store falls back to memory when Redis is unavailable."""
    # Only run this test if we're using the memory fallback
    if conversation_store.redis_client is not None:
        pytest.skip("Redis is available, skipping memory fallback test")

    # Generate a unique session ID
    session_id = str(uuid.uuid4())

    # Save a conversation to memory
    conversation_store.save_conversation(
        session_id,
        {
            "id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [
                {"role": "user", "content": "Memory test", "timestamp": time.time()}
            ],
            "context": {},
            "resolved": False,
            "items": [],
        },
    )

    # Verify it was saved to memory
    assert (
        session_id in conversation_store.memory_store
    ), "Conversation not saved to memory"

    # Retrieve and verify the conversation
    conversation = conversation_store.get_conversation(session_id)
    assert conversation["id"] == session_id, "Session ID mismatch"
    assert (
        "Memory test" in conversation["messages"][0]["content"]
    ), "Message content mismatch"

    # Clean up
    conversation_store.delete_conversation(session_id)
    assert (
        session_id not in conversation_store.memory_store
    ), "Conversation not deleted from memory"
