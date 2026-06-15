"""Lógica central de agendamento isolada das rotas (camada de serviço, sem Repository —
usa SQLAlchemy direto). Reúne recorrência semanal, duração configurável e conflito por
sobreposição de intervalos. Pura o suficiente para testes unitários (só `_has_conflict`
toca o banco)."""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.enums import ACTIVE_STATUSES
from api.models import Schedule

# Horários flexíveis: passos de 15 min e duração configurável (início + duração)
SLOT_STEP_MIN        = 15
DEFAULT_DURATION_MIN = 180        # 3h (padrão, editável por PT)
MIN_DURATION_MIN     = 15
MAX_DURATION_MIN     = 12 * 60


def _validate_duration(minutes: int) -> int:
    if minutes % SLOT_STEP_MIN != 0 or not (MIN_DURATION_MIN <= minutes <= MAX_DURATION_MIN):
        raise HTTPException(400, f"Duração inválida. Use múltiplos de {SLOT_STEP_MIN} min, "
                                 f"entre {MIN_DURATION_MIN} e {MAX_DURATION_MIN}.")
    return minutes


def next_occurrence(weekday: int, hour: int, minute: int, after: datetime) -> datetime:
    """Próxima data/hora (futuro) com o dia-da-semana e horário (hora:minuto) dados. Recorrência semanal."""
    candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= after:
        candidate += timedelta(days=7)
    return candidate


def _eff_start(s: Schedule) -> datetime:
    return s.override_start or s.start_time


def _eff_end(s: Schedule) -> datetime:
    return s.override_end or s.end_time


def _segments(start: datetime, end: datetime) -> list[tuple[int, int, int]]:
    """Janela [start, end) como segmentos (dia_da_semana, min_início, min_fim<=1440),
    dividindo na meia-noite (cobre PT que vira o dia). Base do conflito por intervalo."""
    segs: list[tuple[int, int, int]] = []
    wd = start.weekday()
    cur = start.hour * 60 + start.minute
    remaining = max(0, int((end - start).total_seconds() // 60))
    while remaining > 0:
        take = min(1440 - cur, remaining)
        segs.append((wd, cur, cur + take))
        remaining -= take
        wd = (wd + 1) % 7
        cur = 0
    return segs


def _segments_overlap(a: list[tuple[int, int, int]], b: list[tuple[int, int, int]]) -> bool:
    return any(wa == wb and sa < eb and sb < ea for (wa, sa, ea) in a for (wb, sb, eb) in b)


async def _has_conflict(db: AsyncSession, start: datetime, end: datetime,
                        exclude: int | None = None, effective: bool = False) -> bool:
    """Conflito por sobreposição de intervalos (dia+minuto, com duração e virada de dia).
    `effective`: usa o override desta semana (remarcação só esta semana) ou o slot fixo recorrente."""
    cand = _segments(start, end)
    q = select(Schedule).where(Schedule.status.in_(ACTIVE_STATUSES))
    if exclude is not None:
        q = q.where(Schedule.id != exclude)
    for s in (await db.execute(q)).scalars().all():
        s_start = (s.override_start or s.start_time) if effective else s.start_time
        s_end   = (s.override_end or s.end_time) if effective else s.end_time
        if _segments_overlap(cand, _segments(s_start, s_end)):
            return True
    return False
