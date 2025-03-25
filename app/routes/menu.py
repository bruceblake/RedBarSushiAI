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
def menu_update():
    """
    Handle menu updates from Deliverect.
    
    Deliverect sends menu updates in their specific format with "categories" structure.
    This endpoint processes the data and stores it in our system.
    """
    try:
        data = request.get_json()
        if not data:
            logger.error("[MENU-UPDATE] No data provided in request")
            return jsonify({"error": "No data provided"}), 400
        
        # Log the receipt of data
        if "categories" in data:
            item_count = len(data.get("categories", []))
            logger.info(f"[MENU-UPDATE] Received update with {item_count} categories")
            
            # Process Deliverect format
            logger.info("[MENU-UPDATE] Processing Deliverect menu format")
            processed_data = process_deliverect_menu(data)
            
            # Log sample of processed items
            if processed_data.get('items'):
                sample_items = processed_data.get('items')[:3]
                for item in sample_items:
                    logger.info(f"[MENU-ITEM] '{item.get('name')}' → '{item.get('reference_handler', '')}'")
                
            # Write to file
            success = write_menu_file(processed_data)
            if not success:
                return jsonify({"error": "Failed to write menu file"}), 500
            
            # Verify menu file was written correctly
            reloaded_menu = load_menu_data(force_refresh=True)
            if not reloaded_menu.get("items") and processed_data.get("items"):
                return jsonify({"error": "Menu update failed - could not verify data was saved"}), 500
                
            logger.info(f"[MENU-UPDATE] Menu updated successfully with {len(reloaded_menu.get('items', []))} items")
            
            # Return success response
            return jsonify({
                "success": True,
                "items": len(processed_data.get("items", [])),
                "modifierGroups": len(processed_data.get("modifierGroups", [])),
                "name_variants": len(processed_data.get("name_variants", {}))
            }), 200
        else:
            # Not Deliverect format
            logger.error("[MENU-UPDATE] Unsupported data format - expecting Deliverect structure with categories")
            return jsonify({"error": "Unsupported format - expecting Deliverect structure"}), 400
            
    except Exception as e:
        logger.error(f"Error updating menu: {e}")
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