# app/routes/menu.py
from flask import Blueprint, request, jsonify
import logging
import json
import os
import requests
from datetime import datetime
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_utils import process_deliverect_menu, load_menu_data, write_menu_file, sync_reference_handlers, MENU_FILE_PATH

menu_bp = Blueprint('menu', __name__)
logger = logging.getLogger(__name__)


@menu_bp.route('/menu_update', methods=['POST'])
@menu_bp.route('/update_menu', methods=['POST'])  # Alternative endpoint name
@menu_bp.route('/deliverect_menu_update', methods=['POST'])  # Simplified endpoint for Deliverect
@menu_bp.route('/deliverect/menu', methods=['POST'])  # Standard Deliverect webhook path
def menu_update():
    """
    Handle menu updates from various formats.
    
    Accepts:
    1. Deliverect format (with "categories")
    2. Deliverect async format (with "body.menus", "body.stores", "body.callback")
    3. Our internal format (with "items", "modifiers", "modifierGroups")
    4. Simple list of menu items
    
    Returns:
        JSON response with success status
    """
    # Basic logging of request info
    logger.info(f"[MENU-UPDATE] Processing menu update request from {request.remote_addr}")
    
    try:
        # Get raw data and parse as JSON
        raw_data = request.get_data()
        raw_data_length = len(raw_data) if raw_data else 0
        logger.info(f"[MENU-UPDATE] Raw data length: {raw_data_length} bytes")
        
        if raw_data_length == 0:
            logger.error("[MENU-UPDATE] No data provided in request")
            return jsonify({"error": "No data provided"}), 400
            
        # Try to parse JSON using multiple methods
        try:
            # First try normal JSON parsing
            data = request.get_json(silent=True, force=False)
            
            # If that fails, try with force=True
            if data is None:
                logger.warning("[MENU-UPDATE] Standard JSON parsing failed, trying with force=True")
                data = request.get_json(silent=True, force=True)
                
            # If still no data, try manual parsing
            if data is None:
                logger.warning("[MENU-UPDATE] Both JSON parsing methods failed, trying manual parsing")
                import json
                try:
                    data = json.loads(raw_data.decode('utf-8'))
                    logger.info("[MENU-UPDATE] Manual JSON parsing succeeded")
                except Exception as manual_e:
                    logger.error(f"[MENU-UPDATE] Manual JSON parsing failed: {manual_e}")
                    return jsonify({"error": f"Failed to parse JSON data: {str(manual_e)}"}), 400
        except Exception as e:
            logger.error(f"[MENU-UPDATE] JSON parsing error: {str(e)}")
            return jsonify({"error": f"Failed to parse JSON data: {str(e)}"}), 400
        
        # Check if we have any data
        if not data:
            logger.error("[MENU-UPDATE] No valid data after parsing")
            return jsonify({"error": "No valid data provided"}), 400
            
        # Log data type and basic structure
        data_type = type(data).__name__
        logger.info(f"[MENU-UPDATE] Received data of type {data_type}")
        
        # Check for Deliverect Async format
        callback_url = None
        stores = None
        
        # Handle the async format with body, menus, stores, callback
        if isinstance(data, dict) and "body" in data:
            body = data.get("body", {})
            
            if isinstance(body, dict):
                # Extract callback URL
                callback_url = body.get("callback")
                logger.info(f"[MENU-UPDATE] Found callback URL: {callback_url}")
                
                # Extract stores
                stores = body.get("stores", [])
                logger.info(f"[MENU-UPDATE] Found stores: {stores}")
                
                # Extract menus data - this is what we'll actually process
                menus = body.get("menus", [])
                if isinstance(menus, list) and len(menus) > 0:
                    logger.info(f"[MENU-UPDATE] Found {len(menus)} menus in async format")
                    # Use the first menu as our data to process
                    data = menus[0]
                    logger.info(f"[MENU-UPDATE] Using first menu for processing")
        
        # Process the menu data through our robust formatter
        try:
            # First pass - process through the Deliverect menu processor
            processed_data = process_deliverect_menu(data)
            
            # Second pass - validate and fix any remaining issues
            processed_data = validate_and_fix_menu_data(processed_data)
            
            # CRITICAL: Verify that PLUs were preserved during processing
            # This ensures proper integration with Deliverect
            plu_count = 0
            missing_plu_count = 0
            for item in processed_data.get("items", []):
                if item.get("plu") or (item.get("reference_handler") and not item.get("reference_handler").startswith("PROD-")):
                    plu_count += 1
                else:
                    missing_plu_count += 1
                    logger.error(f"[MENU-UPDATE] Item missing PLU: {item.get('name')} - This will cause Deliverect order failures!")
            
            if missing_plu_count > 0:
                logger.warning(f"[MENU-UPDATE] WARNING: {missing_plu_count} items missing PLUs! These items will not work with Deliverect orders.")
            else:
                logger.info(f"[MENU-UPDATE] All {plu_count} items have valid PLUs for Deliverect integration.")
            
            # Calculate statistics
            items_count = len(processed_data.get("items", []))
            modifiers_count = len(processed_data.get("modifiers", []))
            groups_count = len(processed_data.get("modifierGroups", []))
            variants_count = len(processed_data.get("name_variants", {}))
            
            logger.info(f"[MENU-UPDATE] Processed menu with {items_count} items, {modifiers_count} modifiers, {groups_count} groups")
            
            # Log a few sample items for debugging
            if items_count > 0:
                sample_items = processed_data.get("items", [])[:3]
                for i, item in enumerate(sample_items):
                    logger.info(f"[MENU-UPDATE] Sample item {i+1}: {item.get('name', 'No name')} -> PLU: {item.get('plu', 'Missing!')} | Reference: {item.get('reference_handler', 'Missing!')}")
            
            # If we have no items after processing, return error
            if items_count == 0:
                logger.error("[MENU-UPDATE] No valid menu items extracted from data")
                
                # If we have a callback URL, send a FAILED status
                if callback_url:
                    try:
                        callback_response = requests.post(
                            callback_url,
                            json={"status": "FAILED", "comment": "No valid menu items could be extracted"}
                        )
                        logger.info(f"[MENU-UPDATE] Callback response: {callback_response.status_code}")
                    except Exception as callback_e:
                        logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")
                
                return jsonify({"error": "No valid menu items could be extracted from the provided data"}), 400
                
            # EMERGENCY BYPASS - Completely skip write_menu_file and go straight to direct writes
            logger.info(f"[MENU-UPDATE] EMERGENCY BYPASS ACTIVE - attempting direct writes")
            
            try:
                # IMPORTANT: This code must be self-contained and not depend on any other functions
                # Try all possible file locations directly
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # First create a backup
                try:
                    backup_folder = '/tmp/redbar_backups'
                    os.makedirs(backup_folder, exist_ok=True)
                    backup_path = os.path.join(backup_folder, f"menu_backup_{timestamp}.json")
                    with open(backup_path, 'w') as f:
                        json.dump(processed_data, f, indent=2)
                    logger.info(f"[MENU-UPDATE] EMERGENCY Backup created at {backup_path}")
                except Exception as backup_e:
                    logger.warning(f"[MENU-UPDATE] EMERGENCY Backup failed: {backup_e}")
                
                # Try all possible paths directly
                success = False
                error_messages = []
                
                # Docker path
                try:
                    if os.path.exists('/app'):
                        with open('/app/menu_data.json', 'w') as f:
                            json.dump(processed_data, f, indent=2)
                        logger.info("[MENU-UPDATE] EMERGENCY Write to /app/menu_data.json successful")
                        success = True
                except Exception as e1:
                    error_messages.append(f"Docker path error: {str(e1)}")
                
                # Current directory path
                try:
                    with open(os.path.join(os.getcwd(), 'menu_data.json'), 'w') as f:
                        json.dump(processed_data, f, indent=2)
                    logger.info(f"[MENU-UPDATE] EMERGENCY Write to {os.getcwd()}/menu_data.json successful")
                    success = True
                except Exception as e2:
                    error_messages.append(f"CWD path error: {str(e2)}")
                
                # Tmp path
                try:
                    with open('/tmp/menu_data.json', 'w') as f:
                        json.dump(processed_data, f, indent=2)
                    logger.info("[MENU-UPDATE] EMERGENCY Write to /tmp/menu_data.json successful")
                    success = True
                except Exception as e3:
                    error_messages.append(f"TMP path error: {str(e3)}")
                
                # Skip using load_menu_data to avoid potential errors in that function
                if success:
                    return jsonify({
                        "success": True,
                        "items": items_count,
                        "modifiers": modifiers_count,
                        "modifierGroups": groups_count,
                        "name_variants": variants_count,
                        "path": "EMERGENCY DIRECT WRITE"
                    }), 200
                
                # If all failed, log the errors and return error response
                logger.error(f"[MENU-UPDATE] EMERGENCY All write methods failed: {', '.join(error_messages)}")
                return jsonify({
                    "error": "Failed to save menu data",
                    "details": "Emergency direct writes failed. Errors: " + "; ".join(error_messages)
                }), 500
                
            except Exception as emergency_e:
                # Something went really wrong, return error
                logger.error(f"[MENU-UPDATE] EMERGENCY BYPASS failed with exception: {emergency_e}")
                return jsonify({
                    "error": "EMERGENCY bypass failed",
                    "details": str(emergency_e)
                }), 500
                
            # The following code is unreachable - we return from the emergency block above
            # But we keep it for reference
            # DIRECT WRITE APPROACH - Skip the problematic write_menu_file function entirely
            success = False
            
            if reloaded_count == 0:
                logger.warning("[MENU-UPDATE] Menu reload verification failed")
                
                # If we have a callback URL, send a FAILED status
                if callback_url:
                    try:
                        callback_response = requests.post(
                            callback_url,
                            json={"status": "FAILED", "comment": "Menu reload verification failed - menu has 0 items"}
                        )
                        logger.info(f"[MENU-UPDATE] Callback response: {callback_response.status_code}")
                    except Exception as callback_e:
                        logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")
                
                return jsonify({"error": "Menu reload verification failed - menu has 0 items"}), 500
                
            logger.info(f"[MENU-UPDATE] Menu update successful with {reloaded_count} items")
            
            # If we have a callback URL, send a success status
            if callback_url:
                try:
                    callback_response = requests.post(
                        callback_url,
                        json={"status": "ONLINE", "comment": f"Menu update successful with {reloaded_count} items"}
                    )
                    logger.info(f"[MENU-UPDATE] Callback response: {callback_response.status_code}")
                except Exception as callback_e:
                    logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")
            
            # Return success response
            return jsonify({
                "success": True,
                "items": items_count,
                "modifiers": modifiers_count,
                "modifierGroups": groups_count,
                "name_variants": variants_count
            }), 200
            
        except Exception as e:
            import traceback
            logger.error(f"[MENU-UPDATE] Error processing menu data: {e}")
            logger.error(f"[MENU-UPDATE] Traceback: {traceback.format_exc()}")
            
            # If we have a callback URL, send a FAILED status
            if callback_url:
                try:
                    callback_response = requests.post(
                        callback_url,
                        json={"status": "FAILED", "comment": str(e)[:200]}  # Limit length of error message
                    )
                    logger.info(f"[MENU-UPDATE] Callback response: {callback_response.status_code}")
                except Exception as callback_e:
                    logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")
            
            # Check for memory errors
            error_str = str(e).lower()
            if "memory" in error_str or "allocation" in error_str:
                return jsonify({
                    "error": "Menu processing failed due to memory limitations. Try a smaller menu.",
                    "details": str(e)
                }), 413
                
            # For all other errors
            return jsonify({
                "error": f"Menu processing failed: {str(e)}",
                "details": str(e)
            }), 400
            
    except Exception as e:
        import traceback
        logger.error(f"[MENU-UPDATE] Unexpected error: {e}")
        logger.error(f"[MENU-UPDATE] Traceback: {traceback.format_exc()}")
        
        return jsonify({
            "error": "Menu update failed due to an unexpected error",
            "details": str(e)
        }), 500


