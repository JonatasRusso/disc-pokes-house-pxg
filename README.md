# VKG House — Bot Discord + Site de Gestão de PTs e Pokémons 💀

App para uma comunidade pequena gerenciar **PTs (parties) fixas** de um jogo: agendamento recorrente semanal, confirmação de presença, notificações no Discord e controle de quais pokémons cada pessoa usa.

> ⚠️ **REGRA OBRIGATÓRIA PARA IA E DEVS:** sempre que **alterar uma função, criar uma nova, mudar uma rota/endpoint, modelo de banco ou comando do bot**, **atualize o README da pasta correspondente** (e este, se mudar arquitetura). Os READMEs por pasta são a fonte de verdade para entender o código rapidamente — mantê-los desatualizados quebra esse contrato.

---

## Arquitetura

```
Discord  ←→  Railway (2 processos no mesmo container)  ←→  Vercel (frontend)
                ├─ Bot  (python -m bot.main)
                └─ API  (uvicorn api.main:app)
                        └─ PostgreSQL (Railway)
```

- **Bot** e **API** são **processos separados** que compartilham **apenas o banco**. A API não acessa o objeto `bot` diretamente — a comunicação entre eles é feita pelo banco:
  - API → Bot: tabela **`outbox`** (convites/avisos que o bot envia no Discord).
  - Bot → API: tabela **`bot_heartbeat`** (estado do bot lido pelo `/health`).
- **Frontend** (Vercel) consome a API via rewrite `/api/* → Railway` (`frontend/vercel.json`), então o browser vê tudo como same-origin.

## Stack
- **Bot:** Python, discord.py, APScheduler
- **API:** FastAPI, SQLAlchemy (async), Discord OAuth2 + JWT
- **Banco:** SQLite (dev) / PostgreSQL (prod). Migrações leves idempotentes em `api/database.py`.
- **Frontend:** React + TypeScript + Vite + Tailwind + React Query

## Mapa de pastas (cada uma tem seu README)
| Pasta | Conteúdo |
|---|---|
| `api/` | API FastAPI + camada compartilhada (models, db, auth, timeutil) |
| `api/routes/` | Endpoints REST (auth, schedules, pokemon, characters, members, history) |
| `bot/` | Bot Discord (entrypoint, scheduler, health, config) |
| `bot/commands/` | Slash commands |
| `bot/events/` | Listeners de eventos (reações) |
| `db/` | `schema.sql` de referência |
| `monitoring/` | Stack Prometheus + Grafana + postgres_exporter (status do banco) |
| `frontend/` | App React (Vite) |
| `frontend/src/` | Código-fonte do front |
| `frontend/src/pages/` | Páginas/rotas |
| `frontend/src/components/` | Componentes reutilizáveis |
| `frontend/src/lib/` | Cliente da API e hooks |

## Como rodar / deploy
- Rodar local e deploy: ver **`COMO_RODAR.md`**.
- Variáveis de ambiente: ver **`.env.example`**.
- Fluxo Git: trabalhar em `develop` → PR → `main` (merge dispara deploy no Railway e Vercel).
- Versão visível no rodapé do site vem de `frontend/package.json` (`__APP_VERSION__`).

## Conceitos-chave
- **PT recorrente:** uma PT é fixa e **repete toda semana**. O `start_time` guarda a próxima ocorrência; o bot avança +7 dias quando ela termina (`_rollover_recurring`).
- **Fuso horário:** horários são interpretados no fuso da comunidade via `api/timeutil.now_local()` (offset `APP_UTC_OFFSET`, padrão -3). **Nunca usar `datetime.utcnow()`** para comparar horários de PT.
- **Papéis:** organizador (líder) → pode promover co-líderes; líder/co-líder/admin gerenciam a PT.
- **Pokémon categorias:** `A`=Tank, `B`=DPS, `C`=Sup (armazenadas como A/B/C, exibidas como Tank/DPS/Sup).
- **Auto-marcação:** no início do horário da PT, o bot marca automaticamente os pokémons livres da função de cada membro (rodízio), re-renderiza o painel e avisa — a pessoa não precisa reagir 🎯. Externos usam pokémon próprio.
- **Observabilidade:** API expõe `/metrics` (Prometheus); stack de Grafana/Prometheus em `monitoring/`.
