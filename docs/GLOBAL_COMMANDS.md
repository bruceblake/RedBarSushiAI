# Global Command Handling Documentation

## Overview
Global commands allow users to control the conversation flow at any point, regardless of the current FSM state. This provides a more natural and user-friendly voice interface.

## Implemented Global Commands

### 1. REPEAT Commands
**Purpose**: Repeat the last assistant message when users miss or don't understand something.

**Trigger Phrases**:
- "Repeat that"
- "Say that again"
- "What did you just say?"
- "I didn't catch that"
- "Pardon me"
- "Come again"
- "One more time"

**Behavior**:
- Retrieves the last assistant message from conversation history
- Re-sends the exact same message
- Works in any conversation state

### 2. START_OVER Commands
**Purpose**: Reset the entire conversation and start fresh.

**Trigger Phrases**:
- "Start over"
- "Begin again"
- "Start fresh"
- "Reset"
- "Restart the order"
- "Cancel everything and start over"

**Behavior**:
- Clears conversation history
- Resets FSM to INITIAL state
- Clears cart and order data
- Triggers new greeting

### 3. GO_BACK Commands
**Purpose**: Return to the previous conversation state.

**Trigger Phrases**:
- "Go back"
- "Previous step"
- "Undo that"
- "Take me back"
- "Back up"
- "Let's go back"
- "I changed my mind"

**Behavior**:
- Uses FSM's previous state tracking
- Returns to the last major state
- Provides context-appropriate response
- Currently supports: ORDERING, MAIN_MENU states

### 4. HELP Commands
**Purpose**: Request assistance or clarification.

**Trigger Phrases**:
- "Help"
- "Help me"
- "What can I do?"
- "I'm confused"
- "What are my options?"
- "I need help"
- "How do I..."

**Behavior**:
- Maps to REQUEST_ESCALATION event
- Provides context-sensitive help
- May offer to connect with human agent

### 5. CANCEL Commands
**Purpose**: Cancel current operation or end conversation.

**Trigger Phrases**:
- "Cancel"
- "Stop"
- "End the call"
- "Nevermind"
- "Forget it"
- "I don't want anything"
- "Goodbye"

**Behavior**:
- Maps to CANCEL_ORDER event
- Handled by FSM state transitions
- Confirms cancellation when appropriate

## Technical Implementation

### Architecture
```
User Input → Global Command Detection → Command Handler → Response
                    ↓ (if no command)
              Intent Detection → FSM Processing
```

### Key Components

1. **GlobalCommandDetector** (`app/utils/global_commands.py`)
   - Pattern-based detection using regex
   - Returns command type and confidence score
   - Threshold: 0.8 confidence for activation

2. **Intent Detector Integration** (`app/utils/intent_detector_async.py`)
   - Checks for global commands before state-specific intents
   - Maps some commands to existing FSM events
   - Passes special commands to orchestrator

3. **Orchestrator Handling** (`app/utils/agent_orchestration_async.py`)
   - `_handle_global_command()` method for special commands
   - REPEAT: Fetches from conversation history
   - START_OVER: Resets FSM and context
   - GO_BACK: Restores previous state

4. **Global Command Context** (`app/utils/global_commands.py`)
   - Tracks last response for repeat functionality
   - Maintains state history for go back
   - Configurable history size (default: 10)

## Usage Examples

### In Ordering State
```
User: "I want a salmon roll"
Assistant: "I've added a salmon roll to your order. Would you like anything else?"
User: "What did you say?"
Assistant: "I've added a salmon roll to your order. Would you like anything else?"
```

### Starting Over
```
User: "Actually, let me start over"
Assistant: "Let's start fresh. Welcome to Red Bar Sushi. How can I help you today?"
```

### Going Back
```
User: "Go back"
Assistant: "Okay, let's go back to your order. What would you like to add or change?"
```

## Configuration

### Detection Threshold
- Default: 0.8 confidence
- Adjustable in `intent_detector.detect_intent()`

### History Size
- Default: 10 states/responses
- Configurable in `GlobalCommandContext.max_history_size`

### Pattern Customization
- Add patterns in `GlobalCommandDetector.COMMAND_PATTERNS`
- Use regex with case-insensitive matching

## Best Practices

1. **Command Priority**
   - Global commands checked before state-specific intents
   - Prevents accidental triggering in normal conversation

2. **Context Preservation**
   - Last response always updated
   - State history maintained for go back

3. **Graceful Handling**
   - Appropriate messages when commands can't be executed
   - Example: "I don't have anything to repeat yet"

4. **State-Aware Responses**
   - Different responses based on current state
   - More natural conversation flow

## Future Enhancements

1. **More Commands**
   - "Pause" - Temporarily pause the conversation
   - "Skip" - Skip current question
   - "More info" - Get detailed information

2. **Improved Context**
   - Multi-level undo/redo
   - Bookmark specific states
   - Named checkpoints

3. **Personalization**
   - Learn user's preferred commands
   - Adaptive confidence thresholds
   - Custom command aliases

## Testing

Run the test script to verify functionality:
```bash
python test_global_commands.py
```

This tests:
- Command detection accuracy
- Pattern variations
- Edge cases
- Context-aware responses