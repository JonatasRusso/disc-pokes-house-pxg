from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, require_admin
from api.database import get_db
from api.models import History, User

router = APIRouter(prefix="/history", tags=["history"])


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

    result = await db.execute(query)
    rows   = result.scalars().all()
    return [
        {
            "id":          h.id,
            "actor_id":    h.actor_id,
            "entity_type": h.entity_type,
            "entity_id":   h.entity_id,
            "action":      h.action,
            "detail":      h.detail,
            "happened_at": h.happened_at.isoformat(),
        }
        for h in rows
    ]
