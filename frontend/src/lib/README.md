# frontend/src/lib/ — Cliente da API e hooks

> Ao adicionar/alterar uma função da API ou um tipo, atualize este README e o tipo correspondente.

## `api.ts`
Wrapper `req<T>(path, options)` (fetch com `credentials: include`, base `/api`, lança `Error` com `detail` em erro). Exporta funções e **interfaces TypeScript** espelhando a API.

**Funções por domínio:**
- Auth: `getMe`, `updateMySettings(notify_lead_minutes)`.
- Characters: `getCharacters`, `createCharacter`, `updateCharacter`, `deleteCharacter`.
- Members: `getMembers`.
- Schedules: `getSchedules`, `getFreeSlots`, `getCalendar`, `createSchedule`, `reschedule`, `addMember`, `setMemberExternal`, `cancelSchedule`, `confirmPresence`, `leaveParty`, `setMyCharacter`, `promoteColeader`, `kickMember`.
- Pokémon: `getPokemon`, `getMyPokemon`, `createPokemon`, `updatePokemon`, `deletePokemon`, `assignPokemon`, `unassignPokemon`.
- History: `getHistory`.
- Helpers de horário: `fmtTime`, `fmtDuration`, `buildStartIso`, `DURATION_OPTIONS`, `WEEKDAY_LABEL`/`WEEKDAY_SHORT`, `SLOT_STEP_MIN`, `DEFAULT_DURATION_MIN`.

**Tipos:** `User`, `Character`, `Member`, `Schedule` (+ `ScheduleMember`), `Slot`, `ScheduleIn`, `CalendarParty`, `Pokemon`, `HistoryEntry`, `Role`.

## `queryKeys.ts`
`qk` — chaves centralizadas do React Query (`schedules`, `calendar`, `freeSlots`, `characters`, `members`, `pokemon`, `me`, ...). Use sempre estas chaves em `useQuery`/`invalidateQueries` para evitar cache não invalidado por key divergente.

## `../hooks/` — Hooks de dados
- **`useCharacters()`** — lista + `create`/`update`/`remove` de personagens, com invalidação automática (`qk.characters`). Usado no **Perfil**.
- **`usePartySchedules()`** — lista de PTs + mutações comuns (`confirm`/`leave`/`cancel`/`setChar`/`promote`/`kick`), invalidando `schedules`+`calendar`.

> Os tipos devem bater com o JSON retornado pela API (`api/routes/*`). Mudou a resposta de um endpoint? Atualize o tipo aqui.

## `useAuth.ts`
- **`useAuth()`** — `useQuery(["me"], getMe)`; retorna `{ user, isLoading, isLoggedIn }`. Base dos guards em `App.tsx`.
