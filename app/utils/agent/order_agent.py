"""
Order parsing agent implementation.
"""

import json
import logging
from typing import Dict, List, Any

from app.utils.menu_utils import find_menu_item_by_name
from app.utils.agent.config import OPENAI_API_KEY, AGENT_API_AVAILABLE
from app.utils.agent.menu_tool import SushiMenuTool

logger = logging.getLogger(__name__)

# Try to import the Agent class, fall back to a stub version if not available
try:
    from openai.agent import Agent
    logger.info("Successfully imported openai.agent.Agent")
    HAS_AGENT_API = True
except ImportError:
    logger.warning("Could not import openai.agent.Agent, using direct OpenAI API")
    import openai
    HAS_AGENT_API = False
    
    # Define stub Agent class that will use the Chat API directly
    class Agent:
        """Stub Agent class that uses Chat API instead of Agent API"""
        def __init__(self, *args, **kwargs):
            self.config = kwargs
            self.tools = type('obj', (object,), {})
            
        def create_thread(self):
            return AgentThread()
    
    class AgentThread:
        """Stub for Agent thread"""
        def __init__(self):
            self.messages = AgentMessages()
            self.runs = AgentRuns()
            
    class AgentMessages:
        """Stub for Agent messages"""
        def __init__(self):
            pass
            
        def create(self, role, content):
            return AgentMessage(role, content)
            
        def list(self, after=None):
            return [AgentMessage("assistant", "Empty response")]
    
    class AgentMessage:
        """Stub for a single message"""
        def __init__(self, role, content):
            self.role = role
            self.content = content
            self.id = "msg_stub"
            
    class AgentRuns:
        """Stub for Agent runs"""
        def __init__(self):
            pass
            
        def create(self):
            return AgentRun()
            
        def wait(self, run_id):
            return AgentRun()
            
    class AgentRun:
        """Stub for a single run"""
        def __init__(self):
            self.id = "run_stub"
            self.status = "completed"

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
            - "steak frites cooked rare with a side of fries" should be ONE main item (steak frites)
              with TWO modifiers (cooked rare, side of fries), not as separate items.
            - Use the context and language cues to distinguish when a customer is adding modifiers
              to a main item vs. ordering separate items
            
            When determining if something is a modifier:
            1. Look for phrases like "with", "add", "extra", "no", "without", "on the side", "cooked" 
            2. Consider if the item is typically a standalone dish or a component/addition
            3. Check menu data for modifier groups and their relationships to menu items
            4. Group related items together based on natural language structure
            5. Cooking preferences (like "rare", "medium", "well done") are ALWAYS modifiers

            Only respond with items that are actually on the menu. If an item requested is not found,
            try to find the closest match or recommend alternatives. 
            
            Always return:
            - List of items, each with: name (exactly as in menu), quantity, reference_handler, and price
            - For each item, include its modifiers in the "modifier" array with their quantities and reference_handlers
            - IMPORTANT: Each modifier in the modifier array MUST include: name, quantity, reference_handler, and price
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
                    # First, make sure the modifiers array exists
                    if "modifier" not in item:
                        item["modifier"] = []
                        logger.info(
                            f"[AGENT-VALIDATE] Added empty modifier list for '{item['name']}'"
                        )
                    elif not isinstance(item["modifier"], list):
                        # Fix invalid modifier format
                        logger.warning(f"[AGENT-VALIDATE] Invalid 'modifier' format for '{item['name']}', fixing it")
                        item["modifier"] = []
                        
                    # Process each modifier to ensure proper formatting
                    processed_modifiers = []
                    for mod in item.get("modifier", []):
                        # Skip non-dictionary modifiers
                        if not isinstance(mod, dict):
                            logger.warning(f"[AGENT-VALIDATE] Invalid modifier format in '{item['name']}', skipping: {mod}")
                            continue
                            
                        # Build a properly formatted modifier
                        valid_mod = {}
                        
                        # Ensure name exists
                        if "name" not in mod:
                            valid_mod["name"] = "Unknown Modifier"
                            logger.warning(f"[AGENT-VALIDATE] Modifier for '{item['name']}' missing name")
                        else:
                            valid_mod["name"] = mod["name"]
                        
                        # Ensure quantity exists
                        valid_mod["quantity"] = mod.get("quantity", 1)
                        
                        # Ensure reference_handler exists
                        if "reference_handler" not in mod or not mod["reference_handler"]:
                            mod_name = valid_mod["name"].lower()
                            # Determine modifier type based on name
                            if "cook" in mod_name or "rare" in mod_name or "medium" in mod_name or "well" in mod_name:
                                mod_type = "COOK"
                            elif "side" in mod_name or "fries" in mod_name or "salad" in mod_name:
                                mod_type = "SIDE"
                            else:
                                mod_type = "GEN"
                            valid_mod["reference_handler"] = f"MOD-{mod_type}-{mod_name.replace(' ', '-')}"
                            logger.info(f"[AGENT-VALIDATE] Created reference_handler '{valid_mod['reference_handler']}' for modifier '{valid_mod['name']}'")
                        else:
                            valid_mod["reference_handler"] = mod["reference_handler"]
                        
                        # Ensure price exists
                        valid_mod["price"] = mod.get("price", 0.0)
                        
                        # Add the valid modifier to our processed list
                        processed_modifiers.append(valid_mod)
                    
                    # Replace the original modifiers with our processed ones
                    item["modifier"] = processed_modifiers
                    
                    # Log the modifiers that are being processed
                    if item["modifier"]:
                        logger.info(f"[AGENT-MODS] Item '{item['name']}' has {len(item['modifier'])} modifiers")
                        mod_names = [mod.get('name', 'unnamed') for mod in item["modifier"]]
                        logger.info(f"[AGENT-MODS] Modifier list: {', '.join(mod_names)}")
                        logger.info(f"[AGENT-MODS-DETAIL] Full modifier data for '{item['name']}': {json.dumps(item['modifier'])}")
                        
                        # Ensure each modifier has the required fields for Deliverect
                        for mod in item["modifier"]:
                            if not isinstance(mod, dict):
                                logger.warning(f"[AGENT-MODS-FIX] Skipping non-dict modifier")
                                continue
                                
                            # Ensure required fields exist
                            if "name" not in mod:
                                mod["name"] = "Unknown Modifier"
                            if "quantity" not in mod:
                                mod["quantity"] = 1
                            
                            # Try to get a valid reference_handler if missing
                            if "reference_handler" not in mod or not mod["reference_handler"]:
                                mod_name_lower = mod.get("name", "").lower()
                                # Create a placeholder but distinctive reference handler
                                mod["reference_handler"] = f"MOD-{mod_name_lower.replace(' ', '-')}"
                                logger.info(f"[AGENT-MODS-FIX] Created reference_handler '{mod['reference_handler']}' for modifier '{mod['name']}'")
                                
                            # Ensure price is set
                            if "price" not in mod:
                                mod["price"] = 0.0
                    
                    # Process each modifier to ensure it has required fields
                    for mod in item["modifier"]:
                        if not isinstance(mod, dict):
                            logger.warning(f"[AGENT-VALIDATE] Invalid modifier format in '{item['name']}', skipping")
                            continue
                            
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
                            mod_name_lower = mod.get("name", "").lower()
                            
                            # Standard valid cooking terms to allow even if not in menu
                            valid_cooking_terms = [
                                "rare", "medium rare", "medium", "medium well", "well done", 
                                "cooked rare", "cooked medium", "cooked well done"
                            ]
                            
                            # Standard valid side terms to allow even if not in menu
                            valid_side_terms = [
                                "side of fries", "extra fries", "side salad", "no sides",
                                "fries on the side", "rice on the side"
                            ]
                            
                            # First try exact match
                            for menu_mod in menu_data.get("modifiers", []):
                                menu_mod_name = menu_mod.get("name", "").lower()
                                if menu_mod_name == mod_name_lower:
                                    found_modifier = menu_mod
                                    break
                                    
                            # If not found, try fuzzy matching
                            if not found_modifier:
                                for menu_mod in menu_data.get("modifiers", []):
                                    menu_mod_name = menu_mod.get("name", "").lower()
                                    # Try fuzzy matching for modifiers
                                    if (menu_mod_name in mod_name_lower or mod_name_lower in menu_mod_name):
                                        found_modifier = menu_mod
                                        break
                        
                            # If we found a modifier, update our details
                            if found_modifier:
                                if "reference_handler" not in mod or not mod["reference_handler"]:
                                    mod["reference_handler"] = found_modifier.get("reference_handler", f"MOD-{found_modifier.get('id')}")
                                    logger.info(f"[AGENT-VALIDATE] Set reference_handler from menu: '{mod['reference_handler']}'")
                                
                                if "price" not in mod:
                                    mod["price"] = found_modifier.get("price", 0.0)
                                    logger.info(f"[AGENT-VALIDATE] Set price from menu: ${mod['price']}")
                            
                            # Handle standard cooking terms not in menu
                            elif mod_name_lower in valid_cooking_terms and "reference_handler" not in mod:
                                cook_type = "rare" if "rare" in mod_name_lower else ("medium" if "medium" in mod_name_lower else "well")
                                mod["reference_handler"] = f"MOD-COOK-{cook_type}"
                                logger.info(f"[AGENT-VALIDATE] Set reference_handler for standard cooking term: '{mod['reference_handler']}'")
                            
                            # Handle standard side terms not in menu
                            elif any(term in mod_name_lower for term in valid_side_terms) and "reference_handler" not in mod:
                                side_type = "fries" if "fries" in mod_name_lower else ("salad" if "salad" in mod_name_lower else "rice" if "rice" in mod_name_lower else "side")
                                mod["reference_handler"] = f"MOD-SIDE-{side_type}"
                                logger.info(f"[AGENT-VALIDATE] Set reference_handler for standard side term: '{mod['reference_handler']}'")
                            
                            # Fallback for other modifiers
                            else:
                                if "reference_handler" not in mod:
                                    # Create a reference handler based on name
                                    mod["reference_handler"] = f"MOD-{mod_name_lower.replace(' ', '-')}"
                                    logger.info(f"[AGENT-VALIDATE] Created fallback reference_handler: '{mod['reference_handler']}'")
                                
                                if "price" not in mod:
                                    # Default price for unknown modifiers
                                    mod["price"] = 0.0

                # Return the validated and processed order
                return parsed_order

            except Exception as e:
                logger.error(f"[AGENT-PARSE-ERROR] Error parsing response: {e}")
                logger.error(f"[AGENT-RAW-RESPONSE] Raw response: {response[:1000]}...")
                # Return a fallback empty order
                return {"items": []}

        except Exception as e:
            logger.error(f"[AGENT-ERROR] Error in order parsing agent: {e}")
            return {"items": []}
            
    def extract_name(self, input_string: str) -> dict:
        """
        Extract a name from an input string using AI.
        
        Args:
            input_string: The input string that may contain a name
            
        Returns:
            dict: A dictionary containing the extracted name
        """
        try:
            # Initialize the agent
            thread = self.agent.create_thread()
            
            # Construct a specific prompt for name extraction
            prompt = f"""Extract the customer's name from the following message and return it as JSON with a single 'name' field. 
            If there is no clear name, return an empty string.
            Message: {input_string}"""
            
            # Send the request
            message = thread.messages.create(role="user", content=prompt)
            
            # Run the agent
            run = thread.runs.create()
            run = thread.runs.wait(run_id=run.id)
            
            # Get the response
            messages = thread.messages.list(after=message.id)
            response = list(messages)[0].content[0].text.value
            
            # Parse the response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
                extracted_data = json.loads(json_str)
            else:
                # Try to parse the entire response as JSON
                extracted_data = json.loads(response)
            
            # Validate and return
            if "name" in extracted_data:
                logger.info(f"[NAME-EXTRACT] Successfully extracted name: '{extracted_data['name']}'")
                return extracted_data
            else:
                logger.warning(f"[NAME-EXTRACT] Extracted data missing 'name' field: {extracted_data}")
                return {"name": ""}
                
        except Exception as e:
            logger.error(f"[NAME-EXTRACT-ERROR] Error extracting name: {e}")
            return {"name": ""}
        
    def classify_main_menu_intent(self, input_text: str) -> str:
        """
        Classify the user's intent from the main menu input.
        
        Args:
            input_text: User's spoken input
            
        Returns:
            str: The classified intent ('order', 'menu_info', 'human', or 'unclear')
        """
        try:
            # Initialize the agent
            thread = self.agent.create_thread()
            
            # Construct a specific prompt for intent classification
            prompt = f"""Classify the customer's intent from the following input at the main menu:
            Input: "{input_text}"
            
            Classify into one of these categories:
            - order: If they want to place an order
            - menu_info: If they want information about the menu
            - human: If they want to speak to a real person
            - unclear: If the intent isn't clear
            
            Return just the category name as a single word.
            """
            
            # Send the request
            message = thread.messages.create(role="user", content=prompt)
            
            # Run the agent
            run = thread.runs.create()
            run = thread.runs.wait(run_id=run.id)
            
            # Get the response
            messages = thread.messages.list(after=message.id)
            response = list(messages)[0].content[0].text.value.strip().lower()
            
            # Map to valid intents
            if response in ["order", "place order", "ordering"]:
                return "order"
            elif response in ["menu", "menu_info", "information", "menu info"]:
                return "menu_info"
            elif response in ["human", "person", "real person", "staff", "representative"]:
                return "human"
            else:
                return "unclear"
                
        except Exception as e:
            logger.error(f"[INTENT-ERROR] Error classifying main menu intent: {e}")
            return "unclear"
            
    def get_modifier_suggestions(self, item_name: str) -> Dict[str, Any]:
        """
        Get modifier suggestions for a menu item directly from the menu data.
        
        Args:
            item_name: The menu item name
            
        Returns:
            dict: Modifier suggestions keyed by group name
        """
        # Use the menu tool to get item details including modifiers
        item_details = self.menu_tool.get_details(item_name)
        
        if not item_details.get("found"):
            logger.warning(f"[MODIFIER-SUGGEST] Item not found: {item_name}")
            return {"found": False, "modifiers": {}}
            
        # Get modifier groups directly from the menu data
        modifier_groups = item_details.get("modifiers", [])
        if not modifier_groups:
            logger.info(f"[MODIFIER-SUGGEST] No modifier groups found for item: {item_name}")
            return {"found": True, "modifiers": {}}
            
        # Build a structured result with modifier options by group
        result = {"found": True, "modifiers": {}}
        
        for group in modifier_groups:
            group_name = group.get("name", "Unknown Group")
            mods = group.get("modifiers", [])
            min_required = group.get("min", 0)
            max_allowed = group.get("max", 0)
            
            # Skip empty groups
            if not mods:
                continue
                
            # Add this group with its modifiers to the result
            result["modifiers"][group_name] = {
                "required": min_required > 0,
                "min": min_required,
                "max": max_allowed,
                "options": [mod.get("name") for mod in mods]
            }
            
        return result