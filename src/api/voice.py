from flask import (
    Blueprint,
    request,
    jsonify
)

from src.data import data
from src.socket import emit_log
from src.config import MAX_TIME_TILL_VOICE_ROOM_CLOSE
from src.utils.player_api import format_uuid
import re
import time
import string
import secrets

voice = Blueprint(
    "voice",
    __name__,
    url_prefix="/api/voice"
)

voice_rooms = {}

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
        voice_rooms[world] = {"players":[],"new":[]}
        data["world"][world]["voice"] = time.time_ns() // 1000000

    timediff = (time.time_ns() // 1000000) - data["world"][world].get("voice",0)
    if timediff > MAX_TIME_TILL_VOICE_ROOM_CLOSE: # If voice room hasn't recieved an update recently
        print(f"[api/voice.py] NEW world connected voice room: {world} (last connection {timediff}ms ago)")
        voice_rooms[world] = {"players":[],"new":[]}

    data["world"][world]["voice"] = time.time_ns() // 1000000

    voice_rooms[world]["new"] = []
    request_uuids = []

    for player in value:
        uuid = format_uuid(''.join(f'{x & 0xffffffff:08x}' for x in player["UUID"]))
        request_uuids.append(uuid)

        existing = next((p for p in voice_rooms[world]["players"] if p["uuid"] == uuid), None)
        
        if not existing:
            chars = string.ascii_letters + string.digits
            auth = ''.join(secrets.choice(chars) for _ in range(36))
            voice_rooms[world]["players"].append({"uuid":uuid,"auth":auth,"socket":{"Pos":player["Pos"],"uuid":uuid}})
            voice_rooms[world]["new"].append({"uuid":uuid,"world":world,"auth":auth})
            print(f"[api/voice.py] Player connecting to voice room {world}: {uuid} (Auth: {auth})")
        else:
            existing["socket"] = {"Pos": player["Pos"], "uuid": uuid}

    voice_rooms[world]["players"] = [
        p for p in voice_rooms[world]["players"]
        if p["uuid"] in request_uuids
    ]

    voice_rooms[world]["socket"] = [p["socket"] for p in voice_rooms[world]["players"]]

    emit_log('update',voice_rooms[world]["socket"],f"voice-{world}")

    # no need to save data, its not very important.

    return jsonify(voice_rooms[world]["new"]), 200
