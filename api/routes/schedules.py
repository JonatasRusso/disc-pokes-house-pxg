import json
import os
import uuid
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
from api.timeutil import now_local
from api.enums import (
    PartyRole, Difficulty, ROLE_CAPACITY, ROLE_VALUES, DIFFICULTY_VALUES, ACTIVE_STATUSES,
)
from api.services.schedule_service import (
    DEFAULT_DURATION_MIN, _validate_duration, next_occurrence, _has_conflict,
    _segments, _eff_start, _eff_end,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])

ROLES = set(ROLE_VALUES)
DIFFICULTIES = set(DIFFICULTY_VALUES)
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")


class PartyMemberIn(BaseModel):
    discord_id: str
    role: PartyRole
    character_id: int | None = None


class ScheduleIn(BaseModel):
    character_id: int | None = None     # personagem do criador (None se admin não se incluir)
    role: PartyRole | None = None
    difficulty: Difficulty
    start_time: datetime                # ISO-8601 (usa dia-da-semana + hora:minuto)
    duration_minutes: int = DEFAULT_DURATION_MIN
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
    duration_minutes: int | None = None  # None = mantém a duração atual da PT
    scope: str = "once"    # "once" = só esta semana (override) | "all" = redefine o slot fixo
    force: bool = False    # ignora conflito com OUTRA PT (sobrescreve o horário mesmo ocupado)


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
            "is_external": bool(pm.is_external),  # externo NESTA PT (não usa pokémon)
            "is_guest":    bool(u.is_external),   # convidado de outro servidor (sem login)
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
        "schedule_id":      s.id,
        "weekday":          s.start_time.weekday(),  # slot fixo recorrente
        "hour":             s.start_time.hour,
        "minute":           s.start_time.minute,
        "duration_minutes": int((s.end_time - s.start_time).total_seconds() // 60),
        "difficulty":       s.difficulty,
        "is_override":      s.override_start is not None,  # esta semana está remarcada
        "members":          mmap.get(s.party_id, []),
    } for s in schedules]


