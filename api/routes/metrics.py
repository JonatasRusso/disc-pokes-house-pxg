"""Endpoint /metrics no formato Prometheus para o Grafana acompanhar o status do banco
(e métricas do bot/PTs). As métricas são calculadas a cada scrape, em um registry novo
para não interferir com nada global."""
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from api.database import get_db
from api.models import BotHeartbeat, Pokemon, Schedule, User
from api.timeutil import now_local

router = APIRouter(tags=["metrics"])

HEARTBEAT_STALE_S = 90
ACTIVE_STATUSES = ["pending", "confirmed", "rescheduled"]


@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    reg = CollectorRegistry()
    g = lambda name, doc: Gauge(name, doc, registry=reg)  # noqa: E731

    db_up        = g("discbot_db_up", "1 se o banco respondeu o SELECT 1, 0 caso contrário")
    db_latency   = g("discbot_db_query_latency_seconds", "Latência do SELECT 1 no banco")
    bot_up       = g("discbot_bot_up", "1 se o heartbeat do bot está fresco e pronto")
    bot_latency  = g("discbot_bot_gateway_latency_ms", "Latência do gateway do Discord (ms)")
    bot_guilds   = g("discbot_bot_guilds", "Número de servidores do bot")
    hb_age       = g("discbot_bot_heartbeat_age_seconds", "Idade do último heartbeat do bot")
    sched_active = g("discbot_schedules_active", "PTs ativas (pending/confirmed/rescheduled)")
    poke_assigned = g("discbot_pokemon_assigned", "Pokémons em uso (assigned_to != null)")
    poke_total   = g("discbot_pokemon_total", "Pokémons cadastrados")
    users_total  = g("discbot_users_total", "Usuários cadastrados")

    up = 0
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        db_latency.set(time.perf_counter() - t0)
        up = 1

        async def count(stmt):
            return (await db.execute(stmt)).scalar() or 0

        sched_active.set(await count(
            select(func.count()).select_from(Schedule).where(Schedule.status.in_(ACTIVE_STATUSES))))
        poke_assigned.set(await count(
            select(func.count()).select_from(Pokemon).where(Pokemon.assigned_to.isnot(None))))
        poke_total.set(await count(select(func.count()).select_from(Pokemon)))
        users_total.set(await count(select(func.count()).select_from(User)))

        hb = await db.get(BotHeartbeat, 1)
        if hb and hb.updated_at:
            age = (now_local() - hb.updated_at).total_seconds()
            hb_age.set(age)
            bot_up.set(1 if (bool(hb.is_ready) and age <= HEARTBEAT_STALE_S) else 0)
            bot_latency.set(hb.latency_ms or 0)
            bot_guilds.set(hb.guilds or 0)
    except Exception:
        up = 0

    db_up.set(up)
    return Response(generate_latest(reg), media_type=CONTENT_TYPE_LATEST)
