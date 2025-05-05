# app/routes/location.py

import json
import logging
import requests
from flask import Blueprint, request, session, jsonify, Response
from twilio.twiml.voice_response import VoiceResponse
from app.config import BASE_URL, DELIVERECT_API_URL
from app.utils.deliverect import (
    build_deliverect_order,
    get_deliverect_headers,
    register_new_location,
    update_location_status,
    get_location_webhook_urls,
    generate_order_id,
)
from app.utils.order_utils import (
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
    build_order_description,
    calculate_bill_amount,
)
from app.utils.agent_utils import analyze_user_input

# Import from menu_utils_db instead of menu_utils to use database-backed implementations
from app.utils.menu_utils_db import find_menu_item_by_name
from app.utils.menu_utils_db import (
    load_menu_data,
    validate_modifier_constraints,
    process_deliverect_menu,
    process_product_changes,
    process_modifier_group_changes,
    process_modifier_changes,
    update_menu_ordering,
    process_meal_deal,
)
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.helpers import log_info, commit_with_retry
from app import db
from app.models import Order, Location

location_bp = Blueprint("location", __name__, url_prefix="/location")
logger = logging.getLogger(__name__)

# Dictionary to track busy mode status per location
LOCATIONS_BUSY_STATUS = {}


@location_bp.route("/list", methods=["GET"])
def list_locations():
    """List all registered locations."""
    try:
        locations = db.session.query(Location).all()
        result = []
        for loc in locations:
            result.append(
                {
                    "id": loc.id,
                    "name": loc.name,
                    "status": loc.status,
                    "created_at": (
                        loc.created_at.isoformat()
                        if hasattr(loc, "created_at") and loc.created_at
                        else None
                    ),
                    "updated_at": (
                        loc.updated_at.isoformat()
                        if hasattr(loc, "updated_at") and loc.updated_at
                        else None
                    ),
                }
            )
        return jsonify({"locations": result}), 200
    except Exception as e:
        logger.error(f"Error listing locations: {e}")
        return jsonify({"error": "Failed to list locations"}), 500


@location_bp.route("/info/<location_id>", methods=["GET"])
def location_info(location_id):
    """Get information about a specific location."""
    try:
        location = db.session.query(Location).filter_by(id=location_id).first()
        if not location:
            return jsonify({"error": f"Location {location_id} not found"}), 404

        # Create result with location information
        result = {
            "id": location.id,
            "name": location.name,
            "status": location.status,
            "created_at": (
                location.created_at.isoformat()
                if hasattr(location, "created_at") and location.created_at
                else None
            ),
            "updated_at": (
                location.updated_at.isoformat()
                if hasattr(location, "updated_at") and location.updated_at
                else None
            ),
            "webhook_base": (
                location.webhook_base if hasattr(location, "webhook_base") else None
            ),
            # Don't include API key details for security
            "has_credentials": hasattr(location, "api_key")
            and location.api_key is not None,
            "busy_status": LOCATIONS_BUSY_STATUS.get(location_id, False),
        }

        # Get all webhooks for this location
        result["webhooks"] = get_location_webhook_urls(location_id)

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting location info: {e}")
        return jsonify({"error": f"Failed to get location info: {str(e)}"}), 500


@location_bp.route("/register", methods=["POST"])
def register_without_id():
    """Endpoint for when location ID is not provided in URL."""
    return (
        jsonify(
            {
                "error": "Missing location ID in URL",
                "message": "Please use the format: /location/{location_id}/register",
                "example": "/location/my-location-id/register",
                "help": "The location ID is a unique identifier for this restaurant location. You can use any string without spaces.",
            }
        ),
        400,
    )


