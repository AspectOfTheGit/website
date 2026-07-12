import json
import os
import threading
import boto3

from src.config import AUTO_SAVE_INTERVAL_MINUTES

ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
ACCESS_KEY = os.environ["R2_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["R2_SECRET_ACCESS_KEY"]

BUCKET = "render"
MANIFEST_KEY = "data/manifest.json"

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

_lock = threading.Lock()
_save_timer = None
_save_interval_seconds = max(0, int(AUTO_SAVE_INTERVAL_MINUTES * 60))


class DirtyTrackingDict(dict):
    def __init__(self, store, kind, key, initial=None):
        super().__init__(initial or {})
        self._store = store
        self._kind = kind
        self._key = key

    def _mark_dirty(self):
        if self._store is not None:
            self._store.mark_dirty(self._kind, self._key)

    def _wrap_value(self, value):
        if isinstance(value, DirtyTrackingDict):
            return value
        if isinstance(value, dict):
            return DirtyTrackingDict(self._store, self._kind, self._key, value)
        if isinstance(value, list):
            return [self._wrap_value(item) for item in value]
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, self._wrap_value(value))
        self._mark_dirty()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._mark_dirty()

    def clear(self):
        super().clear()
        self._mark_dirty()

    def pop(self, key, default=None):
        value = super().pop(key, default)
        self._mark_dirty()
        return value

    def popitem(self):
        value = super().popitem()
        self._mark_dirty()
        return value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
            return self[key]
        return self[key]

    def update(self, *args, **kwargs):
        if args:
            other = args[0]
            if hasattr(other, "keys"):
                for key in other.keys():
                    self[key] = other[key]
            else:
                for key, value in other:
                    self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, dict) and not isinstance(value, DirtyTrackingDict):
            wrapped = self._wrap_value(value)
            super().__setitem__(key, wrapped)
            return wrapped
        return value


class LazyCollection:
    def __init__(self, store, kind):
        self._store = store
        self._kind = kind
        self._items = {}

    def _ensure_loaded(self, key):
        if key in self._items:
            return self._items[key]
        item = self._store._load_item(self._kind, key)
        self._items[key] = item
        return item

    def __getitem__(self, key):
        return self._ensure_loaded(key)

    def __contains__(self, key):
        return key in self._items or self._store._has_item(self._kind, key)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        item = DirtyTrackingDict(self._store, self._kind, key, default or {})
        self._items[key] = item
        self._store.mark_dirty(self._kind, key)
        return item

    def keys(self):
        keys = set(self._items.keys())
        keys.update(self._store._manifest_keys(self._kind))
        return keys

    def items(self):
        return [(key, self[key]) for key in self.keys()]

    def values(self):
        return [self[key] for key in self.keys()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def clear(self):
        self._items.clear()


class DataStore:
    def __init__(self):
        self._collections = {}
        self._manifest = {}
        self._dirty_items = set()
        self._last_saved_signatures = {}
        self._load_manifest()

    def _load_manifest(self):
        manifest = _load_json_object(MANIFEST_KEY) or {}
        self._manifest = {
            "account": manifest.get("account", {}),
            "world": manifest.get("world", {}),
            "bot": manifest.get("bot", {}),
        }

    def _get_collection(self, kind):
        if kind not in self._collections:
            self._collections[kind] = LazyCollection(self, kind)
        return self._collections[kind]

    def _manifest_keys(self, kind):
        return set(self._manifest.get(kind, {}).keys())

    def _has_item(self, kind, key):
        return key in self._manifest.get(kind, {}) or key in self._collections.get(kind, LazyCollection(self, kind))._items

    def _load_item(self, kind, key):
        if key in self._collections.get(kind, LazyCollection(self, kind))._items:
            return self._collections[kind]._items[key]

        item_data = None
        manifest_entry = self._manifest.get(kind, {}).get(key)
        if manifest_entry is not None:
            path = manifest_entry.get("path") or _default_path(kind, key)
            item_data = _load_json_object(path)

        if item_data is None:
            item_data = {}

        item = DirtyTrackingDict(self, kind, key, item_data)
        self._get_collection(kind)._items[key] = item
        return item

    def mark_dirty(self, kind, key):
        self._dirty_items.add((kind, key))

    def __getitem__(self, key):
        if key in ("account", "world", "bot"):
            return self._get_collection(key)
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key in ("account", "world", "bot"):
            self._collections[key] = value
        else:
            raise KeyError(key)

    def get(self, key, default=None):
        if key in ("account", "world", "bot"):
            return self._get_collection(key)
        return default

    def setdefault(self, key, default=None):
        if key in ("account", "world", "bot"):
            return self._get_collection(key)
        if key in self._collections:
            return self._collections[key]
        self._collections[key] = default
        return self._collections[key]

    def clear(self):
        self._collections.clear()
        self._dirty_items.clear()
        self._manifest = {}

    def update(self, other):
        for key, value in other.items():
            if key in ("account", "world", "bot"):
                if isinstance(value, dict):
                    collection = self._get_collection(key)
                    for item_key, item_value in value.items():
                        item = DirtyTrackingDict(self, key, item_key, item_value)
                        collection._items[item_key] = item
                        self.mark_dirty(key, item_key)
                        self._manifest.setdefault(key, {})[item_key] = {"path": _default_path(key, item_key)}
                else:
                    self._collections[key] = value
            else:
                self._collections[key] = value


def _default_data():
    return {
        "bot": {},
        "account": {},
        "world": {},
    }


def _default_path(kind, key):
    if kind == "account":
        return f"data/accounts/{key}/data.json"
    if kind == "world":
        return f"data/worlds/{key}/data.json"
    if kind == "bot":
        return f"data/bots/{key}/data.json"
    return f"data/{kind}/{key}.json"


def _load_json_object(key: str):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:
        return None


def _write_json_object(key: str, payload):
    encoded = json.dumps(payload).encode("utf-8")
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=encoded,
        ContentType="application/json",
    )


