# bot/ — Bot do Discord

Processo separado da API (`python -m bot.main`). Compartilha o banco com a API (importa `api.database`, `api.models`, `api.timeutil`).

> Ao criar/alterar comandos, listeners, jobs ou funções, atualize este README (e o de `commands/`/`events/`).

## Arquivos

### `main.py` — Entrypoint
- Cria o `bot` (discord.py) com intents (members, reactions, message_content). Lista de cogs em `COGS`.
- **`on_ready()`** — sincroniza slash commands na guild, roda `sync_roster()`, inicia o scheduler (`start_scheduler`) e grava o heartbeat inicial.
- **`on_app_command_completion(...)`** / **`on_raw_reaction_add(...)`** — chamam `mark_command()` (atualiza `last_command_at` do health) e delegam confirmações de PT (`handle_confirmation`).
- **`on_member_join(...)`** — adiciona o novo membro à tabela `users`.
- **`sync_roster()`** / `_upsert_member(db, member)` — sincronizam todos os membros da guild para `users` (nick = `display_name`).
- `main()` — `init_db()` + carrega cogs + `bot.start(token)`.

### `config.py` — Variáveis de ambiente
- Lê tokens/IDs do Discord (fail-fast se faltar). 
- **`POKEMON_CHANNELS`** — mapa categoria→canal (Tank/DPS/Sup) com fallback pro canal único `DISCORD_POKEMON_CHANNEL_ID`.
- **`POKEMON_CHANNEL_IDS`** — conjunto de canais válidos (guard das reações).

### `scheduler.py` — Jobs periódicos (APScheduler) e notificações
- **`start_scheduler(bot)`** — registra 3 jobs (cada 20s/20s/30s): `_check_schedules`, `_process_outbox`, `write_heartbeat`.
- **`_check_schedules(bot)`** — coração das notificações. Roda rollover, **filtra convidados de fora** (`User.is_external` — sem conta no Discord da house, não dá pra pingar; externos de jogo `PartyMember.is_external` recebem aviso e confirmam normalmente, ficando de fora só do lembrete de pokémon), depois para cada membro não confirmado decide o aviso: **1º aviso** (N min antes, configurável por usuário), **1 min**, **30s**, **atraso** (a cada 30s). "Avisar e deletar": apaga o aviso anterior e some ao confirmar. Estado em `_warn_state` (podado a cada tick). Dispara o lembrete de pokémon dentro da janela de 30 min.
- `_send_warning(...)` — monta/envia o embed do aviso (com reação ✅) e devolve a mensagem.
- `_delete_warn(channel, key)` — apaga a mensagem de aviso atual.
- **`handle_confirmation(bot, payload)`** — reação ✅ confirma presença e apaga o aviso.
- **`_process_outbox(bot)`** — envia itens da `outbox` (`_send_party_invite`, `_send_party_left`, `_send_party_rescheduled`); abandona itens com >15 min sem enviar (ex: bot sem permissão).
- **`_rollover_recurring()`** — avança PTs cuja ocorrência **efetiva** terminou +7 dias (recorrência) e reseta confirmações. Uma remarcação de 1 semana (`override_start/end`) é consumida aqui: limpa o override e pula o slot fixo desta semana, voltando ao normal na próxima.
- **`_eff_start(s)` / `_eff_end(s)`** — ocorrência efetiva (override de 1 semana, se houver). Usadas na janela de checagem, no rollover e na chave `iso` dos avisos.
- **`_pokemon_pt_reminder(...)`** — quando a PT entra na janela de 30 min, marca os membros no canal de cada função listando pokémons livres (1x por ocorrência).
- **Limpeza dos canais:** mensagens transitórias do bot se auto-apagam (`delete_after`) para não poluir — convites/saída/remarcação (`NOTICE_TTL_S`, 30 min) e lembrete de pokémon (`POKE_REMINDER_TTL_S`, 40 min). Avisos de PT já somem ao confirmar; o que sobra é apagado quando a ocorrência sai da janela (prune em `_check_schedules`). O **painel** de `/pokemon-painel` é permanente (não é apagado).
- Constantes: `ROLE_TO_CAT`, `CAT_LABEL`, `OUTBOX_GIVEUP`, `NOTICE_TTL_S`, `POKE_REMINDER_TTL_S`.

### `health.py` — Heartbeat do bot
- **`write_heartbeat(bot)`** — grava na tabela `bot_heartbeat` (is_ready, latência, guilds, memória, last_command_at) para o `/health` da API ler.
- **`mark_command()`** — atualiza `last_command_at` (chamado em comandos/reações).

### `__init__.py` — marcador de pacote (vazio).

## Subpastas
- `commands/` — slash commands. `events/` — listeners. (READMEs próprios.)
