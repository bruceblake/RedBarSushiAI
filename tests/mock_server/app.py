"""
Mock server for external services.
Provides fast, reliable mocks for Twilio, OpenAI, and Deliverect APIs.
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
import base64
import uuid
from datetime import datetime
import asyncio

app = FastAPI(title="RedBarSushi Mock Server")

# Store state for stateful mocks
mock_state = {
    "orders": {},
    "menu_items": [],
    "conversations": {}
}


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mock_server"}


# ======================
# Twilio Mocks
# ======================

@app.post("/twilio/voice/webhook")
async def mock_twilio_voice_webhook(request: Request):
    """Mock Twilio voice webhook."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", f"CA{uuid.uuid4().hex}")
    
    # Return TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Welcome to Red Bar Sushi mock service.</Say>
    <Connect>
        <Stream url="wss://mock-server:8000/ws/media/{call_sid}" />
    </Connect>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/sms/send")
async def mock_twilio_sms(data: dict):
    """Mock Twilio SMS API."""
    return {
        "sid": f"SM{uuid.uuid4().hex}",
        "status": "sent",
        "to": data.get("to"),
        "from": data.get("from"),
        "body": data.get("body"),
        "date_sent": datetime.utcnow().isoformat()
    }


# ======================
# OpenAI Mocks
# ======================

@app.post("/openai/v1/chat/completions")
async def mock_openai_chat(request: Request):
    """Mock OpenAI Chat Completions API."""
    data = await request.json()
    messages = data.get("messages", [])
    
    # Simple intent detection based on last message
    last_message = messages[-1]["content"] if messages else ""
    
    # Generate contextual response
    if "order" in last_message.lower():
        response_text = "I understand you'd like to place an order. What would you like?"
    elif "menu" in last_message.lower():
        response_text = "Our menu includes California Roll ($12.95), Spicy Tuna Roll ($14.95), and Edamame ($5.95)."
    elif "california" in last_message.lower():
        response_text = "I've added California Roll to your order. Would you like anything else?"
    else:
        response_text = "I can help you with your order. What would you like today?"
    
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": data.get("model", "gpt-3.5-turbo"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }


@app.websocket("/openai/v1/realtime")
async def mock_openai_realtime_websocket(websocket):
    """Mock OpenAI Realtime WebSocket."""
    await websocket.accept()
    
    try:
        # Send session.created event
        await websocket.send_json({
            "type": "session.created",
            "session": {
                "id": f"sess_{uuid.uuid4().hex}",
                "model": "gpt-4o-realtime-preview-2024-10-01",
                "modalities": ["text", "audio"],
                "voice": "shimmer"
            }
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "session.update":
                # Acknowledge session update
                await websocket.send_json({
                    "type": "session.updated",
                    "session": data["session"]
                })
                
            elif data["type"] == "input_audio_buffer.append":
                # Simulate audio processing
                await asyncio.sleep(0.1)
                
                # Send transcript
                await websocket.send_json({
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": f"item_{uuid.uuid4().hex}",
                    "transcript": "I would like to order two California rolls"
                })
                
            elif data["type"] == "conversation.item.create":
                # Handle text input
                await websocket.send_json({
                    "type": "conversation.item.created",
                    "item": data.get("item", {})
                })
                
            elif data["type"] == "response.create":
                # Generate response
                await websocket.send_json({
                    "type": "response.created",
                    "response": {
                        "id": f"resp_{uuid.uuid4().hex}",
                        "status": "completed"
                    }
                })
                
                # Send audio delta (mock)
                await websocket.send_json({
                    "type": "response.audio.delta",
                    "delta": base64.b64encode(b"\x00" * 320).decode()  # Mock audio
                })
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


# ======================
# Deliverect Mocks
# ======================

@app.get("/deliverect/locations")
async def mock_deliverect_locations():
    """Mock Deliverect locations endpoint."""
    return {
        "locations": [{
            "_id": "loc_123",
            "name": "Red Bar Sushi Main",
            "channelLinkId": "channel_123",
            "address": "123 Sushi St"
        }]
    }


@app.post("/deliverect/menu/update")
async def mock_deliverect_menu_webhook(data: dict):
    """Mock Deliverect menu update webhook."""
    # Store menu items
    if "products" in data:
        mock_state["menu_items"] = data["products"]
    
    return {"status": "success", "processed": len(data.get("products", []))}


@app.post("/deliverect/orders")
async def mock_deliverect_order_submission(order: dict):
    """Mock Deliverect order submission."""
    order_id = f"dlv_{uuid.uuid4().hex[:8]}"
    
    # Store order
    mock_state["orders"][order_id] = {
        **order,
        "_id": order_id,
        "status": 1,  # Accepted
        "estimatedTime": 15,
        "createdAt": datetime.utcnow().isoformat()
    }
    
    return {
        "_id": order_id,
        "status": 1,
        "channelOrderId": order.get("channelOrderId"),
        "estimatedTime": 15,
        "message": "Order accepted"
    }


@app.get("/deliverect/orders/{order_id}")
async def mock_deliverect_order_status(order_id: str):
    """Mock Deliverect order status endpoint."""
    order = mock_state["orders"].get(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order


@app.post("/deliverect/orders/{order_id}/status")
async def mock_deliverect_order_status_update(order_id: str, data: dict):
    """Mock Deliverect order status update."""
    order = mock_state["orders"].get(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order["status"] = data.get("status", order["status"])
    return {"status": "updated", "order": order}


# ======================
# Mock Data Management
# ======================

@app.post("/mock/reset")
async def reset_mock_state():
    """Reset all mock state."""
    global mock_state
    mock_state = {
        "orders": {},
        "menu_items": [],
        "conversations": {}
    }
    return {"status": "reset"}


@app.get("/mock/state")
async def get_mock_state():
    """Get current mock state for debugging."""
    return mock_state


@app.post("/mock/menu/seed")
async def seed_mock_menu():
    """Seed mock menu with test data."""
    mock_state["menu_items"] = [
        {
            "_id": "item_1",
            "plu": "PLU_CALI_001",
            "name": "California Roll",
            "price": 1295,
            "isAvailable": True
        },
        {
            "_id": "item_2",
            "plu": "PLU_SPICY_TUNA",
            "name": "Spicy Tuna Roll",
            "price": 1495,
            "isAvailable": True
        },
        {
            "_id": "item_3",
            "plu": "PLU_EDAMAME",
            "name": "Edamame",
            "price": 595,
            "isAvailable": True
        }
    ]
    return {"status": "seeded", "items": len(mock_state["menu_items"])}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)