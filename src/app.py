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
import html

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = 1460692900533899438
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
    data = {"bot": {}, "account": {}, "world": {}}
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
    import time
    global data, timeout
    bots = ["AspectOfTheBot","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks","AspectOfTheButt","AspectOfThePoop"]
    for bot in bots:
        # Set Defaults
        data["bot"].setdefault(bot, {})
        data["bot"][bot]["uuid"] = get_uuid(bot)
        data["bot"][bot].setdefault("last_ping", 0)
        data["bot"][bot].setdefault("status", False)
        data["bot"][bot].setdefault("deployer", "")
        data["bot"][bot].setdefault("world", {})
        data["bot"][bot]["world"].setdefault("name", "")
        data["bot"][bot]["world"].setdefault("uuid", "")
        data["bot"][bot]["world"].setdefault("owner", {})
        data["bot"][bot]["world"]["owner"].setdefault("name", "")
        data["bot"][bot]["world"]["owner"].setdefault("uuid", "")
        data["bot"][bot].setdefault("do", {})
        if data["bot"][bot]["last_ping"] != 0 and time.time() - data["bot"][bot]["last_ping"] > timeout and data["bot"][bot]["status"]:
            data["bot"][bot]["status"] = False
            data["bot"][bot]["deployer"] = ""
            notify(bot, f"{bot} disconnected", "bot.disconnect")
        else:
            if data["bot"][bot]["deployer"] == "" and data["bot"][bot]["status"]:
                data["bot"][bot]["do"]["disconnect"] = True # Disconnect bot if no deployer
                contents = [time.strftime('%H:%M:%S'), f"Disconnect requested for {bot}"]
                socketio.emit('log', contents, room=bot)
            #data["bot"][bot].setdefault("world", {})
            #data["bot"][bot]["world"]["name"] = "WorldNamePlaceholder"
            #data["bot"][bot]["world"].setdefault("owner", {})
            #data["bot"][bot]["world"]["owner"]["name"] = "WorldOwnerPlaceholder"
            #data["bot"][bot]["world"]["owner"]["uuid"] = get_uuid(data["bot"][bot]["world"]["owner"]["name"])
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Refreshes account information for the current session
def refreshaccountinfo():
    global data
    mcusername = session.get("mc_username")
    mcuuid = session.get("mc_uuid")
    data.setdefault("account", {})
    data["account"].setdefault(mcuuid, {})
    data["account"][mcuuid]["username"] = mcusername
    data["account"][mcuuid].setdefault("abilities", {}) # Stores player's permissions for what they can do on the website
    data["account"][mcuuid].setdefault("storage", {}) # Stores the storage for the player's account (storage is a dictionary)
    today = datetime.now().date().isoformat()
    data["account"][mcuuid].setdefault("last_deploy", None)
    if data["account"][mcuuid]["last_deploy"] != today:
        data["account"][mcuuid]["used"] = 0

