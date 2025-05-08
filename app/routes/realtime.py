"""
WebSocket routes for realtime audio processing with OpenAI Agents SDK.
This module provides the WebSocket endpoints for handling realtime audio streams.
"""

from flask import Blueprint, request, jsonify, current_app
import logging
import json
import time
import os
import traceback
import base64
import uuid
import websocket  # Import websocket for WebSocketConnectionClosedException handling
from typing import Dict, List, Any, Optional, Tuple, Union
import gevent
from gevent import Greenlet
from gevent.queue import Queue, Empty
from gevent.event import Event

from app import sock
from app.utils.realtime_audio_sdk import realtime_processor
from app.utils.conversation_store_sdk import agents_conversation_store

logger = logging.getLogger(__name__)

# Create blueprint
realtime_bp = Blueprint("realtime", __name__)

@sock.route("/ws/media/<call_sid>")
def handle_media_realtime(ws, call_sid):
    """
    WebSocket endpoint for handling media streams from Twilio.
    
    This function handles bidirectional audio streaming between
    Twilio's Media Streams and OpenAI's Realtime API. It receives audio from Twilio,
    forwards it to OpenAI, and returns synthesized responses back to Twilio.
    
    Uses gevent greenlets for concurrency to work with gevent worker.
    
    Args:
        ws: The WebSocket connection from Twilio
        call_sid: Call SID passed in URL path
    """
    import websocket  # gevent-compatible websocket-client library

    # Log connection
    logger.critical(f"[{call_sid}] WebSocket connection established (Gevent Handler)")
    stream_sid = None  # Will be set later
    openai_ws = None  # Define here for finally block
    
    # --- 1. Initial Setup ---
    try:
        # Get Config
        openai_api_key = current_app.config.get('OPENAI_API_KEY', os.environ.get("OPENAI_API_KEY"))
        if not openai_api_key:
            # Last resort fallback for development
            try:
                from app.utils.agent_utils import OPENAI_API_KEY
                openai_api_key = OPENAI_API_KEY
            except Exception as e:
                logger.error(f"[{call_sid}] Error importing OPENAI_API_KEY: {e}")
                return
        
        openai_ws_url = "wss://api.openai.com/v1/realtime"
        openai_model = current_app.config.get('OPENAI_REALTIME_MODEL', "gpt-4o-realtime-preview-2024-10-01")
        openai_voice = current_app.config.get('OPENAI_REALTIME_VOICE', "shimmer")
        system_instructions = current_app.config.get('OPENAI_REALTIME_INSTRUCTIONS', """
        You are an AI assistant for a sushi restaurant named Red Bar Sushi. Your role is to help customers with their 
        orders and menu questions in a friendly, efficient manner. Speak with a helpful, welcoming tone appropriate 
        for a high-end sushi restaurant.
        """)

        # Handle initial Twilio messages ('connected', 'start') - SYNCHRONOUSLY
        logger.info(f"[{call_sid}] Waiting for initial Twilio messages...")
        connected_received = False
        for _ in range(2):  # Try receiving twice to get connected then start
            try:
                msg_str = ws.receive(timeout=10)  # Blocking receive with timeout
                if msg_str is None:  # Timeout or clean close
                    logger.warning(f"[{call_sid}] Did not receive expected message from Twilio.")
                    return
                
                message = json.loads(msg_str)
                event = message.get("event")
                logger.info(f"[{call_sid}] Received initial message: {event}")

                if event == "connected":
                    connected_received = True
                elif event == "start":
                    stream_sid = message.get("start", {}).get("streamSid")
                    if not stream_sid:
                         logger.error(f"[{call_sid}] 'start' event missing streamSid.")
                         return
                    logger.info(f"[{call_sid}] Twilio media stream started. Stream SID: {stream_sid}")
                    break  # Got start, proceed
                else:
                    logger.warning(f"[{call_sid}] Received unexpected initial message type: {event}")

            except TimeoutError:  # Check exact exception from ws.receive timeout
                logger.error(f"[{call_sid}] Timeout waiting for initial message from Twilio.")
                return
            except json.JSONDecodeError:
                 logger.error(f"[{call_sid}] Failed to decode initial JSON from Twilio: {msg_str}", exc_info=True)
                 return
            except Exception as e:  # Catch WebSocket closed errors specifically if possible
                logger.error(f"[{call_sid}] Error receiving initial message: {e}", exc_info=True)
                return

        if not stream_sid:
            logger.error(f"[{call_sid}] Failed to get Stream SID from initial Twilio messages.")
            return  # Close handled in finally

        # Send Welcome
        ws.send(json.dumps({"type": "connected", "message": "Connected to RedBarSushi AI (Gevent)", 
                           "call_sid": call_sid, "stream_sid": stream_sid}))
        logger.info(f"[{call_sid}] Sent welcome message.")

        # Initialize Agent
        try:
            # If agent factory needs app context, push one temporarily
            from app.agents.factory_with_orchestration import enhanced_agent_factory
            frontline_agent = enhanced_agent_factory.create_agents()
            logger.info(f"[{call_sid}] Successfully initialized agent.")
        except Exception as agent_error:
            logger.error(f"[{call_sid}] Failed to initialize agent: {agent_error}", exc_info=True)
            frontline_agent = None  # Handle gracefully later

        # --- 2. Connect to OpenAI (Using websocket-client) ---
        openai_connect_url = f"{openai_ws_url}?model={openai_model}"  # Model in URL as per docs
        openai_headers = [
            f"Authorization: Bearer {openai_api_key}",
            "OpenAI-Beta: realtime=v1"
        ]
        logger.info(f"[{call_sid}] Connecting to OpenAI: {openai_connect_url}")
        # Use websocket-client's create_connection (blocking, suitable for gevent)
        # Add timeout for connection attempt itself
        openai_ws = websocket.create_connection(openai_connect_url, header=openai_headers, timeout=10)
        # Set timeout for subsequent recv calls
        openai_ws.settimeout(15)  # Example: 15 second timeout for receiving messages
        logger.info(f"[{call_sid}] Successfully connected to OpenAI.")

        # --- 3. Send Session Config ---
        send_openai_session_configuration_sync(openai_ws, call_sid, openai_model, openai_voice, system_instructions)

        # --- 4. Start Concurrent Greenlets ---
        logger.info(f"[{call_sid}] Spawning Greenlets...")
        
        # Pass mutable list for stream_sid if needed, though it's likely set now
        stream_sid_container = [stream_sid] 

        # Context object for agents/tools
        run_context_data = {'call_sid': call_sid, 'stream_sid': stream_sid} 

        # Spawn greenlets
        fwd_greenlet = gevent.spawn(
            receive_from_twilio_and_forward_to_openai_sync, 
            ws, openai_ws, call_sid, stream_sid_container
        )
        proc_greenlet = gevent.spawn(
            process_openai_responses_and_interact_sync, 
            openai_ws, ws, call_sid, stream_sid_container, frontline_agent, run_context_data
        )
        hb_greenlet = gevent.spawn(
            send_heartbeats_sync, 
            ws, call_sid
        )

        # Wait for any of them to finish
        logger.info(f"[{call_sid}] Joining Greenlets...")
        # joinall waits for all specified greenlets, raise_error=False prevents one dying from killing the join immediately
        gevent.joinall([fwd_greenlet, proc_greenlet, hb_greenlet], raise_error=False) 
        logger.info(f"[{call_sid}] Greenlets joined/completed.")

    except websocket.WebSocketTimeoutException:
        logger.error(f"[{call_sid}] Timeout during OpenAI WebSocket operation.")
    except websocket.WebSocketException as e:
        logger.error(f"[{call_sid}] OpenAI WebSocket Error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[{call_sid}] Error in main handler: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] Cleaning up main handler...")
        # Cleanly close OpenAI connection
        if openai_ws and hasattr(openai_ws, 'connected') and openai_ws.connected:
            try:
                logger.info(f"[{call_sid}] Closing OpenAI WebSocket.")
                # websocket-client's close() method doesn't accept code/reason parameters
                openai_ws.close()  # No arguments for websocket-client
            except Exception as close_err:
                logger.error(f"[{call_sid}] Error closing OpenAI WS: {close_err}")
        else:
            logger.info(f"[{call_sid}] OpenAI WS already closed or not established.")

        # Cleanly close Twilio connection
        # Use the correct close method for Flask-Sock/simple-websocket ws object
        if ws and hasattr(ws, 'connected') and ws.connected:
            try:
                logger.info(f"[{call_sid}] Closing Twilio WebSocket.")
                # Simplest form without arguments to avoid state errors
                ws.close()  # No arguments to avoid state errors
            except Exception as close_err:
                logger.error(f"[{call_sid}] Error closing Twilio WS: {close_err}")
        else:
            logger.info(f"[{call_sid}] Twilio WS already closed or not established.")
            
        logger.critical(f"[{call_sid}] WebSocket handler finished.")


