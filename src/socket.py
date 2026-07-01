from flask import session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from src.discord.notify import notify
from src.data import data, save_data
from src.config import BOTS, DEFAULT_ABILITIES, WHITELISTED_COMMANDS, DEPLOYER_COMMANDS, TRUSTED_COMMANDS, PREFIXED_COMMANDS
from src.voice_bandwidth import get_voice_bandwidth_controller
import time
import base64
import re

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

rooms = {}
connected = {} # Who's connected in a voice room
socket_rooms = {}
voice_bandwidth_controller = get_voice_bandwidth_controller()

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

def emit_image(type, file, room):
    encoded = base64.b64encode(file).decode("utf-8")
        
    socketio.emit(
        "screenshot",
        {
            "image": encoded
        },
        room=room
    )
    print(f"[socket.py] Emitted screenshot to {room}, {len(file)} bytes")

def get_uuid_auth(uuid):
    # get the uuid_auth variable from web/routes.py
    from src.web.routes import uuid_auth
    return uuid_auth.get(uuid)


def normalize_audio_chunk(chunk):
    if isinstance(chunk, (bytes, bytearray)):
        return bytes(chunk)

    if isinstance(chunk, memoryview):
        return chunk.tobytes()

    if isinstance(chunk, str):
        try:
            return base64.b64decode(chunk)
        except Exception:
            return None

    if hasattr(chunk, "tobytes"):
        try:
            return chunk.tobytes()
        except Exception:
            return None

    if isinstance(chunk, dict):
        for key in ("audio", "data", "chunk"):
            if key in chunk:
                return normalize_audio_chunk(chunk[key])

    return None


# Events

@socketio.on('connect')
def handle_connect():
    print('[socket.py] Client connected')
    

@socketio.on("disconnect")
def disconnect():
    uuid = session.get("mc_uuid", ".anonymous")

    print(f"[socket.py] Client disconnected: {uuid}")

    for room, members in rooms.items():

        if uuid not in members:
            continue

        members.remove(uuid)

        emit(
            "peer-left",
            uuid,
            room=room,
            include_self=False
        )

        leave_room(room)

        print(f"[socket.py] Removed {uuid} from {room}")

        if len(members) == 0:
            del rooms[room]

        break

    for room, members in list(connected.items()):
        for user_id, sid in list(members.items()):
            if sid == request.sid:
                del members[user_id]

        if len(members) == 0:
            del connected[room]

    socket_rooms.pop(request.sid, None)
            

@socketio.on('join')
def handle_join(room, uuid=None, auth=None):
    if uuid is not None:
        if auth is None or get_uuid_auth(uuid) != auth:
            print(f"[socket.py] Failed join attempt to {room} with uuid {uuid} and auth {auth}")
            return
        else:
            connected.setdefault(room,{})[uuid] = request.sid
    else:
        uuid = session.get("mc_uuid", ".anonymous")

    if room in BOTS or uuid == room:
        join_room(room)
        print(f"[socket.py] {uuid} joined room: {room}")
    elif re.match("^voice-", room):
        if room not in rooms:
            rooms[room] = set()

        rooms[room].add(uuid)
        join_room(room)
        socket_rooms[request.sid] = room
        state = voice_bandwidth_controller.get_state()
        emit("voice-status", state)

        for peer_uuid in list(rooms[room]):
            if peer_uuid == uuid:
                continue

            peer_sid = connected.get(room, {}).get(peer_uuid)
            if peer_sid:
                emit("new-peer", uuid, room=peer_sid)

        existing_peers = [s for s in rooms[room] if s != uuid and s in connected.get(room, {})]
        emit("existing-peers", existing_peers)

        print(f"[socket.py] {uuid} joined room: {room}")
    else:
        print(f"[socket.py] {uuid} failed to join room (Unauthorized): {room}")


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

    emit_log('log', ["INFO","Bot disconnected; requested by deployer."], bot_name)

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["disconnect"] = True
    data["bot"][bot_name]["deployer"] = ""
    

@socketio.on("bot_switch_server")
def switch_request(rdata):
    bot_name = rdata.get("bot").strip()
    try:
        world_uuid = rdata.get("world").strip()
    except:
        world_uuid = ""
        
    if bot_name not in data["bot"]:
        return

    if "mc_uuid" not in session:
        return

    if session["mc_uuid"] != data["bot"][bot_name]["deployer"]:
        return

    print(f"[socket.py] Server switch for {bot_name} | World: {world_uuid}")

    emit_log('log', ["INFO","Bot switching server; requested by deployer."], bot_name)

    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"]["switch"] = world_uuid
    

