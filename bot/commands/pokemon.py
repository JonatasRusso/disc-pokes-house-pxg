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


def build_pokemon_embed(pokemon: Pokemon, guild: discord.Guild | None) -> discord.Embed:
    """Embed de um pokémon no painel, com status de uso e footer com o ID."""
    if pokemon.assigned_to:
        member = guild.get_member(int(pokemon.assigned_to)) if guild else None
        who = member.display_name if member else pokemon.assigned_to
        status = f"🟢 Em uso por **{who}**"
        color = discord.Color.green()
    else:
        status = "⚪ Livre"
        color = discord.Color.greyple()

    embed = discord.Embed(
        title=pokemon.name,
        description=f"`{CATEGORY_LABEL.get(pokemon.category, pokemon.category)}` · {status}\n"
                    f"Reaja 🎯 para marcar · remova a reação para liberar",
        color=color,
    )
    embed.set_footer(text=f"ID: {pokemon.id}")
    url = (pokemon.image_url or "").strip()
    if url.startswith(("http://", "https://")) and len(url) <= 2048 and " " not in url:
        embed.set_thumbnail(url=url)
    return embed


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

    @app_commands.command(name="pokemon-painel", description="(Admin) Postar/atualizar o painel de pokémons no canal")
    async def pokemon_painel(self, interaction: discord.Interaction):
        # Defer evita timeout de 3s e permite responder erros depois do trabalho
        await interaction.response.defer(ephemeral=True)
        try:
            async with AsyncSessionLocal() as db:
                user = await db.get(User, str(interaction.user.id))
                is_admin = bool(user and user.is_admin)
                if not is_admin and interaction.guild and interaction.guild.owner_id == interaction.user.id:
                    is_admin = True
                if not is_admin:
                    await interaction.followup.send(
                        "Apenas admins podem postar o painel. Peça para o dono usar `/admin` em você.",
                        ephemeral=True,
                    )
                    return
                pokemons = (await db.execute(
                    select(Pokemon).order_by(Pokemon.category, Pokemon.name)
                )).scalars().all()

            # Resolve o canal de pokémons
            channel = interaction.guild.get_channel(DISCORD_POKEMON_CHANNEL_ID) if interaction.guild else None
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(DISCORD_POKEMON_CHANNEL_ID)
                except Exception:
                    channel = None
            if channel is None:
                await interaction.followup.send(
                    f"Canal de pokémons (ID `{DISCORD_POKEMON_CHANNEL_ID}`) não encontrado. "
                    "Verifique a variável `DISCORD_POKEMON_CHANNEL_ID` no Railway.",
                    ephemeral=True,
                )
                return

            # Confere permissões do bot no canal
            perms = channel.permissions_for(interaction.guild.me)
            missing = [n for n, ok in [
                ("Ver Canal", perms.view_channel),
                ("Enviar Mensagens", perms.send_messages),
                ("Inserir Links (Embeds)", perms.embed_links),
                ("Adicionar Reações", perms.add_reactions),
            ] if not ok]
            if missing:
                await interaction.followup.send(
                    f"O bot não tem permissão em {channel.mention}: faltando **{', '.join(missing)}**.",
                    ephemeral=True,
                )
                return

            if not pokemons:
                await interaction.followup.send(
                    "Nenhum pokémon cadastrado ainda. Adicione pela aba **Pokémons** no site primeiro.",
                    ephemeral=True,
                )
                return

            # Limpa o painel anterior do bot neste canal
            try:
                await channel.purge(limit=300, check=lambda m: m.author == self.bot.user)
            except discord.Forbidden:
                pass
            except Exception as e:
                log.warning(f"purge do painel falhou: {e}")

            await channel.send(
                "🎯 **Painel de Pokémons da VKG House**\n"
                "Reaja com 🎯 em um pokémon para marcar que vai usá-lo. Remova a reação para liberar."
            )
            count = 0
            for cat in ["A", "B", "C"]:
                group = [p for p in pokemons if p.category == cat]
                if not group:
                    continue
                await channel.send(f"__**{CATEGORY_LABEL[cat]}**__")
                for p in group:
                    msg = await channel.send(embed=build_pokemon_embed(p, interaction.guild))
                    await msg.add_reaction("🎯")
                    count += 1

            await interaction.followup.send(
                f"✅ Painel postado em {channel.mention} ({count} pokémons).", ephemeral=True
            )
        except Exception as e:
            log.exception("Erro no /pokemon-painel")
            try:
                await interaction.followup.send(f"Erro ao postar o painel: `{e}`", ephemeral=True)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(PokemonCog(bot))
