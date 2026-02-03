import os

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OTHER_TOKEN = os.environ.get("OTHER_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

GUILD_ID = 1460692900533899438
REDIRECT_URI = "https://aspectofthe.site/login"
DATA_FILE = "/data/values.json"

BOTS = ["AspectOfTheBot","AspectOfTheNuts","AspectOfTheCream","AspectOfTheSacks","AspectOfTheButt","AspectOfThePoop"]
VALID_BOT_PERMISSIONS = {"annihilate","fly","baritone","attack","place","break"}
BOT_PERMISSION_DEFAULTS = ["baritone","attack"]
BOT_LOBBY_PERMISSIONS = ["fly","baritone","attack"]
TIMEOUT = 10
