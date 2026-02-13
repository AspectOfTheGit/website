import requests
from src.config import DISCORD_TOKEN, GUILD_ID

def announce(message: str, type: str):
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }

    types = {"feature":[0x1abc1f,"New feature"], # Completely new feature introduced
             "upgrade":[0x1abc8e,"Feature update"], # When a feature is upgraded
             "bugfix":[0xbc1a1a,"Bugfixes"], # A bug has been fixed
             "hotfix":[0xbc911a,"Hotfix"] # A breaking bug has been fixed
            }
    
    try:
        color = types[type][0]
        title = types[type][1]
    except:
        color = 0x5c5c5c
        title = "Patch"

    channels = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",headers=headers).json()

    if not channels:
        print("[discord/announce.py] Could not get channels")
        return "Could not get channels"
        
    announcements = next((c for c in channels if c["type"] == 5 and c["name"] == "announcements"),None)
    
    if not announcements:
        print("[discord/announce.py] Could not find announcement channel")
        return "No announcement channel found"

    webhooks = requests.get(
        f"https://discord.com/api/v10/channels/{announcements['id']}/webhooks",headers=headers).json()
    webhook = webhooks[0] if webhooks else requests.post(f"https://discord.com/api/v10/channels/{announcements['id']}/webhooks",headers=headers,json={"name": "Updates"}).json()

    contents = f"# {title}\n\n{message}"
    
    embed = {
        "description": contents,
        "color": color
    }

    requests.post(webhook["url"],json={"embeds": [embed]})
