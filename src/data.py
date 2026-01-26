import json
import os
import threading

from src.config import DATA_FILE

data = {}

_lock = threading.Lock()

def _default_data():
    return {
        "bot": {},
        "account": {},
        "world": {},
    }


def load_data():
    global data

    with _lock:
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = _default_data()
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            _write_data_locked()


def save_data():
    with _lock:
        _write_data_locked()


def _write_data_locked():
    tmp_path = DATA_FILE + ".tmp"

    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=4)

    os.replace(tmp_path, DATA_FILE)