def send_openai_session_configuration_sync(openai_ws, call_sid, openai_model, openai_voice, system_instructions):
    """
    Constructs and sends the session.update message SYNCHRONOUSLY.
    
    Args:
        openai_ws: WebSocket connection to OpenAI
        call_sid: The Twilio call SID
        openai_model: The OpenAI model to use
        openai_voice: The voice to use for TTS
        system_instructions: The system instructions for the assistant
    """
    logger.info(f"[{call_sid}] Preparing session.update payload (sync).")
    
    # Get tool definitions if needed
    try:
        tools = get_tool_definitions_for_openai()
        logger.info(f"[{call_sid}] Successfully loaded {len(tools)} tool definitions")
    except Exception as e:
        logger.error(f"[{call_sid}] Error loading tool definitions: {e}", exc_info=True)
        tools = []  # Fallback to empty tools list
    
    # VAD configuration based on OpenAI documentation
    turn_detection_config = {
        "type": "server_vad",
        "silence_duration_ms": 2000,  # 2 second silence threshold
        "create_response": True       # Auto-generate response on silence detection
    }
    
    # Main session configuration - Removed 'language' which is not accepted by the API
    session_update_payload = {
        "type": "session.update",
        "session": {
            "model": openai_model,
            "voice": openai_voice,
            "instructions": system_instructions,
            "input_audio_format": "g711_ulaw",  # Format for Twilio μ-law audio
            "output_audio_format": "g711_ulaw", # Format for Twilio μ-law audio
            "modalities": ["text", "audio"],
            "turn_detection": turn_detection_config,
            "tools_enabled": True  # Explicitly enable tools support
        }
    }
    
    # Add tools if available
    if tools:
        session_update_payload["session"]["tools"] = tools
        session_update_payload["session"]["tool_choice"] = "auto"
    
    logger.debug(f"[{call_sid}] Session update payload: {json.dumps(session_update_payload)}")
    logger.info(f"[{call_sid}] Sending session.update (sync)")
    try:
        openai_ws.send(json.dumps(session_update_payload))  # Blocking send
        logger.info(f"[{call_sid}] session.update sent successfully (sync).")
    except Exception as e:
        logger.error(f"[{call_sid}] Failed to send session.update (sync): {e}", exc_info=True)
        raise  # Re-raise to potentially terminate if config fails

