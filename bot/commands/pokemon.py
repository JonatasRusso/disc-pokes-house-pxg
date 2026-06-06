import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from api.database import AsyncSessionLocal
from api.models import History, Pokemon, User
from bot.config import DISCORD_POKEMON_CHANNEL_ID

log = logging.getLogger(__name__)

CATEGORY_LABEL = {"A": "Tank", "B": "DPS", "C": "Sup"}
GALLERY_URL = "https://discord.com"


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
    """Nome à esquerda, miniatura à direita, status abaixo. Sem textos extras."""
    status, color = _status(pokemon, guild)
    role = CATEGORY_LABEL.get(pokemon.category, pokemon.category)
    embed = discord.Embed(
        title=pokemon.name,
        description=f"{role} · {status}",
        color=color,
    )
    embed.set_footer(text=f"ID: {pokemon.id}")
    img = valid_image_url(pokemon.image_url)
    if img:
        embed.set_thumbnail(url=img)  # miniatura no canto superior direito
    return embed


def build_gallery_embeds(pokemons: list[Pokemon], title: str) -> list[discord.Embed]:
    """Opção 3: várias imagens lado a lado (truque de embeds com a mesma URL)."""
    imgs = [p for p in pokemons if valid_image_url(p.image_url)]
    embeds: list[discord.Embed] = []
    for i, p in enumerate(imgs[:4]):  # Discord agrupa até 4 imagens numa galeria
        e = discord.Embed(url=GALLERY_URL, color=discord.Color.blurple())
        if i == 0:
            e.title = title
        e.set_image(url=valid_image_url(p.image_url))
        embeds.append(e)
    if not embeds:
        embeds = [discord.Embed(title=title, color=discord.Color.blurple())]
    return embeds


# ---------- Opção 3: botões ----------

async def _toggle_pokemon_button(interaction: discord.Interaction, pokemon_id: int):
    uid = str(interaction.user.id)
    async with AsyncSessionLocal() as db:
        p = await db.get(Pokemon, pokemon_id)
        if not p:
            await interaction.response.send_message("Esse pokémon não existe mais.", ephemeral=True)
            return
        if not await db.get(User, uid):
            db.add(User(discord_id=uid, username=interaction.user.name,
                        avatar_url=str(interaction.user.display_avatar.url)))
            await db.flush()

        if p.assigned_to == uid:
            p.assigned_to, p.assigned_at = None, None
            action, feedback = "unassigned", f"Você liberou **{p.name}**."
        else:
            prev = p.assigned_to
            p.assigned_to, p.assigned_at = uid, datetime.utcnow()
            action = "overridden" if prev else "assigned"
            feedback = f"Você marcou **{p.name}**."
        db.add(History(actor_id=uid, entity_type="pokemon", entity_id=pokemon_id,
                       action=action, detail=f'{{"pokemon":"{p.name}"}}', happened_at=datetime.utcnow()))
        await db.commit()

    await interaction.response.send_message(feedback, ephemeral=True)

    # Atualiza os botões/galeria da mensagem
    ids = []
    for row in interaction.message.components:
        for comp in getattr(row, "children", []):
            cid = getattr(comp, "custom_id", "") or ""
            if cid.startswith("pokebtn:"):
                ids.append(int(cid.split(":")[1]))
    if not ids:
        return
    async with AsyncSessionLocal() as db:
        pokes = (await db.execute(
            select(Pokemon).where(Pokemon.id.in_(ids)).order_by(Pokemon.category, Pokemon.name)
        )).scalars().all()
    cat = pokes[0].category if pokes else ""
    embeds = build_gallery_embeds(pokes, CATEGORY_LABEL.get(cat, cat))
    try:
        await interaction.message.edit(embeds=embeds, view=PokeGridView(pokes))
    except discord.HTTPException:
        pass


class PokeButton(discord.ui.Button):
    def __init__(self, pokemon: Pokemon):
        taken = bool(pokemon.assigned_to)
        super().__init__(
            label=pokemon.name[:80],
            emoji="🟢" if taken else "⚪",
            style=discord.ButtonStyle.secondary if taken else discord.ButtonStyle.success,
            custom_id=f"pokebtn:{pokemon.id}",
        )
        self.pokemon_id = pokemon.id

    async def callback(self, interaction: discord.Interaction):
        await _toggle_pokemon_button(interaction, self.pokemon_id)


class PokeGridView(discord.ui.View):
    def __init__(self, pokemons: list[Pokemon]):
        super().__init__(timeout=None)
        for p in pokemons[:25]:  # máximo de componentes por mensagem
            self.add_item(PokeButton(p))


# ---------- Cog ----------

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

    async def _resolve_channel_and_admin(self, interaction: discord.Interaction):
        """Retorna (channel, pokemons) ou envia erro e retorna (None, None)."""
        async with AsyncSessionLocal() as db:
            user = await db.get(User, str(interaction.user.id))
            is_admin = bool(user and user.is_admin)
            if not is_admin and interaction.guild and interaction.guild.owner_id == interaction.user.id:
                is_admin = True
            if not is_admin:
                await interaction.followup.send("Apenas admins podem postar o painel.", ephemeral=True)
                return None, None
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
            return None, None

        perms = channel.permissions_for(interaction.guild.me)
        missing = [n for n, ok in [
            ("Ver Canal", perms.view_channel), ("Enviar Mensagens", perms.send_messages),
            ("Inserir Links (Embeds)", perms.embed_links), ("Adicionar Reações", perms.add_reactions),
        ] if not ok]
        if missing:
            await interaction.followup.send(
                f"O bot não tem permissão em {channel.mention}: faltando **{', '.join(missing)}**.", ephemeral=True)
            return None, None
        if not pokemons:
            await interaction.followup.send(
                "Nenhum pokémon cadastrado. Adicione pela aba **Pokémons** no site.", ephemeral=True)
            return None, None

        try:
            await channel.purge(limit=300, check=lambda m: m.author == self.bot.user)
        except Exception as e:
            log.warning(f"purge falhou: {e}")
        return channel, pokemons

    @app_commands.command(name="pokemon-painel", description="(Admin) Painel com imagens grandes (marca com reação 🎯)")
    async def pokemon_painel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            channel, pokemons = await self._resolve_channel_and_admin(interaction)
            if not channel:
                return
            await channel.send("🎯 **Painel de Pokémons** — reaja 🎯 para marcar, remova para liberar.")
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
            await interaction.followup.send(f"✅ Painel (imagens) postado em {channel.mention} ({count}).", ephemeral=True)
        except Exception as e:
            log.exception("Erro no /pokemon-painel")
            await interaction.followup.send(f"Erro: `{e}`", ephemeral=True)

    @app_commands.command(name="pokemon-botoes", description="(Admin) Painel em grade com botões (marca clicando)")
    async def pokemon_botoes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            channel, pokemons = await self._resolve_channel_and_admin(interaction)
            if not channel:
                return
            await channel.send("🎯 **Painel de Pokémons (botões)** — clique no pokémon para marcar/desmarcar.")
            for cat in ["A", "B", "C"]:
                group = [p for p in pokemons if p.category == cat]
                if not group:
                    continue
                embeds = build_gallery_embeds(group, CATEGORY_LABEL[cat])
                await channel.send(embeds=embeds, view=PokeGridView(group))
            await interaction.followup.send(f"✅ Painel (botões) postado em {channel.mention}.", ephemeral=True)
        except Exception as e:
            log.exception("Erro no /pokemon-botoes")
            await interaction.followup.send(f"Erro: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PokemonCog(bot))
