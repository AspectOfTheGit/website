from flask import (
    Blueprint,
    session,
    jsonify
)

from src.data import data, save_data
from src.discord.notify import notify
from src.bots.manager import refresh_bot_info
from src.utils.world_api import get_world_info
from src.socket import emit_log
import time
import requests

deploy = Blueprint(
    "deploy",
    __name__,
    url_prefix="/api"
)

@deploy.post("/deploy") # WORK IN PROGRESS
def apideploybot():
    rdata = request.get_json()
    bot = rdata.get("bot", "")
    world = rdata.get("world", "")
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
    # Does token match?
    try:
        if token != data["account"][account]["token"]["deploy"]:
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400
    refresh_bot_info()
    # Bot exists?
    if bot not in data["bot"]:
        return jsonify({"error": "Bot doesn't exist"}), 400
    # Is bot in use?
    if data["bot"][bot]["status"] == True or data["bot"][bot]["deployer"] != "":
        return ({"error": "Bot is unavailable"}), 400
    # Can account deploy?
    try:
        dlimitu = int(data["account"][account]["abilities"]["uses"])
    except:
        dlimitu = 10
    try:
        dlimits = int(data["account"][account]["abilities"]["simultaneous"])
    except:
        dlimits = 1
    deployed = 0
    for botname, botdata in data["bot"].items():
        botdata.setdefault("deployer", "")
        if botdata["deployer"] == account:
            deployed += 1
    if deployed >= dlimits:
        return jsonify({"error": f"Deploy limit reached ({dlimits})"}), 400
    today = datetime.now().date().isoformat()
    try:
        if data["account"][account]["last_deploy"] != today:
            data["account"][account]["last_deploy"] = today
            data["account"][account]["used"] = 0
        if data["account"][account]["used"] >= dlimitu:
            return jsonify({"error": f"Deploy uses spent ({dlimitu})"}), 400
    except:
        data["account"][account].setdefault("last_deploy", today)
        data["account"][account].setdefault("used", 0)

    try:
        worldinfo = get_world_info(world)
        worldname = worldinfo["name"]
    except:
        worldname = "Unknown"

    # Deploy bot
    data["bot"][bot].setdefault("deployer", account)
    data["bot"][bot]["deployer"] = account
    data["bot"][bot]["do"].setdefault("deploy", {})
    data["bot"][bot]["do"]["deploy"] = {}
    data["bot"][bot]["do"]["deploy"]["world"] = world
    data["bot"][bot]["do"]["deploy"]["deployer"] = account

    data["bot"][bot]["do"]["disconnect"] = False # failsafe
    try:
        if data["account"][account]["abilities"]["abandoned"] == True:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = False
        else:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = True
    except:
        data["bot"][bot]["do"]["deploy"]["abandoned"] = True
    try:
        data["bot"][bot]["do"]["deploy"]["uptime"] = data["account"][account]["abilities"]["uptime"]
    except:
        data["bot"][bot]["do"]["deploy"]["uptime"] = 30

    contents = [time.strftime('%H:%M:%S'), f"{bot} deployed to {world} ({worldname}) by {account}"]
    emit_log('log', contents, bot)
    notify(bot, contents[1], "bot.deploy")

    data["account"][account]["used"] += 1
    
    save_data()

    return jsonify({"success": True, "value": {"name": worldname}})
