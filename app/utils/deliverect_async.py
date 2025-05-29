"""
Async utilities for Deliverect integration.
"""
import logging
import uuid
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


def generate_order_id() -> str:
    """Generate a unique order ID."""
    return f"order_{uuid.uuid4().hex[:8]}"


def get_deliverect_headers(api_key: str) -> Dict[str, str]:
    """Get headers for Deliverect API requests."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def build_deliverect_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build order payload for Deliverect."""
    return {
        "channelOrderId": order_data.get("order_id", generate_order_id()),
        "orderType": order_data.get("order_type", "pickup"),
        "customer": {
            "name": order_data.get("customer_name", "Guest"),
            "phone": order_data.get("customer_phone", "")
        },
        "items": order_data.get("items", []),
        "payment": {
            "amount": order_data.get("total_price", 0)
        }
    }


async def send_order_to_deliverect_async(
    order_payload: Dict[str, Any],
    api_key: str,
    channel_link_id: str
) -> Dict[str, Any]:
    """Send order to Deliverect asynchronously."""
    try:
        headers = get_deliverect_headers(api_key)
        url = f"https://api.deliverect.com/channels/{channel_link_id}/orders"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=order_payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to send order to Deliverect: {e}")
        raise