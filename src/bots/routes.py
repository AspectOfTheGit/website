from flask import Blueprint, request, jsonify, abort
from flask_socketio import emit
import time
import base64

from src.config import BOT_TOKEN
from src.data import data, save_data
from src.discord.notify import notify
from src.bots.manager import refresh_bot_info
from src.socket import socketio


bots_bp = Blueprint("bots", __name__, url_prefix="/bots")

def require_bot_auth():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        abort(401, description="Unauthorized")


def get_bot_account():
    account = request.json.get("account") if request.is_json else request.form.get("account")
    if not account:
        abort(400, description="Missing bot account")
    if account not in data.get("bot", {}):
        abort(400, description="Unknown bot")
    return account


def bot_log(bot, message):
    timestamp = time.strftime("%H:%M:%S")
    emit_data = [timestamp, message]
    socketio.emit("log", emit_data, room=bot)
    notify(bot, message, "bot.log")


# Bot Routes

@bots_bp.post("/ping")
def bot_ping():
    require_bot_auth()
    account = get_bot_account()

    first_online = not data["bot"][account].get("status", False)

    data["bot"][account]["status"] = True
    data["bot"][account]["last_ping"] = time.time()

    if first_online:
        bot_log(account, "Bot successfully online")

    save_data()
    return jsonify({"success": True})


@bots_bp.post("/world")
def bot_world_update():
    require_bot_auth()
    account = get_bot_account()

    value = request.json.get("value")
    data["bot"][account].setdefault("world", {})
    data["bot"][account]["world"]["uuid"] = value

    if value == "lobby":
        data["bot"][account]["world"]["name"] = "Lobby"
    else:
        data["bot"][account]["world"]["name"] = value

    data["bot"][account]["last_ping"] = time.time()
    save_data()

    permissions = ["baritone"]
    if value in data.get("world", {}):
        permissions = data["world"][value].get("permissions", permissions)

    return jsonify({"success": True, "permissions": permissions})


@bots_bp.post("/log")
def bot_log_route():
    require_bot_auth()
    account = get_bot_account()

    msg = request.json.get("value")
    if not msg:
        abort(400, description="Missing log value")

    bot_log(account, msg)
    return jsonify({"success": True})


@bots_bp.post("/done/<action>")
def bot_done(action):
    require_bot_auth()
    account = get_bot_account()

    data["bot"][account].setdefault("do", {})
    data["bot"][account]["do"][action] = False

    save_data()
    return jsonify({"success": True})


@bots_bp.post("/screenshot")
def bot_screenshot():
    require_bot_auth()

    account = request.form.get("account")
    if not account or account not in data.get("bot", {}):
        abort(400, description="Invalid bot account")

    if "file" not in request.files:
        abort(400, description="No file provided")

    file = request.files["file"]
    image_bytes = file.read()
    encoded = base64.b64encode(image_bytes).decode("utf-8")

    socketio.emit(
        "screenshot",
        {
            "filename": file.filename,
            "image": encoded
        },
        room=account
    )

    data["bot"][account].setdefault("do", {})
    data["bot"][account]["do"]["screenshot"] = False

    save_data()
    return jsonify({"success": True})

# Public API

@bots_bp.get("/botwhat/<bot>")
def bot_instructions(bot):
    if bot not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    instructions = data["bot"][bot].get("do", {})
    return jsonify(instructions)


@bots_bp.get("/status")
def all_bot_status():
    refresh_bot_info()
    return jsonify({"success": True, "bots": data.get("bot", {})})


@bots_bp.get("/status/<bot>")
def single_bot_status(bot):
    if bot not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    refresh_bot_info()
    return jsonify({"success": True, "bot": data["bot"][bot]})