def notify(account: str, message: str, type: str):
    global data
    '''
    Send a notification to the user via Discord
    '''

    match = re.search(r"^([^.]+)", type)
    typeroot = match.group(1) if match else None

    if typeroot != "bot":
        try:
            user_id = data["account"][account]["discord"]
        except:
            return
        if type not in data["account"][account].get("notifs", []):
            return
    
    saccount = account.lower()
    saccount = re.sub(r"[^a-z0-9-_]", "-", saccount)[:90]

    headers = {"Authorization": f"Bot {DISCORD_TOKEN}","Content-Type": "application/json"}

    try:
        color = {"storage.read":0x1a81bc,
                 "storage.write":0xbc891a,
                 "storage.error":0xff0000,
                 
                 "webpage.save":0xbc891a,
                 "webpage.update":0x07eef2,
                 "webpage.view":0x43ba83,
                 "webpage.interact":0x39d455,

                 "bot.deploy":0x49ba43,
                 "bot.log":0x5c5c5c,
                 "bot.disconnect":0xff0000
                }[type]
    except:
        color = 0x5c5c5c

    channels = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers).json()
    if typeroot == "bot":
        return # Disabled this for now, probably forever
        category = next((c for c in channels if c["type"] == 4 and c["name"] == ".bots"),None)
        log_channel = next((c for c in channels
                            if c["parent_id"] == category["id"] and c["name"] == saccount),
                           None)
        if not log_channel:
            log_channel = requests.post(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers,json={"name": saccount,"parent_id": category["id"],"type": 0}).json()
        webhooks = requests.get(
            f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers).json()
        webhook = webhooks[0] if webhooks else requests.post(f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers,json={"name": saccount}).json()
        
        embed = {
            "description": message,
            "color": color
        }

        requests.post(webhook["url"],json={"embeds": [embed]})
        return
        
    category = next((c for c in channels if c["type"] == 4 and c["name"] == saccount),None)

    if not category:
        category = requests.post(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",
            headers=headers,
            json={
                "name": saccount,
                "type": 4,
                "permission_overwrites": [
                    {
                        "id": user_id,
                        "type": 1,
                        "allow": "1024",
                        "deny": "0"
                    },
                    {
                        "id": str(GUILD_ID),
                        "type": 0,
                        "allow": "0",
                        "deny": "1024"
                    }
                ]
            }
        ).json()

    log_channel = next((c for c in channels
                        if c["parent_id"] == category["id"] and c["name"] == typeroot),
                       None)
    if not log_channel:
        log_channel = requests.post(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers,json={"name": typeroot,"parent_id": category["id"],"type": 0}).json()

    webhooks = requests.get(
        f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers).json()
    webhook = webhooks[0] if webhooks else requests.post(f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers,json={"name": "Logger"}).json()
    
    ts = f"<t:{int(time.time())}:R>"
    contents = f"{ts}\n{message}"
    embed = {
        "description": contents,
        "color": color
    }

    requests.post(webhook["url"],json={"embeds": [embed]})

def createworld(world: str, account: str):
    try:# Create world page
        # Legitidev Request
        worlddata = get_world_info(world)
        print(worlddata) # debug
        if worlddata == None:
            return jsonify({"error": "World does not exist"}), 404
        if worlddata["owner_uuid"] != formatUUID(account):
            return jsonify({"error": "Unauthorized"}), 401

        data["world"][world] = {}
        data["world"][world]["owner"] = account
        data["world"][world]["elements"] = {}
        data["world"][world]["public"] = False
        data["world"][world]["title"] = worlddata["name"]

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except:
        return abort(500)

# Re-evaluate user storage size
def storagesize(account: str):
    global data
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

def formatUUID(u):
    u = u.replace("-", "").strip()
    u = (
        u[:8] + "-" +
        u[8:12] + "-" +
        u[12:16] + "-" +
        u[16:20] + "-" +
        u[20:]
    )
    return u

# Minecraft's annoying styled messages to HTML
# is what I would've said if I didnt decide to use a json serializer specific for ts
def mc_to_html(message):
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except json.JSONDecodeError:
            return html.escape(message)

    def render_part(part):
        if not isinstance(part, dict):
            return html.escape(str(part)).replace("\n", "<br>")
    
        text = html.escape(part.get("text", "")).replace("\n", "<br>")
    
        style_info = part.get("style", {})
        color = style_info.get("color")
        if isinstance(color, int):
            color = f"#{color:06X}"
    
        bold = style_info.get("isBold", False)
        italic = style_info.get("isItalic", False)
        underline = style_info.get("isUnderlined", False)
        strikethrough = style_info.get("isStrikethrough", False)
    
        styles = []
        if color:
            styles.append(f"color:{color}")
        if bold:
            styles.append("font-weight:bold")
        if italic:
            styles.append("font-style:italic")
        if underline and strikethrough:
            styles.append("text-decoration:underline line-through")
        elif underline:
            styles.append("text-decoration:underline")
        elif strikethrough:
            styles.append("text-decoration:line-through")
    
        span_start = f'<span style="{";".join(styles)}">' if styles else ""
        span_end = "</span>" if styles else ""
    
        extra_html = "".join(render_part(e) for e in part.get("extra", []))
    
        return f"{span_start}{text}{extra_html}{span_end}"

    if isinstance(message, dict) and "components" in message:
        html_output = "".join(render_part(part) for part in message["components"])
    else:
        html_output = message

    return html_output.replace("\n", "<br>")
    
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
    mcuuid = session.get("mc_uuid")
    
    if session_token and profile_uuid:
        global data
        mcusername = session.get("mc_username")
        refreshaccountinfo()
        return render_template("account.html", username=mcusername, account=data["account"][mcuuid], profile_uuid=mcuuid, notifs=data["account"][mcuuid].get("notifs", []), discord=data["account"][mcuuid].get("discord", ""))
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
    mcuuid = session.get("mc_uuid")
    
    if session_token and profile_uuid:
        mcusername = session.get("mc_username")
        refreshaccountinfo()
        refreshbotinfo()
        return render_template("deploy.html", username=mcusername, bots=data["bot"], account=data["account"][mcuuid], profile_uuid=mcuuid)
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

