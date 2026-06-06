import discord
from discord.ext import commands
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import Pokemon, History, User
from api.timeutil import now_local
from bot.config import POKEMON_CHANNEL_IDS
from bot.commands.pokemon import build_pokemon_embed


class ReactionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "🎯":
            return
        if payload.channel_id not in POKEMON_CHANNEL_IDS:
            return

        user_id = str(payload.user_id)

        async with AsyncSessionLocal() as db:
            # Encontra o pokémon pela mensagem do painel
            pokemon = (await db.execute(
                select(Pokemon).where(Pokemon.panel_message_id == str(payload.message_id))
            )).scalar_one_or_none()
            if not pokemon:
                return
            pokemon_id = pokemon.id

            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

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
                    happened_at=now_local(),
                ))

            pokemon.assigned_to  = user_id
            pokemon.assigned_at  = now_local()

            db.add(History(
                actor_id=user_id,
                entity_type="pokemon",
                entity_id=pokemon_id,
                action="assigned",
                detail=f'{{"pokemon":"{pokemon.name}"}}',
                happened_at=now_local(),
            ))
            await db.commit()

        # Re-renderiza a mensagem com o status atualizado
        guild = self.bot.get_guild(payload.guild_id)
        if message.embeds:
            await message.edit(embed=build_pokemon_embed(pokemon, guild))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "🎯":
            return
        if payload.channel_id not in POKEMON_CHANNEL_IDS:
            return

        user_id = str(payload.user_id)

        async with AsyncSessionLocal() as db:
            pokemon = (await db.execute(
                select(Pokemon).where(Pokemon.panel_message_id == str(payload.message_id))
            )).scalar_one_or_none()
            if not pokemon or pokemon.assigned_to != user_id:
                return
            pokemon_id = pokemon.id

            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            pokemon.assigned_to = None
            pokemon.assigned_at = None

            db.add(History(
                actor_id=user_id,
                entity_type="pokemon",
                entity_id=pokemon_id,
                action="unassigned",
                detail=f'{{"pokemon":"{pokemon.name}"}}',
                happened_at=now_local(),
            ))
            await db.commit()

        # Re-renderiza a mensagem como livre
        guild = self.bot.get_guild(payload.guild_id)
        if message.embeds:
            await message.edit(embed=build_pokemon_embed(pokemon, guild))


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionCog(bot))
