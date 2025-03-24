# app/routes/menu.py
from flask import Blueprint, request, jsonify
import logging
import json
from app.utils.helpers import log_info, commit_with_retry
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_utils import process_deliverect_menu, load_menu_data, write_menu_file, sync_reference_handlers

menu_bp = Blueprint('menu', __name__)
logger = logging.getLogger(__name__)


@menu_bp.route('/menu_update', methods=['POST'])
def menu_update():
    """
    Handle menu updates from Deliverect or direct API calls.
    
    Deliverect sends menu updates in their specific format with "categories" structure.
    We process this into our internal format while preserving all PLU/reference_handlers exactly.
    """
    try:
        data = request.get_json()
        if not data:
            logger.error("[MENU-UPDATE] No data provided in request")
            return jsonify({"error": "No data provided"}), 400
        
        # Create a backup of the current menu before updating
        try:
            # Load current menu
            current_menu = load_menu_data(force_refresh=True, skip_validation=True)
            
            # Get file path
            from app.config import MENU_FILE_PATH
            import os
            from datetime import datetime
            
            # Generate backup filename with timestamp
            backup_dir = os.path.dirname(MENU_FILE_PATH)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"menu_backup_{timestamp}.json")
            
            # Write backup
            with open(backup_file, "w") as f:
                json.dump(current_menu, f)
                
            logger.info(f"[MENU-BACKUP] Created menu backup at {backup_file}")
        except Exception as backup_err:
            logger.warning(f"[MENU-BACKUP] Failed to create backup: {backup_err}")
        
        # Log the receipt of data - but be careful with potentially large payloads
        item_count = len(data.get("categories", [])) if "categories" in data else "N/A"
        logger.info(f"[MENU-UPDATE] Received update with {item_count} categories")
        
        # Process based on source format
        if "categories" in data:
            # Deliverect format
            logger.info("[MENU-UPDATE] Processing Deliverect menu format")
            processed_data = process_deliverect_menu(data)
            logger.info(f"[MENU-UPDATE] Processed {len(processed_data.get('items', []))} items from Deliverect")
            
            # Log PLU mapping for the first few items
            sample_items = processed_data.get('items', [])[:5]
            for item in sample_items:
                logger.info(f"[MENU-PLU] '{item.get('name')}' → '{item.get('reference_handler', '')}'")
        else:
            # Direct format
            logger.info("[MENU-UPDATE] Processing direct menu update")
            
            # Handle different input structures
            if isinstance(data, list):
                data = {"items": data}
            elif not isinstance(data, dict):
                logger.error("[MENU-UPDATE] Invalid data format - expected JSON object or array")
                return jsonify({"error": "Expected an array or object"}), 400
            
            # Ensure complete structure
            processed_data = data.copy()
            for key in ["items", "modifiers", "modifierGroups"]:
                if key not in processed_data:
                    processed_data[key] = []
        
        # Verify we have items to process
        if len(processed_data.get("items", [])) == 0:
            logger.error("[MENU-UPDATE] No items found in processed data")
            return jsonify({"error": "No menu items found in data"}), 400
        
        # Verify all items have required fields before validation
        items_missing_fields = [
            item.get("name", "(unnamed)") 
            for item in processed_data.get("items", [])
            if not item.get("name") or not item.get("reference_handler")
        ]
        
        if items_missing_fields:
            logger.warning(f"[MENU-UPDATE] {len(items_missing_fields)} items missing required fields: {items_missing_fields[:5]}")
        
        # Validate and fix menu data
        validated_data = validate_and_fix_menu_data(processed_data)
        
        # Verify validation worked properly - all items should have required fields
        validation_failed = False
        for item in validated_data.get("items", []):
            if not item.get("name") or not item.get("reference_handler") or "price" not in item:
                logger.error(f"[MENU-VALIDATION-FAIL] Item validation failed: {item}")
                validation_failed = True
                
        if validation_failed:
            logger.error("[MENU-UPDATE] Validation failed to fix all items")
            return jsonify({"error": "Menu validation failed - some items are missing required fields"}), 400
        
        # Process menu data to generate name variants for voice matching
        # This ensures that even if menu items change, we can still match against common variants
        
        # Make a fake Deliverect format if it didn't come from Deliverect
        # This ensures consistent processing of all menu updates
        if "categories" not in data:
            # Structure it like Deliverect data
            deliverect_format = {
                "categories": []
            }
            
            # Group items by category
            categories = {}
            for item in validated_data.get("items", []):
                category = item.get("category", "Uncategorized")
                if category not in categories:
                    categories[category] = {
                        "id": f"CAT-{len(categories)+1:03d}",
                        "name": category,
                        "products": []
                    }
                
                # Add this item as a product
                categories[category]["products"].append({
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "price": int(float(item.get("price", 0)) * 100),  # Convert to cents
                    "description": item.get("description", ""),
                    "plu": item.get("reference_handler", ""),
                    "available": item.get("available", True),
                    "imageUrl": item.get("imageUrl", "")
                })
            
            # Add all categories to the result
            deliverect_format["categories"] = list(categories.values())
            
            # Process like it came from Deliverect
            logger.info("[MENU-UPDATE] Converting standard menu to Deliverect format for processing")
            processed_data = process_deliverect_menu(deliverect_format)
        else:
            # We already processed it as Deliverect data, keep the result
            processed_data = validated_data
            
        # Ensure name variants were generated
        if "name_variants" not in processed_data and len(processed_data.get("items", [])) > 0:
            logger.warning("[MENU-UPDATE] Name variants not generated, generating manually")
            
            # Add name variants manually
            name_variants = {}
            for item in processed_data.get("items", []):
                name = item.get("name", "")
                if name:
                    name_lower = name.lower()
                    # Base name
                    name_variants[name_lower] = name
                    
                    # Generate word variants
                    words = name_lower.split()
                    for word in words:
                        if len(word) > 3 and word not in ["with", "and", "the", "for"]:
                            name_variants[word] = name
            
            # Add to processed data
            processed_data["name_variants"] = name_variants
            logger.info(f"[MENU-UPDATE] Generated {len(name_variants)} name variants")
        
        # Log summary of processed data
        logger.info(f"[MENU-UPDATE] Validated data: {len(processed_data.get('items', []))} items, " +
                    f"{len(processed_data.get('modifierGroups', []))} modifier groups, " +
                    f"{len(processed_data.get('name_variants', {}))} name variants")
        
        # Write to file and refresh cache
        write_menu_file(processed_data)
        
        # Verify menu file was written correctly by reloading it
        reloaded_menu = load_menu_data(force_refresh=True)
        if len(reloaded_menu.get("items", [])) == 0 and len(processed_data.get("items", [])) > 0:
            logger.error("[MENU-UPDATE] Menu file writing failed - reloaded menu has 0 items")
            return jsonify({"error": "Menu update failed - could not verify menu data was saved correctly"}), 500
            
        logger.info(f"[MENU-UPDATE] Menu updated successfully with {len(reloaded_menu.get('items', []))} items")
        return jsonify({
            "success": True, 
            "items": len(processed_data.get("items", [])),
            "modifierGroups": len(processed_data.get("modifierGroups", [])),
            "name_variants": len(processed_data.get("name_variants", {}))
        }), 200
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