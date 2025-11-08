from flask import Flask, render_template, request, redirect, session, make_response, jsonify
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
    data = {}
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# check bot alive or somethi
timeout = 5

@app.route("/ping", methods=["POST"])
def alive():
    global data
    data["bot"]["AspectOfTheBot"]["status"] = "online"  # mark as online
    data["bot"]["AspectOfTheBot"]["last_ping"] = time.time()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"success": True, "status": "online"})

def botinfo():
    global data, timeout
    bots = ["AspectOfTheBot","AspectOfThePoop"]
    for bot in bots:
        if data["bot"][bot]["last_ping"] != 0 and time.time() - data["bot"][bot]["last_ping"] > timeout:
            data["bot"][bot]["status"] = "offline"
        data["bot"][bot]["world"]["name"] = "World Name Placeholder"
        data["bot"][bot]["world"]["owner"] = "World Owner Placeholder"
        with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)

#######################
@app.route("/")
def home():
    return render_template("index.html")

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
