# monitoring/ — Prometheus + Grafana (status do banco)

Stack de observabilidade para acompanhar o **status do Postgres** (e do bot/PTs). Roda
separado da aplicação, com Docker Compose. Não é necessário em produção — suba localmente
ou num host de monitoramento.

## O que sobe
- **Prometheus** (`:9090`) — coleta as métricas.
- **postgres_exporter** (`:9187`) — métricas profundas do Postgres (conexões, transações, locks, tamanho).
- **Grafana** (`:3000`) — dashboards. Já vem com datasource + dashboard **"DiscBot — Status do Banco & Bot"** provisionados.

De onde vêm as métricas:
- **Postgres** → `postgres_exporter` (precisa do DSN do banco).
- **App** (`db up`, latência do `SELECT 1`, heartbeat do bot, contadores de PT/pokémon) → endpoint **`/metrics`** da API (FastAPI, via `prometheus-client`).

## Como rodar
1. `cp .env.example .env` e preencha:
   - `PG_DSN` — DSN do Postgres (Railway: `DATABASE_URL` com prefixo `postgresql://` e `?sslmode=require`).
   - `GF_ADMIN_PASSWORD` — senha do admin do Grafana.
2. Edite `prometheus/prometheus.yml` → no job `discbot-api`, troque `REPLACE_WITH_YOUR_API_HOST` pelo host da sua API (ex.: `discbot-api-production.up.railway.app`). Para API local: `scheme: http` e target `host.docker.internal:8000`.
3. `docker compose up -d`
4. Abra `http://localhost:3000` (admin / `GF_ADMIN_PASSWORD`) → dashboard já carregado.

## Métricas expostas pela API (`/metrics`)
`discbot_db_up`, `discbot_db_query_latency_seconds`, `discbot_bot_up`,
`discbot_bot_gateway_latency_ms`, `discbot_bot_guilds`, `discbot_bot_heartbeat_age_seconds`,
`discbot_schedules_active`, `discbot_pokemon_assigned`, `discbot_pokemon_total`, `discbot_users_total`.

> O `/metrics` é público (só contadores agregados, nada sensível). Se quiser proteger,
> coloque atrás de um proxy/allowlist ou adicione um token.