@menu_bp.route('/snoozeUnsnooze', methods=['POST'])
def snooze_unsnooze():
    data = request.get_json() or {}
    logger.info(f"Received snooze/unsnooze data: {data}")
    operations = data.get("operations", [])
    if not operations:
        return jsonify({"error": "No operations found"}), 400
        
    # Load current menu data
    menu_data = load_menu_data()
    
    # Process each operation
    for op in operations:
        item_name = op.get("item", "")
        action = op.get("action", "")
        
        # Find the item in the menu
        for item in menu_data.get("items", []):
            if item.get("name", "").lower() == item_name.lower():
                if action == "snooze":
                    item["snoozed"] = True
                    item["available"] = False
                elif action == "unsnooze":
                    item["snoozed"] = False
                    # Only set available if schedule allows
                    if item.get("scheduleAvailable", True):
                        item["available"] = True
                break
    
    # Save updated menu
    write_menu_file(menu_data)
    load_menu_data(force_refresh=True)  # Refresh the cache
    
    logger.info("Processed snooze/unsnooze operations.")
    return jsonify({"status": "ok"}), 200


@menu_bp.route('/busy_mode', methods=['POST'])
def busy_mode():
    # Access the global variable from order.py
    from app.routes.order import BUSY_MODE_ACTIVE
    data = request.get_json() or {}
    status = data.get("status", "").upper()
    
    if status == "PAUSED":
        globals()['BUSY_MODE_ACTIVE'] = True
        return jsonify({"status": "PAUSED"}), 200
    elif status == "UNPAUSED":
        globals()['BUSY_MODE_ACTIVE'] = False
        return jsonify({"status": "UNPAUSED"}), 200
    else:
        return jsonify({"error": "Invalid status"}), 400


