# app/routes/menu.py
from flask import Blueprint, request, jsonify
from app.utils.menu_utils import write_menu_file, load_menu_data, process_deliverect_menu
import logging
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_validator import validate_and_fix_menu_data

menu_bp = Blueprint('menu', __name__)
logger = logging.getLogger(__name__)


@menu_bp.route('/menu_update', methods=['POST'])
def menu_update():
    data = request.get_json()
    log_info(f"Received menu update data: {data}")
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        # Check if data is coming from Deliverect (has categories structure)
        if "categories" in data:
            # Process data from Deliverect format to our internal format
            log_info("Processing Deliverect menu format")
            processed_data = process_deliverect_menu(data)
        else:
            # Handle direct menu updates (non-Deliverect format)
            log_info("Processing direct menu update")
            # If data is a list, wrap it in a dict for compatible structure
            if isinstance(data, list):
                data = {"items": data}
            elif not isinstance(data, dict):
                return jsonify({"error": "Expected an array or object"}), 400
                
            # Make sure we have the expected structure
            processed_data = data.copy()
            if "items" not in processed_data:
                processed_data["items"] = []
            if "modifiers" not in processed_data:
                processed_data["modifiers"] = []
            if "modifierGroups" not in processed_data:
                processed_data["modifierGroups"] = []
        
        # Validate and fix any issues in the menu data
        validated_data = validate_and_fix_menu_data(processed_data)
        
        # Write the processed menu data to file
        write_menu_file(validated_data)
        load_menu_data(force_refresh=True)  # Refresh the cache with new data
        
        log_info("Menu updated successfully")
        return jsonify({"status": "menu updated"}), 200
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