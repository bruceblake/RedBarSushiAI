# app/utils/menu_utils.py
import json
import os
import time
import datetime
import logging
from app.config import MENU_FILE_PATH
MENU_CACHE_DURATION = 10


logger = logging.getLogger(__name__)
_last_load_time = 0
_cached_data = None


def write_menu_file(all_items_data):
    try:
        with open(MENU_FILE_PATH, "w") as f:
            json.dump(all_items_data, f)
        logger.info(f"Menu data written to {MENU_FILE_PATH}.")
    except Exception as e:
        logger.error(f"Error writing menu data file: {e}")


def parse_utc_timestamp(ts_str):
    if not ts_str:
        return None
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1]
    try:
        return datetime.datetime.fromisoformat(ts_str).replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def is_item_snoozed_timebased(item_obj):
    s_start_str = item_obj.get("snoozeStart")
    s_end_str = item_obj.get("snoozeEnd")
    if not s_start_str or not s_end_str:
        return False
    start = parse_utc_timestamp(s_start_str)
    end = parse_utc_timestamp(s_end_str)
    if not (start and end):
        return False
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return (start <= now_utc <= end)


def is_item_currently_available_by_schedule(item_obj):
    all_blocks = item_obj.get("availabilities", [])
    if not all_blocks:
        return True
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    day_of_week = now_utc.isoweekday()
    now_time = now_utc.time()
    found_match = False
    for block in all_blocks:
        block_dow = block.get("dayOfWeek")
        start_str = block.get("startTime", "00:00")
        end_str = block.get("endTime", "23:59")
        if block_dow != day_of_week:
            continue
        try:
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
        except Exception as e:
            logger.error(f"Error parsing block time: {e}")
            continue
        start_t = datetime.time(hour=start_hour, minute=start_min)
        end_t = datetime.time(hour=end_hour, minute=end_min)
        if start_t <= now_time <= end_t:
            found_match = True
            break
    if not found_match:
        logger.info("No matching day/time => item is unavailable right now.")
    return found_match


def load_menu_data(force_refresh=False):
    global _last_load_time, _cached_data
    if force_refresh:
        _cached_data = None
    if _cached_data is not None and (time.time() - _last_load_time < MENU_CACHE_DURATION):
        return _cached_data
    if not os.path.exists(MENU_FILE_PATH):
        logger.info("No menu_data.json found, returning empty.")
        return {"items": [], "modifiers": [], "modifierGroups": []}
    try:
        with open(MENU_FILE_PATH, "r") as f:
            data = json.load(f)
        # Update each item with its availability
        for it in data.get("items", []):
            snoozed = is_item_snoozed_timebased(it)
            schedule_ok = is_item_currently_available_by_schedule(it)
            it["snoozed"] = snoozed
            it["scheduleAvailable"] = schedule_ok
            it["available"] = (not snoozed) and schedule_ok
        _cached_data = data
        _last_load_time = time.time()
        return data
    except Exception as e:
        logger.error(f"Error reading menu data file: {e}")
        return {"items": [], "modifiers": [], "modifierGroups": []}

