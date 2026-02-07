import time
from datetime import datetime

from src.data import data, save_data
from src.utils.world_api import get_world_info
from src.utils.player_api import format_uuid


def _now() -> float:
    return time.time()


def refresh_account_info(mcusername: str, mcuuid: str):
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
    worlddata = get_world_info(world)
    if worlddata is None:
        raise ValueError("World does not exist")

    if worlddata["owner_uuid"] != format_uuid(uuid):
        raise PermissionError("Unauthorized")

    data.setdefault("world", {})

    data["world"][world] = {
        "owner": uuid,
        "token": {},
        "elements": {},
        "public": False,
        "title": worlddata["name"],
    }

    save_data()
