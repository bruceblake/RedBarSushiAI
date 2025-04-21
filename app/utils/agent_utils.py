"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.
"""

import os
import json
import logging
import traceback
from typing import Dict, List, Any
import openai

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a function to log detailed information about OpenAI requests


def log_openai_request(
    model: str, messages: List[Dict[str, Any]], function_name: str = ""
) -> None:
    """Log detailed information about an OpenAI API request"""
    logger.info(f"[OPENAI-REQUEST] Function: {function_name}, Model: {model}")
    try:
        msg_summary = []
        for msg in messages:
            content = msg.get("content", "")
            if content and isinstance(content, str):
                truncated = content[:100] + "..." if len(content) > 100 else content
                msg_summary.append(f"{msg.get('role')}: {truncated}")
        logger.info(f"[OPENAI-MESSAGES] {'; '.join(msg_summary)}")
    except Exception as e:
        logger.error(
            f"[OPENAI-REQUEST-ERROR] Failed to log messages: {str(e)}"
        )  # Broad except, but safe for logging


# Add a function to log detailed information about OpenAI responses
def log_openai_response(response: Any, function_name: str = "") -> None:
    """Log detailed information about an OpenAI API response"""
    logger.info(f"[OPENAI-RESPONSE] Function: {function_name}")
    try:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                content = choice.message.content
                logger.info(
                    f"[OPENAI-CONTENT] {content[:200]}..."
                )  # Log first 200 chars
            elif hasattr(choice, "text"):
                content = choice.text
                logger.info(
                    f"[OPENAI-CONTENT] {content[:200]}..."
                )  # Log first 200 chars
        logger.info(f"[OPENAI-FULL] {str(response)[:500]}...")  # Log first 500 chars
    except Exception as e:
        logger.error(
            f"[OPENAI-RESPONSE-ERROR] Failed to log response: {str(e)}"
        )  # Broad except, but safe for logging
        logger.error(f"[OPENAI-RESPONSE-RAW] {str(response)[:500]}...")


# Ensure OpenAI API key is set
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning(
        "OPENAI_API_KEY environment variable not set! AI features will be limited."
    )
    # For production: use a fallback API key if available in a different file
    try:
        api_key_path = "/home/pegasus/mysite/openai_key.txt"
        if os.path.exists(api_key_path):
            with open(api_key_path, "r") as f:
                OPENAI_API_KEY = f.read().strip()
                logger.info("Found API key in alternate location")
        # Also check some other common locations
        elif os.path.exists("/home/pegasus/openai_key.txt"):
            with open("/home/pegasus/openai_key.txt", "r") as f:
                OPENAI_API_KEY = f.read().strip()
                logger.info("Found API key in home directory")
        elif os.path.exists(
            os.path.join(os.path.dirname(__file__), "..", "..", "openai_key.txt")
        ):
            with open(
                os.path.join(os.path.dirname(__file__), "..", "..", "openai_key.txt"),
                "r",
            ) as f:
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
        log_openai_request("gpt-4.1-mini", messages, "api_key_test")

        try:
            response = openai.chat.completions.create(
                model="gpt-4.1-mini", messages=messages, max_tokens=1
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
        self.current_conversation = []  # To track conversation context

    def search_menu(self, query: str) -> Dict[str, Any]:
        """
        Search the menu for items matching the query.

        Args:
            query: The search query

        Returns:
            dict: The search results
        """
        # Add the query to the conversation context
        self.current_conversation.append({"role": "user", "content": query})
        context = {"conversation": self.current_conversation}
        
        # First try to find exact matches
        item = find_menu_item_by_name(query)
        if item:
            return {"found": True, "items": [item], "query": query}

        # If exact match fails, try AI matching
        try:
            # Import here to avoid circular imports
            from app.utils.menu_matcher import find_menu_item_ai
            
            ai_match = find_menu_item_ai(query, check_availability=False, context=context)
            if ai_match:
                logger.info(f"[MENU-TOOL] AI matcher found: {ai_match.get('name')} for '{query}'")
                return {"found": True, "items": [ai_match], "query": query}
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error in AI matching: {str(e)}")
            # Continue with fallback if AI matching fails

        # Fallback to traditional scoring system
        results = []
        scored_items = []
        query_lower = query.lower().strip()

        # Get all menu items and evaluate with a scoring system
        for item in self.menu_data.get("items", []):
            item_name = item.get("name", "").lower()

            # Skip empty names
            if not item_name:
                continue

            # Calculate match score
            score = 0

            # Check for direct matches
            if item_name == query_lower:
                score = 100
            elif query_lower in item_name:
                # Longer query matches are better
                score = 80 + min(len(query_lower), 15)
            elif item_name in query_lower:
                # If menu item is contained in query
                match_ratio = len(item_name) / len(query_lower)
                score = 60 + int(match_ratio * 20)

            # Word-level matching
            if score < 30:  # Only do word matching for lower-scoring matches
                query_words = set(query_lower.split())
                item_words = set(item_name.split())

                # Words in common
                common_words = query_words.intersection(item_words)

                if common_words:
                    # Calculate scores based on word overlap
                    word_match_ratio = (
                        len(common_words) / len(item_words) if item_words else 0
                    )
                    query_coverage = (
                        len(common_words) / len(query_words) if query_words else 0
                    )

                    # Combined score with higher weight for query coverage
                    word_score = int(
                        (word_match_ratio * 0.4 + query_coverage * 0.6) * 50
                    )
                    score = max(score, word_score)

            # Only include reasonably good matches
            if score >= 30:
                scored_items.append((item, score))

        # Sort by score
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Take the top results
        results = [item for item, _ in scored_items[:5]]

        return {
            "found": len(results) > 0,
            "items": results,
            "query": query,
            "debug_info": {
                "top_matches": (
                    [(item.get("name"), score) for item, score in scored_items[:3]]
                    if scored_items
                    else []
                )
            },
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

    def ai_match_item(self, item_name: str) -> Dict[str, Any]:
        """
        Match an item using AI-based matching.
        
        Args:
            item_name: The name or description of the item to match
            
        Returns:
            dict: The match results
        """
        self.current_conversation.append({"role": "user", "content": f"Find menu item: {item_name}"})
        context = {"conversation": self.current_conversation}
        
        try:
            # Import here to avoid circular imports
            from app.utils.menu_matcher import find_menu_item_ai
            
            ai_match = find_menu_item_ai(item_name, check_availability=False, context=context)
            if ai_match:
                logger.info(f"[MENU-TOOL] AI matcher found: {ai_match.get('name')} for '{item_name}'")
                return {
                    "found": True,
                    "item": ai_match,
                    "confidence": "high",
                    "matching_type": "ai_match"
                }
        except Exception as e:
            logger.error(f"[MENU-TOOL] Error in AI matching: {str(e)}")
            
        # If AI matching fails, try exact match as fallback
        item = find_menu_item_by_name(item_name)
        if item:
            return {
                "found": True,
                "item": item,
                "confidence": "exact",
                "matching_type": "exact_match"
            }
            
        # No match found
        return {"found": False, "item_name": item_name}
    
    def get_details(self, item_name: str) -> Dict[str, Any]:
        """
        Get details for a specific item.

        Args:
            item_name: The name of the item

        Returns:
            dict: The item details
        """
        # First try direct lookup
        item = find_menu_item_by_name(item_name)
        
        # If direct lookup fails, try AI matching
        if not item:
            match_result = self.ai_match_item(item_name)
            if match_result.get("found"):
                item = match_result.get("item")
                
        # If we still don't have an item, return not found
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
                        item_modifiers.append(
                            {
                                "group_name": group.get("name"),
                                "min": group.get("minAllowed", 0),
                                "max": group.get("maxAllowed", 999),
                                "modifiers": group_modifiers,
                            }
                        )

        return {"found": True, "item": item, "modifiers": item_modifiers}


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
                                    "description": "The search query",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ai_match_item",
                        "description": "Match a menu item using AI when the item name might not be exact",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "item_name": {
                                    "type": "string",
                                    "description": "The name or description of the item to match",
                                }
                            },
                            "required": ["item_name"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_menu_categories",
                        "description": "Get all menu categories",
                        "parameters": {"type": "object", "properties": {}},
                    },
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
                                    "description": "The category name",
                                }
                            },
                            "required": ["category"],
                        },
                    },
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
                                    "description": "The name of the item",
                                }
                            },
                            "required": ["item_name"],
                        },
                    },
                },
            ]

            # Create the agent with appropriate tools and model
            agent = Agent(
                model="gpt-4.1-mini",
                instructions="""
                You are an assistant that helps parse customer food orders for a sushi restaurant. 
                Your job is to:
                1. Identify main menu items in customer orders
                2. Extract quantity information
                3. Properly identify and group modifiers with their parent items
                4. Verify all items exist in the actual menu
                5. Return the full order in a structured format

                IMPORTANT: Pay special attention to detecting modifiers vs. main items. For example:
                - "a build a poke bowl with sushi rice, and add spicy tofu and smashed avocado" should be
                  understood as ONE main item (poke bowl) with THREE modifiers (sushi rice, spicy tofu,
                  smashed avocado), not as four separate items.
                - Use the context and language cues to distinguish when a customer is adding modifiers
                  to a main item vs. ordering separate items
                
                When determining if something is a modifier:
                1. Look for phrases like "with", "add", "extra", "no", "without", "on the side" 
                2. Consider if the item is typically a standalone dish or a component/addition
                3. Check menu data for modifier groups and their relationships to menu items
                4. Group related items together based on natural language structure

                Only respond with items that are actually on the menu. If an item requested is not found,
                try to find the closest match or recommend alternatives. 
                
                Always return:
                - List of items, each with: name (exactly as in menu), quantity, reference_handler, and price
                - For each item, include its modifiers in the "modifier" array with their quantities and reference_handlers
                """,
                tools=tools,
            )

            # Register the tool implementations
            agent.tools.search_menu = self.menu_tool.search_menu
            agent.tools.ai_match_item = self.menu_tool.ai_match_item
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
                logger.info(
                    f"[AGENT-ORDER] Initializing order parsing agent for: '{order_text}'"
                )

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
                logger.info(
                    f"[AGENT-RESPONSE] Received response of length: {len(response)}"
                )
                logger.info(f"[AGENT-CONTENT] Response preview: {response[:200]}...")

                # Extract the structured order from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        logger.info(
                            f"[AGENT-JSON] Extracted JSON from code block, length: {len(json_str)}"
                        )
                        parsed_order = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        logger.info(
                            "[AGENT-JSON] Attempting to parse entire response as JSON"
                        )
                        parsed_order = json.loads(response)

                    # Log the parsed result
                    logger.info(
                        f"[AGENT-PARSE] Successfully parsed response as JSON with keys: {list(parsed_order.keys())}"
                    )

                    # Ensure the parsed order has the required structure
                    if "items" not in parsed_order:
                        parsed_order = {"items": []}
                        logger.warning(
                            "[AGENT-VALIDATE] Missing 'items' key in parsed order, adding empty items list"
                        )

                    # Verify all items have required fields and process their modifiers
                    for item in parsed_order["items"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning(
                                "[AGENT-VALIDATE] Item missing 'name', setting to 'Unknown Item'"
                            )
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(
                                f"[AGENT-VALIDATE] Item '{item['name']}' missing quantity, defaulting to 1"
                            )
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get(
                                    "reference_handler", ""
                                )
                                logger.info(
                                    f"[AGENT-PRICE] Found price for '{item['name']}': ${item['price']}"
                                )
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                                logger.warning(
                                    f"[AGENT-PRICE] Could not find price for '{item['name']}', using 0.0"
                                )
                        
                        # Process modifiers array, ensuring each modifier has proper fields
                        if "modifier" not in item:
                            item["modifier"] = []
                            logger.info(
                                f"[AGENT-VALIDATE] Added empty modifier list for '{item['name']}'"
                            )
                        else:
                            # Process each modifier to ensure it has required fields
                            for mod in item["modifier"]:
                                if "name" not in mod:
                                    mod["name"] = "Unknown Modifier"
                                    logger.warning(
                                        f"[AGENT-VALIDATE] Modifier for '{item['name']}' missing name"
                                    )
                                if "quantity" not in mod:
                                    mod["quantity"] = 1
                                    logger.info(
                                        f"[AGENT-VALIDATE] Modifier '{mod.get('name')}' missing quantity, defaulting to 1"
                                    )
                                
                                # Try to find modifier information in the menu
                                if "reference_handler" not in mod or "price" not in mod:
                                    # Get menu data for looking up modifier details
                                    menu_data = self.menu_tool.menu_data
                                    
                                    # Find the modifier in the menu
                                    found_modifier = None
                                    for menu_mod in menu_data.get("modifiers", []):
                                        if menu_mod.get("name", "").lower() == mod.get("name", "").lower():
                                            found_modifier = menu_mod
                                            break
                                    
                                    if found_modifier:
                                        # Set reference handler and price from menu
                                        mod["reference_handler"] = found_modifier.get("reference_handler", "")
                                        mod["price"] = found_modifier.get("price", 0.0)
                                        logger.info(
                                            f"[AGENT-VALIDATE] Found menu data for modifier '{mod.get('name')}'"
                                        )
                                    else:
                                        # Set defaults if not found
                                        if "reference_handler" not in mod:
                                            mod["reference_handler"] = ""
                                        if "price" not in mod:
                                            mod["price"] = 0.0
                                        logger.warning(
                                            f"[AGENT-VALIDATE] Could not find menu data for modifier '{mod.get('name')}'"
                                        )

                    return parsed_order

                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(
                        f"[AGENT-JSON-ERROR] Failed to parse agent response as JSON: {response}"
                    )
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
                                    "description": "The search query",
                                }
                            },
                            "required": ["query"],
                        },
                    },
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
                                    "description": "The name of the item",
                                }
                            },
                            "required": ["item_name"],
                        },
                    },
                },
            ]

            # Create the agent with appropriate tools and model
            agent = Agent(
                model="gpt-4.1-mini",
                instructions="""
                You are an assistant that helps modify existing food orders. 
                Your job is to:
                1. Understand the current order
                2. Parse the customer's modification request
                3. Identify items to add, remove, or modify (including modifiers)
                4. Return the updated order in a structured format
                
                IMPORTANT: Pay special attention to modifiers vs. main items:
                - Adding a modifier to an existing item should be represented as a modification to that item,
                  not as a new separate menu item
                - Look for phrases like "add avocado to my roll" which indicate adding a modifier to an existing item
                - Use context to determine if a mentioned item is a modifier for an existing item or a new main item
                
                Only include items that are actually on the menu. If an item requested is not found,
                try to find the closest match or recommend alternatives.
                
                Always return the full modified order with:
                - 'additions': List of items to add, including any modifiers for each item
                - 'removals': List of items to remove
                - 'modifications': List of modifications to existing items (like adding a modifier to an item)
                """,
                tools=tools,
            )

            # Register the tool implementations
            agent.tools.search_menu = self.menu_tool.search_menu
            agent.tools.get_details = self.menu_tool.get_details

            return agent

        def modify_order(
            self, current_order: Dict[str, Any], modification_text: str
        ) -> Dict[str, Any]:
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
                logger.info(
                    f"[AGENT-MODIFY] Initializing modification agent for: '{modification_text}'"
                )

                # Format the current order
                current_order_str = json.dumps(current_order, indent=2)
                logger.info(
                    f"[AGENT-CURRENT] Current order has {len(current_order.get('items', []))} items"
                )

                # Send the context and modification request
                message = thread.messages.create(
                    role="user",
                    content=f"Current order:\n{current_order_str}\n\nModification request: {modification_text}",
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
                logger.info(
                    f"[AGENT-RESPONSE] Received response of length: {len(response)}"
                )
                logger.info(f"[AGENT-CONTENT] Response preview: {response[:200]}...")

                # Extract the structured modifications from the response
                try:
                    # Try to extract JSON if wrapped in code blocks
                    if "```json" in response:
                        json_str = response.split("```json")[1].split("```")[0].strip()
                        logger.info(
                            f"[AGENT-JSON] Extracted JSON from code block, length: {len(json_str)}"
                        )
                        modifications = json.loads(json_str)
                    # Otherwise try to parse the entire response as JSON
                    else:
                        logger.info(
                            "[AGENT-JSON] Attempting to parse entire response as JSON"
                        )
                        modifications = json.loads(response)

                    # Log the parsed result
                    logger.info(
                        f"[AGENT-PARSE] Successfully parsed response as JSON with keys: {list(modifications.keys())}"
                    )

                    # Ensure the modifications have the required structure
                    if "additions" not in modifications:
                        modifications["additions"] = []
                        logger.warning(
                            "[AGENT-VALIDATE] Missing 'additions' key in modifications, adding empty list"
                        )
                    if "removals" not in modifications:
                        modifications["removals"] = []
                        logger.warning(
                            "[AGENT-VALIDATE] Missing 'removals' key in modifications, adding empty list"
                        )
                    if "modifications" not in modifications:
                        modifications["modifications"] = []
                        logger.warning(
                            "[AGENT-VALIDATE] Missing 'modifications' key in modifications, adding empty list"
                        )

                    # Verify additions have required fields
                    for item in modifications["additions"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning(
                                "[AGENT-VALIDATE] Addition missing 'name', setting to 'Unknown Item'"
                            )
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(
                                f"[AGENT-VALIDATE] Addition '{item['name']}' missing quantity, defaulting to 1"
                            )
                        if "price" not in item:
                            menu_item = find_menu_item_by_name(item["name"])
                            if menu_item:
                                item["price"] = menu_item.get("price", 0.0)
                                item["reference_handler"] = menu_item.get(
                                    "reference_handler", ""
                                )
                                logger.info(
                                    f"[AGENT-PRICE] Found price for addition '{item['name']}': ${item['price']}"
                                )
                            else:
                                item["price"] = 0.0
                                item["reference_handler"] = ""
                                logger.warning(
                                    f"[AGENT-PRICE] Could not find price for addition '{item['name']}', using 0.0"
                                )
                        if "modifier" not in item:
                            item["modifier"] = []
                            logger.info(
                                f"[AGENT-VALIDATE] Added empty modifier list for addition '{item['name']}'"
                            )

                    # Verify removals have required fields
                    for item in modifications["removals"]:
                        if "name" not in item:
                            item["name"] = "Unknown Item"
                            logger.warning(
                                "[AGENT-VALIDATE] Removal missing 'name', setting to 'Unknown Item'"
                            )
                        if "quantity" not in item:
                            item["quantity"] = 1
                            logger.warning(
                                f"[AGENT-VALIDATE] Removal '{item['name']}' missing quantity, defaulting to 1"
                            )

                    return modifications

                except json.JSONDecodeError:
                    # If JSON parsing fails, return a basic structure
                    logger.error(
                        f"[AGENT-JSON-ERROR] Failed to parse agent response as JSON: {response}"
                    )
                    return {
                        "additions": [],
                        "removals": [],
                        "error": "Failed to parse response",
                    }

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
                        {
                            "role": "system",
                            "content": """You are a restaurant order parser for a sushi restaurant. 
                            Your job is to extract menu items and their modifiers from customer orders.
                            
                            IMPORTANT: Pay special attention to detecting modifiers vs. main items. For example:
                            - "a build a poke bowl with sushi rice, and add spicy tofu and smashed avocado" should be
                              understood as ONE main item (poke bowl) with THREE modifiers (sushi rice, spicy tofu,
                              smashed avocado), not as four separate items.
                            - Use the context and language cues to distinguish when a customer is adding modifiers
                              to a main item vs. ordering separate items
                            
                            When determining if something is a modifier:
                            1. Look for phrases like "with", "add", "extra", "no", "without", "on the side" 
                            2. Consider if the item is typically a standalone dish or a component/addition
                            3. Group related items together based on natural language structure
                            """,
                        },
                        {
                            "role": "user",
                            "content": f"""Extract menu items from this order: {order_text}
                            Our menu has these categories: {', '.join(categories)}
                            
                            Respond with a JSON object containing an 'items' array, where each item has:
                            - name: The name of the main menu item
                            - quantity: The quantity ordered (default to 1 if not specified)
                            - modifier: An array of modifiers for this item, each with a name and quantity
                            
                            Example response for "I want a California Roll with extra wasabi and a spicy tuna roll":
                            {{
                              "items": [
                                {{
                                  "name": "California Roll",
                                  "quantity": 1,
                                  "modifier": [
                                    {{ "name": "Extra Wasabi", "quantity": 1 }}
                                  ]
                                }},
                                {{
                                  "name": "Spicy Tuna Roll",
                                  "quantity": 1,
                                  "modifier": []
                                }}
                              ]
                            }}
                            """,
                        },
                    ]

                    # Log the API request
                    logger.info(f"[ORDER-PARSE] Processing order text: '{order_text}'")
                    logger.info(f"[ORDER-PARSE] Using menu categories: {categories}")
                    log_openai_request("gpt-4.1-mini", messages, "parse_order")

                    try:
                        # Initial request to identify potential items
                        response = openai.chat.completions.create(
                            model="gpt-4.1-mini",
                            messages=messages,
                            response_format={"type": "json_object"},
                        )

                        # Log the response
                        log_openai_response(response, "parse_order")
                        logger.info(
                            "[ORDER-PARSE] Successfully received OpenAI response"
                        )

                        # Extract items mentioned in the order
                        initial_parse = json.loads(response.choices[0].message.content)
                        potential_items = initial_parse.get("items", [])
                        logger.info(
                            f"[ORDER-PARSE] Extracted {len(potential_items)} potential items from order"
                        )
                    except Exception as e:
                        logger.error(f"[ORDER-PARSE-ERROR] OpenAI API error: {str(e)}")
                        logger.error(
                            f"[ORDER-PARSE-TRACEBACK] {traceback.format_exc()}"
                        )
                        raise
                else:
                    # No OpenAI API - simple keyword matching
                    logger.warning(
                        "No OpenAI API key available - using simple keyword matching"
                    )
                    items = self.menu_tool.menu_data.get("items", [])
                    
                    # Simple keyword matching
                    order_lower = order_text.lower()
                    potential_items = []
                    
                    # Skip name variants - AI agent will handle matching

                    # Check direct matches with item names
                    for item in items:
                        item_name = item.get("name", "").lower()
                        if (
                            item_name
                            and item_name in order_lower
                            and item.get("name") not in potential_items
                        ):
                            potential_items.append(item.get("name"))

                # Look up each item in the menu for verification
                verified_items = []
                unverified_items = []
                logger.info(
                    f"[ORDER-VERIFY] Starting menu item verification for {len(potential_items)} potential items"
                )

                # First pass: Current verification strategy using search_menu
                for item_name in potential_items:
                    # Search menu for this item
                    logger.info(
                        f"[ORDER-VERIFY-PASS1] Verifying item: '{item_name}' using search_menu"
                    )
                    search_result = self.menu_tool.search_menu(item_name.get("name"))
                    if search_result.get("found"):
                        for menu_item in search_result.get("items", []):
                            logger.info(
                                f"[ORDER-VERIFY-PASS1-SUCCESS] Found '{item_name}' as '{menu_item.get('name')}' (${menu_item.get('price', 0.0)})"
                            )
                            verified_items.append(
                                {
                                    "name": menu_item.get("name"),
                                    "price": menu_item.get("price", 0.0),
                                    "reference_handler": menu_item.get(
                                        "reference_handler", ""
                                    ),
                                    "quantity": 1,  # Default quantity
                                    "modifier": [],  # Default empty modifiers
                                }
                            )
                    else:
                        logger.warning(
                            f"[ORDER-VERIFY-PASS1-FAIL] Could not verify '{item_name}' in first pass"
                        )
                        unverified_items.append(item_name)

                # Second pass: Direct lookup with find_menu_item_by_name for items not found in first pass
                if unverified_items:
                    still_unverified = []
                    logger.info(
                        f"[ORDER-VERIFY-PASS2] Starting second pass verification for {len(unverified_items)} items"
                    )

                    for item_name in unverified_items:
                        logger.info(
                            f"[ORDER-VERIFY-PASS2] Verifying item: '{item_name}' using direct lookup"
                        )
                        menu_item = find_menu_item_by_name(item_name.get("name"))
                        if menu_item:
                            logger.info(
                                f"[ORDER-VERIFY-PASS2-SUCCESS] Direct lookup found '{item_name}' as '{menu_item.get('name')}' (${menu_item.get('price', 0.0)})"
                            )
                            verified_items.append(
                                {
                                    "name": menu_item.get("name"),
                                    "price": menu_item.get("price", 0.0),
                                    "reference_handler": menu_item.get(
                                        "reference_handler", ""
                                    ),
                                    "quantity": 1,
                                    "modifier": [],
                                }
                            )
                        else:
                            logger.warning(
                                f"[ORDER-VERIFY-PASS2-FAIL] Could not verify '{item_name}' in second pass"
                            )
                            still_unverified.append(item_name)

                    # Third pass: Partial/fuzzy matching with menu items and variants
                    if still_unverified:
                        logger.info(
                            f"[ORDER-VERIFY-PASS3] Starting third pass verification with fuzzy matching for {len(still_unverified)} items"
                        )
                        # AI agent will handle menu item matching
                        menu_items = self.menu_tool.menu_data.get("items", [])

                        for item_name in still_unverified:
                            item_lower = item_name.get("name").lower()
                            found = False
                            
                            # Skip name variants - AI agent will handle matching for fuzzy matches


                                         system_message = """You are a fuzzy finding specialist for Red Bar Sushi.