@app.route("/world/<world>")
def world_page(world):
    world = world.strip()
    global data

    data.setdefault("world", {})
    mcusername = session.get("mc_username")
    if world not in data["world"]:
        return jsonify({"error": "World page does not exist"}), 404
    if not mcusername:
        mcusername = ".anonymous"
    if mcusername != data["world"][world]["owner"] and not data["world"][world]["public"]:
        return jsonify({"error": "World page is private"}), 400
    
    notify(data["world"][world]["owner"], f"{world} page viewed by {mcusername}", "webpage.view")
            
    # Load world page
    return render_template("world.html", username=mcusername, world_uuid=world, elements=data["world"][world]["elements"], title=data["world"][world]["title"])

@app.route("/world/<world>/edit")
def world_edit(world):
    world = world.strip()
    global data

    data.setdefault("world", {})
    mcusername = session.get("mc_username")
    if world in data["world"]:
        if mcusername != data["world"][world]["owner"]:# Check if user owns the world
            return jsonify({"error": "Unauthorized"}), 401
    else:
        createworld(world, mcusername, session["mc_uuid"])
            
    # Load world page editor
    return render_template("world_edit.html", username=mcusername, world_uuid=world, elements=data["world"][world]["elements"], title=data["world"][world]["title"])

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

    refreshaccountinfo()

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

def botping(account):
    import time
    
    global data
    if data["bot"][account]["status"] == False:
        time = time.strftime('%H:%M:%S')
        contents = [time, f"Bot successfully online"]
        socketio.emit('log', contents, room=account)
    data["bot"][account]["status"] = True  # mark as online
    data["bot"][account]["last_ping"] = time.time()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/bots/ping", methods=["POST"])
def alive():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    botping(request.json.get("account"))
    
    return jsonify({"success": True, "status": True})

@app.route("/bots/world", methods=["POST"])
def world():
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    account = request.json.get("account")
    
    global data
    data["bot"][account].setdefault("world", {})
    data["bot"][account]["world"].setdefault("owner", {})
    if request.json.get("value") == "lobby":
        data["bot"][account]["world"]["name"] = "Lobby"
    else:
        world_data = get_world_info(request.json.get("value"))
        data["bot"][account].setdefault("world", {})
        data["bot"][account]["world"]["uuid"] = request.json.get("value")
        try:
            data["bot"][account]["world"]["name"] = raw_to_html(world_data["raw_name"])
            data["bot"][account]["world"]["owner"]["uuid"] = world_data["owner_uuid"]
            data["bot"][account]["world"]["owner"]["name"] = get_username(world_data["owner_uuid"])
        except:
            data["bot"][account]["world"]["name"] = "Error fetching world data"
            data["bot"][account]["world"]["owner"]["uuid"] = "?"
            data["bot"][account]["world"]["owner"]["name"] = "Error fetching world data"
        
    botping(bot)

    # Defaults
    permissions = ["baritone"]

    if world in data["world"]:
        if "permissions" in data["world"][world]:
            permissions = data["world"][world]["permissions"]
    
    return jsonify({"success": True, "permissions": permissions })

