from flask import Blueprint, request, jsonify, abort
import time
import requests

from src.config import BOT_TOKEN, BOT_PERMISSION_DEFAULTS, BOT_LOBBY_PERMISSIONS
from src.data import data
from src.socket import emit_log, emit_image
from src.utils.text_api import mc_to_html

from src.bots.manager import (
    mark_online,
    update_world,
    get_instructions,
    complete_instruction,
    refresh_bot_info,
    get_bot_state,
    get_all_bot_states,
)


bots = Blueprint(
    "bots",
    __name__,
    url_prefix="/bots"
)


def require_bot_auth():
    if request.headers.get("Authorization") != BOT_TOKEN:
        abort(401, description="Unauthorized")


def get_bot_account(from_form=False):
    payload = request.form if from_form else request.json
    account = payload.get("account") if payload else None

    if not account:
        abort(400, description="Missing bot account")

    if account not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    return account


# Bot Routes

@bots.post("/ping")
def bot_ping():
    require_bot_auth()
    account = get_bot_account()

    mark_online(account)
    return jsonify({"success": True})


@bots.post("/world")
def bot_world():
    require_bot_auth()
    account = get_bot_account()

    world_uuid = request.json.get("value")
    if not world_uuid:
        abort(400, description="Missing world value")

    update_world(account, world_uuid)

    if world_uuid == "lobby":
        permissions = BOT_LOBBY_PERMISSIONS
    else:
        try:
            permissions = data["world"][world_uuid]["permissions"]
        except:
            permissions = BOT_PERMISSION_DEFAULTS
    return jsonify({"success": True, "permissions":permissions})


@bots.post("/done/<action>")
def bot_done(action):
    require_bot_auth()
    account = get_bot_account()

    complete_instruction(account, action)
    return jsonify({"success": True})

@bots.post("/log")
def bot_log():   
    require_bot_auth()
    
    try:
        msg = mc_to_html(request.json.get('value'))
        if '[{&quot;text&quot;:&quot;' in msg:
            print("[bots/routes.py] Error during bot log (parsing issue) msg:", msg)
            return 500
    except:
        print("[bots/routes.py] Error during bot log (Unknown)")
        return 500
    room_name = request.json.get('account')
    ts = time.strftime('%H:%M:%S')

    contents = [ts, msg]

    #print(f"[app.py] Emitting to room: {room_name}, message: {msg}") # debug
    emit_log('log', contents, room_name)

    return jsonify({"success": True})


@bots.post("/screenshot")
def bot_screenshot():
    require_bot_auth()
    account = get_bot_account(from_form=True)

    if "file" not in request.files:
        print("[bots/routes.py] No file found in screenshot request!")
        abort(400, description="No file uploaded")

    file = request.files["file"]
    try:
        print(file) # debug
    except:
        print("couldnt print file")
    file_bytes = file.read()
    file.seek(0)

    print(file_bytes) # debug
    
    emit_image("screenshot", file_bytes, account)

    complete_instruction(account, "screenshot")
    return jsonify({"success": True})
    

@bots.get("/botwhat/<bot>")
def bot_what(bot):
    if bot not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    return jsonify(get_instructions(bot))
