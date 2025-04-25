# app/routes/menu.py
from flask import Blueprint, request, jsonify
import logging
import json
import os
import requests
import importlib
from datetime import datetime

# app.utils.helpers is imported by other modules
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_utils import (
    load_menu_data,
    write_menu_file,
    sync_reference_handlers,
    MENU_FILE_PATH,
    USE_REDBAR_MENU,
)
from app.utils.deliverect import process_deliverect_menu

menu_bp = Blueprint("menu", __name__)
logger = logging.getLogger(__name__)


@menu_bp.route("/menu_update", methods=["POST"])
@menu_bp.route("/update_menu", methods=["POST"])  # Alternative endpoint name
@menu_bp.route(
    "/deliverect_menu_update", methods=["POST"]
)  # Simplified endpoint for Deliverect
@menu_bp.route("/deliverect/menu", methods=["POST"])  # Standard Deliverect webhook path
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
    # Enhanced logging with more details
    user_agent = request.headers.get("User-Agent", "Unknown")
    content_type = request.headers.get("Content-Type", "Unknown")
    logger.info(
        f"[MENU-UPDATE] Processing menu update request from {request.remote_addr}"
    )
    logger.info(f"[MENU-UPDATE] User-Agent: {user_agent}")
    logger.info(f"[MENU-UPDATE] Content-Type: {content_type}")

    # Check if this is a likely Deliverect update (based on headers or IP)
    is_deliverect = (
        "Deliverect" in user_agent
        or "deliverect" in request.url.lower()
        or content_type.startswith("application/json")
    )
    logger.info(f"[MENU-UPDATE] Is Deliverect update: {is_deliverect}")

    # Skip backup creation - all updates go to the main menu file
    import os
    import json

    try:
        # Just load the current menu data to ensure we have it in memory
        current_menu = load_menu_data(force_refresh=True)
        logger.info(
            f"[MENU-UPDATE] Loaded current menu with {len(current_menu.get('items', []))} items"
        )
    except Exception as load_e:
        logger.warning(f"[MENU-UPDATE] Failed to load current menu: {load_e}")

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
                logger.warning(
                    "[MENU-UPDATE] Standard JSON parsing failed, trying with force=True"
                )
                data = request.get_json(silent=True, force=True)

            # If still no data, try manual parsing
            if data is None:
                logger.warning(
                    "[MENU-UPDATE] Both JSON parsing methods failed, trying manual parsing"
                )
                import json

                try:
                    data = json.loads(raw_data.decode("utf-8"))
                    logger.info("[MENU-UPDATE] Manual JSON parsing succeeded")
                except Exception as manual_e:
                    logger.error(
                        f"[MENU-UPDATE] Manual JSON parsing failed: {manual_e}"
                    )
                    return (
                        jsonify(
                            {"error": f"Failed to parse JSON data: {str(manual_e)}"}
                        ),
                        400,
                    )
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

        # For debugging, log some structure info
        if isinstance(data, dict):
            logger.info(f"[MENU-UPDATE] Top-level keys: {list(data.keys())}")
            # Log some sub-structure details
            for key in data.keys():
                if isinstance(data[key], dict):
                    logger.info(
                        f"[MENU-UPDATE] {key} contains keys: {list(data[key].keys())}"
                    )
                elif isinstance(data[key], list) and len(data[key]) > 0:
                    logger.info(
                        f"[MENU-UPDATE] {key} is a list with {len(data[key])} items"
                    )
                    if isinstance(data[key][0], dict):
                        logger.info(
                            f"[MENU-UPDATE] First item in {key} has keys: {list(data[key][0].keys())}"
                        )
        elif isinstance(data, list) and len(data) > 0:
            logger.info(f"[MENU-UPDATE] Data is a list with {len(data)} items")
            if isinstance(data[0], dict):
                logger.info(
                    f"[MENU-UPDATE] First item has keys: {list(data[0].keys())}"
                )

        # The Deliverect menu processor now handles the event format extraction
        # But we'll keep this code for backward compatibility
        if (
            isinstance(data, dict)
            and "type" in data
            and "data" in data
            and isinstance(data["data"], dict)
            and "menu" in data["data"]
        ):
            logger.info("[MENU-UPDATE] Found Deliverect standard event format")
            # Extract the menu data from the event
            data = data["data"]["menu"]
            logger.info("[MENU-UPDATE] Extracted menu data from event")

        # Check for Deliverect Async format with body.menus structure
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
                    logger.info(
                        f"[MENU-UPDATE] Found {len(menus)} menus in async format"
                    )
                    # Use the first menu as our data to process
                    data = menus[0]
                    logger.info("[MENU-UPDATE] Using first menu for processing")

        # Process the menu data through our robust formatter
        try:
            # Check data integrity before processing
            if is_deliverect:
                logger.info("[MENU-UPDATE] Processing Deliverect format menu data")
                # Log the structure of the data to help debug
                if isinstance(data, dict):
                    top_level_keys = list(data.keys())
                    logger.info(
                        f"[MENU-UPDATE] Top-level keys in data: {top_level_keys}"
                    )

                    # Check for Deliverect-specific structures
                    if "categories" in data:
                        logger.info(
                            f"[MENU-UPDATE] Found standard Deliverect format with categories: {len(data.get('categories', []))}"
                        )
                    elif "products" in data:
                        logger.info(
                            f"[MENU-UPDATE] Found Deliverect product format: {len(data.get('products', []))} products"
                        )
                    elif "channels" in data:
                        logger.info(
                            f"[MENU-UPDATE] Found Deliverect channel format: {len(data.get('channels', []))}"
                        )
                elif isinstance(data, list):
                    logger.info(
                        f"[MENU-UPDATE] Received array data with {len(data)} elements"
                    )

                # Safety check if data is empty or appears invalid from Deliverect
                if not data or (
                    isinstance(data, dict)
                    and not any(
                        key in data
                        for key in ["categories", "products", "channels", "items"]
                    )
                ):
                    logger.error("[MENU-UPDATE] Empty or invalid data from Deliverect")
                    return (
                        jsonify(
                            {"error": "Empty or invalid menu data from Deliverect"}
                        ),
                        400,
                    )

            # First pass - process through the Deliverect menu processor
            logger.info("[MENU-UPDATE] Running data through Deliverect processor")
            processed_data = process_deliverect_menu(data)

            # Check if processed data has items after Deliverect processing
            if not processed_data.get("items"):
                logger.error(
                    "[MENU-UPDATE] No items after Deliverect processing - this indicates a format problem"
                )

                # If this is from Deliverect and processing failed, don't proceed
                if is_deliverect:
                    return (
                        jsonify(
                            {
                                "error": "Failed to process Deliverect menu data - no items found"
                            }
                        ),
                        400,
                    )

            # Second pass - validate and fix any remaining issues
            logger.info("[MENU-UPDATE] Validating and fixing menu data")
            processed_data = validate_and_fix_menu_data(processed_data)

            # CRITICAL: Verify that PLUs were preserved during processing
            # This ensures proper integration with Deliverect
            plu_count = 0
            missing_plu_count = 0
            for item in processed_data.get("items", []):
                if item.get("plu") or (
                    item.get("reference_handler")
                    and not item.get("reference_handler").startswith("PROD-")
                ):
                    plu_count += 1
                else:
                    missing_plu_count += 1
                    logger.error(
                        f"[MENU-UPDATE] Item missing PLU: {item.get('name')} - This will cause Deliverect order failures!"
                    )

            if missing_plu_count > 0:
                logger.warning(
                    f"[MENU-UPDATE] WARNING: {missing_plu_count} items missing PLUs! These items will not work with Deliverect orders."
                )
            else:
                logger.info(
                    f"[MENU-UPDATE] All {plu_count} items have valid PLUs for Deliverect integration."
                )

            # Calculate statistics
            items_count = len(processed_data.get("items", []))
            modifiers_count = len(processed_data.get("modifiers", []))
            groups_count = len(processed_data.get("modifierGroups", []))

            # Remove name_variants field if it exists - AI agent will handle matching
            if "name_variants" in processed_data:
                logger.info(
                    "[MENU-UPDATE] Removing name_variants field - AI agent will handle matching"
                )
                processed_data.pop("name_variants", None)

            logger.info(
                f"[MENU-UPDATE] Processed menu with {items_count} items, {modifiers_count} modifiers, {groups_count} groups"
            )

            # Log a few sample items for debugging
            if items_count > 0:
                sample_items = processed_data.get("items", [])[:3]
                for i, item in enumerate(sample_items):
                    logger.info(
                        f"[MENU-UPDATE] Sample item {i+1}: {item.get('name', 'No name')} -> PLU: {item.get('plu', 'Missing!')} | Reference: {item.get('reference_handler', 'Missing!')}"
                    )

            # If we have no items after processing, this is a serious problem if from Deliverect
            if items_count == 0:
                logger.warning("[MENU-UPDATE] No menu items extracted from data")

                # For Deliverect updates, this is a fatal error - reject the update
                if is_deliverect:
                    logger.error("[MENU-UPDATE] Rejecting empty Deliverect menu update")
                    # If we have a callback URL, send a FAILED status
                    if callback_url:
                        try:
                            callback_response = requests.post(
                                callback_url,
                                json={
                                    "status": "FAILED",
                                    "comment": "Empty menu data - no items found",
                                },
                            )
                            logger.info(
                                f"[MENU-UPDATE] Callback response: {callback_response.status_code}"
                            )
                        except Exception as callback_e:
                            logger.error(
                                f"[MENU-UPDATE] Error sending callback: {callback_e}"
                            )
                    return (
                        jsonify(
                            {
                                "error": "No menu items found in Deliverect data. Update rejected to prevent data loss."
                            }
                        ),
                        400,
                    )

                # For other formats, log a warning but continue
                logger.warning(
                    "[MENU-UPDATE] Continuing with empty update for non-Deliverect request"
                )

            # Save the processed menu
            # Using datetime from imported module
            import os

            # Skip creating a separate backup file - we'll write directly to the main menu file
            logger.info(
                f"[MENU-UPDATE] Proceeding to write menu directly to main file without backup"
            )

            # Retain important data from current menu if this is a partial update
            if is_deliverect and current_menu and isinstance(current_menu, dict):
                # Check if we need to preserve some data from the current menu
                current_items_count = len(current_menu.get("items", []))
                logger.info(
                    f"[MENU-UPDATE] Current menu has {current_items_count} items"
                )

                # Don't allow drastic reduction in menu size for Deliverect updates
                # This prevents accidental data loss due to partial updates
                if (
                    current_items_count > 0
                    and items_count > 0
                    and items_count < current_items_count * 0.5
                ):
                    # This is a suspiciously small update compared to current menu
                    logger.warning(
                        f"[MENU-UPDATE] Potential partial update detected: {items_count} items vs {current_items_count} current items"
                    )

                    # Check if this is likely a single category update rather than full menu
                    processed_categories = set(
                        item.get("category", "")
                        for item in processed_data.get("items", [])
                    )
                    current_categories = set(
                        item.get("category", "")
                        for item in current_menu.get("items", [])
                    )

                    # If we have fewer categories than current menu, it's likely a partial update
                    if len(processed_categories) < len(current_categories) * 0.5:
                        logger.warning(
                            f"[MENU-UPDATE] This appears to be a partial category update. Categories: {processed_categories}"
                        )

                        # In this case, we'll need to merge this data with existing menu
                        # Rather than completely replacing the menu

                        # Strategy: Remove items in these categories from current menu
                        # and add the new items from processed_data
                        updated_items = []
                        # First add items from current menu that aren't in updated categories
                        for item in current_menu.get("items", []):
                            if item.get("category", "") not in processed_categories:
                                updated_items.append(item)

                        # Then add all items from the processed data (the new updates)
                        updated_items.extend(processed_data.get("items", []))

                        # Update processed_data with merged items
                        processed_data["items"] = updated_items
                        logger.info(
                            f"[MENU-UPDATE] Merged menu now has {len(updated_items)} items"
                        )

                # Remove name_variants field if it exists - AI agent will handle matching
                if "name_variants" in processed_data:
                    logger.info(
                        "[MENU-UPDATE] Removing name_variants field - AI agent will handle matching"
                    )
                    processed_data.pop("name_variants", None)
                if "name_variants" in current_menu:
                    logger.info(
                        "[MENU-UPDATE] Current menu has name_variants but we're removing it - AI agent will handle matching"
                    )

            # Detailed logging before attempting to write
            logger.info(
                f"[MENU-UPDATE] About to write menu with {len(processed_data.get('items', []))} items, {len(processed_data.get('modifiers', []))} modifiers, {len(processed_data.get('modifierGroups', []))} groups"
            )

            # Use the standard write_menu_file function to write the menu data
            if write_menu_file(processed_data):
                logger.info(
                    "[MENU-UPDATE] Successfully wrote menu using write_menu_file"
                )
                # Write was successful
            else:
                logger.error("[MENU-UPDATE] Failed to write menu using write_menu_file")

                # If we have a callback URL, send a FAILED status
                if callback_url:
                    try:
                        callback_response = requests.post(
                            callback_url,
                            json={
                                "status": "FAILED",
                                "comment": "Failed to save menu data",
                            },
                        )
                        logger.info(
                            f"[MENU-UPDATE] Callback response: {callback_response.status_code}"
                        )
                    except Exception as callback_e:
                        logger.error(
                            f"[MENU-UPDATE] Error sending callback: {callback_e}"
                        )

                # Return error if write_menu_file failed
                return (
                    jsonify(
                        {
                            "error": "Failed to save menu data",
                            "details": "The menu was processed successfully but could not be saved.",
                        }
                    ),
                    500,
                )

            # Verify the menu was saved correctly
            reloaded_menu = load_menu_data(force_refresh=True)
            reloaded_count = len(reloaded_menu.get("items", []))
            # No need to check name_variants - AI agent will handle matching

            if reloaded_count == 0:
                logger.warning(
                    "[MENU-UPDATE] Menu reload verification failed - no items found"
                )

                # This is a critical error - try to write the processed data again
                try:
                    logger.info(
                        "[MENU-UPDATE] Attempting to write processed data again"
                    )
                    # Write directly to the file as a last resort
                    with open(MENU_FILE_PATH, "w") as f:
                        json.dump(processed_data, f, indent=2)
                    logger.info(f"[MENU-UPDATE] Wrote directly to {MENU_FILE_PATH}")

                    # Reload one more time to confirm
                    restored_menu = load_menu_data(force_refresh=True)
                    restored_count = len(restored_menu.get("items", []))
                    logger.info(
                        f"[MENU-UPDATE] After direct write, menu has {restored_count} items"
                    )
                except Exception as write_e:
                    logger.error(
                        f"[MENU-UPDATE] Failed to write menu data directly: {write_e}"
                    )

                # If we have a callback URL, send a FAILED status
                if callback_url:
                    try:
                        callback_response = requests.post(
                            callback_url,
                            json={
                                "status": "FAILED",
                                "comment": "Menu reload verification failed - menu has 0 items",
                            },
                        )
                        logger.info(
                            f"[MENU-UPDATE] Callback response: {callback_response.status_code}"
                        )
                    except Exception as callback_e:
                        logger.error(
                            f"[MENU-UPDATE] Error sending callback: {callback_e}"
                        )

                return (
                    jsonify(
                        {
                            "error": "Menu reload verification failed - menu has 0 items",
                            "details": "Attempted direct write to menu file, check logs for details",
                        }
                    ),
                    500,
                )

            logger.info(
                f"[MENU-UPDATE] Menu update successful with {reloaded_count} items"
            )

            # If we have a callback URL, send a success status
            if callback_url:
                try:
                    callback_response = requests.post(
                        callback_url,
                        json={
                            "status": "ONLINE",
                            "comment": f"Menu update successful with {reloaded_count} items",
                        },
                    )
                    logger.info(
                        f"[MENU-UPDATE] Callback response: {callback_response.status_code}"
                    )
                except Exception as callback_e:
                    logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")

            # Remove name_variants field if it exists - AI agent will handle matching
            if "name_variants" in processed_data:
                logger.info(
                    "[MENU-UPDATE] Removing name_variants field - AI agent will handle matching"
                )
                processed_data.pop("name_variants", None)

            # No name variants generation needed - AI agent will handle menu item matching
            logger.info(
                "[MENU-UPDATE] No name variants needed - AI agent will handle menu item matching"
            )

            # Return success response
            return (
                jsonify(
                    {
                        "success": True,
                        "items": len(processed_data.get("items", [])),
                        "modifiers": len(processed_data.get("modifiers", [])),
                        "modifierGroups": len(processed_data.get("modifierGroups", [])),
                        "ai_matching": True,  # Indicate that AI agent will handle matching
                        "source": "deliverect" if is_deliverect else "custom",
                        "menu_file_path": MENU_FILE_PATH,
                    }
                ),
                200,
            )

        except Exception as e:
            import traceback

            logger.error(f"[MENU-UPDATE] Error processing menu data: {e}")
            logger.error(f"[MENU-UPDATE] Traceback: {traceback.format_exc()}")

            # If we have a callback URL, send a FAILED status
            if callback_url:
                try:
                    callback_response = requests.post(
                        callback_url,
                        json={
                            "status": "FAILED",
                            "comment": str(e)[:200],
                        },  # Limit length of error message
                    )
                    logger.info(
                        f"[MENU-UPDATE] Callback response: {callback_response.status_code}"
                    )
                except Exception as callback_e:
                    logger.error(f"[MENU-UPDATE] Error sending callback: {callback_e}")

            # Check for memory errors
            error_str = str(e).lower()
            if "memory" in error_str or "allocation" in error_str:
                return (
                    jsonify(
                        {
                            "error": "Menu processing failed due to memory limitations. Try a smaller menu.",
                            "details": str(e),
                        }
                    ),
                    413,
                )

            # For all other errors
            return (
                jsonify(
                    {"error": f"Menu processing failed: {str(e)}", "details": str(e)}
                ),
                400,
            )

    except Exception as e:
        import traceback

        logger.error(f"[MENU-UPDATE] Unexpected error: {e}")
        logger.error(f"[MENU-UPDATE] Traceback: {traceback.format_exc()}")

        return (
            jsonify(
                {
                    "error": "Menu update failed due to an unexpected error",
                    "details": str(e),
                }
            ),
            500,
        )