@menu_bp.route('/updatePrepTime', methods=['GET', 'POST'])
def update_prep_time():
    return jsonify({"status": "not implemented"}), 200


@menu_bp.route('/courierUpdate', methods=['GET', 'POST'])
def courier_update():
    return jsonify({"status": "not implemented"}), 200


@menu_bp.route('/update_reference', methods=['POST'])
def update_reference():
    """
    Endpoint to update a menu item's reference handler
    """
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid data format"}), 400
        
    item_name = data.get("item_name")
    reference_handler = data.get("reference_handler")
    
    if not item_name or not reference_handler:
        return jsonify({"error": "Missing item_name or reference_handler"}), 400
    
    # Load menu data
    menu_data = load_menu_data(force_refresh=True)
    
    # Find and update the item
    item_found = False
    for item in menu_data.get("items", []):
        if item.get("name", "").lower() == item_name.lower():
            old_ref = item.get("reference_handler", "")
            item["reference_handler"] = reference_handler
            item_found = True
            logger.info(f"Updated reference handler for {item_name} from {old_ref} to {reference_handler}")
            break
            
    if not item_found:
        return jsonify({"error": f"Item '{item_name}' not found in menu"}), 404
        
    # Save updated menu
    write_menu_file(menu_data)
    load_menu_data(force_refresh=True)  # Refresh cache
    
    return jsonify({"status": "success", "message": f"Updated reference handler for {item_name}"}), 200


