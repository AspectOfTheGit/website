from flask import session
from flask_socketio import SocketIO, emit, join_room
from src.discord.notify import notify
from src.data import data
from src.config import BOTS
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
    username = session.gwt("mc_username", ".anonymous")
    if room not in BOTS and ussrname != room:
        print(f"[socket.py] {username} failed to join room (Unauthorized): {room} ")
        return
            
    join_room(room)
    print(f'[socket.py] {username} joined room: {room}')

@socketio.on("get_screenshot")
def screenshot_request(rdata):
    bot_name = rdata.get("bot").strip()
    if bot_name not in data["bot"]:
        return

    print(f"[socket.py] Screenshot requested for {bot_name}")

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["screenshot"] = True

@socketio.on("bot_disconnect")
def disconnect_request(rdata):
    bot_name = rdata.get("bot").strip()
    if bot_name not in data["bot"]:
        return

    if "mc_uuid" not in session:
        return

    if session["mc_uuid"] != data["bot"][bot_name]["deployer"]:
        return

    print(f"[socket.py] Disconnect requested for {bot_name}")

    emit_log('log', "Disconnected; requested by deployer.", bot_name)

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["disconnect"] = True

@socketio.on("bot_switch_server")
def switch_request(rdata):
    bot_name = rdata.get("bot").strip()
    world_uuid = rdata.get("world").strip()
    if bot_name not in data["bot"]:
        return

    if "mc_uuid" not in session:
        return

    if session["mc_uuid"] != data["bot"][bot_name]["deployer"]:
        return

    print(f"[socket.py] Server switch for {bot_name} | World: {world_uuid}")

    emit_log('log', "Switching server; requested by deployer.", bot_name)

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["switch"] = world_uuid
