import os
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from api.models import Base

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./discbot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# LEGADO (congelado): migrações idempotentes manuais. A evolução de schema agora é via
# **Alembic** (`alembic/`, rodado no start — ver start.sh/railway.toml). Esta lista fica
# como rede de segurança para bancos de dev antigos; NÃO adicione novas entradas aqui —
# crie uma migração: `alembic revision --autogenerate -m "..."`.
_MIGRATIONS = [
    "ALTER TABLE party_members ADD COLUMN IF NOT EXISTS character_id INTEGER",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS nick TEXT",
    "ALTER TABLE schedules ALTER COLUMN character_id DROP NOT NULL",  # admin pode criar PT sem se incluir
    "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS organizer_id TEXT",
    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS panel_message_id TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_lead_minutes INTEGER DEFAULT 30",
    "ALTER TABLE party_members ADD COLUMN IF NOT EXISTS is_coleader BOOLEAN DEFAULT FALSE",
    "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS override_start TIMESTAMP",  # remarcação só desta semana
    "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS override_end TIMESTAMP",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE",  # convidado de outro servidor
    "ALTER TABLE party_members ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE",  # membro externo nesta PT (sem pokémon)
]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as e:  # SQLite antigo não suporta IF NOT EXISTS; ignora se já existe
                log.info(f"Migração ignorada ({stmt}): {e}")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