# Log message to bot log
@app.route("/bots/log", methods=["POST"])
def update_log():
    import time
    
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        msg = request.json.get('value')
        msg = mc_to_html(msg)
        if '[{&quot;text&quot;:&quot;' in msg:
            print("Error during bot log (parsing issue) msg:", msg)
            return 500
    except:
        print("Error during bot log (Unknown)")
        return 500
    room_name = request.json.get('account')
    time = time.strftime('%H:%M:%S')

    contents = [time, msg]

    #print(f"[app.py] Emitting to room: {room_name}, message: {msg}") # debug
    socketio.emit('log', contents, room=room_name)
    # todo - Only log player messages
    notify(room_name, msg, "bot.log")

    return jsonify({"success": True, "value": contents})

# Bot get request
@app.route("/bots/botwhat/<bot>")
def bot_instruct(bot):
    global data
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(400)
        
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
        return abort(400)

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
@app.route("/bots/done/<action>", methods=["POST"])
def botcompletes(action):
    global data
    
    token = request.headers.get("Authorization")
    if token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    account = request.json.get("account")
    if account not in data["bot"]:
        return abort(400)
        
    data["bot"][account]["do"][action] = False
    return jsonify({"success": True})

##
## API/Utilities
##

## API UTILS
#

@app.route("/api/bots/<bot>/status", methods=["GET"])
def apibotstatus(bot):
    global data
    bot = bot.strip()
    if bot not in data["bot"]:
        return abort(400)
    refreshbotinfo()
    return jsonify({"success": True, "value": data["bot"][bot]})

@app.route("/api/worldinfo", methods=["GET"])
def apiworldinfo():
    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    world_id = match.group(1) if match else None

    if not world_id:
        return jsonify({"error": "Could not get world UUID"}), 400

    try:
        worldinfo = get_world_info(world)
    except:
        return jsonify({"error": "Unknown LegitiDevs Error"}), 500

    if "name" not in worldinfo:
        return jsonify({"error": "LegitiDevs returned malformed data"}), 500
    
    return jsonify({"success": True, "value": worldinfo})

## DEPLOY API
#

