# Important Files and Code Summary for RedBarSushiAI

This document contains the most critical files and code snippets for understanding the RedBarSushiAI system.

## 1. Core Application Entry Point

### app/main.py
```python
# Key sections:
from fastapi import FastAPI
from app.api import api_router
from app.config import settings

app = FastAPI(title="RedBarSushiAI")

# Include all API routes
app.include_router(api_router, prefix="/api")

# Startup event - initializes agents and database
@app.on_event("startup")
async def startup_event():
    # Initialize database
    await init_database()
    # Initialize agents
    await async_agent_factory.initialize_agents()
    # Initialize FSM manager
    await async_fsm_manager.initialize()
```

## 2. Agent Orchestration System

### app/utils/agent_orchestration_async.py
```python
class AsyncAgentOrchestrator:
    """Orchestrates multi-agent conversations with FSM integration."""
    
    async def process_voice_input(self, call_sid: str, transcript: str, **kwargs):
        """Main entry point for processing voice input."""
        # 1. Get or create FSM
        fsm = await self.get_fsm(call_sid)
        
        # 2. Detect intent using LLM
        event = await self.intent_detector.detect_intent(
            transcript, fsm.current_state, fsm.context
        )
        
        # 3. Process FSM transition
        if event:
            await fsm.process_event(event)
        
        # 4. Select agent based on state
        agent = self._get_agent_for_state(fsm.current_state)
        
        # 5. Process with selected agent
        response = await agent.process_input(transcript, fsm.context)
        
        return response
```

## 3. Finite State Machine Implementation

### app/fsm/core.py
```python
class ConversationState(Enum):
    """All possible conversation states."""
    GREETING = "greeting"
    MAIN_MENU = "main_menu"
    ORDERING = "ordering"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    FULFILLMENT = "fulfillment"
    COMPLETION = "completion"
    ESCALATION = "escalation"

class AsyncConversationFSM:
    """Manages conversation flow with state transitions."""
    
    async def process_event(self, event: ConversationEvent):
        """Process an event and transition states."""
        transitions = self._get_transitions()
        current_transitions = transitions.get(self.current_state, {})
        
        if event in current_transitions:
            new_state = current_transitions[event]
            await self.transition_to(new_state)
```

## 4. ConversationRelay Handler (Voice Entry Point)

### app/api/conversation_relay/handler.py
```python
class ConversationRelayHandler:
    """Handles Twilio ConversationRelay webhooks."""
    
    async def handle_prompt(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process voice prompt from Twilio."""
        # Extract transcript
        transcript = prompt_data.get("prompt", {}).get("text", "")
        
        # Get FSM state for logging
        fsm = await async_agent_orchestrator.get_fsm(self.call_sid)
        logger.info(f"FSM State BEFORE: {fsm.current_state.name}")
        
        # Process with orchestrator
        response = await async_agent_orchestrator.process_voice_input(
            call_sid=self.call_sid,
            transcript=transcript,
            language=self.language,
            is_final=True
        )
        
        logger.info(f"FSM State AFTER: {fsm.current_state.name}")
        
        # Format response for Twilio
        return {
            "say": {
                "text": response["text"],
                "language": self.language
            },
            "listen": response.get("requires_response", True)
        }
```

## 5. LLM-Based Intent Detection

### app/utils/intent_detector_async.py
```python
class AsyncIntentDetector:
    """Detects user intents using LLM instead of keywords."""
    
    async def detect_intent(
        self, 
        transcript: str, 
        current_state: ConversationState,
        context: Dict[str, Any]
    ) -> Optional[ConversationEvent]:
        """Detect intent using GPT-4."""
        
        # Build state-specific prompt
        prompt = f"""
        Current conversation state: {current_state.value}
        Customer said: "{transcript}"
        
        Based on the state and what the customer said, what is their intent?
        Possible intents for {current_state.value}:
        {self._get_valid_intents_for_state(current_state)}
        
        Return ONLY the intent name, nothing else.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.1
        )
        
        intent_name = response.choices[0].message.content.strip()
        return self._map_to_event(intent_name)
```

## 6. Frontline Agent (Main Coordinator)

### app/agents/frontline_async_ai.py
```python
class AsyncFrontlineVoiceAgentAI(BaseAsyncAgent):
    """AI-enhanced frontline agent using OpenAI for responses."""
    
    async def process_input(self, transcript: str, context: Dict) -> Dict:
        """Process input using OpenAI."""
        # Build conversation history
        messages = self._build_conversation_history(context)
        
        # Add current message
        messages.append({"role": "user", "content": transcript})
        
        # Get AI response
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            tools=self.tools  # Agent can use tools
        )
        
        # Handle tool calls
        if response.choices[0].message.tool_calls:
            tool_results = await self._execute_tools(
                response.choices[0].message.tool_calls
            )
            # Get final response after tool execution
            return await self._get_response_after_tools(tool_results)
        
        return {
            "text": response.choices[0].message.content,
            "requires_response": True
        }
```

## 7. Menu Database Models

### app/models/menu_async.py
```python
class MenuItem(Base):
    """Menu item model with PLU for POS integration."""
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    plu = Column(String(50), unique=True, nullable=False)  # Critical!
    price = Column(Integer)  # In cents
    category_id = Column(Integer, ForeignKey("menu_categories.id"))
    deliverect_item_id = Column(String(255))
    is_available = Column(Boolean, default=True)
    snoozed_until = Column(DateTime, nullable=True)
    
    # Relationships
    category = relationship("MenuCategory", back_populates="items")
    modifiers = relationship("MenuModifier", secondary="item_modifier_group")

class MenuNameVariant(Base):
    """Maps natural language to specific PLUs."""
    __tablename__ = "menu_name_variants"
    
    id = Column(Integer, primary_key=True)
    variant_phrase = Column(String(255))  # "cali roll"
    canonical_name = Column(String(255))  # "California Roll" 
    target_plu = Column(String(50))       # "PLU_CALI_001"
```

