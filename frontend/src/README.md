# frontend/src/ — Código-fonte do front

> Ao alterar rotas, providers ou estrutura, atualize este README.

## Arquivos
- **`main.tsx`** — entrypoint React. Monta `<App/>` dentro de `BrowserRouter` + `QueryClientProvider` (React Query) + Vercel `Analytics`.
- **`App.tsx`** — define as **rotas** e os guards:
  - `RequireAuth` (exige login), `RequireAdmin` (exige `is_admin`).
  - Rotas: `/` (Login), `/dashboard`, `/minhas-pts`, `/calendario`, `/agendar`, `/remarcar/:id`, `/perfil`, `/admin/planilha`, `/admin/pokemon`, `/admin/logs`.
- **`index.css`** — Tailwind + estilo base (tema escuro).
- **`vite-env.d.ts`** — tipos do Vite + declaração de `__APP_VERSION__`.

## Subpastas
- `pages/` — uma por rota. `components/` — reutilizáveis. `lib/` — cliente da API e auth. (READMEs próprios.)

## Convenções
- Dados via **React Query** (`useQuery`/`useMutation`); chaves comuns: `["me"]`, `["schedules"]`, `["characters"]`, `["pokemon"]`, `["members"]`, `["calendar"]`, `["free-slots"]`. Após mutações, invalidar a chave afetada.
- Todas as chamadas HTTP passam por `src/lib/api.ts` (sempre `credentials: "include"`).
