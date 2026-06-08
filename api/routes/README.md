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
**Helpers:**
- `next_occurrence(weekday, hour, after)` — próxima data futura com aquele dia-da-semana/hora (recorrência semanal).
- `_busy_weekday_hours(db)` / `_conflicts(weekday, hour, busy)` — conflito de horário: marcar trava o horário **+ as 2 horas posteriores**.
- `_occupied_character_ids(db)` — personagens já em PT ativa (regra 1 PT por personagem).
- `_party_members_map(db, party_ids)` — membros por party (nick, role, character, is_coleader).
- `_my_membership(db, schedule, user_id)` / `_can_manage(db, schedule, user)` — permissão (líder/co-líder/admin).
- `_schedule_dict(s)` — serializa schedule (inclui weekday/hour/organizer_id).

**Rotas:**
- `GET ""` (`list_schedules`) — PTs onde o usuário é membro **ou** organizador; inclui members (com `confirmed`), `is_member`, `is_leader`, `can_manage`.
- `GET /calendar` — todas as PTs ativas com membros (para o calendário).
- `GET /free-slots` — grade semanal: cada hora (00:00–23:00) dos próximos 7 dias com flag `free` (sem trava de horário passado; recorrente).
- `POST ""` (`create_schedule`) — cria PT recorrente; `include_self=false` (admin) cria sem participar; enfileira convites na `outbox`.
- `PATCH /{id}/reschedule` — remarca (líder/co-líder/admin); reseta confirmações.
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
- `GET ""` — todos os membros do servidor (tabela `users`, populada pelo bot) com seus **personagens livres** (não ocupados em PT ativa). Usado no seletor de membros ao agendar.
- `occupied_character_ids(db)` — personagens ocupados.

## `history.py` — `/history` (admin)
- `GET ""` — logs com **resumo legível** (resolve discord_id→nick e pokémon_id→nome). Filtro por `entity_type`, paginação.
- `_summary(h, d, name, poke_name)` — monta a frase ("X concedeu admin para Y", "X marcou Charizard"...).
