from flask_socketio import SocketIO, emit, join_room
from src.discord.notify import notify
from src.data import data
import time

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")


#

def emit_storage_log(account, message, event, world_id=None):
    ts = time.strftime('%H:%M:%S')
    prefix = f"`[World {world_id}]`" if world_id else ""
    contents = [ts, f"{prefix} {message}"]

    socketio.emit("log", contents, room=account)
    notify(account, contents[1], event)
    print(f"[socket.py] Emitted storage log to '{account}': {contents[1]}")

def emit_log(type, contents, room, notify=False, event=None):
    socketio.emit(type, contents, room=room)
    if notify:
        notify(room, contents[1], event)
    print(f"[socket.py] Emitted log to '{room}'")


# Events

@socketio.on('connect')
def handle_connect():
    print('[socket.py] Client connected')

@socketio.on('join')
def handle_join(room):
    join_room(room)
    print(f'[socket.py] Client joined room: {room}')

@socketio.on("get_screenshot")
def screenshot_request(bot):
    bot_name = bot.get("bot").strip()
    if bot_name not in data["bot"]:
        return abort(400)

    print(f"[socket.py] Screenshot requested for {bot_name}")

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["screenshot"] = True

@socketio.on("get_screenshot")
def screenshot_request(bot, account, token):
    bot_name = bot.get("bot").strip()
    if bot_name not in data["bot"]:
        return abort(400)

    if account != data["bot"][bot_name]["deployer"]:
        return abort(401)

    if token != data["account"][account]["token"]["deploy"]:
        return abort(401)

    print(f"[socket.py] Disconnect requested for {bot_name}")

    emit_log('log', "Disconnected; requested by deployer.", bot_name)

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["disconnect"] = True
