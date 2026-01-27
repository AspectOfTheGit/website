from flask_socketio import SocketIO
from src.discord.notify import notify
import time

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")


#

def emit_storage_log(account, message, event, world_id=None):
    ts = time.strftime('%H:%M:%S')
    prefix = f"`[World {world_id}]` " if world_id else ""
    contents = [ts, f"{prefix} {message}"]

    socketio.emit("log", contents, room=account)
    notify(account, contents[1], event)

def emit_log(type, contents, room, notify=False, event=None):
    socketio.emit(type, contents, room=room)
    if notify:
        notify(room, contents[1], event)


# Events

@socketio.on('connect')
def handle_connect():
    print('[app.py] Client connected')

@socketio.on('join')
def handle_join(room):
    join_room(room)
    print(f'[app.py] Client joined room: {room}')

@socketio.on("get_screenshot")
def screenshot_request(bot):
    bot_name = bot.get("bot").strip()
    if bot_name not in data["bot"]:
        return abort(400)

    print(f"[app.py] Screenshot requested for {bot_name}")

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["screenshot"] = True
