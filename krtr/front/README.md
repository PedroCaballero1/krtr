# krtr/front

React + Vite + TypeScript + Tailwind + shadcn/ui SPA for krtr, compiled to
static files served by FastAPI (`krtr/back/web/`) in the same domain. See
[`docs/guia-web-seguridad_modal.md`](../../docs/guia-web-seguridad_modal.md) for the
full plan.

This package is installed as an npm workspace from the repo root, so its
dependencies are resolvable from `tests/front/` (which mirrors `src/` 1:1,
outside the package — see the "Frontend (TypeScript/React)" section of
[`CLAUDE.md`](../../CLAUDE.md)).

## Setup

From the repo root:

```sh
npm install
```

## Commands

Run from `krtr/front/` (or with `-w krtr/front` from the repo root):

- `npm run dev` — starts the Vite dev server, proxying `/api`, `/auth` and
  `/healthz` to a FastAPI backend running on `http://localhost:8000`.
- `npm run build` — type-checks and builds the production bundle into `dist/`.
- `npm test` — runs the Vitest suite in `tests/front/`.
- `npm run lint` — runs ESLint over `src/` and `tests/front/`.
- `npm run format` — checks Prettier formatting.