@menu_bp.route("/snoozeUnsnooze", methods=["POST"])
def snooze_unsnooze():
    """
    Handle snooze/unsnooze operations from Deliverect.

    Deliverect webhooks can be received in two formats:
    1. Legacy format with {"operations": [{item, action}]}
    2. Deliverect format with allSnoozedItems (PLU-based) and operations

    Returns:
        JSON response with success status
    """
    data = request.get_json() or {}
    logger.info(f"Received snooze/unsnooze data: {data}")

    # Detect format - check if this is Deliverect format (PLU-based)
    is_deliverect_format = "allSnoozedItems" in data or (
        isinstance(data.get("operations", []), list)
        and all(
            isinstance(op, dict) and "plu" in op for op in data.get("operations", [])
        )
    )

    logger.info("Processing Deliverect format snooze/unsnooze webhook")
    return _process_deliverect_snooze_unsnooze(data)


def _process_deliverect_snooze_unsnooze(data):
    """Process a Deliverect-format snooze/unsnooze webhook."""
    # Load current menu data
    menu_data = load_menu_data()

    # Keep track of changes for logging
    snooze_count = 0
    unsnooze_count = 0

    # Process allSnoozedItems if present (full sync)
    if "allSnoozedItems" in data and isinstance(data["allSnoozedItems"], list):
        snoozed_plus = set(data["allSnoozedItems"])

        # First reset all items to available
        for item in menu_data.get("items", []):
            # If PLU is in the snoozed list, snooze it
            if (
                item.get("plu") in snoozed_plus
                or item.get("reference_handler") in snoozed_plus
            ):
                item["snoozed"] = True
                item["available"] = False
                snooze_count += 1
            else:
                # Not in the snooze list, so unsnooze it
                item["snoozed"] = False
                # Only set available if schedule allows
                if item.get("scheduleAvailable", True):
                    item["available"] = True
                    unsnooze_count += 1

        logger.info(
            f"Processed allSnoozedItems: {snooze_count} snoozed, {unsnooze_count} unsnoozed"
        )

    # Process individual operations
    operations = data.get("operations", [])
    if operations:
        for op in operations:
            plu = op.get("plu", "")
            action = op.get("action", "").lower()  # 'snooze' or 'unsnooze'

            if not plu or not action:
                logger.warning(f"Skipping invalid operation: {op}")
                continue

            # Find the item by PLU
            found = False
            for item in menu_data.get("items", []):
                if item.get("plu") == plu or item.get("reference_handler") == plu:
                    if action == "snooze":
                        item["snoozed"] = True
                        item["available"] = False
                        snooze_count += 1
                    elif action == "unsnooze":
                        item["snoozed"] = False
                        # Only set available if schedule allows
                        if item.get("scheduleAvailable", True):
                            item["available"] = True
                            unsnooze_count += 1
                    found = True
                    break

            if not found:
                logger.warning(f"Item with PLU {plu} not found for {action} operation")

    # Save updated menu
    write_menu_file(menu_data)
    # Refresh the cache to load new data
    from flask import current_app, has_app_context

    if has_app_context() and not current_app.config.get("TESTING", False):
        load_menu_data(force_refresh=True)

    logger.info(
        f"Processed snooze/unsnooze operations: {snooze_count} snoozed, {unsnooze_count} unsnoozed"
    )
    return (
        jsonify(
            {"status": "success", "snoozed": snooze_count, "unsnoozed": unsnooze_count}
        ),
        200,
    )


