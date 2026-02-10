import eventlet
eventlet.monkey_patch()

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from src.socket import socketio
from src.data import load_data
from src.config import CLIENT_SECRET

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )
    app.secret_key = CLIENT_SECRET

    app.config["SERVER_NAME"] = "aspectofthe.site"

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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

    @app.route("/test", subdomain="api")
    def api_test():
        return "api subdomain works"

    socketio.init_app(app)
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
