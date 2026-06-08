# bot/events/ — Listeners de eventos

Cogs com listeners do discord.py. Carregados em `bot/main.py`.

> Ao adicionar/alterar um listener, atualize este README.

## `reactions.py` — `ReactionCog`
Gerencia o marcar/desmarcar de pokémons no painel via reação 🎯.

- **`on_raw_reaction_add(payload)`** — ao reagir 🎯 num canal de pokémon (`POKEMON_CHANNEL_IDS`): encontra o pokémon pela mensagem (`Pokemon.panel_message_id`), atribui ao usuário (cria o `User` se não existir), trata **override** (se já era de outro, avisa o anterior por DM), registra no `History` e re-renderiza o card com `build_pokemon_embed`.
- **`on_raw_reaction_remove(payload)`** — ao remover a reação 🎯, libera o pokémon (se for o dono) e re-renderiza o card.

> Confirmação de PT (reação ✅ no canal de avisos) **não** fica aqui — é tratada em `bot/scheduler.py:handle_confirmation`, chamada por `on_raw_reaction_add` em `bot/main.py`.