@menu_bp.route("/busy_mode", methods=["POST"])
def busy_mode():
    # Access the global variable from order.py - import once at the top
    import app.routes.order

    data = request.get_json() or {}
    status = data.get("status", "").upper()

    if status == "PAUSED":
        app.routes.order.BUSY_MODE_ACTIVE = True
        return jsonify({"status": "PAUSED"}), 200
    elif status == "UNPAUSED":
        app.routes.order.BUSY_MODE_ACTIVE = False
        return jsonify({"status": "UNPAUSED"}), 200
    else:
        return jsonify({"error": "Invalid status"}), 400


@menu_bp.route("/updatePrepTime", methods=["GET", "POST"])
def update_prep_time():
    return jsonify({"status": "not implemented"}), 200


@menu_bp.route("/courierUpdate", methods=["GET", "POST"])
def courier_update():
    return jsonify({"status": "not implemented"}), 200


@menu_bp.route("/update_reference", methods=["POST"])
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
            logger.info(
                f"Updated reference handler for {item_name} from {old_ref} to {reference_handler}"
            )
            break

    if not item_found:
        return jsonify({"error": f"Item '{item_name}' not found in menu"}), 404

    # Save updated menu
    write_menu_file(menu_data)
    load_menu_data(force_refresh=True)  # Refresh cache

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Updated reference handler for {item_name}",
            }
        ),
        200,
    )


