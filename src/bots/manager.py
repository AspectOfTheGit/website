import time

from src.data import data, save_data
from src.config import TIMEOUT
from src.discord.notify import notify


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
        notify(bot, f"{bot} disconnected", "bot.disconnect")
        save_data()


def refresh_bot_info():
    now = _now()

    for bot, botdata in data.get("bot", {}).items():
        if botdata.get("status") and now - botdata.get("last_ping", 0) > TIMEOUT:
            mark_offline(bot)


def update_world(bot: str, world_uuid: str):
    botdata = _ensure_bot(bot)

    botdata.setdefault("world", {})
    botdata["world"]["uuid"] = world_uuid
    botdata["world"]["name"] = "Lobby" if world_uuid == "lobby" else world_uuid
    botdata["last_ping"] = _now()

    save_data()


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
