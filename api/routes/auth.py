import os
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_token, exchange_code, get_current_user, get_discord_user
from api.database import get_db
from api.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
API_URL           = os.getenv("API_URL", "http://localhost:8000")
SITE_URL          = os.getenv("SITE_URL", "http://localhost:5173")


@router.get("/login")
async def login():
    """Redireciona para o OAuth2 do Discord."""
    params = (
        f"client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={API_URL}/auth/callback"
        "&response_type=code"
        "&scope=identify"
    )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"https://discord.com/api/oauth2/authorize?{params}")


@router.get("/callback")
async def callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    token_data   = await exchange_code(code)
    discord_user = await get_discord_user(token_data["access_token"])

    discord_id = discord_user["id"]
    username   = discord_user["username"]
    avatar     = discord_user.get("avatar")
    avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png" if avatar else None

    user = await db.get(User, discord_id)
    if not user:
        user = User(discord_id=discord_id, username=username, avatar_url=avatar_url)
        db.add(user)
    else:
        user.username   = username
        user.avatar_url = avatar_url
    await db.commit()

    jwt_token = create_token(discord_id)
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse(url=f"{SITE_URL}/dashboard")
    resp.set_cookie("session_token", jwt_token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return resp


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session_token")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "discord_id": user.discord_id,
        "username":   user.username,
        "avatar_url": user.avatar_url,
        "is_admin":   user.is_admin,
    }
