# app/routes/menu.py
from flask import Blueprint, request, jsonify
import logging
import json
import os
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_utils import process_deliverect_menu, load_menu_data, write_menu_file, sync_reference_handlers, MENU_FILE_PATH

menu_bp = Blueprint('menu', __name__)
logger = logging.getLogger(__name__)


@menu_bp.route('/menu_update', methods=['POST'])
@menu_bp.route('/update_menu', methods=['POST'])  # Alternative endpoint name
def menu_update():
    """
    Handle menu updates from various formats.
    
    Accepts:
    1. Deliverect format (with "categories")
    2. Our internal format (with "items", "modifiers", "modifierGroups")
    3. Simple list of menu items
    
    Returns:
        JSON response with success status
    """
    # Log the raw request headers to debug issues with Deliverect
    logger.info(f"[MENU-UPDATE] Request headers: {dict(request.headers)}")
    try:
        logger.info(f"[MENU-UPDATE] Request content type: {request.content_type}")
        if request.content_length:
            logger.info(f"[MENU-UPDATE] Content length: {request.content_length}")
    except Exception as e:
        logger.info(f"[MENU-UPDATE] Error logging request info: {e}")
    try:
        import time  # Import here for alt_path creation
        
        # Log the start of request processing
        logger.info(f"[MENU-UPDATE] Processing menu update request from {request.remote_addr}")
        
        # Get content length for logging
        content_length = request.headers.get('Content-Length', 'unknown')
        logger.info(f"[MENU-UPDATE] Request Content-Length: {content_length}")
        
        # Try to get the raw data first for maximum debugging
        try:
            raw_data = request.get_data()
            raw_data_length = len(raw_data)
            logger.info(f"[MENU-UPDATE] Raw data length: {raw_data_length} bytes")
            
            # Log a sample of the raw data for debugging (careful with large data)
            if raw_data_length > 0:
                sample_size = min(200, raw_data_length)
                sample = raw_data[:sample_size]
                try:
                    sample_str = sample.decode('utf-8')
                    logger.info(f"[MENU-UPDATE] Raw data sample: {sample_str}...")
                except:
                    logger.info(f"[MENU-UPDATE] Raw data sample (binary): {sample}...")
        except Exception as raw_e:
            logger.error(f"[MENU-UPDATE] Error getting raw data: {raw_e}")
            
        # Now try to parse as JSON
        try:
            # First try normal JSON parsing
            data = request.get_json(silent=True, force=False)
            
            # If that fails, try with force=True
            if data is None:
                logger.error("[MENU-UPDATE] Failed to parse JSON, trying with force=True")
                data = request.get_json(silent=True, force=True)
                
            # If still no data, try manually parsing the raw data
            if data is None and raw_data_length > 0:
                logger.error("[MENU-UPDATE] Both JSON parsing methods failed, trying manual parsing")
                import json
                try:
                    data = json.loads(raw_data.decode('utf-8'))
                    logger.info("[MENU-UPDATE] Manual JSON parsing succeeded")
                except Exception as manual_e:
                    logger.error(f"[MENU-UPDATE] Manual JSON parsing failed: {manual_e}")
                
            # Check if we got valid data
            if not data:
                logger.error("[MENU-UPDATE] No data provided in request or invalid JSON")
                return jsonify({"error": "No data provided or invalid JSON format"}), 400
                
            # Log data type and size for debugging
            data_type = type(data).__name__
            data_size = len(str(data)) if data else 0
            logger.info(f"[MENU-UPDATE] Got data of type {data_type}, approximate size: {data_size} bytes")
            
            # If it's a dict, log the keys
            if isinstance(data, dict):
                logger.info(f"[MENU-UPDATE] Data keys: {list(data.keys())}")
            # If it's a list, check for special Deliverect format and transform
            elif isinstance(data, list):
                # Check if this is the Deliverect menu in alternative format (list with menu items data)
                if len(data) > 0 and isinstance(data[0], dict):
                    # Check for expected fields in the first item
                    first_item = data[0]
                    if ("availabilities" in first_item or "categories" in first_item or 
                        "modifierGroups" in first_item or "products" in first_item):
                        logger.info("[MENU-UPDATE] Detected Deliverect menu in list format")
                        
                        # First, check if it has "categories" directly (standard Deliverect format)
                        if "categories" in first_item:
                            transformed_data = first_item
                            logger.info(f"[MENU-UPDATE] Using first item in list as main menu: {list(transformed_data.keys())}")
                        # Otherwise, construct a menu structure that uses the list items as products
                        else:
                            # Create a standard format with these list items as products
                            transformed_data = {
                                "items": data,  # Use the entire list as direct menu items
                                "modifiers": [],
                                "modifierGroups": [],
                                "name_variants": {}
                            }
                            logger.info("[MENU-UPDATE] Transformed list to standard menu format")
                        
                        data = transformed_data
                    else:
                        logger.info("[MENU-UPDATE] List format but not recognized as Deliverect menu format")
                
                # Log info about the list (after possible transformation)
                if isinstance(data, list):
                    sample_items = data[:3] if len(data) > 3 else data
                    sample_types = [type(item).__name__ for item in sample_items]
                    logger.info(f"[MENU-UPDATE] Data is a list with {len(data)} items. Sample types: {sample_types}")
            
        except Exception as e:
            logger.error(f"[MENU-UPDATE] JSON parsing error: {str(e)}")
            return jsonify({
                "error": f"Failed to parse JSON: {str(e)}",
                "data_sample": str(raw_data[:200]) if 'raw_data' in locals() else "No sample available"
            }), 400
            
        # Handle empty arrays or empty objects
        if (isinstance(data, list) and len(data) == 0) or (isinstance(data, dict) and len(data) == 0):
            logger.warning("[MENU-UPDATE] Received empty menu data - creating basic default menu")
            from app.utils.menu_utils import create_default_menu
            data = create_default_menu()
        
        # Handle case where data is a list instead of a dictionary
        # Note: we still need this code even though we have transformation above
        # because the transformation may have been skipped if the list didn't match the expected patterns
        if isinstance(data, list):
            logger.info(f"[MENU-UPDATE] Processing list data with {len(data)} items")
            
            # Check for items without names and filter/fix them
            valid_items = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    # If item has no name, try to fix it
                    if not item.get("name"):
                        if item.get("title"):
                            logger.info(f"[MENU-UPDATE] Using 'title' field as name for item {i}")
                            item["name"] = item["title"]
                        elif item.get("product_name"):
                            logger.info(f"[MENU-UPDATE] Using 'product_name' field as name for item {i}")
                            item["name"] = item["product_name"]
                        elif item.get("label"):
                            logger.info(f"[MENU-UPDATE] Using 'label' field as name for item {i}")
                            item["name"] = item["label"]
                        elif item.get("id") or item.get("product_id"):
                            # Generate a name from ID
                            item_id = item.get("id") or item.get("product_id")
                            logger.info(f"[MENU-UPDATE] Using ID to generate name for item {i}: Item {item_id}")
                            item["name"] = f"Item {item_id}"
                        else:
                            # Auto-generate a name from description if available
                            if item.get("description"):
                                desc = item["description"]
                                name = desc.split()[0:2]  # Use first two words of description
                                name = " ".join(name)
                                logger.info(f"[MENU-UPDATE] Using description to generate name for item {i}: {name}")
                                item["name"] = name
                            else:
                                # Last resort: auto-generate a name
                                logger.info(f"[MENU-UPDATE] Auto-generating name for item {i}: Menu Item {i+1}")
                                item["name"] = f"Menu Item {i+1}"
                    
                    # Add required fields if missing
                    if not item.get("reference_handler"):
                        if item.get("plu"):
                            item["reference_handler"] = item["plu"]
                        else:
                            item["reference_handler"] = f"REF-{i:04d}"
                    
                    # Convert price from cents to dollars if needed
                    if "price" in item and isinstance(item["price"], (int, float)) and item["price"] > 100:
                        item["price"] = item["price"] / 100
                    
                    # Now that item is fixed, add it to valid items
                    valid_items.append(item)
                    
            # Log any fixes
            if len(valid_items) < len(data):
                logger.warning(f"[MENU-UPDATE] Filtered out {len(data) - len(valid_items)} invalid items")
                
            # Convert list of valid items to our standard format
            data = {
                "items": valid_items,
                "modifiers": [],
                "modifierGroups": [],
                "name_variants": {}
            }
            
            # Generate name variants for these items
            from app.utils.menu_utils import add_name_variants
            for item in data["items"]:
                try:
                    add_name_variants(item["name"], data["name_variants"])
                except Exception as e:
                    logger.warning(f"[MENU-UPDATE] Error adding name variants for {item.get('name')}: {e}")
                    # Ensure at least the base name is in variants
                    if item.get("name"):
                        data["name_variants"][item["name"].lower()] = item["name"]
        else:
            # Log receipt of dictionary data
            logger.info(f"[MENU-UPDATE] Received menu update. Keys: {list(data.keys())}")
        
        # Process based on format - with chunk processing for large menus
        try:
            if "categories" in data:
                # Deliverect format
                categories_count = len(data.get('categories', []))
                logger.info(f"[MENU-UPDATE] Processing Deliverect format with {categories_count} categories")
                
                # Check if menu is very large (might cause memory issues)
                if categories_count > 30:
                    logger.warning(f"[MENU-UPDATE] Large menu detected with {categories_count} categories - processing with caution")
                
                try:
                    # Log memory usage before processing
                    import resource, gc
                    mem_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    logger.info(f"[MENU-UPDATE] Memory usage before processing: {mem_before/1024:.2f} MB")
                    
                    # Process the menu data
                    processed_data = process_deliverect_menu(data)
                    
                    # Force garbage collection
                    gc.collect()
                    
                    # Log memory after processing
                    mem_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    logger.info(f"[MENU-UPDATE] Memory usage after processing: {mem_after/1024:.2f} MB (change: {(mem_after-mem_before)/1024:.2f} MB)")
                
                except MemoryError:
                    logger.error("[MENU-UPDATE] Memory error processing menu - menu may be too large")
                    return jsonify({"error": "Menu is too large to process with available memory"}), 413
                
                # Verify the conversion worked
                items_count = len(processed_data.get("items", []))
                if items_count == 0:
                    logger.warning("[MENU-UPDATE] Processed Deliverect data has no items!")
                    return jsonify({"error": "Failed to extract any items from Deliverect data"}), 400
                    
                logger.info(f"[MENU-UPDATE] Successfully processed {items_count} items from Deliverect data")
                    
            elif "items" in data:
                # Our internal format
                items = data.get('items', [])
                item_count = len(items)
                logger.info(f"[MENU-UPDATE] Processing internal format with {item_count} items")
                
                # Fix items without names
                fixed_items = []
                for i, item in enumerate(items):
                    if isinstance(item, dict):
                        # If item has no name, try to fix it
                        if not item.get("name"):
                            if item.get("title"):
                                logger.info(f"[MENU-UPDATE] Using 'title' field as name for item {i}")
                                item["name"] = item["title"]
                            elif item.get("product_name"):
                                logger.info(f"[MENU-UPDATE] Using 'product_name' field as name for item {i}")
                                item["name"] = item["product_name"]
                            elif item.get("label"):
                                logger.info(f"[MENU-UPDATE] Using 'label' field as name for item {i}")
                                item["name"] = item["label"]
                            elif item.get("id") or item.get("product_id"):
                                # Generate a name from ID
                                item_id = item.get("id") or item.get("product_id")
                                logger.info(f"[MENU-UPDATE] Using ID to generate name for item {i}: Item {item_id}")
                                item["name"] = f"Item {item_id}"
                            else:
                                # Auto-generate a name from description if available
                                if item.get("description"):
                                    desc = item["description"]
                                    name = desc.split()[0:2]  # Use first two words of description
                                    name = " ".join(name)
                                    logger.info(f"[MENU-UPDATE] Using description to generate name for item {i}: {name}")
                                    item["name"] = name
                                else:
                                    # Last resort: auto-generate a name
                                    logger.info(f"[MENU-UPDATE] Auto-generating name for item {i}: Menu Item {i+1}")
                                    item["name"] = f"Menu Item {i+1}"
                                
                        # Add the fixed item
                        fixed_items.append(item)
                
                # Log fixes
                if len(fixed_items) != item_count:
                    logger.warning(f"[MENU-UPDATE] Fixed or filtered {item_count - len(fixed_items)} invalid items")
                
                # Replace the items in the data
                data["items"] = fixed_items
                processed_data = data.copy()
            else:
                # Unknown format
                logger.error(f"[MENU-UPDATE] Unsupported data format. Keys: {list(data.keys())}")
                return jsonify({
                    "error": "Unsupported format", 
                    "keys": list(data.keys()),
                    "expected": ["categories", "items"]
                }), 400
                
            # Ensure items have required fields
            if "items" in processed_data:
                for i, item in enumerate(processed_data["items"]):
                    if isinstance(item, dict):
                        # Ensure required fields
                        if not item.get("id"):
                            item["id"] = f"auto_{i+1:04d}"
                        if not item.get("reference_handler") and item.get("name"):
                            # Generate a simple reference code from name
                            name = item.get("name", "item").upper()
                            item["reference_handler"] = ''.join(c for c in name if c.isalpha())[:10]
                        # Ensure availability flags
                        if "snoozed" not in item:
                            item["snoozed"] = False
                        if "available" not in item:
                            item["available"] = True
        except Exception as format_error:
            logger.error(f"[MENU-UPDATE] Error processing data format: {format_error}")
            return jsonify({"error": f"Data processing error: {str(format_error)}"}), 400
        
        # Ensure all expected structures exist
        if "items" not in processed_data:
            processed_data["items"] = []
        if "modifiers" not in processed_data:
            processed_data["modifiers"] = []
        if "modifierGroups" not in processed_data:
            processed_data["modifierGroups"] = []
        if "name_variants" not in processed_data:
            processed_data["name_variants"] = {}
        
        # Generate name variants if missing
        try:
            if processed_data.get("items") and not processed_data.get("name_variants", {}):
                logger.info("[MENU-UPDATE] Generating missing name variants")
                processed_data["name_variants"] = {}
                
                for item in processed_data["items"]:
                    if isinstance(item, dict) and item.get("name"):
                        try:
                            add_name_variants(item["name"], processed_data["name_variants"])
                        except Exception as e:
                            logger.warning(f"[MENU-UPDATE] Error adding variants for {item.get('name')}: {e}")
                            # At minimum, add the base name itself as a variant
                            processed_data["name_variants"][item["name"].lower()] = item["name"]
        except Exception as e:
            logger.error(f"[MENU-UPDATE] Error generating name variants: {e}")
            # Create a basic name variants dictionary as fallback
            if processed_data.get("items"):
                processed_data["name_variants"] = {
                    item.get("name", "").lower(): item.get("name", "") 
                    for item in processed_data["items"]
                    if isinstance(item, dict) and item.get("name")
                }
        
        # Validate and fix menu data
        try:
            processed_data = validate_and_fix_menu_data(processed_data)
            logger.info("[MENU-UPDATE] Menu data validated and fixed")
        except ValueError as ve:
            # This is a critical validation error that must be returned to the caller
            error_msg = str(ve)
            logger.error(f"[MENU-UPDATE] Critical validation error: {error_msg}")
            return jsonify({"error": error_msg}), 400
        except Exception as ve:
            logger.warning(f"[MENU-UPDATE] Validation warning: {ve}")
            # Continue with unvalidated data rather than failing
        
        # Log stats about the processed menu
        logger.info(f"[MENU-UPDATE] Final menu has {len(processed_data.get('items', []))} items, " +
                   f"{len(processed_data.get('modifiers', []))} modifiers, " +
                   f"{len(processed_data.get('modifierGroups', []))} modifier groups")
        
        # Save to file - try multiple paths
        production_path = '/home/pegasus/mysite/RedBarSushiAI/menu_data.json'
        paths_to_try = [
            production_path,  # Try production path first
            MENU_FILE_PATH,   # Then try the configured path
            os.path.join(os.getcwd(), 'menu_data.json'),  # Try current directory
            f"/tmp/menu_data_{int(time.time())}.json"  # Fallback to tmp
        ]
        
        # Calculate item count for logging
        item_count = len(processed_data.get("items", []))
        logger.info(f"[MENU-UPDATE] Preparing to save menu with {item_count} items")
        
        # Log a few sample items
        sample_items = processed_data.get("items", [])[:3]
        for i, item in enumerate(sample_items):
            logger.info(f"[MENU-UPDATE] Sample item {i+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}")
        
        # Make sure we don't have duplicate references
        reference_counts = {}
        for item in processed_data.get("items", []):
            ref = item.get("reference_handler", "")
            if ref:
                reference_counts[ref] = reference_counts.get(ref, 0) + 1
        
        # Log duplicate references
        duplicates = [ref for ref, count in reference_counts.items() if count > 1]
        if duplicates:
            logger.warning(f"[MENU-UPDATE] Found {len(duplicates)} duplicate reference handlers: {duplicates[:5]}")
        
        # Try to write to each path
        success = False
        for path in paths_to_try:
            logger.info(f"[MENU-UPDATE] Attempting to write menu to: {path}")
            try:
                # Get directory
                directory = os.path.dirname(path)
                
                # Try to create directory if needed
                if directory and not os.path.exists(directory):
                    try:
                        os.makedirs(directory, exist_ok=True)
                        logger.info(f"[MENU-UPDATE] Created directory: {directory}")
                    except Exception as mkdir_err:
                        logger.error(f"[MENU-UPDATE] Failed to create directory {directory}: {mkdir_err}")
                        continue
                
                # Check write permissions
                if directory and not os.access(directory, os.W_OK):
                    logger.error(f"[MENU-UPDATE] No write permissions for directory: {directory}")
                    continue
                
                # Try to write file
                if write_menu_file(processed_data, path):
                    success = True
                    logger.info(f"[MENU-UPDATE] Successfully wrote menu to: {path}")
                    break
            except Exception as path_err:
                logger.error(f"[MENU-UPDATE] Error writing to {path}: {path_err}")
        
        if not success:
            logger.error("[MENU-UPDATE] Failed to write menu file to any location")
            return jsonify({"error": "Failed to write menu file"}), 500
        
        # Verify the menu file was written correctly by forcing a reload
        reloaded_menu = load_menu_data(force_refresh=True)
        if len(reloaded_menu.get("items", [])) == 0:
            logger.warning("[MENU-UPDATE] Menu reload verification failed!")
            return jsonify({"error": "Menu reload verification failed - menu has 0 items"}), 500
        
        # Log the actual items in the reloaded menu for debugging
        logger.info(f"[MENU-UPDATE] Reloaded menu has {len(reloaded_menu.get('items', []))} items")
        for idx, item in enumerate(reloaded_menu.get("items", [])[:5]):  # Log first 5 items
            logger.info(f"[MENU-UPDATE] Reloaded item {idx+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}")
        else:
            logger.info(f"[MENU-UPDATE] Menu reload verification confirmed {len(reloaded_menu['items'])} items")
        
        # Return success response with stats
        return jsonify({
            "success": True,
            "items": len(processed_data.get("items", [])),
            "modifiers": len(processed_data.get("modifiers", [])),
            "modifierGroups": len(processed_data.get("modifierGroups", [])),
            "name_variants": len(processed_data.get("name_variants", {}))
        }), 200
            
    except Exception as e:
        import traceback
        logger.error(f"[MENU-UPDATE] Error: {e}")
        logger.error(f"[MENU-UPDATE] Traceback: {traceback.format_exc()}")
        
        # Try to handle memory errors specially
        error_str = str(e).lower()
        if "memory" in error_str or "allocation" in error_str:
            return jsonify({
                "error": "Menu update failed due to memory limitations. Try a smaller menu or contact support.",
                "details": str(e)
            }), 413  # Request Entity Too Large
        
        # For all other errors
        return jsonify({
            "error": "Menu update failed. See server logs for details.",
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
