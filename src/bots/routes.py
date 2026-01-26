from flask import Blueprint, request, jsonify, abort
import base64

from src.config import BOT_TOKEN
from src.data import data
from src.socket import socketio

from src.bots.manager import (
    mark_online,
    update_world,
    get_instructions,
    complete_instruction,
    refresh_bot_info,
    get_bot_state,
    get_all_bot_states,
)


bots_bp = Blueprint("bots", __name__, url_prefix="/bots")


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

@bots_bp.post("/ping")
def bot_ping():
    require_bot_auth()
    account = get_bot_account()

    mark_online(account)
    return jsonify({"success": True})


@bots_bp.post("/world")
def bot_world():
    require_bot_auth()
    account = get_bot_account()

    world_uuid = request.json.get("value")
    if not world_uuid:
        abort(400, description="Missing world value")

    update_world(account, world_uuid)
    return jsonify({"success": True})


@bots_bp.post("/done/<action>")
def bot_done(action):
    require_bot_auth()
    account = get_bot_account()

    complete_instruction(account, action)
    return jsonify({"success": True})


@bots_bp.post("/screenshot")
def bot_screenshot():
    require_bot_auth()
    account = get_bot_account(from_form=True)

    if "file" not in request.files:
        abort(400, description="No file uploaded")

    file = request.files["file"]
    encoded = base64.b64encode(file.read()).decode("utf-8")

    socketio.emit(
        "screenshot",
        {
            "filename": file.filename,
            "image": encoded,
        },
        room=account,
    )

    complete_instruction(account, "screenshot")
    return jsonify({"success": True})

# Public API

@bots_bp.get("/botwhat/<bot>")
def bot_what(bot):
    if bot not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    return jsonify(get_instructions(bot))

@bots_bp.get("/status")
def all_status():
    refresh_bot_info()
    return jsonify({"success": True, "bots": get_all_bot_states()})


@bots_bp.get("/status/<bot>")
def single_status(bot):
    if bot not in data.get("bot", {}):
        abort(400, description="Unknown bot")

    refresh_bot_info()
    return jsonify({"success": True, "bot": get_bot_state(bot)})