@app.route("/api/deploy", methods=["POST"]) # WORK IN PROGRESS
def apideploybot():
    import time
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
    if data["bot"][bot]["status"] == True or data["bot"][bot]["deployer"] != "":
        return ({"error": "Bot is unavailable"}), 400
    # Can account deploy?
    try:
        dlimitu = int(data["account"][account]["abilities"]["uses"])
    except:
        dlimitu = 10
    try:
        dlimits = int(data["account"][account]["abilities"]["simultaneous"])
    except:
        dlimits = 1
    deployed = 0
    for botname, botdata in data["bot"].items():
        botdata.setdefault("deployer", "")
        if botdata["deployer"] == account:
            deployed += 1
    if deployed >= dlimits:
        return jsonify({"error": f"Deploy limit reached ({dlimits})"}), 400
    today = datetime.now().date().isoformat()
    try:
        if data["account"][account]["last_deploy"] != today:
            data["account"][account]["last_deploy"] = today
            data["account"][account]["used"] = 0
        if data["account"][account]["used"] >= dlimitu:
            return jsonify({"error": f"Deploy uses spent ({dlimitu})"}), 400
    except:
        data["account"][account].setdefault("last_deploy", today)
        data["account"][account].setdefault("used", 0)

    try:
        worldinfo = get_world_info(world)
        worldname = worldinfo["name"]
    except:
        worldname = "Unknown"

    # Deploy bot
    data["bot"][bot].setdefault("deployer", account)
    data["bot"][bot]["deployer"] = account
    data["bot"][bot]["do"].setdefault("deploy", {})
    data["bot"][bot]["do"]["deploy"] = {}
    data["bot"][bot]["do"]["deploy"]["world"] = world
    data["bot"][bot]["do"]["deploy"]["deployer"] = account

    data["bot"][bot]["do"]["disconnect"] = False # failsafe
    try:
        if data["account"][account]["abilities"]["abandoned"] == True:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = False
        else:
            data["bot"][bot]["do"]["deploy"]["abandoned"] = True
    except:
        data["bot"][bot]["do"]["deploy"]["abandoned"] = True
    try:
        data["bot"][bot]["do"]["deploy"]["uptime"] = data["account"][account]["abilities"]["uptime"]
    except:
        data["bot"][bot]["do"]["deploy"]["uptime"] = 30

    print(f"[app.py] {bot} deployed to {world} ({worldname}) by {account}")
    contents = [time.strftime('%H:%M:%S'), f"{bot} deployed to {world} ({worldname}) by {account}"]
    socketio.emit('log', contents, room=bot)
    notify(bot, contents[1], "bot.deploy")

    data["account"][account]["used"] += 1
    
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
                contents = [time, f"`[World {world_id}]` Write request attempted with incorrect token"]
            else:
                contents = [time, "Write request attempted with incorrect token"]
            socketio.emit('log', contents, room=account)
            notify(account, contents[1], "storage.error")
            return jsonify({"error": "Unauthorized"}), 401
    except:
        return jsonify({"error": "No Token Generated"}), 400
    # Is size over limit?
    data["account"][account].setdefault("abilities", {})
    capacity = data["account"][account]["abilities"].get("capacity", 1)
    size = len(content.encode('utf-8'))
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("capacity", {})
    data["account"][account]["storage"]["capacity"].setdefault("main", 0)
    storagesize(account)
    total = data["account"][account]["storage"]["size"] - data["account"][account]["storage"]["capacity"]["main"] + size
    # total is in bytes, capacity is in MB
    if int(total) > float(capacity) * 1024 * 1024:
        if world_id:
            contents = [time, f"`[World {world_id}]` Write request attempted with large data of {size} bytes"]
        else:
            contents = [time, f"Write request attempted with large data of {size} bytes"]
        socketio.emit('log', contents, room=account)
        notify(account, contents[1], "storage.error")
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    # Save content
    data["account"][account]["storage"]["capacity"]["main"] = size
    storagesize(account)
    data["account"][account]["storage"]["contents"] = content

    # Emit to logs
    if world_id:
        contents = [time, f"`[World {world_id}]` Successfully wrote new data to storage"]
    else:
        contents = [time, f"Successfully wrote new data to storage"]
    socketio.emit('log', contents, room=account)
    notify(account, contents[1], "storage.write")

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True})

@app.route("/api/storage/read", methods=["POST"])
def apistorageread():
    import time
    
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

    # Emit to logs
    ua = request.headers.get("User-Agent", "")
    match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
    world_id = match.group(1) if match else None

    time = time.strftime('%H:%M:%S')
    
    if world_id:
        contents = [time, f"`[World {world_id}]` Successful read request to storage"]
    else:
        contents = [time, "Successful read request to storage"]
    socketio.emit('log', contents, room=account)
    notify(account, contents[1], "storage.read")
    
    # return storage
    return jsonify({"success": True, "value": data["account"][account]["storage"]["contents"]})

@app.route("/api/storage/readkey", methods=["POST"])
def apistoragereadkey():
    import time
    
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    token = rdata.get("token", "")
    key = rdata.get("key", "")
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
        
    # return storage value from key
    try:
        storagedict = json.loads(data["account"][account]["storage"]["contents"])
        try:
            # Emit to logs
            ua = request.headers.get("User-Agent", "")
            match = re.search(r"world:([a-zA-Z0-9-]+)", ua)
            world_id = match.group(1) if match else None

            time = time.strftime('%H:%M:%S')
    
            if world_id:
                contents = [time, f"`[World {world_id}]` Successful read key request to storage"]
            else:
                contents = [time, "Successful read key request to storage"]
            socketio.emit('log', contents, room=account)
            notify(account, contents[1], "storage.read")
    
            return jsonify({"success": True, "value": storagedict[key]})
        except:
            return jsonify({"error": f"Key '{key}' not found"}), 500
    except:
        return jsonify({"error": "Could not convert to dictionary"}), 500

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
    chars = string.ascii_letters + string.digits + ''.join(c for c in string.punctuation if c not in ('"', "'"))
    new_token = ''.join(secrets.choice(chars) for _ in range(24))

    data["account"][account].setdefault("token", {})
    data["account"][account]["token"].setdefault(token, {})

    data["account"][account]["token"][token] = new_token

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"token": new_token}), 200
    
