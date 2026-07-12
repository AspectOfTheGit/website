from flask import (
    Blueprint,
    request,
    jsonify
)

from src.data import data
from src.socket import emit_log, connected
from src.config import MAX_TIME_TILL_VOICE_ROOM_CLOSE, DATAPACK_VERSION, OTHER_TOKEN
from src.utils.player_api import format_uuid
from src.voice_bandwidth import get_voice_bandwidth_controller
import re
import time
import string
import secrets
import calendar
from datetime import datetime, timezone

voice = Blueprint(
    "voice",
    __name__,
    subdomain="api",
    url_prefix="/voice"
)

voice_rooms = {}
voice_bandwidth_controller = get_voice_bandwidth_controller()

DEFAULT_INPUT_VOLUME = 100
DEFAULT_OUTPUT_VOLUME = 100


def _normalize_volume(raw_value, fallback):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return fallback

    return max(0, min(100, value))


def _extract_volume_updates(player_payload):
    if not isinstance(player_payload, dict):
        return {}

    options = player_payload.get("options")
    if not isinstance(options, dict):
        return {}

    updates = {}

    input_options = options.get("input")
    if isinstance(input_options, dict) and "volume" in input_options:
        updates["input_volume"] = _normalize_volume(input_options.get("volume"), DEFAULT_INPUT_VOLUME)

    output_options = options.get("output")
    if isinstance(output_options, dict) and "volume" in output_options:
        updates["output_volume"] = _normalize_volume(output_options.get("volume"), DEFAULT_OUTPUT_VOLUME)

    return updates


def get_player_voice_options(world_uuid, player_uuid):
    room = voice_rooms.get(world_uuid, {})
    options_map = room.get("player_options", {})
    existing = options_map.get(player_uuid, {})

    return {
        "input_volume": _normalize_volume(existing.get("input_volume"), DEFAULT_INPUT_VOLUME),
        "output_volume": _normalize_volume(existing.get("output_volume"), DEFAULT_OUTPUT_VOLUME),
    }

@voice.get("/version")
def apivoiceversion():
    return f"\"{DATAPACK_VERSION}\"", 200, {'Content-Type': 'text/plain'}


@voice.get("/usage")
def apivoiceusage():
    token = request.headers.get("token", "") or request.args.get("token", "")
    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    now_ms = time.time_ns() // 1000000
    now_utc = datetime.now(timezone.utc)
    _, days_in_month = calendar.monthrange(now_utc.year, now_utc.month)
    day_of_month = max(1, now_utc.day)

    bandwidth = voice_bandwidth_controller.get_state()
    used_bytes = bandwidth.get("used_bytes", 0)
    projected_used_bytes = int((used_bytes / day_of_month) * days_in_month)

    rooms = []
    active_worlds = 0

    for world, room_data in voice_rooms.items():
        room_name = f"voice-{world}"
        world_last_voice_ms = data.get("world", {}).get(world, {}).get("voice", 0)
        idle_ms = now_ms - world_last_voice_ms if world_last_voice_ms else None
        is_active = bool(idle_ms is not None and idle_ms <= MAX_TIME_TILL_VOICE_ROOM_CLOSE)

        if is_active:
            active_worlds += 1

        tracked_players = room_data.get("players", [])
        web_connected = connected.get(room_name, {})

        rooms.append(
            {
                "world": world,
                "active": is_active,
                "idle_ms": idle_ms,
                "tracked_players": len(tracked_players),
                "web_connected_clients": len(web_connected),
            }
        )

    return jsonify(
        {
            "timestamp_utc": now_utc.isoformat(),
            "rooms": {
                "total": len(voice_rooms),
                "active": active_worlds,
                "details": rooms,
            },
            "bandwidth": {
                **bandwidth,
                "used_gb": round(used_bytes / (1024 ** 3), 3),
                "limit_gb": round(bandwidth.get("limit_bytes", 0) / (1024 ** 3), 3),
                "projected_used_bytes_month_end": projected_used_bytes,
                "projected_used_gb_month_end": round(projected_used_bytes / (1024 ** 3), 3),
                "month": f"{now_utc.year:04d}-{now_utc.month:02d}",
            },
        }
    ), 200