The customer is ordering something that is not exactly word for word on.
the menu but may be similar. It is your job to figure out what the correct
item on the menu the customer is trying to order
If you are able to accurately find one then output in this format:
{
  "name": best_match.get("name"),
  "price": best_match.get("price", 0.0),
  "reference_handler": best_match.get(
    "reference_handler", ""
  ),
  "quantity": 1,
  "modifier": [],
}

if you are not then output the same with the name as NOT_FOUND""" 


                            res = client.chat.completions.create(
                                model="gpt-4.1-mini",
                                messages=[
                                    {"role": "system", "content": system_message},
                                    {"role": "user", "content": f"Here is the menu: {menu_items}"},
                                ]
                            )

                            if res.get("name") == "NOT_FOUND":
                                found = False
                            else:
                                
                                verified_items.append(res)
                                found = True
                            


                            # If still not found, try matching directly against menu items
                            if not found:
                                best_match = None
                                best_match_score = 0

                                for menu_item in menu_items:
                                    menu_item_name = menu_item.get("name", "").lower()
                                    # Check partial containment in either direction
                                    if menu_item_name and (
                                        item_lower in menu_item_name
                                        or menu_item_name in item_lower
                                    ):
                                        # Calculate a simple match score (longer matches are better)
                                        match_length = min(
                                            len(item_lower), len(menu_item_name)
                                        )
                                        if match_length > best_match_score:
                                            best_match = menu_item
                                            best_match_score = match_length

                                if best_match:
                                    logger.info(
                                        f"[ORDER-VERIFY-PASS3-SUCCESS] Direct fuzzy match found '{item_name}' as '{best_match.get('name')}' (${best_match.get('price', 0.0)})"
                                    )
                                    verified_items.append(
                                        {
                                            "name": best_match.get("name"),
                                            "price": best_match.get("price", 0.0),
                                            "reference_handler": best_match.get(
                                                "reference_handler", ""
                                            ),
                                            "quantity": 1,
                                            "modifier": [],
                                        }
                                    )
                                    found = True

                            if not found:
                                logger.error(
                                    f"[ORDER-VERIFY-FAIL] Failed to verify item '{item_name}' after all verification passes"
                                )

                # Log summary of verification process
                verification_rate = (
                    len(verified_items) / len(potential_items) if potential_items else 0
                )
                logger.info(
                    f"[ORDER-VERIFY-SUMMARY] Verification complete: {len(verified_items)}/{len(potential_items)} items verified ({verification_rate:.0%})"
                )
                for item in verified_items:
                    logger.info(
                        f"[ORDER-ITEM-VERIFIED] {item.get('name')} (${item.get('price'):.2f})"
                    )

                # Final structured order
                return {
                    "items": verified_items,
                    "intent": "order_food" if verified_items else "other",
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

        def modify_order(
            self, current_order: Dict[str, Any], modification_text: str
        ) -> Dict[str, Any]:
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
                    current_items = "\n".join(
                        [
                            f"- {item.get('quantity', 1)}x {item.get('name')}"
                            for item in current_order.get("items", [])
                        ]
                    )

                    # Prepare messages for the API call
                    messages = [
                        {
                            "role": "system",
                            "content": """You are a sushi restaurant order modifier. Process order changes and return JSON.
                            
                            IMPORTANT: Pay special attention to modifiers vs. main items:
                            - Adding a modifier to an existing item should be represented as a modification to that item,
                              not as a new separate menu item
                            - Look for phrases like "add avocado to my roll" which indicate adding a modifier to an existing item
                            - Use context to determine if a mentioned item is a modifier for an existing item or a new main item
                            """,
                        },
                        {
                            "role": "user",
                            "content": f"""Current order:
{current_items}

