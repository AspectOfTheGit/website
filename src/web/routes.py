from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    abort,
    current_app,
    send_file
)
import requests
import time
import os

from src.data import data, save_data
from src.discord.notify import notify
from src.bots.manager import refresh_bot_info
from src.config import OTHER_TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, DEFAULT_ABILITIES, VALID_BOT_PERMISSIONS, MAX_TIME_TILL_VOICE_ROOM_CLOSE, DATAPACK_TEMPLATE_FILE, VOICE_SPATIAL_MAX_DISTANCE, VOICE_SPATIAL_MIN_GAIN, get_voice_webrtc_ice_servers
from src.api.voice import voice_rooms

from src.utils.data_api import (
    refresh_account_info,
    create_world
)
from src.utils.world_api import get_world_info
from src.utils.text_api import raw_to_html

web = Blueprint(
    "web",
    __name__
)

AUTH_REQ_URL = (
    "https://mc-auth.com/oAuth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=profile"
    "&response_type=code"
)

uuid_auth = {}


def openWebsite(account):
    if data["account"][account].get("flag", {}).get("0", True) == False:
        data["account"][account].setdefault("flag", {})
        data["account"][account]["flag"]["0"] = True

        save_data()

        text = "It seems^2 you have^1 everything.&Visit %ec47b834-bf42-4761-b3a9-3b9b5018f142,^4 I will be waiting."
        for world_uuid in data["egg"].keys():
            visited = data["account"][account]["man"].get(world_uuid, False)
            if visited == False:
                match world_uuid:
                    case "6c4e4446-9974-4334-a423-92d6c52e97c6":# The Tower
                        text = "What you seek,^2 or not,^2 lies under %6c4e4446-9974-4334-a423-92d6c52e97c6.^4&Follow the path of candles to the fake altar."
                        break
                    case "93d2aa1d-7eb4-426c-879e-e5ec955d91c4":# Forgotten Rooms
                        text = "What you seek,^2 or not,^2 lies within the %93d2aa1d-7eb4-426c-879e-e5ec955d91c4.^4&&From the lamppost to the mineshaft,^2&Past the flipped house, to the null room.^4&&Find the room of sea lanterns, and fall from the cobble path.^4&A distortion lies north in the void, an invisible doorway..."
                        break
                    case _: # this should only show if I forget to add a world here
                        text = "Hmm, you are missing something^1.^2.^3.^5&&Yet,^4 Not even I know what it is.^6&Interesting^1.^3.^5.^5&Perhaps you should return later."
                        break

        return render_template("man.html", text=text)
    return None
    

# Misc

@web.route("/")
def index():
    open_result = open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result
    if open_result is not None:
        return open_result
    
    return render_template(
        "index.html",
        username=session.get("mc_username")
    )