@socketio.on("bot_chat")
def bot_chat(rdata):
    bot_name = rdata.get("bot").strip()
    try:
        msg = rdata.get("msg").strip()
    except:
        msg = ""
        
    if bot_name not in data["bot"]:
        return

    if "mc_uuid" not in session:
        return

    if not data["bot"][bot_name]["status"]:
        return

    account = session["mc_uuid"]
    
    try:
        if data["account"][account]["abilities"]["send"] not in [True,"true"]:
            return
    except:
        if DEFAULT_ABILITIES["send"] == False:
            return

    ts = time.time()

    if (ts - data["account"][account].get("last_chat",0)) < 7:
        print(f"[socket.py] Chat message failed (Ratelimited) through {bot_name} by {account} | Message: {msg}")
        return

    if msg[0] == "/":
        type = "command"
    else:
        type = "chat"

    if type == "command":
        match = re.search(r'^/?(\w+) ?(.*)?', msg)
        if match:
            if session["mc_uuid"] == data["bot"][bot_name]["deployer"]:
                if match.group(1) not in DEPLOYER_COMMANDS and match.group(1) not in WHITELISTED_COMMANDS:
                    if data["account"][session["mc_uuid"]].get("trusted", False):
                        if match.group(1) not in TRUSTED_COMMANDS:
                            print(f"[socket.py] Chat message failed (Blacklisted Command) through {bot_name} by {account} | Message: {msg}")
                            return
                    else:
                        print(f"[socket.py] Chat message failed (Blacklisted Command) through {bot_name} by {account} | Message: {msg}")
                        return
            else:
                if match.group(1) not in WHITELISTED_COMMANDS:
                    if data["account"][session["mc_uuid"]].get("trusted", False):
                        if match.group(1) not in TRUSTED_COMMANDS:
                            print(f"[socket.py] Chat message failed (Blacklisted Command) through {bot_name} by {account} | Message: {msg}")
                            return
                    else:
                        print(f"[socket.py] Chat message failed (Blacklisted Command) through {bot_name} by {account} | Message: {msg}")
                        return
            if match.group(1) in PREFIXED_COMMANDS:
                prefix = f"/{match.group(1)} {session['mc_username']} | > "
                msg = f"{prefix}{match.group(2)}"
        else:
            print(f"[socket.py] Chat message failed (Couldn't find match for command) through {bot_name} by {account} | Message: {msg}")
            return
    else:
        msg = msg.replace("<","\\<")
        prefix = f"<light_purple>{session['mc_username']}<dark_gray> | > <gray>"
        msg = f"{prefix}{msg}"

    print(f"[socket.py] Chat message sent through {bot_name} by {account} | Message: {msg}")

    data["account"][account]["last_chat"] = ts
    
    data["bot"][bot_name].setdefault("do", {})
    data["bot"][bot_name]["do"].setdefault("chat", [])
    
    data["bot"][bot_name]["do"]["chat"].append(msg)

    save_data()
    

@socketio.on("audio")
def handle_audio(data):
    room = socket_rooms.get(request.sid)
    uuid = session.get("mc_uuid")

    if isinstance(data, dict):
        room = data.get("room") or room
        uuid = data.get("from") or uuid
        chunk = data.get("audio")
    else:
        chunk = data

    if not room or not re.match("^voice-", room):
        return

    if uuid is None:
        return

    if room not in rooms or uuid not in rooms[room]:
        return

    chunk = normalize_audio_chunk(chunk)
    if chunk is None:
        return

    size = len(chunk)
    voice_bandwidth_controller.record_bytes(size)
    state = voice_bandwidth_controller.get_state()

    if not state["enabled"]:
        emit("voice-status", state)
        return

    for peer_uuid, peer_sid in list(connected.get(room, {}).items()):
        if peer_uuid == uuid:
            continue
        socketio.emit("audio", [uuid, chunk], room=peer_sid, binary=True)

    emit("voice-status", state)


@socketio.on("signal")
def handle_signal(data):
    uuid = data.get("from")
    auth = data.get("auth")
    target = data.get("to")
    signal_data = data.get("signal")

    if uuid is not None:
        if auth is None or get_uuid_auth(uuid) != auth:
            return
    else:
        uuid = session.get("mc_uuid", ".anonymous")

    if target:
        sender_room = next((room_name for room_name, members in connected.items() if uuid in members), None)
        if sender_room:
            target_sid = connected.get(sender_room, {}).get(target)
            if target_sid:
                emit("signal", {"from": uuid, "signal": signal_data}, room=target_sid)
