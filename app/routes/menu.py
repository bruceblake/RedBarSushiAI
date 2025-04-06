# app/routes/menu.py
from flask import Blueprint, request, jsonify
import logging
import json
import os
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_utils import process_deliverect_menu, load_menu_data, write_menu_file, sync_reference_handlers

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
    try:
        import time  # Import here for alt_path creation
        
        # Get JSON data from request
        data = request.get_json()
        if not data:
            logger.error("[MENU-UPDATE] No data provided in request")
            return jsonify({"error": "No data provided"}), 400
            
        # Handle empty arrays or empty objects
        if (isinstance(data, list) and len(data) == 0) or (isinstance(data, dict) and len(data) == 0):
            logger.warning("[MENU-UPDATE] Received empty menu data - creating basic default menu")
            from app.utils.menu_utils import create_default_menu
            data = create_default_menu()
        
        # Handle case where data is a list instead of a dictionary
        if isinstance(data, list):
            logger.info(f"[MENU-UPDATE] Received list data with {len(data)} items")
            
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
                    
                    # Now that name is fixed, add it to valid items
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
        else:
            # Log receipt of dictionary data
            logger.info(f"[MENU-UPDATE] Received menu update. Keys: {list(data.keys())}")
        
        # Process based on format
        try:
            if "categories" in data:
                # Deliverect format
                logger.info(f"[MENU-UPDATE] Processing Deliverect format with {len(data.get('categories', []))} categories")
                processed_data = process_deliverect_menu(data)
                
                # Verify the conversion worked
                if not processed_data.get("items"):
                    logger.warning("[MENU-UPDATE] Processed Deliverect data has no items!")
                    return jsonify({"error": "Failed to extract any items from Deliverect data"}), 400
                    
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
        
        # Save to file
        success = write_menu_file(processed_data)
        if not success:
            logger.error("[MENU-UPDATE] Failed to write menu file, trying alternate location")
            # Try alternative location
            alt_path = f"/tmp/menu_data_{int(time.time())}.json"
            success = write_menu_file(processed_data, alt_path)
            if not success:
                return jsonify({"error": "Failed to write menu file"}), 500
            logger.info(f"[MENU-UPDATE] Wrote menu to alternate location: {alt_path}")
        
        # Verify the menu file was written correctly by forcing a reload
        reloaded_menu = load_menu_data(force_refresh=True)
        if len(reloaded_menu.get("items", [])) == 0:
            logger.warning("[MENU-UPDATE] Menu reload verification failed!")
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
        logger.error(f"[MENU-UPDATE] Error: {e}")
        return jsonify({"error": f"Menu update failed: {str(e)}"}), 500


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
    
    # Load menu data with optional location
    menu_data = load_menu_data(force_refresh=False, location_id=location_id)
    
    # Return menu data
    return jsonify(menu_data), 200
