import discord
from discord import app_commands
from discord.ext import commands
from api.database import AsyncSessionLocal
from api.models import User, History
from api.timeutil import now_local


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="(Owner) Conceder ou revogar permissão de admin a um usuário")
    @app_commands.describe(usuario="Usuário do Discord", acao="grant para conceder, revoke para revogar")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Conceder", value="grant"),
        app_commands.Choice(name="Revogar", value="revoke"),
    ])
    async def admin(self, interaction: discord.Interaction, usuario: discord.Member, acao: str):
        # Apenas o dono do servidor pode usar este comando
        if interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message("Apenas o dono do servidor pode usar este comando.", ephemeral=True)
            return

        target_id = str(usuario.id)
        actor_id  = str(interaction.user.id)

        async with AsyncSessionLocal() as db:
            # Garante que o usuário alvo existe no banco
            target = await db.get(User, target_id)
            if not target:
                target = User(discord_id=target_id, username=usuario.name, avatar_url=str(usuario.display_avatar.url))
                db.add(target)

            target.is_admin = (acao == "grant")

            log = History(
                actor_id=actor_id,
                entity_type="admin",
                entity_id=None,
                action="admin_granted" if acao == "grant" else "admin_revoked",
                detail=f'{{"target":"{target_id}","username":"{usuario.name}"}}',
                happened_at=now_local(),
            )
            db.add(log)
            await db.commit()

        action_label = "agora é admin ✅" if acao == "grant" else "não é mais admin ❌"
        await interaction.response.send_message(
            f"{usuario.mention} {action_label}.", ephemeral=False
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