## WORLD API

@app.post("/api/world/<world>/permissions")
def apiworldbotpermissions(world):
    global data
    rdata = request.get_json()
    permissions = rdata.get("permissions", "")

    account = session["mc_username"]
    
    if not account:
        return jsonify({"error": "Unauthorized"}), 401

    if world not in data["world"]:
        createworld(world, account, session["mc_uuid"])

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401
    
    if not all(x in {"annihilate","fly"} for x in permissions):
        return jsonify({"error": "Contains invalid permission"}), 400

    data["world"][world]["permissions"] = permissions

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True})

@app.post("/api/world/<world>/edit/save/elements")
def apiworldeditelements(world):
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")

    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_username"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    # Check if over storage limit
    worldstore = "world-" + world
    data["account"][account].setdefault("abilities", {})
    capacity = data["account"][account]["abilities"].get("capacity", 1)
    size = len(content.encode('utf-8'))
    data["account"][account].setdefault("storage", {})
    data["account"][account]["storage"].setdefault("capacity", {})
    data["account"][account]["storage"]["capacity"].setdefault(worldstore, 0)
    storagesize(account)
    total = data["account"][account]["storage"]["size"] - data["account"][account]["storage"]["capacity"][worldstore] + size
    # total is in bytes, capacity is in MB
    if int(total) > float(capacity) * 1024 * 1024:
        return jsonify({"error": "Storage Limit Exceeded"}), 400

    # save here
    data["account"][account]["storage"]["capacity"][worldstore] = size
    storagesize(account)

    try:
        data["world"][world]["elements"] = content
    except:
        return jsonify({"error": "Malformed Dictionary"}), 400

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    notify(account, f"{world} elements saved", "webpage.save")

    return jsonify({"success": True}), 200

@app.post("/api/world/<world>/edit/save/settings")
def apiworldeditsettings(world):
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")

    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_username"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        for setting in content:
            if setting not in ["title","public"]:
                return jsonify({"error": f"Unknown setting '{setting}'"}), 400
            data["world"][world][setting] = content[setting]
    except:
        return jsonify({"error": "Malformed Dictionary"}), 400

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    notify(account, f"{world} settings saved", "webpage.save")

    return jsonify({"success": True}), 200

@app.post("/api/world/<world>/edit/update")
def apiworldeditupdate(world):
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    content = rdata.get("content", "")
    user = rdata.get("user", "*")

    '''
    Content: merges into the web page
     | Format: [{id:0,value:"New Text"},{id:4,color:"#FF00FF"}]
     | "id" is the target element's id. Everything else is the element's data.
    User: who to update the web page for
     | Examples: "user1", ["user2","anotheruser"], "*" (for all)
    '''

    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_username"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    if world not in data["world"]:
        return jsonify({"error": "No world page"}), 400

    if account != data["world"][world]["owner"]:
        return jsonify({"error": "Unauthorized"}), 401

    # Check if keys are valid
    for i in content:
        for key in i:
            if key not in ["id","value","color"]:
                return jsonify({"error": "Invalid key '" + key + "'"}), 400

    # update here
    emit = [user, content]
    size = len(emit.encode('utf-8'))
    # Check if over size limit
    if size > 1024 * 10:
        return jsonify({"error": "Size Limit Exceeded"}), 400
    socketio.emit('update', emit, room=worldstore) # Will be sent to everyone viewing the page, but only chosen users are affected; Unrecommended for transferring personal data

    notify(account, f"{world} recieved updates", "webpage.update")
    
    return jsonify({"success": True}), 200

# Miscellaneous (is that spelt right)

