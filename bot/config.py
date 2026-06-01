import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN            = os.environ["DISCORD_TOKEN"]
DISCORD_CLIENT_ID        = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET    = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_GUILD_ID         = int(os.environ["DISCORD_GUILD_ID"])
DISCORD_NOTIFY_CHANNEL_ID  = int(os.environ["DISCORD_NOTIFY_CHANNEL_ID"])
DISCORD_POKEMON_CHANNEL_ID = int(os.environ["DISCORD_POKEMON_CHANNEL_ID"])

SITE_URL   = os.getenv("SITE_URL", "http://localhost:5173")
API_URL    = os.getenv("API_URL",  "http://localhost:8000")
JWT_SECRET = os.environ["JWT_SECRET"]
