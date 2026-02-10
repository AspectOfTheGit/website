import eventlet
eventlet.monkey_patch()

from flask import Flask, request, render_template
from src.socket import socketio
from src.data import load_data
from src.config import CLIENT_SECRET

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        subdomain_matching=True
    )
    app.secret_key = CLIENT_SECRET

    app.config["SERVER_NAME"] = "aspectofthe.site"

    load_data()

    from src.bots.routes import bots
    from src.web.routes import web
    from src.api.storage import storage
    from src.api.debug import debug
    from src.api.tokens import token
    from src.api.discord import discord
    from src.api.world import world
    from src.api.deploy import deploy
    from src.api.voice import voice
    from src.api.utils import utils
    
    app.register_blueprint(bots)
    app.register_blueprint(web)
    app.register_blueprint(storage)
    app.register_blueprint(debug)
    app.register_blueprint(token)
    app.register_blueprint(discord)
    app.register_blueprint(world)
    app.register_blueprint(deploy)
    app.register_blueprint(voice)
    app.register_blueprint(utils)

    @app.before_request
    def before_request():
        print("HOST:", request.host)
        print("URL ROOT:", request.url_root)
        print(request.headers.get("X-Forwarded-Host"))

    @app.route("/test", subdomain="<subdomain>")
    def api_test(subdomain):
        return f"Subdomain: {subdomain}", 200

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html",error=error), 404

    socketio.init_app(app)
    return app

app = create_app()

#if __name__ == "__main__":
#    socketio.run(app, host="0.0.0.0", port=10000)
