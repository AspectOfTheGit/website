import time

from src.data import data, save_data
from src.config import TIMEOUT, BOTS, BOT_PERMISSION_DEFAULTS
from src.discord.notify import notify
from src.socket import emit_log
from src.utils.player_api import get_uuid


def _now() -> float:
    return time.time()


def _ensure_bot(bot: str):
    data.setdefault("bot", {})
    data["bot"].setdefault(bot, {})
    botdata = data["bot"][bot]

    botdata.setdefault("status", False)
    botdata.setdefault("last_ping", 0)
    botdata.setdefault("world", {})
    botdata.setdefault("do", {})

    return botdata
    

def mark_online(bot: str) -> bool:
    botdata = _ensure_bot(bot)
    was_offline = not botdata["status"]

    botdata["status"] = True
    botdata["last_ping"] = _now()

    if was_offline:
        notify(bot, f"{bot} connected", "bot.connect")

    save_data()
    return was_offline


def mark_offline(bot: str):
    botdata = _ensure_bot(bot)

    if botdata["status"]:
        botdata["status"] = False
        botdata["deployer"] = ""
        notify(bot, f"{bot} disconnected", "bot.disconnect")
        save_data()


def refresh_bot_info():
    now = _now()

    data.setdefault("bot",{})
    for bot in BOTS:
        # Set Defaults
        data["bot"].setdefault(bot, {})
        data["bot"][bot]["uuid"] = get_uuid(bot)
        data["bot"][bot].setdefault("last_ping", 0)
        data["bot"][bot].setdefault("status", False)
        data["bot"][bot].setdefault("deployer", "")
        data["bot"][bot].setdefault("world", {})
        data["bot"][bot]["world"].setdefault("name", "")
        data["bot"][bot]["world"].setdefault("uuid", "")
        data["bot"][bot]["world"].setdefault("owner", {})
        data["bot"][bot]["world"]["owner"].setdefault("name", "")
        data["bot"][bot]["world"]["owner"].setdefault("uuid", "")
        data["bot"][bot].setdefault("do", {})
        if data["bot"][bot]["last_ping"] != 0 and now - data["bot"][bot]["last_ping"] > TIMEOUT and data["bot"][bot]["status"]:
            mark_offline(bot)
        else:
            if data["bot"][bot]["deployer"] == "" and data["bot"][bot]["status"]:
                data["bot"][bot]["do"]["disconnect"] = True # Disconnect bot if no deployer
                contents = [time.strftime('%H:%M:%S'), f"Disconnect requested for {bot}"]
                emit_log('log', contents, bot)
    save_data()


def update_world(bot: str, world_uuid: str):
    botdata = _ensure_bot(bot)

    botdata.setdefault("world", {})
    botdata["world"].setdefault("owner", {})
    if world_uuid == "lobby":
        botdata["world"]["name"] = "Lobby"
    else:
        world_data = get_world_info(world_uuid)
        botdata.setdefault("world", {})
        botdata["world"]["uuid"] = world_uuid
        try:
            botdata["world"]["name"] = raw_to_html(world_data["raw_name"])
            botdata["world"]["owner"]["uuid"] = world_data["owner_uuid"]
            botdata["world"]["owner"]["name"] = get_username(world_data["owner_uuid"])
        except:
            botdata["world"]["name"] = "Error fetching world data"
            botdata["world"]["owner"]["uuid"] = "?"
            botdata["world"]["owner"]["name"] = "Error fetching world data"

    # Defaults
    permissions = BOT_PERMISSION_DEFAULTS

    if world_uuid in data["world"]:
        if "permissions" in data["world"][world_uuid]:
            permissions = data["world"][world_uuid]["permissions"]

    save_data()
    
    return permissions


def set_instruction(bot: str, action: str, value):
    botdata = _ensure_bot(bot)

    botdata["do"][action] = value

    save_data()


def get_instructions(bot: str):
    botdata = _ensure_bot(bot)

    return botdata["do"]


def complete_instruction(bot: str, action: str):
    botdata = _ensure_bot(bot)

    if action in botdata["do"]:
        botdata["do"][action] = False
        save_data()


def request_deploy(bot: str, world_uuid: str):
    set_instruction(bot, "deploy", {"world": world_uuid}) # todo - add full payload


def request_disconnect(bot: str):
    set_instruction(bot, "disconnect")


def get_bot_state(bot: str):
    return data.get("bot", {}).get(bot, {})


def get_all_bot_states():
    return data.get("bot", {})
