"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.
"""
import os
import json
import logging
import traceback
from typing import Dict, List, Any, Optional, Tuple
import openai

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a function to log detailed information about OpenAI requests
def log_openai_request(model, messages, function_name=""):
    """Log detailed information about an OpenAI API request"""
    logger.info(f"[OPENAI-REQUEST] Function: {function_name}, Model: {model}")
    try:
        msg_summary = []
        for msg in messages:
            content = msg.get('content', '')
            if content and isinstance(content, str):
                truncated = content[:100] + "..." if len(content) > 100 else content
                msg_summary.append(f"{msg.get('role')}: {truncated}")
        logger.info(f"[OPENAI-MESSAGES] {'; '.join(msg_summary)}")
    except Exception as e:
        logger.error(f"[OPENAI-REQUEST-ERROR] Failed to log messages: {str(e)}")
    
# Add a function to log detailed information about OpenAI responses
def log_openai_response(response, function_name=""):
    """Log detailed information about an OpenAI API response"""
    logger.info(f"[OPENAI-RESPONSE] Function: {function_name}")
    try:
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message'):
                content = choice.message.content
                logger.info(f"[OPENAI-CONTENT] {content[:200]}...")  # Log first 200 chars
            elif hasattr(choice, 'text'):
                content = choice.text
                logger.info(f"[OPENAI-CONTENT] {content[:200]}...")  # Log first 200 chars
        logger.info(f"[OPENAI-FULL] {str(response)[:500]}...")  # Log first 500 chars
    except Exception as e:
        logger.error(f"[OPENAI-RESPONSE-ERROR] Failed to log response: {str(e)}")
        logger.error(f"[OPENAI-RESPONSE-RAW] {str(response)[:500]}...")

# Ensure OpenAI API key is set
OPENAI_API_KEY = "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"
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable not set! AI features will be limited.")
    # For production: use a fallback API key if available in a different file
    try:
        api_key_path = "/home/pegasus/mysite/openai_key.txt"
        if os.path.exists(api_key_path):
            with open(api_key_path, 'r') as f:
                OPENAI_API_KEY = f.read().strip()
                logger.info("Found API key in alternate location")
        # Also check some other common locations
        elif os.path.exists("/home/pegasus/openai_key.txt"):
            with open("/home/pegasus/openai_key.txt", 'r') as f:
                OPENAI_API_KEY = f.read().strip()
                logger.info("Found API key in home directory")
        elif os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", "openai_key.txt")):
            with open(os.path.join(os.path.dirname(__file__), "..", "..", "openai_key.txt"), 'r') as f:
                OPENAI_API_KEY = f.read().strip()
                logger.info("Found API key in project root")
    except Exception as e:
        logger.error(f"Error loading API key from file: {e}")

# If we have an API key, set it for OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Check if OpenAI version supports the Agent API
try:
    # Only import if we have an API key
    if OPENAI_API_KEY:
        from openai.agent import Agent
        from openai.agent.types import AgentAction, AgentFinish, AgentStep
        AGENT_API_AVAILABLE = True
    else:
        AGENT_API_AVAILABLE = False
except ImportError:
    AGENT_API_AVAILABLE = False
    # Using older version of OpenAI API - will use alternative implementation

# For non-agent API fallback, test if we can access the API at all
if not AGENT_API_AVAILABLE and OPENAI_API_KEY:
    # Try to confirm API key works
    try:
        # Simple test call
        messages = [{"role": "user", "content": "Test"}]
        
        # Log the API request
        log_openai_request("gpt-4o", messages, "api_key_test")
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1
            )
            
            # Log the API response
            log_openai_response(response, "api_key_test")
            
            # If we got here, API key works for chat completions
            logger.info("OpenAI API key confirmed working for chat completions")
        except Exception as e:
            logger.error(f"Error during OpenAI API call: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    except Exception as e:
        logger.error(f"Error testing OpenAI API key: {e}")
        # Mark as unavailable so we use simpler fallbacks
        OPENAI_API_KEY = None

from app.utils.menu_utils import load_menu_data, find_menu_item_by_name

class SushiMenuTool:
    """A tool for querying the sushi menu."""
    
    def __init__(self):
        """Initialize the tool with menu data."""
        self.menu_data = load_menu_data()
    
    def search_menu(self, query: str) -> Dict[str, Any]:
        """
        Search the menu for items matching the query.
        
        Args:
            query: The search query
            
        Returns:
            dict: The search results
        """
        results = []
        query_lower = query.lower().strip()
        
        # First try to find exact matches
        item = find_menu_item_by_name(query)
        if item:
            return {"found": True, "items": [item], "query": query}
        
        # Then try to find partial matches
        name_variants = self.menu_data.get("name_variants", {})
        matching_variants = []
        
        for variant, item_name in name_variants.items():
            if query_lower in variant:
                matching_variants.append((variant, item_name))
        
        # Find the actual items for the matching variants
        for _, item_name in matching_variants:
            for item in self.menu_data.get("items", []):
                if item.get("name") == item_name and item not in results:
                    results.append(item)
        
        return {
            "found": len(results) > 0,
            "items": results,
            "query": query
        }
    
    def get_menu_categories(self) -> List[str]:
        """
        Get all menu categories.
        
        Returns:
            list: All menu categories
        """
        categories = set()
        for item in self.menu_data.get("items", []):
            logger.info(f"item: {item.name}")
            category = item.get("category")
            if category:
                categories.add(category)
        return sorted(list(categories))
    
    def get_items_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all items in a category.
        
        Args:
            category: The category name
            
        Returns:
            list: All items in the category
        """
        results = []
        category_lower = category.lower().strip()
        
        for item in self.menu_data.get("items", []):
            item_category = item.get("category", "").lower()
            if item_category == category_lower:
                results.append(item)
        
        return results
    
    def get_details(self, item_name: str) -> Dict[str, Any]:
        """
        Get details for a specific item.
        
        Args:
            item_name: The name of the item
            
        Returns:
            dict: The item details
        """
        item = find_menu_item_by_name(item_name)
        if not item:
            return {"found": False, "item_name": item_name}
        
        # Get modifiers for this item if any
        item_modifiers = []
        modifier_groups = item.get("modifierGroups", [])
        
        for group_id in modifier_groups:
            for group in self.menu_data.get("modifierGroups", []):
                if group.get("id") == group_id:
                    group_modifiers = []
                    for mod_id in group.get("modifiers", []):
                        for modifier in self.menu_data.get("modifiers", []):
                            if modifier.get("id") == mod_id:
                                group_modifiers.append(modifier)
                    
                    if group_modifiers:
                        item_modifiers.append({
                            "group_name": group.get("name"),
                            "min": group.get("minAllowed", 0),
                            "max": group.get("maxAllowed", 999),
                            "modifiers": group_modifiers
                        })
        
        return {
            "found": True,
            "item": item,
            "modifiers": item_modifiers
        }

