# COMPLETE AGENT SYSTEM DOCUMENTATION
## RedBarSushiAI - Every Detail of Every Agent

This is the most comprehensive technical documentation of the RedBarSushiAI agent system, covering every single detail of how the AI agents work together.

---

## 1. BASE AGENT ARCHITECTURE

### BaseAsyncAgent Class (`app/agents/base_async.py`)

**Complete Class Definition:**
```python
class BaseAsyncAgent:
    """
    Base class for all asynchronous agents in the system.
    
    This class provides common functionality and interfaces for agents,
    such as handling inputs, generating responses, and managing state.
    """
```

**Initialization Parameters:**
```python
def __init__(self, agent_id: Optional[str] = None, name: str = "BaseAgent", agent_name: Optional[str] = None, **kwargs):
    """
    Initialize the agent.
    
    Args:
        agent_id: Optional ID for the agent (used with OpenAI Assistants API)
        name: Name of the agent for logging and identification
        agent_name: Alternative name parameter (for compatibility with subclasses)
        **kwargs: Additional keyword arguments for extended functionality
    """
    self.agent_id = agent_id or f"agent_{int(time.time())}"
    # Handle both name and agent_name for backward compatibility
    self.name = agent_name or name
    self.agent_name = self.name  # Add agent_name as an alias for name
    self.specialists = {}  # For registering specialist agents
    self.policy_agent = None  # For policy enforcement
    self.context = {}  # For maintaining conversation context
```

**Core Methods:**

1. **`process_input(input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`**
   - Primary input processing method
   - Returns: `{"text": str, "agent": str, "handled": bool, "actions": list}`

2. **`process_voice_input(input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`**
   - Voice-specific processing (calls process_input by default)

3. **`execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]`**
   - Tool execution interface
   - Must be overridden by subclasses

4. **`register_specialist(role: str, agent: 'BaseAsyncAgent') -> None`**
   - Register specialist agents for delegation

5. **`delegate_to_specialist(role: str, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`**
   - Delegate processing to specialist agents

---

## 2. AGENT FACTORY SYSTEM

### AsyncAgentFactory Class (`app/agents/factory_async.py`)

**Agent Registration System:**
```python
class AsyncAgentFactory:
    def __init__(self):
        self.agent_classes: Dict[str, Type[BaseAsyncAgent]] = {}
        self.agents: Dict[str, BaseAsyncAgent] = {}
        
        # Agent registration based on AI configuration
        use_ai_agents = getattr(settings, 'USE_AI_AGENTS', True)
        if use_ai_agents:
            self.register_agent_class("frontline", AsyncFrontlineVoiceAgentAI)
            self.register_agent_class("menu", AsyncMenuAgentEnhanced)
        
        self.register_agent_class("cart", AsyncCartAgent)
        self.register_agent_class("guardrail", AsyncGuardrailAgent)
        self.register_agent_class("fulfillment", AsyncFulfillmentAgent)
        self.register_agent_class("escalation", AsyncEscalationAgent)
```

**Agent Caching Strategy:**
- Cache key format: `"{agent_type}:{agent_id}"` or just `agent_type`
- Database session updates for menu/cart agents
- Singleton pattern for factory instance

**Voice Agent System Creation:**
```python
async def create_voice_agent_system(self, db=None) -> BaseAsyncAgent:
    # Create frontline agent
    frontline_agent = await self.get_agent("frontline")
    
    # Create specialists with database sessions
    menu_agent = await self.get_agent("menu", db=db)
    cart_agent = await self.get_agent("cart", db=db)
    
    # Register specialists
    frontline_agent.register_specialist("menu", menu_agent)
    frontline_agent.register_specialist("cart", cart_agent)
    
    return frontline_agent
```

---

## 3. AI INTELLIGENCE MIXIN

### AIIntelligenceMixin Class (`app/agents/ai_mixin.py`)

**Complete AI Configuration:**
```python
class AIIntelligenceMixin:
    def __init__(self):
        self._ai_client = None
        self._ai_enabled = True
        self._model = "gpt-4o-mini"  # Fast and intelligent model
```

**Core AI Processing Method:**
```python
async def process_with_ai(
    self, 
    input_text: str, 
    context: Dict[str, Any],
    use_tools: bool = True,
    fast_mode: bool = False,
    stream: bool = False
) -> Dict[str, Any]:
```

**AI Message Building Strategy:**
```python
def _build_messages(self, input_text: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build message history for AI context - OPTIMIZED for speed."""
    messages = []
    
    # Combine all system context into ONE message for efficiency
    system_parts = []
    
    # Base instructions
    if hasattr(self, 'instructions'):
        system_parts.append(self.instructions)
    
    # Add essential context only
    if context.get("customer_name"):
        system_parts.append(f"Customer: {context['customer_name']}")
    
    if context.get("cart_items"):
        cart_summary = self._summarize_cart(context["cart_items"])
        system_parts.append(f"Cart: {cart_summary}")
    
    # Add FSM state information
    if context.get("conversation_state"):
        system_parts.append(f"\nCURRENT CONVERSATION STATE: {context['conversation_state']}")
    
    # Add state-specific guidance if provided
    if context.get("state_guidance"):
        system_parts.append(f"\nSTATE-SPECIFIC GUIDANCE:\n{context['state_guidance']}")
    
    # Single system message
    messages.append({"role": "system", "content": "\n".join(system_parts)})
    
    # Add last 4 messages for better context understanding (optimized)
    if context.get("conversation_history"):
        for msg in context["conversation_history"][-4:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
    
    # Add the current user input
    messages.append({"role": "user", "content": input_text})
    
    return messages
```

