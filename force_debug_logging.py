#!/usr/bin/env python

import os
import sys
import logging
import shutil

# Function to modify logging configuration in main.py
def enhance_main_logging():
    main_path = "app/main.py"
    backup_path = f"{main_path}.bak"
    
    # Create backup if it doesn't exist
    if not os.path.exists(backup_path):
        shutil.copy2(main_path, backup_path)
        print(f"Created backup of main.py at {backup_path}")
    
    # Read the file content
    try:
        with open(main_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {main_path}")
        return False
    
    # Check if we already enhanced this file
    if "FORCE_DEBUG_LOGGING" in content:
        print("Main.py already has enhanced logging.")
        return True
    
    # Determine where to add our logging configuration
    # Look for imports section or FastAPI app creation
    if "import logging" in content:
        # Add after import logging
        content = content.replace(
            "import logging",
            "import logging\n\n# FORCE_DEBUG_LOGGING - Set all loggers to DEBUG level\nlogging.basicConfig(level=logging.DEBUG)\nlogging.getLogger().setLevel(logging.DEBUG)\nlogging.getLogger('app').setLevel(logging.DEBUG)\nlogging.getLogger('app.utils.realtime_audio_async').setLevel(logging.DEBUG)\nlogging.getLogger('app.api.voice_async').setLevel(logging.DEBUG)\nlogging.getLogger('app.utils.agent_orchestration_async').setLevel(logging.DEBUG)\nlogging.critical('⚠️ FORCED DEBUG LOGGING ENABLED ⚠️')"
        )
    elif "FastAPI(" in content:
        # Add before FastAPI app creation
        content = content.replace(
            "app = FastAPI(",
            "# FORCE_DEBUG_LOGGING - Set all loggers to DEBUG level\nlogging.basicConfig(level=logging.DEBUG)\nlogging.getLogger().setLevel(logging.DEBUG)\nlogging.getLogger('app').setLevel(logging.DEBUG)\nlogging.getLogger('app.utils.realtime_audio_async').setLevel(logging.DEBUG)\nlogging.getLogger('app.api.voice_async').setLevel(logging.DEBUG)\nlogging.getLogger('app.utils.agent_orchestration_async').setLevel(logging.DEBUG)\nlogging.critical('⚠️ FORCED DEBUG LOGGING ENABLED ⚠️')\n\napp = FastAPI("
        )
    else:
        print("Could not find suitable location to add logging configuration in main.py")
        return False
    
    # Write the modified content back to the file
    try:
        with open(main_path, 'w') as f:
            f.write(content)
        print("Successfully enhanced logging in main.py")
        return True
    except Exception as e:
        print(f"Error writing to {main_path}: {e}")
        return False

# Function to add critical logging to OpenAI Realtime client
def enhance_realtime_client():
    client_path = "app/utils/realtime_audio_async.py"
    backup_path = f"{client_path}.bak"
    
    # Create backup if it doesn't exist
    if not os.path.exists(backup_path):
        shutil.copy2(client_path, backup_path)
        print(f"Created backup of realtime_audio_async.py at {backup_path}")
    
    # Read the file content
    try:
        with open(client_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {client_path}")
        return False
    
    # Check if we already enhanced this file
    if "CRITICAL_DEBUG" in content:
        print("Realtime client already has critical logging.")
        return True
    
    # Add critical logging to connect method
    if "async def connect" in content:
        # Find the start of the connect method
        connect_method_start = content.find("async def connect")
        connect_method_body_start = content.find(":", connect_method_start) + 1
        
        # Find the indentation level
        next_line_start = content.find("\n", connect_method_body_start) + 1
        indentation = ""
        for char in content[next_line_start:]:
            if char in " \t":
                indentation += char
            else:
                break
        
        # Create the critical logging statements
        critical_logging = f"\n{indentation}# CRITICAL_DEBUG - Force log connection attempt\n"
        critical_logging += f"{indentation}logger.critical(f\"[{{self.call_sid}}] !!! OpenAIRealtimeClient.connect() ENTERED. API Key configured: {{True if self.api_key else 'NO - THIS IS THE PROBLEM!'}}\")\n"
        
        # Insert right after the method declaration
        content = content[:connect_method_body_start] + critical_logging + content[connect_method_body_start:]
    else:
        print("Could not find connect method in realtime client.")
        return False
    
    # Enhance exception handling in connect method
    if "except websockets.exceptions.InvalidStatusCode as e:" in content:
        content = content.replace(
            "except websockets.exceptions.InvalidStatusCode as e:",
            "except websockets.exceptions.InvalidStatusCode as e:\n"
            f"{indentation}    # CRITICAL_DEBUG - Enhanced error logging\n"
            f"{indentation}    logger.critical(f\"[{{self.call_sid}}] CRITICAL: OpenAI Connect Failed: Invalid status {{e.status_code}}. API Key used: {{True if self.api_key else 'NO KEY'}}\", exc_info=True)"
        )
    
    if "except Exception as e:" in content and "Failed to connect to OpenAI Realtime API" in content:
        content = content.replace(
            "except Exception as e:",
            "except Exception as e:\n"
            f"{indentation}    # CRITICAL_DEBUG - Enhanced error logging\n"
            f"{indentation}    logger.critical(f\"[{{self.call_sid}}] CRITICAL: OpenAI Connect Failed: Generic Exception. API Key used: {{True if self.api_key else 'NO KEY'}}\", exc_info=True)"
        )
    
    # Write the modified content back to the file
    try:
        with open(client_path, 'w') as f:
            f.write(content)
        print("Successfully enhanced logging in realtime_audio_async.py")
        return True
    except Exception as e:
        print(f"Error writing to {client_path}: {e}")
        return False

# Function to enhance voice_async.py
def enhance_voice_async():
    voice_path = "app/api/voice_async.py"
    backup_path = f"{voice_path}.bak"
    
    # Create backup if it doesn't exist
    if not os.path.exists(backup_path):
        shutil.copy2(voice_path, backup_path)
        print(f"Created backup of voice_async.py at {backup_path}")
    
    # Read the file content
    try:
        with open(voice_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {voice_path}")
        return False
    
    # Check if we already enhanced this file
    if "CRITICAL_DEBUG" in content:
        print("Voice async already has critical logging.")
        return True
    
    # Enhance OpenAI connection logging
    if "await openai_client_instance.connect()" in content:
        # Find indentation level
        connect_line = content.find("await openai_client_instance.connect()")
        line_start = content.rfind("\n", 0, connect_line) + 1
        indentation = content[line_start:connect_line]
        
        # Add critical logging before and after connect call
        before_logging = f"{indentation}# CRITICAL_DEBUG - Log before connection attempt\n"
        before_logging += f"{indentation}logger.critical(f\"[{{call_sid}}] WS Handler: !!! ATTEMPTING openai_client_instance.connect(). Client instance: {{openai_client_instance}}\")\n"
        
        content = content.replace(
            f"{indentation}await openai_client_instance.connect()",
            f"{before_logging}{indentation}is_openai_connected = await openai_client_instance.connect()\n"
            f"{indentation}# CRITICAL_DEBUG - Log connection result\n"
            f"{indentation}logger.critical(f\"[{{call_sid}}] WS Handler: !!! RESULT of openai_client_instance.connect(): {{is_openai_connected}}\")\n"
            f"{indentation}if not is_openai_connected:\n"
            f"{indentation}    logger.critical(f\"[{{call_sid}}] WS Handler: !!! OpenAI CONNECTION FAILED - This is where 'couldn\'t connect' message likely originates.\")\n"
        )
    else:
        print("Could not find OpenAI connect call in voice_async.py")
        return False
    
    # Write the modified content back to the file
    try:
        with open(voice_path, 'w') as f:
            f.write(content)
        print("Successfully enhanced logging in voice_async.py")
        return True
    except Exception as e:
        print(f"Error writing to {voice_path}: {e}")
        return False

# Create a settings module to force environment variables
def create_or_update_settings():
    settings_path = "app/force_settings.py"
    
    # Check if the file already exists
    if os.path.exists(settings_path):
        # Read to check if we need to update
        with open(settings_path, 'r') as f:
            content = f.read()
        if "OPENAI_API_KEY" in content:
            print("Settings module already exists with OPENAI_API_KEY.")
            return True
    
    # Create the settings module
    content = """"""
# CRITICAL DEBUGGING - Force environment variables to be set
# This module overrides environment variables in memory for debugging purposes
import os
import logging

# Check if real variables are set
def debug_check_env():
    # Critical variables to check
    critical_vars = ['OPENAI_API_KEY', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']
    missing = [var for var in critical_vars if not os.environ.get(var)]
    
    if missing:
        logger = logging.getLogger(__name__)
        logger.critical(f"⚠️ CRITICAL ENVIRONMENT VARIABLES MISSING: {', '.join(missing)} ⚠️")
        logger.critical("⚠️ Checking for fallback values set in force_settings.py ⚠️")
        
        # Set default values in os.environ only if not already set
        # UNCOMMENT AND REPLACE WITH REAL VALUES WHEN DEBUGGING:
        # if 'OPENAI_API_KEY' in missing and not os.environ.get('OPENAI_API_KEY'):
        #     os.environ['OPENAI_API_KEY'] = 'sk-your-key-here'
        #     logger.critical("⚠️ FORCED OPENAI_API_KEY environment variable ⚠️")
        # 
        # if 'TWILIO_ACCOUNT_SID' in missing and not os.environ.get('TWILIO_ACCOUNT_SID'):
        #     os.environ['TWILIO_ACCOUNT_SID'] = 'AC-your-sid-here'
        #     logger.critical("⚠️ FORCED TWILIO_ACCOUNT_SID environment variable ⚠️")
        # 
        # if 'TWILIO_AUTH_TOKEN' in missing and not os.environ.get('TWILIO_AUTH_TOKEN'):
        #     os.environ['TWILIO_AUTH_TOKEN'] = 'your-auth-token-here'
        #     logger.critical("⚠️ FORCED TWILIO_AUTH_TOKEN environment variable ⚠️")
        # 
        # if 'TWILIO_PHONE_NUMBER' in missing and not os.environ.get('TWILIO_PHONE_NUMBER'):
        #     os.environ['TWILIO_PHONE_NUMBER'] = '+1234567890'
        #     logger.critical("⚠️ FORCED TWILIO_PHONE_NUMBER environment variable ⚠️")
    
    # Check after potential setting
    still_missing = [var for var in critical_vars if not os.environ.get(var)]
    return still_missing

# Run check on import
missing_vars = debug_check_env()
if missing_vars:
    logging.critical(f"⚠️ AFTER FORCE_SETTINGS, STILL MISSING: {', '.join(missing_vars)} ⚠️")
""""""
    
    # Write to file
    try:
        with open(settings_path, 'w') as f:
            f.write(content)
        print(f"Created force_settings.py at {settings_path}")
        return True
    except Exception as e:
        print(f"Error creating {settings_path}: {e}")
        return False

# Add import of force_settings to main.py if not already there
def add_force_settings_import():
    main_path = "app/main.py"
    
    try:
        with open(main_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {main_path}")
        return False
    
    # Check if import already exists
    if "import app.force_settings" in content or "from app import force_settings" in content:
        print("Force settings import already exists in main.py")
        return True
    
    # Add right after imports or at the beginning if no imports
    if "import" in content:
        # Find the last import statement
        import_lines = [line for line in content.split("\n") if line.strip().startswith("import ") or line.strip().startswith("from ")] 
        if import_lines:
            last_import = import_lines[-1]
            content = content.replace(
                last_import,
                f"{last_import}\n\n# CRITICAL_DEBUG - Import forced settings\ntry:\n    import app.force_settings\n    print("✅ Imported force_settings for environment variable checks")\nexcept Exception as e:\n    print(f"❌ Error importing force_settings: {{e}}")"
            )
    else:
        # Add at the beginning
        content = f"# CRITICAL_DEBUG - Import forced settings\ntry:\n    import app.force_settings\n    print("✅ Imported force_settings for environment variable checks")\nexcept Exception as e:\n    print(f"❌ Error importing force_settings: {{e}}")\n\n{content}"
    
    # Write the modified content back to the file
    try:
        with open(main_path, 'w') as f:
            f.write(content)
        print("Successfully added force_settings import to main.py")
        return True
    except Exception as e:
        print(f"Error writing to {main_path}: {e}")
        return False

# Main function
def main():
    print("\033[1;33m======= CRITICAL DEBUGGING ENHANCEMENTS =======\033[0m")
    print("This script will make multiple changes to force detailed logging of OpenAI connection issues.")
    print("\033[1;31mWARNING: This is intended for debugging only. Backups will be created.\033[0m")
    print()
    
    # Execute all enhancement functions
    result1 = enhance_main_logging()
    result2 = enhance_realtime_client()
    result3 = enhance_voice_async()
    result4 = create_or_update_settings()
    result5 = add_force_settings_import()
    
    # Report results
    if all([result1, result2, result3, result4, result5]):
        print("\033[1;32m✅ All critical debugging enhancements completed successfully!\033[0m")
        print("\033[1;33mREMINDER: You must redeploy your application for these changes to take effect.\033[0m")
        print("\033[1;33mTo restore original files:\033[0m")
        print("1. cp app/main.py.bak app/main.py")
        print("2. cp app/utils/realtime_audio_async.py.bak app/utils/realtime_audio_async.py")
        print("3. cp app/api/voice_async.py.bak app/api/voice_async.py")
        print("4. rm app/force_settings.py")
    else:
        print("\033[1;31m❌ Some enhancements failed. See errors above.\033[0m")
        return 1
    
    print("\nNext steps:")
    print("1. Redeploy your application")
    print("2. Make a test call to your Twilio number")
    print("3. Check logs for CRITICAL level messages about OpenAI connection")
    print("4. If you see 'API Key configured: NO' or 'Invalid status 401', update OPENAI_API_KEY in Render dashboard")
    return 0

if __name__ == "__main__":
    sys.exit(main())