@location_bp.route("/<location_id>/register", methods=["POST"])
def register_channel_per_location(location_id):
    """Register or update channel status with Deliverect for a specific location."""
    data = request.get_json() or {}
    status = data.get("status")

    if not status:
        return jsonify({"error": "Missing status parameter"}), 400

    location_name = data.get("name", f"Location {location_id}")
    api_credentials = data.get("credentials")
    webhook_base = data.get("webhook_base", BASE_URL)

    # Register or update location in the database
    success = register_new_location(
        location_id=location_id,
        location_name=location_name,
        api_credentials=api_credentials,
        webhook_base=webhook_base,
    )

    if not success:
        return jsonify({"error": "Failed to register location"}), 500

    # Update location status
    if status == "register":
        update_location_status(location_id, "registered")
        log_info(f"Location {location_id} registered with Deliverect")
    elif status == "active":
        update_location_status(location_id, "active")
        log_info(f"Location {location_id} activated with Deliverect")
    elif status == "inactive":
        update_location_status(location_id, "inactive")
        log_info(f"Location {location_id} deactivated with Deliverect")
    else:
        return jsonify({"error": f"Invalid status: {status}"}), 400

    # Return webhook URLs for this location
    webhook_urls = get_location_webhook_urls(location_id)
    return jsonify(webhook_urls), 200


@location_bp.route("/<location_id>/menu_update", methods=["POST"])
def menu_update_per_location(location_id):
    """Handle menu updates from Deliverect for a specific location."""
    data = request.get_json()
    log_info(f"Received menu update data for location {location_id}: {data}")
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        # Handle different menu update formats
        if "categories" in data:
            # If data has categories, it's coming from Deliverect
            log_info(f"Processing Deliverect menu format for location {location_id}")
            processed_data = process_deliverect_menu(data, location_id)
        else:
            # Direct menu update (already in our format)
            log_info(f"Processing direct menu update for location {location_id}")
            # Ensure the data has our expected structure
            processed_data = data.copy()
            if isinstance(processed_data, list):
                processed_data = {"items": processed_data}
            if not isinstance(processed_data, dict):
                return jsonify({"error": "Expected an array or object"}), 400

            # Ensure required keys exist
            if "items" not in processed_data:
                processed_data["items"] = []
            if "modifiers" not in processed_data:
                processed_data["modifiers"] = []
            if "modifierGroups" not in processed_data:
                processed_data["modifierGroups"] = []

        # Validate and fix any issues in the menu data
        validated_data = validate_and_fix_menu_data(processed_data)

        # Save the updated menu with location-specific filename
        from app.utils.menu_utils import write_menu_file

        write_menu_file(validated_data)

        # Force refresh the cache to make new menu available immediately
        from app.utils.menu_utils import load_menu_data

        load_menu_data(force_refresh=True, location_id=location_id)

        log_info(f"Menu updated successfully for location {location_id}")
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing menu update for location {location_id}: {e}")
        return jsonify({"error": str(e)}), 500


@location_bp.route("/<location_id>/product_update", methods=["POST"])
def product_update_per_location(location_id):
    """Handle product updates from Deliverect for a specific location."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    product_id = data.get("id")
    if not product_id:
        return jsonify({"error": "Missing product ID"}), 400

    try:
        # Process product changes
        success = process_product_changes(product_id, data, location_id)

        if success:
            log_info(
                f"Product {product_id} updated successfully for location {location_id}"
            )
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        log_info(f"Error updating product for location {location_id}: {e}")
        return jsonify({"error": str(e)}), 500


@location_bp.route("/<location_id>/modifier_group_update", methods=["POST"])
def modifier_group_update_per_location(location_id):
    """Handle modifier group updates from Deliverect for a specific location."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    group_id = data.get("id")
    if not group_id:
        return jsonify({"error": "Missing group ID"}), 400

    try:
        # Process modifier group changes
        success = process_modifier_group_changes(group_id, data)

        if success:
            log_info(
                f"Modifier group {group_id} updated successfully for location {location_id}"
            )
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Modifier group not found"}), 404
    except Exception as e:
        log_info(f"Error updating modifier group for location {location_id}: {e}")
        return jsonify({"error": str(e)}), 500


