# RedBarSushiAI Agent System - Complete Technical Documentation

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Base Agent Framework](#base-agent-framework)
3. [AI Intelligence Mixin](#ai-intelligence-mixin)
4. [Frontline Voice Agent (AI-Enhanced)](#frontline-voice-agent-ai-enhanced)
5. [Menu Agent (Enhanced)](#menu-agent-enhanced)
6. [Cart Agent](#cart-agent)
7. [Agent Factory](#agent-factory)
8. [Agent Orchestration](#agent-orchestration)
9. [Intent Detection System](#intent-detection-system)
10. [Hierarchical State Machine (HSM)](#hierarchical-state-machine-hsm)
11. [FSM Integration](#fsm-integration)
12. [Error Handling & Recovery](#error-handling--recovery)
13. [Performance Optimizations](#performance-optimizations)
14. [Integration Points](#integration-points)

---

## System Architecture Overview

The RedBarSushiAI agent system implements a sophisticated multi-agent architecture with:

- **Hierarchical State Machine (HSM)** for conversation flow management
- **AI-powered agents** using OpenAI GPT-4o-mini for intelligent decision making
- **Async-first design** with non-blocking I/O operations
- **Tool-based interactions** allowing agents to execute specific functions
- **Context synchronization** across agents and conversation storage
- **Dynamic agent orchestration** based on conversation state

### Key Architectural Patterns

1. **Multi-Agent System with Orchestration**: Specialized agents coordinated by an orchestrator
2. **Finite State Machine (FSM)**: Hierarchical states managing conversation flow
3. **Voice Processing Architecture**: ConversationRelay for webhook-based voice handling
4. **Database Architecture**: Async SQLAlchemy 2.0 with connection pooling
5. **AI-Only Menu Matching**: No hardcoded logic, everything through LLM

---

## Base Agent Framework

### BaseAsyncAgent Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/base_async.py`

#### Class Definition
```python
class BaseAsyncAgent:
    """
    Base class for all asynchronous agents in the system.
    Provides common functionality and interfaces for agents.
    """
```

#### Initialization Parameters
```python
def __init__(self, 
             agent_id: Optional[str] = None, 
             name: str = "BaseAgent", 
             agent_name: Optional[str] = None, 
             **kwargs):
```

**Parameters:**
- `agent_id`: Optional ID for the agent (used with OpenAI Assistants API)
- `name`: Name of the agent for logging and identification
- `agent_name`: Alternative name parameter (for compatibility with subclasses)
- `**kwargs`: Additional keyword arguments for extended functionality

#### Core Attributes
```python
self.agent_id = agent_id or f"agent_{int(time.time())}"
self.name = agent_name or name
self.agent_name = self.name  # Alias for name
self.specialists = {}  # For registering specialist agents
self.policy_agent = None  # For policy enforcement
self.context = {}  # For maintaining conversation context
```

#### Core Methods

##### process_input
```python
async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```
**Purpose**: Process a text input and generate a response
**Returns**: Agent's response with text, agent name, handled status, and actions

##### process_voice_input
```python
async def process_voice_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```
**Purpose**: Process voice input (calls process_input by default, can be overridden)

##### execute_tool
```python
async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
```
**Purpose**: Execute a tool owned by this agent
**Returns**: Tool execution result

##### Specialist Management
```python
def register_specialist(self, role: str, agent: 'BaseAsyncAgent') -> None:
def register_policy_agent(self, agent: 'BaseAsyncAgent') -> None:
async def delegate_to_specialist(self, role: str, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```

##### Context Management
```python
def update_context(self, context: Dict[str, Any]) -> None:
def get_context(self) -> Dict[str, Any]:
def get_tools(self) -> List[Dict[str, Any]]:
```

---

## AI Intelligence Mixin

### AIIntelligenceMixin Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/ai_mixin.py`

#### Purpose
Adds AI capabilities to async agents while maintaining async nature and FSM integration.

#### Initialization
```python
def __init__(self):
    """Initialize the AI client."""
    self._ai_client = None
    self._ai_enabled = True
    self._model = "gpt-4o-mini"  # Fast and intelligent model
```

#### Core Method: process_with_ai

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

**Purpose**: Process input using AI for intelligent understanding and response

**Parameters:**
- `input_text`: The user's input text
- `context`: Conversation context
- `use_tools`: Whether to enable tool calling
- `fast_mode`: Whether to use fast mode (unused currently)
- `stream`: Whether to stream the response

**API Call Configuration:**
```python
params = {
    "model": self._model,
    "messages": messages,
    "temperature": 0.0,  # Zero for fastest, most deterministic responses
    "max_tokens": effective_max_tokens,
    "stream": False
}

if use_tools and hasattr(self, 'tools') and self.tools:
    params["tools"] = self.tools
    params["tool_choice"] = "auto"
```

#### Message Building (_build_messages)

**Purpose**: Build message history for AI context - OPTIMIZED for speed

**Key Features:**
- Combines all system context into ONE message for efficiency
- Adds essential context only (customer name, cart items, FSM state)
- Includes last 4 messages for better context understanding
- State-specific guidance injection

#### Tool Execution Handling

**Process Flow:**
1. Check for tool calls in AI response
2. Execute each tool using `execute_tool` method
3. Get final response after tool execution with follow-up API call
4. Extract actions from tool results

**Tool Result Processing:**
```python
async def _get_final_response_after_tools(self, original_message, tool_results, context):
    # Build follow-up messages including tool results
    # Add assistant's message with tool calls
    # Add tool results as tool messages
    # Get final response with second API call
```

#### Fast Response System

```python
async def get_fast_response(self, input_text: str, context: Dict[str, Any]) -> str:
```
**Purpose**: Get fast, contextual response without full AI processing for immediate feedback

#### Intent Understanding

```python
async def understand_intent(self, input_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
```
**Purpose**: Use AI to understand user intent from their input

**System Prompt Template:**
```
You are an intelligent intent classifier for a restaurant ordering system.

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
```

#### Streaming Support

```python
async def process_with_ai_streaming(
    self,
    input_text: str,
    context: Dict[str, Any],
    use_tools: bool = True,
    callback: Optional[Callable[[str, bool], None]] = None
) -> Dict[str, Any]:
```

**Features:**
- Streams response in real-time
- Breaks at sentence boundaries
- Handles tool calling by falling back to non-streaming
- Sends chunks via callback function

---

## Frontline Voice Agent (AI-Enhanced)

### AsyncFrontlineVoiceAgentAI Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/frontline_async_ai.py`

#### Class Definition
```python
class AsyncFrontlineVoiceAgentAI(BaseAsyncAgent, AIIntelligenceMixin):
    """
    AI-enhanced frontline agent for handling voice interactions.
    Uses AI for understanding intent and generating responses
    while maintaining compatibility with async FSM orchestration.
    """
```

#### Initialization

```python
def __init__(self, agent_id: Optional[str] = None):
    """Initialize the AI-enhanced frontline voice agent."""
    BaseAsyncAgent.__init__(self, agent_id=agent_id, name="FrontlineVoiceAI")
    AIIntelligenceMixin.__init__(self)
    
    # Set agent-specific max tokens
    self._default_max_tokens = settings.FRONTEND_AGENT_MAX_TOKENS
    
    self.conversation_state = "GREETING"
    self.greeting_done = False
```

#### Context Structure
```python
self.context = {
    "customer_name": None,
    "order_type": None,
    "order_items": [],
    "current_item": None,
    "conversation_history": []
}
```

#### Available States
```python
self.states = [
    "GREETING", "MAIN_MENU", "ORDERING", "VALIDATION", 
    "CONFIRMATION", "FULFILLMENT", "COMPLETION", "FOLLOW_UP",
    "ESCALATION"
]
```

#### AI Instructions (Dynamic)

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

#### Complete Tool Definitions

##### 1. lookup_menu_item
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

##### 2. get_menu_categories
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

##### 3. get_items_by_category
```json
{
    "type": "function",
    "function": {
        "name": "get_items_by_category",
        "description": "Get all menu items in a specific category with names, prices, and descriptions",
        "parameters": {
            "type": "object",
            "properties": {
                "category_name": {
                    "type": "string",
                    "description": "Name of the category (e.g., 'Steak & Burgers', 'Pizzas')"
                }
            },
            "required": ["category_name"]
        }
    }
}
```

##### 4. add_to_cart
```json
{
    "type": "function",
    "function": {
        "name": "add_to_cart",
        "description": "Add an item to the customer's order",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of items to add",
                    "default": 1
                },
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of modifiers (e.g., 'spicy', 'no wasabi')"
                }
            },
            "required": ["item_name"]
        }
    }
}
```

##### 5. update_customer_info
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
                "order_type": {
                    "type": "string",
                    "enum": ["pickup", "delivery"],
                    "description": "Type of order"
                }
            }
        }
    }
}
```

##### 6. get_cart_summary
```json
{
    "type": "function",
    "function": {
        "name": "get_cart_summary",
        "description": "Get a summary of the current order",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

##### 7. confirm_order
```json
{
    "type": "function",
    "function": {
        "name": "confirm_order",
        "description": "Confirm the order is complete and ready to submit",
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

##### 8. escalate_to_human
```json
{
    "type": "function",
    "function": {
        "name": "escalate_to_human",
        "description": "Transfer to a human staff member",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation"
                }
            },
            "required": ["reason"]
        }
    }
}
```

#### State Handlers

##### Greeting State Handler (_handle_greeting)

```python
async def _handle_greeting(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
```

**Purpose**: Handle inputs in the greeting state using AI

**State Guidance Provided to AI:**
```python
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
```

##### Main Menu State Handler (_handle_main_menu)

```python
async def _handle_main_menu(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
```

**State Guidance for Name Acknowledgment:**
```python
context["state_guidance"] = f"""
You just got the customer's name ({self.context['customer_name']}) and transitioned to the main menu.
Acknowledge their name warmly and ask how you can help them today.
IMPORTANT: Use their name {self.context['customer_name']} in your response!
For example: "Nice to meet you, {self.context['customer_name']}! How can I help you today?"
"""
```

**State Guidance for Regular Processing:**
```python
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
```

##### Ordering State Handler (_handle_ordering)

```python
async def _handle_ordering(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
```

**Features:**
- Uses AI to detect order completion intent with high accuracy
- Dynamic order confirmation generation
- Intelligent processing of add/modify/complete requests

**Completion Detection Logic:**
```python
completion_intent = await self.understand_intent(input_text, completion_check_context)
if completion_intent.get("intent") == "complete_order" and completion_intent.get("confidence", 0) > 0.6:
    # User is indicating they're done ordering
    self.conversation_state = "VALIDATION"
```

**State Guidance:**
```python
context["state_guidance"] = f"""
CRITICAL CONTEXT: You are in the ACTIVE ORDERING phase.

Customer: {self.context.get('customer_name')} (name already confirmed)
Current cart: {self.context.get('order_items', [])}

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

Customer name is ALREADY SET: {self.context.get('customer_name')} - never change this.
"""
```

#### Tool Execution

##### execute_tool Method
```python
async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
```

**Tool Routing:**
- `lookup_menu_item` → `_lookup_menu_item`
- `get_menu_categories` → `_get_menu_categories`
- `get_items_by_category` → `_get_items_by_category`
- `add_to_cart` → `_add_to_cart`
- `update_customer_info` → `_update_customer_info`
- `get_cart_summary` → `_get_cart_summary`
- `confirm_order` → Returns confirmation status
- `escalate_to_human` → Returns escalation status

##### Key Tool Implementations

**_add_to_cart**:
```python
async def _add_to_cart(self, item_name: str, quantity: int, modifiers: List[str]) -> Dict[str, Any]:
```
1. Delegates to cart specialist if available
2. Updates cart specialist context with call_sid
3. Looks up item PLU via menu specialist
4. Handles disambiguation automatically
5. Updates local context on success

**_update_customer_info**:
```python
async def _update_customer_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
```
- Updates customer name and order type
- Critical logging for debugging
- Returns success status with updated fields

#### Context Management

**State Transitions Based on Actions:**
```python
async def _update_state_from_actions(self, actions: List[Dict[str, Any]]):
    for action in actions:
        action_type = action.get("type")
        
        if action_type == "set_customer_name":
            self.context["customer_name"] = action.get("name")
            if self.conversation_state == "GREETING":
                self.conversation_state = "MAIN_MENU"
                
        elif action_type == "cart_updated":
            if self.conversation_state == "MAIN_MENU":
                self.conversation_state = "ORDERING"
                
        elif action_type == "order_confirmed":
            confirmed = action.get("confirmed")
            if confirmed:
                self.conversation_state = "FULFILLMENT"
            else:
                self.conversation_state = "ORDERING"
```

---

## Menu Agent (Enhanced)

### AsyncMenuAgentEnhanced Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/menu_async_enhanced.py`

#### Class Definition
```python
class AsyncMenuAgentEnhanced(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Enhanced menu agent with AI capabilities and efficient database access.
    """
```

#### Initialization
```python
def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
    """Initialize the enhanced menu agent."""
    BaseAsyncAgent.__init__(self, agent_id=agent_id, name="MenuEnhanced")
    AIIntelligenceMixin.__init__(self)
    
    # Set agent-specific max tokens
    self._default_max_tokens = getattr(settings, 'MENU_AGENT_MAX_TOKENS', 256)
    self.context = {}  # Store context for disambiguation
    
    self.db = db
    self._menu_cache = {}
    self._cache_ttl = 300  # 5 minutes
```

#### AI Instructions
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

#### Complete Tool Definitions

##### 1. lookup_menu_item
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

##### 2. list_categories
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

##### 3. get_items_by_category
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

##### 4. search_menu
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

##### 5. get_item_details
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

#### Menu Item Lookup with Disambiguation

```python
async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
    """Look up a menu item using the matcher with disambiguation support."""
```

**Process Flow:**
1. Initialize AsyncMenuMatcher with database session
2. Find all matching items with confidence threshold (0.5)
3. Handle disambiguation if multiple matches found
4. Return formatted item details

**Disambiguation Response Format:**
```python
return {
    "found": False,
    "needs_disambiguation": True,
    "clarification_needed": clarification,
    "candidates": [
        {
            "name": match["name"],
            "price": f"${match.get('price', 0):.2f}",
            "category": match.get("category", "Unknown")
        }
        for match in matches[:5]
    ],
    "disambiguation_type": "menu_item"
}
```

**Single Match Response Format:**
```python
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
```

#### Database Integration

**Categories Listing:**
```python
async def _list_categories(self) -> Dict[str, Any]:
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
```

**Items by Category:**
```python
async def _get_items_by_category(self, category_name: str) -> Dict[str, Any]:
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
```

---

## Cart Agent

### AsyncCartAgent Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/cart_async.py`

#### Class Definition
```python
class AsyncCartAgent(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Async Cart Agent that handles building customer orders.
    Translates natural language into structured cart items and validates them.
    """
```

#### Initialization
```python
def __init__(self, agent_id: Optional[str] = None, db: Optional[Any] = None):
    """Initialize the Async Cart Agent."""
    BaseAsyncAgent.__init__(self, agent_id=agent_id, name="Cart")
    AIIntelligenceMixin.__init__(self)
    self.db = db
    
    # Set agent-specific max tokens
    self._default_max_tokens = getattr(settings, 'CART_AGENT_MAX_TOKENS', 256)
    self.disambiguation_context = None  # Store disambiguation state
```

#### Optimized AI Instructions
```python
self.instructions = """
Cart specialist. Be FAST and ACCURATE.

For any order:
1. lookup_menu_item(item_name="[item name]")
2. add_item_to_cart(plu=result, quantity=[number])
3. Confirm what was added

For "that's all": get_current_cart() and confirm total.
For menu questions: Direct them to specific items or categories.

BE BRIEF. USE TOOLS. ADD TO CART.
"""
```

#### Complete Tool Definitions

##### 1. lookup_menu_item
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
                    "description": "The name of the menu item to look up"
                }
            },
            "required": ["item_name"]
        }
    }
}
```

##### 2. add_item_to_cart
```json
{
    "type": "function",
    "function": {
        "name": "add_item_to_cart",
        "description": "Add an item to the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {
                "plu": {
                    "type": "string",
                    "description": "The PLU code of the menu item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The quantity of this item"
                },
                "modifiers": {
                    "type": "array",
                    "description": "Optional list of modifiers to add to this item",
                    "items": {
                        "type": "object",
                        "properties": {
                            "plu": {
                                "type": "string",
                                "description": "The PLU code of the modifier"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The quantity of this modifier"
                            }
                        },
                        "required": ["plu", "quantity"]
                    }
                },
                "special_instructions": {
                    "type": "string",
                    "description": "Optional special instructions for this item"
                }
            },
            "required": ["plu", "quantity"]
        }
    }
}
```

##### 3. remove_from_cart
```json
{
    "type": "function",
    "function": {
        "name": "remove_from_cart",
        "description": "Remove an item from the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {
                "item_index": {
                    "type": "integer",
                    "description": "The index of the item to remove (0-based)"
                }
            },
            "required": ["item_index"]
        }
    }
}
```

##### 4. modify_cart_item
```json
{
    "type": "function",
    "function": {
        "name": "modify_cart_item",
        "description": "Modify an item in the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {
                "item_index": {
                    "type": "integer",
                    "description": "The index of the item to modify (0-based)"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The new quantity of this item"
                },
                "add_modifiers": {
                    "type": "array",
                    "description": "Optional list of modifiers to add to this item",
                    "items": {
                        "type": "object",
                        "properties": {
                            "plu": {
                                "type": "string",
                                "description": "The PLU code of the modifier"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "The quantity of this modifier"
                            }
                        },
                        "required": ["plu", "quantity"]
                    }
                },
                "remove_modifier_indices": {
                    "type": "array",
                    "description": "Optional list of modifier indices to remove (0-based)",
                    "items": {
                        "type": "integer"
                    }
                },
                "special_instructions": {
                    "type": "string",
                    "description": "Optional new special instructions for this item"
                }
            },
            "required": ["item_index"]
        }
    }
}
```

##### 5. get_current_cart
```json
{
    "type": "function",
    "function": {
        "name": "get_current_cart",
        "description": "Get the current state of the customer's cart",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

##### 6. suggest_additions
```json
{
    "type": "function",
    "function": {
        "name": "suggest_additions",
        "description": "Suggest items to add to the cart based on what's already there",
        "parameters": {
            "type": "object",
            "properties": {
                "suggestion_type": {
                    "type": "string",
                    "description": "The type of suggestion to make",
                    "enum": ["drinks", "sides", "desserts", "popular", "combos"]
                }
            },
            "required": ["suggestion_type"]
        }
    }
}
```

##### 7. clear_cart
```json
{
    "type": "function",
    "function": {
        "name": "clear_cart",
        "description": "Clear the entire cart",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
```

#### Cart Management Implementation

##### Add Item to Cart
```python
async def _add_item_to_cart(
    self, 
    plu: str, 
    quantity: int = 1, 
    modifiers: Optional[List[Dict[str, Any]]] = None, 
    special_instructions: Optional[str] = None
) -> Dict[str, Any]:
```

**Process Flow:**
1. Get current call SID from context
2. Validate item exists in database by PLU
3. Validate modifiers if provided
4. Create new item entry with validated data
5. Get current cart from conversation store
6. Check for existing item (same PLU, modifiers, instructions)
7. Update quantity or add new item
8. Calculate total price (items + modifiers)
9. Update conversation store with new cart
10. Return success response with cart summary

**Cart Item Structure:**
```python
new_item = {
    "plu": plu,
    "name": item.get("name", ""),
    "price": item.get("price", 0),
    "quantity": quantity,
    "modifiers": validated_modifiers,
    "special_instructions": special_instructions
}
```

**Price Calculation:**
```python
total_price = 0
for cart_item in cart["items"]:
    item_price = cart_item.get("price", 0) * cart_item.get("quantity", 1)
    # Add modifier prices
    for modifier in cart_item.get("modifiers", []):
        item_price += modifier.get("price_change", 0) * modifier.get("quantity", 1)
    total_price += item_price
```

##### Get Current Cart
```python
async def _get_current_cart(self) -> Dict[str, Any]:
```

**Returns Formatted Cart:**
```python
return {
    "success": True,
    "item_count": len(current_cart.get("items", [])),
    "total_price": current_cart.get("total_price", 0),
    "formatted_total": total_price_str,
    "items": formatted_items
}
```

**Formatted Item Structure:**
```python
formatted_items.append({
    "index": i,
    "name": item.get("name", ""),
    "quantity": item.get("quantity", 1),
    "price": price_str,
    "modifiers": formatted_modifiers,
    "special_instructions": item.get("special_instructions")
})
```

#### Order Completion Detection

**AI-Powered Completion Logic:**
```python
# Check if order is ready for validation FIRST
order_ready = False
input_lower = input_text.lower()
completion_phrases = ["that's all", "done", "ready", "checkout", "complete", "finished", "that's it", "that is it", "i'm done", "nothing else"]

if any(phrase in input_lower for phrase in completion_phrases):
    order_ready = True
    # For completion phrases, respond quickly without AI if cart has items
    if current_cart.get("items"):
        items_text = ", ".join([f"{item['quantity']} {item['name']}" for item in current_cart["items"]])
        total = current_cart.get("total_price", 0)
        response = {
            "text": f"Perfect! Your order includes: {items_text}. Total: ${total:.2f}. Let me confirm all the details.",
            "agent": self.name,
            "handled": True,
            "ai_generated": False
        }
```

#### Context Management

**Call SID Tracking:**
```python
def set_current_call(self, call_sid: str):
    """Set the current call SID for context."""
    self.current_call_sid = call_sid
    self.context["call_sid"] = call_sid

def _get_current_call_sid(self) -> Optional[str]:
    """Get the current call SID from context."""
    if "call_sid" in self.context:
        return self.context["call_sid"]
    return self.current_call_sid
```

---

## Agent Factory

### AsyncAgentFactory Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/agents/factory_async.py`

#### Purpose
Factory for creating and managing async agent instances with caching and configuration.

#### Initialization
```python
def __init__(self):
    """Initialize the async agent factory."""
    self.agent_classes: Dict[str, Type[BaseAsyncAgent]] = {}
    self.agents: Dict[str, BaseAsyncAgent] = {}
    
    # Register standard agents
    use_ai_agents = getattr(settings, 'USE_AI_AGENTS', True)
    if use_ai_agents:
        self.register_agent_class("frontline", AsyncFrontlineVoiceAgentAI)
        self.register_agent_class("menu", AsyncMenuAgentEnhanced)
    else:
        self.register_agent_class("frontline", AsyncFrontlineVoiceAgent)
        self.register_agent_class("menu", AsyncMenuAgent)
    
    self.register_agent_class("cart", AsyncCartAgent)
    self.register_agent_class("guardrail", AsyncGuardrailAgent)
    self.register_agent_class("fulfillment", AsyncFulfillmentAgent)
    self.register_agent_class("escalation", AsyncEscalationAgent)
```

#### Agent Creation with Caching

```python
async def get_agent(self, agent_type: str, agent_id: Optional[str] = None, db=None) -> BaseAsyncAgent:
    """Get or create an agent instance."""
    # Create a cache key for this agent
    cache_key = f"{agent_type}:{agent_id}" if agent_id else agent_type
    
    # Check if we already have this agent
    if cache_key in self.agents:
        # Update the db if it's a menu or cart agent
        if (agent_type == "menu" or agent_type == "cart") and db is not None:
            self.agents[cache_key].db = db
        return self.agents[cache_key]
    
    # Create a new agent
    if agent_type in self.agent_classes:
        agent_class = self.agent_classes[agent_type]
        
        # Initialize the agent with appropriate parameters
        if (agent_type == "menu" or agent_type == "cart") and db is not None:
            # Menu and Cart agents need database session for async operations
            agent = agent_class(agent_id=agent_id, db=db)
        elif agent_id:
            agent = agent_class(agent_id=agent_id)
        else:
            agent = agent_class()
        
        # Store in cache
        self.agents[cache_key] = agent
        return agent
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")
```

#### Voice Agent System Creation

```python
async def create_voice_agent_system(self, db=None) -> BaseAsyncAgent:
    """Create a complete voice agent system with all specialists."""
    # Create the frontline agent
    frontline_agent = await self.get_agent("frontline")
    
    # Create and register specialist agents
    menu_agent = await self.get_agent("menu", db=db)
    cart_agent = await self.get_agent("cart", db=db)
    
    # Register specialists with the frontline agent
    frontline_agent.register_specialist("menu", menu_agent)
    frontline_agent.register_specialist("cart", cart_agent)
    
    return frontline_agent
```

**Singleton Instance:**
```python
# Singleton instance for easy import
async_agent_factory = AsyncAgentFactory()
```

---

## Agent Orchestration

### AsyncAgentOrchestrator Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/utils/agent_orchestration_async.py`

#### Purpose
Orchestrates interactions between async agents and manages conversation state using HSM.

#### Initialization
```python
def __init__(self):
    """Initialize the async agent orchestrator."""
    self.frontline_agent = None
    self.menu_agent = None
    self.cart_agent = None
    self.guardrail_agent = None
    self.fulfillment_agent = None
    self.escalation_agent = None
    self.active_sessions = {}
    self.conversation_store = async_conversation_store
```

#### Agent Initialization
```python
async def initialize(self, db=None):
    """Initialize the orchestrator and its agents."""
    # Create the complete voice agent system and get specialist agents
    self.frontline_agent = await async_agent_factory.create_voice_agent_system(db=db)
    self.menu_agent = await async_agent_factory.get_agent("menu", db=db)
    self.cart_agent = await async_agent_factory.get_agent("cart", db=db)
    self.guardrail_agent = await async_agent_factory.get_agent("guardrail")
    self.fulfillment_agent = await async_agent_factory.get_agent("fulfillment")
    self.escalation_agent = await async_agent_factory.get_agent("escalation")
```

#### Voice Input Processing

```python
async def process_voice_input(
    self, 
    call_sid: str, 
    input_text: str, 
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
```

**Process Flow:**
1. Initialize agents if needed
2. Track active session
3. Add user message to conversation store
4. Get current HSM state
5. Handle first interaction with START_CONVERSATION event
6. Check for global commands
7. Process transcript with HSM using intent detection
8. Select appropriate agent based on HSM state
9. Execute agent processing
10. Update session state
11. Return complete response

#### Agent Selection Logic

```python
async def _process_with_appropriate_agent(
    self, 
    current_state: str, 
    input_text: str, 
    context: Dict[str, Any]
) -> Tuple[Any, Dict[str, Any]]:
```

**State-Based Agent Selection:**

1. **MAIN_MENU/GREETING States:**
   - Check for `requesting_menu_info` flag
   - Use Menu Agent if requesting menu info
   - Use Frontline Agent otherwise

2. **ACTIVE.ORDERING States:**
   - Use Cart Agent for order management
   - Pass existing cart from context
   - Synchronize cart back to context after processing
   - Check for order completion triggers

3. **VALIDATION State:**
   - Use Guardrail Agent for validation

4. **ACTIVE.CONFIRMATION States:**
   - Use Frontline Agent with cart context
   - Check for order confirmation/rejection triggers

5. **ACTIVE.FULFILLMENT States:**
   - Use Fulfillment Agent with cart context
   - Check for fulfillment completion triggers

6. **ERROR_RECOVERY States:**
   - Use Frontline Agent for error recovery

7. **Default Case:**
   - Use Frontline Agent as fallback

#### HSM Event Detection

```python
async def _detect_hsm_event(self, input_text: str, current_state: str, context: Dict[str, Any]) -> Optional[HSMEvent]:
```

**Process:**
1. Use existing intent detector with state mapping
2. Convert HSM states to FSM-style for compatibility
3. Detect intent using AI-based intent detector
4. Map FSM events to HSM events
5. Return HSM event for processing

**State Mapping:**
```python
state_mapping = {
    ConversationHSMStates.INITIAL: "INITIAL",
    ConversationHSMStates.GREETING: "GREETING", 
    ConversationHSMStates.MAIN_MENU: "MAIN_MENU",
    ConversationHSMStates.ORDERING: "ORDERING",
    ConversationHSMStates.VALIDATION: "VALIDATION",
    ConversationHSMStates.CONFIRMATION: "CONFIRMATION",
    ConversationHSMStates.FULFILLMENT: "FULFILLMENT",
    ConversationHSMStates.COMPLETION: "COMPLETION",
    ConversationHSMStates.FOLLOW_UP: "FOLLOW_UP",
    ConversationHSMStates.ESCALATION: "ESCALATION"
}
```

#### Streaming Support

```python
async def process_voice_input_streaming(
    self,
    call_sid: str,
    input_text: str,
    stream_callback: Callable[[str, bool], None],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
```

**Features:**
- Streaming only supported for Frontline Agent in GREETING/MAIN_MENU states
- Falls back to non-streaming for complex states or when tools are needed
- Sends response chunks via callback function
- Returns complete response for final processing

#### New Conversation Initialization

```python
async def start_new_conversation(self, call_sid: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```

**Process:**
1. Set correlation ID from call_sid
2. Create new session tracking
3. Initialize HSM for new conversation
4. Trigger START_CONVERSATION event
5. Get greeting from HSM or generate with Frontline Agent
6. Add greeting to conversation store
7. Return greeting response

#### Session Management

```python
async def cleanup_inactive_sessions(self, max_idle_time: int = 3600) -> int:
```

**Cleanup Process:**
1. Find inactive sessions (idle > max_idle_time)
2. Remove from active sessions
3. Remove from conversation store
4. Remove from agents conversation store
5. Remove from HSM manager
6. Return count of cleaned sessions

**Singleton Instance:**
```python
# Singleton instance for easy import
async_agent_orchestrator = AsyncAgentOrchestrator()
```

---

## Intent Detection System

### AsyncIntentDetector Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/utils/intent_detector_async.py`

#### Purpose
Uses OpenAI to detect user intents from transcripts, replacing keyword-based detection with intelligent understanding.

#### Initialization
```python
def __init__(self):
    """Initialize the intent detector with OpenAI client."""
    self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    self.model = "gpt-4o-mini"  # Fast model for intent detection
```

#### Intent Detection Method

```python
async def detect_intent(
    self, 
    transcript: str, 
    current_state: ConversationState,
    context: Dict[str, Any]
) -> Optional[ConversationEvent]:
```

**Process Flow:**
1. Check for global commands first
2. Build state-specific system prompt
3. Make OpenAI API call with low temperature (0.1) for consistency
4. Map detected intent to FSM event
5. Return ConversationEvent or None

#### State-Specific System Prompts

##### GREETING State
```
Allowed intents:
- PROVIDE_NAME: User is giving their name or responding to name request
- SKIP_NAME: User wants to skip giving name or proceed without it
- REQUEST_ESCALATION: User is confused or asking for help

IMPORTANT: If user mentions ordering or menu in GREETING state, still return PROVIDE_NAME if no name is detected, or SKIP_NAME if they're trying to proceed without giving name.

Examples:
"John" -> PROVIDE_NAME
"My name is Sarah" -> PROVIDE_NAME  
"I don't want to give my name" -> SKIP_NAME
"Can I order?" -> SKIP_NAME
"What do you have?" -> SKIP_NAME
"What?" -> REQUEST_ESCALATION
```

##### MAIN_MENU State
```
Allowed intents:
- START_ORDER: User wants to place an order or add items
- REQUEST_MENU: User wants to know about menu/items/prices
- REQUEST_HOURS: User asking about hours or location
- REQUEST_HUMAN: User wants to speak to a person
- GENERAL_QUESTION: User has a question not covered above

Examples:
"I'd like to order something" -> START_ORDER
"Can I get two items" -> START_ORDER
"What do you have on the menu?" -> REQUEST_MENU
"Are you open now?" -> REQUEST_HOURS
"I need to speak to someone" -> REQUEST_HUMAN
"Do you deliver?" -> GENERAL_QUESTION
```

##### ORDERING State
```
Allowed intents:
- ADD_ITEM: User is adding items to their order
- REMOVE_ITEM: User wants to remove something
- MODIFY_ITEM: User wants to change something (quantity, preparation)
- REQUEST_MENU: User asking about menu items while ordering
- COMPLETE_ORDER: User is done ordering
- CANCEL_ORDER: User wants to cancel everything
- REQUEST_CANCELLATION: User mentions cancelling but isn't sure

Examples:
"Add an item" -> ADD_ITEM
"Remove that item" -> REMOVE_ITEM
"Make that 3 instead" -> MODIFY_ITEM
"What comes with that?" -> REQUEST_MENU
"That's all for now" -> COMPLETE_ORDER
"Never mind, cancel everything" -> CANCEL_ORDER
"Actually, maybe I should cancel" -> REQUEST_CANCELLATION
"I want to cancel my order" -> REQUEST_CANCELLATION
```

#### Intent to Event Mapping

```python
def _map_intent_to_event(self, intent: str, current_state: ConversationState) -> Optional[ConversationEvent]:
```

**State-Specific Mappings:**

**GREETING State:**
```python
{
    "PROVIDE_NAME": ConversationEvent.USER_PROVIDES_NAME,
    "SKIP_NAME": ConversationEvent.USER_PROVIDES_NAME,
    "REQUEST_ESCALATION": None
}
```

**MAIN_MENU State:**
```python
{
    "START_ORDER": ConversationEvent.START_ORDER,
    "REQUEST_MENU": ConversationEvent.REQUEST_MENU_INFO,
    "REQUEST_HOURS": ConversationEvent.REQUEST_MENU_INFO,
    "REQUEST_HUMAN": ConversationEvent.REQUEST_ESCALATION,
    "GENERAL_QUESTION": None
}
```

**ORDERING State:**
```python
{
    "ADD_ITEM": None,  # Handled by cart agent
    "REMOVE_ITEM": None,  # Handled by cart agent
    "MODIFY_ITEM": None,  # Handled by cart agent
    "REQUEST_MENU": ConversationEvent.REQUEST_MENU_QUERY,
    "COMPLETE_ORDER": ConversationEvent.COMPLETE_ORDER,
    "CANCEL_ORDER": ConversationEvent.CANCEL_ORDER,
    "REQUEST_CANCELLATION": ConversationEvent.USER_REQUESTS_CANCELLATION
}
```

#### Global Command Detection

```python
async def detect_global_command(self, transcript: str) -> Tuple[GlobalCommand, float]:
```

**Supported Global Commands:**
- CANCEL: Cancel current order
- HELP: Request assistance
- REPEAT: Repeat last response
- START_OVER: Start conversation from beginning
- GO_BACK: Return to previous state

**Singleton Instance:**
```python
# Singleton instance
intent_detector = AsyncIntentDetector()
```

---

## Hierarchical State Machine (HSM)

### Core HSM Components

#### ConversationHSMStates

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/fsm/hsm_core.py`

**Hierarchical State Definitions:**

##### Root States
- `INITIAL`: Initial conversation state
- `ACTIVE`: Main conversation flow
- `COMPLETION`: Conversation completion
- `ERROR_RECOVERY`: Error handling and recovery

##### ACTIVE Substates
- `ACTIVE.GREETING`: Getting customer information
- `ACTIVE.MAIN_MENU`: Main menu interaction
- `ACTIVE.ORDERING`: Order building process
- `ACTIVE.VALIDATION`: Order validation
- `ACTIVE.CONFIRMATION`: Order confirmation
- `ACTIVE.FULFILLMENT`: Order fulfillment
- `ACTIVE.FOLLOW_UP`: Post-order follow-up
- `ACTIVE.ESCALATION`: Human escalation

##### ORDERING Substates (Hierarchical)
- `ACTIVE.ORDERING.BROWSING`: Browsing menu items
- `ACTIVE.ORDERING.MENU_INQUIRY`: Asking about specific items
- `ACTIVE.ORDERING.ITEM_CUSTOMIZATION`: Customizing items
- `ACTIVE.ORDERING.CART_REVIEW`: Reviewing cart contents
- `ACTIVE.ORDERING.VALIDATION`: Validating individual items

##### CONFIRMATION Substates
- `ACTIVE.CONFIRMATION.REVIEW`: Reviewing final order
- `ACTIVE.CONFIRMATION.MODIFY`: Modifying order
- `ACTIVE.CONFIRMATION.PAYMENT`: Payment information
- `ACTIVE.CONFIRMATION.DELIVERY`: Delivery information

##### FULFILLMENT Substates
- `ACTIVE.FULFILLMENT.PROCESSING`: Processing order
- `ACTIVE.FULFILLMENT.TRACKING`: Order tracking
- `ACTIVE.FULFILLMENT.DELIVERY`: Delivery coordination

##### Global Superstates (Entry from Any State)
- `GLOBAL_INQUIRY`: General inquiries
- `GLOBAL_HELP`: Help requests
- `GLOBAL_CANCELLATION`: Order cancellation

##### ERROR_RECOVERY Substates
- `ERROR_RECOVERY.RETRY`: Retry last action
- `ERROR_RECOVERY.FALLBACK`: Fallback to safe state
- `ERROR_RECOVERY.ESCALATION`: Escalate to human

#### ConversationHSMEvents

**Event Categories:**

##### Lifecycle Events
- `START_CONVERSATION`: Initialize conversation
- `END_CONVERSATION`: End conversation

##### User Interaction Events
- `USER_PROVIDES_NAME`: User gives their name
- `USER_GREETS`: User greeting
- `USER_SAYS_GOODBYE`: User farewell

##### Menu and Ordering Events
- `REQUEST_MENU_INFO`: Request menu information
- `START_ORDER`: Start ordering process
- `ADD_ITEM`: Add item to cart
- `REMOVE_ITEM`: Remove item from cart
- `MODIFY_ITEM`: Modify existing item
- `SELECT_ITEM`: Select specific item
- `ASK_ABOUT_ITEM`: Ask about item details
- `REQUEST_RECOMMENDATIONS`: Request recommendations

##### Cart and Customization Events
- `VIEW_CART`: View current cart
- `CLEAR_CART`: Clear entire cart
- `ADD_MODIFICATION`: Add item modification
- `SET_QUANTITY`: Set item quantity
- `CONFIRM_ITEM`: Confirm item configuration
- `CANCEL_ITEM`: Cancel item configuration

##### Order Flow Events
- `COMPLETE_ORDER`: Complete ordering
- `VALIDATE_ORDER`: Validate order details
- `ORDER_VALID`: Order validation successful
- `ORDER_INVALID`: Order validation failed
- `MODIFY_ORDER`: Modify existing order
- `CONFIRM_ORDER`: Confirm final order
- `REJECT_ORDER`: Reject order

##### Fulfillment Events
- `FULFILL_ORDER`: Begin order fulfillment
- `PROVIDE_DELIVERY_INFO`: Provide delivery information
- `CHOOSE_PICKUP`: Choose pickup option
- `COMPLETE_INTERACTION`: Complete interaction

##### Error and Navigation Events
- `ERROR_OCCURRED`: Error occurred
- `RETRY_LAST_ACTION`: Retry last action
- `ESCALATE_DUE_TO_ERROR`: Escalate due to error
- `FALLBACK_TO_MAIN_MENU`: Fallback to main menu
- `GO_BACK`: Go to previous state
- `START_OVER`: Start conversation over
- `REPEAT`: Repeat last response

#### HSMStateDefinition

```python
@dataclass
class HSMStateDefinition:
    """Definition of a hierarchical state."""
    name: str
    parent_state_name: Optional[str] = None
    initial_substate_name: Optional[str] = None
    on_enter: Optional[Callable] = None
    on_exit: Optional[Callable] = None
    handle_event: Optional[Callable] = None
    substates: List[str] = field(default_factory=list)
```

**Key Methods:**
- `add_substate(substate_name)`: Add a substate
- `is_parent_of(state_name, all_states)`: Check parent relationship

#### HSMEvent

```python
class HSMEvent:
    """Base class for HSM events."""
    
    def __init__(self, name: str, data: Optional[Dict[str, Any]] = None):
        self.name = name
        self.data = data or {}
```

#### HSMStateHandler (Abstract Base)

```python
class HSMStateHandler(ABC):
    """Abstract base class for HSM state handlers."""
    
    def __init__(self, state_name: str):
        self.state_name = state_name
        self.logger = get_logger(f"{__name__}.{state_name}")
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """Called when entering this state."""
        
    async def on_exit(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """Called when exiting this state."""
    
    @abstractmethod
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """Handle an event in this state."""
        pass
```

### HSM Manager

#### HSMManager Class

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/fsm/hsm_manager.py`

#### Purpose
Manages the Hierarchical State Machine for conversations, coordinates state transitions, event handling, and maintains the state hierarchy.

#### Initialization
```python
def __init__(self):
    """Initialize the HSM Manager."""
    self.states: Dict[str, HSMStateDefinition] = {}
    self.handlers: Dict[str, HSMStateHandler] = {}
    self.transitions: Dict[str, List[HSMTransition]] = defaultdict(list)
    self.state_store = hsm_state_store
    
    # Initialize with default conversation states
    self._initialize_states()
```

#### State Handler Registration

**Automatic Handler Registration:**
```python
def _register_default_handlers(self):
    """Register all default HSM state handlers."""
    # Main state handlers
    self.register_handler(ConversationHSMStates.GREETING, GreetingHSMHandler())
    self.register_handler(ConversationHSMStates.MAIN_MENU, MainMenuHSMHandler())
    self.register_handler(ConversationHSMStates.COMPLETION, CompletionHandler())
    
    # Ordering handlers
    self.register_handler(ConversationHSMStates.ORDERING, OrderingSuperStateHandler())
    self.register_handler(ConversationHSMStates.ORDERING_BROWSING, OrderingBrowsingHandler())
    self.register_handler(ConversationHSMStates.ORDERING_MENU_INQUIRY, OrderingMenuInquiryHandler())
    # ... (continues for all states)
```

#### Event Handling

```python
async def handle_event(self, call_sid: str, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
    """Process an event for a conversation."""
```

**Process Flow:**
1. Get current state configuration
2. Process event from leaf to root (event bubbling)
3. Check for transitions from each state
4. Evaluate guard conditions
5. Execute transition actions
6. Let state handlers process unhandled events
7. Perform state transition if target found
8. Return new leaf state

#### State Transition Logic

```python
async def _transition_to(self, call_sid: str, target_state_name: str, event: HSMEvent, context: Dict[str, Any]) -> None:
    """Perform a state transition."""
```

**Transition Process:**
1. Calculate transition path (exit and enter paths)
2. Exit states from leaf to common ancestor
3. Update state path in storage
4. Enter states from common ancestor to target
5. Recursively enter initial substates

**Path Calculation:**
```python
def _calculate_transition_path(self, current_path: List[str], target_state_name: str) -> Tuple[List[str], List[str]]:
    """Calculate which states to exit and enter for a transition."""
    # Build target path
    target_path = self._build_state_path(target_state_name)
    
    # Find common ancestor
    common_length = 0
    for i in range(min(len(current_path), len(target_path))):
        if current_path[i] == target_path[i]:
            common_length = i + 1
        else:
            break
    
    # States to exit (in reverse order)
    exit_path = current_path[common_length:][::-1]
    
    # States to enter
    enter_path = target_path[common_length:]
    
    return exit_path, enter_path
```

#### State Lifecycle Management

**Enter State:**
```python
async def _enter_state(self, call_sid: str, state_name: str, event: Optional[HSMEvent], context: Dict[str, Any]) -> None:
    """Execute entry actions for a state."""
    state_def = self.states.get(state_name)
    if state_def and state_def.on_enter:
        await state_def.on_enter(context, event)
    
    handler = self.handlers.get(state_name)
    if handler:
        await handler.on_enter(context, event)
```

**Exit State:**
```python
async def _exit_state(self, call_sid: str, state_name: str, event: Optional[HSMEvent], context: Dict[str, Any]) -> None:
    """Execute exit actions for a state."""
    handler = self.handlers.get(state_name)
    if handler:
        await handler.on_exit(context, event)
    
    state_def = self.states.get(state_name)
    if state_def and state_def.on_exit:
        await state_def.on_exit(context, event)
```

**Singleton Instance:**
```python
# Global instance for easy access
hsm_manager = HSMManager()
```

---

## FSM Integration

### Core FSM Components (Compatibility Layer)

**Location**: `/home/proxyie/MySoftware/RedBarSushiAI/app/fsm/core.py`

#### Purpose
Provides backwards compatibility with existing FSM-based code while using HSM implementation underneath.

#### ConversationState (Compatibility Enum)
```python
class ConversationState(Enum):
    """Backwards compatibility enum for conversation states."""
    INITIAL = ConversationHSMStates.INITIAL
    GREETING = ConversationHSMStates.GREETING
    MAIN_MENU = ConversationHSMStates.MAIN_MENU
    ORDERING = ConversationHSMStates.ORDERING
    VALIDATION = ConversationHSMStates.VALIDATION
    CONFIRMATION = ConversationHSMStates.CONFIRMATION
    FULFILLMENT = ConversationHSMStates.FULFILLMENT
    COMPLETION = ConversationHSMStates.COMPLETION
    ERROR_RECOVERY = ConversationHSMStates.ERROR_RECOVERY
    ESCALATION = ConversationHSMStates.ESCALATION
```

#### ConversationEvent (Compatibility Enum)
```python
class ConversationEvent(Enum):
    """Backwards compatibility enum for conversation events."""
    START_CONVERSATION = ConversationHSMEvents.START_CONVERSATION
    END_CONVERSATION = ConversationHSMEvents.END_CONVERSATION
    USER_GREETS = ConversationHSMEvents.USER_GREETS
    USER_SAYS_GOODBYE = ConversationHSMEvents.USER_SAYS_GOODBYE
    REQUEST_MENU_INFO = ConversationHSMEvents.REQUEST_MENU_INFO
    START_ORDER = ConversationHSMEvents.START_ORDER
    ADD_ITEM = ConversationHSMEvents.ADD_ITEM
    REMOVE_ITEM = ConversationHSMEvents.REMOVE_ITEM
    MODIFY_ITEM = ConversationHSMEvents.MODIFY_ITEM
    SELECT_ITEM = ConversationHSMEvents.SELECT_ITEM
```

#### AsyncConversationFSM (Compatibility Wrapper)
```python
class AsyncConversationFSM:
    """
    Async Finite State Machine for conversation management.
    This is a compatibility wrapper around the HSM implementation.
    """
    
    def __init__(self, initial_state: ConversationState = ConversationState.GREETING):
        """Initialize the FSM with HSM backend."""
        self.hsm_manager = BaseHSMManager()
        self.current_state = initial_state
        self.handlers: Dict[ConversationState, AsyncStateHandler] = {}
```

---

## Error Handling & Recovery

### Error Recovery States

#### ERROR_RECOVERY Superstates
- `ERROR_RECOVERY.RETRY`: Attempt to retry the last action
- `ERROR_RECOVERY.FALLBACK`: Fall back to a safe state (usually MAIN_MENU)
- `ERROR_RECOVERY.ESCALATION`: Escalate to human assistance

#### Error Handling in Orchestrator

```python
try:
    agent, response = await self._process_with_appropriate_agent(current_leaf, input_text, context)
except Exception as e:
    logger.error(f"Agent processing error: {str(e)}", exc_info=True)
    # Transition to ERROR state
    error_event = HSMEvent(ConversationHSMEvents.ERROR_OCCURRED, {"error": str(e)})
    await hsm_manager.handle_event(call_sid, error_event, context)
    # Return error response
    return {
        "text": "I'm sorry, I encountered an error processing your request. Please try again or ask for assistance.",
        "handled": True,
        "agent": "ErrorHandler",
        "error": str(e),
        "state": ConversationHSMStates.ERROR_RECOVERY
    }
```

#### Graceful Degradation

**AI Fallbacks:**
- When OpenAI API fails, agents return structured fallback responses
- No hardcoded fallbacks - proper error messages instead
- Conversation continues with reduced functionality

**Database Fallbacks:**
- Session creation for database agents when needed
- Graceful handling of database unavailability
- Error messages guide users to retry

---

## Performance Optimizations

### AI Processing Optimizations

#### Token Limits
- Frontline Agent: `settings.FRONTEND_AGENT_MAX_TOKENS`
- Menu Agent: `settings.MENU_AGENT_MAX_TOKENS` (default: 256)
- Cart Agent: `settings.CART_AGENT_MAX_TOKENS` (default: 256)

#### Message Building Optimization
```python
def _build_messages(self, input_text: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build message history for AI context - OPTIMIZED for speed."""
    # Combine all system context into ONE message for efficiency
    # Add essential context only
    # Add last 4 messages for better context understanding (optimized)
```

#### Fast Response System
```python
async def get_fast_response(self, input_text: str, context: Dict[str, Any]) -> str:
    """Get fast, contextual response without full AI processing."""
    # Quick responses based on state and input patterns
    # Used for immediate feedback while full processing happens
```

#### Streaming Support
- Real-time response streaming for faster perceived response times
- Sentence-boundary chunking for natural delivery
- Fallback to non-streaming when tools are required

### Database Optimizations

#### Connection Pooling
- Async SQLAlchemy 2.0 with connection pooling
- Reuse of database sessions across agent calls
- Lazy session creation only when needed

#### Caching Strategies
- Agent instance caching in factory
- Menu data caching with TTL (5 minutes)
- Response caching for common patterns (temporarily disabled for debugging)

### Context Synchronization
- Efficient context passing between agents
- Cart synchronization between agents and conversation store
- Minimal context copying to avoid performance overhead

---

## Integration Points

### Database Integration

#### Menu Integration
- Async menu matcher for intelligent item matching
- PLU-based item identification for POS integration
- Real-time availability checking
- Modifier group handling

#### Cart Persistence
- Redis-based cart storage via conversation store
- Atomic cart operations
- Price calculation with modifiers
- Cart synchronization across agents

### External Service Integration

#### OpenAI API Integration
- Connection pooling for API clients
- Timeout handling with graceful degradation
- Tool calling for structured interactions
- Intent detection with context awareness

#### Twilio Integration
- ConversationRelay for voice processing
- HTTP webhook handling (no WebSocket)
- TwiML generation for call routing
- Interruption handling for user barge-in

#### POS Integration (Deliverect)
- PLU mapping for order submission
- Real-time menu synchronization
- Order status tracking
- Availability updates

### State Persistence

#### Redis Integration
- HSM state persistence
- Conversation history storage
- Session management
- Cart data storage

#### Conversation Store
- Message history tracking
- Context preservation across calls
- Customer information persistence
- Order data management

### Agent Communication

#### Specialist Registration
```python
frontline_agent.register_specialist("menu", menu_agent)
frontline_agent.register_specialist("cart", cart_agent)
```

#### Tool Delegation
```python
async def delegate_to_specialist(self, role: str, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```

#### Context Synchronization
- Call SID tracking across agents
- Cart state synchronization
- Customer information sharing
- Conversation history access

---

## Conclusion

The RedBarSushiAI agent system represents a sophisticated implementation of modern conversational AI architecture. Key strengths include:

1. **Hierarchical State Management**: HSM provides flexible, nested state handling for complex conversation flows
2. **AI-First Design**: No hardcoded logic - everything uses intelligent LLM-based decision making
3. **Async Architecture**: Non-blocking operations throughout for optimal performance
4. **Tool-Based Interactions**: Structured function calling for reliable system integration
5. **Graceful Error Handling**: Comprehensive error recovery without fallback implementations
6. **Performance Optimization**: Streaming, caching, and connection pooling for fast response times

The system successfully balances intelligent AI capabilities with reliable system integration, providing a robust foundation for voice-based restaurant ordering.