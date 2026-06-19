# TripOptimizer — frontend

React 18 + TypeScript + Vite single-page UI for [TripOptimizer](../README.md). It consumes the FastAPI backend and renders the cheapest itinerary: a route map, an itinerary timeline with per-leg price provenance, a cost summary, and ranked alternatives. Trip state is encoded in the URL search params, so any result is shareable.

See the [root README](../README.md) for the project overview, architecture, and deployment.

## Develop

```bash
npm install
npm run dev        # http://localhost:5173 — proxies /api → http://localhost:8000 in dev
```

Run the backend separately (`cd ../backend && uv run uvicorn tripoptimizer.api.app:app --reload`).

## Scripts

| Script | Does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check (`tsc --noEmit`) + production build to `dist/` |
| `npm run typecheck` | Type-check only |
| `npm run test` / `test:cov` | Vitest (RTL + MSW), optionally with coverage |
| `npm run e2e` | Playwright E2E (boots backend + frontend automatically) |

## Configuration

`VITE_API_BASE_URL` — base URL of the API. Empty (default) uses the Vite dev proxy (`/api`); in production set it to the deployed backend origin. See `.env.example`.

## Stack

- **Data/state:** TanStack Query (server state), React Hook Form + Zod (form validation mirroring the backend's Pydantic contract), URL search params (shareable trip state)
- **UI:** Tailwind + hand-written shadcn/ui primitives, `react-simple-maps` for the keyless SVG map
- **Design direction:** Warm Bento / Editorial (cream + amber, display type, tabular mono)
