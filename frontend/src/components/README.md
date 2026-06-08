# frontend/src/components/ — Componentes reutilizáveis

> Ao adicionar/alterar props ou comportamento, atualize este README.

## `Layout.tsx`
Casca do app: navbar (marca **💀 VKG House**, links Dashboard / Minhas PTs / Agendar / Calendário / Perfil; Admin/Pokémons/Logs só para admin), avatar + badge **Admin** + logout, e rodapé com a versão (`__APP_VERSION__`). Envolve todas as páginas.

## `WeeklySlots.tsx`
Grade semanal (colunas = dias da semana começando na **segunda**, linhas = horas 00:00–23:00). Props: `slots` (de `getFreeSlots`), `selected`, `onSelect`, `parties?` (de `getCalendar`).
- Células: **verde** = disponível (clicável), **roxo** = selecionada, **âmbar** = PT marcada (mostra nicks; tooltip com membros). Usado em **Agendar**, **Remarcar** e **Calendário** (este só leitura, `onSelect` vazio).

## `MemberPicker.tsx`
Seletor dos membros da PT ao agendar. Props: `members` (de `getMembers`), `excludeId` (o criador), `value`/`onChange` (lista de `PartyMemberInput`).
- Por linha: escolhe o membro, a função e o personagem **livre** dele; se não tiver personagem, marca como "será convidado a criar". Exporta a interface `PartyMemberInput`.