@location_bp.route("/<location_id>/modifier_update", methods=["POST"])
def modifier_update_per_location(location_id):
    """Handle modifier updates from Deliverect for a specific location."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    modifier_id = data.get("id")
    if not modifier_id:
        return jsonify({"error": "Missing modifier ID"}), 400

    try:
        # Process modifier changes
        success = process_modifier_changes(modifier_id, data)

        if success:
            log_info(
                f"Modifier {modifier_id} updated successfully for location {location_id}"
            )
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Modifier not found"}), 404
    except Exception as e:
        log_info(f"Error updating modifier for location {location_id}: {e}")
        return jsonify({"error": str(e)}), 500


@location_bp.route("/<location_id>/menu_ordering", methods=["POST"])
def menu_ordering_per_location(location_id):
    """Handle menu ordering updates from Deliverect for a specific location."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        # Process ordering changes
        success = update_menu_ordering(data, location_id)

        if success:
            log_info(f"Menu ordering updated successfully for location {location_id}")
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Failed to update menu ordering"}), 500
    except Exception as e:
        log_info(f"Error updating menu ordering for location {location_id}: {e}")
        return jsonify({"error": str(e)}), 500


@location_bp.route("/<location_id>/snoozeUnsnooze", methods=["POST"])
def snooze_unsnooze_per_location(location_id):
    """Endpoint to snooze or unsnooze menu items for a specific location."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    operations = data.get("operations", [])

    # Load current menu data for this location
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)

    # Process each operation
    for op in operations:
        item_name = op.get("item")
        action = op.get("action")
        duration = op.get("duration", 60)  # Default 60 minutes

        if not item_name or not action:
            continue

        # Find the item
        found_item = None
        for item in menu_data.get("items", []):
            if item.get("name") == item_name:
                found_item = item
                break

        if not found_item:
            continue

        # Apply the operation
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        if action == "snooze":
            found_item["snoozeStart"] = now.isoformat()
            found_item["snoozeEnd"] = (
                now + datetime.timedelta(minutes=duration)
            ).isoformat()
        elif action == "unsnooze":
            if "snoozeStart" in found_item:
                del found_item["snoozeStart"]
            if "snoozeEnd" in found_item:
                del found_item["snoozeEnd"]

    # Save the updated menu data
    from app.utils.menu_utils import write_menu_file

    write_menu_file(menu_data)

    return jsonify({"success": True})


@location_bp.route("/<location_id>/busy_mode", methods=["GET", "POST"])
def busy_mode_per_location(location_id):
    """Endpoint to toggle busy mode status for a specific location."""
    if request.method == "POST":
        data = request.get_json()
        busy = data.get("busy")

        if busy is not None:
            LOCATIONS_BUSY_STATUS[location_id] = busy

    # Both GET and POST return current status
    return jsonify(
        {"success": True, "busy": LOCATIONS_BUSY_STATUS.get(location_id, False)}
    )


@location_bp.route("/<location_id>/take_order", methods=["POST"])
def take_order_per_location(location_id):
    """Handle order taking for a specific location."""
    # Store location in session
    session["location_id"] = location_id

    # Check if location is in busy mode
    if LOCATIONS_BUSY_STATUS.get(location_id, False):
        response = VoiceResponse()
        response.say(
            f"We're currently busy at our {location_id} location and not accepting new orders right now."
        )

        # Instead of hanging up, give them options
        with response.gather(
            input="dtmf", action="/main_menu", num_digits=1, timeout=7
        ) as g:
            g.say(
                "Press 1 to return to the main menu, press 2 to try a different location, or stay on the line to end the call."
            )

        # Add a redirect to a graceful exit if they don't respond
        response.redirect("/graceful_exit")
        return Response(str(response), mimetype="text/xml")

    # Load location-specific menu data
    data = load_menu_data(location_id=location_id)
    available_items = [it for it in data.get("items", []) if it.get("available")]
    response = VoiceResponse()
    if not available_items:
        response.say(
            f"I'm sorry, our menu at our {location_id} location is currently unavailable."
        )

        # Instead of hanging up, give them options
        with response.gather(
            input="dtmf", action="/main_menu", num_digits=1, timeout=7
        ) as g:
            g.say(
                "Press 1 to return to the main menu, press 2 to try a different location, or stay on the line to end the call."
            )

        # Add a redirect to a graceful exit if they don't respond
        response.redirect("/graceful_exit")
        return Response(str(response), mimetype="text/xml")

    user_resp = request.form.get("SpeechResult", "").strip()
    # Consider offloading this asynchronously in production
    analysis = analyze_user_input(user_resp)
    intent = analysis.get("intent", "other")
    if intent != "order_food" or not analysis.get("menu_items"):
        with response.gather(
            input="speech",
            action=f"/location/{location_id}/take_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            timeout=3,
        ) as g:
            g.say(
                "I'm sorry, I couldn't understand that request. Please repeat your order."
            )
        return Response(str(response), mimetype="text/xml")

    order_items = []
    for item_entity in analysis["menu_items"]:
        item_name = item_entity.get("name", "")
        matched_item = find_menu_item_by_name(item_name)
        if not matched_item:
            response.say(
                f"Sorry, we don't have {item_name} on our menu at our {location_id} location."
            )
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")
        if not matched_item.get("available", False):
            response.say(
                f"Sorry, {matched_item['name']} is not available right now at our {location_id} location."
            )
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")

        # Check for meal deals
        if "childProducts" in matched_item:
            # Process as a meal deal
            meal_deal_selections = {}
            for child in matched_item.get("childProducts", []):
                child_id = child.get("id")
                # For now, handle child products in a basic way
                # In a real implementation, would need to parse out which variants
                # the customer selected for each child product
                modifier_list = []
                for mod in item_entity.get("modifier", []):
                    if mod.get("for_component") == child_id:
                        modifier_list.append(mod)

                meal_deal_selections[child_id] = {
                    "name": child.get("name"),
                    "modifier": modifier_list,
                }

            processed_item = process_meal_deal(matched_item, meal_deal_selections)
            order_items.append(processed_item)
        else:
            # Regular item, check modifier constraints
            item_with_mods = {
                "name": item_name,
                "reference_handler": matched_item.get("reference_handler", ""),
                "modifier": item_entity.get("modifier", []),
                "quantity": item_entity.get("quantity", 1),
                "price": matched_item.get("price", 0.0),
            }

            # Validate modifier constraints
            is_valid, error_message = validate_modifier_constraints([item_with_mods])
            if not is_valid:
                response.say(
                    f"Sorry, there's an issue with your order: {error_message}"
                )
                response.redirect("/graceful_exit")
                return Response(str(response), mimetype="text/xml")

            order_items.append(item_with_mods)

    calculate_bill_amount(order_items)
    order_description = build_order_description(order_items)
    generate_order_id(location_id)
    session["bill_amount"] = int(session["total_price"] * 100)
    session["order_items_json"] = json.dumps(order_items)
    session["order_message"] = (
        f"{order_description}\nYour total is ${session['total_price']:.2f}."
    )

    with response.gather(
        input="speech dtmf",
        action=f"/location/{location_id}/confirm_order_from_initial",
        enhanced=True,
        speech_model="phone_call",
        language="en-US",
        speech_timeout="auto",
        num_digits=1,
    ) as g:
        g.say(
            session["order_message"]
            + " If correct, say yes or press 1. If you need changes, say no or press 2."
        )
    return Response(str(response), mimetype="text/xml")


@location_bp.route("/<location_id>/confirm_order_from_initial", methods=["POST"])
def confirm_order_from_initial_per_location(location_id):
    """Handle order confirmation for a specific location."""
    # Store location in session
    session["location_id"] = location_id

    user_resp = (request.form.get("SpeechResult", "") or "").lower()
    dtmf_input = request.form.get("Digits", "")
    log_info(
        f"Order confirmation at {location_id}: Speech='{user_resp}', DTMF='{dtmf_input}'"
    )
    interpreted = None
    if dtmf_input:
        result = dtmf_yes_no(dtmf_input)
        interpreted = result if result else None
    else:
        if user_said_yes(user_resp):
            interpreted = "yes"
        elif user_said_no(user_resp):
            interpreted = "no"
    order_items = json.loads(session.get("order_items_json", "[]"))
    order_id = session.get("order_id", "") or generate_order_id(location_id)
    session["order_id"] = order_id
    sender = session.get("sender", "")
    caller_name = session.get("caller_name", "Valued Customer")
    response = VoiceResponse()
    log_info(f"User confirmation interpreted as: {interpreted}")

    if interpreted == "yes":
        if len(order_items) == 0:
            response.say("I'm sorry, your order appears to be empty. Please try again.")
            response.redirect("/graceful_exit")
            return Response(str(response), mimetype="text/xml")

        # Save order to database
        try:
            text_msg = session.get("order_message", "")
            new_order = Order(
                id=order_id,
                sender=sender,
                caller_name=caller_name,
                message=text_msg,
                location_id=location_id,
            )
            db.session.add(new_order)
            if not commit_with_retry(db.session):
                raise Exception("Commit failed")
            log_info(f"Order {order_id} for location {location_id} saved successfully.")
        except Exception:
            db.session.rollback()
            response.say(
                "Sorry, we encountered a database issue. Please try again later."
            )
            return Response(str(response), mimetype="text/xml")

        # Build the Deliverect payload with location ID
        deliverect_payload = build_deliverect_order(
            sender=sender,
            caller_name=caller_name,
            order_items=order_items,
            total_price=session.get("total_price", 0.0),
            order_id=order_id,
            location_id=location_id,
        )

        # Send the order to Deliverect
        try:
            deliverect_url = DELIVERECT_API_URL
            response_deliv = requests.post(
                deliverect_url,
                json=deliverect_payload,
                headers=get_deliverect_headers(location_id),
                timeout=10,
            )

            if response_deliv.status_code != 200:
                log_info(
                    f"Deliverect API error for location {location_id}: Status {response_deliv.status_code}, Response: {response_deliv.text}"
                )
            else:
                log_info(
                    f"Deliverect order for location {location_id} successfully submitted: {response_deliv.text}"
                )
        except requests.RequestException as e:
            log_info(
                f"Error sending order to Deliverect for location {location_id}: {str(e)}"
            )

        # Offload SMS confirmation to Celery
        from tasks import send_confirmation_sms_task

        send_confirmation_sms_task.delay(
            order_id,
            session.get("order_message", ""),
            sender,
            caller_name,
            session.get("bill_amount", 0),
            order_items,
            location_id,
        )

        # Calculate prep time
        time_taken = 20 + (1 * len(order_items))

        # Provide confirmation to customer
        response.say(
            f"Great! Your order at our {location_id} location is confirmed and will be ready in about {time_taken} minutes. "
            "A confirmation text will be sent. Thank you!"
        )
        response.redirect("/graceful_exit")

    elif interpreted == "no":
        session["modification_in_progress"] = True
        # Save location_id in session for reference
        session["location_id"] = location_id
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
        ) as g:
            g.say("OK, please describe how you'd like your order changed.")
    else:
        with response.gather(
            input="speech dtmf",
            action=f"/location/{location_id}/confirm_order_from_initial",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1,
        ) as g:
            g.say(
                "I didn't catch that. Say yes or press 1 if correct, or no or press 2 to modify."
            )

    return Response(str(response), mimetype="text/xml")


@location_bp.route("/<location_id>/order_status", methods=["POST"])
def order_status_per_location(location_id):
    """Handle order status updates from Deliverect for a specific location."""
    data = request.get_json() or {}
    status = data.get("status")
    order_id = data.get("channelOrderId")
    code = data.get("code")

    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400

    # Log failed orders
    if status == "FAILED" or code == 120:
        log_info(
            f"Order {order_id} at location {location_id} failed with code={code} or status={status}."
        )

    # Find the order in the database
    try:
        order_record = db.session.query(Order).filter_by(id=order_id).first()
        if not order_record:
            return jsonify({"error": "Order not found"}), 404

        # Update order status in database
        order_record.status = status
        if not commit_with_retry(db.session):
            return jsonify({"error": "Database error"}), 500

        # Send status update to customer
        status_message = f"Your order ({order_id}) at our {location_id} location status is now: {status}"
        from tasks import send_order_status_update_task

        send_order_status_update_task.delay(order_id, status_message, location_id)

        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(
            f"Error processing order status update for location {location_id}: {str(e)}"
        )
        return jsonify({"error": "Internal server error"}), 500
