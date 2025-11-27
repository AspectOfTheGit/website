import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, session, make_response, jsonify, Response, send_file, abort
from flask_socketio import SocketIO, emit, join_room
import os
import requests
import time
from datetime import datetime
import json
import re
from markupsafe import Markup
import threading
import base64

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

#def send_logs():
#    while True:
#        socketio.emit('log', f"Server time: {time.strftime('%H:%M:%S')}")
#        socketio.sleep(1)

#socketio.start_background_task(send_logs)

AUTH_REQ_URL = (
    f"https://mc-auth.com/oAuth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&scope=profile"
    f"&response_type=code"
)

# for raw to html
COLOURS = {
    "black": "#000000",
    "dark_blue": "#0000AA",
    "dark_green": "#00AA00",
    "dark_aqua": "#00AAAA",
    "dark_red": "#AA0000",
    "dark_purple": "#AA00AA",
    "gold": "#FFAA00",
    "gray": "#AAAAAA",
    "dark_gray": "#555555",
    "blue": "#5555FF",
    "green": "#55FF55",
    "aqua": "#55FFFF",
    "red": "#FF5555",
    "light_purple": "#FF55FF",
    "yellow": "#FFFF55",
    "white": "#FFFFFF"
}
HEX_COLOUR = re.compile(r'^#?[0-9A-Fa-f]{6}$')

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
        return jsonify({"error": "Unauthorized"}), 401
    
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
        return jsonify({"error": "Unauthorized"}), 401
    
    global data
    data["bot"][request.json.get("account")].setdefault("world", {})
    data["bot"][request.json.get("account")]["world"].setdefault("owner", {})
    if request.json.get("value") == "lobby":
        data["bot"][request.json.get("account")]["world"]["name"] = "Lobby"
    else:
        world_data = get_world_info(request.json.get("value"))
        data["bot"][request.json.get("account")].setdefault("world", {})
        data["bot"][request.json.get("account")]["world"]["uuid"] = request.json.get("value")
        try:
            data["bot"][request.json.get("account")]["world"]["name"] = raw_to_html(world_data["raw_name"])
            data["bot"][request.json.get("account")]["world"]["owner"]["uuid"] = world_data["owner_uuid"]
            data["bot"][request.json.get("account")]["world"]["owner"]["name"] = get_username(world_data["owner_uuid"])
        except:
            data["bot"][request.json.get("account")]["world"]["name"] = "Error fetching world data"
            data["bot"][request.json.get("account")]["world"]["owner"]["uuid"] = "?"
            data["bot"][request.json.get("account")]["world"]["owner"]["name"] = "Error fetching world data"
        
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"success": True, "status": True})

def botinfo():
    global data, timeout
    bots = ["AspectOfTheBot","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks","AspectOfTheButt","AspectOfThePoop"]
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

# uses legitidevs to get world info
def get_world_info(uuid: str):
    url = f"https://api.legiti.dev/world/{uuid}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.HTTPError as http_err:
        print(f"[app.py] HTTP error occurred: {http_err} — Status code: {response.status_code}")
    except requests.RequestException as err:
        print(f"[app.py] Request error occurred: {err}")
    except ValueError:
        print("[app.py] Response was not valid JSON")
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

