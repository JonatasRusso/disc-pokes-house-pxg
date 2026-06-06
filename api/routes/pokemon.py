from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, require_admin
from api.database import get_db
from api.models import History, Pokemon, User

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


class PokemonIn(BaseModel):
    name: str
    image_url: str | None = None
    category: str


class PokemonUpdate(BaseModel):
    name: str | None = None
    image_url: str | None = None
    category: str | None = None


@router.get("")
async def list_pokemon(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pokemon).order_by(Pokemon.category, Pokemon.name))
    pokemons = result.scalars().all()
    return [_poke_dict(p) for p in pokemons]


@router.get("/my")
async def my_pokemon(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pokemon).where(Pokemon.assigned_to == user.discord_id))
    return [_poke_dict(p) for p in result.scalars().all()]


def _clean_image_url(url: str | None) -> str | None:
    """Aceita apenas URL http(s) válida e dentro do limite do Discord (2048)."""
    if not url:
        return None
    url = url.strip()
    if url.startswith(("http://", "https://")) and len(url) <= 2048 and " " not in url:
        return url
    return None


@router.post("")
async def create_pokemon(body: PokemonIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if body.category not in ("A", "B", "C"):
        raise HTTPException(400, "Categoria inválida. Use A, B ou C.")
    p = Pokemon(name=body.name.strip(), image_url=_clean_image_url(body.image_url), category=body.category)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _poke_dict(p)


@router.patch("/{pokemon_id}")
async def update_pokemon(pokemon_id: int, body: PokemonUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Pokemon, pokemon_id)
    if not p:
        raise HTTPException(404, "Pokémon não encontrado")
    if body.name is not None:
        p.name = body.name.strip()
    if body.category is not None:
        if body.category not in ("A", "B", "C"):
            raise HTTPException(400, "Categoria inválida. Use A, B ou C.")
        p.category = body.category
    if body.image_url is not None:
        p.image_url = _clean_image_url(body.image_url)
    await db.commit()
    await db.refresh(p)
    return _poke_dict(p)


@router.delete("/{pokemon_id}")
async def delete_pokemon(pokemon_id: int, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Pokemon, pokemon_id)
    if not p:
        raise HTTPException(404, "Pokémon não encontrado")
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.patch("/{pokemon_id}/assign")
async def assign_pokemon(pokemon_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p = await db.get(Pokemon, pokemon_id)
    if not p:
        raise HTTPException(404, "Pokémon não encontrado")

    previous = p.assigned_to
    p.assigned_to  = user.discord_id
    p.assigned_at  = datetime.utcnow()

    action = "overridden" if previous and previous != user.discord_id else "assigned"
    db.add(History(
        actor_id=user.discord_id,
        entity_type="pokemon",
        entity_id=pokemon_id,
        action=action,
        detail=f'{{"from":"{previous}","to":"{user.discord_id}"}}',
    ))
    await db.commit()
    return _poke_dict(p)


@router.patch("/{pokemon_id}/unassign")
async def unassign_pokemon(pokemon_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p = await db.get(Pokemon, pokemon_id)
    if not p:
        raise HTTPException(404, "Pokémon não encontrado")
    if p.assigned_to != user.discord_id and not user.is_admin:
        raise HTTPException(403, "Você não está usando este pokémon")

    p.assigned_to = None
    p.assigned_at = None
    db.add(History(actor_id=user.discord_id, entity_type="pokemon", entity_id=pokemon_id, action="unassigned"))
    await db.commit()
    return _poke_dict(p)


def _poke_dict(p: Pokemon) -> dict:
    return {
        "id":          p.id,
        "name":        p.name,
        "image_url":   p.image_url,
        "category":    p.category,
        "assigned_to": p.assigned_to,
        "assigned_at": p.assigned_at.isoformat() if p.assigned_at else None,
    }
