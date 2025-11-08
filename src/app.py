from flask import Flask, render_template, request, redirect, session, make_response, jsonify, Response, send_file, abort
import os
import requests
import time
from datetime import datetime
import json
#import threading

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret")

AUTH_REQ_URL = (
    f"https://mc-auth.com/oAuth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&scope=profile"
    f"&response_type=code"
)
# get the file dictionary stuff

try:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
except:
    data = '{}'
    data.setdefault("bot", {})
    data = json.loads(data)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# check bot alive or somethi
timeout = 5

@app.route("/ping", methods=["POST"])
def alive():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403
    
    global data
    data["bot"][request.json.get("account")]["status"] = True  # mark as online
    data["bot"][request.json.get("account")]["last_ping"] = time.time()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"success": True, "status": True})

@app.route("/world", methods=["POST"])
def world():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403
    
    global data
    data["bot"][request.json.get("account")].setdefault("world", {})
    data["bot"][request.json.get("account")]["world"].setdefault("owner", {})
    if request.json.get("value") == "lobby":
        data["bot"][request.json.get("account")]["world"]["name"] = "Lobby"
    else:
        world_data = get_world_info(request.json.get("value"))
        data["bot"][request.json.get("account")].setdefault("world", {})
        data["bot"][request.json.get("account")]["world"]["uuid"] = request.json.get("value")
        data["bot"][request.json.get("account")]["world"]["name"] = world_data["name"]
        data["bot"][request.json.get("account")]["world"]["owner"]["uuid"] = world_data["owner_uuid"]
        data["bot"][request.json.get("account")]["world"]["owner"]["name"] = get_username(world_data["owner_uuid"])
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"success": True, "status": True})

def botinfo():
    global data, timeout
    bots = ["AspectOfTheBot"]
    for bot in bots:
        data["bot"].setdefault(bot, {})
        if data["bot"][bot]["last_ping"] != 0 and time.time() - data["bot"][bot]["last_ping"] > timeout:
            data["bot"][bot]["status"] = False
        else:
            data["bot"][bot]["uuid"] = get_uuid(bot)
            #data["bot"][bot].setdefault("world", {})
            #data["bot"][bot]["world"]["name"] = "WorldNamePlaceholder"
            #data["bot"][bot]["world"].setdefault("owner", {})
            #data["bot"][bot]["world"]["owner"]["name"] = "WorldOwnerPlaceholder"
            #data["bot"][bot]["world"]["owner"]["uuid"] = get_uuid(data["bot"][bot]["world"]["owner"]["name"])
        with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)

# get head of player
@app.route("/head/<username>")
def head_proxy(username):
    username = username.strip()
    if not username:
        return abort(400)
    size = request.args.get("size", "100")
    try:
        int(size)
    except Exception:
        size = "100"

    minotar_url = f"https://minotar.net/avatar/{username}/{size}.png"

    r = requests.get(minotar_url, stream=True, timeout=8)
    if r.status_code != 200:
        # fallback
        return abort(404)
    return Response(r.content, content_type=r.headers.get("Content-Type", "image/png"))

# uses legitidevs to get world info
def get_world_info(uuid: str):
    url = f"https://api.legiti.dev/world/{uuid}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} — Status code: {response.status_code}")
    except requests.RequestException as err:
        print(f"Request error occurred: {err}")
    except ValueError:
        print("Response was not valid JSON")
    return None

def get_username(uuid: str) -> str | None:
    uuid = uuid.replace("-", "")
    url = f"https://api.ashcon.app/mojang/v2/user/{uuid}" # wtf is ashcon
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("username") # username is this
    except requests.RequestException:
        return None

# uh oh here comes mojang api

def get_uuid(username: str) -> str | None:
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get("id")  # UUID
        else:
            return None
    except Exception:
        return None

######################




#help




#######################
@app.route("/")
def home():
    return render_template("index.html")

# temporary to clear the disk data
@app.route("/clear")
def clear_data():
    data = '{"bot":{"AspectOfTheBot":{}}}'
    data = json.loads(data)
    open(DATA_FILE, "w").close()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/status")
def status():
    botinfo()
    return render_template("status.html",bots=data["bot"])

@app.route("/login")
def mc_login():
    session_token = request.cookies.get("authorization.sessionToken")
    profile_uuid = request.cookies.get("profile.uuid")
    
    if session_token and profile_uuid:
        check_session_res = requests.post(
            f"https://aspectofthe.site/check-session",
            headers={"Session-Token": session_token},
            json={"profile_uuid": profile_uuid}
        )
        if check_session_res.ok and check_session_res.json().get("success"):
            return redirect(f"/signedintest")
    
    code = request.args.get("code")
    
    if not code:
        return redirect(AUTH_REQ_URL)
    
    mc_auth_payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    mc_auth_response = requests.post(
        "https://mc-auth.com/oAuth2/token",
        json=mc_auth_payload
    ).json()
    
    if mc_auth_response.get("error"):
        return "Internal error occurred.", 500
    
    token_response = requests.post(
        f"https://aspectofthe.site/login",
        json={"access_token": mc_auth_response["access_token"]}
    )
    
    if not token_response.ok:
        return redirect("/")
    
    token_data = token_response.json()
    session_token = token_data["sessionToken"]
    refresh_token = token_data["refreshToken"]
    profile_uuid = token_data["profile_uuid"]
    refresh_expires = token_data["refreshTokenExpiresAt"]
    
    resp = make_response(redirect(f"/signedintest"))
    expires_dt = datetime.utcfromtimestamp(refresh_expires)
    resp.set_cookie("authorization.sessionToken", session_token, path="/", expires=expires_dt)
    resp.set_cookie("authorization.refreshToken", refresh_token, path="/", expires=expires_dt)
    resp.set_cookie("profile.uuid", profile_uuid, path="/", expires=expires_dt)
    
    return resp

@app.route("/test", methods=["POST"])
def update_value():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403

    data["motd"]=request.json.get("value")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"success": True, "value": data["motd"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