@router.get("/free-slots")
async def free_slots(exclude: int | None = None, db: AsyncSession = Depends(get_db)):
    """Grade semanal recorrente (hora cheia) com flag `free` por hora — usada só na
    visualização do calendário. Uma hora é `free` se nenhuma PT ativa a ocupa.
    `exclude`: schedule a ignorar (ao remarcar, libera o slot da própria PT)."""
    day_start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    end       = day_start + timedelta(days=7)

    q = select(Schedule).where(Schedule.status.in_(ACTIVE_STATUSES))
    if exclude is not None:
        q = q.where(Schedule.id != exclude)
    occupied: list[tuple[int, int, int]] = []
    for s in (await db.execute(q)).scalars().all():
        occupied += _segments(s.start_time, s.end_time)

    slots = []
    cursor = day_start
    while cursor < end:
        wd, m0, m1 = cursor.weekday(), cursor.hour * 60, cursor.hour * 60 + 60
        free = not any(w == wd and m0 < e and s < m1 for (w, s, e) in occupied)
        slots.append({"start": cursor.isoformat(), "end": (cursor + timedelta(hours=1)).isoformat(), "free": free})
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

    # Recorrência semanal: próxima ocorrência do dia-da-semana + hora:minuto escolhidos
    duration = _validate_duration(body.duration_minutes)
    start_time = next_occurrence(
        body.start_time.weekday(), body.start_time.hour, body.start_time.minute, now_local())
    end_time = start_time + timedelta(minutes=duration)

    # Conflito de horário (sobreposição de intervalos, recorrente)
    if await _has_conflict(db, start_time, end_time):
        raise HTTPException(400, "Já existe uma PT que se sobrepõe a esse horário.")

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
    if body.scope not in ("once", "all"):
        raise HTTPException(400, "scope inválido (use 'once' ou 'all').")

    # Líder, co-líder ou admin podem remarcar
    if not await _can_manage(db, schedule, user):
        raise HTTPException(403, "Apenas líder/co-líder podem remarcar a PT.")

    # Duração: nova (se enviada) ou mantém a atual da PT
    if body.duration_minutes is not None:
        duration = _validate_duration(body.duration_minutes)
    else:
        duration = int((schedule.end_time - schedule.start_time).total_seconds() // 60)
    new_start = next_occurrence(
        body.new_start.weekday(), body.new_start.hour, body.new_start.minute, now_local())
    new_end   = new_start + timedelta(minutes=duration)

    if body.scope == "all":
        # Redefine o slot fixo recorrente, ignorando a própria PT (libera o próprio slot).
        # `force` permite sobrescrever o horário de OUTRA PT.
        if await _has_conflict(db, new_start, new_end, exclude=schedule_id, effective=False) and not body.force:
            raise HTTPException(400, "Já existe uma PT que se sobrepõe a esse horário. "
                                     "Marque a opção de sobrescrever para continuar.")
        schedule.start_time     = new_start
        schedule.end_time       = new_end
        schedule.override_start = None   # redefinir o fixo cancela qualquer remarcação de 1 semana
        schedule.override_end   = None
    else:
        # Remarca só esta semana: grava o override e mantém o slot fixo. Conflito pela
        # ocorrência efetiva (override desta semana) das outras PTs ativas.
        if await _has_conflict(db, new_start, new_end, exclude=schedule_id, effective=True) and not body.force:
            raise HTTPException(400, "Já existe uma PT que se sobrepõe a esse horário. "
                                     "Marque a opção de sobrescrever para continuar.")
        schedule.override_start = new_start
        schedule.override_end   = new_end

    schedule.status = "rescheduled"

    # Reseta confirmações
    confs = await db.execute(
        select(ScheduleConfirmation).where(ScheduleConfirmation.schedule_id == schedule_id)
    )
    for conf in confs.scalars().all():
        conf.confirmed = False
        conf.last_ping = None

    # Avisa os demais membros no Discord (texto diferente por modo)
    members = (await db.execute(
        select(PartyMember).where(PartyMember.party_id == schedule.party_id)
    )).scalars().all()
    for m in members:
        if m.user_id == user.discord_id:
            continue
        db.add(Outbox(kind="party_rescheduled", target_user_id=m.user_id, payload=json.dumps({
            "who":         user.nick or user.username,
            "schedule_id": schedule_id,
            "scope":       body.scope,
            "new_start":   new_start.isoformat(),
            "difficulty":  schedule.difficulty,
            "link":        f"{SITE_URL}/minhas-pts",
        })))

    db.add(History(
        actor_id=user.discord_id,
        entity_type="schedule",
        entity_id=schedule_id,
        action="rescheduled",
        detail=f'{{"new_start":"{new_start.isoformat()}","scope":"{body.scope}"}}',
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
    target = await db.get(User, body.user_id)
    await db.delete(pm)
    conf = await db.execute(select(ScheduleConfirmation).where(
        ScheduleConfirmation.schedule_id == schedule_id, ScheduleConfirmation.user_id == body.user_id))
    conf = conf.scalar_one_or_none()
    if conf:
        await db.delete(conf)
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id, action="kicked",
                   detail=f'{{"member":"{body.user_id}"}}'))
    # Externo não recebe aviso no Discord (não está no servidor) e o registro-convidado é descartado.
    if target and target.is_external:
        await db.delete(target)
    else:
        db.add(Outbox(kind="party_left", target_user_id=body.user_id, payload=json.dumps({
            "who": "A liderança", "schedule_id": schedule_id, "kicked": True,
        })))
    await db.commit()
    return {"ok": True}


class AddMemberIn(BaseModel):
    discord_id: str | None = None     # membro da house (do seletor)
    external_name: str | None = None  # OU convidado de outro servidor (só nome)
    role: PartyRole
    character_id: int | None = None


async def _add_capacity_check(db: AsyncSession, schedule: Schedule, role: str):
    members = (await db.execute(
        select(PartyMember).where(PartyMember.party_id == schedule.party_id)
    )).scalars().all()
    if len(members) >= 4:
        raise HTTPException(400, "A PT já está completa.")
    if sum(1 for m in members if m.role == role) >= ROLE_CAPACITY[role]:
        raise HTTPException(400, f"A PT já tem o máximo de {role} ({ROLE_CAPACITY[role]}).")


@router.post("/{schedule_id}/add-member")
async def add_member(schedule_id: int, body: AddMemberIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Líder/co-líder/admin adiciona um membro a uma PT incompleta.
    Respeita a composição 1 TANK / 2 DPS / 1 SUP. O membro pode ser da house (convidado
    no Discord) ou um externo de outro servidor (só ocupa a vaga — não usa pokémon)."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    if not await _can_manage(db, schedule, user):
        raise HTTPException(403, "Apenas líder/co-líder podem adicionar membros.")
    if body.role not in ROLES:
        raise HTTPException(400, f"Função inválida. Use: {ROLES}")

    # --- Externo de outro servidor: ocupa a vaga, sem login/pokémon/ping ---
    if body.external_name and not body.discord_id:
        name = body.external_name.strip()[:40]
        if not name:
            raise HTTPException(400, "Informe o nome do externo.")
        await _add_capacity_check(db, schedule, body.role)
        guest_id = f"ext:{uuid.uuid4().hex}"
        db.add(User(discord_id=guest_id, username=name, nick=name, is_external=True))
        db.add(PartyMember(party_id=schedule.party_id, user_id=guest_id, role=body.role,
                           character_id=None, is_external=True))
        db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id,
                       action="member_added", detail=json.dumps({"external": name, "role": body.role})))
        await db.commit()
        return {"ok": True}

    # --- Membro da house ---
    if not body.discord_id:
        raise HTTPException(400, "Informe o membro ou o nome do externo.")
    if await _my_membership(db, schedule, body.discord_id):
        raise HTTPException(400, "Esse usuário já está na PT.")

    await _add_capacity_check(db, schedule, body.role)

    target = await db.get(User, body.discord_id)
    if not target or target.is_external:
        raise HTTPException(404, "Usuário não encontrado no servidor.")

    if body.character_id is not None:
        ch = await db.get(Character, body.character_id)
        if not ch or ch.user_id != body.discord_id:
            raise HTTPException(400, "Personagem inválido para esse membro.")
        if body.character_id in await _occupied_character_ids(db):
            raise HTTPException(400, f"Personagem '{ch.name}' já está em uma PT ativa.")

    db.add(PartyMember(
        party_id=schedule.party_id, user_id=body.discord_id,
        role=body.role, character_id=body.character_id,
    ))
    db.add(ScheduleConfirmation(schedule_id=schedule_id, user_id=body.discord_id))
    db.add(Outbox(kind="party_invite", target_user_id=body.discord_id, payload=json.dumps({
        "inviter":         user.nick or user.username,
        "schedule_id":     schedule_id,
        "start_time":      _eff_start(schedule).isoformat(),
        "difficulty":      schedule.difficulty,
        "role":            body.role,
        "needs_character": body.character_id is None,
        "link":            f"{SITE_URL}/minhas-pts",
    })))
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id,
                   action="member_added", detail=f'{{"member":"{body.discord_id}","role":"{body.role}"}}'))
    await db.commit()
    return {"ok": True}


