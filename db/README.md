# db/ — Esquema de referência

## `schema.sql`
DDL de referência das tabelas (instalação "do zero" / documentação).

> ⚠️ Em runtime, o schema **real** é criado pelo SQLAlchemy: `api/database.py:init_db()` roda `Base.metadata.create_all` (a partir de `api/models.py`) + as migrações idempotentes de `_MIGRATIONS`. Portanto:
> - **Fonte de verdade do schema = `api/models.py`** (+ migrações em `api/database.py`).
> - Ao adicionar/alterar uma coluna ou tabela: altere `api/models.py`, adicione o `ALTER TABLE ... IF NOT EXISTS` em `_MIGRATIONS` (para bancos já existentes) e **atualize este `schema.sql`** para manter a referência coerente.

Tabelas: `users`, `characters`, `parties`, `party_members`, `schedules`, `schedule_confirmations`, `pokemon`, `history`, `outbox` (a `bot_heartbeat` é criada via `create_all`).
