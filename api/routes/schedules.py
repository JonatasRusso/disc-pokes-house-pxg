import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, require_admin
from api.database import get_db
from api.models import (
    Character, History, Outbox, Party, PartyMember, Schedule,
    ScheduleConfirmation, User
)

router = APIRouter(prefix="/schedules", tags=["schedules"])

ROLES = {"DPS", "SUP", "TANK"}
DIFFICULTIES = {"HARD", "NW"}
ACTIVE_STATUSES = ["pending", "confirmed", "rescheduled"]
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")


def next_occurrence(weekday: int, hour: int, after: datetime) -> datetime:
    """Próxima data/hora (futuro) com o dia-da-semana e hora dados. Recorrência semanal."""
    candidate = after.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= after:
        candidate += timedelta(days=7)
    return candidate


async def _busy_weekday_hours(db: AsyncSession) -> list[tuple[int, int]]:
    """(dia_da_semana, hora) de cada PT ativa — base da grade semanal recorrente."""
    result = await db.execute(select(Schedule).where(Schedule.status.in_(ACTIVE_STATUSES)))
    return [(s.start_time.weekday(), s.start_time.hour) for s in result.scalars().all()]


def _conflicts(weekday: int, hour: int, busy: list[tuple[int, int]]) -> bool:
    """Marcar uma PT trava o horário marcado + as 2 horas posteriores.
    Logo, a hora `hour` está ocupada se cair em [bh, bh+2] de alguma PT existente."""
    return any(bwd == weekday and 0 <= (hour - bh) <= 2 for bwd, bh in busy)


class PartyMemberIn(BaseModel):
    discord_id: str
    role: str
    character_id: int | None = None


class ScheduleIn(BaseModel):
    character_id: int | None = None     # personagem do criador (None se admin não se incluir)
    role: str | None = None
    difficulty: str
    start_time: datetime                # ISO-8601
    party_members: list[PartyMemberIn]  # demais membros da PT
    include_self: bool = True           # False: admin organiza PT sem participar


async def _occupied_character_ids(db: AsyncSession) -> set[int]:
    """IDs de personagens já em uma PT ativa (pending/confirmed)."""
    result = await db.execute(
        select(PartyMember.character_id)
        .join(Schedule, Schedule.party_id == PartyMember.party_id)
        .where(
            Schedule.status.in_(ACTIVE_STATUSES),
            PartyMember.character_id.isnot(None),
        )
    )
    return {row[0] for row in result.all() if row[0] is not None}


class RescheduleIn(BaseModel):
    new_start: datetime


