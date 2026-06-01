import discord
from discord.ext import commands
from sqlalchemy import select
from datetime import datetime
from api.database import AsyncSessionLocal
from api.models import Pokemon, History, User
from bot.config import DISCORD_POKEMON_CHANNEL_ID


class ReactionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "🎯":
            return
        if payload.channel_id != DISCORD_POKEMON_CHANNEL_ID:
            return

        message_id = str(payload.message_id)
        user_id    = str(payload.user_id)

        async with AsyncSessionLocal() as db:
            # Encontra pokémon pelo message_id registrado na mensagem (guardamos via footer "ID: X")
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            # Extrai ID do pokémon do footer da embed
            pokemon_id = None
            if message.embeds:
                footer_text = message.embeds[0].footer.text or ""
                for part in footer_text.split("|"):
                    part = part.strip()
                    if part.startswith("ID:"):
                        try:
                            pokemon_id = int(part.split(":")[1].strip())
                        except ValueError:
                            pass

            if pokemon_id is None:
                return

            pokemon = await db.get(Pokemon, pokemon_id)
            if not pokemon:
                return

            # Garante usuário no banco
            user = await db.get(User, user_id)
            if not user:
                guild  = self.bot.get_guild(payload.guild_id)
                member = guild.get_member(payload.user_id)
                if not member:
                    return
                user = User(
                    discord_id=user_id,
                    username=member.name,
                    avatar_url=str(member.display_avatar.url),
                )
                db.add(user)
                await db.flush()

            previous_owner_id = pokemon.assigned_to

            if previous_owner_id and previous_owner_id != user_id:
                # Override: notifica quem estava usando
                guild      = self.bot.get_guild(payload.guild_id)
                prev_member = guild.get_member(int(previous_owner_id))
                if prev_member:
                    try:
                        await prev_member.send(
                            f"⚠️ **{pokemon.name}** foi atribuído a <@{user_id}>. "
                            "Por favor, retire sua reação 🎯 da mensagem."
                        )
                    except discord.Forbidden:
                        pass

                db.add(History(
                    actor_id=user_id,
                    entity_type="pokemon",
                    entity_id=pokemon_id,
                    action="overridden",
                    detail=f'{{"from":"{previous_owner_id}","to":"{user_id}"}}',
                    happened_at=datetime.utcnow(),
                ))

            pokemon.assigned_to  = user_id
            pokemon.assigned_at  = datetime.utcnow()

            db.add(History(
                actor_id=user_id,
                entity_type="pokemon",
                entity_id=pokemon_id,
                action="assigned",
                detail=f'{{"pokemon":"{pokemon.name}"}}',
                happened_at=datetime.utcnow(),
            ))
            await db.commit()

        # Edita a mensagem para refletir o novo dono
        guild   = self.bot.get_guild(payload.guild_id)
        member  = guild.get_member(payload.user_id)
        display = member.display_name if member else user_id

        if message.embeds:
            embed = message.embeds[0]
            new_embed = embed.copy()
            new_embed.color = discord.Color.green()
            new_embed.description = (
                f"✅ **{pokemon.name}** está sendo usado por **{display}**.\n"
                "Retire a reação 🎯 para liberar."
            )
            await message.edit(embed=new_embed)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "🎯":
            return
        if payload.channel_id != DISCORD_POKEMON_CHANNEL_ID:
            return

        user_id = str(payload.user_id)

        async with AsyncSessionLocal() as db:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            pokemon_id = None
            if message.embeds:
                footer_text = message.embeds[0].footer.text or ""
                for part in footer_text.split("|"):
                    part = part.strip()
                    if part.startswith("ID:"):
                        try:
                            pokemon_id = int(part.split(":")[1].strip())
                        except ValueError:
                            pass

            if pokemon_id is None:
                return

            pokemon = await db.get(Pokemon, pokemon_id)
            if not pokemon or pokemon.assigned_to != user_id:
                return

            pokemon.assigned_to = None
            pokemon.assigned_at = None

            db.add(History(
                actor_id=user_id,
                entity_type="pokemon",
                entity_id=pokemon_id,
                action="unassigned",
                detail=f'{{"pokemon":"{pokemon.name}"}}',
                happened_at=datetime.utcnow(),
            ))
            await db.commit()

        # Edita a mensagem para livre
        if message.embeds:
            embed = message.embeds[0]
            new_embed = embed.copy()
            new_embed.color = discord.Color.yellow()
            new_embed.description = (
                f"**{pokemon.name}** está livre para uso.\n"
                "Reaja com 🎯 para marcar que vai usar."
            )
            await message.edit(embed=new_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionCog(bot))
