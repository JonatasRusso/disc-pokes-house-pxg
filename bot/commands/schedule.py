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
                    Schedule.status.in_(["pending", "confirmed"]),
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
            embed.add_field(
                name=f"ID #{s.id} — {s.difficulty}",
                value=f"🕐 {s.start_time.strftime('%d/%m/%Y %H:%M')} → {s.end_time.strftime('%H:%M')}\nStatus: `{s.status}`",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="nao-posso", description="Avisar que não pode comparecer e remarcar")
    @app_commands.describe(id="ID do horário (use /meus-horarios para ver)")
    async def nao_posso(self, interaction: discord.Interaction, id: int):
        url = f"{SITE_URL}/remarcar/{id}"
        embed = discord.Embed(
            title="❌ Remarcar Horário",
            description=(
                f"Clique no link para escolher um novo horário no site:\n\n"
                f"**[Remarcar horário #{id}]({url})**\n\n"
                "Os outros membros da PT serão notificados automaticamente."
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleCog(bot))
