import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from api.database import AsyncSessionLocal
from api.models import Pokemon, User
from bot.config import POKEMON_CHANNELS

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

            if not pokemons:
                await interaction.followup.send(
                    "Nenhum pokémon cadastrado. Adicione pela aba **Pokémons** no site.", ephemeral=True)
                return

            async def _resolve(cid):
                ch = interaction.guild.get_channel(cid) if (cid and interaction.guild) else None
                if ch is None and cid:
                    try:
                        ch = await self.bot.fetch_channel(cid)
                    except Exception:
                        ch = None
                return ch

            posted: dict[int, str] = {}
            purged: set[int] = set()
            used_channels: set = set()
            for cat in ["A", "B", "C"]:
                group = [p for p in pokemons if p.category == cat]
                if not group:
                    continue
                cid = POKEMON_CHANNELS.get(cat)
                channel = await _resolve(cid)
                if channel is None:
                    await interaction.followup.send(
                        f"Canal de **{CATEGORY_LABEL[cat]}** (ID `{cid}`) não encontrado. "
                        "Verifique as variáveis `DISCORD_POKEMON_CHANNEL_*` no Railway.", ephemeral=True)
                    return

                perms = channel.permissions_for(interaction.guild.me)
                missing = [n for n, ok in [
                    ("Ver Canal", perms.view_channel), ("Enviar Mensagens", perms.send_messages),
                    ("Inserir Links (Embeds)", perms.embed_links), ("Adicionar Reações", perms.add_reactions),
                ] if not ok]
                if missing:
                    await interaction.followup.send(
                        f"Sem permissão em {channel.mention} (**{CATEGORY_LABEL[cat]}**): faltando **{', '.join(missing)}**.",
                        ephemeral=True)
                    return

                # Limpa o canal uma vez (vários grupos podem cair no mesmo canal se usar o canal único)
                if channel.id not in purged:
                    try:
                        await channel.purge(limit=300, check=lambda m: m.author == self.bot.user)
                    except Exception as e:
                        log.warning(f"purge falhou em {channel.id}: {e}")
                    purged.add(channel.id)
                    await channel.send("🎯 **Painel de Pokémons** — reaja 🎯 para marcar, remova para liberar.")

                await channel.send(f"__**{CATEGORY_LABEL[cat]}**__")
                for p in group:
                    msg = await channel.send(embed=build_pokemon_embed(p, interaction.guild))
                    await msg.add_reaction("🎯")
                    posted[p.id] = str(msg.id)
                used_channels.add(channel.mention)

            # Liga cada mensagem ao pokémon
            async with AsyncSessionLocal() as db:
                for pid, mid in posted.items():
                    pk = await db.get(Pokemon, pid)
                    if pk:
                        pk.panel_message_id = mid
                await db.commit()

            await interaction.followup.send(
                f"✅ Painel postado em {', '.join(used_channels)} ({len(posted)} pokémons).", ephemeral=True)
        except Exception as e:
            log.exception("Erro no /pokemon-painel")
            await interaction.followup.send(f"Erro: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PokemonCog(bot))