@web.route("/login")
def login():
    code = request.args.get("code")
    if not code:
        return redirect(AUTH_REQ_URL)

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    r = requests.post(
        "https://mc-auth.com/oAuth2/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    ).json()

    if r.get("error"):
        return "Login failed", 500

    mc_username = r["data"]["profile"]["name"]
    mc_uuid = r["data"]["profile"]["id"]

    session["mc_access_token"] = r["access_token"]
    session["mc_username"] = mc_username
    session["mc_uuid"] = mc_uuid

    refresh_account_info(mc_username, mc_uuid)
    return redirect("/")


@web.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@web.route("/account")
def account():
    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result

    if not session.get("mc_access_token"):
        return redirect("/login")

    mc_uuid = session["mc_uuid"]
    username = session["mc_username"]
    refresh_account_info(username, mc_uuid)
    trusted=data["account"][mc_uuid].get("trusted",False)

    return render_template(
        "account.html",
        username=username,
        account=data["account"][mc_uuid],
        mcuuid=mc_uuid,
        notifs=data["account"][mc_uuid].get("notifs", []),
        discord=data["account"][mc_uuid].get("discord", ""),
        validbotperms=VALID_BOT_PERMISSIONS,
        trusted=trusted
    )


@web.route("/utils")
def utilities():
    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result
    
    return render_template(
        "utilities.html",
        username=session.get("mc_username")
    )


@web.route("/discord")
def discord():
    return redirect("https://discord.gg/MwNxGuGK6T")


@web.route("/voice/datapack")
def voice_datapack_template_download():
    static_dir = current_app.static_folder
    template_path = os.path.join(static_dir, DATAPACK_TEMPLATE_FILE)

    if not os.path.isfile(template_path):
        return jsonify({"error": "Template datapack not configured"}), 404

    return send_file(
        template_path,
        as_attachment=True,
        download_name="Voice-Chat-Datapack.zip",
        mimetype="application/zip",
        max_age=0
    )


@web.route("/debug")
def debug_page():
    if not session.get("mc_access_token"):
            return redirect("/login")
    
    mc_uuid = session["mc_uuid"]

    if mc_uuid == "758482853e864d0b807e94bc452fdf02":
        return render_template("debug.html", token=OTHER_TOKEN, abilitydefaults=DEFAULT_ABILITIES)


# Bot Pages

@web.route("/bots")
def bots_home():
    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result
    
    return render_template(
        "aspectbots.html",
        username=session.get("mc_username")
    )


@web.route("/bots/deploy")
def bots_deploy():
    if not session.get("mc_access_token"):
        return redirect("/login")

    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result

    refresh_account_info(session["mc_username"], session["mc_uuid"])
    refresh_bot_info()

    return render_template(
        "deploy.html",
        username=session["mc_username"],
        bots=data["bot"],
        account=data["account"][session["mc_uuid"]],
        mcuuid=session["mc_uuid"]
    )


@web.route("/bots/status")
def bots_status():
    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result

    refresh_bot_info()
    return render_template(
        "status.html",
        bots=data["bot"],
        username=session.get("mc_username")
    )


@web.route("/bots/status/<bot>")
def bot_status(bot):
    open_result = openWebsite(session["mc_uuid"]) if session.get("mc_uuid") else None
    if open_result is not None:
        return open_result
    
    if bot not in data["bot"]:
        abort(400)

    is_deployer = 'deployer' in request.args

    if not is_deployer and session.get("mc_uuid",None) == data["bot"][bot]["deployer"]:
        return redirect(f"/bots/status/{bot}?deployer")

    if session.get("mc_uuid","") in data["account"]:
        if data["account"][session.get("mc_uuid",None)]["abilities"].get("send",False) in [True,"true"]:
            can_chat = True
        elif DEFAULT_ABILITIES["send"] == True:
            can_chat = True
        else:
            can_chat = False
    else:
        can_chat = False

    return render_template(
        "bot_status.html",
        bot=data["bot"][bot],
        bot_name=bot,
        username=session.get("mc_username"),
        is_deployer=is_deployer,
        can_chat=can_chat
    )


# World Pages

@web.route("/world/<world>")
def world_page(world):
    world = world.strip()
    data.setdefault("world", {})

    redirectifnone = request.args.get('redirectifnone', False)

    if world not in data["world"]:
        if redirectifnone:
            return redirect(f"https://legiti.dev/browse/{world}")
        else:
            return jsonify({"error": "World page does not exist"}), 404

    username = session.get("mc_username", ".anonymous")
    uuid = session.get("mc_uuid")

    if (
        uuid != data["world"][world]["owner"]
        and not data["world"][world]["public"]
    ):
        if redirectifnone:
            return redirect(f"https://legiti.dev/browse/{world}")
        else:
            return jsonify({"error": "World page is private"}), 400

    notify(
        data["world"][world]["owner"],
        f"{world} page viewed by {username}",
        "webpage.view"
    )

    return render_template(
        "world.html",
        username=username,
        world_uuid=world,
        elements=data["world"][world]["elements"],
        title=data["world"][world]["title"]
    )


@web.route("/world/<world>/edit")
def world_edit(world):
    world = world.strip()

    if not session.get("mc_access_token"):
        return redirect("/login")

    data.setdefault("world", {})

    if world in data["world"]:
        if session["mc_uuid"] != data["world"][world]["owner"]:
            return jsonify({"error": "Unauthorized"}), 401
    else:
        create_world(world, session["mc_uuid"])

    return render_template(
        "world_edit.html",
        username=session["mc_username"],
        world_uuid=world,
        elements=data["world"][world]["elements"],
        title=data["world"][world]["title"]
    )


# Voice Rooms

@web.route("/voice/<world>")
def voice_room(world):
    world = world.strip()

    auth = request.args.get('auth', False)
    
    if not auth:
        return jsonify({"error": "Unauthorized"}), 401

    data.setdefault("world", {})

    if world not in data["world"]:
        return jsonify({"error": "Voice room not found"}), 400

    if world not in voice_rooms or "players" not in voice_rooms[world]:
        return jsonify({"error": "Voice room not active"}), 400

    uuid=next((p["uuid"] for p in voice_rooms[world]["players"] if p["auth"] == auth), None)

    if uuid == None:
        return jsonify({"error": "Unauthorized"}), 401

    timediff = (time.time_ns() // 1000000) - data["world"][world].get("voice",0)
    if timediff > MAX_TIME_TILL_VOICE_ROOM_CLOSE: # If voice room hasn't recieved an update recently
        return jsonify({"error": f"Voice room closed (since {timediff-MAX_TIME_TILL_VOICE_ROOM_CLOSE}ms ago)"}), 400
    
    # Store uuid and auth for socket connection (storing in session is a security risk as world might use session maliciously and can access their entire account)
    uuid_auth[uuid] = auth

    world_display_name = world
    world_data = get_world_info(world)
    try:
        if world_data and world_data.get("raw_name"):
            world_display_name = raw_to_html(world_data["raw_name"])
        elif world_data and world_data.get("name"):
            world_display_name = world_data["name"]
    except Exception:
        world_display_name = world

    return render_template(
        "voice_room.html",
        username=session.get("mc_username"),
        mc_uuid=uuid,
        world_uuid=world,
        world_display_name=world_display_name,
        auth=auth,
        voice_spatial_max_distance=VOICE_SPATIAL_MAX_DISTANCE,
        voice_spatial_min_gain=VOICE_SPATIAL_MIN_GAIN,
        voice_webrtc_ice_servers=get_voice_webrtc_ice_servers(),
    )
