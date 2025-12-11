import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, session, make_response, jsonify, Response, send_file, abort
from flask_socketio import SocketIO, emit, join_room
import os
import requests
import time
from datetime import datetime, timedelta
import json
import re
from markupsafe import Markup
import threading
import base64
import secrets
import string

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
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
        #print(data)
except:
    data = {"bot": {}, "account": {}}
    os.makedirs("/data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    #print("No file found")

#
## FUNCTIONS
#

# Refresh the bot information for all bots:
# Bot array, Status, uuid
def refreshbotinfo():
    global data, timeout
    bots = ["AspectOfTheBot","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks","AspectOfTheButt","AspectOfThePoop"]
    for bot in bots:
        data["bot"].setdefault(bot, {})
        if data["bot"][bot]["last_ping"] != 0 and time.time() - data["bot"][bot]["last_ping"] > timeout:
            data["bot"][bot]["status"] = False
            data["bot"][bot]["deployer"] = ""
        else:
            data["bot"][bot]["uuid"] = get_uuid(bot)
            if data["bot"][bot]["deployer"] == "":
                data["bot"][bot]["do"]["disconnect"] == True # Disconnect bot if no deployer
            #data["bot"][bot].setdefault("world", {})
            #data["bot"][bot]["world"]["name"] = "WorldNamePlaceholder"
            #data["bot"][bot]["world"].setdefault("owner", {})
            #data["bot"][bot]["world"]["owner"]["name"] = "WorldOwnerPlaceholder"
            #data["bot"][bot]["world"]["owner"]["uuid"] = get_uuid(data["bot"][bot]["world"]["owner"]["name"])
        with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)

# Use legitidevs to get world info
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

# Use ashcon api to get username from uuid
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

# Get HTML from raw json text
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

# Get username from uuid using mojang api
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

#
## MAIN ROUTES
#

@app.route("/")
def index():
    mcusername = session.get("mc_username")
    return render_template("index.html", username=mcusername)

@app.route("/account")
def accountpage():
    session_token = session.get("mc_access_token")
    profile_uuid = session.get("mc_uuid")
    
    if session_token and profile_uuid:
        global data
        mcusername = session.get("mc_username")
        data.setdefault("account", {})
        data["account"].setdefault(mcusername, {})
        data["account"][mcusername].setdefault("abilities", {}) # Stores player's permissions for what they can do on the website
        data["account"][mcusername].setdefault("storage", {}) # Stores the storage for the player's account (storage is a dictionary)
        return render_template("account.html", username=mcusername, account=data["account"][mcusername])
    else:
        return redirect("/login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/utils")
def utilities():
    mcusername = session.get("mc_username")
    return render_template("utilities.html", username=mcusername)
    
@app.route("/bots")
def home():
    mcusername = session.get("mc_username")
    return render_template("aspectbots.html", username=mcusername)

@app.route("/bots/deploy")
def start_deploy():
    # If not logged in, then log in first
    session_token = session.get("mc_access_token")
    profile_uuid = session.get("mc_uuid")
    
    if session_token and profile_uuid:
        mcusername = session.get("mc_username")
        refreshbotinfo()
        return render_template("deploy.html", username=mcusername, bots=data["bot"], account=data["account"][mcusername], profile_uuid=profile_uuid)
    else:
        return redirect("/login")

@app.route("/bots/status")
def status():
    refreshbotinfo()
    mcusername = session.get("mc_username")
    return render_template("status.html", bots=data["bot"], username=mcusername)

@app.route("/bots/status/<bot>")
def bot_status(bot):
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(400)
    mcusername = session.get("mc_username")
    return render_template("bot_status.html", bot=data["bot"][bot], bot_name=bot, username=mcusername)

@app.route("/login")
def mc_login():
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
        data=mc_auth_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    ).json()

    if mc_auth_response.get("error"):
        return "Error while attempting login", 500

    session['mc_access_token'] = mc_auth_response["access_token"]
    session['mc_username'] = mc_auth_response["data"]["profile"]["name"]
    session['mc_uuid'] = mc_auth_response["data"]["profile"]["id"]

    return redirect("/")

#
## BOT ROUTES
#

