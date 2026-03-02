from flask import (
    Blueprint,
    request,
    jsonify
)

import re
import requests

utils = Blueprint(
    "utils",
    __name__,
    subdomain="api",
    url_prefix="/utils"
)


@utils.post("/get-world-uuid")
def getworlduuid():
    match = re.search(r"world:([a-zA-Z0-9-]+)", request.headers.get("User-Agent", ""))
    match = match.group(1) if match else None

    if not match:
        return jsonify({"error": "Not sent from a world"}), 400

    return jsonify({"world": match}), 200


@utils.post("/profile/<username>")
def profilewithusername(username):
    if not username:
        return jsonify({"error": "Please provide a username"}), 400

    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
        else:
            return jsonify({"error": "Server did not return status 200"}), 500
    except Exception:
        return jsonify({"error": "Exception on sending request"}), 500

    return jsonify(data), 200
    

@utils.post("/profile/<username>/<key>")
def profilewithusernamewithkey(username, key):
    if not username:
        return jsonify({"error": "Please provide a username"}), 400

    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
        else:
            return jsonify({"error": "Server did not return status 200"}), 500
    except Exception:
        return jsonify({"error": "Exception on sending request"}), 500

    if key:
        if key in data:
            data = data[key]
        else:
            return jsonify({"error": "Invalid key"}), 400

    return jsonify(data), 200


@utils.post("/format-uuid")
def requestformatuuid():# todo Add the array format: convert to AND convert from
    rdata = request.get_json()
    uuid = rdata.get("uuid", "")
    format = rdata.get("format", "")
    
    if not uuid:
        return jsonify({"error": "Please provide a UUID"}), 400

    if not format:
        return jsonify({"error": "Please provide a format type"}), 400

    if format == "hyphenated":
        u = uuid.replace("-", "").strip()
        uuid = (
            u[:8] + "-" +
            u[8:12] + "-" +
            u[12:16] + "-" +
            u[16:20] + "-" +
            u[20:]
        )

    if format == "unhyphenated":
        uuid = uuid.replace("-", "").strip()

    if format == "array":
        return jsonify({"error": "Array format wip"}), 404

    return jsonify(uuid), 200
    

@utils.post("/legitidev/player/<uuid>/rank")
def legitidevplayerrank(uuid):
    rdata = request.get_json()
    format = rdata.get("format", "default")
    
    if not uuid:
        return jsonify({"error": "Please provide a UUID"}), 400

    url = f"https://api.legiti.dev/player/{uuid}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
        else:
            return jsonify({"error": "Server did not return status 200"}), 500
    except Exception:
        return jsonify({"error": "Exception on sending request"}), 500

    data = data.get("rank","Unknown Player")
    if data == "Unknown Player":
        return jsonify({"error": "Player not registered on LegitiDevs"}), 404
        

    if format == "prefix":
        data = "wip"

    return jsonify(data), 200
