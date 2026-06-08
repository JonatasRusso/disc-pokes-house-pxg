# bot/commands/ — Slash commands

Cada arquivo é um Cog carregado em `bot/main.py` (`COGS`). Cada um expõe `setup(bot)`.

> Ao adicionar/alterar um comando, atualize este README.

## `schedule.py` — `ScheduleCog`
Comandos que apontam para o site (a gestão real é no front):
- **`/agendar`** — manda link do formulário de agendamento.
- **`/meus-horarios`** — lista as próximas PTs do usuário (consulta o banco).
- **`/nao-posso [id]`** — manda link para remarcar a PT no site.

## `pokemon.py` — `PokemonCog`
**Helpers:**
- `valid_image_url(url)` — aceita só http(s) ≤2048 chars.
- `_status(pokemon, guild)` — retorna texto/cor do status (🟢 em uso por X / ⚪ livre).
- **`build_pokemon_embed(pokemon, guild)`** — embed do card (nome + miniatura + status). **Reusado pelo `events/reactions.py`** ao re-renderizar.

**Comandos:**
- **`/meus-pokemon`** — pokémons atribuídos ao usuário.
- **`/pokemon-status`** — grid de uso de todos.
- **`/pokemon-painel`** (admin) — posta o painel no canal de cada função (`POKEMON_CHANNELS`): purga o painel antigo do bot, posta um card por pokémon com reação 🎯 e grava `pokemon.panel_message_id` (liga reação→pokémon). Checa permissões e responde erros claros.

## `admin.py` — `AdminCog`
- **`/admin @usuario [grant/revoke]`** (somente dono do servidor) — concede/revoga `is_admin`; registra no `History`.
