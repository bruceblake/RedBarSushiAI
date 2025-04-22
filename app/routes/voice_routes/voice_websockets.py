"""
Voice websockets module. This module contains websocket routes for real-time audio processing
and conversational interactions.
"""

import logging
import json
import asyncio
import time
import os
from flask import session, request
import openai

# Import sock from app
from app import sock

# Import blueprint
from . import voice_bp

# Import helpers
from .voice_core import get_session_id

# Import agent utilities
from app.utils.agent_utils import OrderParsingAgent

# Import real-time audio processing utilities
from app.utils.realtime_audio import get_audio_processor

# Set up logger
logger = logging.getLogger(__name__)

@sock.route("/api/ws/speech-to-text")
def speech_to_text(ws):
    """
    WebSocket endpoint for real-time speech-to-text conversion.
    
    This endpoint:
    1. Receives streaming audio data from client
    2. Processes it with the configured speech recognition service
    3. Returns real-time transcription results
    
    Used by web clients for real-time speech input processing.
    """
    # Set up session ID for tracking
    session_id = get_session_id()
    
    # Log connection
    logger.info(f"Speech-to-text WebSocket connected: {session_id}")
    
    # Get the audio processor for this session
    try:
        audio_processor = get_audio_processor()
        processor_config = {
            "interim_results": True,  # Return partial results as they arrive
            "model": "whisper-1",     # Use Whisper model for best results
            "format": "webm",         # Expected audio format
            "language": "en"          # English language
        }
        
        # Initialize the processor
        audio_processor.initialize(processor_config)
        
        # Send confirmation of connection
        ws.send(json.dumps({"status": "connected", "session_id": session_id}))
        
        # Process incoming audio data
        buffer = bytearray()
        
        while True:
            # Receive binary audio data
            data = ws.receive()
            
            # Check for client disconnect
            if data is None:
                logger.info(f"Speech-to-text WebSocket disconnected: {session_id}")
                break
            
            # Check for JSON control messages
            if isinstance(data, str):
                try:
                    msg = json.loads(data)
                    if msg.get("command") == "stop":
                        # Client is done sending audio
                        logger.info(f"Speech-to-text received stop command: {session_id}")
                        final_result = audio_processor.finalize(buffer)
                        if final_result:
                            ws.send(json.dumps({
                                "text": final_result["text"],
                                "is_final": True,
                                "confidence": final_result.get("confidence", 0.0)
                            }))
                        break
                except:
                    # Not a valid JSON control message, continue processing
                    pass
            
            # Process binary audio data
            if isinstance(data, bytes):
                # Add to buffer
                buffer.extend(data)
                
                # Process the current buffer
                result = audio_processor.process_chunk(buffer)
                
                # If we have a result, send it to the client
                if result:
                    ws.send(json.dumps({
                        "text": result["text"],
                        "is_final": result.get("is_final", False),
                        "confidence": result.get("confidence", 0.0)
                    }))
                    
                    # If this is a final result, clear the buffer
                    if result.get("is_final", False):
                        buffer = bytearray()
        
        # Clean up when done
        audio_processor.cleanup()
        
    except Exception as e:
        # Log the error
        logger.error(f"Error in speech-to-text WebSocket: {str(e)}")
        
        # Send error to client
        try:
            ws.send(json.dumps({"error": str(e)}))
        except:
            pass

