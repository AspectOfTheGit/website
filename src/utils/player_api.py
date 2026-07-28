import requests

from src.data import data, save_data

def get_username(uuid: str) -> str | None:
    uuid = uuid.replace("-", "")
    url = f"https://api.ashcon.app/mojang/v2/user/{uuid}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("username")
    except requests.RequestException:
        return None

def get_uuid(username: str) -> str | None:
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get("id")
        else:
            return None
    except Exception:
        return None

def int_array_to_uuid(int_array):
    most_sig = (int_array[0] << 32) | (int_array[1] & 0xFFFFFFFF)
    least_sig = (int_array[2] << 32) | (int_array[3] & 0xFFFFFFFF)
    
    combined = (most_sig << 64) | least_sig
    
    return f"{combined:032x}"

def hyphenate_uuid(u):
    u = u.replace("-", "").strip()
    u = (
        u[:8] + "-" +
        u[8:12] + "-" +
        u[12:16] + "-" +
        u[16:20] + "-" +
        u[20:]
    )
    return u

def storage_size(account: str):
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("capacity", {})
    total = 0
    try:
        for i in data["account"][account]["storage"]["capacity"].keys():
            total += data["account"][account]["storage"]["capacity"][i]
    except:
        try:
            total = data["account"][account]["abilities"]["capacity"] * 1024 * 1024
        except:
            total = 10000000
    data["account"][account]["storage"]["size"] = total

    save_data()
