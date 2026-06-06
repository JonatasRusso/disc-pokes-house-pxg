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


async def _party_members_map(db: AsyncSession, party_ids: list[int]) -> dict[int, list[dict]]:
    """party_id -> lista de membros [{discord_id, nick, role, character}]."""
    if not party_ids:
        return {}
    rows = await db.execute(
        select(PartyMember, User, Character)
        .join(User, User.discord_id == PartyMember.user_id)
        .outerjoin(Character, Character.id == PartyMember.character_id)
        .where(PartyMember.party_id.in_(party_ids))
    )
    out: dict[int, list[dict]] = {}
    role_order = {"TANK": 0, "SUP": 1, "DPS": 2}
    for pm, u, ch in rows.all():
        out.setdefault(pm.party_id, []).append({
            "discord_id":  u.discord_id,
            "nick":        u.nick or u.username,
            "role":        pm.role,
            "character":   ch.name if ch else None,
            "is_coleader": bool(pm.is_coleader),
        })
    for members in out.values():
        members.sort(key=lambda m: role_order.get(m["role"], 9))
    return out


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
    mmap = await _party_members_map(db, [s.party_id for s in schedules])

    # Confirmações por (schedule_id, user_id)
    schedule_ids = [s.id for s in schedules]
    conf_map: dict[tuple[int, str], bool] = {}
    if schedule_ids:
        confs = await db.execute(
            select(ScheduleConfirmation).where(ScheduleConfirmation.schedule_id.in_(schedule_ids))
        )
        conf_map = {(c.schedule_id, c.user_id): c.confirmed for c in confs.scalars().all()}

    out = []
    for s in schedules:
        members = [
            {**m, "confirmed": conf_map.get((s.id, m["discord_id"]), False)}
            for m in mmap.get(s.party_id, [])
        ]
        me = next((m for m in members if m["discord_id"] == user.discord_id), None)
        is_leader = s.organizer_id == user.discord_id
        can_manage = bool(user.is_admin or is_leader or (me and me["is_coleader"]))
        out.append({
            **_schedule_dict(s),
            "members":      members,
            "is_member":    me is not None,
            "is_leader":    is_leader,
            "can_manage":   can_manage,
            "organizer_id": s.organizer_id,
        })
    return out


