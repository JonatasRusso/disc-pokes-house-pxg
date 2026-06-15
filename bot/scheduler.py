"""
Scheduler de notificações de horários de party.
- A cada minuto verifica schedules que começam em ≤30 min e ainda não foram notificados.
- Pinga cada membro não confirmado a cada minuto até confirmação ou início da party.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from api.database import AsyncSessionLocal
from api.models import History, Outbox, Pokemon, Schedule, ScheduleConfirmation, PartyMember, User
from api.timeutil import now_local
from bot.config import DISCORD_NOTIFY_CHANNEL_ID, POKEMON_CHANNELS, SITE_URL
from bot.commands.pokemon import build_pokemon_embed

log = logging.getLogger(__name__)

# (schedule_id, user_id) -> estado do aviso da ocorrência atual
# {"iso": str, "msg_id": int|None, "sent": set[str], "last_late": datetime|None}
_warn_state: dict[tuple[int, str], dict] = {}

# schedule_id -> start_time iso já lembrado (evita repetir o lembrete de pokémon na mesma ocorrência)
_poke_reminded: dict[int, str] = {}

ROLE_TO_CAT  = {"TANK": "A", "DPS": "B", "SUP": "C"}
CAT_LABEL    = {"A": "Tank", "B": "DPS", "C": "Sup"}


def _eff_start(s: Schedule) -> datetime:
    """Início efetivo da próxima ocorrência (override de 1 semana, se houver)."""
    return s.override_start or s.start_time


def _eff_end(s: Schedule) -> datetime:
    return s.override_end or s.end_time


def start_scheduler(bot: discord.Client):
    from bot.health import write_heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_check_schedules, "interval", seconds=20, args=[bot])
    scheduler.add_job(_process_outbox, "interval", seconds=20, args=[bot])
    scheduler.add_job(write_heartbeat, "interval", seconds=30, args=[bot])
    scheduler.start()
    log.info("Scheduler iniciado.")
    return scheduler


async def _delete_warn(channel: discord.TextChannel, key: tuple[int, str]):
    """Apaga a mensagem de aviso atual (avisar e deletar)."""
    st = _warn_state.get(key)
    if st and st.get("msg_id"):
        try:
            await channel.get_partial_message(st["msg_id"]).delete()
        except Exception:
            pass
        st["msg_id"] = None


OUTBOX_GIVEUP = timedelta(minutes=15)  # abandona item que não envia há 15 min (ex: bot sem permissão)

# TTL de mensagens transitórias do bot (auto-apagam para não poluir os canais)
NOTICE_TTL_S        = 30 * 60   # convites / saída / remarcação
POKE_REMINDER_TTL_S = 40 * 60   # lembrete de pokémon (posta ~30 min antes; some no início da PT)

# Carência da varredura de pokémons órfãos: só libera marcação mais antiga que isto
# (protege marcação recém-feita, auto ou manual).
POKE_ORPHAN_GRACE_S = 30 * 60


async def _process_outbox(bot: discord.Client):
    """Envia mensagens enfileiradas pela API (convites de PT, etc)."""
    channel = bot.get_channel(DISCORD_NOTIFY_CHANNEL_ID)
    if not channel:
        return

    now = now_local()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Outbox).where(Outbox.sent_at.is_(None)).order_by(Outbox.id).limit(20)
        )
        items = result.scalars().all()

        for item in items:
            try:
                if item.kind == "party_invite":
                    await _send_party_invite(channel, item)
                elif item.kind == "party_left":
                    await _send_party_left(channel, item)
                elif item.kind == "party_rescheduled":
                    await _send_party_rescheduled(channel, item)
                item.sent_at = now
            except Exception as e:
                age = now - (item.created_at or now)
                if age > OUTBOX_GIVEUP:
                    item.sent_at = now  # abandona para não ficar reenviando pra sempre
                    log.warning(f"Outbox #{item.id} abandonado após {age} sem enviar: {e}")
                else:
                    log.warning(f"Falha ao enviar outbox #{item.id} (vai tentar de novo): {e}")

        await db.commit()


async def _send_party_invite(channel: discord.TextChannel, item: Outbox):
    data = json.loads(item.payload or "{}")
    inviter   = data.get("inviter", "Alguém")
    start_iso = data.get("start_time")
    role      = data.get("role", "")
    link      = data.get("link", SITE_URL)
    needs_char = data.get("needs_character", False)

    try:
        when = datetime.fromisoformat(start_iso).strftime("%d/%m %H:%M") if start_iso else "em breve"
    except (ValueError, TypeError):
        when = "em breve"

    desc = (
        f"<@{item.target_user_id}>, **{inviter}** te convidou para uma PT!\n\n"
        f"🕐 Horário: `{when}` | Função: `{role}`\n"
        f"➡️ Acesse o site para confirmar: {link}"
    )
    if needs_char:
        desc += "\n\n⚠️ Você ainda não tem um personagem cadastrado — crie um no site para entrar na PT."

    embed = discord.Embed(
        title="💀 Convite de PT",
        description=desc,
        color=discord.Color.blurple(),
    )
    await channel.send(
        content=f"<@{item.target_user_id}>",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
        delete_after=NOTICE_TTL_S,
    )


async def _send_party_left(channel: discord.TextChannel, item: Outbox):
    data = json.loads(item.payload or "{}")
    who = data.get("who", "Alguém")
    sid = data.get("schedule_id")
    embed = discord.Embed(
        title="🚪 Saída de PT",
        description=f"<@{item.target_user_id}>, **{who}** saiu da sua PT (#{sid}). "
                    "Talvez seja preciso chamar outra pessoa.",
        color=discord.Color.orange(),
    )
    await channel.send(
        content=f"<@{item.target_user_id}>",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
        delete_after=NOTICE_TTL_S,
    )


async def _send_party_rescheduled(channel: discord.TextChannel, item: Outbox):
    data = json.loads(item.payload or "{}")
    who      = data.get("who", "Alguém")
    sid      = data.get("schedule_id")
    scope    = data.get("scope", "once")
    diff     = data.get("difficulty", "")
    link     = data.get("link", SITE_URL)
    new_iso  = data.get("new_start")
    try:
        when = datetime.fromisoformat(new_iso).strftime("%d/%m %H:%M") if new_iso else "novo horário"
    except (ValueError, TypeError):
        when = "novo horário"

    if scope == "once":
        title = "📅 PT remarcada — só esta semana"
        desc = (
            f"<@{item.target_user_id}>, **{who}** remarcou a PT 💀 **{diff}** (#{sid}) "
            f"**desta semana** para `{when}`.\n"
            f"Na próxima semana volta ao horário de sempre.\n"
            f"➡️ Confirme presença no site: {link}"
        )
        color = discord.Color.blue()
    else:
        title = "🔁 Horário fixo da PT alterado"
        desc = (
            f"<@{item.target_user_id}>, **{who}** mudou o horário fixo da PT 💀 **{diff}** (#{sid}) "
            f"para `{when}` — valendo a partir de agora.\n"
            f"➡️ Confirme presença no site: {link}"
        )
        color = discord.Color.purple()

    embed = discord.Embed(title=title, description=desc, color=color)
    await channel.send(
        content=f"<@{item.target_user_id}>",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
        delete_after=NOTICE_TTL_S,
    )


async def _rollover_recurring(bot: discord.Client):
    """Recorrência semanal: parties cuja ocorrência efetiva já terminou avançam para a
    próxima semana. Uma remarcação de 1 semana (override) é consumida aqui — limpa o
    override e pula o slot fixo desta semana, voltando ao normal na próxima."""
    now = now_local()
    touched_pokemons: dict[int, Pokemon] = {}
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule).where(
                Schedule.status.in_(["pending", "confirmed", "rescheduled"]),
            )
        )
        rolled = 0
        for s in result.scalars().all():
            if _eff_end(s) >= now:
                continue  # ocorrência efetiva ainda não terminou

            # Libera os pokémons dos membros desta party que terminou
            members = (await db.execute(
                select(PartyMember).where(PartyMember.party_id == s.party_id)
            )).scalars().all()
            member_ids = {m.user_id for m in members if not m.is_external}
            if member_ids:
                held = (await db.execute(
                    select(Pokemon).where(Pokemon.assigned_to.in_(member_ids))
                )).scalars().all()
                for p in held:
                    prev_owner = p.assigned_to
                    p.assigned_to = None
                    p.assigned_at = None
                    db.add(History(
                        actor_id=prev_owner,
                        entity_type="pokemon",
                        entity_id=p.id,
                        action="unassigned",
                        detail=json.dumps({"pokemon": p.name, "auto": True}),
                        happened_at=now
                    ))
                    touched_pokemons[p.id] = p

            # Consome o ciclo. Se tinha override, a ocorrência base desta semana fica
            # suprimida → avança o slot fixo ao menos uma semana.
            had_override = s.override_start is not None
            s.override_start = None
            s.override_end   = None
            if had_override:
                s.start_time += timedelta(days=7)
                s.end_time   += timedelta(days=7)
            while s.start_time <= now:  # cobre bot fora do ar por vários dias
                s.start_time += timedelta(days=7)
                s.end_time   += timedelta(days=7)
            s.status = "pending"
            confs = await db.execute(
                select(ScheduleConfirmation).where(ScheduleConfirmation.schedule_id == s.id)
            )
            for conf in confs.scalars().all():
                conf.confirmed = False
                conf.last_ping = None
            rolled += 1
        if rolled:
            await db.commit()
            log.info(f"{rolled} party(ies) recorrente(s) avançada(s) para a próxima semana.")

    # Re-renderiza os cards do painel fora da transação
    for p in touched_pokemons.values():
        await _rerender_pokemon(bot, p)


async def _sweep_orphan_pokemons(bot: discord.Client):
    """Libera pokémons cujo dono NÃO está em nenhuma PT ativa (PT cancelada, membro que
    saiu/foi removido, ou resíduo antigo) e que foram marcados há mais que a carência.
    Complementa o rollover (que solta no fim de cada ocorrência). Quem está em PT ativa
    nunca é tocado; a carência protege marcação recém-feita (auto ou manual)."""
    now = now_local()
    cutoff = now - timedelta(seconds=POKE_ORPHAN_GRACE_S)
    freed: list[Pokemon] = []
    async with AsyncSessionLocal() as db:
        active_ids = set((await db.execute(
            select(PartyMember.user_id)
            .join(Schedule, Schedule.party_id == PartyMember.party_id)
            .where(Schedule.status.in_(["pending", "confirmed", "rescheduled"]))
        )).scalars().all())

        assigned = (await db.execute(
            select(Pokemon).where(Pokemon.assigned_to.isnot(None))
        )).scalars().all()

        for p in assigned:
            if p.assigned_to in active_ids:
                continue  # dono em PT ativa → mantém
            if p.assigned_at and p.assigned_at > cutoff:
                continue  # marcado há pouco → carência
            prev = p.assigned_to
            p.assigned_to = None
            p.assigned_at = None
            db.add(History(
                actor_id=prev, entity_type="pokemon", entity_id=p.id, action="unassigned",
                detail=json.dumps({"pokemon": p.name, "auto": True, "orphan": True}),
                happened_at=now,
            ))
            freed.append(p)

        if freed:
            await db.commit()
            log.info(f"{len(freed)} pokémon(s) órfão(s) liberado(s).")

    for p in freed:
        await _rerender_pokemon(bot, p)


async def _check_schedules(bot: discord.Client):
    await _rollover_recurring(bot)
    await _sweep_orphan_pokemons(bot)

    now = now_local()
    channel = bot.get_channel(DISCORD_NOTIFY_CHANNEL_ID)
    if not channel:
        return

    seen_keys: set[tuple[int, str]] = set()
    async with AsyncSessionLocal() as db:
        # Schedules ativos cuja ocorrência efetiva começa em até 24h ou começou há até 30 min
        eff = func.coalesce(Schedule.override_start, Schedule.start_time)
        result = await db.execute(
            select(Schedule).where(
                Schedule.status.in_(["pending", "confirmed", "rescheduled"]),
                eff <= now + timedelta(hours=24),
                eff >= now - timedelta(minutes=30),
            )
        )
        schedules = result.scalars().all()

        for schedule in schedules:
            members = (await db.execute(
                select(PartyMember).where(PartyMember.party_id == schedule.party_id)
            )).scalars().all()

            # Convidados de OUTRO servidor Discord (User.is_external) não estão na guild:
            # não há como pingar (e evita int() em ids 'ext:'). Os externos de jogo
            # (PartyMember.is_external, mas presentes no Discord) recebem aviso normalmente —
            # ficam de fora só do lembrete de pokémon (tratado em _pokemon_pt_reminder).
            real_members = []
            for m in members:
                u = await db.get(User, m.user_id)
                if u and u.is_external:
                    continue
                real_members.append(m)
            members = real_members

            sched_secs = (_eff_start(schedule) - now).total_seconds()
            iso = _eff_start(schedule).isoformat()

            # Auto-marca os pokémons no início do horário da PT (a pessoa não precisa marcar)
            if sched_secs <= 0:
                await _pokemon_auto_assign(bot, db, schedule, members)

            for member in members:
                key = (schedule.id, member.user_id)
                seen_keys.add(key)
                st = _warn_state.get(key)
                # Ocorrência mudou (rollover/remarcação): limpa
                if st and st.get("iso") != iso:
                    await _delete_warn(channel, key)
                    _warn_state.pop(key, None)
                    st = None

                conf = (await db.execute(
                    select(ScheduleConfirmation).where(
                        ScheduleConfirmation.schedule_id == schedule.id,
                        ScheduleConfirmation.user_id == member.user_id,
                    )
                )).scalar_one_or_none()
                if not conf:
                    conf = ScheduleConfirmation(schedule_id=schedule.id, user_id=member.user_id, confirmed=False)
                    db.add(conf)

                # Confirmou: apaga o aviso e encerra
                if conf.confirmed:
                    if st:
                        await _delete_warn(channel, key)
                        _warn_state.pop(key, None)
                    continue

                u = await db.get(User, member.user_id)
                lead = (u.notify_lead_minutes if (u and u.notify_lead_minutes) else 30)

                # Fora da janela de aviso?
                if sched_secs > lead * 60 or sched_secs < -30 * 60:
                    continue

                if st is None:
                    st = {"iso": iso, "msg_id": None, "sent": set(), "last_late": None}
                    _warn_state[key] = st

                # Decide qual aviso disparar
                milestone = None
                if sched_secs <= 0:
                    if st["last_late"] is None or (now - st["last_late"]).total_seconds() >= 30:
                        milestone = "late"
                elif sched_secs <= 30 and "30s" not in st["sent"]:
                    milestone = "30s"
                elif sched_secs <= 60 and "1min" not in st["sent"]:
                    milestone = "1min"
                elif sched_secs <= lead * 60 and "first" not in st["sent"]:
                    milestone = "first"

                if milestone:
                    await _delete_warn(channel, key)
                    msg = await _send_warning(channel, schedule, member, milestone, sched_secs)
                    st["msg_id"] = msg.id if msg else None
                    if milestone == "late":
                        st["last_late"] = now
                    else:
                        st["sent"].add(milestone)
                conf.last_ping = now

        await db.commit()

    # PTs que saíram da janela: apaga o aviso que sobrou no canal e limpa o estado
    for k in [k for k in _warn_state if k not in seen_keys]:
        await _delete_warn(channel, k)
        _warn_state.pop(k, None)


async def _rerender_pokemon(bot: discord.Client, pokemon: Pokemon):
    """Atualiza o card do pokémon no painel para refletir o dono atual."""
    cid = POKEMON_CHANNELS.get(pokemon.category)
    channel = bot.get_channel(cid) if cid else None
    if not channel or not pokemon.panel_message_id:
        return
    try:
        msg = channel.get_partial_message(int(pokemon.panel_message_id))
        await msg.edit(embed=build_pokemon_embed(pokemon, channel.guild))
    except Exception:
        pass


async def _pokemon_auto_assign(bot: discord.Client, db, schedule: Schedule, members: list):
    """No início do horário da PT, marca automaticamente os pokémons LIVRES da função de
    cada membro (a pessoa não precisa marcar — já é pra estar com ela). Distribui em rodízio
    entre os membros da mesma função. Externos usam pokémon próprio — são ignorados.
    Roda 1x por ocorrência."""
    iso = _eff_start(schedule).isoformat()
    if _poke_reminded.get(schedule.id) == iso:
        return

    non_ext = [m for m in members if not m.is_external]
    member_ids = {m.user_id for m in non_ext}
    if not member_ids:
        return

    touched: dict[int, Pokemon] = {}  # pokémons a re-renderizar (deduplicados por id)

    # Libera o que estes membros tinham (da ocorrência anterior) para redistribuir do zero
    held = (await db.execute(select(Pokemon).where(Pokemon.assigned_to.in_(member_ids)))).scalars().all()
    for p in held:
        p.assigned_to = None
        p.assigned_at = None
        touched[p.id] = p
    await db.flush()

    assigned: dict[str, list[tuple]] = {}  # cat -> [(member, pokemon)]
    for cat in ["A", "B", "C"]:
        role_members = [m for m in non_ext if ROLE_TO_CAT.get(m.role) == cat]
        if not role_members:
            continue
        free = (await db.execute(
            select(Pokemon).where(Pokemon.category == cat, Pokemon.assigned_to.is_(None)).order_by(Pokemon.name)
        )).scalars().all()
        for i, p in enumerate(free):
            m = role_members[i % len(role_members)]
            p.assigned_to = m.user_id
            p.assigned_at = now_local()
            touched[p.id] = p
            assigned.setdefault(cat, []).append((m, p))
            db.add(History(actor_id=m.user_id, entity_type="pokemon", entity_id=p.id,
                           action="assigned", detail=json.dumps({"pokemon": p.name, "auto": True})))

    await db.commit()

    # Atualiza os cards do painel
    for p in touched.values():
        await _rerender_pokemon(bot, p)

    # Avisa cada canal de função o que foi marcado (auto-apaga)
    for cat, pairs in assigned.items():
        channel = bot.get_channel(POKEMON_CHANNELS.get(cat)) if POKEMON_CHANNELS.get(cat) else None
        if not channel:
            continue
        by_member: dict[str, list[str]] = {}
        for m, p in pairs:
            by_member.setdefault(m.user_id, []).append(p.name)
        lines = []
        for uid, names in by_member.items():
            mem = channel.guild.get_member(int(uid)) if channel.guild else None
            who = mem.mention if mem else f"<@{uid}>"
            lines.append(f"{who}: {', '.join(names)}")
        embed = discord.Embed(
            title=f"🎯 {CAT_LABEL[cat]} — pokémons marcados automaticamente",
            description=(f"A PT **{schedule.difficulty}** está começando. "
                        f"Já marquei os livres pra vocês:\n\n" + "\n".join(lines)),
            color=discord.Color.teal(),
        )
        await channel.send(embed=embed, delete_after=POKE_REMINDER_TTL_S)

    _poke_reminded[schedule.id] = iso


async def _send_warning(channel: discord.TextChannel, schedule: Schedule, member, milestone: str, secs: float):
    guild = channel.guild
    mem = guild.get_member(int(member.user_id))
    if not mem:
        return None

    if milestone == "first":
        mins = max(1, int(secs / 60))
        title, when = "⏰ Sua PT está chegando", f"em **{mins} min**"
        color = discord.Color.orange()
    elif milestone == "1min":
        title, when, color = "⏰ Falta 1 minuto!", "em **1 minuto**", discord.Color.orange()
    elif milestone == "30s":
        title, when, color = "⏰ Faltam 30 segundos!", "em **30 segundos**", discord.Color.gold()
    else:  # late
        late_min = int((-secs) / 60)
        title = "🚨 A PT já começou — cadê você?"
        when = f"há **{late_min} min**" if late_min else "**agora**"
        color = discord.Color.red()

    embed = discord.Embed(
        title=title,
        description=(
            f"{mem.mention}, a PT 💀 **{schedule.difficulty}** (`{member.role}`) começa {when}.\n"
            f"Reaja ✅ para confirmar."
        ),
        color=color,
    )
    embed.set_footer(text=f"schedule_id:{schedule.id}|user_id:{member.user_id}")
    msg = await channel.send(
        content=mem.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)
    )
    await msg.add_reaction("✅")
    return msg


async def handle_confirmation(bot: discord.Client, payload: discord.RawReactionActionEvent):
    """Chamado pelo evento on_raw_reaction_add para confirmações de schedule."""
    if str(payload.emoji) != "✅":
        return
    if payload.channel_id != DISCORD_NOTIFY_CHANNEL_ID:
        return
    if payload.user_id == bot.user.id:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    schedule_id = None
    expected_user_id = None

    if message.embeds:
        footer = message.embeds[0].footer.text or ""
        for part in footer.split("|"):
            part = part.strip()
            if part.startswith("schedule_id:"):
                try:
                    schedule_id = int(part.split(":")[1])
                except ValueError:
                    pass
            elif part.startswith("user_id:"):
                expected_user_id = part.split(":")[1]

    if not schedule_id or not expected_user_id:
        return
    if str(payload.user_id) != expected_user_id:
        return

    async with AsyncSessionLocal() as db:
        conf = await db.execute(
            select(ScheduleConfirmation).where(
                ScheduleConfirmation.schedule_id == schedule_id,
                ScheduleConfirmation.user_id == expected_user_id,
            )
        )
        conf = conf.scalar_one_or_none()
        if conf:
            conf.confirmed = True
            await db.commit()

    # Avisar e deletar: apaga a mensagem ao confirmar e limpa o estado
    _warn_state.pop((schedule_id, expected_user_id), None)
    try:
        await message.delete()
    except Exception:
        pass