def receive_from_twilio_and_forward_to_openai_sync(twilio_ws, openai_ws, call_sid, stream_sid_container):
    """
    Receives from Twilio (sync), forwards audio to OpenAI (sync). Runs in a greenlet.
    
    Args:
        twilio_ws: The WebSocket connection from Twilio
        openai_ws: The WebSocket connection to OpenAI
        call_sid: The Twilio call SID
        stream_sid_container: Mutable list containing the stream SID
    """
    # websocket module is now imported at the top level
    logger.info(f"[{call_sid}] Starting Twilio->OpenAI forwarding greenlet.")
    try:
        while True:
            # Check if OpenAI connection is still alive before receiving
            if not openai_ws or not hasattr(openai_ws, 'connected') or not openai_ws.connected:
                 logger.warning(f"[{call_sid}] OpenAI WS no longer connected. Stopping Twilio forwarder.")
                 break
                 
            try:
                # Blocking receive with timeout (gevent compatible)
                message_str = twilio_ws.receive(timeout=5)  # Adjust timeout as needed
                if message_str is None:  # Timeout occurred, loop again
                    gevent.sleep(0.01)  # Yield control
                    continue

                message = json.loads(message_str)
                event = message.get("event")

                if event == "start":
                    # Already handled mostly, but update just in case
                    new_sid = message.get("start", {}).get("streamSid")
                    if new_sid and stream_sid_container[0] != new_sid:
                         logger.info(f"[{call_sid}] Received Stream SID: {new_sid}")
                         stream_sid_container[0] = new_sid
                elif event == "media":
                    audio_payload = message.get("media", {}).get("payload")
                    if audio_payload:
                        openai_audio_message = {
                            "type": "input_audio_buffer.append",
                            "audio": audio_payload
                        }
                        openai_ws.send(json.dumps(openai_audio_message))  # Blocking send
                    else:
                        logger.warning(f"[{call_sid}] Twilio 'media' event with no payload.")
                elif event == "stop":
                    logger.info(f"[{call_sid}] Twilio 'stop' event received. Stopping audio forwarding.")
                    # No need to send commit/finalize with default server VAD
                    break
                # Handle 'mark' if needed
                elif event == "mark":
                    mark_name = message.get("mark", {}).get("name", "")
                    logger.info(f"[{call_sid}] Received mark event: {mark_name}")
                else:
                    logger.debug(f"[{call_sid}] Unhandled Twilio event: {event}")

            except TimeoutError:  # Or specific timeout exception for ws.receive
                 # No message received in timeout window, continue loop
                 gevent.sleep(0.01)
                 continue
            except json.JSONDecodeError:
                logger.error(f"[{call_sid}] Error decoding JSON from Twilio: {message_str}", exc_info=True)
            except websocket.WebSocketConnectionClosedException:  # Error sending to OpenAI
                 logger.warning(f"[{call_sid}] OpenAI WS connection closed during send. Stopping forwarder.")
                 break
            except Exception as e:  # Catch errors from ws.receive or ws.send
                 if "closed" in str(e).lower():  # Crude check for closed connection on twilio_ws
                      logger.info(f"[{call_sid}] Twilio WS connection closed.")
                 else:
                      logger.error(f"[{call_sid}] Error in Twilio->OpenAI greenlet: {e}", exc_info=True)
                 break  # Exit loop on significant errors

    except Exception as e:  # Catch errors in the greenlet's outer loop
        logger.error(f"[{call_sid}] Unhandled error in Twilio->OpenAI greenlet: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] Twilio->OpenAI forwarding greenlet finished.")