@router.get("")
async def list_schedules(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # PTs onde o usuário é membro OU que ele organizou (admin sem se incluir)
    member_party_ids = select(PartyMember.party_id).where(PartyMember.user_id == user.discord_id)
    result = await db.execute(
        select(Schedule)
        .where(
            or_(
                Schedule.organizer_id == user.discord_id,
                Schedule.party_id.in_(member_party_ids),
            )
        )
        .order_by(Schedule.start_time)
    )
    schedules = result.scalars().unique().all()
    return [_schedule_dict(s) for s in schedules]


@router.get("/free-slots")
async def free_slots(db: AsyncSession = Depends(get_db)):
    """Grade semanal recorrente: para cada hora (00:00..23:00) dos 7 dias da semana,
    retorna o bloco de 3h com flag `free`. Sem trava de horário — escolher um dia já
    passado nesta semana agenda para a próxima semana. Livre = sem conflito recorrente."""
    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end       = day_start + timedelta(days=7)

    busy = await _busy_weekday_hours(db)

    slots = []
    cursor = day_start
    while cursor < end:
        slot_end = cursor + timedelta(hours=3)
        free     = not _conflicts(cursor.weekday(), cursor.hour, busy)
        slots.append({"start": cursor.isoformat(), "end": slot_end.isoformat(), "free": free})
        cursor += timedelta(hours=1)

    return slots


@router.post("")
async def create_schedule(body: ScheduleIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.difficulty not in DIFFICULTIES:
        raise HTTPException(400, f"Dificuldade inválida. Use: {DIFFICULTIES}")

    include_self = body.include_self
    if not include_self and not user.is_admin:
        raise HTTPException(403, "Apenas admins podem criar uma PT sem participar.")

    # Personagem do criador (só quando ele participa)
    if include_self:
        if not body.character_id or body.role not in ROLES:
            raise HTTPException(400, "Selecione seu personagem e sua função.")
        char = await db.get(Character, body.character_id)
        if not char or char.user_id != user.discord_id:
            raise HTTPException(404, "Personagem não encontrado")
    else:
        if not body.party_members:
            raise HTTPException(400, "Informe ao menos um membro para a PT.")

    # Recorrência semanal: calcula a próxima ocorrência do dia-da-semana/hora escolhidos
    start_time = next_occurrence(body.start_time.weekday(), body.start_time.hour, datetime.utcnow())

    # Conflito de horário (marcar trava o horário + 2 horas posteriores)
    busy = await _busy_weekday_hours(db)
    if _conflicts(start_time.weekday(), start_time.hour, busy):
        raise HTTPException(400, "Já existe uma PT nesse horário semanal.")

    # Regra: 1 PT ativa por personagem
    occupied = await _occupied_character_ids(db)
    if include_self and body.character_id in occupied:
        raise HTTPException(400, f"Personagem '{char.name}' já está em uma PT ativa.")

    # Valida personagens dos membros convidados
    for m in body.party_members:
        if m.discord_id == user.discord_id:
            continue
        if m.role not in ROLES:
            raise HTTPException(400, f"Função inválida para membro {m.discord_id}")
        if m.character_id is not None:
            mc = await db.get(Character, m.character_id)
            if not mc or mc.user_id != m.discord_id:
                raise HTTPException(400, f"Personagem inválido para membro {m.discord_id}")
            if m.character_id in occupied:
                raise HTTPException(400, f"Personagem '{mc.name}' já está em uma PT ativa.")

    end_time = start_time + timedelta(hours=3)

    # Cria party
    party = Party()
    db.add(party)
    await db.flush()

    # Membro principal (criador) — só se ele participa
    seen = set()
    self_members = []
    if include_self:
        db.add(PartyMember(
            party_id=party.id, user_id=user.discord_id, role=body.role, character_id=body.character_id,
        ))
        seen.add(user.discord_id)
        self_members.append(user.discord_id)

    # Demais membros (deduplicados)
    invited = []
    for m in body.party_members:
        if m.discord_id in seen:
            continue
        seen.add(m.discord_id)
        db.add(PartyMember(
            party_id=party.id, user_id=m.discord_id, role=m.role, character_id=m.character_id,
        ))
        invited.append(m)

    schedule = Schedule(
        party_id=party.id,
        character_id=body.character_id if include_self else None,
        organizer_id=user.discord_id,
        difficulty=body.difficulty,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(schedule)
    await db.flush()

    # Confirmações pendentes para todos os membros
    for uid in self_members + [m.discord_id for m in invited]:
        db.add(ScheduleConfirmation(schedule_id=schedule.id, user_id=uid))

    # Enfileira convite no Discord para cada membro convidado
    for m in invited:
        payload = {
            "inviter":         user.username,
            "schedule_id":     schedule.id,
            "start_time":      start_time.isoformat(),
            "difficulty":      body.difficulty,
            "role":            m.role,
            "needs_character": m.character_id is None,
            "link":            f"{SITE_URL}/dashboard",
        }
        db.add(Outbox(kind="party_invite", target_user_id=m.discord_id, payload=json.dumps(payload)))

    db.add(History(
        actor_id=user.discord_id,
        entity_type="schedule",
        entity_id=schedule.id,
        action="created",
        detail=f'{{"difficulty":"{body.difficulty}","start":"{start_time.isoformat()}"}}',
    ))
    await db.commit()
    await db.refresh(schedule)
    return _schedule_dict(schedule)


@router.patch("/{schedule_id}/reschedule")
async def reschedule(schedule_id: int, body: RescheduleIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")

    # Membro da party OU admin podem remarcar
    member = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == schedule.party_id,
            PartyMember.user_id == user.discord_id,
        )
    )
    if not member.scalar_one_or_none() and not user.is_admin:
        raise HTTPException(403, "Você não é membro desta party")

    new_start = next_occurrence(body.new_start.weekday(), body.new_start.hour, datetime.utcnow())
    # Evita conflito com outras PTs (ignora a própria)
    busy = [(wd, h) for (wd, h) in await _busy_weekday_hours(db)
            if not (wd == schedule.start_time.weekday() and h == schedule.start_time.hour)]
    if _conflicts(new_start.weekday(), new_start.hour, busy):
        raise HTTPException(400, "Já existe uma PT nesse horário semanal.")
    schedule.start_time = new_start
    schedule.end_time   = new_start + timedelta(hours=3)
    schedule.status     = "rescheduled"

    # Reseta confirmações
    confs = await db.execute(
        select(ScheduleConfirmation).where(ScheduleConfirmation.schedule_id == schedule_id)
    )
    for conf in confs.scalars().all():
        conf.confirmed = False
        conf.last_ping = None

    db.add(History(
        actor_id=user.discord_id,
        entity_type="schedule",
        entity_id=schedule_id,
        action="rescheduled",
        detail=f'{{"new_start":"{new_start.isoformat()}"}}',
    ))
    await db.commit()
    return _schedule_dict(schedule)


@router.delete("/{schedule_id}")
async def cancel_schedule(schedule_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")

    member = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == schedule.party_id,
            PartyMember.user_id == user.discord_id,
        )
    )
    if not member.scalar_one_or_none() and not user.is_admin:
        raise HTTPException(403, "Sem permissão")

    schedule.status = "cancelled"
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id, action="cancelled"))
    await db.commit()
    return {"ok": True}


# Admin: editar qualquer schedule
@router.patch("/{schedule_id}/admin")
async def admin_edit_schedule(
    schedule_id: int,
    body: ScheduleIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    if body.difficulty:
        schedule.difficulty = body.difficulty
    if body.start_time:
        schedule.start_time = body.start_time
        schedule.end_time   = body.start_time + timedelta(hours=3)
    db.add(History(
        actor_id=admin.discord_id,
        entity_type="schedule",
        entity_id=schedule_id,
        action="admin_edited",
        detail=f'{{"by":"{admin.discord_id}"}}',
    ))
    await db.commit()
    return _schedule_dict(schedule)


def _schedule_dict(s: Schedule) -> dict:
    return {
        "id":         s.id,
        "party_id":   s.party_id,
        "difficulty": s.difficulty,
        "start_time":   s.start_time.isoformat(),
        "end_time":     s.end_time.isoformat(),
        "weekday":      s.start_time.weekday(),  # 0=Seg .. 6=Dom
        "hour":         s.start_time.hour,
        "organizer_id": s.organizer_id,
        "status":       s.status,
    }
