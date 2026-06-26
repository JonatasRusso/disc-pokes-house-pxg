import asyncio
import logging
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from bot.config import DISCORD_TOKEN, DISCORD_GUILD_ID
from bot.scheduler import start_scheduler, handle_confirmation
from bot.health import write_heartbeat, mark_command
from api.database import init_db, AsyncSessionLocal
from api.models import User

# Logs no stdout (o Railway marca stderr como "error" mesmo sendo INFO).
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
# APScheduler loga cada execução de job no INFO — silencia o ruído de rotina.
logging.getLogger("apscheduler").setLevel(logging.WARNING)
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


async def _upsert_member(db, member: discord.Member):
    """Insere/atualiza um membro na tabela users (sem mexer em is_admin)."""
    if member.bot:
        return
    db_user = await db.get(User, str(member.id))
    avatar_url = str(member.display_avatar.url)
    nick = member.display_name  # apelido no servidor (ou nome global se não tiver)
    if db_user:
        db_user.username   = member.name
        db_user.nick       = nick
        db_user.avatar_url = avatar_url
    else:
        db.add(User(discord_id=str(member.id), username=member.name, nick=nick, avatar_url=avatar_url))


async def sync_roster():
    """Sincroniza o roster da guild para a tabela users."""
    guild = bot.get_guild(DISCORD_GUILD_ID)
    if not guild:
        log.warning("Guild não encontrada para sincronizar roster.")
        return
    count = 0
    async with AsyncSessionLocal() as db:
        async for member in guild.fetch_members(limit=None):
            await _upsert_member(db, member)
            count += 1
        await db.commit()
    log.info(f"Roster sincronizado: {count} membros.")


@bot.event
async def on_ready():
    log.info(f"Bot online como {bot.user} (ID: {bot.user.id})")
    guild = discord.Object(id=DISCORD_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)
    log.info(f"{len(synced)} comandos slash sincronizados.")
    await sync_roster()
    start_scheduler(bot)
    await write_heartbeat(bot)  # heartbeat inicial


@bot.event
async def on_app_command_completion(interaction, command):
    mark_command()


@bot.event
async def on_member_join(member: discord.Member):
    async with AsyncSessionLocal() as db:
        await _upsert_member(db, member)
        await db.commit()


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    mark_command()
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