Modification request: {modification_text}

Return JSON with:
- 'additions': List of new items to add, each with name, quantity, and modifier array
- 'removals': List of items to remove, each with name and quantity
- 'modifications': List of modifications to existing items (like adding a modifier to an item), 
  each with item_name, and a modifier array
""",
                        },
                    ]

                    # Log the request
                    logger.info(
                        f"[MODIFY-ORDER] Processing modification: '{modification_text}'"
                    )
                    logger.info(
                        f"[MODIFY-ORDER] Current order has {len(current_order.get('items', []))} items"
                    )
                    log_openai_request("gpt-4.1-mini", messages, "modify_order")

                    try:
                        # Request to identify modifications
                        response = openai.chat.completions.create(
                            model="gpt-4.1-mini",
                            messages=messages,
                            response_format={"type": "json_object"},
                        )

                        # Log the response
                        log_openai_response(response, "modify_order")
                        logger.info(
                            "[MODIFY-ORDER] Successfully received OpenAI response"
                        )

                        # Parse the response
                        modifications = json.loads(response.choices[0].message.content)
                        logger.info(
                            f"[MODIFY-ORDER] Parsed modifications: additions={len(modifications.get('additions', []))}, removals={len(modifications.get('removals', []))}"
                        )
                    except Exception as e:
                        logger.error(f"[MODIFY-ORDER-ERROR] OpenAI API error: {str(e)}")
                        logger.error(
                            f"[MODIFY-ORDER-TRACEBACK] {traceback.format_exc()}"
                        )
                        raise
                else:
                    # No OpenAI API - very simple keyword matching
                    logger.warning(
                        "No OpenAI API key available - using simple keyword matching for modifications"
                    )
                    modifications = {"additions": [], "removals": []}

                    # Extract possible add/remove keywords
                    mod_lower = modification_text.lower()
                    self.menu_tool.menu_data.get("items", [])
                    # Skip name variants - AI agent will handle matching

                    # Very simple add/remove detection
                    is_addition = any(
                        w in mod_lower for w in ["add", "want", "more", "with"]
                    )
                    is_removal = any(
                        w in mod_lower
                        for w in ["remove", "no", "without", "don't want", "cancel"]
                    )

                    # Check current order items for potential removals
                    if is_removal:
                        for item in current_order.get("items", []):
                            item_name = item.get("name", "").lower()
                            if item_name and item_name in mod_lower:
                                modifications["removals"].append(
                                    {"name": item.get("name"), "quantity": 1}
                                )

                    # Skip name variants for additions - AI agent will handle matching
                    # Check all menu items for potential additions using direct matching only
                    # This is a simple fallback - the proper AI agent will do better matching

                # Ensure required structure
                if "additions" not in modifications:
                    modifications["additions"] = []
                if "removals" not in modifications:
                    modifications["removals"] = []
                if "modifications" not in modifications:
                    modifications["modifications"] = []

                # Verify and enhance additions (only if OpenAI API available)
                for item in modifications.get("additions", []):
                    if "name" in item:
                        menu_item = find_menu_item_by_name(item["name"])
                        if menu_item:
                            item["price"] = menu_item.get("price", 0.0)
                            item["reference_handler"] = menu_item.get(
                                "reference_handler", ""
                            )
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
    
    Detects three main intents:
    - order_food: Customer wants to place an order
    - ask_menu: Customer is asking about menu items
    - other: Other types of queries
    
    Args:
        input_text: The user's input text

    Returns:
        dict: The analysis results with consistent structure across all intents
    """
    # First, determine if this is a menu question using OpenAI if available
    intent = "other"
    menu_items = []
    
    try:
        if OPENAI_API_KEY:
            # Prepare messages for intent classification
            messages = [
                {
                    "role": "system",
                    "content": "You are a restaurant AI assistant that classifies customer queries. Determine if the customer is placing an order or asking about the menu."
                },
                {
                    "role": "user",
                    "content": f"Classify this customer query: '{input_text}'\nRespond with JSON containing 'intent' which must be one of: 'order_food', 'ask_menu', or 'other'."
                }
            ]
            
            # Log the API request
            log_openai_request("gpt-4.1-mini", messages, "intent_classification")
            
            try:
                # Make the classification request
                response = openai.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                
                # Log the API response
                log_openai_response(response, "intent_classification")
                
                # Extract the intent
                classification = json.loads(response.choices[0].message.content)
                intent = classification.get("intent", "other")
                logger.info(f"[INTENT-CLASSIFICATION] Classified intent as: '{intent}'")
                
            except Exception as e:
                logger.error(f"[INTENT-ERROR] OpenAI API error: {str(e)}")
                logger.error(f"[INTENT-TRACEBACK] {traceback.format_exc()}")
                # Fall back to order parsing
        
        # If intent is still "other" or "order_food", try parsing as an order
        if intent in ["other", "order_food"]:
            # Create an order parsing agent
            agent = OrderParsingAgent()
            
            # Parse the input
            logger.info(f"[ANALYZE-INPUT] Analyzing user input: '{input_text}'")
            parsed_order = agent.parse_order(input_text)
            logger.info(f"[PARSED-ORDER]: {parsed_order}")
            
            # If we found menu items, this is likely an order
            if parsed_order.get("items"):
                menu_items = parsed_order.get("items", [])
                intent = "order_food"
                logger.info(f"[ANALYZE-RESULT] Found {len(menu_items)} items, intent: 'order_food'")
    
    except Exception as e:
        logger.error(f"[ANALYZE-ERROR] Error in analyze_user_input: {str(e)}")
        logger.error(f"[ANALYZE-TRACEBACK] {traceback.format_exc()}")
    
    # Return a consistent structure for all intents
    result = {
        "intent": intent,
        "menu_items": menu_items
    }
    
    # Add any intent-specific data
    if intent == "ask_menu":
        # Extract the menu query for ask_menu intent
        menu_tool = SushiMenuTool()
        query = input_text.strip()
        search_result = menu_tool.search_menu(query)
        result["menu_query"] = query
        result["search_results"] = search_result
    
    logger.info(f"[ANALYZE-FINAL] Final intent: '{intent}' with {len(menu_items)} menu items")
    return result


def get_order_modifications(
    user_input: str, current_order_items: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
    logger.info(
        f"[ORDER-MODIFICATIONS] Processing modification request: '{user_input}'"
    )
    modifications = agent.modify_order(current_order, user_input)

    logger.info(
        f"[ORDER-MODIFICATIONS] Found modifications: additions={len(modifications.get('additions', []))}, removals={len(modifications.get('removals', []))}, modifications={len(modifications.get('modifications', []))}"
    )
    return modifications
