# api/ — Backend FastAPI + camada compartilhada

Camada de dados/HTTP usada pela **API** e importada também pelo **bot** (models, database, timeutil são compartilhados entre os dois processos).

> Ao alterar/criar funções aqui, atualize este README.

## Arquivos

### `main.py` — App FastAPI
- Cria o `app`, configura **CORS** (`allow_origins=[SITE_URL]`), registra os routers de `api/routes/`.
- `lifespan(app)` — roda `init_db()` no startup.
- **`health()`** → `GET /health`: health check rico. Checa banco (`SELECT 1` + latência), lê o **heartbeat do bot** da tabela `bot_heartbeat`, reporta uptime/memória da API, **recursos do container** (CPU/disco) e `env_ok`. Retorna `status: ok|degraded` (degraded se banco caiu, bot sem heartbeat >90s, ou env crítica faltando). Latência/CPU/disco não afetam o `status` — são métricas para alerta externo.
- `_api_memory_mb()` — memória do processo da API.
- `_resources()` — CPU (`cpu_percent`, amostrado em thread p/ não bloquear o loop) e disco (`disk_used_gb`/`disk_total_gb`/`disk_percent`) via `psutil`.
- Constantes: `START_TIME`, `REQUIRED_ENVS`, `HEARTBEAT_STALE_S`.

### `database.py` — Conexão e migrações
- `engine` (async), `AsyncSessionLocal` (sessionmaker), `DATABASE_URL` (env, default SQLite).
- **`init_db()`** — `create_all` (cria tabelas novas) + roda `_MIGRATIONS` (lista de `ALTER TABLE ... IF NOT EXISTS` idempotentes, pois `create_all` não altera tabelas existentes). **Adicionar colunas novas aqui.**
- **`get_db()`** — dependência FastAPI que injeta uma sessão.

### `models.py` — Modelos SQLAlchemy (tabelas)
- `User` (discord_id PK, is_admin, **notify_lead_minutes**, nick), `Character`, `Party`, `PartyMember` (role, character_id, **is_coleader**), `Schedule` (start/end_time, status, organizer_id, character_id), `ScheduleConfirmation` (confirmed, last_ping), `Pokemon` (category A/B/C, assigned_to, **panel_message_id**), `History` (log de ações), `Outbox` (fila API→bot), **`BotHeartbeat`** (estado do bot p/ `/health`).
- Defaults de timestamp usam `now_local` (fuso da comunidade).

### `auth.py` — Autenticação (JWT + Discord OAuth)
- `create_token(discord_id)`, `decode_token(token)` — JWT em cookie `session_token`.
- **`get_current_user(...)`** — dependência: valida o cookie e retorna o `User` (401 se inválido).
- **`require_admin(...)`** — dependência: exige `user.is_admin` (403 caso contrário).
- `exchange_code(code)` — troca o code do OAuth2 por access_token; `get_discord_user(token)` — busca o perfil no Discord.

### `timeutil.py` — Fuso horário
- **`now_local()`** — hora local (naive) da comunidade. **Usar sempre isto** em vez de `datetime.utcnow()` para horários de PT.
- `LOCAL_TZ`, offset via `APP_UTC_OFFSET` (default -3 / Brasília, sem horário de verão).

### `__init__.py` — marcador de pacote (vazio).

## Subpasta
- `routes/` — endpoints REST (ver README próprio).
