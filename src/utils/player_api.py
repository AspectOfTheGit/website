import re

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
    numbers = re.findall(r'-?\d+', int_array)
    
    int_array = [int(n) for n in numbers]
    
    if len(int_array) != 4:
        raise ValueError("Invalid Minecraft UUID array. Must contain 4 integers.")

    unsigned = [i & 0xFFFFFFFF for i in int_array]
    combined = (unsigned[0] << 96) | (unsigned[1] << 64) | (unsigned[2] << 32) | unsigned[3]
    
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
