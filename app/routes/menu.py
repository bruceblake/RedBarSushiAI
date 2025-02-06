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
    # Assume the provided data is in the correct format
    write_menu_file(data)
    return jsonify({"status": "menu updated"}), 200


@menu_bp.route('/snoozeUnsnooze', methods=['POST'])
def snooze_unsnooze():
    data = request.get_json() or {}
    logger.info(f"Received snooze/unsnooze data: {data}")
    operations = data.get("operations", [])
    if not operations:
        return jsonify({"error": "No operations found"}), 400
    # Process snooze/unsnooze operations here...
    logger.info("Processed snooze/unsnooze operations.")
    return jsonify({"status": "ok"}), 200


@menu_bp.route('/busy_mode', methods=['POST'])
def busy_mode():
    # Here you might set a global flag to pause orders
    return jsonify({"status": "PAUSED"}), 200


@menu_bp.route('/updatePrepTime', methods=['GET', 'POST'])
def update_prep_time():
    return jsonify({"status": "not implemented"}), 200


@menu_bp.route('/courierUpdate', methods=['GET', 'POST'])
def courier_update():
    return jsonify({"status": "not implemented"}), 200

