import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import Schedule, ScheduleConfirmation, Party, PartyMember, User
from bot.config import SITE_URL


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="agendar", description="Abrir formulário para agendar uma PT")
    async def agendar(self, interaction: discord.Interaction):
        url = f"{SITE_URL}/agendar"
        embed = discord.Embed(
            title="📅 Agendar Horário",
            description=f"Clique no link para preencher o formulário no site:\n\n**[Abrir formulário]({url})**",
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Você precisará fazer login com Discord no site.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="meus-horarios", description="Ver seus próximos horários agendados")
    async def meus_horarios(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Schedule)
                .join(Party)
                .join(PartyMember, PartyMember.party_id == Party.id)
                .where(
                    PartyMember.user_id == user_id,
                    Schedule.status.in_(["pending", "confirmed", "rescheduled"]),
                )
                .order_by(Schedule.start_time)
                .limit(5)
            )
            schedules = result.scalars().all()

        if not schedules:
            await interaction.response.send_message("Você não tem horários agendados.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Seus Horários", color=discord.Color.green())
        for s in schedules:
            eff_start = s.override_start or s.start_time
            eff_end   = s.override_end or s.end_time
            extra = "\n📌 Remarcada só esta semana (volta ao normal depois)" if s.override_start else ""
            embed.add_field(
                name=f"ID #{s.id} — {s.difficulty}",
                value=f"🕐 {eff_start.strftime('%d/%m/%Y %H:%M')} → {eff_end.strftime('%H:%M')}\nStatus: `{s.status}`{extra}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="nao-posso", description="Avisar que não pode comparecer e remarcar")
    @app_commands.describe(id="ID do horário (use /meus-horarios para ver)")
    async def nao_posso(self, interaction: discord.Interaction, id: int):
        once_url = f"{SITE_URL}/remarcar/{id}?scope=once"
        all_url  = f"{SITE_URL}/remarcar/{id}?scope=all"
        embed = discord.Embed(
            title="❌ Remarcar Horário",
            description=(
                f"Como você quer remarcar a PT **#{id}**?\n\n"
                f"📅 **Só esta semana** — move apenas a próxima ocorrência; "
                f"na semana seguinte volta ao horário de sempre.\n"
                f"🔁 **Todas as semanas** — muda o horário fixo da PT a partir de agora.\n\n"
                f"Você escolhe o novo horário no site. Os outros membros são avisados automaticamente."
            ),
            color=discord.Color.orange(),
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="📅 Só esta semana", style=discord.ButtonStyle.link, url=once_url))
        view.add_item(discord.ui.Button(label="🔁 Todas as semanas", style=discord.ButtonStyle.link, url=all_url))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleCog(bot))