'''
| ROUTES for the bots
All POST routes relating to the bot will require headers:
 - Authorization (Bot token)
 - account (The bot account the request is sent from)

/ping (POST)
Recieved every ~1 seconds from each bot account
Sets status of bot to online
If not recieved for 10 seconds (indicated by timeout variable), status is set offline

/world (POST)
 - value (World UUID or 'lobby')
Recieved whenever bot connects to a server
Sets the world that the bot is currently in

/log (POST)
 - value (Message recieved)
Recieved whenever the bot recieves a message
Sends the message to the bot log

/screenshot (POST)
Includes screenshot file
Recieved whenever a screenshot is requested for the bot
May have a delay of ~3 seconds
Sends the screenshot to the bot log

/botwhat/<account>
Requested every ~5 seconds by each bot account
Tells each bot what to do (e.g. take a screenshot)

/done/<action>
Recieved whenever the bot completes a request
(Doesnt include screenshot)
When recieved, updates todo for bot.
'''
# check bot alive or somethi
timeout = 10

@app.route("/bots/ping", methods=["POST"])
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

@app.route("/bots/world", methods=["POST"])
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

# Log message to bot log
@app.route("/bots/log", methods=["POST"])
def update_log():
    import time
    
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    msg = request.json.get('value')
    room_name = request.json.get('account')
    time = time.strftime('%H:%M:%S')

    contents = [time, msg]

    #print(f"[app.py] Emitting to room: {room_name}, message: {msg}") # debug
    socketio.emit('log', contents, room=room_name)

    return jsonify({"success": True, "value": contents})

# Bot get request
@app.route("/bots/botwhat/<bot>")
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
@app.route("/bots/screenshot", methods=["POST"])
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

# Bot completes instruction
@app.route("/bots/done/<action>")
def botcompletes(action):
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    account = request.form.get("account")
    if account not in data["bot"]:
        return abort(404)
        
    data["bot"][account]["do"][action] = False
    return jsonify({"success": True})

##
## API/Utilities
##

## BOT API
#

@app.route("/api/bots/<bot>/status", methods=["GET"])
def apibotstatus(bot):
    global data
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(400)
    refreshbotinfo()
    return jsonify({"success": True, "value": data["bot"][bot]})

## DEPLOY API
#

@app.route("/api/deploy", methods=["POST"]) # WORK IN PROGRESS
def apideploybot():
    global data
    
    rdata = request.get_json()
    bot = rdata.get("bot", "")
    world = rdata.get("world", "")
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
    # Does token match?
    try:
        if token != data["account"][account]["token"]["deploy"]:
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400
    refreshbotinfo()
    # Bot exists?
    if bot not in data["bot"]:
        return jsonify({"error": "Bot doesn't exist"}), 400
    # Is bot in use?
    if data["bot"][bot]["status"] == True:
        return ({"error": "Bot is unavailable"}), 400
    # Can account deploy?
    try:
        dlimitu = data["account"][account]["abilities"]["uses"]
    except:
        dlimitu = 10
    try:
        dlimits = data["account"][account]["abilities"]["simultaneous"]
    except:
        dlimits = 1
    deployed = 0
    for botname, botdata in data["bot"].items():
        botdata.setdefault("deployer", "")
        if botdata["deployer"] == account:
            deployed += 1
    if deployed >= dlimits:
        return jsonify({"error": f"Deploy limit reached ({dlimits})"}), 400
    try:
        if data["account"][account]["used"] >= dlimitu:
            return jsonify({"error": f"Deploy uses spent ({dlimitu})"}), 400
    except:
        data["account"][account].setdefault("used", 0)

    try:
        worldinfo = getworldinfo(world)
        worldname = worldinfo["name"]
    except:
        worldname = "Unknown"

    # Deploy bot
    data["bot"][bot].setdefault("deployer", "")
    data["bot"][bot]["deployer"] = account
    data["account"][account]["used"] += 1
    data["bot"][bot]["do"].setdefault("deploy", {})
    data["bot"][bot]["do"]["deploy"]["world"] = world
    try:
        if data["account"][account]["abilities"]["abandoned"] == True:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = -999
        else:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = 1
    except:
        data["bot"][bot]["do"]["deploy"]["abandoned"] = 1
    try:
        data["bot"][bot]["do"]["deploy"]["uptime"] = data["account"][account]["abilities"]["uptime"]
    except:
        data["bot"][bot]["do"]["deploy"]["uptime"] = 30

    print(f"[app.py] {bot} deployed to {world} ({worldname}) by {account}")
    
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True, "value": {"name": worldname}})

