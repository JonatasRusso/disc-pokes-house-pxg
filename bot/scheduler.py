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
from api.models import Outbox, Pokemon, Schedule, ScheduleConfirmation, PartyMember, User
from api.timeutil import now_local
from bot.config import DISCORD_NOTIFY_CHANNEL_ID, POKEMON_CHANNELS, SITE_URL

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
    )


async def _rollover_recurring():
    """Recorrência semanal: parties cuja ocorrência efetiva já terminou avançam para a
    próxima semana. Uma remarcação de 1 semana (override) é consumida aqui — limpa o
    override e pula o slot fixo desta semana, voltando ao normal na próxima."""
    now = now_local()
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


async def _check_schedules(bot: discord.Client):
    await _rollover_recurring()

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

            # Lembrete de pokémons quando entra na janela de 30 min
            if 0 <= sched_secs <= 30 * 60:
                await _pokemon_pt_reminder(bot, db, schedule, members)

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

    # Limpa estado de avisos de PTs que saíram da janela (evita acúmulo em memória)
    for k in [k for k in _warn_state if k not in seen_keys]:
        _warn_state.pop(k, None)


async def _pokemon_pt_reminder(bot: discord.Client, db, schedule: Schedule, members: list):
    """Quando a PT entra na janela de 30 min, lembra os membros (1x por ocorrência).
    Posta no canal de cada função presente na PT (Tank/DPS/Sup)."""
    iso = _eff_start(schedule).isoformat()
    if _poke_reminded.get(schedule.id) == iso:
        return

    free = (await db.execute(select(Pokemon).where(Pokemon.assigned_to.is_(None)))).scalars().all()

    sent_any = False
    for cat in ["A", "B", "C"]:
        # Externos usam pokémon próprio (de outro servidor) — não são chamados para marcar
        cat_members = [m for m in members if ROLE_TO_CAT.get(m.role) == cat and not m.is_external]
        if not cat_members:
            continue
        channel = bot.get_channel(POKEMON_CHANNELS.get(cat)) if POKEMON_CHANNELS.get(cat) else None
        if not channel:
            continue

        names = [p.name for p in free if p.category == cat]
        mentions = " ".join(f"<@{m.user_id}>" for m in cat_members)
        embed = discord.Embed(
            title=f"🎯 {CAT_LABEL[cat]} — marquem os pokémons da PT!",
            description=(
                f"A PT **{schedule.difficulty}** começa em breve.\n"
                f"Marquem seus pokémons reagindo com 🎯.\n\n"
                f"Livres: " + (", ".join(names) if names else "— nenhum livre")
            ),
            color=discord.Color.teal(),
        )
        await channel.send(
            content=mentions,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        sent_any = True

    if sent_any:
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
