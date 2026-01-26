import time
from datetime import datetime

from src.data import data, load_data, save_data
from src.config import TIMEOUT
from src.bots.manager import mark_offline
from src.utils.world_api import get_world_info
from src.utils.player_api import format_uuid


def _now() -> float:
    return time.time()


def refresh_bot_info():
    load_data()
    
    now = _now()

    for bot, botdata in data.get("bot", {}).items():
        if (
            botdata.get("status")
            and now - botdata.get("last_ping", 0) > TIMEOUT
        ):
            mark_offline(bot)


def refresh_account_info(mcusername: str, mcuuid: str):
    load_data()
    
    data.setdefault("account", {})
    account = data["account"].setdefault(mcuuid, {})

    account["username"] = mcusername
    account.setdefault("abilities", {})
    account.setdefault("storage", {})
    account.setdefault("used", 0)

    today = datetime.now().date().isoformat()
    last = account.get("last_deploy")

    if last != today:
        account["used"] = 0
        account["last_deploy"] = today


def create_world(world: str, uuid: str):
    load_data()
    
    worlddata = get_world_info(world)
    if worlddata is None:
        raise ValueError("World does not exist")

    if worlddata["owner_uuid"] != format_uuid(uuid):
        raise PermissionError("Unauthorized")

    data.setdefault("world", {})

    data["world"][world] = {
        "owner": uuid,
        "elements": {},
        "public": False,
        "title": worlddata["name"],
    }

    save_data()
