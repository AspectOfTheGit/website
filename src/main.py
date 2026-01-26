import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO
from app.data import load_data

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

def create_app():
    app = Flask(__name__)
    app.secret_key = "..."

    load_data()

    from app.bots.routes import bots_bp
    app.register_blueprint(bots_bp)

    socketio.init_app(app)
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
