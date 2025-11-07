from flask import Flask, render_template, request, redirect, session, make_response, jsonify
import os
import requests

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = "https://aspectofthe.site/loggedin"

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/loggedin")
def loggedin():
    code = request.args.get("code")
    resp = requests.post("https://mc-auth.com/api/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    })
    user_data = resp.json()
    session["mc_user"] = user_data
    return f"Logged in as {user_data['username']}"