@router.get("/calendar")
async def calendar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Todas as PTs ativas com seus membros — visível para qualquer membro logado."""
    result = await db.execute(select(Schedule).where(Schedule.status.in_(ACTIVE_STATUSES)))
    schedules = result.scalars().all()
    mmap = await _party_members_map(db, [s.party_id for s in schedules])
    return [{
        "schedule_id": s.id,
        "weekday":     s.start_time.weekday(),
        "hour":        s.start_time.hour,
        "difficulty":  s.difficulty,
        "members":     mmap.get(s.party_id, []),
    } for s in schedules]


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

    # Líder, co-líder ou admin podem remarcar
    if not await _can_manage(db, schedule, user):
        raise HTTPException(403, "Apenas líder/co-líder podem remarcar a PT.")

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


async def _my_membership(db: AsyncSession, schedule: Schedule, user_id: str) -> PartyMember | None:
    res = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == schedule.party_id,
            PartyMember.user_id == user_id,
        )
    )
    return res.scalar_one_or_none()


async def _can_manage(db: AsyncSession, schedule: Schedule, user: User) -> bool:
    """Pode gerenciar quem é: admin, organizador (líder) ou co-líder."""
    if user.is_admin or schedule.organizer_id == user.discord_id:
        return True
    pm = await _my_membership(db, schedule, user.discord_id)
    return bool(pm and pm.is_coleader)


class PromoteIn(BaseModel):
    user_id: str
    coleader: bool = True


@router.post("/{schedule_id}/promote")
async def promote_member(schedule_id: int, body: PromoteIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Líder/organizador (ou admin) promove/rebaixa um membro a co-líder."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    if not (user.is_admin or schedule.organizer_id == user.discord_id):
        raise HTTPException(403, "Apenas o líder da PT pode definir co-líderes.")

    pm = await _my_membership(db, schedule, body.user_id)
    if not pm:
        raise HTTPException(404, "Membro não está na PT")
    pm.is_coleader = body.coleader
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id,
                   action="coleader_set", detail=f'{{"member":"{body.user_id}","coleader":{str(body.coleader).lower()}}}'))
    await db.commit()
    return {"ok": True}


@router.post("/{schedule_id}/kick")
async def kick_member(schedule_id: int, body: PromoteIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Líder/co-líder/admin remove um membro da PT."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    if not await _can_manage(db, schedule, user):
        raise HTTPException(403, "Sem permissão para gerenciar esta PT.")
    if body.user_id == schedule.organizer_id:
        raise HTTPException(400, "Não é possível remover o líder.")

    pm = await _my_membership(db, schedule, body.user_id)
    if not pm:
        raise HTTPException(404, "Membro não está na PT")
    await db.delete(pm)
    conf = await db.execute(select(ScheduleConfirmation).where(
        ScheduleConfirmation.schedule_id == schedule_id, ScheduleConfirmation.user_id == body.user_id))
    conf = conf.scalar_one_or_none()
    if conf:
        await db.delete(conf)
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id, action="kicked",
                   detail=f'{{"member":"{body.user_id}"}}'))
    db.add(Outbox(kind="party_left", target_user_id=body.user_id, payload=json.dumps({
        "who": "A liderança", "schedule_id": schedule_id, "kicked": True,
    })))
    await db.commit()
    return {"ok": True}


@router.post("/{schedule_id}/confirm")
async def confirm_presence(schedule_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Membro confirma presença na PT."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    pm = await _my_membership(db, schedule, user.discord_id)
    if not pm:
        raise HTTPException(403, "Você não é membro desta party")
    if pm.character_id is None:
        raise HTTPException(400, "Defina seu personagem antes de confirmar.")

    conf = await db.execute(
        select(ScheduleConfirmation).where(
            ScheduleConfirmation.schedule_id == schedule_id,
            ScheduleConfirmation.user_id == user.discord_id,
        )
    )
    conf = conf.scalar_one_or_none()
    if not conf:
        conf = ScheduleConfirmation(schedule_id=schedule_id, user_id=user.discord_id)
        db.add(conf)
    conf.confirmed = True
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id, action="confirmed"))
    await db.commit()
    return {"ok": True}


@router.post("/{schedule_id}/leave")
async def leave_party(schedule_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Membro sai da PT. Se a PT ficar vazia, é cancelada."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    pm = await _my_membership(db, schedule, user.discord_id)
    if not pm:
        raise HTTPException(403, "Você não é membro desta party")

    await db.delete(pm)
    conf = await db.execute(
        select(ScheduleConfirmation).where(
            ScheduleConfirmation.schedule_id == schedule_id,
            ScheduleConfirmation.user_id == user.discord_id,
        )
    )
    conf = conf.scalar_one_or_none()
    if conf:
        await db.delete(conf)
    await db.flush()

    remaining = (await db.execute(
        select(PartyMember).where(PartyMember.party_id == schedule.party_id)
    )).scalars().all()
    if not remaining:
        schedule.status = "cancelled"

    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id, action="left"))

    # Avisa os demais membros no canal
    for m in remaining:
        db.add(Outbox(kind="party_left", target_user_id=m.user_id, payload=json.dumps({
            "who": user.username, "schedule_id": schedule_id,
        })))
    await db.commit()
    return {"ok": True, "cancelled": not remaining}


class MyCharIn(BaseModel):
    character_id: int


@router.patch("/{schedule_id}/my-character")
async def set_my_character(schedule_id: int, body: MyCharIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Membro define/confirma o personagem que vai usar na PT."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    pm = await _my_membership(db, schedule, user.discord_id)
    if not pm:
        raise HTTPException(403, "Você não é membro desta party")

    char = await db.get(Character, body.character_id)
    if not char or char.user_id != user.discord_id:
        raise HTTPException(404, "Personagem não encontrado")

    occupied = await _occupied_character_ids(db)
    if body.character_id in occupied and pm.character_id != body.character_id:
        raise HTTPException(400, f"Personagem '{char.name}' já está em uma PT ativa.")

    pm.character_id = body.character_id
    await db.commit()
    return {"ok": True}


@router.delete("/{schedule_id}")
async def cancel_schedule(schedule_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")

    if not await _can_manage(db, schedule, user):
        raise HTTPException(403, "Apenas líder/co-líder podem cancelar a PT.")

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