## 8. Menu Matching with Cache

### app/utils/menu_matcher_cache_async.py
```python
class AsyncCachedMenuMatcher:
    """Matches natural language to menu items with caching."""
    
    async def match_menu_item(self, query: str) -> Optional[Dict]:
        """Three-tier matching strategy."""
        # 1. Try exact match (fastest)
        exact_match = await self._exact_match(query)
        if exact_match:
            return exact_match
            
        # 2. Try fuzzy match
        fuzzy_match = await self._fuzzy_match(query)
        if fuzzy_match and fuzzy_match["confidence"] > 0.8:
            return fuzzy_match
            
        # 3. Use AI matching (most accurate)
        return await self._ai_match(query)
    
    async def _ai_match(self, query: str) -> Optional[Dict]:
        """Use GPT-4 to match menu items."""
        items = await self._get_all_items()
        
        prompt = f"""
        Customer asked for: "{query}"
        
        Available menu items:
        {json.dumps([{"name": i.name, "plu": i.plu} for i in items])}
        
        Which item best matches? Return the PLU.
        """
        
        # Call OpenAI and return matched item
```

## 9. Order Models

### app/models/order_async.py
```python
class Order(Base):
    """Order model for database storage."""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True)
    deliverect_channel_order_id = Column(String(255), unique=True)
    customer_phone = Column(String(50))
    order_type = Column(String(50))  # delivery, pickup
    status = Column(String(50))
    total_price = Column(Integer)  # In cents
    
    # Relationships
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    """Individual items within an order."""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_item_plu = Column(String(50))  # Links to menu via PLU
    quantity = Column(Integer)
    price = Column(Integer)
    
    # Relationships
    modifiers = relationship("OrderItemModifier")
```

## 10. Deliverect Integration

### app/utils/deliverect/orders_async.py
```python
async def submit_order_to_deliverect(order_data: Dict) -> Dict:
    """Submit order to Deliverect POS system."""
    
    # Format order for Deliverect
    deliverect_order = {
        "channelOrderId": order_data["order_id"],
        "channelName": settings.DELIVERECT_CHANNEL_NAME,
        "orderType": order_data["order_type"],
        "customer": {
            "name": order_data["customer_name"],
            "phone": order_data["customer_phone"]
        },
        "items": [
            {
                "plu": item["plu"],  # Critical - must match POS
                "name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "modifiers": [
                    {
                        "plu": mod["plu"],
                        "name": mod["name"],
                        "price": mod["price"]
                    }
                    for mod in item.get("modifiers", [])
                ]
            }
            for item in order_data["items"]
        ],
        "payment": {
            "amount": order_data["total_price"],
            "type": order_data.get("payment_type", "cash")
        }
    }
    
    # Submit to Deliverect API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.DELIVERECT_BASE_URL}/orders",
            json=deliverect_order,
            headers={"Authorization": f"Bearer {settings.DELIVERECT_API_KEY}"}
        )
        
    return response.json()
```

## 11. Database Configuration

### app/db_async.py
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

## 12. Configuration Management

### app/config.py
```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings from environment."""
    
    # Database
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6380/0"
    
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_REALTIME_MODEL: str = "gpt-4o-realtime-preview-2024-10-01"
    OPENAI_REALTIME_VOICE: str = "shimmer"
    
    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    
    # Deliverect
    DELIVERECT_API_KEY: str
    DELIVERECT_CHANNEL_NAME: str
    DELIVERECT_BASE_URL: str = "https://api.staging.deliverect.com"
    
    # Application
    VOICE_HANDLER: str = "conversation_relay"  # or "realtime"
    FASTAPI_ENV: str = "development"
    
    class Config:
        env_file = ".env.development"

settings = Settings()
```

## Key Architecture Decisions

1. **Async Throughout**: Every I/O operation uses async/await
2. **No Hardcoded Keywords**: All intent detection uses LLM
3. **PLU-Based Integration**: Menu items linked to POS via PLU codes
4. **Multi-Agent Architecture**: Specialized agents for different tasks
5. **FSM for Flow Control**: Explicit state management
6. **ConversationRelay**: Reliable webhook-based voice handling
7. **Three-Tier Menu Matching**: Exact → Fuzzy → AI
8. **Redis Caching**: For menu data and conversation state
9. **PostgreSQL**: Source of truth for all data
10. **Test Strategy**: Unit → Integration → E2E (staging only)

## Critical Integration Points

1. **Twilio → FastAPI**: Via ConversationRelay webhook or WebSocket
2. **FastAPI → OpenAI**: For transcription, TTS, and AI responses
3. **FastAPI → Deliverect**: For menu updates and order submission
4. **FSM ↔ Agents**: State-based agent selection and handoffs
5. **Cache ↔ Database**: Redis caches PostgreSQL data

## Testing Approach

- **Development**: Heavy mocking, unit and integration tests
- **Staging**: Real services, end-to-end tests
- **No mocks in E2E**: Use real Twilio, OpenAI, Deliverect (sandbox)

This system is designed to handle natural voice conversations for restaurant ordering with high reliability and flexibility.