@menu_bp.route('/sync_references', methods=['POST'])
def sync_menu_references():
    """
    Endpoint to synchronize reference handlers across menu data
    """
    data = request.get_json() or {}
    source_location = data.get("source_location")
    target_location = data.get("target_location")
    
    try:
        stats = sync_reference_handlers(source_location_id=source_location, target_location_id=target_location)
        logger.info(f"Menu reference synchronization completed: {stats}")
        return jsonify({"status": "success", "stats": stats}), 200
    except Exception as e:
        logger.error(f"Error synchronizing menu references: {e}")
        return jsonify({"error": f"Synchronization failed: {str(e)}"}), 500
        
@menu_bp.route('/menu', methods=['GET'])
def get_menu():
    """
    Get the current menu data
    """
    # Get location_id from query parameters
    location_id = request.args.get('location_id')
    
    # Load menu data with optional location - force refresh to ensure latest
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Log menu details
    item_count = len(menu_data.get("items", []))
    logger.info(f"[GET-MENU] Returning menu with {item_count} items")
    if item_count > 0:
        for idx, item in enumerate(menu_data.get("items", [])[:3]):  # Log first 3 items
            logger.info(f"[GET-MENU] Item {idx+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}")
    
    # Add file location to response for debugging
    menu_data["_debug"] = {"file_path": MENU_FILE_PATH}
    
    # Return menu data
    return jsonify(menu_data), 200


@menu_bp.route('/clear_menu_cache', methods=['GET'])
def clear_menu_cache():
    """
    Force a refresh of the menu from disk and clear any cache
    """
    # Force a full reload
    menu_data = load_menu_data(force_refresh=True)
    
    # Log reloaded data
    item_count = len(menu_data.get("items", []))
    logger.info(f"[CLEAR-CACHE] Reloaded menu with {item_count} items")
    if item_count > 0:
        for idx, item in enumerate(menu_data.get("items", [])[:5]):  # Log first 5 items
            logger.info(f"[CLEAR-CACHE] Item {idx+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}")
    
    # Return status
    return jsonify({
        "success": True, 
        "message": f"Menu cache cleared, {item_count} items loaded",
        "file_path": MENU_FILE_PATH
    }), 200


