# frontend/src/lib/ — Cliente da API e hooks

> Ao adicionar/alterar uma função da API ou um tipo, atualize este README e o tipo correspondente.

## `api.ts`
Wrapper `req<T>(path, options)` (fetch com `credentials: include`, base `/api`, lança `Error` com `detail` em erro). Exporta funções e **interfaces TypeScript** espelhando a API.

**Funções por domínio:**
- Auth: `getMe`, `updateMySettings(notify_lead_minutes)`.
- Characters: `getCharacters`, `createCharacter`, `updateCharacter`, `deleteCharacter`.
- Members: `getMembers`.
- Schedules: `getSchedules`, `getFreeSlots`, `getCalendar`, `createSchedule`, `reschedule`, `cancelSchedule`, `confirmPresence`, `leaveParty`, `setMyCharacter`, `promoteColeader`, `kickMember`.
- Pokémon: `getPokemon`, `getMyPokemon`, `createPokemon`, `updatePokemon`, `deletePokemon`, `assignPokemon`, `unassignPokemon`.
- History: `getHistory`.

**Tipos:** `User`, `Character`, `Member`, `Schedule` (+ `ScheduleMember`), `Slot`, `ScheduleIn`, `CalendarParty`, `Pokemon`, `HistoryEntry`. Constante `WEEKDAY_LABEL` (0=Segunda..6=Domingo, padrão Python).

> Os tipos devem bater com o JSON retornado pela API (`api/routes/*`). Mudou a resposta de um endpoint? Atualize o tipo aqui.

## `useAuth.ts`
- **`useAuth()`** — `useQuery(["me"], getMe)`; retorna `{ user, isLoading, isLoggedIn }`. Base dos guards em `App.tsx`.
