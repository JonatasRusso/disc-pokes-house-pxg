import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routes import auth, characters, schedules, pokemon, history, members

SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="DiscBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[SITE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(schedules.router)
app.include_router(pokemon.router)
app.include_router(history.router)
app.include_router(members.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
