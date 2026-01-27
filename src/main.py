import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO
from src.data import load_data
from src.config import CLIENT_SECRET

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )
    app.secret_key = CLIENT_SECRET

    load_data()

    from src.bots.routes import bots
    from src.web.routes import web
    from src.api.storage import storage
    app.register_blueprint(bots)
    app.register_blueprint(web)
    app.register_blueprint(storage)

    socketio.init_app(app)
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