def load_data():
    global data

    with _lock:
        data = DataStore()


def save_data():
    global _save_timer

    with _lock:
        if not isinstance(data, DataStore) or not data._dirty_items or _save_interval_seconds <= 0:
            return

        if _save_timer is not None:
            return

        _save_timer = threading.Timer(_save_interval_seconds, flush_data)
        _save_timer.daemon = True
        _save_timer.start()


def flush_data():
    global _save_timer

    with _lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None

        _write_data_locked()


def _write_data_locked():
    if not isinstance(data, DataStore):
        return

    if not data._dirty_items:
        return

    current_signatures = {}
    for kind, key in sorted(data._dirty_items):
        item = data._get_collection(kind)._items.get(key)
        if item is None:
            continue
        current_signatures[(kind, key)] = _snapshot_item(item)

    changed_items = {
        item_key: signature
        for item_key, signature in current_signatures.items()
        if data._last_saved_signatures.get(item_key) != signature
    }

    if not changed_items:
        data._dirty_items.clear()
        return

    manifest = {
        "version": 2,
        "account": {},
        "world": {},
        "bot": {},
    }

    for kind in ("account", "world", "bot"):
        for item_key in sorted(changed_items):
            if item_key[0] != kind:
                continue
            item = data._get_collection(kind)._items.get(item_key[1])
            if item is None:
                continue
            path = _default_path(kind, item_key[1])
            _write_json_object(path, dict(item))
            manifest[kind][item_key[1]] = {"path": path}
            data._manifest.setdefault(kind, {})[item_key[1]] = {"path": path}

    for kind in ("account", "world", "bot"):
        for key in data._get_collection(kind).keys():
            if kind not in manifest:
                manifest[kind] = {}
            entry = data._manifest.get(kind, {}).get(key)
            if entry is not None and key not in manifest[kind]:
                manifest[kind][key] = entry

    _write_json_object(MANIFEST_KEY, manifest)
    data._last_saved_signatures.update(changed_items)
    data._dirty_items.clear()


def _snapshot_item(item):
    return json.dumps(dict(item), sort_keys=True, separators=(",", ":"))


data = DataStore()