from flask import (
    Blueprint,
    request,
    jsonify
)

from src.data import data
from src.socket import emit_log
import re
import time

voice = Blueprint(
    "voice",
    __name__,
    url_prefix="/api/voice"
)


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


    data["world"][world]["voice"] = time.time_ns() // 1000000
    emit_log('update',"HI, i'm an update",f"voice-{world}")

    # no need to save data, its not very important.

    return jsonify({"success": True}), 200