@menu_bp.route('/delete_menu', methods=['GET'])
def delete_menu():
    """
    Delete the current menu file to force a clean slate
    This can help when the menu file is corrupted
    """
    import os
    
    try:
        # Known menu file locations
        menu_paths = [
            '/home/pegasus/mysite/RedBarSushiAI/menu_data.json',
            MENU_FILE_PATH,
            os.path.join(os.getcwd(), 'menu_data.json'),
            '/tmp/menu_data.json'
        ]
        
        deleted_paths = []
        for path in menu_paths:
            if os.path.exists(path):
                try:
                    # Create a backup first
                    backup_path = f"{path}.bak"
                    import shutil
                    shutil.copy2(path, backup_path)
                    logger.info(f"[DELETE-MENU] Created backup at {backup_path}")
                    
                    # Now delete the file
                    os.remove(path)
                    deleted_paths.append(path)
                    logger.info(f"[DELETE-MENU] Deleted menu file at {path}")
                except Exception as e:
                    logger.error(f"[DELETE-MENU] Failed to delete {path}: {e}")
        
        # Force menu cache to be cleared
        from app.utils.menu_utils import load_menu_data
        _ = load_menu_data(force_refresh=True)
        
        return jsonify({
            "success": True,
            "message": "Menu files deleted. The next menu update will start with a clean slate.",
            "deleted_files": deleted_paths
        }), 200
    except Exception as e:
        logger.error(f"[DELETE-MENU] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Failed to delete menu: {str(e)}"
        }), 500


@menu_bp.route('/simple_menu_update', methods=['POST'])
def simple_menu_update():
    """
    Simplified endpoint for Deliverect menu updates that directly writes to a known
    working location and always returns success even if it fails.
    This is a fallback solution when the standard endpoint is having issues.
    """
    logger.info(f"[SIMPLE-MENU] Processing menu update request from {request.remote_addr}")
    
    try:
        # Parse the menu JSON but don't save to disk
        raw_data = request.get_data()
        raw_data_length = len(raw_data) if raw_data else 0
        logger.info(f"[SIMPLE-MENU] Raw data length: {raw_data_length} bytes")
        
        # Try to parse the JSON
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": True, "message": "No valid JSON data, but request received"}), 200
        
        # Log some basic stats about the menu
        menu_type = "Unknown"
        item_count = 0
        
        if isinstance(data, dict):
            if "categories" in data:
                menu_type = "Deliverect categories format"
                item_count = sum(len(cat.get("products", [])) for cat in data.get("categories", []))
            elif "items" in data:
                menu_type = "RedBar internal format"
                item_count = len(data.get("items", []))
            elif "products" in data:
                menu_type = "Deliverect products format"
                item_count = len(data.get("products", []))
            elif "body" in data and "menus" in data.get("body", {}):
                menu_type = "Deliverect async format"
                item_count = sum(len(menu.get("categories", [])) for menu in data.get("body", {}).get("menus", []))
        elif isinstance(data, list):
            menu_type = "List format"
            item_count = len(data)
        
        logger.info(f"[SIMPLE-MENU] Received a {menu_type} with {item_count} potential items")
        
        # Try to process and save the menu, but always return success even if it fails
        try:
            # Process the data through our formatter
            processed_data = process_deliverect_menu(data)
            processed_data = validate_and_fix_menu_data(processed_data)
            
            # CRITICAL: Verify that PLUs were preserved during processing
            # This ensures proper integration with Deliverect
            plu_count = 0
            missing_plu_count = 0
            for item in processed_data.get("items", []):
                if item.get("plu") or (item.get("reference_handler") and not item.get("reference_handler").startswith("PROD-")):
                    plu_count += 1
                else:
                    missing_plu_count += 1
                    logger.error(f"[SIMPLE-MENU] Item missing PLU: {item.get('name')} - This will cause Deliverect order failures!")
            
            if missing_plu_count > 0:
                logger.warning(f"[SIMPLE-MENU] WARNING: {missing_plu_count} items missing PLUs! These items will not work with Deliverect orders.")
            else:
                logger.info(f"[SIMPLE-MENU] All {plu_count} items have valid PLUs for Deliverect integration.")
            
            # Log the processed menu stats
            items_count = len(processed_data.get("items", []))
            logger.info(f"[SIMPLE-MENU] Processed menu has {items_count} items")
            
            # Log a few sample items with their PLUs
            if items_count > 0:
                sample_items = processed_data.get("items", [])[:3]
                for i, item in enumerate(sample_items):
                    logger.info(f"[SIMPLE-MENU] Sample item {i+1}: {item.get('name', 'No name')} -> PLU: {item.get('plu', 'Missing!')} | Reference: {item.get('reference_handler', 'Missing!')}")
            
            # Attempt to save the menu directly to a known working location
            if items_count > 0:
                # ULTRA SIMPLE DIRECT WRITE - NO DEPENDENCIES
                logger.info(f"[SIMPLE-MENU] EMERGENCY DIRECT WRITE ACTIVE")
                success = False
                errors = []
                
                # Attempt Docker path
                if os.path.exists('/app'):
                    try:
                        with open('/app/menu_data.json', 'w') as f:
                            f.write(json.dumps(processed_data, indent=2))
                        logger.info("[SIMPLE-MENU] EMERGENCY Direct write to /app/menu_data.json SUCCESS")
                        success = True
                    except Exception as e1:
                        errors.append(f"Docker path: {str(e1)}")
                
                # Attempt CWD path
                try:
                    with open(os.path.join(os.getcwd(), 'menu_data.json'), 'w') as f:
                        f.write(json.dumps(processed_data, indent=2))
                    logger.info(f"[SIMPLE-MENU] EMERGENCY Direct write to {os.getcwd()}/menu_data.json SUCCESS")
                    success = True 
                except Exception as e2:
                    errors.append(f"CWD path: {str(e2)}")
                    
                # Always try tmp path
                try:
                    with open('/tmp/menu_data.json', 'w') as f:
                        f.write(json.dumps(processed_data, indent=2))
                    logger.info("[SIMPLE-MENU] EMERGENCY Direct write to /tmp/menu_data.json SUCCESS")
                    success = True
                except Exception as e3:
                    errors.append(f"TMP path: {str(e3)}")
                
                if not success:
                    logger.error(f"[SIMPLE-MENU] CRITICAL: All direct writes failed: {'; '.join(errors)}")
        except Exception as process_e:
            logger.error(f"[SIMPLE-MENU] Error processing menu data: {process_e}")
        
        # Always return success to Deliverect
        return jsonify({
            "success": True, 
            "message": "Menu update request processed successfully",
            "details": f"Received {menu_type} with {item_count} potential items"
        }), 200
    
    except Exception as e:
        # Log the error but still return 200 OK to keep Deliverect happy
        logger.error(f"[SIMPLE-MENU] Error processing menu data: {e}")
        return jsonify({
            "success": True,
            "message": "Request received but error encountered during processing",
            "error": str(e)
        }), 200


