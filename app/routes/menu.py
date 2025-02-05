# app/routes/menu.py
from flask import Blueprint, request, jsonify
from app.utils.menu_utils import write_menu_file, load_menu_data
import logging

menu_bp = Blueprint('menu', __name__)
logger = logging.getLogger(__name__)

@menu_bp.route('/menu_update', methods=['POST'])
def menu_update():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"error": "Expected an array"}), 400

    # In your original code, you parsed products, modifiers, etc.
    # Here we simply write the received JSON to the menu file.
    write_menu_file(data)
    return jsonify({"status": "menu updated"}), 200

@menu_bp.route('/snoozeUnsnooze', methods=['POST'])
def snooze_unsnooze():
    data = request.get_json() or {}
    logger.info(f"Received snooze/unsnooze data: {data}")
    operations = data.get("operations", [])
    if not operations:
        return jsonify({"error": "No operations found"}), 400

    # Process each operation (snooze or unsnooze)
    for op in operations:
        action = op.get("action")
        op_data = op.get("data", {})
        items = op_data.get("items", [])
        # Here you would update each item's snooze status in your menu data
        # For brevity, this example does not implement full update logic.
        logger.info(f"Processing {action} for items: {items}")
    return jsonify({"status": "ok"}), 200

@menu_bp.route('/busy_mode', methods=['POST'])
def busy_mode():
    return jsonify({"status": "PAUSED"}), 200

@menu_bp.route('/updatePrepTime', methods=['GET','POST'])
def update_prep_time():
    return jsonify({"status": "not implemented"}), 200

@menu_bp.route('/courierUpdate', methods=['GET','POST'])
def courier_update():
    return jsonify({"status": "not implemented"}), 200
