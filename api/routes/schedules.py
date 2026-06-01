from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, require_admin
from api.database import get_db
from api.models import (
    Character, History, Party, PartyMember, Schedule,
    ScheduleConfirmation, User
)

router = APIRouter(prefix="/schedules", tags=["schedules"])

ROLES = {"DPS", "SUP", "TANK"}
DIFFICULTIES = {"HARD", "NW"}


class ScheduleIn(BaseModel):
    character_id: int
    role: str
    difficulty: str
    start_time: datetime      # ISO-8601
    party_members: list[dict]  # [{"discord_id": "...", "role": "DPS"}, ...]


class RescheduleIn(BaseModel):
    new_start: datetime


@router.get("")
async def list_schedules(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Schedule)
        .join(Party)
        .join(PartyMember, PartyMember.party_id == Party.id)
        .where(PartyMember.user_id == user.discord_id)
        .order_by(Schedule.start_time)
    )
    schedules = result.scalars().unique().all()
    return [_schedule_dict(s) for s in schedules]


@router.get("/free-slots")
async def free_slots(db: AsyncSession = Depends(get_db)):
    """Retorna blocos de 3h disponíveis nos próximos 7 dias."""
    now   = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    end   = now + timedelta(days=7)

    result = await db.execute(
        select(Schedule).where(
            Schedule.status.in_(["pending", "confirmed"]),
            Schedule.start_time >= now,
            Schedule.start_time <= end,
        )
    )
    busy = result.scalars().all()
    busy_ranges = [(s.start_time, s.end_time) for s in busy]

    slots = []
    cursor = now
    while cursor < end:
        slot_end = cursor + timedelta(hours=3)
        overlap  = any(s < slot_end and e > cursor for s, e in busy_ranges)
        if not overlap:
            slots.append({"start": cursor.isoformat(), "end": slot_end.isoformat()})
        cursor += timedelta(hours=1)

    return slots


@router.post("")
async def create_schedule(body: ScheduleIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.difficulty not in DIFFICULTIES:
        raise HTTPException(400, f"Dificuldade inválida. Use: {DIFFICULTIES}")
    if body.role not in ROLES:
        raise HTTPException(400, f"Função inválida. Use: {ROLES}")

    char = await db.get(Character, body.character_id)
    if not char or char.user_id != user.discord_id:
        raise HTTPException(404, "Personagem não encontrado")

    end_time = body.start_time + timedelta(hours=3)

    # Cria party
    party = Party()
    db.add(party)
    await db.flush()

    # Membro principal
    db.add(PartyMember(party_id=party.id, user_id=user.discord_id, role=body.role))

    # Demais membros
    for m in body.party_members:
        if m["discord_id"] == user.discord_id:
            continue
        if m.get("role") not in ROLES:
            raise HTTPException(400, f"Função inválida para membro {m['discord_id']}")
        db.add(PartyMember(party_id=party.id, user_id=m["discord_id"], role=m["role"]))

    schedule = Schedule(
        party_id=party.id,
        character_id=body.character_id,
        difficulty=body.difficulty,
        start_time=body.start_time,
        end_time=end_time,
    )
    db.add(schedule)
    await db.flush()

    # Confirmações pendentes para cada membro
    all_members = [user.discord_id] + [m["discord_id"] for m in body.party_members if m["discord_id"] != user.discord_id]
    for uid in all_members:
        db.add(ScheduleConfirmation(schedule_id=schedule.id, user_id=uid))

    db.add(History(
        actor_id=user.discord_id,
        entity_type="schedule",
        entity_id=schedule.id,
        action="created",
        detail=f'{{"difficulty":"{body.difficulty}","start":"{body.start_time.isoformat()}"}}',
    ))
    await db.commit()
    await db.refresh(schedule)
    return _schedule_dict(schedule)


@router.patch("/{schedule_id}/reschedule")
async def reschedule(schedule_id: int, body: RescheduleIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")

    # Verifica se o usuário é membro da party
    member = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == schedule.party_id,
            PartyMember.user_id == user.discord_id,
        )
    )
    if not member.scalar_one_or_none():
        raise HTTPException(403, "Você não é membro desta party")

    schedule.start_time = body.new_start
    schedule.end_time   = body.new_start + timedelta(hours=3)
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
        detail=f'{{"new_start":"{body.new_start.isoformat()}"}}',
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
        "start_time": s.start_time.isoformat(),
        "end_time":   s.end_time.isoformat(),
        "status":     s.status,
    }