@menu_bp.route("/sync_references", methods=["POST"])
def sync_menu_references():
    """
    Endpoint to synchronize reference handlers across menu data
    """
    data = request.get_json() or {}
    source_location = data.get("source_location")
    target_location = data.get("target_location")

    try:
        stats = sync_reference_handlers(
            source_location_id=source_location, target_location_id=target_location
        )
        logger.info(f"Menu reference synchronization completed: {stats}")
        return jsonify({"status": "success", "stats": stats}), 200
    except Exception as e:
        logger.error(f"Error synchronizing menu references: {e}")
        return jsonify({"error": f"Synchronization failed: {str(e)}"}), 500


@menu_bp.route("/menu", methods=["GET"])
def get_menu():
    """
    Get the current menu data
    """
    # Get location_id from query parameters
    location_id = request.args.get("location_id")

    # Load menu data with optional location - force refresh to ensure latest
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)

    # Log menu details
    item_count = len(menu_data.get("items", []))
    logger.info(f"[GET-MENU] Returning menu with {item_count} items")
    if item_count > 0:
        for idx, item in enumerate(menu_data.get("items", [])[:3]):  # Log first 3 items
            logger.info(
                f"[GET-MENU] Item {idx+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}"
            )

    # Remove name_variants if it exists - AI agent will handle matching
    if "name_variants" in menu_data:
        logger.info(
            "[GET-MENU] Removing name_variants field - AI agent will handle matching"
        )
        menu_data.pop("name_variants", None)

    # Add file location to response for debugging
    menu_data["_debug"] = {"file_path": MENU_FILE_PATH}
    menu_data["ai_matching"] = True  # Indicate that AI agent will handle matching

    # Return menu data
    return jsonify(menu_data), 200