## STORAGE API
#

@app.route("/api/storage/write", methods=["POST"])
def apistoragewrite():
    import time

    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    world_id = match.group(1) if match else None
    
    global data
    rdata = request.get_json()
    content = rdata.get("contents", "")
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400
    time = time.strftime('%H:%M:%S')
    # Does token match?
    try:
        if token != data["account"][account]["token"]["write"]:
            if world_id:
                contents = [time, f"[World {world_id}] Write request attempted with incorrect token"]
            else:
                contents = [time, "Write request attempted with incorrect token"]
            socketio.emit('log', contents, room=account)
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400
    # Is size over limit?
    data["account"][account].setdefault("abilities", {})
    capacity = data["account"][account]["abilities"].get("capacity", 1)
    size = len(content.encode('utf-8'))
    if size > capacity * 1024 * 1024:
        if world_id:
            contents = [time, f"[World {world_id}] Write request attempted with large data of {size} bytes"]
        else:
            contents = [time, f"Write request attempted with large data of {size} bytes"]
        socketio.emit('log', contents, room=account)
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    # Save content
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("contents", "")
    data["account"][account]["storage"]["contents"] = content

    # Emit to logs
    if world_id:
        contents = [time, f"[World {world_id}] Successfully wrote to storage: {content}"]
    else:
        contents = [time, f"Successfully wrote to storage: {content}"]
    socketio.emit('log', contents, room=account)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True})

@app.route("/api/storage/read", methods=["POST"])
def apistorageread():
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    # Does account exist?
    if account not in data["account"]:
        #print("Account doesn't exist") # debug
        return jsonify({"error": "Account doesn't exist"}), 400
    # Does token match?
    try:
        if token != data["account"][account]["token"]["read"]:
            #print("Incorrect token") # debug
            return jsonify({"error": "Unauthorized"}), 401
    except:
        #print("No token generated") # debug
        return jsonify({"error": "No Token Generated"}), 400
        
    # return storage
    return jsonify({"success": True, "value": data["account"][account]["storage"]["contents"]})

## TOKENS

@app.post("/api/refresh-token/<token>")
def apirefreshtoken(token):
    global data

    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_username"]

    if account not in data["account"]:
        #print("Account doesn't exist")
        return jsonify({"error": "Account doesn't exist"}), 400

    if token not in ["write", "read", "deploy"]:
        #print("Invalid token type")
        return jsonify({"error": "Invalid Token Type"}), 400

    # generate new token
    chars = string.ascii_letters + string.digits + string.punctuation
    new_token = ''.join(secrets.choice(chars) for _ in range(24))

    data["account"][account].setdefault("token", {})
    data["account"][account]["token"].setdefault(token, {})

    data["account"][account]["token"][token] = new_token

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"token": new_token}), 200

## debug or other stuff

@app.route("/api/permission", methods=["POST"])
def changeaccountpermission():
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    permission = rdata.get("permission", "")
    value = rdata.get("value", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data["account"].setdefault(account, {})
    data["account"][account].setdefault("abilities", {})
    data["account"][account]["abilities"][permission] = value

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True}), 200

@app.route("/api/deletebotdata", methods=["POST"])
def deletebotdata():
    global data
    rdata = request.get_json()
    bot = rdata.get("bot", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if bot not in data["bot"] and bot != "*":
        return jsonify({"error": "Bot doesn't exist"}), 400
        
    if bot == "*":
        data["bot"] = {}
    else:
        data["bot"][bot] = {}

    refreshbotinfo()

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True}), 200
    
#
# socketio
#

@socketio.on('connect')
def handle_connect():
    print('[app.py] Client connected')

@socketio.on('join')
def handle_join(room):
    join_room(room)
    print(f'[app.py] Client joined room: {room}')

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
