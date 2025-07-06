# RedBarSushiAI System Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [AI Agent System Prompts](#ai-agent-system-prompts)
3. [Agent Orchestration Logic](#agent-orchestration-logic)
4. [Conversation Flow Management](#conversation-flow-management)
5. [State Management and FSM](#state-management-and-fsm)
6. [Tool Calling Mechanisms](#tool-calling-mechanisms)
7. [Voice Processing Architecture](#voice-processing-architecture)
8. [Database Integration](#database-integration)
9. [Key Architectural Patterns](#key-architectural-patterns)

## Overview

RedBarSushiAI is a sophisticated AI-powered voice ordering system that combines hierarchical state machines (HSM) with specialized AI agents to enable natural language phone ordering. The system uses OpenAI's GPT models for intelligent conversation management and tool calling.

### Core Components
- **Multi-Agent System**: Specialized AI agents for different conversation aspects
- **Hierarchical State Machine**: Fluid conversation state management
- **Voice Processing**: Twilio ConversationRelay for reliable audio handling
- **Tool System**: Standardized tool calling for database operations
- **Intent Detection**: LLM-based understanding of user intentions

## AI Agent System Prompts

### 1. Frontline Voice Agent (`AsyncFrontlineVoiceAgentAI`)

**Primary Instructions:**
```
You are {RESTAURANT_GREETING_NAME} from {RESTAURANT_NAME}, taking phone orders. Be warm, friendly, and efficient.

KEY TASKS:
1. Get customer name ONLY when in GREETING state
2. Take orders accurately when in MAIN_MENU or ORDERING states
3. Use tools to lookup menu items and manage cart
4. Keep responses short (1-2 sentences)

REMEMBER: Be conversational, accurate with menu/prices, use tools for everything.
```

**State-Specific Guidance:**

*GREETING State:*
```
The customer just responded to your greeting.

CRITICAL: Look for their name in their response: "{input_text}"

If you detect a name, you MUST:
1. IMMEDIATELY call the update_customer_info tool with {"name": "detected_name"}
2. THEN respond with "Nice to meet you, [name]! How can I help you today?"

Common name patterns to look for:
- Single word like "Bruce" → extract "Bruce" and call update_customer_info({"name": "Bruce"})
- "My name is Sarah" → extract "Sarah" and call update_customer_info({"name": "Sarah"})
- "I'm John" → extract "John" and call update_customer_info({"name": "John"})

IMPORTANT: Even if the input is just a single word that could be a name, treat it as a name and call the tool!
```

*MAIN_MENU State:*
```
CRITICAL CONTEXT: You are in the MAIN MENU phase after greeting is complete.

Customer name: {customer_name}
User input: "{input_text}"

INTELLIGENT ANALYSIS REQUIRED:

1. FIRST: Analyze if this is a NAME CORRECTION
   - If the customer is correcting/updating their name, call update_customer_info tool
   - Acknowledge the correction naturally and ask how you can help

2. SECOND: If this is about FOOD/ORDERING
   - Use add_to_cart tool for specific items
   - Use menu tools for questions about items/categories

3. THIRD: For other requests
   - Answer questions helpfully
   - Guide them toward ordering when appropriate

Use your AI intelligence to determine the user's TRUE intent. Do not rely on keyword matching.
```

*ORDERING State:*
```
CRITICAL CONTEXT: You are in the ACTIVE ORDERING phase.

Customer: {customer_name} (name already confirmed)
Current cart: {order_items}

User input: "{input_text}"

INTELLIGENT ORDER PROCESSING RULES:
1. NEW FOOD ITEMS mentioned → Use add_to_cart tool with the specific item name
2. QUANTITY changes to existing items → Use appropriate cart modification tools
3. MENU QUESTIONS about items/prices → Use lookup_menu_item tool
4. ORDER COMPLETION signals → NEVER use add_to_cart, just acknowledge politely

CRITICAL - NEVER ADD ITEMS WHEN USER INDICATES COMPLETION:
- If user says they're done, finished, that's all, etc. → DO NOT add anything to cart
- Completion means they want to STOP ADDING and move to checkout
- Your role is to understand intent accurately using context clues

Customer name is ALREADY SET: {customer_name} - never change this.
```

### 2. Menu Agent (`AsyncMenuAgentEnhanced`)

**Primary Instructions:**
```
You are a menu specialist for {RESTAURANT_NAME}. Your role is to help customers
understand our menu, make recommendations, and answer questions about our dishes.

KEY RESPONSIBILITIES:
1. Provide accurate information about menu items, prices, and ingredients
2. Make personalized recommendations based on preferences
3. Explain dishes in an appetizing way
4. Help with dietary restrictions and allergies
5. Suggest popular items and good combinations

MENU KNOWLEDGE:
- Use the lookup tools to get accurate, real-time menu information
- Never make up dishes or prices
- Always check availability before recommending
- Be aware of modifier options (size, spice level, extras)

COMMUNICATION STYLE:
- Enthusiastic about the food
- Descriptive but concise
- Helpful with suggestions
- Knowledgeable about Japanese cuisine

IMPORTANT RULES:
- Only recommend items that actually exist in our database
- Always provide accurate prices
- Mention if items are unavailable or snoozed
- Be helpful with substitutions for dietary needs
```

### 3. Cart Agent (`AsyncCartAgent`)

**Primary Instructions:**
```
Cart specialist. Be FAST and ACCURATE.

For any order:
1. lookup_menu_item(item_name="[item name]")
2. add_item_to_cart(plu=result, quantity=[number])
3. Confirm what was added

For "that's all": get_current_cart() and confirm total.
For menu questions: Direct them to specific items or categories.

BE BRIEF. USE TOOLS. ADD TO CART.
```

**Extended State Guidance:**
```
You are the cart specialist. Your job is to:
1. Identify menu items the customer wants to order
2. Extract quantities (default to 1 if not specified)
3. Use the lookup_menu_item tool to verify each item exists
4. Use the add_item_to_cart tool to add valid items
5. Provide a friendly confirmation of what was added

If the customer says things like "that's all", "done", "ready to checkout", 
acknowledge their order is complete and summarize their cart.

IMPORTANT: Always use your tools to look up and add items. Don't just respond
without actually processing the order.
```

## Agent Orchestration Logic

### 1. Agent Selection Process (`AsyncAgentOrchestrator`)

The orchestrator selects agents based on the current HSM state:

```python
# Core selection logic in _process_with_appropriate_agent()

if current_state in [ConversationHSMStates.MAIN_MENU, ConversationHSMStates.GREETING]:
    if context.get("requesting_menu_info", False):
        # Use menu agent for menu inquiries
        agent = self.menu_agent
        response = await agent.process_input(input_text, agent_context)
    else:
        # Use frontline agent for main menu and greeting
        agent_context["hsm_state"] = current_state
        agent_context["state_transition_occurred"] = True
        agent = self.frontline_agent
        response = await agent.process_voice_input(input_text, agent_context)

elif current_state.startswith("ACTIVE.ORDERING"):
    # Use cart agent for order management
    agent = self.cart_agent
    response = await agent.process_input(input_text, agent_context)
    
    # Synchronize cart data
    conversation = await async_agents_conversation_store.get_conversation(call_sid)
    cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
    context["cart"] = cart  # Update shared context

elif current_state == ConversationHSMStates.VALIDATION:
    # Use guardrail agent for validation
    agent = self.guardrail_agent
    response = await agent.process_input(input_text, agent_context)

elif current_state.startswith("ACTIVE.CONFIRMATION"):
    # Use frontline agent for confirmation
    agent_context["cart"] = context.get("cart", {"items": [], "total_price": 0})
    agent = self.frontline_agent
    response = await agent.process_voice_input(input_text, agent_context)
```

### 2. Agent Factory and Registration

```python
class AsyncAgentFactory:
    def __init__(self):
        # Register AI-enhanced agents if enabled
        use_ai_agents = getattr(settings, 'USE_AI_AGENTS', True)
        if use_ai_agents:
            self.register_agent_class("frontline", AsyncFrontlineVoiceAgentAI)
            self.register_agent_class("menu", AsyncMenuAgentEnhanced)
        
        self.register_agent_class("cart", AsyncCartAgent)
        self.register_agent_class("guardrail", AsyncGuardrailAgent)
        self.register_agent_class("fulfillment", AsyncFulfillmentAgent)
        self.register_agent_class("escalation", AsyncEscalationAgent)
    
    async def create_voice_agent_system(self, db=None):
        # Create frontline agent with specialist registration
        frontline_agent = await self.get_agent("frontline")
        menu_agent = await self.get_agent("menu", db=db)
        cart_agent = await self.get_agent("cart", db=db)
        
        # Register specialists with frontline agent
        frontline_agent.register_specialist("menu", menu_agent)
        frontline_agent.register_specialist("cart", cart_agent)
        
        return frontline_agent
```

## Conversation Flow Management

### 1. Voice Input Processing Flow

```python
async def process_voice_input(self, call_sid: str, input_text: str, context: Dict[str, Any]):
    # 1. Initialize session and HSM if needed
    if call_sid not in self.active_sessions:
        await self.initialize_hsm(call_sid, context)
    
    # 2. Add user message to conversation store
    await self.conversation_store.add_message(call_sid, "user", input_text)
    
    # 3. Get current HSM state
    current_states = await hsm_manager.get_current_states(call_sid)
    current_leaf = current_states[-1] if current_states else ConversationHSMStates.INITIAL
    
    # 4. Handle first interaction
    if context.get("first_interaction") and current_leaf == ConversationHSMStates.INITIAL:
        start_event = HSMEvent(ConversationHSMEvents.START_CONVERSATION, context)
        await hsm_manager.handle_event(call_sid, start_event, context)
    
    # 5. Check for global commands
    if not context.get("first_interaction"):
        global_cmd, confidence = await intent_detector.detect_global_command(input_text)
        if global_cmd != GlobalCommand.NONE and confidence >= 0.8:
            response = await self._handle_global_command(global_cmd, call_sid, context)
            if response:
                return response
    
    # 6. Process with HSM for state transitions
    event = await self._detect_hsm_event(input_text, current_leaf, context)
    if event:
        new_leaf = await hsm_manager.handle_event(call_sid, event, context)
        if new_leaf:
            current_leaf = new_leaf
    
    # 7. Select and process with appropriate agent
    agent, response = await self._process_with_appropriate_agent(current_leaf, input_text, context)
    
    # 8. Update session state and return response
    self.active_sessions[call_sid]["state"] = current_leaf
    return response
```

### 2. Agent Communication Patterns

**Delegation Pattern:**
```python
async def delegate_to_specialist(self, role: str, input_text: str, context: Dict[str, Any]):
    if role in self.specialists:
        specialist = self.specialists[role]
        specialist_context = context.copy()
        specialist_context["delegated_by"] = self.name
        response = await specialist.process_input(input_text, specialist_context)
        return response
```

**Tool Execution Pattern:**
```python
async def execute_tool(self, tool_name: str, args: Dict[str, Any]):
    if tool_name == "lookup_menu_item":
        return await self._lookup_menu_item(args.get("item_name", ""))
    elif tool_name == "add_to_cart":
        return await self._add_to_cart(args.get("plu"), args.get("quantity", 1))
```

## State Management and FSM

### 1. Hierarchical State Machine Structure

**State Hierarchy:**
```
INITIAL
ACTIVE/
├── GREETING
├── MAIN_MENU  
├── ORDERING/
│   ├── BROWSING
│   ├── MENU_INQUIRY
│   ├── ITEM_CUSTOMIZATION
│   ├── CART_REVIEW
│   └── VALIDATION
├── VALIDATION
├── CONFIRMATION/
│   ├── REVIEW
│   ├── MODIFY
│   ├── PAYMENT
│   └── DELIVERY
├── FULFILLMENT/
│   ├── PROCESSING
│   ├── TRACKING
│   └── DELIVERY
├── FOLLOW_UP
└── ESCALATION
COMPLETION
ERROR_RECOVERY/
├── RETRY
├── FALLBACK
└── ESCALATION
```

### 2. Event Detection and Processing

**Intent Detection (LLM-based):**
```python
class AsyncIntentDetector:
    async def detect_intent(self, transcript: str, current_state: ConversationState, context: Dict[str, Any]):
        # Build state-specific system prompt
        system_prompt = self._build_system_prompt(current_state)
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.1,  # Low temperature for consistent intent detection
            max_tokens=50
        )
        
        intent = response.choices[0].message.content.strip().upper()
        event = self._map_intent_to_event(intent, current_state)
        return event
```

**State-Specific Intent Mappings:**
```python
# GREETING state intents
"PROVIDE_NAME": ConversationEvent.USER_PROVIDES_NAME,
"SKIP_NAME": ConversationEvent.USER_PROVIDES_NAME,
"REQUEST_ESCALATION": None

# MAIN_MENU state intents  
"START_ORDER": ConversationEvent.START_ORDER,
"REQUEST_MENU": ConversationEvent.REQUEST_MENU_INFO,
"REQUEST_HUMAN": ConversationEvent.REQUEST_ESCALATION,

# ORDERING state intents
"ADD_ITEM": None,  # Handled by cart agent
"COMPLETE_ORDER": ConversationEvent.COMPLETE_ORDER,
"CANCEL_ORDER": ConversationEvent.CANCEL_ORDER,
```

### 3. State Transition Logic

**HSM Manager Event Processing:**
```python
async def handle_event(self, call_sid: str, event: HSMEvent, context: Dict[str, Any]):
    # Get current state configuration
    current_path = await self.state_store.get_current_state_path(call_sid)
    
    # Process event from leaf to root (bubbling)
    for i in range(len(current_path) - 1, -1, -1):
        state_name = current_path[i]
        
        # Check for transitions from this state
        transition_key = f"{state_name}:{event.name}"
        transitions = self.transitions.get(transition_key, [])
        
        for transition in transitions:
            if transition.guard and not await transition.guard(event, context):
                continue
            
            # Found valid transition
            target_state = transition.target_state
            handled = True
            break
        
        if not handled:
            # Let state handler process the event
            handler = self.handlers.get(state_name)
            if handler:
                handler_target = await handler.handle_event(event, context)
                if handler_target:
                    target_state = handler_target
                    handled = True
    
    # Perform transition if needed
    if target_state:
        await self._transition_to(call_sid, target_state, event, context)
        return await self.state_store.get_leaf_state(call_sid)
```

### 4. State Handler Examples

**Greeting State Handler:**
```python
class GreetingHSMHandler(HSMStateHandler):
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]):
        if event.name == ConversationHSMEvents.USER_PROVIDES_NAME:
            # Transition to MAIN_MENU - agent handles name extraction
            return ConversationHSMStates.MAIN_MENU
        elif event.name == ConversationHSMEvents.REQUEST_MENU_INFO:
            return ConversationHSMStates.MAIN_MENU
        elif event.name == ConversationHSMEvents.START_ORDER:
            return ConversationHSMStates.ORDERING
        return None
```

**Ordering Superstate Handler:**
```python
class OrderingSuperStateHandler(HSMStateHandler):
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None):
        # Initialize cart if not present
        if "cart" not in context:
            context["cart"] = {"items": [], "total_price": 0.0, "item_count": 0}
    
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]):
        if event.name == "CLEAR_CART":
            context["cart"]["items"] = []
            return ConversationHSMStates.ORDERING_BROWSING
        elif event.name == "CHECKOUT":
            if context["cart"]["item_count"] > 0:
                return ConversationHSMStates.CONFIRMATION
        return None
```

## Tool Calling Mechanisms

### 1. AI Mixin Tool Processing

**Tool Execution Flow:**
```python
class AIIntelligenceMixin:
    async def _process_ai_response(self, response: Any, context: Dict[str, Any]):
        message = response.choices[0].message
        
        # Handle tool calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_results = []
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Execute tool using the agent's execute_tool method
                if hasattr(self, 'execute_tool'):
                    result = await self.execute_tool(tool_name, tool_args)
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
            
            # Get final response after tool execution
            return await self._get_final_response_after_tools(message, tool_results, context)
```

**Tool Result Processing:**
```python
async def _get_final_response_after_tools(self, original_message, tool_results, context):
    # Build follow-up messages including tool results
    messages = self._build_messages("", context)
    messages.append(original_message.model_dump())
    
    # Add tool results
    for i, result in enumerate(tool_results):
        messages.append({
            "role": "tool",
            "tool_call_id": original_message.tool_calls[i].id,
            "content": json.dumps(convert_decimals(result["result"]))
        })
    
    # Get final response
    final_response = await client.chat.completions.create(
        model=self._model,
        messages=messages,
        temperature=0.1,
        max_tokens=tool_response_max_tokens
    )
    
    return {
        "text": final_response.choices[0].message.content,
        "tool_results": tool_results,
        "actions": self._extract_actions_from_tools(tool_results)
    }
```

### 2. Tool Definitions

**Frontline Agent Tools:**
```python
{
    "type": "function",
    "function": {
        "name": "lookup_menu_item",
        "description": "Look up information about a specific menu item",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item to look up"
                }
            },
            "required": ["item_name"]
        }
    }
},
{
    "type": "function", 
    "function": {
        "name": "add_to_cart",
        "description": "Add an item to the customer's order",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string"},
                "quantity": {"type": "integer", "default": 1},
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of modifiers (e.g., 'spicy', 'no wasabi')"
                }
            },
            "required": ["item_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "update_customer_info",
        "description": "Update customer information",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "order_type": {
                    "type": "string", 
                    "enum": ["pickup", "delivery"]
                }
            }
        }
    }
}
```

**Cart Agent Tools:**
```python
{
    "type": "function",
    "function": {
        "name": "add_item_to_cart",
        "description": "Add an item to the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {
                "plu": {"type": "string", "description": "The PLU code of the menu item"},
                "quantity": {"type": "integer"},
                "modifiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "plu": {"type": "string"},
                            "quantity": {"type": "integer"}
                        },
                        "required": ["plu", "quantity"]
                    }
                },
                "special_instructions": {"type": "string"}
            },
            "required": ["plu", "quantity"]
        }
    }
}
```

### 3. Tool Implementation Examples

**Menu Lookup with Disambiguation:**
```python
async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
    # Use menu matcher to find all matching items
    matcher = AsyncMenuMatcher(self.db)
    await matcher.initialize()
    matches = await matcher.find_all_matching_items(item_name, threshold=0.5)
    
    if not matches:
        return {"found": False, "search_term": item_name}
    
    # Check if disambiguation is needed
    if len(matches) > 1:
        options = []
        for match in matches[:5]:
            options.append({
                'name': match.get('name', ''),
                'price': match.get('price', 0),
                'confidence': match.get('confidence', 0)
            })
        
        clarification = f"I found multiple items matching '{item_name}'. Which one did you mean?\n\n"
        for i, option in enumerate(options, 1):
            clarification += f"{i}. {option['name']} - ${option['price']:.2f}\n"
        
        return {
            "found": False,
            "needs_disambiguation": True,
            "clarification_needed": clarification,
            "candidates": options
        }
    
    # Single best match found
    best_match = matches[0]
    return {
        "found": True,
        "item": {
            "name": best_match.get("name"),
            "plu": best_match.get("plu"),
            "price": f"${best_match.get('price', 0):.2f}",
            "description": best_match.get("description", ""),
            "available": best_match.get("is_available", True)
        }
    }
```

**Cart Management:**
```python
async def _add_item_to_cart(self, plu: str, quantity: int = 1, modifiers: List[Dict] = None):
    call_sid = self._get_current_call_sid()
    
    # Validate the item exists
    item = await async_menu_db_store.get_item_by_plu(plu, self.db)
    if not item:
        return {"success": False, "message": f"Item with PLU {plu} not found"}
    
    # Create new item entry
    new_item = {
        "plu": plu,
        "name": item.get("name", ""),
        "price": item.get("price", 0),
        "quantity": quantity,
        "modifiers": validated_modifiers,
        "special_instructions": special_instructions
    }
    
    # Get current cart and update
    conversation = await async_agents_conversation_store.get_conversation(call_sid)
    cart = conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
    
    # Check for existing item (same PLU and modifiers)
    item_found = False
    for existing_item in cart["items"]:
        if (existing_item.get("plu") == plu and 
            existing_item.get("modifiers") == validated_modifiers):
            existing_item["quantity"] += quantity
            item_found = True
            break
    
    if not item_found:
        cart["items"].append(new_item)
    
    # Calculate total price
    total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in cart["items"])
    cart["total_price"] = total_price
    
    # Save updated cart
    conversation["context"]["cart"] = cart
    await async_agents_conversation_store.save_conversation(call_sid, conversation)
    
    return {
        "success": True,
        "message": f"Added {quantity} {item.get('name')} to cart",
        "total_price": total_price,
        "items": cart["items"]
    }
```

## Voice Processing Architecture

### 1. Twilio ConversationRelay Integration

**HTTP Webhook-Based Processing:**
- No WebSocket connections required
- Built-in retries and error handling
- Reliable audio chunk delivery
- TwiML generation for call routing

**Audio Processing Flow:**
```python
# Voice input processing endpoint
@app.post("/voice/process")
async def process_voice_input(request: VoiceInputRequest):
    # 1. Receive audio chunk from Twilio
    # 2. Process with orchestrator
    response = await async_agent_orchestrator.process_voice_input(
        call_sid=request.call_sid,
        input_text=request.transcript,
        context=request.context
    )
    
    # 3. Generate TwiML response for TTS
    twiml = generate_twiml_response(response["text"])
    return twiml
```

### 2. Streaming Response Support

**AI Streaming Implementation:**
```python
async def process_with_ai_streaming(self, input_text, context, callback):
    # Enable streaming for faster response times
    params = {
        "model": self._model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": effective_max_tokens,
        "stream": True  # Enable streaming
    }
    
    # Create streaming completion
    stream = await client.chat.completions.create(**params)
    
    # Collect and stream response
    full_response = ""
    sentence_buffer = ""
    
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            sentence_buffer += token
            
            # Send complete sentences via callback
            if any(ender in sentence_buffer for ender in [".", "!", "?", ":", "\n"]):
                if callback:
                    await callback(sentence_buffer.strip(), False)
                sentence_buffer = ""
    
    # Send final chunk
    if sentence_buffer.strip() and callback:
        await callback(sentence_buffer.strip(), True)
    
    return {"text": full_response, "streamed": True}
```

## Database Integration

### 1. Async SQLAlchemy 2.0 Architecture

**Connection Management:**
```python
# Async engine configuration with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DATABASE_DEBUG
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with async_session_factory() as session:
        yield session
```

**Menu Data Relationships:**
```python
# Critical PLU-based menu matching
MenuItem ← PLU → MenuNameVariant

# Menu models with async support
class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True)
    plu = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("menu_categories.id"))
    is_available = Column(Boolean, default=True)
    snoozed_until = Column(DateTime, nullable=True)
    
    # Relationships
    category = relationship("MenuCategory", back_populates="items")
    modifier_groups = relationship("ModifierGroup", secondary="item_modifier_groups")
```

### 2. Menu Matching and PLU System

**Async Menu Matcher:**
```python
class AsyncMenuMatcher:
    async def find_all_matching_items(self, item_name: str, threshold: float = 0.5):
        # Use fuzzy matching with PLU validation
        potential_matches = await self._fuzzy_search(item_name)
        
        validated_matches = []
        for match in potential_matches:
            if match["confidence"] >= threshold:
                # Validate PLU exists and item is available
                item = await get_item_by_plu(self.db, match["plu"])
                if item and item.is_available and not item.snoozed_until:
                    validated_matches.append({
                        "name": item.name,
                        "plu": item.plu,
                        "price": float(item.price),
                        "description": item.description,
                        "category": item.category.name if item.category else "",
                        "confidence": match["confidence"],
                        "is_available": True
                    })
        
        return sorted(validated_matches, key=lambda x: x["confidence"], reverse=True)
```

### 3. Cart and Order Management

**Redis-Based Session Storage:**
```python
class AsyncAgentsConversationStore:
    async def get_conversation(self, call_sid: str) -> Dict[str, Any]:
        conversation_json = await self.redis.get(f"conversation:{call_sid}")
        if conversation_json:
            return json.loads(conversation_json)
        return {"messages": [], "context": {}}
    
    async def save_conversation(self, call_sid: str, conversation: Dict[str, Any]):
        conversation_json = json.dumps(conversation, default=self._json_serializer)
        await self.redis.setex(
            f"conversation:{call_sid}", 
            self.ttl, 
            conversation_json
        )
    
    async def get_cart(self, call_sid: str) -> Dict[str, Any]:
        conversation = await self.get_conversation(call_sid)
        return conversation.get("context", {}).get("cart", {"items": [], "total_price": 0})
```

## Key Architectural Patterns

### 1. Async-First Design
- All I/O operations use async/await
- Non-blocking database and API calls
- Concurrent tool execution where possible
- Streaming response support for faster UX

### 2. Dependency Injection
- FastAPI's dependency system for database sessions
- Redis connection management
- Agent factory pattern for instance creation
- Service layer separation

### 3. Event-Driven Architecture
- HSM event processing for state transitions
- Intent detection triggers appropriate events
- Tool calling results generate actions
- Global command handling across states

### 4. AI-Only Decision Making
- No hardcoded keyword matching
- LLM-based intent detection for all decisions
- Context-aware prompt engineering
- Dynamic response generation

### 5. Hierarchical State Management
- Nested state structures for complex flows
- Event bubbling from leaf to root states
- State-specific handler registration
- Graceful error recovery patterns

### 6. Tool-Based Architecture
- Standardized tool calling interface
- Database operations abstracted through tools
- Agent specialization through tool sets
- Disambiguation handling in tool responses

### 7. Context Preservation
- Redis-based session storage
- Conversation history maintenance
- Cart state synchronization across agents
- Customer information persistence

This architecture enables RedBarSushiAI to handle complex voice ordering scenarios with natural language understanding, robust state management, and reliable voice processing, all while maintaining scalability and maintainability through its modular design.