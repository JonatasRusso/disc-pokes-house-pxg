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
from api.models import Outbox, Schedule, ScheduleConfirmation, PartyMember, User
from bot.config import DISCORD_NOTIFY_CHANNEL_ID, SITE_URL

log = logging.getLogger(__name__)

# schedule_id -> message_id da mensagem de notificação no Discord
_active_pings: dict[int, int] = {}


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


async def _check_schedules(bot: discord.Client):
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
