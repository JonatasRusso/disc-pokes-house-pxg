# frontend/src/pages/ — Páginas (uma por rota)

Mapeadas em `src/App.tsx`. Dados via React Query (`src/lib/api.ts`).

> Ao adicionar/alterar uma página ou suas ações, atualize este README.

## Públicas / usuário
- **`Login.tsx`** (`/`) — botão "Entrar com Discord" (`/api/auth/login`). Redireciona logados ao dashboard.
- **`Dashboard.tsx`** (`/dashboard`) — resumo enxuto: próximas PTs (link p/ gerenciar) + pokémons em uso. Sem gestão pesada.
- **`MinhasPTs.tsx`** (`/minhas-pts`) — **gestão das PTs**. Componente `PTCard`: status por membro (✅/⏳, personagem), e ações conforme papel:
  - Próprias: definir personagem, **confirmar presença**, **sair da PT**.
  - Líder/co-líder: **remarcar**, **cancelar PT**, **promover co-líder** (`+co/−co`), **remover** membro.
- **`Calendario.tsx`** (`/calendario`) — `WeeklySlots` só-leitura com todas as PTs (`getCalendar`).
- **`Agendar.tsx`** (`/agendar`) — cria PT: personagem, função, dificuldade, horário (`WeeklySlots`), membros (`MemberPicker`). Admin: checkbox "organizar sem me incluir".
- **`Remarcar.tsx`** (`/remarcar/:id`) — escolhe novo horário (`WeeklySlots`) e remarca; avisa os membros.
- **`Perfil.tsx`** (`/perfil`) — info do Discord, **config de notificação** (minutos do 1º aviso → `updateMySettings`) e CRUD dos próprios personagens.

## Admin (`RequireAdmin`)
- **`AdminPlanilha.tsx`** (`/admin/planilha`) — tabela de todas as PTs; remarcar/cancelar.
- **`AdminPokemon.tsx`** (`/admin/pokemon`) — CRUD de pokémons (nome, imagem, categoria Tank/DPS/Sup), liberar uso; dica do `/pokemon-painel`.
- **`AdminLogs.tsx`** (`/admin/logs`) — histórico legível (`getHistory`) com filtro por tipo e paginação.
