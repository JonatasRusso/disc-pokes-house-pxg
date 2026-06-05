import os
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Character, PartyMember, Schedule, User

router = APIRouter(prefix="/members", tags=["members"])

BOT_ID = os.getenv("DISCORD_CLIENT_ID")

ACTIVE_STATUSES = ["pending", "confirmed"]


async def occupied_character_ids(db: AsyncSession) -> set[int]:
    """IDs de personagens já em uma PT ativa (pending/confirmed)."""
    result = await db.execute(
        select(PartyMember.character_id)
        .join(Schedule, Schedule.party_id == PartyMember.party_id)
        .where(
            Schedule.status.in_(ACTIVE_STATUSES),
            PartyMember.character_id.isnot(None),
        )
    )
    return {row[0] for row in result.all() if row[0] is not None}


@router.get("")
async def list_members(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Lista todos os membros do servidor com seus personagens livres."""
    users_result = await db.execute(select(User).order_by(User.username))
    users = users_result.scalars().all()

    chars_result = await db.execute(select(Character))
    all_chars = chars_result.scalars().all()

    occupied = await occupied_character_ids(db)

    by_user: dict[str, list] = {}
    for c in all_chars:
        if c.id in occupied:
            continue  # personagem já em PT ativa
        by_user.setdefault(c.user_id, []).append({"id": c.id, "name": c.name})

    members = []
    for u in users:
        if BOT_ID and u.discord_id == BOT_ID:
            continue
        members.append({
            "discord_id": u.discord_id,
            "username":   u.username,
            "avatar_url": u.avatar_url,
            "characters": by_user.get(u.discord_id, []),
        })
    return members
