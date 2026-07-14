import signal
import atexit
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, render_template
from flask_cors import CORS
from src.socket import socketio
from src.data import load_data, flush_data
from src.config import CLIENT_SECRET
from src.voice_relay.main import init_voice_relay, shutdown_voice_relay

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        subdomain_matching=True
    )

    app.secret_key = CLIENT_SECRET

    app.config.update(
        SERVER_NAME="aspectofthe.site",
        SESSION_COOKIE_DOMAIN=".aspectofthe.site",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="None",
    )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    CORS(
        app,
        supports_credentials=True,
        origins=[
            "https://aspectofthe.site",
            "https://api.aspectofthe.site",
        ]
    )

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

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html",error=error), 404

    socketio.init_app(app)
    init_voice_relay(lambda sid, event, payload: socketio.emit(event, payload, room=sid))
    return app

app = create_app()

atexit.register(flush_data)
atexit.register(shutdown_voice_relay)

def _shutdown_handler(*_args):
    shutdown_voice_relay()
    flush_data()
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _shutdown_handler)

#if __name__ == "__main__":
#    socketio.run(app, host="0.0.0.0", port=10000)