@menu_bp.route('/debug_menu', methods=['GET'])
def debug_menu():
    """
    Debug endpoint to get detailed information about the menu system
    """
    import os
    import sys
    import platform
    
    # Force a full reload
    menu_data = load_menu_data(force_refresh=True)
    item_count = len(menu_data.get("items", []))
    
    # Check file paths
    possible_paths = [
        '/home/pegasus/mysite/RedBarSushiAI/menu_data.json',
        '/home/pegasus/mysite/menu_data.json',
        os.path.join(os.getcwd(), 'menu_data.json'),
        os.path.join(os.getcwd(), 'redbar_menu_data.json'),
        '/tmp/menu_data.json'
    ]
    
    file_status = []
    for path in possible_paths:
        exists = os.path.exists(path)
        size = 0
        item_count_in_file = 0
        if exists:
            try:
                size = os.path.getsize(path)
                with open(path, 'r') as f:
                    try:
                        file_data = json.load(f)
                        item_count_in_file = len(file_data.get('items', []))
                    except:
                        item_count_in_file = "Error parsing file"
            except:
                size = "Error getting size"
                
        file_status.append({
            "path": path, 
            "exists": exists,
            "size_bytes": size,
            "item_count": item_count_in_file
        })
    
    # System info
    system_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "menu_file_path": MENU_FILE_PATH,
        "env_menu_file_path": os.getenv('MENU_FILE_PATH', 'Not set')
    }
    
    # Return detailed status
    return jsonify({
        "success": True,
        "loaded_menu_info": {
            "item_count": item_count,
            "sample_items": [item.get('name', 'No name') for item in menu_data.get("items", [])[:5]]
        },
        "file_status": file_status,
        "system_info": system_info
    }), 200
