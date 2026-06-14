import json
import threading
import os
import boto3

ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
ACCESS_KEY = os.environ["R2_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["R2_SECRET_ACCESS_KEY"]

BUCKET = "render"
KEY = "data.json"

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

_lock = threading.Lock()

data = {}


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
            obj = s3.get_object(Bucket=BUCKET, Key=KEY)
            loaded = json.loads(obj["Body"].read().decode("utf-8"))
        except Exception:
            loaded = _default_data()

        data.clear()
        data.update(loaded)

        _write_data_locked()


def save_data():
    with _lock:
        _write_data_locked()


def _write_data_locked():
    payload = json.dumps(data).encode("utf-8")

    s3.put_object(
        Bucket=BUCKET,
        Key=KEY,
        Body=payload,
        ContentType="application/json",
    )