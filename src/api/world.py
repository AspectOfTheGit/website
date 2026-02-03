from flask import (
    Blueprint,
    session,
    request,
    jsonify
)

from src.data import data, save_data
from src.config import VALID_BOT_PERMISSIONS, USER_SOCKET_LIMIT
from src.utils.data_api import create_world
from src.utils.player_api import storage_size
from src.discord.notify import notify
from src.socket import emit_log

world = Blueprint(
    "world",
    __name__,
    url_prefix="/api/world"
)

@world.post("/<world>/permissions")
def apiworldbotpermissions(world):
    rdata = request.get_json()
    permissions = rdata.get("permissions", "")

    account = session["mc_uuid"]
    
    if not account:
        return jsonify({"error": "Unauthorized"}), 401

    if world not in data["world"]:
        create_world(world, account, session["mc_uuid"])

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401
    
    if not all(x in VALID_BOT_PERMISSIONS for x in permissions):
        return jsonify({"error": "Contains invalid permission"}), 400

    data["world"][world]["permissions"] = permissions

    save_data()

    return jsonify({"success": True})

@world.post("/<world>/edit/save/elements")
def apiworldeditelements(world):
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    # Check if over storage limit
    worldstore = "world-" + world
    data["account"][account].setdefault("abilities", {})
    capacity = data["account"][account]["abilities"].get("capacity", 1)
    size = len(content.encode('utf-8'))
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("capacity", {})
    data["account"][account]["storage"]["capacity"].setdefault(worldstore, 0)
    storage_size(account)
    total = data["account"][account]["storage"]["size"] - data["account"][account]["storage"]["capacity"][worldstore] + size
    # total is in bytes, capacity is in MB
    if int(total) > float(capacity) * 1024 * 1024:
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    # save here
    data["account"][account]["storage"]["capacity"][worldstore] = size
    storage_size(account)

    try:
        data["world"][world]["elements"] = content
    except:
        return jsonify({"error": "Malformed Dictionary"}), 400

    save_data()

    notify(account, f"{world} elements saved", "webpage.save")

    return jsonify({"success": True}), 200

@world.post("/<world>/edit/save/settings")
def apiworldeditsettings(world):
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        for setting in content:
            if setting not in ["title","public"]:
                return jsonify({"error": f"Unknown setting '{setting}'"}), 400
            data["world"][world][setting] = content[setting]
    except:
        return jsonify({"error": "Malformed Dictionary"}), 400

    save_data()

    notify(account, f"{world} settings saved", "webpage.save")

    return jsonify({"success": True}), 200

@world.post("/<world>/edit/update")
def apiworldeditupdate(world):
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")
    user = rdata.get("user", "*")

    '''
    Content: merges into the web page
     | Format: [{id:0,value:"New Text"},{id:4,color:"#FF00FF"}]
     | "id" is the target element's id. Everything else is the element's data.
    User: who to update the web page for
     | Examples: "user1", ["user2","anotheruser"], "*" (for all)
    '''

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    # Check if keys are valid
    for i in content:
        for key in i:
            if key not in ["id","value","color"]:
                return jsonify({"error": "Invalid key '" + key + "'"}), 400

    # update here
    emit = [user, content]
    size = len(emit.encode('utf-8'))
    # Check if over size limit
    if size > USER_SOCKET_LIMIT:
        return jsonify({"error": "Size Limit Exceeded"}), 400
    emit_log('update', emit, world) # Will be sent to everyone viewing the page, but only chosen users are affected; Unrecommended for transferring personal data

    notify(account, f"{world} recieved updates", "webpage.update")
    
    return jsonify({"success": True}), 200