@app.post("/api/set-discord")
def apisetdiscord():
    global data
    rdata = request.get_json()
    id = rdata.get("new_id", "")

    if "mc_username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    account = session["mc_username"]

    if account not in data["account"]:
        return jsonify({"error": "Account doesn't exist"}), 400

    data["account"][account]["discord"] = id

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    # If discord notifications has been used before, change the users able to view

    headers = {"Authorization": f"Bot {DISCORD_TOKEN}","Content-Type": "application/json"}
    saccount = account.lower()

    channels = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels", headers=headers).json()
    category_id = None
    for c in channels:
        if c["type"] == 4 and c["name"] == saccount:
            category_id = c["id"]
    if not category_id:
        return jsonify({"success": True}), 200

    r = requests.get(f"https://discord.com/api/v10/channels/{category_id}", headers=headers)
    if r.status_code != 200:
        return jsonify({"success": True}), 200
    category = r.json()
    
    overwrites = category.get("permission_overwrites", [])

    everyone_overwrite = next((o for o in overwrites if o["type"] == 0), None)
    if not everyone_overwrite:
        requests.patch(
            f"https://discord.com/api/v10/channels/{category_id}",
            headers=headers,
            json={
                "permission_overwrites": [
                    {
                        "id": str(GUILD_ID),
                        "type": 0,
                        "allow": "0",
                        "deny": "1024"
                    }
                ]
            }
        )

    for overwrite in overwrites:
        if overwrite["type"] == 1:
            requests.delete(f"https://discord.com/api/v10/channels/{category_id}/permissions/{overwrite['id']}", headers=headers)

    requests.put(
        f"https://discord.com/api/v10/channels/{category_id}/permissions/{id}",
        headers=headers,
        json={
            "type": 1,
            "allow": "1024",
            "deny": "0"
        }
    )

    return jsonify({"success": True}), 200

@app.post("/api/set-notifs")
def apisetnotifs():
    global data
    rdata = request.get_json()
    prefs = rdata.get("prefs", "")

    account = session["mc_username"]
    
    if not account:
        return jsonify({"error": "Unauthorized"}), 401
    
    if not all(x in {"storage.read","storage.write","storage.error","webpage.view","webpage.update","webpage.interact","webpage.save"} for x in prefs):
        return jsonify({"error": "Contains invalid notification type"}), 400

    data["account"][account]["notifs"] = prefs

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True})

## debug or other stuff

@app.route("/api/permission", methods=["POST"])
def changeaccountpermission():
    global data
    rdata = request.get_json()
    account = rdata.get("account", "")
    permission = rdata.get("permission", "")
    value = rdata.get("value", "")
    type = rdata.get("type", "string")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data["account"].setdefault(account, {})
    data["account"][account].setdefault("abilities", {})
    if type == "integer":
        data["account"][account]["abilities"][permission] = int(value)
    else:
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

    return jsonify({"success": True}), 200

@app.route("/api/deleteworlddata", methods=["POST"])
def deleteworldpage():
    global data
    rdata = request.get_json()
    world = rdata.get("world", "")
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if world not in data["world"] and world != "*":
        return jsonify({"error": "World page doesn't exist"}), 400
        
    if world == "*":
        data["world"] = {}
    else:
        del data["world"][world]

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"success": True}), 200

@app.route("/api/getdata", methods=["POST"])
def debug_getdata():
    global data
    rdata = request.get_json()
    token = rdata.get("token", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    refreshbotinfo()

    return jsonify({"success": True, "value": data}), 200

# i dont havr access to computer rn
@app.route("/api/forcelogin", methods=["POST"])
def debug_forcelogin():
    global data
    rdata = request.get_json()
    token = rdata.get("token", "")
    account = rdata.get("account", "")

    if token != OTHER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    session["mc_username"] = account
    session["mc_uuid"] = get_uuid(account)
    session["mc_access_token"] = True

    refreshaccountinfo()

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
        return abort(400)

    print(f"[app.py] Screenshot requested for {bot_name}")

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["screenshot"] = True


if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
