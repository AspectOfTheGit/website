from flask import (
    Blueprint,
    request,
    session,
    jsonify
)

import time
import re
from flask_socketio import SocketIO

from src.data import data, save_data
from src.utils.player_api import storage_size
from src.discord.notify import notify

storage = Blueprint(
    "storage",
    __name__,
    url_prefix="/api/storage"
)

# todo - Optimise/make functions

@storage.route("/write")
def write():
    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    world_id = match.group(1) if match else None
    
    rdata = request.get_json()
    content = rdata.get("contents", "")
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
    ts = time.strftime('%H:%M:%S')
    # Does token match?
    try:
        if token != data["account"][account]["token"]["write"]:
            if world_id:
                contents = [time, f"`[World {world_id}]` Write request attempted with incorrect token"]
            else:
                contents = [time, "Write request attempted with incorrect token"]
            socketio.emit('log', contents, room=account)
            notify(account, contents[1], "storage.error")
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400
    # Is size over limit?
    data["account"][account].setdefault("abilities", {})
    capacity = data["account"][account]["abilities"].get("capacity", 1)
    size = len(content.encode('utf-8'))
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("capacity", {})
    data["account"][account]["storage"]["capacity"].setdefault("main", 0)
    storage_size(account)
    total = data["account"][account]["storage"]["size"] - data["account"][account]["storage"]["capacity"]["main"] + size
    # total is in bytes, capacity is in MB
    if int(total) > float(capacity) * 1024 * 1024:
        if world_id:
            contents = [ts, f"`[World {world_id}]` Write request attempted with large data of {size} bytes"]
        else:
            contents = [ts, f"Write request attempted with large data of {size} bytes"]
        socketio.emit('log', contents, room=account)
        notify(account, contents[1], "storage.error")
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    # Save content
    data["account"][account]["storage"]["capacity"]["main"] = size
    storage_size(account)
    data["account"][account]["storage"]["contents"] = content

    # Emit to logs
    if world_id:
        contents = [ts, f"`[World {world_id}]` Successfully wrote new data to storage"]
    else:
        contents = [ts, f"Successfully wrote new data to storage"]
    socketio.emit('log', contents, room=account)
    notify(account, contents[1], "storage.write")

    save_data()

    return jsonify({"success": True})

@storage.post("/read")
def read():
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        #print("Account doesn't exist") # debug
        return jsonify({"error": "Account doesn't exist"}), 400
    # Does token match?
    try:
        if token != data["account"][account]["token"]["read"]:
            #print("Incorrect token") # debug
            return jsonify({"error": "Unauthorized"}), 401
    except:
        #print("No token generated") # debug
        return jsonify({"error": "No Token Generated"}), 400

    # Emit to logs
    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    world_id = match.group(1) if match else None

    ts = time.strftime('%H:%M:%S')
    
    if world_id:
        contents = [ts, f"`[World {world_id}]` Successful read request to storage"]
    else:
        contents = [ts, "Successful read request to storage"]
    socketio.emit('log', contents, room=account)
    notify(account, contents[1], "storage.read")
    
    # return storage
    return jsonify({"success": True, "value": data["account"][account]["storage"]["contents"]})

@storage.post("/readkey")
def readkey():
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    key = rdata.get("key", "")
    # Does account exist?
    if account not in data["account"]:
        #print("Account doesn't exist") # debug
        return jsonify({"error": "Account doesn't exist"}), 400
    # Does token match?
    try:
        if token != data["account"][account]["token"]["read"]:
            #print("Incorrect token") # debug
            return jsonify({"error": "Unauthorized"}), 401
    except:
        #print("No token generated") # debug
        return jsonify({"error": "No Token Generated"}), 400
        
    # return storage value from key
    try:
        storagedict = json.loads(data["account"][account]["storage"]["contents"])
        try:
            # Emit to logs
            ua = request.headers.get("User-Agent", "")
            match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
            world_id = match.group(1) if match else None

            ts = time.strftime('%H:%M:%S')
    
            if world_id:
                contents = [ts, f"`[World {world_id}]` Successful read key request to storage"]
            else:
                contents = [ts, "Successful read key request to storage"]
            socketio.emit('log', contents, room=account)
            notify(account, contents[1], "storage.read")
    
            return jsonify({"success": True, "value": storagedict[key]})
        except:
            return jsonify({"error": f"Key '{key}' not found"}), 500
    except:
        return jsonify({"error": "Could not convert to dictionary"}), 500
    
