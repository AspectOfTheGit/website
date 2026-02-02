from flask import (
    Blueprint,
    request,
    jsonify
)

from src.data import data, save_data
from src.config import OTHER_TOKEN
from src.utils.data_api import refresh_account_info
from src.bots.manager import refresh_bot_info

debug = Blueprint(
    "debug",
    __name__,
    url_prefix="/api/debug"
)


@debug.post("/permission")
def changeaccountpermission():
    rdata = request.get_json()
    account = rdata.get("account", "")
    permission = rdata.get("permission", "")
    value = rdata.get("value", "")
    type = rdata.get("type", "string")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data["account"].setdefault(account, {})
    data["account"][account].setdefault("abilities", {})
    if type == "integer":
        data["account"][account]["abilities"][permission] = int(value)
    else:
        data["account"][account]["abilities"][permission] = value

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/deletebotdata")
def deletebotdata():
    rdata = request.get_json()
    bot = rdata.get("bot", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if bot not in data["bot"] and bot != "*":
        return jsonify({"error": "Bot doesn't exist"}), 400
        
    if bot == "*":
        data["bot"] = {}
    else:
        data["bot"][bot] = {}

    refresh_bot_info()

    return jsonify({"success": True}), 200


@debug.post("/deleteworlddata")
def deleteworldpage():
    rdata = request.get_json()
    world = rdata.get("world", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if world not in data["world"] and world != "*":
        return jsonify({"error": "World page doesn't exist"}), 400
        
    if world == "*":
        data["world"] = {}
    else:
        del data["world"][world]

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/getdata")
def debug_getdata():
    rdata = request.get_json()
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    refresh_bot_info()

    return jsonify({"success": True, "value": data}), 200


@debug.post("/setdata")
def debug_setdata():
    rdata = request.get_json()
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    data = json.loads(rdata.get("value", ""))

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/forcelogin")
def debug_forcelogin():
    rdata = request.get_json()
    token = rdata.get("token", "")
    account = rdata.get("account", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    session["mc_username"] = account
    session["mc_uuid"] = get_uuid(account)
    session["mc_access_token"] = True

    refreshaccountinfo()

    return jsonify({"success": True}), 200
