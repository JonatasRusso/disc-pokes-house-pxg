"""
Scheduler de notificações de horários de party.
- A cada minuto verifica schedules que começam em ≤30 min e ainda não foram notificados.
- Pinga cada membro não confirmado a cada minuto até confirmação ou início da party.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from api.database import AsyncSessionLocal
from api.models import Outbox, Pokemon, Schedule, ScheduleConfirmation, PartyMember, User
from bot.config import DISCORD_NOTIFY_CHANNEL_ID, DISCORD_POKEMON_CHANNEL_ID, SITE_URL

log = logging.getLogger(__name__)

# schedule_id -> message_id da mensagem de notificação no Discord
_active_pings: dict[int, int] = {}

# schedule_id -> start_time iso já lembrado (evita repetir o lembrete de pokémon na mesma ocorrência)
_poke_reminded: dict[int, str] = {}

ROLE_TO_CAT  = {"TANK": "A", "DPS": "B", "SUP": "C"}
CAT_LABEL    = {"A": "Tank", "B": "DPS", "C": "Sup"}


def start_scheduler(bot: discord.Client):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_check_schedules, "interval", minutes=1, args=[bot])
    scheduler.add_job(_process_outbox, "interval", seconds=20, args=[bot])
    scheduler.start()
    log.info("Scheduler iniciado.")
    return scheduler


async def _process_outbox(bot: discord.Client):
    """Envia mensagens enfileiradas pela API (convites de PT, etc)."""
    channel = bot.get_channel(DISCORD_NOTIFY_CHANNEL_ID)
    if not channel:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Outbox).where(Outbox.sent_at.is_(None)).order_by(Outbox.id).limit(20)
        )
        items = result.scalars().all()

        for item in items:
            try:
                if item.kind == "party_invite":
                    await _send_party_invite(channel, item)
            except Exception as e:
                log.warning(f"Falha ao enviar outbox #{item.id}: {e}")
                continue
            item.sent_at = datetime.utcnow()

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
        title="🎉 Convite de Party",
        description=desc,
        color=discord.Color.blurple(),
    )
    await channel.send(
        content=f"<@{item.target_user_id}>",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )


async def _rollover_recurring():
    """Recorrência semanal: parties que já terminaram avançam para a próxima semana."""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule).where(
                Schedule.status.in_(["pending", "confirmed", "rescheduled"]),
                Schedule.end_time < now,
            )
        )
        rolled = 0
        for s in result.scalars().all():
            # Avança em blocos de 7 dias até a próxima ocorrência futura
            while s.end_time < now:
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

    now     = datetime.now(timezone.utc)
    soon    = now + timedelta(minutes=30)

    channel = bot.get_channel(DISCORD_NOTIFY_CHANNEL_ID)
    if not channel:
        log.warning("Canal de notificações não encontrado.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule).where(
                Schedule.status.in_(["pending", "confirmed"]),
                Schedule.start_time <= soon.replace(tzinfo=None),
                Schedule.start_time >= now.replace(tzinfo=None),
            )
        )
        schedules = result.scalars().all()

        for schedule in schedules:
            members_result = await db.execute(
                select(PartyMember).where(PartyMember.party_id == schedule.party_id)
            )
            members = members_result.scalars().all()

            # Lembrete de pokémons da PT (uma vez por ocorrência)
            await _pokemon_pt_reminder(bot, db, schedule, members)

            for member in members:
                conf_result = await db.execute(
                    select(ScheduleConfirmation).where(
                        ScheduleConfirmation.schedule_id == schedule.id,
                        ScheduleConfirmation.user_id == member.user_id,
                    )
                )
                conf = conf_result.scalar_one_or_none()

                if conf and conf.confirmed:
                    continue  # já confirmou

                # Cria confirmação se ainda não existe
                if not conf:
                    conf = ScheduleConfirmation(
                        schedule_id=schedule.id,
                        user_id=member.user_id,
                        confirmed=False,
                    )
                    db.add(conf)

                conf.last_ping = datetime.utcnow()
                await _send_ping(bot, channel, schedule, member.user_id, member.role)

        await db.commit()


async def _pokemon_pt_reminder(bot: discord.Client, db, schedule: Schedule, members: list):
    """Quando a PT entra na janela de 30 min, lembra os membros de marcar os pokémons (1x por ocorrência)."""
    iso = schedule.start_time.isoformat()
    if _poke_reminded.get(schedule.id) == iso:
        return

    channel = bot.get_channel(DISCORD_POKEMON_CHANNEL_ID)
    if not channel:
        return

    free = (await db.execute(select(Pokemon).where(Pokemon.assigned_to.is_(None)))).scalars().all()
    roles_present = {m.role for m in members}
    cats = {ROLE_TO_CAT[r] for r in roles_present if r in ROLE_TO_CAT}

    lines = []
    for cat in ["A", "B", "C"]:
        if cat not in cats:
            continue
        names = [p.name for p in free if p.category == cat]
        lines.append(f"**{CAT_LABEL[cat]}**: " + (", ".join(names) if names else "— nenhum livre"))

    mentions = " ".join(f"<@{m.user_id}>" for m in members)
    embed = discord.Embed(
        title="🎯 Marquem os pokémons da PT!",
        description=(
            f"A PT **{schedule.difficulty}** começa em breve.\n"
            f"Marquem seus pokémons no painel reagindo com 🎯.\n\n"
            f"Livres por função:\n" + ("\n".join(lines) if lines else "—")
        ),
        color=discord.Color.teal(),
    )
    await channel.send(
        content=mentions,
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    _poke_reminded[schedule.id] = iso


async def _send_ping(
    bot: discord.Client,
    channel: discord.TextChannel,
    schedule: Schedule,
    user_id: str,
    role: str,
):
    guild = channel.guild
    member = guild.get_member(int(user_id))
    if not member:
        return

    minutes_left = int((schedule.start_time - datetime.utcnow()).total_seconds() / 60)

    embed = discord.Embed(
        title="⏰ Confirmação de Party",
        description=(
            f"{member.mention}, sua party começa em **{minutes_left} minutos**!\n\n"
            f"🎮 Dificuldade: `{schedule.difficulty}` | Função: `{role}`\n"
            f"🕐 Horário: `{schedule.start_time.strftime('%d/%m %H:%M')}` → `{schedule.end_time.strftime('%H:%M')}`\n\n"
            f"Reaja com ✅ para confirmar ou acesse o site para remarcar:\n"
            f"[Remarcar horário #{schedule.id}]({SITE_URL}/remarcar/{schedule.id})"
        ),
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"schedule_id:{schedule.id}|user_id:{user_id}")

    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")


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

    # Edita a mensagem para indicar confirmação
    if message.embeds:
        embed = message.embeds[0].copy()
        embed.color = discord.Color.green()
        embed.title = "✅ Confirmado!"
        await message.edit(embed=embed)
