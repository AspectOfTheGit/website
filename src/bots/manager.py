import time
from app.data import data, save_data
from app.config import TIMEOUT
from app.discord.notify import notify

def refresh_bot_info():
    bots = [
        "AspectOfTheBot",
        "AspectOfTheNuts",
        "AspectOfTheCream",
        "AspectOfTheSacks",
        "AspectOfTheButt",
        "AspectOfThePoop"
    ]

    for bot in bots:
        data["bot"].setdefault(bot, {})
        data["bot"][bot].setdefault("last_ping", 0)
        data["bot"][bot].setdefault("status", False)

        if (
            data["bot"][bot]["status"]
            and time.time() - data["bot"][bot]["last_ping"] > TIMEOUT
        ):
            data["bot"][bot]["status"] = False
            notify(bot, f"{bot} disconnected", "bot.disconnect")

    save_data()
