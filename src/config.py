import os

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

GUILD_ID = 1460692900533899438
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

BOTS = ["AspectOfTheBot","AspectOfTheButt","AspectOfThePoop","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks"] # Valid bots
VALID_BOT_PERMISSIONS = {"annihilate","fly","baritone","attack","place","break"} # Permissions that can be given to the bot
BOT_PERMISSION_DEFAULTS = ["baritone","attack"] # Permissions given to the bot by default while in any world
BOT_LOBBY_PERMISSIONS = ["fly","baritone","attack"] # Permissions given to the bot while in lobby
TIMEOUT = 10 # in seconds, how long the backend will wait until the bot is marked as offline

DEFAULT_ABILITIES = {"send":True,"capacity":1,"uses":10,"simultaneous":1,"uptime":30,"abandoned":True,"unowned":True} # Default capabilities for each account

WHITELISTED_COMMANDS = ["listall","find","uuid","list"] # Commands that can be sent by anyone through bots
DEPLOYER_COMMANDS = ["trigger"] # Commands that can only be sent by the deployer through bots
TRUSTED_COMMANDS = ["shout","msg","tell"] # Commands tht only trusted users can send through bots (deployer or not)
PREFIXED_COMMANDS = ["shout","msg","tell"] # Commands that should include the users name as prefix

USER_SOCKET_LIMIT = 1024 * 10 # in bytes, how much the backend can send through a socket from a user influenced input

VALID_WORLD_ELEMENT_KEYS = ["id","value","color"] # Valid world page element properties

MAX_TIME_TILL_VOICE_ROOM_CLOSE = 3000 # in milliseconds, how long until a voice room closes due to no ping sent from world

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