@menu_bp.route("/clear_menu_cache", methods=["GET"])
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
            logger.info(
                f"[CLEAR-CACHE] Item {idx+1}: {item.get('name', 'No name')} -> {item.get('reference_handler', 'No ref')}"
            )

    # Return status
    return (
        jsonify(
            {
                "success": True,
                "message": f"Menu cache cleared, {item_count} items loaded",
                "file_path": MENU_FILE_PATH,
            }
        ),
        200,
    )


@menu_bp.route("/delete_menu", methods=["GET"])
def delete_menu():
    """
    Delete the current menu file to force a clean slate
    This can help when the menu file is corrupted
    """
    import os

    try:
        # Known menu file locations
        menu_paths = [
            "/home/pegasus/mysite/RedBarSushiAI/menu_data.json",
            MENU_FILE_PATH,
            os.path.join(os.getcwd(), "menu_data.json"),
            "/tmp/menu_data.json",
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

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Menu files deleted. The next menu update will start with a clean slate.",
                    "deleted_files": deleted_paths,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"[DELETE-MENU] Error: {str(e)}")
        return (
            jsonify({"success": False, "error": f"Failed to delete menu: {str(e)}"}),
            500,
        )


@menu_bp.route("/toggle_menu", methods=["GET", "POST"])
@menu_bp.route("/change_menu", methods=["GET", "POST"])
def toggle_menu():
    """Toggle between menu_data.json and redbar_menu_data.json"""
    current_setting = os.environ.get("USE_REDBAR_MENU", "false").lower() == "true"

    # Allow explicit setting through query param
    if request.args.get("use_redbar") is not None:
        new_setting = request.args.get("use_redbar").lower() in ["true", "1", "yes"]
        logger.info(
            f"Setting USE_REDBAR_MENU to {new_setting} based on query parameter"
        )
    else:
        # Toggle if no parameter provided
        new_setting = not current_setting
        logger.info(f"Toggling USE_REDBAR_MENU from {current_setting} to {new_setting}")

    # Set environment variable
    os.environ["USE_REDBAR_MENU"] = str(new_setting).lower()

    # Update the global USE_REDBAR_MENU variable in menu_utils
    import app.utils.menu_utils as menu_utils

    menu_utils.USE_REDBAR_MENU = new_setting

    # Clear the menu cache to force a reload
    menu_utils._menu_cache = None
    menu_utils._last_refresh_time = 0

    # Reload the module to update the file paths
    importlib.reload(menu_utils)

    # Force refresh the menu data
    try:
        menu_data = load_menu_data(force_refresh=True)
        item_count = len(menu_data.get("items", []))

        # Check if the actual file we're using matches what we expect
        expected_filename = "redbar_menu_data.json" if new_setting else "menu_data.json"
        actual_filename = os.path.basename(MENU_FILE_PATH)
        filename_match = expected_filename in actual_filename

        return jsonify(
            {
                "success": True,
                "use_redbar_menu": new_setting,
                "menu_file_path": MENU_FILE_PATH,
                "filename_match": filename_match,
                "item_count": item_count,
                "message": f"Now using {'redbar_menu_data.json' if new_setting else 'menu_data.json'} with {item_count} items",
            }
        )
    except Exception as e:
        logger.error(f"Error toggling menu: {e}")
        return (
            jsonify(
                {"success": False, "error": str(e), "use_redbar_menu": new_setting}
            ),
            500,
        )