@voice.post("/update")
def apivoiceupdate():
    match = re.search(r"world:([a-zA-Z0-9-]+)", request.headers.get("User-Agent", ""))
    match = match.group(1) if match else False

    value = request.get_json(silent=True)
    
    token = request.headers.get("token", "")
    world = request.headers.get("world", match)

    if not world:
        return jsonify({"error": "No world provided"}), 400

    if world not in data["world"]:
        return jsonify({"error": "World not registered"}), 400

    try:
        if token != data["world"][world]["token"]["voice"]:
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400

    if world not in voice_rooms:
        print(f"[api/voice.py] NEW world connected voice room (for the first time): {world}")
        voice_rooms[world] = {
            "players": [],
            "new": [],
            "audio": {},
            "player_options": {},
            "bandwidth": voice_bandwidth_controller.get_state(),
        }
        data["world"][world]["voice"] = time.time_ns() // 1000000

    timediff = (time.time_ns() // 1000000) - data["world"][world].get("voice",0)
    if timediff > MAX_TIME_TILL_VOICE_ROOM_CLOSE: # If voice room hasn't recieved an update recently
        print(f"[api/voice.py] NEW world connected voice room: {world} (last connection {timediff}ms ago)")
        voice_rooms[world] = {
            "players": [],
            "new": [],
            "socket": [],
            "audio": {},
            "player_options": {},
            "bandwidth": voice_bandwidth_controller.get_state(),
        }

    data["world"][world]["voice"] = time.time_ns() // 1000000

    voice_rooms[world]["new"] = []
    voice_rooms[world].setdefault("player_options", {})
    request_uuids = []

    for player in value["players"]:
        uuid = format_uuid(''.join(f'{x & 0xffffffff:08x}' for x in player["UUID"])) # Convert UUID from array to hex
        request_uuids.append(uuid)

        # Persist only supported options and keep existing values when omitted.
        volume_updates = _extract_volume_updates(player)
        if uuid not in voice_rooms[world]["player_options"]:
            voice_rooms[world]["player_options"][uuid] = {
                "input_volume": DEFAULT_INPUT_VOLUME,
                "output_volume": DEFAULT_OUTPUT_VOLUME,
            }
        voice_rooms[world]["player_options"][uuid].update(volume_updates)

        current_options = get_player_voice_options(world, uuid)

        existing = next((p for p in voice_rooms[world]["players"] if p["uuid"] == uuid), None) # Find UUID in current voice room session.
        
        if not existing: # If user is new to the voice room
            chars = string.ascii_letters + string.digits
            auth = ''.join(secrets.choice(chars) for _ in range(36)) # Generate a new auth string for that user
            voice_rooms[world]["players"].append({"uuid":uuid,"auth":auth,"options":current_options}) # Init data for them
            voice_rooms[world]["new"].append({"uuid":uuid,"world":world,"auth":auth}) # To tell the game the auth URL
            print(f"[api/voice.py] Player connecting to voice room {world}: {uuid} (Auth: {auth})")
        # Update data for all users (this data is sent to all other users connected to voice room)
        existing = next((p for p in voice_rooms[world]["players"] if p["uuid"] == uuid), None)
        existing["options"] = current_options
        existing["socket"] = {"Pos": player["Eyes"], "uuid": uuid, "Name": player.get("Name",uuid), "Rot": player["Rotation"]}

    voice_rooms[world]["players"] = [
        p for p in voice_rooms[world]["players"]
        if p["uuid"] in request_uuids
    ] # Remove any players from voice room data that werent sent by the game (they disconnected from voice room)

    room = f"voice-{world}"
    voice_rooms[world]["socket"] = [p["socket"] for p in voice_rooms[world]["players"] if connected.get(room) and p["uuid"] in connected[room]] # Construct list to send to users
    voice_rooms[world]["bandwidth"] = voice_bandwidth_controller.get_state()

    emit_log('update',voice_rooms[world]["socket"],f"voice-{world}") # Send data to users (position, rotation, etc.)

    return jsonify(voice_rooms[world]["new"]), 200 # Return with any new users with auth URL for them to join voice room

    '''
    Sent to Users:
    [{"Pos":[x,y,z],"Rot":[x,y],"Name":"PlayerUsername","uuid":"player-uuid"},{...}...]
    List of Dictionaries. Each dictionary is the data of one player.

    Sent to World:
    [{"uuid":"new-player-uuid","world":"world-uuid","auth":"authkey"}]
    List of Dictionaries. Each dictionary is one new player connection (this data is sent so the world can provide the URL to the player)
    '''