def process_openai_responses_and_interact_sync(openai_ws, twilio_ws, call_sid, stream_sid_container, frontline_agent, run_context_data):
    """
    Receives from OpenAI (sync), forwards audio to Twilio (sync), interacts with Agent (sync).
    Runs in a greenlet.
    
    Args:
        openai_ws: WebSocket connection to OpenAI
        twilio_ws: WebSocket connection to Twilio
        call_sid: The Twilio call SID
        stream_sid_container: Mutable list containing the stream SID
        frontline_agent: The frontline agent instance
        run_context_data: Context data for tools and agent
    """
    # websocket module is now imported at the top level
    logger.info(f"[{call_sid}] Starting OpenAI->Twilio/Agent processing greenlet")
    
    # Define event types to log with different verbosity
    LOG_EVENT_TYPES = [
        'session.created', 'session.updated', 'session.error', 'session.success',
        'speech.started', 'speech.finished', 'speech.segmentation',
        'silence_detected', 'input_audio_buffer.speech_started', 'input_audio_buffer.speech_stopped'
    ]
    
    try:
        while True:
            try:
                # Check if Twilio connection is still alive before receiving
                if not twilio_ws or not hasattr(twilio_ws, 'connected') or not twilio_ws.connected:
                     logger.warning(f"[{call_sid}] Twilio WS no longer connected. Stopping OpenAI processor.")
                     break

                # Blocking receive from OpenAI with timeout
                message_str = openai_ws.recv()  # websocket-client uses settimeout for recv
                if not message_str:  # Connection likely closed cleanly
                    logger.info(f"[{call_sid}] OpenAI WS recv returned empty, likely closed.")
                    break

                payload = json.loads(message_str)
                event_type = payload.get("type")
                
                # Basic logging (adjust verbosity)
                if event_type not in ["response.audio.delta", "transcript.delta"]:
                     logger.debug(f"[{call_sid}] OpenAI Event Received - Type: '{event_type}'")

                # 1. Handle Audio Output from OpenAI (TTS)
                if event_type == "response.audio.delta" and payload.get("delta"):
                    if stream_sid_container[0]:
                         twilio_media_message = {
                             "event": "media",
                             "streamSid": stream_sid_container[0],
                             "media": {"payload": payload["delta"]}
                         }
                         twilio_ws.send(json.dumps(twilio_media_message))  # Blocking send
                    else:
                         logger.warning(f"[{call_sid}] Stream SID not available for sending audio delta.")

                # 2. Handle Final User Transcript 
                elif event_type == "conversation.item.input_audio_transcription.completed":  # Verified type
                    transcript = payload.get("transcript", "")
                    logger.info(f"[{call_sid}] Final User Transcript: '{transcript}'")
                    if transcript and frontline_agent:
                        try:
                            # --- AGENT INTEGRATION (SYNCHRONOUS) ---
                            logger.info(f"[{call_sid}] Processing transcript with agent...")
                            # Assuming process_voice_input is now synchronous or gevent-compatible
                            agent_response_text = frontline_agent.process_voice_input(call_sid, transcript, context=run_context_data) 
                            logger.info(f"[{call_sid}] Agent response: '{agent_response_text}'")

                            if agent_response_text:
                                # --- TTS Trigger (SYNCHRONOUS) ---
                                # Step 1: Create conversation item
                                tts_item_payload = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "assistant",  # Or user, test which works
                                        "content": [{"type": "input_text", "text": agent_response_text}]  # Verified type
                                    }
                                }
                                logger.info(f"[{call_sid}] Sending TTS item to OpenAI")
                                openai_ws.send(json.dumps(tts_item_payload))

                                # Step 2: Create response
                                tts_response_payload = {
                                    "type": "response.create",
                                    "response": {"modalities": ["audio"]}
                                }
                                logger.info(f"[{call_sid}] Sending response.create for TTS")
                                openai_ws.send(json.dumps(tts_response_payload))

                        except Exception as agent_err:
                             logger.error(f"[{call_sid}] Error processing transcript with agent: {agent_err}", exc_info=True)
                             # Send TTS error message to user
                             try:
                                error_message = "I'm sorry, I'm having trouble understanding. Could you please try again?"
                                openai_ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "assistant",
                                        "content": [{"type": "input_text", "text": error_message}]
                                    }
                                }))
                                openai_ws.send(json.dumps({
                                    "type": "response.create",
                                    "response": {"modalities": ["audio"]}
                                }))
                             except Exception as recovery_err:
                                logger.error(f"[{call_sid}] Failed to send error message: {recovery_err}")

                # 3. Handle Tool Calls
                elif event_type == "tool_calls":  # Verified type
                    tool_calls_data = payload.get("tool_calls", [])
                    logger.info(f"[{call_sid}] Received tool_calls: {tool_calls_data}")
                    tool_outputs = []
                    
                    for tc in tool_calls_data:
                        tool_call_id = tc["id"]
                        function_name = tc["function"]["name"]
                        try:
                             function_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                             logger.error(f"[{call_sid}] Failed to parse tool args for {function_name}: {tc['function']['arguments']}")
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps({"error": "Invalid arguments JSON"})})
                             continue

                        logger.info(f"[{call_sid}] Executing tool '{function_name}' with args: {function_args}")
                        try:
                             # --- TOOL EXECUTION (SYNCHRONOUS) ---
                             tool_result = execute_rbs_tool_sync(function_name, function_args, run_context_data) 
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps(tool_result)})
                        except Exception as tool_exec_err:
                             logger.error(f"[{call_sid}] Error executing tool {function_name}: {tool_exec_err}", exc_info=True)
                             tool_outputs.append({"tool_call_id": tool_call_id, "output": json.dumps({"error": str(tool_exec_err)})})

                    if tool_outputs:
                        # Send results back (Step 1 of Tool Flow Part 2)
                        for tool_output in tool_outputs:
                            # Each tool result needs its own conversation.item.create event
                            tool_results_item = {
                                "type": "conversation.item.create", 
                                "item": {
                                    "type": "function_call_output", 
                                    "call_id": tool_output["tool_call_id"],
                                    "output": tool_output["output"] 
                                }
                            }
                            logger.info(f"[{call_sid}] Sending tool result for {tool_output['tool_call_id']}")
                            openai_ws.send(json.dumps(tool_results_item))
                        
                        # Request a single response after all tool results
                        response_trigger = {
                            "type": "response.create",
                            "response": {"modalities": ["text", "audio"]}
                        }
                        logger.info(f"[{call_sid}] Sending response.create after tool results")
                        openai_ws.send(json.dumps(response_trigger))

                # 4. Handle Session Errors
                elif event_type == "error" or event_type == "session.error" or "error" in payload:
                     error_details = payload.get("error", payload)
                     logger.error(f"[{call_sid}] OpenAI Session Error Received: {error_details}")
                     # Send TTS error message to user
                     try:
                        error_message = "I'm sorry, I'm experiencing technical difficulties. Please try again in a moment."
                        openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "input_text", "text": error_message}]
                            }
                        }))
                        openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {"modalities": ["audio"]}
                        }))
                        # Give TTS time to complete
                        gevent.sleep(3)
                     except Exception as e:
                        logger.error(f"[{call_sid}] Failed to send error message: {e}")
                     
                     try:
                        if twilio_ws.connected:
                            # Use no-argument close to avoid state errors
                            twilio_ws.close()
                     except Exception as close_err:
                          logger.error(f"[{call_sid}] Error closing Twilio WS after OpenAI error: {close_err}")
                     break # Exit loop

                # Log other events for debugging
                elif event_type in LOG_EVENT_TYPES:
                     logger.info(f"[{call_sid}] OpenAI Event Logged - Type: '{event_type}'")
                
                # For VAD detection events
                elif event_type == "input_audio_buffer.speech_started":
                    logger.info(f"[{call_sid}] VAD detected speech start")
                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info(f"[{call_sid}] VAD detected speech stop")

            except websocket.WebSocketTimeoutException:
                 # Expected during inactivity, just continue loop
                 gevent.sleep(0.01)
                 continue
            except json.JSONDecodeError:
                logger.error(f"[{call_sid}] Error decoding JSON from OpenAI: {message_str}", exc_info=True)
            except websocket.WebSocketConnectionClosedException:
                 logger.info(f"[{call_sid}] OpenAI WS connection closed.")
                 break
            except Exception as e:  # Catch errors sending to twilio_ws or other processing
                 if "closed" in str(e).lower():  # Crude check
                      logger.info(f"[{call_sid}] Twilio WS connection closed during processing.")
                 else:
                      logger.error(f"[{call_sid}] Error processing OpenAI message: {e}", exc_info=True)
                 break  # Exit loop on significant errors

    except Exception as e:  # Catch errors in the greenlet's outer loop
        logger.error(f"[{call_sid}] Unhandled error in OpenAI->Twilio/Agent greenlet: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] OpenAI->Twilio/Agent processing greenlet finished.")

