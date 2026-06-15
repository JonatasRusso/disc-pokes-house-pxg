# api/routes/ — Endpoints REST

Cada arquivo é um `APIRouter` registrado em `api/main.py`. Prefixo entre parênteses. Quase todas as rotas exigem login (cookie `session_token` via `get_current_user`); rotas admin usam `require_admin`.

> Ao criar/alterar uma rota ou helper, atualize este README.

## `auth.py` — `/auth`
- `GET /auth/login` — redireciona para o OAuth2 do Discord.
- `GET /auth/callback` — troca o code, cria/atualiza o `User`, seta cookie JWT, redireciona pro site.
- `POST /auth/logout` — apaga o cookie.
- `GET /auth/me` — dados do usuário logado (inclui `notify_lead_minutes`).
- `PATCH /auth/me` — atualiza configurações do usuário (hoje: `notify_lead_minutes`, 1–1440).
- `_user_dict(user)` — serializa o usuário.

## `characters.py` — `/characters`
- `GET ""` — lista personagens do usuário.
- `POST ""` — cria personagem (só nome).
- `PATCH /{char_id}` — renomeia (valida dono).
- `DELETE /{char_id}` — remove (valida dono).

## `schedules.py` — `/schedules` (núcleo das PTs)
> A **lógica de agendamento** vive em [`api/services/schedule_service.py`](../services/schedule_service.py) (camada de serviço testável, sem Repository): `next_occurrence(weekday, hour, minute, after)`, `_segments`/`_segments_overlap`/`_has_conflict(db, start, end, exclude, effective)` (conflito por sobreposição de intervalos — dia+minuto, duração variável, virada de meia-noite), `_eff_start`/`_eff_end`, `_validate_duration`, e as constantes de duração. As rotas importam de lá.

**Helpers (nas rotas):**
- `ROLE_CAPACITY` (de `api.enums`) — composição da PT: `{TANK:1, DPS:2, SUP:1}`.
- `_occupied_character_ids(db)` — personagens já em PT ativa (regra 1 PT por personagem).
- `_party_members_map(db, party_ids)` — membros por party (nick, role, character, is_coleader).
- `_my_membership(db, schedule, user_id)` / `_can_manage(db, schedule, user)` — permissão (líder/co-líder/admin).
- `_eff_start(s)` / `_eff_end(s)` — ocorrência **efetiva** (`override_start/end` se houver, senão o slot fixo).
- `_schedule_dict(s)` — serializa schedule. `start_time/end_time` = ocorrência efetiva; `weekday/hour/minute/duration_minutes` = slot fixo recorrente; `is_override`/`override_start` indicam remarcação só desta semana.

**Rotas:**
- `GET ""` (`list_schedules`) — PTs onde o usuário é membro **ou** organizador; inclui members (com `confirmed`), `is_member`, `is_leader`, `can_manage`.
- `GET /calendar` — todas as PTs ativas com membros (para o calendário).
- `GET /calendar` retorna `weekday/hour/minute/duration_minutes` por PT (para o picker e o calendário).
- `GET /free-slots` — grade por hora cheia (7 dias) com flag `free` por hora — **só para a visualização do calendário** (o input usa o `SlotPicker`, não a grade). Query `exclude={id}` ignora uma PT.
- `POST ""` (`create_schedule`) — cria PT recorrente; body tem `start_time` (dia+hora:minuto) e `duration_minutes` (padrão 180); `include_self=false` (admin) cria sem participar; enfileira convites na `outbox`.
- `PATCH /{id}/reschedule` — remarca (líder/co-líder/admin); reseta confirmações e avisa os demais (outbox `party_rescheduled`). Body: `scope` `"once"`/`"all"`, `duration_minutes` (opcional — mantém a atual se ausente), `force` (ignora conflito com OUTRA PT). Conflito por sobreposição de intervalos (`once` usa override efetivo; `all` usa o slot fixo); ambos ignoram a própria PT.
- `POST /{id}/add-member` — líder/co-líder/admin adiciona membro a uma PT incompleta; valida a composição (`ROLE_CAPACITY`). Membro da house (`discord_id`): cria `PartyMember` + confirmação pendente e convida no Discord (outbox `party_invite`). Externo de outro servidor (`external_name`): cria um `User` convidado (`is_external=true`, id `ext:<uuid>`) + `PartyMember.is_external=true`. O externo ocupa a vaga mas **não usa pokémon, não recebe ping e não confirma**. Membros são serializados com `is_external` (flag por participação `party_members.is_external`) e `is_guest` (convidado, `users.is_external`).
- `POST /{id}/set-external` — **qualquer membro da PT** (ou admin) marca/desmarca outro membro como externo nesta PT (`party_members.is_external`): usa pokémon próprio (de outro servidor de jogo), então **fica fora do lembrete de pokémon** — mas continua recebendo aviso de início e confirmando presença. Convidado (`is_guest`) é externo fixo. Log `member_external`.
- `POST /{id}/confirm` — membro confirma presença.
- `POST /{id}/leave` — membro sai; cancela a PT se esvaziar; avisa os demais (outbox).
- `PATCH /{id}/my-character` — membro define seu personagem na PT.
- `POST /{id}/promote` — líder define/remove co-líder.
- `POST /{id}/kick` — líder/co-líder remove um membro.
- `DELETE /{id}` (`cancel_schedule`) — cancela a PT (líder/co-líder/admin).
- `PATCH /{id}/admin` (`admin_edit_schedule`) — edição por admin (pouco usado pela UI).

## `pokemon.py` — `/pokemon`
- `GET ""` — lista todos; `GET /my` — os atribuídos ao usuário.
- `POST ""` / `PATCH /{id}` / `DELETE /{id}` — CRUD (admin). `_clean_image_url` valida a URL (http(s), ≤2048).
- `PATCH /{id}/assign` / `PATCH /{id}/unassign` — marcar/liberar uso (também acionado pelas reações 🎯 no bot).
- `_poke_dict(p)` — serializa.

## `members.py` — `/members`
- `GET ""` — todos os membros do servidor (tabela `users`, populada pelo bot) com seus **personagens livres** (não ocupados em PT ativa). Usado no seletor de membros ao agendar. **Exclui convidados externos** (`is_external`).
- `occupied_character_ids(db)` — personagens ocupados.

## `metrics.py` — `/metrics` (Prometheus)
- `GET /metrics` — métricas no formato Prometheus (sem auth): `discbot_db_up`, `discbot_db_query_latency_seconds`, `discbot_bot_up`, `discbot_bot_gateway_latency_ms`, `discbot_bot_guilds`, `discbot_schedules_active`, `discbot_pokemon_assigned/total`, `discbot_users_total`. Calculadas por scrape num `CollectorRegistry` próprio. Consumido pelo stack em `monitoring/` (Prometheus + Grafana + postgres_exporter).

## `history.py` — `/history` (admin)
- `GET ""` — logs com **resumo legível** (resolve discord_id→nick e pokémon_id→nome). Filtro por `entity_type`, paginação.
- `_summary(h, d, name, poke_name)` — monta a frase ("X concedeu admin para Y", "X marcou Charizard"...).