@menu_bp.route("/write_test", methods=["GET", "POST"])
def write_test():
    """
    Super-simple endpoint that just tries to write a file to verify permissions.
    """
    results = {}

    # Try to write to various paths
    paths = ["/app/test.txt", os.path.join(os.getcwd(), "test.txt"), "/tmp/test.txt"]

    for path in paths:
        try:
            with open(path, "w") as f:
                f.write(f"Test file created at {datetime.now()}")
            results[path] = "SUCCESS"
        except Exception as e:
            results[path] = f"ERROR: {str(e)}"

    return (
        jsonify(
            {
                "success": True,
                "results": results,
                "cwd": os.getcwd(),
                "env": dict(os.environ),
                "user": os.getuid(),
            }
        ),
        200,
    )


@menu_bp.route("/menu_settings", methods=["GET"])
def menu_settings():
    """Show current menu settings and configuration"""
    # Check menu file status
    current_setting = os.environ.get("USE_REDBAR_MENU", "false").lower() == "true"
    menu_utils_setting = USE_REDBAR_MENU

    # Get loaded menu file path
    try:
        # Force refresh the menu data to ensure we're looking at what's actually loaded
        menu_data = load_menu_data(force_refresh=True)
        item_count = len(menu_data.get("items", []))

        # Check specific menu items to help identify which menu we're using
        items_sample = [item.get("name") for item in menu_data.get("items", [])[:5]]
        # Check for distinctive items to help identify the menu
        has_redbar_items = any(name and "Roll" in name for name in items_sample)

        return jsonify(
            {
                "status": "success",
                "menu_file_path": MENU_FILE_PATH,
                "USE_REDBAR_MENU_env": current_setting,
                "USE_REDBAR_MENU_var": menu_utils_setting,
                "item_count": item_count,
                "items_sample": items_sample,
                "likely_using_redbar_menu": has_redbar_items,
                "current_menu": (
                    "redbar_menu_data.json" if menu_utils_setting else "menu_data.json"
                ),
                "menu_file_exists": os.path.exists(MENU_FILE_PATH),
                "redbar_menu_exists": os.path.exists(
                    os.path.join(os.getcwd(), "redbar_menu_data.json")
                ),
                "regular_menu_exists": os.path.exists(
                    os.path.join(os.getcwd(), "menu_data.json")
                ),
                "toggle_url": request.url_root + "toggle_menu",
            }
        )
    except Exception as e:
        logger.error(f"Error checking menu settings: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(e),
                    "USE_REDBAR_MENU_env": current_setting,
                    "USE_REDBAR_MENU_var": menu_utils_setting,
                }
            ),
            500,
        )


