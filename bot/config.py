import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN            = os.environ["DISCORD_TOKEN"]
DISCORD_CLIENT_ID        = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET    = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_GUILD_ID         = int(os.environ["DISCORD_GUILD_ID"])
DISCORD_NOTIFY_CHANNEL_ID  = int(os.environ["DISCORD_NOTIFY_CHANNEL_ID"])


def _cid(value):
    return int(value) if value else None


# Canal único (compatibilidade) + canais por função (Tank/DPS/Sup)
DISCORD_POKEMON_CHANNEL_ID = _cid(os.getenv("DISCORD_POKEMON_CHANNEL_ID"))

# Mapa categoria -> canal. Se um canal específico não estiver definido, usa o canal único.
POKEMON_CHANNELS = {
    "A": _cid(os.getenv("DISCORD_POKEMON_CHANNEL_TANK")) or DISCORD_POKEMON_CHANNEL_ID,  # Tank
    "B": _cid(os.getenv("DISCORD_POKEMON_CHANNEL_DPS"))  or DISCORD_POKEMON_CHANNEL_ID,  # DPS
    "C": _cid(os.getenv("DISCORD_POKEMON_CHANNEL_SUP"))  or DISCORD_POKEMON_CHANNEL_ID,  # Sup
}
# Conjunto de canais de pokémon válidos (para o guard das reações)
POKEMON_CHANNEL_IDS = {c for c in POKEMON_CHANNELS.values() if c}

SITE_URL   = os.getenv("SITE_URL", "http://localhost:5173")
API_URL    = os.getenv("API_URL",  "http://localhost:8000")
JWT_SECRET = os.environ["JWT_SECRET"]
