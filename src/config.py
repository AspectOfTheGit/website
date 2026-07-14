import json
import logging
import os
import threading
import time

import requests

LOGGER = logging.getLogger(__name__)

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
TURN_TOKEN_ID = os.environ.get("TURN_TOKEN_ID")
TURN_API_TOKEN = os.environ.get("TURN_API_TOKEN")

GUILD_ID = 1515347143882182786
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

BOTS = ["AspectOfTheBot","AspectOfTheButt","AspectOfThePoop","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks"] # Valid bots
VALID_BOT_PERMISSIONS = {"annihilate","fly","baritone","attack","place","break"} # Permissions that can be given to the bot
BOT_PERMISSION_DEFAULTS = ["baritone","attack"] # Permissions given to the bot by default while in any world
BOT_LOBBY_PERMISSIONS = ["fly","baritone","attack"] # Permissions given to the bot while in lobby
TIMEOUT = 10 # in seconds, how long the backend will wait until the bot is marked as offline
AUTO_SAVE_INTERVAL_MINUTES = 15 # In minutes, how often dirty data should be flushed automatically. Set to 0 to disable periodic auto-save

DEFAULT_ABILITIES = {"send":True, # Whether the user can send messages through the bot
                     "capacity":1, # In MB, how much storage capacity the user has
                     "uses":10, # How many times the user can deploy a bot per day
                     "simultaneous":1, # How many bots a user can have deployed at the same time
                     "uptime":30, # In minutes, how long a user can have a bot deployed
                     "abandoned":True, # Whether the bot automatically disconnects after being alone for one minute
                     "unowned":True # Whether the user can deploy bots to worlds they don't own
                    } # Default capabilities for each account

WHITELISTED_COMMANDS = ["listall","find","uuid","list"] # Commands that can be sent by anyone through bots
DEPLOYER_COMMANDS = ["trigger"] # Commands that can only be sent by the deployer through bots
TRUSTED_COMMANDS = ["shout","msg","tell"] # Commands that only trusted users can send through bots (deployer or not)
PREFIXED_COMMANDS = ["shout","msg","tell"] # Commands that should include the users name as prefix

USER_SOCKET_LIMIT = 1024 * 10 # in bytes, how much the backend can send through a socket from a user influenced input

VALID_WORLD_ELEMENT_KEYS = ["id","value","color"] # Valid world page element properties

MAX_TIME_TILL_VOICE_ROOM_CLOSE = 5000 # in milliseconds, how long until a voice room closes due to no ping sent from world

VOICE_ROOM_START_BITRATE_KBPS = 32
VOICE_ROOM_MIN_BITRATE_KBPS = 12
VOICE_ROOM_BANDWIDTH_LIMIT_BYTES = 1024 * 1024 * 1024 * 20
VOICE_ROOM_BANDWIDTH_DETERIORATION_THRESHOLD_RATIO = 0.6
VOICE_WEBRTC_TURN_TTL_SECONDS = max(60, int(os.environ.get("VOICE_WEBRTC_TURN_TTL_SECONDS", "86400")))
DEFAULT_CLOUDFLARE_STUN_URLS = [
    "stun:stun.cloudflare.com:3478",
]
DEFAULT_CLOUDFLARE_TURN_URLS = [
    "turn:turn.cloudflare.com:3478?transport=udp",
    "turn:turn.cloudflare.com:3478?transport=tcp",
    "turns:turn.cloudflare.com:5349?transport=tcp",
]
_MANUAL_VOICE_WEBRTC_ICE_SERVERS = []
try:
    raw_ice_servers = os.environ.get("VOICE_WEBRTC_ICE_SERVERS", "[]")
    parsed_ice_servers = json.loads(raw_ice_servers)
    if isinstance(parsed_ice_servers, list):
        _MANUAL_VOICE_WEBRTC_ICE_SERVERS = [server for server in parsed_ice_servers if isinstance(server, dict)]
except Exception:
    _MANUAL_VOICE_WEBRTC_ICE_SERVERS = []

_voice_webrtc_ice_servers_cache = []
_voice_webrtc_ice_servers_expires_at = 0
_voice_webrtc_ice_servers_lock = threading.Lock()


