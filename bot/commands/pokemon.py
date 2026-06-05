import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import Pokemon, User


CATEGORY_LABEL = {"A": "Tank", "B": "DPS", "C": "Sup"}


class PokemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="meus-pokemon", description="Ver pokémons atribuídos a você")
    async def meus_pokemon(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Pokemon).where(Pokemon.assigned_to == user_id).order_by(Pokemon.category, Pokemon.name)
            )
            pokemons = result.scalars().all()

        if not pokemons:
            await interaction.response.send_message("Você não está usando nenhum pokémon no momento.", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Seus Pokémons em Uso", color=discord.Color.purple())
        for cat in ["A", "B", "C"]:
            group = [p for p in pokemons if p.category == cat]
            if group:
                embed.add_field(
                    name=CATEGORY_LABEL[cat],
                    value="\n".join(f"• {p.name}" for p in group),
                    inline=False,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pokemon-status", description="Ver grid de uso de todos os pokémons")
    async def pokemon_status(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Pokemon).order_by(Pokemon.category, Pokemon.name))
            pokemons = result.scalars().all()

        embed = discord.Embed(title="📊 Status dos Pokémons", color=discord.Color.gold())
        for cat in ["A", "B", "C"]:
            group = [p for p in pokemons if p.category == cat]
            if group:
                lines = []
                for p in group:
                    if p.assigned_to:
                        guild = interaction.guild
                        member = guild.get_member(int(p.assigned_to)) if guild else None
                        name = member.display_name if member else p.assigned_to
                        lines.append(f"🟢 {p.name} — {name}")
                    else:
                        lines.append(f"⚪ {p.name} — *livre*")
                embed.add_field(name=CATEGORY_LABEL[cat], value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pokemon-anunciar", description="(Admin) Anunciar pokémon disponível para uso")
    @app_commands.describe(pokemon_id="ID do pokémon", mensagem="Mensagem opcional")
    async def pokemon_anunciar(self, interaction: discord.Interaction, pokemon_id: int, mensagem: str = ""):
        async with AsyncSessionLocal() as db:
            pokemon = await db.get(Pokemon, pokemon_id)
            if not pokemon:
                await interaction.response.send_message("Pokémon não encontrado.", ephemeral=True)
                return

            user = await db.get(User, str(interaction.user.id))
            if not user or not user.is_admin:
                await interaction.response.send_message("Apenas admins podem anunciar pokémons.", ephemeral=True)
                return

        from bot.config import DISCORD_POKEMON_CHANNEL_ID
        channel = interaction.guild.get_channel(DISCORD_POKEMON_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Canal de pokémons não encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎯 {pokemon.name} disponível!",
            description=mensagem or f"**{pokemon.name}** [{CATEGORY_LABEL[pokemon.category]}] está livre para uso.\nReaja com 🎯 para marcar que vai usar.",
            color=discord.Color.yellow(),
        )
        embed.set_footer(text=f"ID: {pokemon.id} | Categoria: {pokemon.category}")
        if pokemon.image_url:
            embed.set_thumbnail(url=pokemon.image_url)

        msg = await channel.send(embed=embed)
        await msg.add_reaction("🎯")
        await interaction.response.send_message(f"Anúncio postado em {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PokemonCog(bot))
