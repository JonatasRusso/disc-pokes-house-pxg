import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from api.database import AsyncSessionLocal
from api.models import Pokemon, User
from bot.config import DISCORD_POKEMON_CHANNEL_ID

log = logging.getLogger(__name__)

CATEGORY_LABEL = {"A": "Tank", "B": "DPS", "C": "Sup"}


def valid_image_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if url.startswith(("http://", "https://")) and len(url) <= 2048 and " " not in url:
        return url
    return None


def _status(pokemon: Pokemon, guild: discord.Guild | None) -> tuple[str, discord.Color]:
    if pokemon.assigned_to:
        member = guild.get_member(int(pokemon.assigned_to)) if guild else None
        who = member.display_name if member else pokemon.assigned_to
        return f"🟢 {who}", discord.Color.green()
    return "⚪ Livre", discord.Color.greyple()


def build_pokemon_embed(pokemon: Pokemon, guild: discord.Guild | None) -> discord.Embed:
    """Nome à esquerda, miniatura à direita, status abaixo. Bem enxuto."""
    status, color = _status(pokemon, guild)
    role = CATEGORY_LABEL.get(pokemon.category, pokemon.category)
    embed = discord.Embed(title=pokemon.name, description=f"{role} · {status}", color=color)
    img = valid_image_url(pokemon.image_url)
    if img:
        embed.set_thumbnail(url=img)
    return embed


class PokemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="meus-pokemon", description="Ver pokémons atribuídos a você")
    async def meus_pokemon(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        async with AsyncSessionLocal() as db:
            pokemons = (await db.execute(
                select(Pokemon).where(Pokemon.assigned_to == user_id).order_by(Pokemon.category, Pokemon.name)
            )).scalars().all()

        if not pokemons:
            await interaction.response.send_message("Você não está usando nenhum pokémon no momento.", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Seus Pokémons em Uso", color=discord.Color.purple())
        for cat in ["A", "B", "C"]:
            group = [p for p in pokemons if p.category == cat]
            if group:
                embed.add_field(name=CATEGORY_LABEL[cat], value="\n".join(f"• {p.name}" for p in group), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pokemon-status", description="Ver grid de uso de todos os pokémons")
    async def pokemon_status(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as db:
            pokemons = (await db.execute(select(Pokemon).order_by(Pokemon.category, Pokemon.name))).scalars().all()

        embed = discord.Embed(title="📊 Status dos Pokémons", color=discord.Color.gold())
        for cat in ["A", "B", "C"]:
            group = [p for p in pokemons if p.category == cat]
            if group:
                lines = []
                for p in group:
                    status, _ = _status(p, interaction.guild)
                    lines.append(f"{status} — {p.name}")
                embed.add_field(name=CATEGORY_LABEL[cat], value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pokemon-painel", description="(Admin) Postar o painel de pokémons no canal")
    async def pokemon_painel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            async with AsyncSessionLocal() as db:
                user = await db.get(User, str(interaction.user.id))
                is_admin = bool(user and user.is_admin)
                if not is_admin and interaction.guild and interaction.guild.owner_id == interaction.user.id:
                    is_admin = True
                if not is_admin:
                    await interaction.followup.send("Apenas admins podem postar o painel.", ephemeral=True)
                    return
                pokemons = (await db.execute(
                    select(Pokemon).order_by(Pokemon.category, Pokemon.name)
                )).scalars().all()

            channel = interaction.guild.get_channel(DISCORD_POKEMON_CHANNEL_ID) if interaction.guild else None
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(DISCORD_POKEMON_CHANNEL_ID)
                except Exception:
                    channel = None
            if channel is None:
                await interaction.followup.send(
                    f"Canal de pokémons (ID `{DISCORD_POKEMON_CHANNEL_ID}`) não encontrado.", ephemeral=True)
                return

            perms = channel.permissions_for(interaction.guild.me)
            missing = [n for n, ok in [
                ("Ver Canal", perms.view_channel), ("Enviar Mensagens", perms.send_messages),
                ("Inserir Links (Embeds)", perms.embed_links), ("Adicionar Reações", perms.add_reactions),
            ] if not ok]
            if missing:
                await interaction.followup.send(
                    f"O bot não tem permissão em {channel.mention}: faltando **{', '.join(missing)}**.", ephemeral=True)
                return
            if not pokemons:
                await interaction.followup.send(
                    "Nenhum pokémon cadastrado. Adicione pela aba **Pokémons** no site.", ephemeral=True)
                return

            try:
                await channel.purge(limit=300, check=lambda m: m.author == self.bot.user)
            except Exception as e:
                log.warning(f"purge falhou: {e}")

            await channel.send("🎯 **Painel de Pokémons** — reaja 🎯 para marcar, remova para liberar.")
            posted: dict[int, str] = {}
            for cat in ["A", "B", "C"]:
                group = [p for p in pokemons if p.category == cat]
                if not group:
                    continue
                await channel.send(f"__**{CATEGORY_LABEL[cat]}**__")
                for p in group:
                    msg = await channel.send(embed=build_pokemon_embed(p, interaction.guild))
                    await msg.add_reaction("🎯")
                    posted[p.id] = str(msg.id)

            # Liga cada mensagem ao pokémon (substitui o ID que ficava visível no card)
            async with AsyncSessionLocal() as db:
                for pid, mid in posted.items():
                    pk = await db.get(Pokemon, pid)
                    if pk:
                        pk.panel_message_id = mid
                await db.commit()

            await interaction.followup.send(f"✅ Painel postado em {channel.mention} ({len(posted)}).", ephemeral=True)
        except Exception as e:
            log.exception("Erro no /pokemon-painel")
            await interaction.followup.send(f"Erro: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PokemonCog(bot))