# Check if OpenAI Agent API is available, if not use alternative implementation
if AGENT_API_AVAILABLE and OPENAI_API_KEY:
    class OrderParsingAgent:
        """Agent for parsing customer orders."""
        
        def __init__(self):
            """Initialize the agent."""
            self.menu_tool = SushiMenuTool()
            self.agent = self._create_agent()
        
        def _create_agent(self) -> Agent:
            """
            Create the OpenAI agent.
            
            Returns:
                Agent: The configured OpenAI agent
            """
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_menu",
                        "description": "Search for menu items matching a query",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_menu_categories",
                        "description": "Get all menu categories",
                        "parameters": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_items_by_category",
                        "description": "Get all items in a category",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "description": "The category name"
                                }
                            },
                            "required": ["category"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_details",
                        "description": "Get details for a specific item",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "item_name": {
                                    "type": "string",
                                    "description": "The name of the item"
                                }
                            },
                            "required": ["item_name"]
                        }
                    }
                }
            ]
            
            # Create the agent with appropriate tools and model
            agent = Agent(
                model="gpt-4o",
                instructions="""
                You are an assistant that helps parse customer food orders for a sushi restaurant. 
                Your job is to:
                1. Identify menu items in customer orders
                2. Extract quantity information
                3. Parse any modifiers or special requests
                4. Verify all items exist in the actual menu
                5. Return the full order in a structured format
                
                Only respond with items that are actually on the menu. If an item requested is not found,
                try to find the closest match or recommend alternatives. 
                
                Always return:
                - List of items, each with: name (exactly as in menu), quantity, reference_handler, and price
                - Any modifiers for each item with their quantities
                """,
                tools=tools
            )
            
            # Register the tool implementations
            agent.tools.search_menu = self.menu_tool.search_menu
            agent.tools.get_menu_categories = self.menu_tool.get_menu_categories
            agent.tools.get_items_by_category = self.menu_tool.get_items_by_category
            agent.tools.get_details = self.menu_tool.get_details
            
            return agent
        
        def parse_order(self, order_text: str) -> Dict[str, Any]:
            """
            Parse a natural language order into structured data.
            
            Args:
                order_text: The customer's order text
                
            Returns:
                dict: The parsed order
            """
            try:
                # Initialize the agent
                thread = self.agent.create_thread()
                
                # Log agent initialization
                logger.info(f"[AGENT-ORDER] Initializing order parsing agent for: '{order_text}'")
                
                # Send the order message
                message = thread.messages.create(role="user", content=order_text)
                logger.info(f"[AGENT-MESSAGE] Created message with ID: {message.id}")
                
                # Run the agent
                run = thread.runs.create()
                logger.info(f"[AGENT-RUN] Created run with ID: {run.id}")
                
                # Wait for the run to complete
                run = thread.runs.wait(run_id=run.id)
                logger.info(f"[AGENT-COMPLETE] Run completed with status: {run.status}")
                
                # Get the agent's final response
                messages = thread.messages.list(after=message.id)
                response = list(messages)[0].content[0].text.value
                logger.info(f"[AGENT-RESPONSE] Received response of length: {len(response)}")
                logger.info(f"[AGENT-CONTENT] Response preview: {response[:200]}...")
                
                # Extract the structured order from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        logger.info(f"[AGENT-JSON] Extracted JSON from code block, length: {len(json_str)}")
                        parsed_order = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        logger.info("[AGENT-JSON] Attempting to parse entire response as JSON")
                        parsed_order = json.loads(response)
                    
                    # Log the parsed result
                    logger.info(f"[AGENT-PARSE] Successfully parsed response as JSON with keys: {list(parsed_order.keys())}")
                    
                    # Ensure the parsed order has the required structure
                    if "items" not in parsed_order:
                        parsed_order = {"items": []}
                        logger.warning("[AGENT-VALIDATE] Missing 'items' key in parsed order, adding empty items list")
                    
                    # Verify all items have required fields
                    for item in parsed_order["items"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning("[AGENT-VALIDATE] Item missing 'name', setting to 'Unknown Item'")
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(f"[AGENT-VALIDATE] Item '{item['name']}' missing quantity, defaulting to 1")
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get("reference_handler", "")
                                logger.info(f"[AGENT-PRICE] Found price for '{item['name']}': ${item['price']}")
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                                logger.warning(f"[AGENT-PRICE] Could not find price for '{item['name']}', using 0.0")
                        if "modifier" not in item:
                            item["modifier"] = []
                            logger.info(f"[AGENT-VALIDATE] Added empty modifier list for '{item['name']}'")
                    
                    return parsed_order
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(f"[AGENT-JSON-ERROR] Failed to parse agent response as JSON: {response}")
                    return {"items": [], "error": "Failed to parse response"}
                    
            except Exception as e:
                logger.error(f"[AGENT-ERROR] Error in parse_order: {str(e)}")
                logger.error(f"[AGENT-TRACEBACK] {traceback.format_exc()}")
                return {"items": [], "error": str(e)}

    class OrderModificationAgent:
        """Agent for modifying existing orders."""
        
        def __init__(self):
            """Initialize the agent."""
            self.menu_tool = SushiMenuTool()
            self.agent = self._create_agent()
        
        def _create_agent(self) -> Agent:
            """
            Create the OpenAI agent.
            
            Returns:
                Agent: The configured OpenAI agent
            """
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_menu",
                        "description": "Search for menu items matching a query",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_details",
                        "description": "Get details for a specific item",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "item_name": {
                                    "type": "string",
                                    "description": "The name of the item"
                                }
                            },
                            "required": ["item_name"]
                        }
                    }
                }
            ]
            
            # Create the agent with appropriate tools and model
            agent = Agent(
                model="gpt-4o",
                instructions="""
                You are an assistant that helps modify existing food orders. 
                Your job is to:
                1. Understand the current order
                2. Parse the customer's modification request
                3. Identify items to add, remove, or modify
                4. Return the updated order in a structured format
                
                Only include items that are actually on the menu. If an item requested is not found,
                try to find the closest match or recommend alternatives.
                
                Always return the full modified order with:
                - 'additions': List of items to add
                - 'removals': List of items to remove
                """,
                tools=tools
            )
            
            # Register the tool implementations
            agent.tools.search_menu = self.menu_tool.search_menu
            agent.tools.get_details = self.menu_tool.get_details
            
            return agent
        
        def modify_order(self, current_order: Dict[str, Any], modification_text: str) -> Dict[str, Any]:
            """
            Modify an existing order based on customer request.
            
            Args:
                current_order: The current order items
                modification_text: The customer's modification request
                
            Returns:
                dict: The modification instructions (additions and removals)
            """
            try:
                # Initialize the agent
                thread = self.agent.create_thread()
                logger.info(f"[AGENT-MODIFY] Initializing modification agent for: '{modification_text}'")
                
                # Format the current order
                current_order_str = json.dumps(current_order, indent=2)
                logger.info(f"[AGENT-CURRENT] Current order has {len(current_order.get('items', []))} items")
                
                # Send the context and modification request
                message = thread.messages.create(
                    role="user", 
                    content=f"Current order:\n{current_order_str}\n\nModification request: {modification_text}"
                )
                logger.info(f"[AGENT-MESSAGE] Created message with ID: {message.id}")
                
                # Run the agent
                run = thread.runs.create()
                logger.info(f"[AGENT-RUN] Created run with ID: {run.id}")
                
                # Wait for the run to complete
                run = thread.runs.wait(run_id=run.id)
                logger.info(f"[AGENT-COMPLETE] Run completed with status: {run.status}")
                
                # Get the agent's final response
                messages = thread.messages.list(after=message.id)
                response = list(messages)[0].content[0].text.value
                logger.info(f"[AGENT-RESPONSE] Received response of length: {len(response)}")
                logger.info(f"[AGENT-CONTENT] Response preview: {response[:200]}...")
                
                # Extract the structured modifications from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        logger.info(f"[AGENT-JSON] Extracted JSON from code block, length: {len(json_str)}")
                        modifications = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        logger.info("[AGENT-JSON] Attempting to parse entire response as JSON")
                        modifications = json.loads(response)
                    
                    # Log the parsed result
                    logger.info(f"[AGENT-PARSE] Successfully parsed response as JSON with keys: {list(modifications.keys())}")
                    
                    # Ensure the modifications have the required structure
                    if "additions" not in modifications:
                        modifications["additions"] = []
                        logger.warning("[AGENT-VALIDATE] Missing 'additions' key in modifications, adding empty list")
                    if "removals" not in modifications:
                        modifications["removals"] = []
                        logger.warning("[AGENT-VALIDATE] Missing 'removals' key in modifications, adding empty list")
                    
                    # Verify additions have required fields
                    for item in modifications["additions"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning("[AGENT-VALIDATE] Addition missing 'name', setting to 'Unknown Item'")
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(f"[AGENT-VALIDATE] Addition '{item['name']}' missing quantity, defaulting to 1")
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get("reference_handler", "")
                                logger.info(f"[AGENT-PRICE] Found price for addition '{item['name']}': ${item['price']}")
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                                logger.warning(f"[AGENT-PRICE] Could not find price for addition '{item['name']}', using 0.0")
                        if "modifier" not in item:
                            item["modifier"] = []
                            logger.info(f"[AGENT-VALIDATE] Added empty modifier list for addition '{item['name']}'")
                    
                    # Verify removals have required fields
                    for item in modifications["removals"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning("[AGENT-VALIDATE] Removal missing 'name', setting to 'Unknown Item'")
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(f"[AGENT-VALIDATE] Removal '{item['name']}' missing quantity, defaulting to 1")
                    
                    return modifications
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(f"[AGENT-JSON-ERROR] Failed to parse agent response as JSON: {response}")
                    return {"additions": [], "removals": [], "error": "Failed to parse response"}
                    
            except Exception as e:
                logger.error(f"[AGENT-ERROR] Error in modify_order: {str(e)}")
                logger.error(f"[AGENT-TRACEBACK] {traceback.format_exc()}")
                return {"additions": [], "removals": [], "error": str(e)}
else:
    # Fallback implementation - includes both no API key and no Agent API situations
    class OrderParsingAgent:
        """Fallback implementation of OrderParsingAgent."""
        
        def __init__(self):
            """Initialize the agent."""
            self.menu_tool = SushiMenuTool()
        
        def parse_order(self, order_text: str) -> Dict[str, Any]:
            """
            Parse a natural language order into structured data.
            
            Args:
                order_text: The customer's order text
                
            Returns:
                dict: The parsed order
            """
            try:
                # For OpenAI API available but no agent API
                if OPENAI_API_KEY:
                    # Get the menu categories to provide context
                    categories = self.menu_tool.get_menu_categories()
                    
                    # Prepare messages for the API call
                    messages = [
                        {"role": "system", "content": "You are a restaurant order parser. Extract menu items from customer orders into JSON."},
                        {"role": "user", "content": f"Extract menu items from this order: {order_text}\nOur menu has these categories: {', '.join(categories)}\nRespond with a JSON object containing an 'items' array of item names."}
                    ]
                    
                    # Log the API request
                    logger.info(f"[ORDER-PARSE] Processing order text: '{order_text}'")
                    logger.info(f"[ORDER-PARSE] Using menu categories: {categories}")
                    log_openai_request("gpt-4o", messages, "parse_order")
                    
                    try:
                        # Initial request to identify potential items
                        response = openai.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            response_format={"type": "json_object"}
                        )
                        
                        # Log the response
                        log_openai_response(response, "parse_order")
                        logger.info("[ORDER-PARSE] Successfully received OpenAI response")
                        
                        # Extract items mentioned in the order
                        initial_parse = json.loads(response.choices[0].message.content)
                        potential_items = initial_parse.get("items", [])
                        logger.info(f"[ORDER-PARSE] Extracted {len(potential_items)} potential items from order")
                    except Exception as e:
                        logger.error(f"[ORDER-PARSE-ERROR] OpenAI API error: {str(e)}")
                        logger.error(f"[ORDER-PARSE-TRACEBACK] {traceback.format_exc()}")
                        raise
                else:
                    # No OpenAI API - simple keyword matching
                    logger.warning("No OpenAI API key available - using simple keyword matching")
                    items = self.menu_tool.menu_data.get("items", [])
                    name_variants = self.menu_tool.menu_data.get("name_variants", {})
                    
                    # Simple keyword matching
                    order_lower = order_text.lower()
                    potential_items = []
                    
                    # Check direct matches with name variants
                    for variant, item_name in name_variants.items():
                        if variant in order_lower:
                            potential_items.append(item_name)
                    
                    # Check direct matches with item names
                    for item in items:
                        item_name = item.get("name", "").lower()
                        if item_name and item_name in order_lower and item.get("name") not in potential_items:
                            potential_items.append(item.get("name"))
                
                # Look up each item in the menu for verification
                verified_items = []
                unverified_items = []
                logger.info(f"[ORDER-VERIFY] Starting menu item verification for {len(potential_items)} potential items")

                # First pass: Current verification strategy using search_menu
                for item_name in potential_items:
                    # Search menu for this item
                    logger.info(f"[ORDER-VERIFY-PASS1] Verifying item: '{item_name}' using search_menu")
                    search_result = self.menu_tool.search_menu(item_name)
                    if search_result.get("found"):
                        for menu_item in search_result.get("items", []):
                            logger.info(f"[ORDER-VERIFY-PASS1-SUCCESS] Found '{item_name}' as '{menu_item.get('name')}' (${menu_item.get('price', 0.0)})")
                            verified_items.append({
                                "name": menu_item.get("name"),
                                "price": menu_item.get("price", 0.0),
                                "reference_handler": menu_item.get("reference_handler", ""),
                                "quantity": 1,  # Default quantity
                                "modifier": []  # Default empty modifiers
                            })
                    else:
                        logger.warning(f"[ORDER-VERIFY-PASS1-FAIL] Could not verify '{item_name}' in first pass")
                        unverified_items.append(item_name)

                # Second pass: Direct lookup with find_menu_item_by_name for items not found in first pass
                if unverified_items:
                    still_unverified = []
                    logger.info(f"[ORDER-VERIFY-PASS2] Starting second pass verification for {len(unverified_items)} items")
                    
                    for item_name in unverified_items:
                        logger.info(f"[ORDER-VERIFY-PASS2] Verifying item: '{item_name}' using direct lookup")
                        menu_item = find_menu_item_by_name(item_name)
                        if menu_item:
                            logger.info(f"[ORDER-VERIFY-PASS2-SUCCESS] Direct lookup found '{item_name}' as '{menu_item.get('name')}' (${menu_item.get('price', 0.0)})")
                            verified_items.append({
                                "name": menu_item.get("name"),
                                "price": menu_item.get("price", 0.0),
                                "reference_handler": menu_item.get("reference_handler", ""),
                                "quantity": 1,
                                "modifier": []
                            })
                        else:
                            logger.warning(f"[ORDER-VERIFY-PASS2-FAIL] Could not verify '{item_name}' in second pass")
                            still_unverified.append(item_name)
                    
                    # Third pass: Partial/fuzzy matching with menu items and variants
                    if still_unverified:
                        logger.info(f"[ORDER-VERIFY-PASS3] Starting third pass verification with fuzzy matching for {len(still_unverified)} items")
                        name_variants = self.menu_tool.menu_data.get("name_variants", {})
                        menu_items = self.menu_tool.menu_data.get("items", [])
                        
                        for item_name in still_unverified:
                            item_lower = item_name.lower()
                            found = False
                            
                            # Try fuzzy matching with name variants
                            for variant, menu_item_name in name_variants.items():
                                # Check if item name is contained in variant or variant is contained in item name
                                if item_lower in variant.lower() or variant.lower() in item_lower:
                                    logger.info(f"[ORDER-VERIFY-PASS3-FUZZY] Found partial match: '{item_name}' ~ '{variant}' → '{menu_item_name}'")
                                    menu_item = find_menu_item_by_name(menu_item_name)
                                    if menu_item:
                                        logger.info(f"[ORDER-VERIFY-PASS3-SUCCESS] Fuzzy match found '{item_name}' as '{menu_item.get('name')}' (${menu_item.get('price', 0.0)})")
                                        verified_items.append({
                                            "name": menu_item.get("name"),
                                            "price": menu_item.get("price", 0.0),
                                            "reference_handler": menu_item.get("reference_handler", ""),
                                            "quantity": 1,
                                            "modifier": []
                                        })
                                        found = True
                                        break
                            
                            # If still not found, try matching directly against menu items
                            if not found:
                                best_match = None
                                best_match_score = 0
                                
                                for menu_item in menu_items:
                                    menu_item_name = menu_item.get("name", "").lower()
                                    # Check partial containment in either direction
                                    if menu_item_name and (item_lower in menu_item_name or menu_item_name in item_lower):
                                        # Calculate a simple match score (longer matches are better)
                                        match_length = min(len(item_lower), len(menu_item_name))
                                        if match_length > best_match_score:
                                            best_match = menu_item
                                            best_match_score = match_length
                                
                                if best_match:
                                    logger.info(f"[ORDER-VERIFY-PASS3-SUCCESS] Direct fuzzy match found '{item_name}' as '{best_match.get('name')}' (${best_match.get('price', 0.0)})")
                                    verified_items.append({
                                        "name": best_match.get("name"),
                                        "price": best_match.get("price", 0.0),
                                        "reference_handler": best_match.get("reference_handler", ""),
                                        "quantity": 1,
                                        "modifier": []
                                    })
                                    found = True
                            
                            if not found:
                                logger.error(f"[ORDER-VERIFY-FAIL] Failed to verify item '{item_name}' after all verification passes")

                # Log summary of verification process
                verification_rate = len(verified_items) / len(potential_items) if potential_items else 0
                logger.info(f"[ORDER-VERIFY-SUMMARY] Verification complete: {len(verified_items)}/{len(potential_items)} items verified ({verification_rate:.0%})")
                for item in verified_items:
                    logger.info(f"[ORDER-ITEM-VERIFIED] {item.get('name')} (${item.get('price'):.2f})")

                # Final structured order
                return {
                    "items": verified_items,
                    "intent": "order_food" if verified_items else "other"
                }
                
            except Exception as e:
                logger.error(f"[ORDER-ERROR] Error in parse_order fallback: {str(e)}")
                logger.error(f"[ORDER-TRACEBACK] {traceback.format_exc()}")
                return {"items": [], "error": str(e)}
    
    class OrderModificationAgent:
        """Fallback implementation of OrderModificationAgent."""
        
        def __init__(self):
            """Initialize the agent."""
            self.menu_tool = SushiMenuTool()
        
        def modify_order(self, current_order: Dict[str, Any], modification_text: str) -> Dict[str, Any]:
            """
            Modify an existing order based on customer request.
            
            Args:
                current_order: The current order items
                modification_text: The customer's modification request
                
            Returns:
                dict: The modification instructions (additions and removals)
            """
            try:
                # For OpenAI API available but no agent API
                if OPENAI_API_KEY:
                    # Format the current order for the prompt
                    current_items = "\n".join([f"- {item.get('quantity', 1)}x {item.get('name')}" for item in current_order.get("items", [])])
                    
                    # Prepare messages for the API call
                    messages = [
                        {"role": "system", "content": "You are a sushi restaurant order modifier. Process order changes and return JSON."},
                        {"role": "user", "content": f"Current order:\n{current_items}\n\nModification request: {modification_text}\n\nReturn JSON with 'additions' and 'removals' arrays."}
                    ]
                    
                    # Log the request
                    logger.info(f"[MODIFY-ORDER] Processing modification: '{modification_text}'")
                    logger.info(f"[MODIFY-ORDER] Current order has {len(current_order.get('items', []))} items")
                    log_openai_request("gpt-4o", messages, "modify_order")
                    
                    try:
                        # Request to identify modifications
                        response = openai.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            response_format={"type": "json_object"}
                        )
                        
                        # Log the response
                        log_openai_response(response, "modify_order")
                        logger.info("[MODIFY-ORDER] Successfully received OpenAI response")
                        
                        # Parse the response
                        modifications = json.loads(response.choices[0].message.content)
                        logger.info(f"[MODIFY-ORDER] Parsed modifications: additions={len(modifications.get('additions', []))}, removals={len(modifications.get('removals', []))}")
                    except Exception as e:
                        logger.error(f"[MODIFY-ORDER-ERROR] OpenAI API error: {str(e)}")
                        logger.error(f"[MODIFY-ORDER-TRACEBACK] {traceback.format_exc()}")
                        raise
                else:
                    # No OpenAI API - very simple keyword matching
                    logger.warning("No OpenAI API key available - using simple keyword matching for modifications")
                    modifications = {"additions": [], "removals": []}
                    
                    # Extract possible add/remove keywords
                    mod_lower = modification_text.lower()
                    items = self.menu_tool.menu_data.get("items", [])
                    name_variants = self.menu_tool.menu_data.get("name_variants", {})
                    
                    # Very simple add/remove detection
                    is_addition = any(w in mod_lower for w in ["add", "want", "more", "with"])
                    is_removal = any(w in mod_lower for w in ["remove", "no", "without", "don't want", "cancel"])
                    
                    # Check current order items for potential removals
                    if is_removal:
                        for item in current_order.get("items", []):
                            item_name = item.get("name", "").lower()
                            if item_name and item_name in mod_lower:
                                modifications["removals"].append({
                                    "name": item.get("name"),
                                    "quantity": 1
                                })
                    
                    # Check all menu items for potential additions
                    if is_addition:
                        for variant, item_name in name_variants.items():
                            if variant in mod_lower:
                                # Only add it if not already in the list
                                if not any(add_item.get("name") == item_name for add_item in modifications["additions"]):
                                    menu_item = find_menu_item_by_name(item_name)
                                    if menu_item:
                                        modifications["additions"].append({
                                            "name": item_name,
                                            "quantity": 1,
                                            "price": menu_item.get("price", 0.0),
                                            "reference_handler": menu_item.get("reference_handler", ""),
                                            "modifier": []
                                        })
                
                # Ensure required structure
                if "additions" not in modifications:
                    modifications["additions"] = []
                if "removals" not in modifications:
                    modifications["removals"] = []
                
                # Verify and enhance additions (only if OpenAI API available)
                for item in modifications.get("additions", []):
                    if "name" in item:
                        menu_item = find_menu_item_by_name(item["name"])
                        if menu_item:
                            item["price"] = menu_item.get("price", 0.0)
                            item["reference_handler"] = menu_item.get("reference_handler", "")
                            if "quantity" not in item:
                                item["quantity"] = 1
                            if "modifier" not in item:
                                item["modifier"] = []
                
                return modifications
                
            except Exception as e:
                logger.error(f"[MODIFY-ERROR] Error in modify_order fallback: {str(e)}")
                logger.error(f"[MODIFY-TRACEBACK] {traceback.format_exc()}")
                return {"additions": [], "removals": [], "error": str(e)}


