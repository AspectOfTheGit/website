from flask import (
    Blueprint,
    request,
    jsonify
)

import re

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
        return return jsonify({"error": "Exception on sending request"}), 500

    return jsonify({"profile": data}), 200
