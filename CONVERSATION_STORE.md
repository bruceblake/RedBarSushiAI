# Conversation Store for Menu Questions and Order Resolution

This document describes the Redis-backed conversation store used for maintaining context between interactions in the Red Bar Sushi AI system.

## Overview

The conversation store provides persistent state storage for multi-turn conversations, allowing the AI to maintain context across multiple interactions with the user. This is particularly useful for menu questions and order resolution, where a single conversation may span multiple turns.

## Implementation Details

The conversation store is implemented in `app/utils/conversation_store.py` and provides the following key features:

1. **Redis-backed Storage**: Uses Redis as the primary storage backend for conversation state.
2. **Automatic Fallback**: Falls back to in-memory storage if Redis is unavailable.
3. **Conversation Management**: Provides methods for creating, retrieving, updating, and deleting conversations.
4. **Message History**: Maintains a complete history of the conversation between the AI and the user.
5. **Contextual Information**: Stores additional context like order items and resolution status.
6. **Automatic Expiration**: Automatically expires conversations after a configurable period.

## Key Components

1. **ConversationStore Class**: Manages the Redis connection and provides the core functionality.
2. **conversation_store Singleton**: A global instance for easy access throughout the application.
3. **Interactive Order Resolution Integration**: Used in `menu_matcher.py` for maintaining context during order resolution.
4. **Menu Questions Integration**: Used in the voice response system for maintaining context during menu questions.
5. **Optimized Menu Handler Integration**: Provides context-aware menu question handling with caching.

## Usage Examples

### Creating a New Conversation

```python
from app.utils.conversation_store import conversation_store

# Generate a session ID
session_id = str(uuid.uuid4())

# Create a new conversation
conversation_store.save_conversation(session_id, {
    "id": session_id,
    "created_at": time.time(),
    "updated_at": time.time(),
    "messages": [
        {"role": "user", "content": "Initial user message", "timestamp": time.time()}
    ],
    "context": {},
    "resolved": False,
    "items": []
})
```

### Adding Messages to a Conversation

```python
# Add a user message
conversation_store.add_message(session_id, "user", "What sushi do you have?")

# Add an assistant response
conversation_store.add_message(session_id, "assistant", "We have California Roll, Spicy Tuna Roll, and more.")
```

### Retrieving a Conversation

```python
# Get the current state of a conversation
conversation = conversation_store.get_conversation(session_id)

# Access conversation data
messages = conversation["messages"]
resolved = conversation["resolved"]
items = conversation["items"]
```

### Updating Conversation State

```python
# Update conversation metadata
conversation_store.update_conversation(session_id, {
    "resolved": True,
    "items": [{"name": "California Roll", "quantity": 2}]
})
```

## Integration with Menu Questions

The conversation store is integrated with the menu questions handling in the voice response system. When a user asks a question about the menu, the system:

1. Retrieves or creates a session ID (using the Twilio CallSid when available)
2. Fetches any existing conversation from the store
3. Processes the user's query in the context of the previous conversation
4. Stores the interaction (both the user's query and the AI's response) in the conversation store
5. Returns a response that takes the conversation history into account

## Integration with Order Resolution

The conversation store is also integrated with the interactive order resolution system:

1. When a user starts an order, a conversation is created
2. As the user and AI exchange messages to clarify the order, these are stored in the conversation
3. The order state (items, quantities, modifications) is tracked in the conversation
4. When the order is finalized, the conversation is marked as resolved

## Performance Considerations

1. Redis connections are pooled and reused for efficiency
2. The system includes built-in caching to reduce Redis access
3. Failed Redis operations automatically fall back to in-memory storage
4. Auto-cleanup processes prevent memory leaks
5. Expired conversations are automatically removed

## Troubleshooting

If conversations are not being maintained correctly:

1. Check that Redis is running and accessible
2. Verify that the CELERY_BROKER_URL environment variable is set correctly
3. Check the logs for any Redis connection errors
4. Verify that the conversation session IDs are being transmitted correctly
5. Inspect the conversation store contents using Redis CLI