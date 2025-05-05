"""
Fulfillment Agent for RedBarSushiAI.
This module provides the fulfillment agent that handles order submission and status tracking.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
import uuid
from datetime import datetime, timedelta
from app.agents.base import tool, Tool

from app.agents.base import BaseAgent
from app.utils.conversation_store_sdk import agents_conversation_store
from app.utils.agents_sdk import guardrail
from app.utils.deliverect import send_order_to_deliverect, get_order_status

logger = logging.getLogger(__name__)

class FulfillmentAgent(BaseAgent):
    """
    Fulfillment Agent that handles order submission and tracking.
    Finalizes orders, submits them to Deliverect, and manages SMS updates.
    """
    
    def __init__(
        self,
        name: str = "Fulfillment Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Fulfillment Agent."""
        
        instructions = """
        You are a fulfillment specialist for Red Bar Sushi restaurant.
        Your primary responsibilities are:
        
        1. Finalize customer orders by confirming delivery details or pickup time
        2. Format orders for submission to our Deliverect system
        3. Submit orders and handle the submission response
        4. Track order status and provide updates to customers
        5. Schedule SMS notifications for important status changes
        
        COMMUNICATION STYLE:
        - Be professional but friendly
        - Confirm all important details before submitting orders
        - Provide clear information about timing and next steps
        - Be direct when there are issues that need resolution
        
        IMPORTANT RULES:
        - Always confirm the order total before submission
        - Validate customer contact information
        - Use the exact PLU codes from the cart
        - Format the order payload according to Deliverect requirements
        - Submit the order only after full confirmation
        - Schedule appropriate SMS notifications for status updates
        
        ORDER SUBMISSION PROCESS:
        1. Review and confirm the cart with the customer
        2. Gather delivery details or confirm pickup time
        3. Prepare the order payload with all required fields
        4. Submit the order to Deliverect
        5. Schedule status tracking and notifications
        6. Provide order confirmation details to the customer
        
        You will receive finalized carts and customer details and should handle
        the entire submission process while providing clear feedback on status.
        """
        
        # Define the tools this agent can use
        tools = [
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
            },
            {
                "type": "function",
                "function": {
                    "name": "place_order",
                    "description": "Submit an order to Deliverect",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_type": {
                                "type": "integer",
                                "description": "The type of order: 1=pickup, 2=delivery, 3=eat-in",
                                "enum": [1, 2, 3]
                            },
                            "customer_details": {
                                "type": "object",
                                "description": "Customer information",
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
                                        "description": "Customer's email (optional)"
                                    }
                                },
                                "required": ["name", "phone"]
                            },
                            "delivery_details": {
                                "type": "object",
                                "description": "Delivery information (required for delivery orders)",
                                "properties": {
                                    "address": {
                                        "type": "string",
                                        "description": "Delivery address"
                                    },
                                    "city": {
                                        "type": "string",
                                        "description": "City"
                                    },
                                    "zip": {
                                        "type": "string",
                                        "description": "ZIP/Postal code"
                                    },
                                    "instructions": {
                                        "type": "string",
                                        "description": "Delivery instructions (optional)"
                                    }
                                },
                                "required": ["address", "city", "zip"]
                            },
                            "pickup_time": {
                                "type": "string",
                                "description": "ISO 8601 pickup time (for pickup orders)"
                            },
                            "delivery_time": {
                                "type": "string",
                                "description": "ISO 8601 delivery time (for delivery orders)"
                            },
                            "order_notes": {
                                "type": "string",
                                "description": "General notes for the order"
                            }
                        },
                        "required": ["order_type", "customer_details"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_order_status",
                    "description": "Check the status of a previously placed order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The ID of the order to check"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "send_status_sms",
                    "description": "Send an SMS update to the customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The ID of the order"
                            },
                            "phone": {
                                "type": "string",
                                "description": "Customer's phone number"
                            },
                            "message": {
                                "type": "string",
                                "description": "The message to send"
                            }
                        },
                        "required": ["order_id", "phone", "message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_estimated_times",
                    "description": "Get estimated preparation and delivery times",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_type": {
                                "type": "integer",
                                "description": "The type of order: 1=pickup, 2=delivery, 3=eat-in",
                                "enum": [1, 2, 3]
                            }
                        },
                        "required": ["order_type"]
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Fulfillment agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
    
    @tool
    def get_current_cart(self) -> Dict[str, Any]:
        """
        Get the current state of the customer's cart.
        
        Returns:
            The current cart
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session",
                "total_price": 0,
                "items": []
            }
        
        # Get the current cart
        current_cart = agents_conversation_store.get_cart(call_sid)
        
        # Calculate a formatted total price string
        total_price_cents = current_cart.get("total_price", 0)
        total_price_str = f"${total_price_cents/100:.2f}" if isinstance(total_price_cents, (int, float)) else "$0.00"
        
        # Format item details for better readability
        formatted_items = []
        for i, item in enumerate(current_cart.get("items", [])):
            price_cents = item.get("price", 0)
            price_str = f"${price_cents/100:.2f}" if isinstance(price_cents, (int, float)) else "$0.00"
            
            formatted_modifiers = []
            for modifier in item.get("modifiers", []):
                mod_price = modifier.get("price_change", 0)
                mod_price_str = f"${mod_price/100:.2f}" if mod_price else ""
                
                formatted_modifiers.append({
                    "name": modifier.get("name", ""),
                    "quantity": modifier.get("quantity", 1),
                    "price": mod_price_str
                })
            
            formatted_items.append({
                "index": i,
                "name": item.get("name", ""),
                "quantity": item.get("quantity", 1),
                "price": price_str,
                "plu": item.get("plu", ""),
                "modifiers": formatted_modifiers,
                "special_instructions": item.get("special_instructions")
            })
        
        # Return the formatted cart
        return {
            "success": True,
            "item_count": len(current_cart.get("items", [])),
            "total_price": current_cart.get("total_price", 0),
            "formatted_total": total_price_str,
            "items": formatted_items
        }
    
    @tool
    @guardrail(
        on="tool_response",
        check=lambda result, **_: result.get("success", False),
        on_fail="retry",
        max_retries=2,
        message="Order submission failed"
    )
    def place_order(
        self, 
        order_type: int, 
        customer_details: Dict[str, str],
        delivery_details: Optional[Dict[str, str]] = None,
        pickup_time: Optional[str] = None,
        delivery_time: Optional[str] = None,
        order_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit an order to Deliverect.
        
        Args:
            order_type: The type of order (1=pickup, 2=delivery, 3=eat-in)
            customer_details: Customer information (name, phone, email)
            delivery_details: Delivery information (required for delivery orders)
            pickup_time: ISO 8601 pickup time (for pickup orders)
            delivery_time: ISO 8601 delivery time (for delivery orders)
            order_notes: General notes for the order
            
        Returns:
            Order submission result
        """
        # Get the current call SID from context
        call_sid = self._get_current_call_sid()
        if not call_sid:
            logger.error("No call SID found in context")
            return {
                "success": False,
                "message": "Could not identify the current session"
            }
        
        logger.info(f"Placing order for call {call_sid}")
        
        # Get the current cart
        cart = agents_conversation_store.get_cart(call_sid)
        items = cart.get("items", [])
        
        # Validate there are items in the cart
        if not items:
            logger.error("Attempted to place order with empty cart")
            return {
                "success": False,
                "message": "The cart is empty"
            }
        
        # Validate the order type
        if order_type not in [1, 2, 3]:
            logger.error(f"Invalid order type: {order_type}")
            return {
                "success": False,
                "message": f"Invalid order type: {order_type}"
            }
        
        # Validate delivery details for delivery orders
        if order_type == 2 and not delivery_details:
            logger.error("Missing delivery details for delivery order")
            return {
                "success": False,
                "message": "Delivery details are required for delivery orders"
            }
        
        # Generate a unique channel order ID
        channel_order_id = f"RBS-{int(time.time())}-{str(uuid.uuid4())[:5]}"
        
        # Prepare the order payload
        payload = {
            "channelOrderId": channel_order_id,
            "channelOrderDisplayId": channel_order_id[:12],
            "orderType": order_type,
            "customer": {
                "name": customer_details.get("name", ""),
                "phoneNumber": customer_details.get("phone", "")
            },
            "orderIsAlreadyPaid": False,
            "payment": {
                "amount": cart.get("total_price", 0),
                "type": 1  # 1 = cash
            },
            "items": []
        }
        
        # Add email if provided
        if customer_details.get("email"):
            payload["customer"]["email"] = customer_details["email"]
        
        # Add delivery details if applicable
        if order_type == 2 and delivery_details:
            payload["deliveryAddress"] = {
                "street": delivery_details.get("address", ""),
                "city": delivery_details.get("city", ""),
                "postalCode": delivery_details.get("zip", "")
            }
        
        # Add pickup/delivery time if applicable
        if order_type == 1 and pickup_time:
            payload["pickupTime"] = pickup_time
        elif order_type == 2 and delivery_time:
            payload["deliveryTime"] = delivery_time
        
        # Add order notes if provided
        if order_notes:
            payload["note"] = order_notes
        
        # Format the items for the payload
        for item in items:
            item_payload = {
                "plu": item.get("plu", ""),
                "name": item.get("name", ""),
                "price": item.get("price", 0),
                "quantity": item.get("quantity", 1),
                "subItems": []
            }
            
            # Add special instructions as a note if present
            if item.get("special_instructions"):
                item_payload["note"] = item.get("special_instructions")
            
            # Add modifiers
            for modifier in item.get("modifiers", []):
                modifier_payload = {
                    "plu": modifier.get("plu", ""),
                    "name": modifier.get("name", ""),
                    "price": modifier.get("price_change", 0),
                    "quantity": modifier.get("quantity", 1)
                }
                
                item_payload["subItems"].append(modifier_payload)
            
            payload["items"].append(item_payload)
        
        # Submit the order to Deliverect
        try:
            # In a production environment, this would call Deliverect's API
            # For now, simulate a successful response
            # result = send_order_to_deliverect(payload)
            
            # Simulated successful response
            result = {
                "success": True,
                "order_id": channel_order_id,
                "status": 10,  # Initial status (received)
                "message": "Order received"
            }
            
            # Schedule a status update SMS
            try:
                # For now, just log the SMS - in production, queue a Celery task
                msg = f"Thank you for your order at Red Bar Sushi! Your order #{channel_order_id[:8]} "
                msg += f"has been received and will be ready in about 20-30 minutes. "
                msg += f"Total: {cart.get('formatted_total', '$0.00')}"
                
                logger.info(f"SMS to {customer_details.get('phone')}: {msg}")
                
                # In production, this would call:
                # from tasks import send_confirmation_sms_task
                # send_confirmation_sms_task.delay(channel_order_id, customer_details["phone"], msg)
            except Exception as sms_error:
                logger.error(f"Error scheduling SMS: {str(sms_error)}")
            
            # Return success
            return {
                "success": True,
                "order_id": channel_order_id,
                "status": "received",
                "status_code": 10,
                "message": "Your order has been received and will be ready in about 20-30 minutes.",
                "estimated_time": self._get_estimated_time(order_type)
            }
            
        except Exception as e:
            logger.error(f"Error submitting order: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to submit order: {str(e)}"
            }
    
    @tool
    def check_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Check the status of a previously placed order.
        
        Args:
            order_id: The ID of the order to check
            
        Returns:
            The current order status
        """
        try:
            # In a production environment, this would call Deliverect's API
            # For now, simulate a status response
            # status = get_order_status(order_id)
            
            # Simulated status response
            status = {
                "status": 20,  # Accepted by restaurant
                "status_text": "Accepted",
                "timestamp": datetime.now().isoformat()
            }
            
            # Map status code to readable status
            status_map = {
                10: "Received",
                20: "Accepted",
                30: "In Preparation",
                40: "Prepared",
                70: "Ready for Pickup",
                80: "Delivered/Completed",
                90: "Rejected",
                100: "Cancellation Request",
                110: "Canceled"
            }
            
            status_text = status_map.get(status["status"], "Unknown")
            
            return {
                "success": True,
                "order_id": order_id,
                "status": status_text,
                "status_code": status["status"],
                "timestamp": status["timestamp"]
            }
            
        except Exception as e:
            logger.error(f"Error checking order status: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to check order status: {str(e)}"
            }
    
    @tool
    def send_status_sms(self, order_id: str, phone: str, message: str) -> Dict[str, Any]:
        """
        Send an SMS update to the customer.
        
        Args:
            order_id: The ID of the order
            phone: Customer's phone number
            message: The message to send
            
        Returns:
            SMS send result
        """
        try:
            # In a production environment, this would call Twilio's API via Celery
            # For now, just log the message
            logger.info(f"SMS to {phone} for order {order_id}: {message}")
            
            # In production, this would call:
            # from tasks import send_status_update_task
            # send_status_update_task.delay(order_id, phone, message)
            
            return {
                "success": True,
                "order_id": order_id,
                "phone": phone,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to send SMS: {str(e)}"
            }
    
    @tool
    def get_estimated_times(self, order_type: int) -> Dict[str, Any]:
        """
        Get estimated preparation and delivery times.
        
        Args:
            order_type: The type of order
            
        Returns:
            Estimated times
        """
        # Get the current time
        now = datetime.now()
        
        # Calculate estimated prep time (20-30 minutes)
        prep_time = now + timedelta(minutes=25)
        
        # Calculate estimated delivery time if applicable (45-60 minutes)
        delivery_time = now + timedelta(minutes=55) if order_type == 2 else None
        
        return {
            "success": True,
            "preparation_time": prep_time.isoformat(),
            "formatted_prep_time": prep_time.strftime("%I:%M %p"),
            "delivery_time": delivery_time.isoformat() if delivery_time else None,
            "formatted_delivery_time": delivery_time.strftime("%I:%M %p") if delivery_time else None,
            "order_type": order_type
        }
    
    def _get_estimated_time(self, order_type: int) -> str:
        """
        Get a formatted estimated time based on order type.
        
        Args:
            order_type: The type of order
            
        Returns:
            Formatted time string
        """
        now = datetime.now()
        
        if order_type == 1:  # Pickup
            est_time = now + timedelta(minutes=25)
            return est_time.strftime("%I:%M %p")
        elif order_type == 2:  # Delivery
            est_time = now + timedelta(minutes=55)
            return est_time.strftime("%I:%M %p")
        else:  # Eat-in
            est_time = now + timedelta(minutes=20)
            return est_time.strftime("%I:%M %p")
    
    def _get_current_call_sid(self) -> Optional[str]:
        """
        Get the current call SID from context.
        In a real implementation, this would be passed from the voice controller.
        
        Returns:
            The call SID if available, None otherwise
        """
        # This is a placeholder that will be replaced with actual implementation
        # when integrating with the voice controller
        return getattr(self, "current_call_sid", None)
    
    def set_current_call(self, call_sid: str):
        """
        Set the current call SID for context.
        
        Args:
            call_sid: The Twilio call SID
        """
        self.current_call_sid = call_sid
    
    def process_fulfillment_request(self, call_sid: str, request_text: str) -> Dict[str, Any]:
        """
        Process a fulfillment request for an order.
        
        Args:
            call_sid: The Twilio call SID
            request_text: The fulfillment request text
            
        Returns:
            The processing result
        """
        # Set the current call for context
        self.set_current_call(call_sid)
        
        # Process the message with the agent
        start_time = time.time()
        response = self.process_message(call_sid, request_text)
        duration = time.time() - start_time
        
        logger.info(f"Processed fulfillment request in {duration:.2f}s: {request_text}")
        
        # Return the result
        return {
            "success": True,
            "response": response,
            "processing_time": duration
        }