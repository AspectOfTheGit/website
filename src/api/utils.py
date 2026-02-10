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
