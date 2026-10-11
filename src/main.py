import signal
import atexit
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, render_template
from flask.sessions import SecureCookieSessionInterface
from flask_cors import CORS
from src.socket import socketio
from src.data import flush_data
from src.config import CLIENT_SECRET
from src.voice_relay.main import init_voice_relay, shutdown_voice_relay


class DomainAliasMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        original_host = environ.get("HTTP_HOST", environ.get("SERVER_NAME", ""))
        host, separator, port = original_host.partition(":")
        host = host.lower()
        if host == "aspectofthe.site" or host.endswith(".aspectofthe.site"):
            environ["ORIGINAL_HTTP_HOST"] = original_host
            host = f"{host[:-len('site')]}website"
            environ["HTTP_HOST"] = f"{host}{separator}{port}"
            environ["SERVER_NAME"] = host

        return self.app(environ, start_response)


class DomainSessionInterface(SecureCookieSessionInterface):
    def get_cookie_domain(self, app):
        host = request.environ.get("ORIGINAL_HTTP_HOST", request.host).split(":", 1)[0].lower()
        if host == "aspectofthe.site" or host.endswith(".aspectofthe.site"):
            return ".aspectofthe.site"
        return app.config["SESSION_COOKIE_DOMAIN"] or ".aspectofthe.website"


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        subdomain_matching=True
    )

    app.secret_key = CLIENT_SECRET

    app.config.update(
        SERVER_NAME="aspectofthe.website",
        SESSION_COOKIE_DOMAIN=None,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="None",
    )

    app.session_interface = DomainSessionInterface()
    app.wsgi_app = ProxyFix(DomainAliasMiddleware(app.wsgi_app), x_proto=1, x_host=1)

    @app.context_processor
    def domain_context():
        host = request.environ.get("ORIGINAL_HTTP_HOST", request.host).split(":", 1)[0].lower()
        legacy_domain = host == "aspectofthe.site" or host.endswith(".aspectofthe.site")
        site_domain = "aspectofthe.site" if legacy_domain else "aspectofthe.website"
        return {
            "is_legacy_domain": legacy_domain,
            "api_base_url": f"https://api.{site_domain}",
            "site_domain": site_domain,
        }

    CORS(
        app,
        supports_credentials=True,
        origins=[
            "https://aspectofthe.website",
            "https://api.aspectofthe.website",
            "https://aspectofthe.site",
            "https://api.aspectofthe.site",
        ]
    )

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

    def _emit_voice_relay_signal(sid, event, payload):
        print(f"[main.py] Voice relay signal -> sid={sid} event={event}")
        socketio.emit(event, payload, to=sid, namespace="/")

    init_voice_relay(_emit_voice_relay_signal)
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
