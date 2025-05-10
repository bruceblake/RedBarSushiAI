#!/usr/bin/env python

import os
import sys
import shutil

# Define path to the OpenAI Realtime client
REALTIME_CLIENT_PATH = "app/utils/realtime_audio_async.py"
ENHANCED_CLIENT_PATH = "app/utils/enhanced_realtime_audio_async.py"

def enhance_openai_client():
    print("\033[1m===== Enhancing OpenAI Realtime Client =====\033[0m")
    
    # Ensure the enhanced client file exists
    if not os.path.exists(ENHANCED_CLIENT_PATH):
        print("\033[31m❌ Enhanced client file not found at: {ENHANCED_CLIENT_PATH}\033[0m")
        return False
    
    # Backup the original file if not already backed up
    backup_path = f"{REALTIME_CLIENT_PATH}.bak"
    if not os.path.exists(backup_path):
        try:
            shutil.copy2(REALTIME_CLIENT_PATH, backup_path)
            print(f"\033[32m✅ Original client backed up to: {backup_path}\033[0m")
        except Exception as e:
            print(f"\033[31m❌ Failed to backup original client: {str(e)}\033[0m")
            return False
    else:
        print(f"\033[33m⚠️ Backup already exists at: {backup_path}\033[0m")
    
    # Copy the enhanced client to replace the original
    try:
        shutil.copy2(ENHANCED_CLIENT_PATH, REALTIME_CLIENT_PATH)
        print(f"\033[32m✅ Enhanced client successfully installed to: {REALTIME_CLIENT_PATH}\033[0m")
    except Exception as e:
        print(f"\033[31m❌ Failed to install enhanced client: {str(e)}\033[0m")
        return False
    
    print("\033[32m✅ OpenAI Realtime client has been enhanced with detailed logging and error handling.\033[0m")
    print("\033[33m⚠️ To restore the original client, run: cp {backup_path} {REALTIME_CLIENT_PATH}\033[0m")
    
    return True

def add_tracing_to_voice_handler():
    print("\033[1m===== Adding Detailed Tracing to Voice WebSocket Handler =====\033[0m")
    
    voice_handler_path = "app/api/voice_async.py"
    backup_path = f"{voice_handler_path}.bak"
    
    # Backup the original file if not already backed up
    if not os.path.exists(backup_path):
        try:
            shutil.copy2(voice_handler_path, backup_path)
            print(f"\033[32m✅ Original voice handler backed up to: {backup_path}\033[0m")
        except Exception as e:
            print(f"\033[31m❌ Failed to backup original voice handler: {str(e)}\033[0m")
            return False
    else:
        print(f"\033[33m⚠️ Voice handler backup already exists at: {backup_path}\033[0m")
    
    # Read the current content of the file
    try:
        with open(voice_handler_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"\033[31m❌ Failed to read voice handler file: {str(e)}\033[0m")
        return False
    
    # Find key points to enhance with detailed logging
    enhanced = False
    
    # Check if we already enhanced this file
    if "ENHANCED_LOGGING" in content:
        print("\033[33m⚠️ Voice handler appears to already have enhanced logging.\033[0m")
        return True
    
    # Add our custom imports at the top if needed
    if "import traceback" not in content:
        content = content.replace(
            "import logging",
            "import logging\nimport traceback  # ENHANCED_LOGGING"
        )
        enhanced = True
    
    # Add detailed connection logging
    if "openai_client_instance = await" in content:
        content = content.replace(
            "openai_client_instance = await async_agent_orchestrator.realtime_client_manager.get_client(call_sid)",
            "# ENHANCED_LOGGING - Get OpenAI client with detailed tracing\n"
            "        logger.info(f\"[{call_sid}] WS Handler: Getting OpenAI client instance...\")\n"
            "        openai_client_instance = await async_agent_orchestrator.realtime_client_manager.get_client(call_sid)\n"
            "        if not openai_client_instance:\n"
            "            logger.error(f\"[{call_sid}] WS Handler: CRITICAL - OpenAI client instance NOT FOUND for call after initial setup.\")\n"
            "            await websocket.close(code=1011, reason=\"Internal OpenAI client error\")\n"
            "            return\n"
            "        logger.info(f\"[{call_sid}] WS Handler: OpenAI client instance obtained successfully.\")"
        )
        enhanced = True
    
    # Enhance connection logging, ensuring there's a clear log of connection success/failure
    if "await openai_client_instance.connect()" in content:
        content = content.replace(
            "await openai_client_instance.connect()",
            "# ENHANCED_LOGGING - Connect to OpenAI with detailed status\n"
            "        logger.info(f\"[{call_sid}] WS Handler: Attempting to connect to OpenAI Realtime API...\")\n"
            "        is_openai_connected = await openai_client_instance.connect()\n"
            "        if not is_openai_connected:\n"
            "            logger.error(f\"[{call_sid}] WS Handler: FAILED TO CONNECT OpenAIRealtimeClient.\")\n"
            "            # This is likely where the 'couldn\'t connect' message comes from\n"
            "            await websocket.send_text(json.dumps({\n"
            "                \"event\": \"ai_error\", \n"
            "                \"message\": \"Failed to connect to OpenAI speech services after greeting.\"\n"
            "            }))  # Custom event for client handling\n"
            "        else:\n"
            "            logger.info(f\"[{call_sid}] WS Handler: Successfully connected to OpenAI Realtime API.\")"
        )
        enhanced = True
    
    # Enhance websocket closure handling
    if "except WebSocketDisconnect" in content:
        content = content.replace(
            "except WebSocketDisconnect:",
            "except WebSocketDisconnect as e:\n"
            "        # ENHANCED_LOGGING - Detailed WebSocket disconnect tracking\n"
            "        logger.info(f\"[{call_sid}] WS Handler: WebSocket disconnected with code {getattr(e, 'code', 'unknown')}\")\n"
            "        traceback.print_exc()  # ENHANCED_LOGGING"
        )
        enhanced = True
    
    # Enhance exception handling throughout
    if "except Exception as e:" in content:
        content = content.replace(
            "except Exception as e:",
            "except Exception as e:\n"
            "        # ENHANCED_LOGGING - Detailed exception tracking\n"
            "        logger.error(f\"[{call_sid}] WS Handler: Exception in WebSocket handler: {str(e)}\")\n"
            "        traceback.print_exc()  # ENHANCED_LOGGING"
        )
        enhanced = True
    
    # Write back the enhanced content if changes were made
    if enhanced:
        try:
            with open(voice_handler_path, 'w') as f:
                f.write(content)
            print("\033[32m✅ Voice WebSocket handler enhanced with detailed tracing and error handling.\033[0m")
        except Exception as e:
            print(f"\033[31m❌ Failed to write enhanced voice handler: {str(e)}\033[0m")
            return False
    else:
        print("\033[33m⚠️ No changes made to voice handler - it may already have similar enhancements.\033[0m")
    
    return True

if __name__ == "__main__":
    print("\033[1m===== RedBarSushiAI Debugging Enhancement =====\033[0m")
    print("This script will enhance the OpenAI Realtime client and voice handler with detailed logging.")
    
    client_success = enhance_openai_client()
    handler_success = add_tracing_to_voice_handler()
    
    if client_success and handler_success:
        print("\033[32;1m✅ Debugging enhancements completed successfully.\033[0m")
        print("\033[32m   The next call attempt will have much more detailed logging about the OpenAI connection.\033[0m")
    else:
        print("\033[31;1m❌ Some debugging enhancements failed. Check the output above for details.\033[0m")
        sys.exit(1)