def execute_rbs_tool_sync(function_name, args, run_context_data):
    """
    Executes the appropriate RedBarSushiAI tool SYNCHRONOUSLY.
    
    Args:
        function_name: The name of the function to execute
        args: The arguments to pass to the function
        run_context_data: Context data for the tool
        
    Returns:
        The result of the tool execution
    """
    call_sid = run_context_data.get('call_sid', 'unknown')
    logger.info(f"[{call_sid}] Attempting SYNC execution: Tool='{function_name}', Args={args}")

    try:
        # Import the tools registry if available
        try:
            from app.routes.voice.utils.tools_registry import execute_tool
            # Use the registry's execute_tool function if available
            return execute_tool(function_name, args, call_sid=call_sid)
        except ImportError:
            logger.warning(f"[{call_sid}] Tools registry not available, falling back to direct execution")
            
        # --- Direct Dispatch Method ---
        # Import agent factory to get specialized agents
        from app.agents.factory_with_orchestration import enhanced_agent_factory
            
        if function_name == "lookup_menu_item":
            menu_agent = enhanced_agent_factory.get_menu_agent()
            if not menu_agent:
                return {"error": "Menu agent not available"}
            return menu_agent.lookup_menu_item(item_name=args.get("item_name"))
            
        elif function_name == "add_item_to_cart":
            cart_agent = enhanced_agent_factory.get_cart_agent()
            if not cart_agent:
                return {"error": "Cart agent not available"}
            return cart_agent.add_to_cart(
                item_plu=args.get("plu"), 
                quantity=args.get("quantity", 1),
                modifiers=args.get("modifiers", [])
            )
            
        elif function_name == "get_current_cart":
            cart_agent = enhanced_agent_factory.get_cart_agent()
            if not cart_agent:
                return {"error": "Cart agent not available"}
            return cart_agent.get_cart(session_id=call_sid)
            
        elif function_name == "get_restaurant_info":
            # This could be handled directly if not requiring a specialized agent
            info_type = args.get("query", "general")
            # Sample restaurant information
            info = {
                "hours": "Monday-Friday: 11am-10pm, Saturday-Sunday: 12pm-11pm",
                "location": "123 Main Street, Anytown, USA",
                "phone": "(555) 123-4567",
                "delivery": "Available within 5 miles, $3.99 fee"
            }
            return {"info_type": info_type, "information": info.get(info_type, "Information not available")}
            
        else:
            logger.error(f"[{call_sid}] Unknown tool requested: {function_name}")
            return {"error": f"Unknown tool: {function_name}"}
            
    except Exception as e:
        logger.error(f"[{call_sid}] Error executing tool '{function_name}': {e}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

def send_heartbeats_sync(twilio_ws, call_sid):
    """
    Sends heartbeats to Twilio periodically. Runs in a greenlet.
    
    Args:
        twilio_ws: WebSocket connection to Twilio
        call_sid: The Twilio call SID
    """
    logger.info(f"[{call_sid}] Starting heartbeat greenlet.")
    count = 0
    try:
        while True:
            gevent.sleep(10)  # Wait 10 seconds
            count += 1
            if not twilio_ws or not hasattr(twilio_ws, 'connected') or not twilio_ws.connected:
                logger.info(f"[{call_sid}] Twilio WS closed. Stopping heartbeats.")
                break
            try:
                heartbeat = {"type": "heartbeat", "count": count, "timestamp": time.time()}
                twilio_ws.send(json.dumps(heartbeat))  # Blocking send
                # logger.debug(f"[{call_sid}] Sent heartbeat #{count}")
            except Exception as e:
                 logger.error(f"[{call_sid}] Error sending heartbeat: {e}")
                 break  # Stop on error
    except Exception as e:
         logger.error(f"[{call_sid}] Unhandled error in heartbeat greenlet: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid}] Heartbeat greenlet finished.")

def get_tool_definitions_for_openai():
    """
    Return the tool definitions for OpenAI Realtime API in the proper format.
    
    This function defines the schema for tools that can be called by OpenAI's model.
    Enhanced descriptions to guide tool selection.
    
    Returns:
        List of tool definitions in the format expected by OpenAI
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_menu_item",
                "description": "Use this tool only when a customer asks about a specific menu item's details (price, description, ingredients, availability). Input the customer's phrasing of the item name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {
                            "type": "string",
                            "description": "The exact name or phrase the customer used to refer to the menu item"
                        }
                    },
                    "required": ["item_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_item_to_cart",
                "description": "Use this tool only to add a confirmed item, quantity, and selected modifiers (identified by their PLUs) to the current order. Do not use this for inquiries or before confirming the item with the customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plu": {
                            "type": "string",
                            "description": "The exact PLU code of the menu item (obtained from lookup_menu_item)"
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "The quantity of the item to add (default: 1)",
                            "default": 1
                        },
                        "modifiers": {
                            "type": "array",
                            "description": "Modifiers to apply to the item (if any)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "plu": {
                                        "type": "string",
                                        "description": "The exact PLU code of the modifier (obtained from lookup_menu_item)"
                                    },
                                    "quantity": {
                                        "type": "integer",
                                        "description": "The quantity of the modifier (default: 1)",
                                        "default": 1
                                    }
                                },
                                "required": ["plu"]
                            }
                        }
                    },
                    "required": ["plu"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_cart",
                "description": "Use this tool to retrieve the current contents and total price of the order, typically for summarization before confirmation or when the customer asks what's in their cart.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_restaurant_info",
                "description": "Use this tool to answer general questions about the restaurant like operating hours, address, phone number, or delivery policies. Do not use for menu-specific questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The specific information being requested (e.g., 'hours', 'location', 'phone', 'delivery')"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]


def send_heartbeats(ws, call_sid, shutdown_event):
    """
    Sends periodic heartbeat messages to keep the WebSocket connection alive.
    """
    logger.info(f"[{call_sid}] Starting heartbeat greenlet")
    count = 0
    
    try:
        while not shutdown_event.is_set():
            gevent.sleep(10)  # Send heartbeat every 10 seconds
            if shutdown_event.is_set():
                break
                
            count += 1
            try:
                heartbeat = {
                    "type": "heartbeat",
                    "count": count,
                    "timestamp": time.time()
                }
                ws.send(json.dumps(heartbeat))
                logger.debug(f"[{call_sid}] Sent heartbeat #{count}")
            except Exception as e:
                logger.error(f"[{call_sid}] Heartbeat error: {e}")
                shutdown_event.set()
                break
                
    except Exception as e:
        logger.error(f"[{call_sid}] Error in heartbeat greenlet: {e}")
        logger.error(traceback.format_exc())
        shutdown_event.set()
    finally:
        logger.info(f"[{call_sid}] Heartbeat greenlet ended")


# Legacy route removed - all connections should now use /ws/media/<call_sid>
# TwiML must include the call_sid in the path parameter


@sock.route("/ws/realtime")
def handle_realtime(ws):
    """
    WebSocket endpoint for realtime AI conversation.
    
    Args:
        ws: The WebSocket connection
    """
    logger.info("WebSocket connection established for realtime AI")
    
    # Get the call SID from query parameters or headers
    call_sid = request.args.get("CallSid") or request.headers.get("X-Twilio-CallSid")
    
    if not call_sid:
        logger.error("No CallSid provided")
        ws.send(json.dumps({"error": "No CallSid provided"}))
        return
    
    logger.info(f"[{call_sid}] Starting realtime AI for call")
    
    # Send initial message
    ws.send(json.dumps({
        "type": "connected",
        "message": "Connected to realtime AI processor",
        "call_sid": call_sid
    }))
    
    # Audio processing queue and stop event
    audio_queue = Queue()
    stop_event = Event()
    
    # Audio receiver greenlet
    def receive_audio():
        while not stop_event.is_set():
            try:
                data = ws.receive(timeout=0.5)
                
                # If no data received, just continue
                if not data:
                    gevent.sleep(0.01)
                    continue
                
                # Check if it's a control message
                if isinstance(data, str):
                    try:
                        control = json.loads(data)
                        if control.get("type") == "end":
                            logger.info(f"[{call_sid}] Received end message for call")
                            stop_event.set()
                            break
                    except json.JSONDecodeError:
                        # Not JSON, treat as binary audio data
                        pass
                
                # Put data in queue for processing
                audio_queue.put(data)
            except TimeoutError:
                # Normal timeout during polling, continue
                continue
            except Exception as e:
                logger.error(f"[{call_sid}] Error receiving WebSocket message: {str(e)}")
                stop_event.set()
                break
    
    # Result sender greenlet
    def process_and_send_results():
        audio_chunks = []
        
        def get_next_audio_chunk():
            """Generator that yields audio chunks from the queue"""
            while not stop_event.is_set():
                try:
                    # Get data with timeout to regularly check stop_event
                    chunk = audio_queue.get(timeout=0.5)
                    yield chunk
                except Empty:
                    # No data available yet
                    if stop_event.is_set() and len(audio_chunks) == 0:
                        # If stopped and no more audio, break
                        break
                    gevent.sleep(0.01)
                    continue
                except Exception as e:
                    logger.error(f"[{call_sid}] Error getting audio chunk: {e}")
                    if stop_event.is_set():
                        break
        
        try:
            # Process audio chunks with the realtime processor
            for result in realtime_processor.process_realtime_session_sync(
                call_sid, get_next_audio_chunk()
            ):
                if stop_event.is_set():
                    break
                    
                ws.send(json.dumps(result))
                
                # If this is a final result, we can reset
                if result.get("type") == "final":
                    audio_chunks = []
        except Exception as e:
            logger.error(f"[{call_sid}] Error processing realtime session: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                ws.send(json.dumps({"type": "error", "message": str(e)}))
            except:
                pass
            finally:
                stop_event.set()
    
    # Start greenlets
    receiver = gevent.spawn(receive_audio)
    processor = gevent.spawn(process_and_send_results)
    
    # Wait for either to finish
    gevent.joinall([receiver, processor], count=1)
    
    # Signal all greenlets to stop
    stop_event.set()
    
    # Wait for cleanup
    gevent.sleep(0.5)
    
    # Kill any remaining greenlets
    if not receiver.dead:
        receiver.kill()
    if not processor.dead:
        processor.kill()
    
    logger.info(f"[{call_sid}] Realtime AI session ended")


@realtime_bp.route("/capabilities", methods=["GET"])
def get_capabilities():
    """
    Get the realtime capabilities of the system.
    
    Returns:
        JSON response with capabilities
    """
    # Get configuration from app config with fallbacks
    openai_model = current_app.config.get('OPENAI_REALTIME_MODEL', "gpt-4o-realtime-preview-2024-10-01") if hasattr(current_app, 'config') else "gpt-4o-realtime-preview-2024-10-01"
    
    # Determine what capabilities are available
    capabilities = {
        "websockets_available": True,
        "realtime_audio": True,
        "speech_to_text": True,
        "text_to_speech": True,
        "model": openai_model,
        "supported_audio_formats": ["g711_ulaw", "pcm16"],
        "supported_sample_rates": [8000, 16000],
        "supported_voices": ["alloy", "nova", "shimmer", "echo", "fable", "onyx"],
        "bidirectional_streaming": True,
        "tool_support": True,
        "messages": {
            "session.update": "Initial configuration",
            "input_audio_buffer.append": "Send audio to model",
            "input_audio_buffer.finalize": "Mark end of audio input",
            "conversation.item.create": "Send text for TTS",
            "response.audio.delta": "Audio response from model",
            "transcript.delta": "Interim transcription",
            "transcript.final": "Final transcription",
            "tool_calls": "Model requests tools",
            "tool_results": "Tool response to model"
        },
        "endpoints": {
            "media": "/ws/media/<call_sid>",
            "realtime": "/ws/realtime",
            "capabilities": "/realtime/capabilities",
            "healthcheck": "/realtime/healthcheck"
        }
    }
    
    return jsonify(capabilities)


@realtime_bp.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Health check endpoint for the realtime service.
    
    Returns:
        JSON response with health status
    """
    # Check if the OpenAI client is available
    openai_status = "ok" if realtime_processor.openai_client else "error"
    
    # Try to import agent components to check if they're available
    agent_status = "unknown"
    try:
        from app.agents.factory_with_orchestration import enhanced_agent_factory
        agent_status = "ok"
    except ImportError:
        agent_status = "error"
    except Exception:
        agent_status = "error"
    
    # Check for tools registry
    tools_status = "unknown"
    try:
        from app.routes.voice.utils.tools_registry import execute_tool
        tools_status = "ok"
    except ImportError:
        tools_status = "error"
    except Exception:
        tools_status = "error"
    
    return jsonify({
        "status": "ok",
        "service": "realtime",
        "openai_status": openai_status,
        "agent_status": agent_status,
        "tools_status": tools_status,
        "websocket_available": True,
        "timestamp": time.time()
    })


# This function has been moved to the top - DELETE THIS COMMENT AFTER MERGING