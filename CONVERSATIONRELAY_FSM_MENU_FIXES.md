# ConversationRelay FSM and Menu Update Fixes

## Issues Identified

1. **Menu Cache Not Clearing Properly**
   - Duplicate `clear_cached_menu_matcher()` function definitions in `menu_matcher_cache_async.py`
   - Menu agent uses cached matcher that may hold stale data
   - Global singleton pattern prevents fresh data loading

2. **FSM State Transitions**
   - ConversationRelay handler doesn't explicitly manage FSM transitions
   - States may get stuck if proper events aren't triggered
   - No clear logging of state transitions in ConversationRelay context

## Fixes Required

### 1. Fix Menu Cache Clearing

The duplicate function in `app/utils/menu_matcher_cache_async.py` needs to be fixed:

```python
# Remove duplicate at line 141-144 and keep only the implementation at line 102
```

### 2. Force Menu Reload in Agents

After a Deliverect menu update, the menu agent needs to create a new matcher instance:

```python
# In app/agents/menu_async.py, modify _lookup_menu_item:
async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
    logger.info(f"Looking up menu item: {item_name}")
    
    # Always create a fresh matcher with current DB session
    # This ensures we get the latest menu data
    async_matcher = await get_cached_async_menu_matcher(self.db, force_refresh=True)
    item_result, score = await async_matcher.match_item(item_name)
    # ... rest of implementation
```

### 3. Add FSM Transition Logging

In `app/api/conversation_relay/handler.py`, add explicit FSM state tracking:

```python
async def handle_prompt(self, message: Dict[str, Any]):
    voice_prompt = message.get("voicePrompt", "")
    
    # Log current FSM state before processing
    fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
    logger.info(f"FSM State before prompt: {fsm.current_state.name}")
    
    # Process the prompt
    response = await async_agent_orchestrator.process_voice_input(
        self.call_sid, voice_prompt
    )
    
    # Log FSM state after processing
    fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
    logger.info(f"FSM State after prompt: {fsm.current_state.name}")
```

### 4. Trigger FSM Transitions Based on Intent

The agent orchestrator needs to detect intents and trigger appropriate FSM events:

```python
# In the agent orchestrator's process_voice_input:
# Add intent detection for common transitions
if "order" in input_text.lower() or "like to order" in input_text.lower():
    await fsm.trigger(ConversationEvent.START_ORDER)
elif "that's all" in input_text.lower() or "complete my order" in input_text.lower():
    await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
```

## Testing the Fixes

### 1. Test Menu Updates
```bash
# Watch logs during menu update
docker-compose logs -f app | grep -i "menu"

# After Deliverect push, verify:
# - "Invalidating menu cache..." appears
# - "Menu cache invalidated successfully" appears
# - Next menu lookup shows "Creating new menu matcher"
```

### 2. Test FSM Transitions
```bash
# Watch FSM state transitions
docker-compose logs -f app | grep -i "fsm state"

# During a call, verify transitions:
# - INITIAL → GREETING (on setup)
# - GREETING → MAIN_MENU (after name)
# - MAIN_MENU → ORDERING (when ordering)
# - ORDERING → VALIDATION → CONFIRMATION
```

### 3. Monitor ConversationRelay Events
```bash
# Watch ConversationRelay handler
docker-compose logs -f app | grep -i "conversationrelay"
```

## Quick Database Check

To verify menu items are actually in the database after update:

```bash
# Check menu items in database
docker-compose exec app python -c "
import asyncio
from app.db_async import get_db
from sqlalchemy import select
from app.models.menu_async import MenuItem

async def check_menu():
    async for db in get_db():
        result = await db.execute(select(MenuItem).limit(10))
        items = result.scalars().all()
        for item in items:
            print(f'Item: {item.name}, PLU: {item.plu}, Available: {item.is_available}')
        break

asyncio.run(check_menu())
"
```

## Environment Variables to Check

Ensure these are set in your `.env`:

```bash
# For better logging
LOG_LEVEL=DEBUG

# Voice handler
VOICE_HANDLER=conversation_relay

# Menu cache TTL (optional, default is 3600 seconds)
MENU_CACHE_TTL=300  # 5 minutes for testing
```

## Common Issues and Solutions

1. **"Menu item not found" even after update**
   - Check if PLU codes match between Deliverect and database
   - Verify menu update webhook is actually being called
   - Check Redis is running and accessible

2. **FSM stuck in MAIN_MENU state**
   - Ensure proper intent detection for "order" keywords
   - Check if cart agent is properly initialized
   - Verify FSM event triggers are being called

3. **ConversationRelay not sending responses**
   - Check WebSocket connection is stable
   - Verify agent responses have "text" field
   - Ensure TTS provider is configured correctly