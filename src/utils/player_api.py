import requests

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

def format_uuid(u):
    u = u.replace("-", "").strip()
    u = (
        u[:8] + "-" +
        u[8:12] + "-" +
        u[12:16] + "-" +
        u[16:20] + "-" +
        u[20:]
    )
    return u

