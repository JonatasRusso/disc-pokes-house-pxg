# frontend/ — Site (React + Vite + TypeScript + Tailwind)

SPA que consome a API do Railway. Deploy na **Vercel**.

> Ao criar/alterar páginas, componentes ou funções da API client, atualize o README da subpasta correspondente.

## Configuração
- `index.html` — HTML raiz (título "VKG House").
- `vite.config.ts` — Vite + plugin React; injeta `__APP_VERSION__` (lido de `package.json`); proxy `/api → localhost:8000` em dev.
- `vercel.json` — em produção, **rewrite `/api/* → Railway`** (a API) + fallback SPA (`/(.*) → /index.html`). É o que faz o front e a API parecerem same-origin.
- `tailwind.config.js`, `postcss.config.js`, `tsconfig.json` — build/estilo.
- `package.json` — deps e **`version`** (aparece no rodapé do site via `__APP_VERSION__`). **Subir a versão a cada deploy.**

## Scripts
- `npm run dev` — dev server (porta 5173). `npm run build` — `tsc -b && vite build`.

## Estrutura
- `src/` — código (ver README). Páginas em `src/pages/`, componentes em `src/components/`, cliente da API em `src/lib/`.
