import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_admin
from api.database import get_db
from api.models import History, Pokemon, User

router = APIRouter(prefix="/history", tags=["history"])


def _summary(h: History, d: dict, name, poke_name) -> str:
    """Texto legível: quem fez o quê para quem."""
    a = name(h.actor_id)
    if h.entity_type == "admin":
        t = name(d.get("target"))
        if h.action == "admin_granted":
            return f"{a} concedeu admin para {t}"
        if h.action == "admin_revoked":
            return f"{a} removeu admin de {t}"
    if h.entity_type == "pokemon":
        pname = poke_name(h.entity_id) or d.get("pokemon") or f"#{h.entity_id}"
        if h.action == "assigned":
            return f"{a} marcou que vai usar {pname}"
        if h.action == "unassigned":
            return f"{a} liberou {pname}"
        if h.action == "overridden":
            return f"{a} assumiu {pname} (antes com {name(d.get('from'))})"
    if h.entity_type == "schedule":
        if h.action == "created":
            return f"{a} criou uma PT ({d.get('difficulty', '')})"
        if h.action == "rescheduled":
            return f"{a} remarcou a PT #{h.entity_id}"
        if h.action == "cancelled":
            return f"{a} cancelou a PT #{h.entity_id}"
        if h.action == "admin_edited":
            return f"{a} editou a PT #{h.entity_id}"
        if h.action == "member_added":
            return f"{a} adicionou {name(d.get('member'))} ({d.get('role', '')}) na PT #{h.entity_id}"
    return f"{a} — {h.action}"


@router.get("")
async def get_history(
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(History).order_by(History.happened_at.desc()).limit(limit).offset(offset)
    if entity_type:
        query = query.where(History.entity_type == entity_type)

    rows = (await db.execute(query)).scalars().all()

    # Coleta IDs de usuários e pokémons referenciados para resolver nomes
    user_ids: set[str] = set()
    poke_ids: set[int] = set()
    parsed: list[dict] = []
    for h in rows:
        try:
            d = json.loads(h.detail) if h.detail else {}
        except (ValueError, TypeError):
            d = {}
        parsed.append(d)
        if h.actor_id:
            user_ids.add(h.actor_id)
        for k in ("target", "from", "to", "member"):
            if d.get(k):
                user_ids.add(d[k])
        if h.entity_type == "pokemon" and h.entity_id:
            poke_ids.add(h.entity_id)

    users = {}
    if user_ids:
        res = await db.execute(select(User).where(User.discord_id.in_(user_ids)))
        users = {u.discord_id: (u.nick or u.username) for u in res.scalars().all()}
    pokes = {}
    if poke_ids:
        res = await db.execute(select(Pokemon).where(Pokemon.id.in_(poke_ids)))
        pokes = {p.id: p.name for p in res.scalars().all()}

    def name(uid):
        if not uid:
            return "—"
        return users.get(uid, uid)

    def poke_name(pid):
        return pokes.get(pid)

    return [
        {
            "id":          h.id,
            "actor_id":    h.actor_id,
            "actor_name":  name(h.actor_id),
            "entity_type": h.entity_type,
            "entity_id":   h.entity_id,
            "action":      h.action,
            "detail":      h.detail,
            "summary":     _summary(h, d, name, poke_name),
            "happened_at": h.happened_at.isoformat(),
        }
        for h, d in zip(rows, parsed)
    ]
