# Key Files Reference Guide

## Priority 1 - Core Understanding (Start Here)

1. **README.md** - Complete system overview (just updated)
2. **CLAUDE.md** - Comprehensive architectural documentation
3. **IMPORTANT_FILES_SUMMARY.md** - Key code snippets
4. **app/main.py** - Application entry point

## Priority 2 - Voice Flow Understanding

5. **app/api/conversation_relay/handler.py** - Voice webhook handler
6. **app/utils/agent_orchestration_async.py** - Agent coordination
7. **app/fsm/core.py** - Conversation state machine
8. **app/utils/intent_detector_async.py** - LLM intent detection

## Priority 3 - Agent System

9. **app/agents/frontline_async_ai.py** - Main conversation agent
10. **app/agents/factory_async.py** - Agent creation/registration
11. **app/agents/menu_async_enhanced.py** - Menu inquiries
12. **app/agents/cart_async.py** - Order building
13. **app/agents/fulfillment_async.py** - Order submission

## Priority 4 - Data Models

14. **app/models/menu_async.py** - Menu database schema
15. **app/models/order_async.py** - Order database schema
16. **app/db_async.py** - Database configuration

## Priority 5 - Integration Points

17. **app/utils/menu_matcher_cache_async.py** - Menu matching logic
18. **app/utils/deliverect/orders_async.py** - POS integration
19. **app/api/deliverect_menu.py** - Menu webhook handler
20. **app/config.py** - Configuration management

## Priority 6 - Testing

21. **tests/TEST_STRATEGY.md** - Testing approach
22. **tests/conftest.py** - Test configuration
23. **tests/integration/test_fsm_orchestration.py** - FSM tests
24. **tests/integration/test_conversation_relay.py** - Voice tests

## File Locations Quick Reference

```
app/
├── api/
│   ├── conversation_relay/   # Voice handling
│   ├── menu/                 # Menu APIs
│   └── order/                # Order APIs
├── agents/                   # AI agents
├── fsm/                      # State machine
├── models/                   # Database models
├── utils/                    # Utilities
│   ├── deliverect/          # POS integration
│   └── agent_utils/         # Agent helpers
└── schemas/                  # Data validation
```

## Key Concepts by File

| Concept          | Primary File                    | Purpose                  |
| ---------------- | ------------------------------- | ------------------------ |
| Voice Entry      | `conversation_relay/handler.py` | Receives Twilio webhooks |
| Agent Selection  | `agent_orchestration_async.py`  | Routes to right agent    |
| State Management | `fsm/core.py`                   | Tracks conversation flow |
| Intent Detection | `intent_detector_async.py`      | No keywords, uses LLM    |
| Menu Matching    | `menu_matcher_cache_async.py`   | Natural language → PLU   |
| Order Submission | `deliverect/orders_async.py`    | Send to POS              |
| Caching          | `redis_async.py`                | Performance optimization |
| Database         | `db_async.py`                   | PostgreSQL setup         |

## Environment Variables Required

From `app/config.py`:

- `DATABASE_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `DELIVERECT_API_KEY`
- `VOICE_HANDLER` (conversation_relay or realtime)

## Quick Commands

```bash
# Start development
./start_docker.sh

# Run tests (unit + integration)
pytest tests/unit tests/integration -v

# Check logs
docker logs -f redbarsushi-app-1

# Access database
docker exec -it redbarsushi-postgres-1 psql -U redbarsushi

# Clear menu cache
docker exec -it redbarsushi-app-1 python -c "from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher; import asyncio; asyncio.run(clear_cached_menu_matcher())"
```
