from flask import (
    Blueprint,
    session,
    request,
    jsonify
)

from src.data import data, save_data
import string
import secrets

token = Blueprint(
    "token",
    __name__,
    subdomain="api"
)

@token.post("/refresh-token/<token>")
def apirefreshtoken(token):
    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_uuid"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if token not in ["write", "read", "deploy"]:
        return jsonify({"error": "Invalid Token Type"}), 400

    chars = string.ascii_letters + string.digits + ''.join(c for c in string.punctuation if c not in ('"', "'"))
    new_token = ''.join(secrets.choice(chars) for _ in range(24))

    data["account"][account].setdefault("token", {})
    data["account"][account]["token"].setdefault(token, {})

    data["account"][account]["token"][token] = new_token

    save_data()

    return jsonify({"token": new_token}), 200

@token.post("/refresh-world-token/<token>")
def apirefreshworldtoken(token):
    rdata = request.get_json()
    world = rdata.get("world", "")

    account = session["mc_uuid"]

    if world not in data["world"]:
        return jsonify({"error": "World doesn't exist"}), 400

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    if token not in ["voice"]:
        return jsonify({"error": "Invalid Token Type"}), 400

    chars = string.ascii_letters + string.digits + ''.join(c for c in string.punctuation if c not in ('"', "'"))
    new_token = ''.join(secrets.choice(chars) for _ in range(24))

    data["world"][world].setdefault("token", {})
    data["world"][world]["token"].setdefault(token, {})

    data["world"][world]["token"][token] = new_token

    save_data()

    return jsonify({"token": new_token}), 200
