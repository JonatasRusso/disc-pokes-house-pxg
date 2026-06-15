# bot/commands/ — Slash commands

Cada arquivo é um Cog carregado em `bot/main.py` (`COGS`). Cada um expõe `setup(bot)`.

> Ao adicionar/alterar um comando, atualize este README.

## `schedule.py` — `ScheduleCog`
Comandos enxutos que apontam para o site (a gestão real é no front — sem queries no bot):
- **`/site`** — link pro painel do site (`/dashboard`): PTs, agenda, remarcação, pokémons.
- **`/agendar`** — manda link do formulário de agendamento.
- **`/remarcar [id]`** — mostra 2 botões de link para remarcar no site: **📅 Só esta semana** (`?scope=once`) e **🔁 Todas as semanas** (`?scope=all`).
- **`/resumo`** (admin) — posta na hora o resumo das PTs da semana (mesmo conteúdo do post automático de segunda).

## `pokemon.py` — `PokemonCog`
**Helpers:**
- `valid_image_url(url)` — aceita só http(s) ≤2048 chars.
- `_status(pokemon, guild)` — retorna texto/cor do status (🟢 em uso por X / ⚪ livre).
- **`build_pokemon_embed(pokemon, guild)`** — embed do card (nome + miniatura + status). **Reusado pelo `events/reactions.py`** ao re-renderizar.

**Comandos:** (consulta de pokémon migrou pro site — `/dashboard`)
- **`/pokemon-painel`** (admin) — posta o painel no canal de cada função (`POKEMON_CHANNELS`): purga o painel antigo do bot, posta um card por pokémon com reação 🎯 e grava `pokemon.panel_message_id` (liga reação→pokémon). Checa permissões e responde erros claros.

## `admin.py` — `AdminCog`
- **`/admin @usuario [grant/revoke]`** (somente dono do servidor) — concede/revoga `is_admin`; registra no `History`.