# get html from the raw json
def raw_to_html(component):
    # allow both dict and JSON string inputs
    if isinstance(component, str):
        try:
            component = json.loads(component)
        except json.JSONDecodeError:
            return Markup(component)

    segments = []

    def collect(c, inherited=None):
        # collect is a nice word
        if isinstance(c, str):
            style_str = inherited.get("_style_str", "") if inherited else ""
            segments.append((c, style_str))
            return

        if inherited is None:
            inherited = {}

        text = c.get("text", "")
        color = c.get("color", inherited.get("color"))
        italic = c.get("italic", inherited.get("italic", False))
        bold = c.get("bold", inherited.get("bold", False))
        underlined = c.get("underlined", inherited.get("underlined", False))
        strikethrough = c.get("strikethrough", inherited.get("strikethrough", False))

        # gimme colour
        resolved_color = None
        if color:
            if color in COLOURS:
                resolved_color = COLOURS[color]
            elif HEX_COLOUR.match(color):
                resolved_color = color if color.startswith("#") else f"#{color}"

        # build dem parts ig
        style_parts = []
        if resolved_color:
            style_parts.append(f"color:{resolved_color}")
        if italic:
            style_parts.append("font-style:italic")
        if bold:
            style_parts.append("font-weight:bold")
        # combine the styles properly
        decorations = []
        if underlined:
            decorations.append("underline")
        if strikethrough:
            decorations.append("line-through")
        if decorations:
            style_parts.append("text-decoration:" + " ".join(decorations))

        style_str = ";".join(style_parts)  # may be empty string womp

        new_inherited = dict(inherited)
        new_inherited.update({
            "color": resolved_color or color,
            "italic": italic,
            "bold": bold,
            "underlined": underlined,
            "strikethrough": strikethrough,
            "_style_str": style_str
        })

        # append this (could be empty)
        if text:
            segments.append((text, style_str))

        # AGAIN
        for e in c.get("extra", []):
            collect(e, new_inherited)

    collect(component)

    # merge pls
    if not segments:
        return Markup("")

    merged = []
    cur_text, cur_style = segments[0]
    for t, s in segments[1:]:
        if s == cur_style:
            cur_text += t
        else:
            merged.append((cur_text, cur_style))
            cur_text, cur_style = t, s
    merged.append((cur_text, cur_style))

    # build HTML yes
    out = []
    for text, style in merged:
        if style:
            # escape text
            escaped = Markup.escape(text)
            out.append(f"<span style='{style}'>{escaped}</span>")
        else:
            out.append(Markup.escape(text))

    return Markup("".join(out))


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

@app.route("/deploy")
def start_deploy():
    # If not logged in, then log in first
    session_token = request.cookies.get("authorization.sessionToken")
    profile_uuid = request.cookies.get("profile.uuid")
    
    if session_token and profile_uuid:
        return render_template("deploy.html")
    else:
        return redirect("/login")

@app.route("/status")
def status():
    botinfo()
    return render_template("status.html",bots=data["bot"])

@app.route("/status/<bot>")
def bot_status(bot):
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(400)
    return render_template("bot_status.html",bot=data["bot"][bot],bot_name=bot)

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

@app.route("/log", methods=["POST"])
def update_log():
    import time
    
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    msg = request.json.get('value')
    room_name = request.json.get('account')
    time = time.strftime('%H:%M:%S')

    contents = [time, msg]

    print(f"[app.py] Emitting to room: {room_name}, message: {msg}") # debug
    socketio.emit('log', contents, room=room_name)

    return jsonify({"success": True, "value": contents})

# Bot get request
@app.route("/botwhat/<bot>")
def bot_instruct(bot):
    global data
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(404)
        
    try:
        return jsonify(data["bot"][bot]["do"])
    except:
        return 200

# Bot posts screenshot
@app.route("/screenshot", methods=["POST"])
def upload_screenshot():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    account = request.form.get("account")
    if account not in data["bot"]:
        return abort(404)

    if "file" not in request.files:
        abort(400, "No file uploaded")
    
    file = request.files["file"]
    file_bytes = file.read()
    encoded_image = base64.b64encode(file_bytes).decode("utf-8")

    socketio.emit(
        "screenshot",
        {"filename": file.filename, "image": encoded_image},# filename probably unused but just in case i want it
        room=account
    )

    data["bot"][account]["do"]["screenshot"] = False

    print(f"[app.py] Screenshot recieved from {account}: {file.filename}")
    return {"status": "success"}

# socketio
#

@socketio.on('connect')
def handle_connect():
    print('[app.py] Client connected')

@socketio.on('join')
def handle_join(bot_name):
    join_room(bot_name)
    print(f'[app.py] Client joined room: {bot_name}')

@socketio.on("get_screenshot")
def screenshot_request(bot):
    bot_name = bot.get("bot").strip()
    if bot_name not in data["bot"]:
        return abort(404)

    print(f"[app.py] Screenshot requested for {bot_name}")

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["screenshot"] = True
    

if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