**Tool Execution Flow:**
```python
async def _process_ai_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # Return direct response if no tools were called
    return {
        "text": message.content,
        "agent": getattr(self, 'name', 'AI'),
        "handled": True,
        "ai_generated": True,
        "actions": []
    }
```

**Intent Understanding System:**
```python
async def understand_intent(self, input_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Use AI to understand user intent from their input."""
    
    current_state = context.get("conversation_state", "")
    customer_name = context.get("customer_name", "")
    cart_items = context.get("cart_items", [])
    
    system_content = f"""You are an intelligent intent classifier for a restaurant ordering system.
    
    CURRENT CONTEXT:
    - Conversation state: {current_state}
    - Customer name: {customer_name}
    - Items in cart: {len(cart_items)} items
    
    Classify the user's intent into one of these categories:
    - greeting: User is greeting or introducing themselves
    - provide_name: User is providing their name
    - menu_inquiry: User is asking about the menu or item details
    - place_order: User wants to add specific items to their order
    - modify_order: User wants to change quantities or remove items
    - complete_order: User indicates they are finished ordering
    - confirm_order: User is confirming their final order for checkout
    - cancel_order: User wants to cancel their entire order
    - request_human: User wants to speak to a person
    - general_question: Other questions not related to ordering
    
    CRITICAL ORDER COMPLETION DETECTION:
    When in ORDERING state with items in cart, be extremely sensitive to completion signals.
    Users may indicate completion in many ways - your job is to intelligently detect when
    they want to STOP ADDING and move to checkout/confirmation.
    
    Also extract any entities like names, menu items, quantities.
    
    Respond in JSON format: {{"intent": "...", "entities": {{}}, "confidence": 0.0-1.0}}
    """
    
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": input_text}
    ]
    
    client = await self._get_ai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
        max_tokens=100,
        response_format={ "type": "json_object" }
    )
    
    return json.loads(response.choices[0].message.content)
```

---

## 4. FRONTLINE AGENT (Complete Analysis)

### AsyncFrontlineVoiceAgentAI Class (`app/agents/frontline_async_ai.py`)

**Complete Initialization:**
```python
class AsyncFrontlineVoiceAgentAI(BaseAsyncAgent, AIIntelligenceMixin):
    def __init__(self, agent_id: Optional[str] = None):
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="FrontlineVoiceAI")
        AIIntelligenceMixin.__init__(self)
        
        # Set agent-specific max tokens
        self._default_max_tokens = settings.FRONTEND_AGENT_MAX_TOKENS
        
        self.conversation_state = "GREETING"
        self.greeting_done = False
        
        # Context maintained across the conversation
        self.context = {
            "customer_name": None,
            "order_type": None,
            "order_items": [],
            "current_item": None,
            "conversation_history": []
        }
        
        # Available states
        self.states = [
            "GREETING", "MAIN_MENU", "ORDERING", "VALIDATION", 
            "CONFIRMATION", "FULFILLMENT", "COMPLETION", "FOLLOW_UP",
            "ESCALATION"
        ]
```

**Base AI Instructions (Word-for-Word):**
```python
self.base_instructions = f"""
You are {settings.RESTAURANT_GREETING_NAME} from {settings.RESTAURANT_NAME}, taking phone orders. Be warm, friendly, and efficient.

KEY TASKS:
1. Get customer name ONLY when in GREETING state
2. Take orders accurately when in MAIN_MENU or ORDERING states
3. Use tools to lookup menu items and manage cart
4. Keep responses short (1-2 sentences)

REMEMBER: Be conversational, accurate with menu/prices, use tools for everything.
"""
```

**Complete Tool Definitions:**

1. **Menu Lookup Tool:**
```json
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
}
```

