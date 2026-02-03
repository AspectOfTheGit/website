from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    abort
)
import requests

from src.data import data
from src.utils.world_api import get_world_info
from src.utils.player_api import get_uuid
from src.discord.notify import notify
from src.bots.manager import refresh_bot_info
from src.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, VALID_BOT_PERMISSIONS

from src.utils.data_api import (
    refresh_account_info,
    create_world
)

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

# Misc

@web.route("/")
def index():
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
    if not session.get("mc_access_token"):
        return redirect("/login")

    mc_uuid = session["mc_uuid"]
    username = session["mc_username"]
    refresh_account_info(username, mc_uuid)

    return render_template(
        "account.html",
        username=username,
        account=data["account"][mc_uuid],
        mcuuid=mc_uuid,
        notifs=data["account"][mc_uuid].get("notifs", []),
        discord=data["account"][mc_uuid].get("discord", ""),
        validbotperms=VALID_BOT_PERMISSIONS
    )


@web.route("/utils")
def utilities():
    return render_template(
        "utilities.html",
        username=session.get("mc_username")
    )

# Bot Pages

@web.route("/bots")
def bots_home():
    return render_template(
        "aspectbots.html",
        username=session.get("mc_username")
    )


@web.route("/bots/deploy")
def bots_deploy():
    if not session.get("mc_access_token"):
        return redirect("/login")

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
    refresh_bot_info()
    return render_template(
        "status.html",
        bots=data["bot"],
        username=session.get("mc_username")
    )


@web.route("/bots/status/<bot>")
def bot_status(bot):
    if bot not in data["bot"]:
        abort(400)

    return render_template(
        "bot_status.html",
        bot=data["bot"][bot],
        bot_name=bot,
        username=session.get("mc_username")
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
