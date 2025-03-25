"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import openai

logger = logging.getLogger(__name__)

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
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=1
        )
        # If we got here, API key works for chat completions
        logger.info("OpenAI API key confirmed working for chat completions")
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
                
                # Send the order message
                message = thread.messages.create(role="user", content=order_text)
                
                # Run the agent
                run = thread.runs.create()
                
                # Wait for the run to complete
                run = thread.runs.wait(run_id=run.id)
                
                # Get the agent's final response
                messages = thread.messages.list(after=message.id)
                response = list(messages)[0].content[0].text.value
                
                # Extract the structured order from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        parsed_order = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        parsed_order = json.loads(response)
                    
                    # Ensure the parsed order has the required structure
                    if "items" not in parsed_order:
                        parsed_order = {"items": []}
                    
                    # Verify all items have required fields
                    for item in parsed_order["items"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                        if "quantity" not in item:
                            item["quantity"] = 1
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get("reference_handler", "")
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                        if "modifier" not in item:
                            item["modifier"] = []
                    
                    return parsed_order
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(f"Failed to parse agent response as JSON: {response}")
                    return {"items": [], "error": "Failed to parse response"}
                    
            except Exception as e:
                logger.error(f"Error in parse_order: {str(e)}")
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
                
                # Format the current order
                current_order_str = json.dumps(current_order, indent=2)
                
                # Send the context and modification request
                message = thread.messages.create(
                    role="user", 
                    content=f"Current order:\n{current_order_str}\n\nModification request: {modification_text}"
                )
                
                # Run the agent
                run = thread.runs.create()
                
                # Wait for the run to complete
                run = thread.runs.wait(run_id=run.id)
                
                # Get the agent's final response
                messages = thread.messages.list(after=message.id)
                response = list(messages)[0].content[0].text.value
                
                # Extract the structured modifications from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        modifications = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        modifications = json.loads(response)
                    
                    # Ensure the modifications have the required structure
                    if "additions" not in modifications:
                        modifications["additions"] = []
                    if "removals" not in modifications:
                        modifications["removals"] = []
                    
                    # Verify additions have required fields
                    for item in modifications["additions"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                        if "quantity" not in item:
                            item["quantity"] = 1
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get("reference_handler", "")
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                        if "modifier" not in item:
                            item["modifier"] = []
                    
                    # Verify removals have required fields
                    for item in modifications["removals"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                        if "quantity" not in item:
                            item["quantity"] = 1
                    
                    return modifications
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(f"Failed to parse agent response as JSON: {response}")
                    return {"additions": [], "removals": [], "error": "Failed to parse response"}
                    
            except Exception as e:
                logger.error(f"Error in modify_order: {str(e)}")
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
                    
                    # Initial request to identify potential items
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a sushi restaurant order parser. Extract menu items from customer orders into JSON."},
                            {"role": "user", "content": f"Extract menu items from this order: {order_text}\nOur menu has these categories: {', '.join(categories)}\nRespond with a JSON object containing an 'items' array of item names."}
                        ],
                        response_format={"type": "json_object"}
                    )
                    
                    # Extract items mentioned in the order
                    initial_parse = json.loads(response.choices[0].message.content)
                    potential_items = initial_parse.get("items", [])
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
                for item_name in potential_items:
                    # Search menu for this item
                    search_result = self.menu_tool.search_menu(item_name)
                    if search_result.get("found"):
                        for menu_item in search_result.get("items", []):
                            verified_items.append({
                                "name": menu_item.get("name"),
                                "price": menu_item.get("price", 0.0),
                                "reference_handler": menu_item.get("reference_handler", ""),
                                "quantity": 1,  # Default quantity
                                "modifier": []  # Default empty modifiers
                            })
                
                # Final structured order
                return {
                    "items": verified_items,
                    "intent": "order_food" if verified_items else "other"
                }
                
            except Exception as e:
                logger.error(f"Error in parse_order fallback: {str(e)}")
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
                    
                    # Request to identify modifications
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a sushi restaurant order modifier. Process order changes and return JSON."},
                            {"role": "user", "content": f"Current order:\n{current_items}\n\nModification request: {modification_text}\n\nReturn JSON with 'additions' and 'removals' arrays."}
                        ],
                        response_format={"type": "json_object"}
                    )
                    
                    # Parse the response
                    modifications = json.loads(response.choices[0].message.content)
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
                logger.error(f"Error in modify_order fallback: {str(e)}")
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
    parsed_order = agent.parse_order(input_text)
    
    # Determine intent based on the parsed order
    if parsed_order.get("items"):
        return {
            "intent": "order_food",
            "menu_items": parsed_order.get("items", [])
        }
    
    # Default to "other" intent if no clear intent is determined
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
    modifications = agent.modify_order(current_order, user_input)
    
    return modifications
