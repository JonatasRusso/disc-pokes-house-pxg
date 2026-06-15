# frontend/src/components/ — Componentes reutilizáveis

> Ao adicionar/alterar props ou comportamento, atualize este README.

## `Layout.tsx`
Casca do app: navbar enxuta (marca **💀 VKG House**, links **Início / PTs / Calendário / Perfil**; **Agendar** saiu do topo — acessível pelo botão em PTs; admin agrupado num dropdown **Admin ▾** → Planilha / Pokémons / Logs), avatar + badge **Admin** + logout, e rodapé com a versão (`__APP_VERSION__`). Envolve todas as páginas.

## `SlotPicker.tsx`
Seletor compacto de horário (substitui a grade no input). Props: `value` (`SlotValue` = `{weekday, time "HH:MM", durationMin}`), `onChange`, `parties?` (de `getCalendar`), `excludeScheduleId?`.
- Campos: **dia da semana**, **início** (`input type=time`, passo 15 min), **duração** (`DURATION_OPTIONS`), e **"começar logo após outra PT"** (preenche dia+início com o fim da PT escolhida, mesmo em horário quebrado). Mostra o fim calculado e as PTs já marcadas no dia. Usado em **Agendar** e **Remarcar**. Converte para ISO via `buildStartIso` na página.

## `WeekCalendar.tsx`
Agenda semanal **só leitura** (substitui a antiga `WeeklySlots`). Props: `parties` (de `getCalendar`). Eixo de horas + blocos **posicionados pelo minuto de início e dimensionados pela duração**; janela ajustada ao intervalo das PTs; cor por dificuldade (HARD/NW), 📌 = remarcada esta semana; tooltip com membros. Usado no **Calendário**.

## `MemberPicker.tsx`
Seletor dos membros da PT ao agendar. Props: `members` (de `getMembers`), `excludeId` (o criador), `value`/`onChange` (lista de `PartyMemberInput`).
- Por linha: escolhe o membro, a função e o personagem **livre** dele; se não tiver personagem, marca como "será convidado a criar". Exporta a interface `PartyMemberInput`.
