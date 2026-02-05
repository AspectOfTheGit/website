import requests

def get_world_info(uuid: str):
    try:
        r = requests.get(f"https://api.legiti.dev/world/{uuid}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
