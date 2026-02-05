from flask import Blueprint, request, jsonify
import time
import re
import json

from src.data import data, save_data
from src.utils.player_api import storage_size
from src.socket import emit_storage_log

storage = Blueprint(
    "storage",
    __name__,
    url_prefix="/api/storage"
)


def get_world_id():
    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    return match.group(1) if match else None


def get_account(account):
    if account not in data["account"]:
        return None, (jsonify({"error": "Account doesn't exist"}), 400)
    return data["account"][account], None


def check_token(account_data, token, token_type):
    tokens = account_data.get("token")
    if not tokens or token_type not in tokens:
        return jsonify({"error": "No Token Generated"}), 400
    if token != tokens[token_type]:
        return jsonify({"error": "Unauthorized"}), 401
    return None


def can_write(account, new_size):
    account_data = data["account"][account]

    account_data.setdefault("abilities", {})
    account_data.setdefault("storage", {})
    account_data["storage"].setdefault("capacity", {})

    capacity_mb = account_data["abilities"].get("capacity", 1)

    storage_size(account)
    current_size = account_data["storage"]["size"]
    old_main = account_data["storage"]["capacity"].get("main", 0)

    projected = current_size - old_main + new_size
    return float(projected) <= float(capacity_mb) * 1024 * 1024


# Routes

@storage.post("/write")
def write():
    rdata = request.get_json() or {}
    content = rdata.get("contents", "")
    account = rdata.get("account", "")
    token = rdata.get("token", "")

    world_id = get_world_id()

    account_data, err = get_account(account)
    if err:
        return err

    err = check_token(account_data, token, "write")
    if err:
        emit_storage_log(
            account,
            "Write request attempted with incorrect token",
            "storage.error",
            world_id
        )
        return err

    size = len(content.encode("utf-8"))

    if not can_write(account, size):
        emit_storage_log(
            account,
            f"Write request attempted with large data of {size} bytes",
            "storage.error",
            world_id
        )
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    account_data["storage"]["capacity"]["main"] = size
    account_data["storage"]["contents"] = content
    storage_size(account)

    emit_storage_log(
        account,
        "Successfully wrote new data to storage",
        "storage.write",
        world_id
    )

    save_data()
    return jsonify({"success": True})


@storage.post("/read")
def read():
    rdata = request.get_json() or {}
    account = rdata.get("account", "")
    token = rdata.get("token", "")

    world_id = get_world_id()

    account_data, err = get_account(account)
    if err:
        return err

    err = check_token(account_data, token, "read")
    if err:
        return err

    emit_storage_log(
        account,
        "Successful read request to storage",
        "storage.read",
        world_id
    )

    return jsonify({
        "success": True,
        "value": account_data["storage"].get("contents", "")
    })


@storage.post("/readkey")
def readkey():
    rdata = request.get_json() or {}
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    key = rdata.get("key", "")

    world_id = get_world_id()

    account_data, err = get_account(account)
    if err:
        return err

    err = check_token(account_data, token, "read")
    if err:
        return err

    try:
        storagedict = json.loads(account_data["storage"].get("contents", "{}"))
    except json.JSONDecodeError:
        return jsonify({"error": "Could not convert to dictionary"}), 500

    if key not in storagedict:
        return jsonify({"error": f"Key '{key}' not found"}), 500

    emit_storage_log(
        account,
        "Successful read key request to storage",
        "storage.read",
        world_id
    )

    return jsonify({
        "success": True,
        "value": storagedict[key]
    })
