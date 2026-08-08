import json

from flask import (
    Blueprint,
    session,
    request,
    jsonify
)

from src.data import data, save_data
from src.config import OTHER_TOKEN
from src.utils.player_api import get_uuid
from src.utils.data_api import refresh_account_info
from src.bots.manager import refresh_bot_info
from src.discord.announce import announce

debug = Blueprint(
    "debug",
    __name__,
    subdomain="api",
    url_prefix="/debug"
)


@debug.post("/permission")
def changeaccountpermission():
    rdata = request.get_json()
    account = rdata.get("account", "")
    permission = rdata.get("permission", "")
    value = rdata.get("value", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data["account"].setdefault(account, {})
    data["account"][account].setdefault("abilities", {})
    data["account"][account]["abilities"][permission] = value

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/man")
def addman():
    rdata = request.get_json()
    man = rdata.get("man", {})
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    worlduuid = man.get("world", "")

    data.setdefault("egg", {})
    data["egg"].setdefault(worlduuid, {})
    data["egg"][worlduuid]["token"] = man.get("token", "")

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/removeman")
def removeman():
    rdata = request.get_json()
    man = rdata.get("man", {})
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    worlduuid = man.get("world", "")

    if "egg" in data and worlduuid in data["egg"]:
        del data["egg"][worlduuid]

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/setman")
def setaccountman():
    rdata = request.get_json()
    account = rdata.get("account", "")
    man = rdata.get("man", {})
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    worlduuid = man.get("world", "")
    value = man.get("value", False)

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
    
    data["account"][account].setdefault("man", {})
    data["account"][account]["man"][worlduuid] = value

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/setaccountdata")
def setaccountdata():
    rdata = request.get_json()
    account = rdata.get("account", "")
    data_ = rdata.get("data", {})
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    data["account"][account] = data_

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/setflag")
def setaccountflag():
    rdata = request.get_json()
    account = rdata.get("account", "")
    flag = str(rdata.get("flag", ""))
    value = rdata.get("value", False)
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    data["account"].setdefault(account, {})
    data["account"][account].setdefault("flag", {})
    data["account"][account]["flag"][flag] = value

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/trusted")
def toggletrusted():
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data["account"].setdefault(account, {})
    if data["account"][account].get("trusted",False):
        data["account"][account]["trusted"] = False
    else:
        data["account"][account]["trusted"] = True

    save_data()

    return jsonify({"success": True,"value":data["account"][account]["trusted"]}), 200


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


@debug.post("/deleteaccountdata")
def deleteaccountdata():
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
        
    data["account"][account] = {}

    save_data()

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

    return jsonify({"success": True, "value": data.to_dict()}), 200


@debug.post("/setdata")
def debug_setdata():
    rdata = request.get_json()
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    new_data = json.loads(rdata.get("value", ""))
    data.clear()
    data.update(new_data)

    save_data()

    return jsonify({"success": True}), 200


@debug.post("/announce")
def debug_announce():
    rdata = request.get_json()
    token = rdata.get("token", "")
    message = rdata.get("message", "")
    type = rdata.get("type", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    announce(message, type)

    return jsonify({"success": True}), 200
    

@debug.post("/forcelogin")
def debug_forcelogin():
    rdata = request.get_json()
    token = rdata.get("token", "")
    account = rdata.get("account", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    accountuuid = get_uuid(account)

    session["mc_username"] = account
    session["mc_uuid"] = accountuuid
    session["mc_access_token"] = True

    refresh_account_info(account, accountuuid)

    return jsonify({"success": True, "account":{"name": account, "uuid": accountuuid}}), 200


@debug.get("session")
def debug_getsession():
    session_data = session if session else None
    return jsonify({"success": True, "session": session_data}), 200
