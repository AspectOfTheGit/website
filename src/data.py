import json
import os
from app.config import DATA_FILE

data = {}

def load_data():
    global data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = {"bot": {}, "account": {}, "world": {}}
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        save_data()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