def _normalize_ice_servers(ice_servers):
    if not isinstance(ice_servers, list):
        return []

    normalized = []
    for entry in ice_servers:
        if not isinstance(entry, dict):
            continue

        urls = entry.get("urls")
        if isinstance(urls, str):
            urls = [urls]
        elif not isinstance(urls, list):
            continue

        sanitized_urls = [url for url in urls if isinstance(url, str) and url.strip()]
        if not sanitized_urls:
            continue

        normalized_entry = {
            "urls": sanitized_urls,
        }

        username = entry.get("username")
        credential = entry.get("credential")
        if username:
            normalized_entry["username"] = str(username)
        if credential:
            normalized_entry["credential"] = str(credential)

        normalized.append(normalized_entry)

    return normalized


def _get_fallback_voice_webrtc_ice_servers():
    return [{
        "urls": DEFAULT_CLOUDFLARE_STUN_URLS,
    }]


def _fetch_cloudflare_turn_ice_servers():
    if not TURN_TOKEN_ID or not TURN_API_TOKEN:
        return None

    endpoint = (
        "https://rtc.live.cloudflare.com/v1/turn/keys/"
        f"{TURN_TOKEN_ID}/credentials/generate-ice-servers"
    )

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {TURN_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"ttl": VOICE_WEBRTC_TURN_TTL_SECONDS},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return _normalize_ice_servers(payload.get("iceServers", []))
    except Exception:
        LOGGER.exception("Failed generating Cloudflare TURN ICE credentials")
        return None


def get_voice_webrtc_ice_servers(force_refresh=False):
    global _voice_webrtc_ice_servers_cache
    global _voice_webrtc_ice_servers_expires_at

    if _MANUAL_VOICE_WEBRTC_ICE_SERVERS:
        return list(_MANUAL_VOICE_WEBRTC_ICE_SERVERS)

    now = int(time.time())

    with _voice_webrtc_ice_servers_lock:
        if (
            not force_refresh
            and _voice_webrtc_ice_servers_cache
            and now < _voice_webrtc_ice_servers_expires_at
        ):
            return list(_voice_webrtc_ice_servers_cache)

        generated_ice_servers = _fetch_cloudflare_turn_ice_servers()
        if generated_ice_servers:
            _voice_webrtc_ice_servers_cache = generated_ice_servers
            _voice_webrtc_ice_servers_expires_at = now + max(60, VOICE_WEBRTC_TURN_TTL_SECONDS - 60)
            return list(_voice_webrtc_ice_servers_cache)

        fallback_ice_servers = _get_fallback_voice_webrtc_ice_servers()
        _voice_webrtc_ice_servers_cache = fallback_ice_servers
        _voice_webrtc_ice_servers_expires_at = now + 300
        return list(_voice_webrtc_ice_servers_cache)

VOICE_SPATIAL_MAX_DISTANCE = 20
VOICE_SPATIAL_MIN_GAIN = 0.02
VOICE_NOISE_GATE_ENABLED = True
VOICE_NOISE_GATE_OPEN_BYTES = 220
VOICE_NOISE_GATE_CLOSE_BYTES = 150
VOICE_NOISE_GATE_HOLD_MS = 500

DATAPACK_VERSION = "1.1" # The version of the voice chat datapack. Used in the api /voice/version endpoint
DATAPACK_TEMPLATE_FILE = os.environ.get("DATAPACK_TEMPLATE_FILE", "misc/voice-chat-datapack/latest.zip") # Relative to static folder when serving locally

COLOURS = {
    "black": "#000000",
    "dark_blue": "#0000AA",
    "dark_green": "#00AA00",
    "dark_aqua": "#00AAAA",
    "dark_red": "#AA0000",
    "dark_purple": "#AA00AA",
    "gold": "#FFAA00",
    "gray": "#AAAAAA",
    "dark_gray": "#555555",
    "blue": "#5555FF",
    "green": "#55FF55",
    "aqua": "#55FFFF",
    "red": "#FF5555",
    "light_purple": "#FF55FF",
    "yellow": "#FFFF55",
    "white": "#FFFFFF"
} # Minecraft colours converted to hex
