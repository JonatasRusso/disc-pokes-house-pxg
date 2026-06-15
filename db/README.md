# db/ — Esquema e migrações

## Migrações: Alembic (`alembic/`)
A evolução de schema é via **Alembic**. Roda no start (`start.sh` / `railway.toml`: `alembic upgrade head`) antes de subir API+bot, então o deploy aplica as migrações sozinho.
- **Fonte de verdade do schema = `api/models.py`** (`Base.metadata`), usado pelo autogenerate.
- **Criar migração** após mudar os modelos: `alembic revision --autogenerate -m "descrição"` → revisa o arquivo gerado em `alembic/versions/` → commita. (SQLite usa batch mode automaticamente.)
- A revisão inicial `0001_baseline` cria tudo via `create_all` (idempotente): em banco já existente é no-op + registra a versão; em banco novo cria o schema.
- Config: `alembic.ini` + `alembic/env.py` (async, lê `DATABASE_URL`).
- Comandos úteis (local): `alembic upgrade head`, `alembic downgrade -1`, `alembic history`, `alembic current`.

> ⚠️ Adotar em um banco que **já existe** sem passar pela baseline: `alembic stamp 0001_baseline` uma vez (marca como aplicado). Como a baseline é `create_all` idempotente, `alembic upgrade head` direto também é seguro.

## `schema.sql`
DDL de referência (documentação / leitura). Mantenha coerente com `api/models.py` ao mudar o schema.

## Legado
`api/database.py:_MIGRATIONS` (ALTER ... IF NOT EXISTS) está **congelado** — rede de segurança p/ bancos de dev antigos. Não adicione novas entradas; use Alembic.

Tabelas: `users`, `characters`, `parties`, `party_members`, `schedules`, `schedule_confirmations`, `pokemon`, `history`, `outbox`, `bot_heartbeat`.