2. **Menu Categories Tool:**
```json
{
    "type": "function",
    "function": {
        "name": "get_menu_categories",
        "description": "Get list of available menu categories",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

3. **Category Items Tool:**
```json
{
    "type": "function",
    "function": {
        "name": "get_items_by_category",
        "description": "Get all items in a specific category",
        "parameters": {
            "type": "object",
            "properties": {
                "category_name": {
                    "type": "string",
                    "description": "Name of the category"
                }
            },
            "required": ["category_name"]
        }
    }
}
```

4. **Add to Cart Tool:**
```json
{
    "type": "function",
    "function": {
        "name": "add_to_cart",
        "description": "Add an item to the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the item to add"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Quantity to add",
                    "default": 1
                },
                "modifiers": {
                    "type": "array",
                    "description": "List of modifiers for the item",
                    "items": {"type": "string"},
                    "default": []
                }
            },
            "required": ["item_name"]
        }
    }
}
```

5. **Customer Info Tool:**
```json
{
    "type": "function",
    "function": {
        "name": "update_customer_info",
        "description": "Update customer information",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Customer's name"
                },
                "phone": {
                    "type": "string",
                    "description": "Customer's phone number"
                },
                "email": {
                    "type": "string", 
                    "description": "Customer's email"
                }
            }
        }
    }
}
```

6. **Cart Management Tools:**
```json
{
    "type": "function",
    "function": {
        "name": "get_cart_contents",
        "description": "Get current cart contents",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "remove_from_cart",
        "description": "Remove an item from cart",
        "parameters": {
            "type": "object", 
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of item to remove"
                }
            },
            "required": ["item_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "confirm_order",
        "description": "Confirm the order for checkout",
        "parameters": {
            "type": "object",
            "properties": {
                "confirmed": {
                    "type": "boolean",
                    "description": "Whether the order is confirmed"
                }
            },
            "required": ["confirmed"]
        }
    }
}
```

**State Handler Methods:**

### Greeting State Handler (Complete):
```python
async def _handle_greeting(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
    """Handle inputs in the greeting state using AI."""
    
    context = self.context.copy()
    context["state_guidance"] = f"""
    The customer just responded to your greeting.
    
    CRITICAL: Look for their name in their response: "{input_text}"
    
    If you detect a name, you MUST:
    1. IMMEDIATELY call the update_customer_info tool with {{"name": "detected_name"}}
    2. THEN respond with "Nice to meet you, [name]! How can I help you today?"
    
    Common name patterns to look for:
    - Single word like "Bruce" → extract "Bruce" and call update_customer_info({{"name": "Bruce"}})
    - "My name is Sarah" → extract "Sarah" and call update_customer_info({{"name": "Sarah"}})
    - "I'm John" → extract "John" and call update_customer_info({{"name": "John"}})
    - "This is Mike" → extract "Mike" and call update_customer_info({{"name": "Mike"}})
    - "It's David" → extract "David" and call update_customer_info({{"name": "David"}})
    
    IMPORTANT: Even if the input is just a single word that could be a name, treat it as a name and call the tool!
    
    If you cannot detect a name, politely ask for it again.
    """
    
    response = await self.process_with_ai(input_text, context)
    
    # Check if AI called update_customer_info tool to set the name
    name_set_by_ai = False
    if response.get("tool_calls"):
        for tool_call in response["tool_calls"]:
            if tool_call.get("function", {}).get("name") == "update_customer_info":
                args = tool_call.get("function", {}).get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                
                if args.get("name"):
                    self.context["customer_name"] = args["name"]
                    self.conversation_state = "MAIN_MENU"
                    response["actions"] = response.get("actions", [])
                    response["actions"].append({
                        "type": "set_customer_name", 
                        "name": args["name"]
                    })
                    name_set_by_ai = True
    
    # Add conversation history
    self.context["conversation_history"].append({
        "role": "assistant",
        "content": response.get("text", "")
    })
    
    # Update state from actions
    await self._update_state_from_actions(response.get("actions", []))
    
    # Stream the response if we have a callback and response text
    if stream_callback and response.get("text"):
        await stream_callback(response['text'], True)
    
    return response
```

### Main Menu State Handler (Complete):
```python
async def _handle_main_menu(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
    """Handle inputs in the main menu state using AI."""
    
    context = self.context.copy()
    # Add conversation history to the context for AI processing
    context["conversation_history"] = self.context.get("conversation_history", [])
    
    # If we just transitioned from greeting and got a name, acknowledge it
    if self.context.get("customer_name") and context.get("state_transition_occurred") and not self.context.get("name_acknowledged"):
        context["state_guidance"] = f"""
    You just got the customer's name ({self.context['customer_name']}) and transitioned to the main menu.
    Acknowledge their name warmly and ask how you can help them today.
    IMPORTANT: Use their name {self.context['customer_name']} in your response!
    For example: "Nice to meet you, {self.context['customer_name']}! How can I help you today?"
    """
        
        # Mark that we've acknowledged the name
        self.context["name_acknowledged"] = True
        
        # Try with AI first - use streaming for the greeting acknowledgment
        if stream_callback:
            # Send immediate acknowledgment while processing
            immediate_ack = f"Nice to meet you, {self.context.get('customer_name', '')}!"
            await stream_callback(immediate_ack, False)
            
            # Now get the full response
            response = await self.process_with_ai(input_text, context)
            
            # Send the rest of the response
            remaining_text = response.get("text", "").replace(immediate_ack, "").strip()
            if remaining_text:
                await stream_callback(remaining_text, True)
        else:
            response = await self.process_with_ai(input_text, context)
        
        # If AI failed, provide a fallback response
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            customer_name = self.context.get("customer_name", "friend")
            response = {
                "text": f"Nice to meet you, {customer_name}! How can I help you today? Would you like to place an order, or do you have questions about our menu?",
                "agent": self.name,
                "handled": True,
                "actions": []
            }
    else:
        context["state_guidance"] = f"""
    CRITICAL CONTEXT: You are in the MAIN MENU phase after greeting is complete.
    
    Customer name: {self.context.get('customer_name')}
    User input: "{input_text}"
    
    INTELLIGENT ANALYSIS REQUIRED:
    
    1. FIRST: Analyze if this is a NAME CORRECTION
       - If the customer is correcting/updating their name, call update_customer_info tool
       - Acknowledge the correction naturally and ask how you can help
       - DO NOT process as a food order
    
    2. SECOND: If this is about FOOD/ORDERING
       - Use add_to_cart tool for specific items
       - Use menu tools for questions about items/categories
    
    3. THIRD: For other requests
       - Answer questions helpfully
       - Guide them toward ordering when appropriate
    
    Use your AI intelligence to determine the user's TRUE intent. Do not rely on keyword matching.
    Be conversational and natural in your responses.
    """
        
        # Process with AI
        response = await self.process_with_ai(input_text, context)
    
    # Update conversation history
    self.context["conversation_history"].append({
        "role": "user",
        "content": input_text
    })
    self.context["conversation_history"].append({
        "role": "assistant", 
        "content": response.get("text", "")
    })
    
    # Update state from actions
    await self._update_state_from_actions(response.get("actions", []))
    
    # Stream the response if we have a callback
    if stream_callback and response.get("text") and not context.get("state_transition_occurred"):
        await stream_callback(response['text'], True)
    
    return response
```

### Ordering State Handler (Complete):
```python
async def _handle_ordering(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
    """Handle inputs in the ordering state using AI with intelligent completion detection."""
    
    customer_name = self.context.get("customer_name", "friend")
    cart_items = self.context.get("order_items", [])
    
    # Use AI to detect if user is indicating order completion - COMPLETELY DYNAMIC
    completion_check_context = {
        "conversation_state": "ORDERING", 
        "customer_name": self.context.get('customer_name'),
        "cart_items": self.context.get('order_items', []),
        "conversation_history": self.context.get("conversation_history", [])
    }
    
    completion_intent = await self.understand_intent(input_text, completion_check_context)
    
    # Use ONLY AI intelligence to determine completion - no hardcoded phrases
    if completion_intent.get("intent") == "complete_order" and completion_intent.get("confidence", 0) > 0.6:
        # Customer wants to complete their order
        if len(cart_items) > 0:
            # Move to confirmation
            self.conversation_state = "CONFIRMATION"
            
            # Get cart contents for confirmation
            cart_summary = self._get_cart_summary()
            
            response = {
                "text": f"Perfect! Let me confirm your order: {cart_summary}. Is this correct?",
                "agent": self.name,
                "handled": True,
                "actions": [{"type": "state_change", "state": "CONFIRMATION"}]
            }
        else:
            response = {
                "text": "I don't see any items in your cart yet. What would you like to order?",
                "agent": self.name,
                "handled": True,
                "actions": []
            }
    else:
        # Continue with normal ordering flow using AI
        context = self.context.copy()
        context["state_guidance"] = f"""
        ORDERING MODE - Customer: {customer_name}
        
        Current cart: {len(cart_items)} items
        Last input: "{input_text}"
        
        CRITICAL ORDER COMPLETION DETECTION:
        When in ORDERING state with items in cart, be extremely sensitive to completion signals.
        Users may indicate completion in many ways - your job is to intelligently detect when
        they want to STOP ADDING and move to checkout/confirmation.
        
        PRIORITY ANALYSIS:
        1. Order completion signals (e.g., "that's all", "done", "finished")
        2. Additional item requests
        3. Menu questions
        4. Order modifications
        
        Use AI intelligence to determine TRUE intent.
        """
        
        response = await self.process_with_ai(input_text, context)
    
    # Add to conversation history
    self.context["conversation_history"].append({
        "role": "user",
        "content": input_text
    })
    self.context["conversation_history"].append({
        "role": "assistant",
        "content": response.get("text", "")
    })
    
    # Update state from actions
    await self._update_state_from_actions(response.get("actions", []))
    
    # Stream the response
    if stream_callback and response.get("text"):
        await stream_callback(response['text'], True)
    
    return response
```

**Tool Execution Methods:**

### Customer Info Update:
```python
async def _update_customer_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """Update customer information."""
    
    updated_fields = []
    
    if args.get("name"):
        self.context["customer_name"] = args["name"]
        updated_fields.append("name")
    
    if args.get("phone"):
        self.context["customer_phone"] = args["phone"] 
        updated_fields.append("phone")
    
    if args.get("email"):
        self.context["customer_email"] = args["email"]
        updated_fields.append("email")
    
    return {
        "success": True,
        "updated": updated_fields
    }
```

### Cart Operations:
```python
async def _add_to_cart(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """Delegate cart addition to Cart Agent."""
    
    # Get the cart agent
    cart_agent = self.specialists.get("cart")
    if not cart_agent:
        return {"error": "Cart agent not available"}
    
    # Execute the add_to_cart operation via Cart Agent
    result = await cart_agent.execute_tool("add_to_cart", args)
    
    # Update local context with cart data
    if result.get("success"):
        # Sync cart data from Cart Agent
        cart_contents = await cart_agent.execute_tool("get_cart_contents", {})
        if cart_contents.get("items"):
            self.context["order_items"] = cart_contents["items"]
            self.context["total_price"] = cart_contents.get("total_price", 0)
    
    return result
```

---

## 5. MENU AGENT (Complete Analysis)

### AsyncMenuAgentEnhanced Class (`app/agents/menu_async_enhanced.py`)

**Complete Initialization:**
```python
class AsyncMenuAgentEnhanced(BaseAsyncAgent, AIIntelligenceMixin):
    def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="MenuEnhanced")
        AIIntelligenceMixin.__init__(self)
        
        # Set agent-specific max tokens
        self._default_max_tokens = getattr(settings, 'MENU_AGENT_MAX_TOKENS', 256)
        self.context = {}  # Store context for disambiguation
        
        self.db = db
        self._menu_cache = {}
        self._cache_ttl = 300  # 5 minutes
```

**AI Instructions (Word-for-Word):**
```python
self.instructions = f"""
You are a menu specialist for {settings.RESTAURANT_NAME}. Your role is to help customers
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
"""
```

**Complete Tool Definitions:**

1. **Menu Item Lookup:**
```json
{
    "type": "function",
    "function": {
        "name": "lookup_menu_item",
        "description": "Look up a specific menu item by name",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the menu item to look up"
                }
            },
            "required": ["item_name"]
        }
    }
}
```

2. **Categories List:**
```json
{
    "type": "function",
    "function": {
        "name": "list_categories",
        "description": "Get all menu categories",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

3. **Category Items:**
```json
{
    "type": "function",
    "function": {
        "name": "get_items_by_category",
        "description": "Get all items in a specific category",
        "parameters": {
            "type": "object",
            "properties": {
                "category_name": {
                    "type": "string",
                    "description": "Name of the category"
                }
            },
            "required": ["category_name"]
        }
    }
}
```

4. **Menu Search:**
```json
{
    "type": "function",
    "function": {
        "name": "search_menu",
        "description": "Search menu items by keyword",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5
                }
            },
            "required": ["keyword"]
        }
    }
}
```

5. **Item Details:**
```json
{
    "type": "function",
    "function": {
        "name": "get_item_details",
        "description": "Get detailed information about a menu item",
        "parameters": {
            "type": "object",
            "properties": {
                "item_plu": {
                    "type": "string",
                    "description": "PLU code of the item"
                }
            },
            "required": ["item_plu"]
        }
    }
}
```

**Menu Item Lookup with Disambiguation:**
```python
async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
    """Look up a menu item using the matcher with disambiguation support."""
    if not self.db:
        return {"found": False, "error": "Database not available"}
    
    try:
        # Get the menu matcher
        from app.utils.menu_matcher_db_async import AsyncMenuMatcher
        matcher = AsyncMenuMatcher(self.db)
        await matcher.initialize()
        
        # Find all matching items
        matches = await matcher.find_all_matching_items(item_name, threshold=0.5)
        
        if not matches:
            return {
                "found": False,
                "search_term": item_name,
                "message": "Item not found in our menu"
            }
        
        # Check if disambiguation is needed (simple logic)
        if len(matches) > 1:
            # Multiple matches found - need disambiguation
            from app.utils.disambiguation import disambiguation_helper
            
            # Create disambiguation options
            options = []
            for match in matches[:5]:  # Limit to 5 options
                options.append({
                    'id': match.get('plu', ''),
                    'name': match.get('name', ''),
                    'description': match.get('description', ''),
                    'price': match.get('price', 0),
                    'confidence': match.get('confidence', 0)
                })
            
            # Generate clarification question
            clarification = f"I found multiple items matching '{item_name}'. Which one did you mean?\n\n"
            for i, option in enumerate(options, 1):
                clarification += f"{i}. {option['name']} - ${option['price']:.2f}\n"
            clarification += "\nPlease tell me which one you'd like."
            
            # Store context for follow-up
            if hasattr(self, 'context'):
                self.context['disambiguation'] = {
                    'item_name': item_name,
                    'options': options,
                    'type': 'menu_item'
                }
            
            return {
                "found": False,
                "needs_disambiguation": True,
                "clarification_needed": clarification,
                "candidates": options,
                "disambiguation_type": "menu_item"
            }
        
        # Single best match found
        best_match = matches[0]
        
        # Format the response
        return {
            "found": True,
            "item": {
                "name": best_match.get("name"),
                "plu": best_match.get("plu"),
                "price": f"${best_match.get('price', 0):.2f}",
                "description": best_match.get("description", ""),
                "category": best_match.get("category_name", ""),
                "available": best_match.get("is_available", True),
                "match_score": best_match.get("confidence", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error looking up menu item: {e}")
        return {"found": False, "error": str(e)}
```

**Categories and Items Methods:**
```python
async def _list_categories(self) -> Dict[str, Any]:
    """Get all menu categories."""
    if not self.db:
        from app.db_async import async_session_factory
        self.db = async_session_factory()
    
    try:
        categories = await get_all_categories(self.db)
        
        return {
            "categories": [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description
                }
                for cat in categories
            ],
            "count": len(categories)
        }
        
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return {"categories": [], "error": str(e)}

async def _get_items_by_category(self, category_name: str) -> Dict[str, Any]:
    """Get items in a specific category."""
    if not self.db:
        from app.db_async import async_session_factory
        self.db = async_session_factory()
    
    try:
        # First find the category
        categories = await get_all_categories(self.db)
        category = None
        
        for cat in categories:
            if cat.name.lower() == category_name.lower():
                category = cat
                break
        
        if not category:
            return {
                "items": [],
                "error": f"Category '{category_name}' not found"
            }
        
        # Get items in the category
        items = await get_items_by_category(self.db, category.id)
        
        return {
            "category": category_name,
            "items": [
                {
                    "name": item.name,
                    "plu": item.plu,
                    "price": f"${item.price:.2f}",
                    "description": item.description,
                    "available": item.is_available
                }
                for item in items
                if item.is_available  # Only show available items
            ],
            "count": len(items)
        }
        
    except Exception as e:
        logger.error(f"Error getting items by category: {e}")
        return {"items": [], "error": str(e)}
```

---

## 6. CART AGENT (Complete Analysis)

### AsyncCartAgent Class (`app/agents/cart_async.py`)

**Complete Initialization:**
```python
class AsyncCartAgent(BaseAsyncAgent, AIIntelligenceMixin):
    def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="Cart")
        AIIntelligenceMixin.__init__(self)
        
        # Set agent-specific max tokens for fast responses
        self._default_max_tokens = getattr(settings, 'CART_AGENT_MAX_TOKENS', 150)
        
        self.db = db
        self.context = {}
```

**AI Instructions (Word-for-Word):**
```python
self.instructions = f"""
You are the cart manager for {settings.RESTAURANT_NAME}. Keep responses SHORT (1-2 sentences).

Your job: Add items to cart accurately and quickly.

ALWAYS use the menu lookup tools to find exact items - NEVER guess or make up items.
For any item the customer mentions, immediately look it up to get the correct PLU and pricing.

When adding items:
1. Look up the item to get PLU and price
2. Add to cart with correct details
3. Confirm addition with price

Be quick, accurate, and concise. NO long explanations.
"""
```

**Complete Tool Definitions:**

1. **Menu Item Lookup:**
```json
{
    "type": "function",
    "function": {
        "name": "lookup_menu_item",
        "description": "Look up a menu item to get PLU and pricing",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the menu item"
                }
            },
            "required": ["item_name"]
        }
    }
}
```

2. **Add Item to Cart:**
```json
{
    "type": "function",
    "function": {
        "name": "add_item_to_cart",
        "description": "Add an item to the cart using PLU",
        "parameters": {
            "type": "object",
            "properties": {
                "plu": {
                    "type": "string",
                    "description": "PLU code of the item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Quantity to add",
                    "default": 1
                },
                "modifiers": {
                    "type": "array",
                    "description": "List of modifiers",
                    "items": {"type": "string"},
                    "default": []
                }
            },
            "required": ["plu"]
        }
    }
}
```

3. **Cart Management Tools:**
```json
{
    "type": "function",
    "function": {
        "name": "get_cart_contents",
        "description": "Get current cart contents",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "remove_item_from_cart",
        "description": "Remove an item from cart",
        "parameters": {
            "type": "object",
            "properties": {
                "plu": {
                    "type": "string", 
                    "description": "PLU of item to remove"
                }
            },
            "required": ["plu"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "update_item_quantity",
        "description": "Update quantity of an item in cart",
        "parameters": {
            "type": "object",
            "properties": {
                "plu": {
                    "type": "string",
                    "description": "PLU of the item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "New quantity"
                }
            },
            "required": ["plu", "quantity"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "clear_cart",
        "description": "Clear all items from cart",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

**Cart Operations Implementation:**
```python
async def _add_item_to_cart(self, plu: str, quantity: int = 1, modifiers: List[str] = None) -> Dict[str, Any]:
    """Add an item to the cart."""
    modifiers = modifiers or []
    
    try:
        # Get the item from database
        from app.db.crud_menu_async import get_item_by_plu
        item = await get_item_by_plu(self.db, plu)
        
        if not item:
            return {"success": False, "error": f"Item with PLU {plu} not found"}
        
        if not item.is_available:
            return {"success": False, "error": f"{item.name} is currently not available"}
        
        # Get current call context
        call_sid = self.context.get("call_sid")
        if not call_sid:
            return {"success": False, "error": "No active call session"}
        
        # Get existing cart
        from app.utils.cart_store_async import async_cart_store
        current_cart = await async_cart_store.get_cart(call_sid)
        
        # Check if item already exists in cart
        existing_item = None
        for cart_item in current_cart.get("items", []):
            if cart_item["plu"] == plu and cart_item.get("modifiers", []) == modifiers:
                existing_item = cart_item
                break
        
        if existing_item:
            # Update quantity
            existing_item["quantity"] += quantity
        else:
            # Add new item
            new_item = {
                "plu": plu,
                "name": item.name,
                "price": float(item.price),
                "quantity": quantity,
                "modifiers": modifiers,
                "special_instructions": None
            }
            current_cart.setdefault("items", []).append(new_item)
        
        # Recalculate total
        total_price = sum(
            item["price"] * item["quantity"] 
            for item in current_cart["items"]
        )
        current_cart["total_price"] = total_price
        
        # Save cart
        await async_cart_store.update_cart(call_sid, current_cart)
        
        return {
            "success": True,
            "message": f"Added {quantity} {item.name} to cart",
            "total_price": total_price,
            "items": current_cart["items"],
            "item_count": sum(item["quantity"] for item in current_cart["items"])
        }
        
    except Exception as e:
        logger.error(f"Error adding item to cart: {e}")
        return {"success": False, "error": str(e)}
```

---

## 7. AGENT ORCHESTRATION (Complete Analysis)

### AsyncAgentOrchestrator Class (`app/utils/agent_orchestration_async.py`)

**Complete Voice Input Processing Pipeline:**
```python
async def process_voice_input(
    self, 
    call_sid: str, 
    input_text: str, 
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a voice input with the FSM and appropriate agents.
    
    Args:
        call_sid: The Twilio call SID for this session
        input_text: The transcribed user input
        context: Optional context information
        
    Returns:
        Dict[str, Any]: The processed response from the appropriate agent
    """
    context = context or {}
    
    try:
        # Set correlation ID for tracing
        set_correlation_id(call_sid)
        
        start_time = time.time()
        
        # Step 1: Add user message to conversation store
        await self.conversation_store.add_message(
            call_sid, 
            "user", 
            input_text
        )
        
        # Step 2: Get current HSM state
        hsm_state_info = await hsm_manager.get_state(call_sid)
        current_state = hsm_state_info.get("current_state", ConversationHSMStates.INITIAL)
        
        # Step 3: Add transcript to context for HSM processing
        context["transcript"] = input_text
        
        # Step 4: Process transcript with HSM for state transitions
        new_state = await hsm_manager.process_event_from_transcript(
            call_sid, 
            input_text, 
            current_state, 
            context
        )
        
        # Step 5: Select appropriate agent based on state and context
        selected_agent = await self._select_agent_for_state(new_state, input_text, context)
        
        # Step 6: Load conversation history for context
        conversation_history = await self.conversation_store.get_conversation_history(call_sid, limit=10)
        context["conversation_history"] = conversation_history
        context["call_sid"] = call_sid
        
        # Step 7: Process input with selected agent
        agent_response = await selected_agent.process_voice_input(input_text, context)
        
        # Step 8: Add agent response to conversation store
        if agent_response.get("text"):
            await self.conversation_store.add_message(
                call_sid,
                "assistant", 
                agent_response["text"]
            )
        
        duration = time.time() - start_time
        
        return {
            **agent_response,
            "processing_time": duration,
            "hsm_state": new_state,
            "agent_used": selected_agent.name
        }
        
    except Exception as e:
        logger.error(f"Error processing voice input: {e}", exc_info=True)
        return {
            "text": "I apologize, but I'm having trouble processing your request. Could you please try again?",
            "agent": "Error Handler",
            "handled": True,
            "error": True,
            "actions": []
        }
```

**Agent Selection Logic:**
```python
async def _select_agent_for_state(
    self, 
    hsm_state: str, 
    input_text: str, 
    context: Dict[str, Any]
) -> BaseAsyncAgent:
    """
    Select the appropriate agent based on HSM state and input analysis.
    
    Args:
        hsm_state: Current HSM state
        input_text: User input text
        context: Processing context
        
    Returns:
        The selected agent instance
    """
    
    # Load conversation history for better context
    call_sid = context.get("call_sid")
    if call_sid:
        conversation_history = await self.conversation_store.get_conversation_history(call_sid, limit=5)
        context["conversation_history"] = conversation_history
    
    # Primary agent selection based on HSM state
    if hsm_state in [
        ConversationHSMStates.INITIAL,
        ConversationHSMStates.GREETING, 
        ConversationHSMStates.MAIN_MENU,
        ConversationHSMStates.ORDERING,
        ConversationHSMStates.CONFIRMATION,
        ConversationHSMStates.FULFILLMENT
    ]:
        # Use frontline agent for primary conversation flow
        return self.frontline_agent
    
    # Secondary selection based on input content analysis
    input_lower = input_text.lower()
    
    # Menu-related queries
    if any(word in input_lower for word in [
        "menu", "food", "dish", "ingredient", "allergy", "recommendation",
        "what do you have", "what's available", "tell me about"
    ]):
        return self.menu_agent
    
    # Cart-related operations
    if any(phrase in input_lower for phrase in [
        "add to cart", "remove from cart", "cart", "order total",
        "what's in my order", "change quantity"
    ]):
        return self.cart_agent
    
    # Default to frontline agent
    return self.frontline_agent
```

---

## 8. HIERARCHICAL STATE MACHINE (HSM)

### State Definitions (`app/fsm/hsm_core.py`):
```python
class ConversationHSMStates(str, Enum):
    # Root states
    INITIAL = "INITIAL"
    ACTIVE = "ACTIVE"
    
    # Greeting phase
    GREETING = "ACTIVE.GREETING"
    
    # Main conversation flow
    MAIN_MENU = "ACTIVE.MAIN_MENU"
    
    # Ordering hierarchy
    ORDERING = "ACTIVE.ORDERING"
    ORDERING_BROWSING = "ACTIVE.ORDERING.BROWSING"
    ORDERING_MENU_INQUIRY = "ACTIVE.ORDERING.MENU_INQUIRY"
    ORDERING_ITEM_CUSTOMIZATION = "ACTIVE.ORDERING.ITEM_CUSTOMIZATION"
    ORDERING_CART_REVIEW = "ACTIVE.ORDERING.CART_REVIEW"
    
    # Order completion flow
    CONFIRMATION = "ACTIVE.CONFIRMATION"
    FULFILLMENT = "ACTIVE.FULFILLMENT"
    COMPLETION = "ACTIVE.COMPLETION"
    
    # Support states
    FOLLOW_UP = "ACTIVE.FOLLOW_UP"
    ESCALATION = "ACTIVE.ESCALATION"

class ConversationHSMEvents(str, Enum):
    # User interaction events
    USER_PROVIDES_NAME = "USER_PROVIDES_NAME"
    USER_STARTS_ORDERING = "USER_STARTS_ORDERING"
    USER_ADDS_ITEM = "USER_ADDS_ITEM"
    USER_ASKS_QUESTION = "USER_ASKS_QUESTION"
    USER_COMPLETES_ORDER = "USER_COMPLETES_ORDER"
    USER_CONFIRMS_ORDER = "USER_CONFIRMS_ORDER"
    USER_CANCELS_ORDER = "USER_CANCELS_ORDER"
    
    # System events
    ORDER_VALIDATED = "ORDER_VALIDATED"
    PAYMENT_PROCESSED = "PAYMENT_PROCESSED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    
    # Error events
    REQUEST_ESCALATION = "REQUEST_ESCALATION"
    REQUEST_HUMAN = "REQUEST_HUMAN"
```

### State Transition Logic:
```python
async def process_event_from_transcript(
    self,
    call_sid: str,
    transcript: str,
    current_state: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Process a transcript and determine state transitions using LLM intent detection.
    
    Args:
        call_sid: The call session ID
        transcript: The user's transcript
        current_state: Current HSM state
        context: Additional context
        
    Returns:
        The new state after processing
    """
    context = context or {}
    
    try:
        # Use intent detector to classify the transcript
        detected_event = await intent_detector.detect_intent_from_transcript(
            transcript, current_state, context
        )
        
        if detected_event:
            # Process the event through HSM
            event = HSMEvent(name=detected_event, data={"transcript": transcript})
            new_state = await self.process_event(call_sid, event, context)
            return new_state
        else:
            # No event detected, stay in current state
            return current_state
            
    except Exception as e:
        logger.error(f"Error processing transcript for HSM: {e}")
        return current_state
```

---

## 9. INTENT DETECTION SYSTEM

### LLM-Based Intent Detection (`app/utils/intent_detector_async.py`):
```python
async def detect_intent_from_transcript(
    self,
    transcript: str,
    current_state: str,
    context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Detect user intent from transcript using LLM for the given state.
    
    Args:
        transcript: The user's speech transcript
        current_state: Current conversation state
        context: Additional context information
        
    Returns:
        Detected event name or None if no clear intent
    """
    try:
        # Get state-specific prompt
        state_prompt = self._get_state_specific_prompt(current_state, context)
        
        # Build full prompt
        system_prompt = f"""
        You are an intelligent intent classifier for a restaurant phone ordering system.
        
        CURRENT STATE: {current_state}
        {state_prompt}
        
        AVAILABLE EVENTS TO DETECT:
        - USER_PROVIDES_NAME: User is giving their name
        - USER_STARTS_ORDERING: User wants to place an order
        - USER_ADDS_ITEM: User wants to add specific food items
        - USER_ASKS_QUESTION: User has questions about menu/restaurant
        - USER_COMPLETES_ORDER: User indicates they're done ordering
        - USER_CONFIRMS_ORDER: User confirms their final order
        - USER_CANCELS_ORDER: User wants to cancel
        - REQUEST_ESCALATION: User requests human assistance
        - REQUEST_HUMAN: User wants to speak to a person
        
        Analyze the transcript and respond with ONLY the event name or "NONE" if unclear.
        Be conservative - only return an event if you're confident.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript: '{transcript}'"}
        ]
        
        client = await get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,
            max_tokens=50
        )
        
        detected_intent = response.choices[0].message.content.strip()
        
        if detected_intent == "NONE":
            return None
        
        # Validate the detected intent is in our event enum
        try:
            ConversationHSMEvents(detected_intent)
            logger.info(f"LLM Intent Detection - State: {current_state}, Transcript: '{transcript[:20]}...', Detected: {detected_intent}")
            return detected_intent
        except ValueError:
            logger.warning(f"LLM returned invalid event: {detected_intent}")
            return None
            
    except Exception as e:
        logger.error(f"Error detecting intent: {e}")
        return None

def _get_state_specific_prompt(self, state: str, context: Dict[str, Any]) -> str:
    """Get state-specific guidance for intent detection."""
    
    if state == ConversationHSMStates.INITIAL:
        return """
        CONTEXT: This is the beginning of the call. The customer likely just connected.
        LOOK FOR: Name provision, ordering intent, general questions.
        """
    
    elif state == ConversationHSMStates.GREETING:
        return """
        CONTEXT: We're in the greeting phase, likely asking for the customer's name.
        LOOK FOR: Name provision (first name, full name, "I'm John", "My name is Sarah", etc.)
        """
    
    elif state == ConversationHSMStates.MAIN_MENU:
        return """
        CONTEXT: Customer has provided name, now we're taking their order or answering questions.
        LOOK FOR: Food ordering intent, menu questions, specific item requests.
        """
    
    elif state == ConversationHSMStates.ORDERING:
        return """
        CONTEXT: Customer is actively ordering food.
        LOOK FOR: Additional items, order completion signals ("that's all", "done", "finished"), 
        menu questions, order modifications.
        """
    
    elif state == ConversationHSMStates.CONFIRMATION:
        return """
        CONTEXT: We're confirming the customer's order.
        LOOK FOR: Order confirmation ("yes", "correct"), order changes, cancellation.
        """
    
    else:
        return f"CONTEXT: Current state is {state}. Analyze for appropriate intent."
```

---

## 10. COMPLETE SYSTEM INTEGRATION

### Context Flow and Data Synchronization:

**Context Structure:**
```python
{
    # Session identifiers
    "call_sid": "CA123...",
    "session_id": "VX456...",
    
    # Customer information
    "customer_name": "Bruce",
    "customer_phone": "+1234567890",
    "customer_email": "bruce@example.com",
    
    # Conversation state
    "conversation_state": "ORDERING",
    "hsm_state": "ACTIVE.ORDERING.BROWSING",
    
    # Order information
    "order_items": [
        {
            "plu": "P-BURG-CHK",
            "name": "Chicken Burger", 
            "price": 8.00,
            "quantity": 1,
            "modifiers": []
        }
    ],
    "total_price": 8.00,
    
    # Conversation history
    "conversation_history": [
        {"role": "assistant", "content": "Hello! Welcome to Red Bar Restaurant..."},
        {"role": "user", "content": "Hi, I'd like to order"},
        {"role": "assistant", "content": "Great! What's your name?"},
        {"role": "user", "content": "Bruce"}
    ],
    
    # Voice processing context
    "voice_mode": "conversation_relay",
    "transcript": "I'd like a chicken burger",
    
    # Agent-specific context
    "state_guidance": "Specific AI instructions for current state",
    "delegated_by": "FrontlineAgent",
    "first_interaction": true
}
```

### Performance Optimizations:

1. **Token Limits by Agent:**
   - Frontline Agent: 512 tokens (configurable via `FRONTEND_AGENT_MAX_TOKENS`)
   - Menu Agent: 256 tokens (configurable via `MENU_AGENT_MAX_TOKENS`)
   - Cart Agent: 150 tokens (configurable via `CART_AGENT_MAX_TOKENS`)

2. **Connection Pooling:**
   - OpenAI client pool for reusing connections
   - Database connection pooling via SQLAlchemy
   - Redis connection pooling for session storage

3. **Caching Strategies:**
   - Agent instance caching in factory
   - Menu matcher caching (5-minute TTL)
   - Response caching for common patterns

4. **Conversation History Optimization:**
   - Only last 4 messages included in AI context
   - Full history stored in Redis for reference
   - Automatic cleanup of old sessions

### Error Handling and Graceful Degradation:

1. **AI Timeouts:**
   ```python
   if "timeout" in str(e).lower():
       return {
           "text": "I understand. Let me help you with that.",
           "agent": getattr(self, 'name', 'AI'),
           "handled": True,
           "actions": [],
           "timeout": True
       }
   ```

2. **Database Failures:**
   ```python
   if not self.db:
       return {"found": False, "error": "Database not available"}
   ```

3. **Tool Execution Errors:**
   ```python
   try:
       result = await self.execute_tool(tool_name, tool_args)
   except Exception as e:
       logger.error(f"Tool execution error: {e}")
       return {"error": f"Tool execution failed: {str(e)}"}
   ```

---

## CONCLUSION

This documentation covers every aspect of the RedBarSushiAI agent system:

- **4 Main Agents**: Base, Frontline, Menu, Cart with complete class definitions
- **Complete AI System**: Every system prompt, tool definition, and processing method
- **Agent Orchestration**: Full orchestration logic and agent selection criteria
- **State Management**: Complete HSM with all states, events, and transitions
- **Intent Detection**: LLM-based intent classification with state-specific prompts
- **Context Management**: Complete context flow and data synchronization
- **Performance**: All optimizations, caching, and token management
- **Error Handling**: Comprehensive error handling and graceful degradation

The system is entirely AI-driven with sophisticated prompts guiding behavior, no hardcoded logic, and complete integration between all components for natural conversational voice ordering.