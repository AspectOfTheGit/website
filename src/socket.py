from flask import session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from src.discord.notify import notify
from src.data import data, save_data
from src.config import (
    BOTS,
    DEFAULT_ABILITIES,
    WHITELISTED_COMMANDS,
    DEPLOYER_COMMANDS,
    TRUSTED_COMMANDS,
    PREFIXED_COMMANDS,
    VOICE_SPATIAL_MAX_DISTANCE,
    VOICE_SPATIAL_MIN_GAIN,
)
from src.voice_bandwidth import get_voice_bandwidth_controller
import time
import base64
import re
import math

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

    if isinstance(chunk, (list, tuple)):
        # Some clients/proxies may serialize binary payloads to integer arrays.
        if chunk and all(isinstance(x, int) and 0 <= x <= 255 for x in chunk):
            try:
                return bytes(chunk)
            except Exception:
                return None
        return None

    if hasattr(chunk, "tobytes"):
        try:
            return chunk.tobytes()
        except Exception:
            return None

    if isinstance(chunk, dict):
        # Node-style Buffer JSON payload: {"type": "Buffer", "data": [...]}.
        if chunk.get("type") == "Buffer" and isinstance(chunk.get("data"), (list, tuple)):
            return normalize_audio_chunk(chunk.get("data"))

        for key in ("audio", "data", "chunk"):
            if key in chunk:
                return normalize_audio_chunk(chunk[key])

    return None


def parse_audio_event_payload(data=None, binary_payload=None):
    room = None
    sender_uuid = None
    chunk = None
    mime_type = None

    if isinstance(data, dict):
        room = data.get("room")
        sender_uuid = data.get("from")
        chunk = data.get("audio") or data.get("data") or data.get("chunk")
        mime_type = data.get("mimeType") or data.get("mime")
    elif isinstance(data, (list, tuple)):
        if data and all(isinstance(item, int) and 0 <= item <= 255 for item in data):
            chunk = data
        else:
            for item in data:
                if isinstance(item, dict):
                    room = item.get("room") or room
                    sender_uuid = item.get("from") or sender_uuid
                    chunk = item.get("audio") or item.get("data") or item.get("chunk") or chunk
                    mime_type = item.get("mimeType") or item.get("mime") or mime_type
                elif chunk is None and (isinstance(item, (bytes, bytearray, memoryview)) or hasattr(item, "tobytes")):
                    chunk = item

    if chunk is None and binary_payload is not None:
        chunk = binary_payload

    if chunk is None and data is not None and not isinstance(data, (dict, list, tuple)):
        chunk = data

    return room, sender_uuid, normalize_audio_chunk(chunk), mime_type


def _safe_vec3(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None

    try:
        return float(value[0]), float(value[1]), float(value[2])
    except Exception:
        return None


def _safe_rot(value):
    if not isinstance(value, (list, tuple)) or len(value) < 1:
        return None

    try:
        return float(value[0])
    except Exception:
        return None


def _get_room_player_socket(world_uuid, player_uuid):
    try:
        from src.api.voice import voice_rooms
        players = voice_rooms.get(world_uuid, {}).get("players", [])
    except Exception:
        return None

    player = next((p for p in players if p.get("uuid") == player_uuid), None)
    if not player:
        return None

    return player.get("socket")


def get_spatial_audio_state(room, speaker_uuid, listener_uuid):
    if not room.startswith("voice-"):
        return None

    world_uuid = room[len("voice-"):]

    speaker_socket = _get_room_player_socket(world_uuid, speaker_uuid)
    listener_socket = _get_room_player_socket(world_uuid, listener_uuid)
    if not speaker_socket or not listener_socket:
        return None

    speaker_pos = _safe_vec3(speaker_socket.get("Pos"))
    listener_pos = _safe_vec3(listener_socket.get("Pos"))
    listener_yaw = _safe_rot(listener_socket.get("Rot"))
    if not speaker_pos or not listener_pos or listener_yaw is None:
        return None

    dx = speaker_pos[0] - listener_pos[0]
    dy = speaker_pos[1] - listener_pos[1]
    dz = speaker_pos[2] - listener_pos[2]

    distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    if distance >= VOICE_SPATIAL_MAX_DISTANCE:
        return {
            "distance": distance,
            "gain": 0.0,
            "pan": 0.0,
        }

    # Smooth quadratic falloff for better near-field clarity.
    normalized = max(0.0, 1.0 - (distance / VOICE_SPATIAL_MAX_DISTANCE))
    gain = max(0.0, normalized * normalized)

    yaw_rad = math.radians(listener_yaw)
    right_x = math.cos(yaw_rad)
    right_z = -math.sin(yaw_rad)

    horizontal_distance = math.sqrt((dx * dx) + (dz * dz))
    if horizontal_distance <= 1e-6:
        pan = 0.0
    else:
        pan = (dx * right_x + dz * right_z) / horizontal_distance
        pan = max(-1.0, min(1.0, pan))

    return {
        "distance": distance,
        "gain": gain,
        # Flip sign to match browser stereo panner orientation with Minecraft yaw.
        "pan": -pan,
    }


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

        # Force all peers to restart MediaRecorder so late joiners receive a fresh init segment.
        socketio.emit("voice-restart-stream", {"reason": "peer-join", "peer": uuid}, room=room)

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
def handle_audio(data=None, *args):
    room = socket_rooms.get(request.sid)
    uuid = session.get("mc_uuid")

    payload_room, payload_uuid, chunk, mime_type = parse_audio_event_payload(data, next((arg for arg in args if arg is not None), None))
    room = payload_room or room
    uuid = payload_uuid or uuid

    if uuid is None:
        for room_name, members in connected.items():
            if request.sid in members.values():
                uuid = next((member_uuid for member_uuid, member_sid in members.items() if member_sid == request.sid), None)
                break

    if not room or not re.match("^voice-", room):
        return

    if uuid is None:
        return

    if room not in rooms or uuid not in rooms[room]:
        return

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

        spatial = get_spatial_audio_state(room, uuid, peer_uuid)

        socketio.emit(
            "audio",
            {
                "from": uuid,
                "audio": chunk,
                "mimeType": mime_type,
                "spatial": spatial,
            },
            room=peer_sid,
        )

    emit("voice-status", state)


@socketio.on("voice-request-restart")
def handle_voice_request_restart(data=None):
    if not isinstance(data, dict):
        return

    room = socket_rooms.get(request.sid)
    requester_uuid = None

    if room and room in connected:
        requester_uuid = next((member_uuid for member_uuid, member_sid in connected[room].items() if member_sid == request.sid), None)

    if not room or not re.match("^voice-", room) or not requester_uuid:
        return

    target_uuid = data.get("peer")
    if not target_uuid or target_uuid == requester_uuid:
        return

    target_sid = connected.get(room, {}).get(target_uuid)
    if not target_sid:
        return

    socketio.emit(
        "voice-restart-stream",
        {
            "reason": "peer-request",
            "requestedBy": requester_uuid,
        },
        room=target_sid,
    )


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
