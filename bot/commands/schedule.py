import discord
from discord import app_commands
from discord.ext import commands
from bot.config import SITE_URL


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="site", description="Abrir o painel da House no site (PTs, agenda, pokémons)")
    async def site(self, interaction: discord.Interaction):
        url = f"{SITE_URL}/dashboard"
        embed = discord.Embed(
            title="🏠 VKG House",
            description=(
                f"Tudo é gerenciado no site:\n\n**[Abrir o painel]({url})**\n\n"
                "Lá você vê e gerencia suas PTs, agenda, remarca, confirma presença e acompanha os pokémons."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Login com Discord no site.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @app_commands.command(name="remarcar", description="Remarcar uma PT (escolher novo horário no site)")
    @app_commands.describe(id="ID do horário (veja em Minhas PTs no site)")
    async def remarcar(self, interaction: discord.Interaction, id: int):
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