@menu_bp.route("/debug_menu", methods=["GET"])
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
        "/home/pegasus/mysite/RedBarSushiAI/menu_data.json",
        "/home/pegasus/mysite/menu_data.json",
        os.path.join(os.getcwd(), "menu_data.json"),
        os.path.join(os.getcwd(), "redbar_menu_data.json"),
        "/tmp/menu_data.json",
    ]

    file_status = []
    for path in possible_paths:
        exists = os.path.exists(path)
        size = 0
        item_count_in_file = 0
        if exists:
            try:
                size = os.path.getsize(path)
                with open(path, "r") as f:
                    try:
                        file_data = json.load(f)
                        item_count_in_file = len(file_data.get("items", []))
                    except:
                        item_count_in_file = "Error parsing file"
            except:
                size = "Error getting size"

        file_status.append(
            {
                "path": path,
                "exists": exists,
                "size_bytes": size,
                "item_count": item_count_in_file,
            }
        )

    # System info
    system_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "menu_file_path": MENU_FILE_PATH,
        "env_menu_file_path": os.getenv("MENU_FILE_PATH", "Not set"),
    }

    # Return detailed status
    return (
        jsonify(
            {
                "success": True,
                "loaded_menu_info": {
                    "item_count": item_count,
                    "sample_items": [
                        item.get("name", "No name")
                        for item in menu_data.get("items", [])[:5]
                    ],
                },
                "file_status": file_status,
                "system_info": system_info,
            }
        ),
        200,
    )
