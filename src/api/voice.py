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
    
    rdata = request.get_json()
    account = rdata.get("account", "")
    world = rdata.get("world", match)
    value = rdata.get("value", "")
    token = rdata.get("token", "")

    if not world:
        return jsonify({"error": "No world provided"}), 400

    if world not in data["world"]:
        return jsonify({"error": "World not registered"}), 400

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    #if token != data["account"][account]["token"]["deploy"]:# todo - create a token for this
    #    return jsonify({"error": "Unauthorized"}), 401

    data["world"][world]["voice"] = time.time_ns() // 1000000
    emit_log('update',"HI, i'm an update",f"voice-{world}")

    # no need to save data, its not very important.

    return jsonify({"success": True}), 200