@sock.route("/api/ws/conversation")
def conversation(ws):
    """
    WebSocket endpoint for multi-turn conversations with the AI.
    
    This endpoint:
    1. Maintains a conversation history
    2. Processes incoming messages
    3. Generates AI responses
    4. Returns responses to the client
    
    Used by web clients for chatbot-style interactions.
    """
    # Set up session ID for tracking
    session_id = get_session_id()
    
    # Log connection
    logger.info(f"Conversation WebSocket connected: {session_id}")
    
    # Initialize conversation history
    conversation_history = []
    
    # Add initial system message
    system_message = {
        "role": "system", 
        "content": (
            "You are an AI assistant for Red Bar Sushi, a Japanese sushi restaurant. "
            "You can help with menu information, taking orders, and answering questions "
            "about the restaurant. Keep your responses concise and helpful. "
            "If asked about placing an order, collect the complete order details before confirming."
        )
    }
    conversation_history.append(system_message)
    
    # Send confirmation of connection
    ws.send(json.dumps({
        "status": "connected", 
        "session_id": session_id,
        "message": "Hello! I'm the Red Bar Sushi AI assistant. How can I help you today?"
    }))
    
    # Process incoming messages
    while True:
        # Receive message
        data = ws.receive()
        
        # Check for client disconnect
        if data is None:
            logger.info(f"Conversation WebSocket disconnected: {session_id}")
            break
        
        try:
            # Parse the message
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            # Log the incoming message
            logger.info(f"Conversation received: {user_message[:50]}{'...' if len(user_message) > 50 else ''}")
            
            # Check for empty message
            if not user_message:
                ws.send(json.dumps({
                    "message": "I didn't receive any message. How can I help you?"
                }))
                continue
            
            # Add user message to history
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Generate response using OrderParsingAgent
            try:
                agent = OrderParsingAgent()
                
                # Check if this is a menu question
                if any(keyword in user_message.lower() for keyword in ["menu", "what do you have", "what's on the menu", "price", "cost"]):
                    # Handle as menu question
                    response = agent.menu_tool.answer_menu_question(user_message)
                else:
                    # Use general conversation
                    response = agent.generate_response(conversation_history)
            except Exception as agent_error:
                # Fall back to simple OpenAI completion
                logger.error(f"Agent error: {str(agent_error)}, falling back to OpenAI")
                
                try:
                    # Create a completion with the conversation history
                    oai_response = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=conversation_history,
                        max_tokens=150,
                        temperature=0.7
                    )
                    
                    # Extract the response text
                    response = oai_response.choices[0].message.content
                except Exception as openai_error:
                    # Ultimate fallback for all errors
                    logger.error(f"OpenAI fallback error: {str(openai_error)}")
                    response = "I'm sorry, I'm having trouble processing your request right now. Please try again."
            
            # Add assistant response to history
            conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Keep conversation history at a reasonable size (last 10 messages)
            if len(conversation_history) > 11:  # 1 system message + 10 conversation turns
                # Always keep the system message
                conversation_history = [system_message] + conversation_history[-10:]
            
            # Send response to client
            ws.send(json.dumps({
                "message": response
            }))
            
        except json.JSONDecodeError:
            # Handle invalid JSON
            logger.error(f"Invalid JSON received in conversation WebSocket: {data[:50]}...")
            ws.send(json.dumps({
                "error": "Invalid message format. Please send a valid JSON object with a 'message' field."
            }))
        except Exception as e:
            # Handle other errors
            logger.error(f"Error in conversation WebSocket: {str(e)}")
            ws.send(json.dumps({
                "error": "An error occurred while processing your message. Please try again."
            }))

@sock.route("/api/ws/text-to-speech")
def text_to_speech(ws):
    """
    WebSocket endpoint for real-time text-to-speech conversion.
    
    This endpoint:
    1. Receives text from client
    2. Converts it to speech using TTS service
    3. Streams audio data back to client
    
    Used by web clients for real-time speech output.
    """
    # Set up session ID for tracking
    session_id = get_session_id()
    
    # Log connection
    logger.info(f"Text-to-speech WebSocket connected: {session_id}")
    
    # Send confirmation of connection
    ws.send(json.dumps({
        "status": "connected", 
        "session_id": session_id
    }))
    
    # Initialize TTS service
    try:
        from app.utils.tts_service import TTSService
        tts = TTSService()
    except ImportError:
        logger.error("TTS service module not available")
        ws.send(json.dumps({
            "error": "Text-to-speech service is not available."
        }))
        return
    
    # Process incoming text messages
    while True:
        # Receive message
        data = ws.receive()
        
        # Check for client disconnect
        if data is None:
            logger.info(f"Text-to-speech WebSocket disconnected: {session_id}")
            break
        
        try:
            # Parse the message
            message_data = json.loads(data)
            text = message_data.get("text", "")
            voice = message_data.get("voice", "en-US-Neural2-F")  # Default voice
            
            # Log the incoming text
            logger.info(f"Text-to-speech received: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Check for empty text
            if not text:
                ws.send(json.dumps({
                    "error": "No text provided for speech synthesis."
                }))
                continue
            
            # Generate speech
            try:
                # Get audio data and format
                audio_data, audio_format = tts.synthesize(text, voice)
                
                # Send audio metadata
                ws.send(json.dumps({
                    "format": audio_format,
                    "size": len(audio_data),
                    "text": text,
                    "content_follows": True
                }))
                
                # Send binary audio data
                ws.send(audio_data)
                
            except Exception as tts_error:
                # Handle TTS errors
                logger.error(f"TTS error: {str(tts_error)}")
                ws.send(json.dumps({
                    "error": "Error generating speech. Please try again.",
                    "details": str(tts_error)
                }))
                
        except json.JSONDecodeError:
            # Handle invalid JSON
            logger.error(f"Invalid JSON received in text-to-speech WebSocket: {data[:50]}...")
            ws.send(json.dumps({
                "error": "Invalid message format. Please send a valid JSON object with a 'text' field."
            }))
        except Exception as e:
            # Handle other errors
            logger.error(f"Error in text-to-speech WebSocket: {str(e)}")
            ws.send(json.dumps({
                "error": "An error occurred while processing your request. Please try again."
            }))