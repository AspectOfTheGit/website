import time
import re
import requests
from src.config import DISCORD_TOKEN, GUILD_ID
from src.data import data

# todo - store channels that have been created to reduce requests sent

def notify(account: str, message: str, type: str):
    match = re.search(r"^([^.]+)", type)
    typeroot = match.group(1) if match else None

    if typeroot != "bot":
        saccount = data["account"][account]["username"].lower()
        saccount = re.sub(r"[^a-z0-9-_]", "-", saccount)[:90]
        try:
            user_id = data["account"][account]["discord"]
        except:
            return
        if type not in data["account"][account].get("notifs", []):
            return
    else:
        saccount = account.lower()

    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        color = {"storage.read":0x1a81bc,
                 "storage.write":0xbc891a,
                 "storage.error":0xff0000,
                 
                 "webpage.save":0xbc891a,
                 "webpage.update":0x07eef2,
                 "webpage.view":0x43ba83,
                 "webpage.interact":0x39d455,

                 "bot.deploy":0x49ba43,
                 "bot.log":0x5c5c5c,
                 "bot.disconnect":0xff0000
                }[type]
    except:
        color = 0x5c5c5c

    channels = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers).json()
    if typeroot == "bot":
        if type == "bot.log":
            return # Disabled bot log notifications, probably forever
        try:
            category = next((c for c in channels if c["type"] == 4 and c["name"] == ".bots"),{"id":None})
            log_channel = next((c for c in channels
                                if c["parent_id"] == category["id"] and c["name"] == saccount),
                               None)
        except:
            print("[discord/notify.py] bot log discord error, classic")
            return
        if not log_channel:
            log_channel = requests.post(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers,json={"name": saccount,"parent_id": category["id"],"type": 0}).json()
        webhooks = requests.get(
            f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers).json()
        webhook = webhooks[0] if webhooks else requests.post(f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers,json={"name": saccount}).json()
        
        embed = {
            "description": message,
            "color": color
        }

        requests.post(webhook["url"],json={"embeds": [embed]})
        return
        
    category = next((c for c in channels if c["type"] == 4 and c["name"] == saccount),None)

    if not category:
        category = requests.post(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",
            headers=headers,
            json={
                "name": saccount,
                "type": 4,
                "permission_overwrites": [
                    {
                        "id": user_id,
                        "type": 1,
                        "allow": "1024",
                        "deny": "0"
                    },
                    {
                        "id": str(GUILD_ID),
                        "type": 0,
                        "allow": "0",
                        "deny": "1024"
                    }
                ]
            }
        ).json()

    log_channel = next((c for c in channels
                        if c["parent_id"] == category["id"] and c["name"] == typeroot),
                       None)
    if not log_channel:
        log_channel = requests.post(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers,json={"name": typeroot,"parent_id": category["id"],"type": 0}).json()

    webhooks = requests.get(
        f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers).json()
    webhook = webhooks[0] if webhooks else requests.post(f"https://discord.com/api/v10/channels/{log_channel['id']}/webhooks",headers=headers,json={"name": "Logger"}).json()
    
    ts = f"<t:{int(time.time())}:R>"
    contents = f"{ts}\n{message}"
    embed = {
        "description": contents,
        "color": color
    }

    requests.post(webhook["url"],json={"embeds": [embed]})