def analyze_user_input(input_text: str) -> Dict[str, Any]:
    """
    Analyze user input to determine intent and extract order items.
    
    Args:
        input_text: The user's input text
        
    Returns:
        dict: The analysis results
    """
    # Create an order parsing agent
    agent = OrderParsingAgent()
    
    # Parse the input
    logger.info(f"[ANALYZE-INPUT] Analyzing user input: '{input_text}'")
    parsed_order = agent.parse_order(input_text)
    logger.info(f"[PARSED-ORDER]: {parsed_order}")
    
    # Determine intent based on the parsed order
    if parsed_order.get("items"):
        logger.info(f"[ANALYZE-RESULT] Found {len(parsed_order.get('items', []))} items, intent: 'order_food'")
        return {
            "intent": "order_food",
            "menu_items": parsed_order.get("items", [])
        }
    
    # Default to "other" intent if no clear intent is determined
    logger.info("[ANALYZE-RESULT] No items found, intent: 'other'")
    return {"intent": "other"}


def get_order_modifications(user_input: str, current_order_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Use AI to interpret order modifications from user speech.
    
    Args:
        user_input: The user's modification request
        current_order_items: The current order items
        
    Returns:
        dict: The parsed modifications
    """
    # Prepare current order structure if provided
    current_order = {"items": current_order_items or []}
    
    # Create an order modification agent
    agent = OrderModificationAgent()
    
    # Get modifications
    logger.info(f"[ORDER-MODIFICATIONS] Processing modification request: '{user_input}'")
    modifications = agent.modify_order(current_order, user_input)
    
    logger.info(f"[ORDER-MODIFICATIONS] Found modifications: additions={len(modifications.get('additions', []))}, removals={len(modifications.get('removals', []))}")
    return modifications
