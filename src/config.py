import os

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

GUILD_ID = 1460692900533899438
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

BOTS = ["AspectOfTheBot","AspectOfTheButt","AspectOfThePoop","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks"]
VALID_BOT_PERMISSIONS = {"annihilate","fly","baritone","attack","place","break"}
BOT_PERMISSION_DEFAULTS = ["baritone","attack"]
BOT_LOBBY_PERMISSIONS = ["fly","baritone","attack"]
TIMEOUT = 10

WHITELISTED_COMMANDS = ["listall","find","uuid"]
DEPLOYER_COMMANDS = ["trigger"]

USER_SOCKET_LIMIT = 1024 * 10

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
}
