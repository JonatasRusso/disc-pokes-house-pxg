"""Heartbeat do bot — gravado no banco para o /health da API (processos separados) ler."""
import logging
import math

import discord

try:
    import psutil
except ImportError:  # psutil é opcional
    psutil = None

from api.database import AsyncSessionLocal
from api.models import BotHeartbeat
from api.timeutil import now_local

log = logging.getLogger(__name__)

# Atualizado a cada comando/evento processado
_last_command_at = None


def mark_command():
    global _last_command_at
    _last_command_at = now_local()


def _process_memory_mb():
    if psutil is None:
        return None
    try:
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None


async def write_heartbeat(bot: discord.Client):
    ready = bot.is_ready()
    latency = bot.latency  # pode ser nan antes de conectar
    latency_ms = round(latency * 1000) if (ready and not math.isnan(latency)) else None
    try:
        async with AsyncSessionLocal() as db:
            hb = await db.get(BotHeartbeat, 1)
            if not hb:
                hb = BotHeartbeat(id=1)
                db.add(hb)
            hb.is_ready        = ready
            hb.latency_ms      = latency_ms
            hb.guilds          = len(bot.guilds)
            hb.memory_mb       = _process_memory_mb()
            hb.last_command_at = _last_command_at
            hb.updated_at      = now_local()
            await db.commit()
    except Exception as e:
        log.warning(f"Falha ao gravar heartbeat: {e}")
