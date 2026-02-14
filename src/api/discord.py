from flask import (
    Blueprint,
    session,
    jsonify,
    request
)

from src.data import data, save_data
import time
import re
import requests
from src.config import DISCORD_TOKEN, GUILD_ID

discord = Blueprint(
    "discord",
    __name__,
    subdomain="api",
)

@discord.post("/set-discord")
def apisetdiscord():
    global data
    rdata = request.get_json()
    id = rdata.get("new_id", "")

    if "mc_uuid" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_uuid"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    data["account"][account]["discord"] = id

    save_data()

    # If discord notifications has been used before, change the users able to view

    headers = {"Authorization": f"Bot {DISCORD_TOKEN}","Content-Type": "application/json"}
    saccount = account.lower()

    channels = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels", headers=headers).json()
    category_id = None
    for c in channels:
        if c["type"] == 4 and c["name"] == saccount:
            category_id = c["id"]
    if not category_id:
        return jsonify({"success": True}), 200

    r = requests.get(f"https://discord.com/api/v10/channels/{category_id}", headers=headers)
    if r.status_code != 200:
        return jsonify({"success": True}), 200
    category = r.json()
    
    overwrites = category.get("permission_overwrites", [])

    everyone_overwrite = next((o for o in overwrites if o["type"] == 0), None)
    if not everyone_overwrite:
        requests.patch(
            f"https://discord.com/api/v10/channels/{category_id}",
            headers=headers,
            json={
                "permission_overwrites": [
                    {
                        "id": str(GUILD_ID),
                        "type": 0,
                        "allow": "0",
                        "deny": "1024"
                    }
                ]
            }
        )

    for overwrite in overwrites:
        if overwrite["type"] == 1:
            requests.delete(f"https://discord.com/api/v10/channels/{category_id}/permissions/{overwrite['id']}", headers=headers)

    requests.put(
        f"https://discord.com/api/v10/channels/{category_id}/permissions/{id}",
        headers=headers,
        json={
            "type": 1,
            "allow": "1024",
            "deny": "0"
        }
    )

    return jsonify({"success": True}), 200

@discord.post("/set-notifs")
def apisetnotifs():
    rdata = request.get_json()
    prefs = rdata.get("prefs", "")

    account = session["mc_uuid"]
    
    if not account:
        return jsonify({"error": "Unauthorized"}), 401
    
    if not all(x in {"storage.read","storage.write","storage.error","webpage.view","webpage.update","webpage.interact","webpage.save"} for x in prefs):
        return jsonify({"error": "Contains invalid notification type"}), 400

    data["account"][account]["notifs"] = prefs

    save_data()

    return jsonify({"success": True})
