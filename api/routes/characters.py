from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Character, User

router = APIRouter(prefix="/characters", tags=["characters"])


class CharacterIn(BaseModel):
    name: str


@router.get("")
async def list_characters(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.user_id == user.discord_id))
    chars = result.scalars().all()
    return [{"id": c.id, "name": c.name} for c in chars]


@router.post("")
async def create_character(body: CharacterIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    char = Character(user_id=user.discord_id, name=body.name)
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return {"id": char.id, "name": char.name}


@router.patch("/{char_id}")
async def update_character(char_id: int, body: CharacterIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, char_id)
    if not char or char.user_id != user.discord_id:
        raise HTTPException(404, "Personagem não encontrado")
    if body.name:
        char.name = body.name
    await db.commit()
    return {"id": char.id, "name": char.name}


@router.delete("/{char_id}")
async def delete_character(char_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, char_id)
    if not char or char.user_id != user.discord_id:
        raise HTTPException(404, "Personagem não encontrado")
    await db.delete(char)
    await db.commit()
    return {"ok": True}