class SetExternalIn(BaseModel):
    user_id: str
    external: bool = True


@router.post("/{schedule_id}/set-external")
async def set_member_external(schedule_id: int, body: SetExternalIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Marca/desmarca um membro como externo NESTA PT (não usa pokémon nem recebe ping).
    Qualquer membro da PT (ou admin) pode marcar."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Horário não encontrado")
    if not (user.is_admin or await _my_membership(db, schedule, user.discord_id)):
        raise HTTPException(403, "Você não é membro desta PT.")

    pm = await _my_membership(db, schedule, body.user_id)
    if not pm:
        raise HTTPException(404, "Membro não está na PT")

    target = await db.get(User, body.user_id)
    if target and target.is_external and not body.external:
        raise HTTPException(400, "Convidado de outro servidor é sempre externo.")

    pm.is_external = body.external
    db.add(History(actor_id=user.discord_id, entity_type="schedule", entity_id=schedule_id,
                   action="member_external", detail=json.dumps({"member": body.user_id, "external": body.external})))
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
    if pm.character_id is None and not pm.is_external:
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

    # Avisa os demais membros no canal (externos não recebem aviso — não estão no servidor)
    for m in remaining:
        mu = await db.get(User, m.user_id)
        if mu and mu.is_external:
            continue
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
        duration = _validate_duration(body.duration_minutes)
        schedule.start_time = body.start_time
        schedule.end_time   = body.start_time + timedelta(minutes=duration)
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
        # start_time/end_time = ocorrência EFETIVA (com override aplicado, se houver)
        "start_time":   _eff_start(s).isoformat(),
        "end_time":     _eff_end(s).isoformat(),
        # weekday/hour/minute = slot FIXO recorrente (sempre o base, ignora override)
        "weekday":      s.start_time.weekday(),  # 0=Seg .. 6=Dom
        "hour":         s.start_time.hour,
        "minute":       s.start_time.minute,
        "duration_minutes": int((_eff_end(s) - _eff_start(s)).total_seconds() // 60),
        "is_override":     s.override_start is not None,  # remarcada só esta semana
        "override_start":  s.override_start.isoformat() if s.override_start else None,
        "organizer_id": s.organizer_id,
        "status":       s.status,
    }
