import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from bot.config import DISCORD_TOKEN, DISCORD_GUILD_ID
from bot.scheduler import start_scheduler, handle_confirmation
from api.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

COGS = [
    "bot.commands.schedule",
    "bot.commands.pokemon",
    "bot.commands.admin",
    "bot.events.reactions",
]

intents = discord.Intents.default()
intents.message_content = True
intents.reactions       = True
intents.members         = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info(f"Bot online como {bot.user} (ID: {bot.user.id})")
    guild = discord.Object(id=DISCORD_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)
    log.info(f"{len(synced)} comandos slash sincronizados.")
    start_scheduler(bot)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Delega confirmações de schedule ao scheduler
    await handle_confirmation(bot, payload)
    # As reações de pokémon são tratadas pelo ReactionCog


async def main():
    await init_db()
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            log.info(f"Cog carregado: {cog}")
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
