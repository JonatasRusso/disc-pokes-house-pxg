import asyncio
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.database import init_db, AsyncSessionLocal
from api.models import BotHeartbeat
from api.timeutil import now_local
from api.routes import auth, characters, schedules, pokemon, history, members, metrics

try:
    import psutil
except ImportError:
    psutil = None

SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")
START_TIME = time.time()

# Envs obrigatórias — usadas para o env_ok do health
REQUIRED_ENVS = ["DISCORD_TOKEN", "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "JWT_SECRET", "DATABASE_URL"]

# Considera o bot "fresco" se o heartbeat foi atualizado nos últimos 90s
HEARTBEAT_STALE_S = 90


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="DiscBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[SITE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(schedules.router)
app.include_router(pokemon.router)
app.include_router(history.router)
app.include_router(members.router)
app.include_router(metrics.router)


def _api_memory_mb():
    if psutil is None:
        return None
    try:
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None


async def _resources():
    """CPU e disco do container. cpu_percent bloqueia 0.5s → roda em thread p/ não travar o loop."""
    if psutil is None:
        return None
    try:
        cpu = await asyncio.to_thread(psutil.cpu_percent, 0.5)
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": cpu,
            "disk_used_gb": round(disk.used / 1024 ** 3, 2),
            "disk_total_gb": round(disk.total / 1024 ** 3, 2),
            "disk_percent": disk.percent,
        }
    except Exception:
        return None


@app.get("/health")
async def health():
    now = now_local()

    # --- Banco ---
    db_connected, db_latency_ms = False, None
    try:
        async with AsyncSessionLocal() as db:
            t0 = time.perf_counter()
            await db.execute(text("SELECT 1"))
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            db_connected = True
            hb = await db.get(BotHeartbeat, 1)
    except Exception:
        hb = None

    # --- Bot (via heartbeat no banco) ---
    discord_block = {
        "connected": False, "latency_ms": None, "guilds": 0,
        "memory_mb": None, "last_command_at": None, "heartbeat_age_s": None,
    }
    bot_fresh = False
    if hb and hb.updated_at:
        age = (now - hb.updated_at).total_seconds()
        bot_fresh = age <= HEARTBEAT_STALE_S and bool(hb.is_ready)
        discord_block = {
            "connected": bool(hb.is_ready) and age <= HEARTBEAT_STALE_S,
            "latency_ms": hb.latency_ms,
            "guilds": hb.guilds or 0,
            "memory_mb": hb.memory_mb,
            "last_command_at": hb.last_command_at.isoformat() if hb.last_command_at else None,
            "heartbeat_age_s": round(age),
        }

    env_ok = all(os.getenv(k) for k in REQUIRED_ENVS)
    status = "ok" if (db_connected and bot_fresh and env_ok) else "degraded"

    return {
        "status": status,
        "timestamp": now.isoformat(),
        "api": {
            "uptime_seconds": round(time.time() - START_TIME),
            "memory_mb": _api_memory_mb(),
        },
        "db": {"connected": db_connected, "latency_ms": db_latency_ms},
        "discord": discord_block,
        "resources": await _resources(),
        "env_ok": env_ok,
    }
