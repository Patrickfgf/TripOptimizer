# TripOptimizer

**Find the cheapest *order* to visit a set of cities — not just the cheapest flights.**

When you plan a multi-country trip, the cheapest plan is rarely the order you'd guess. The order of the cities changes the date of each flight (days accumulate), and the date changes the price. TripOptimizer searches the city orderings *and* slides the trip within a flexible date window to return the lowest total-cost itinerary, with full per-leg price provenance.

> Built as a portfolio project spanning Data Engineering, Data Science, and Full-Stack — a pure Python optimization core behind a FastAPI service, with a React/TypeScript single-page frontend.

[![CI](https://github.com/Patrickfgf/TripOptimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Patrickfgf/TripOptimizer/actions/workflows/ci.yml)

**🔗 Live demo: [tripoptimizer-rouge.vercel.app](https://tripoptimizer-rouge.vercel.app)** — runs in your browser, no API key needed. · API health: [`/health`](https://tripoptimizer-api.onrender.com/health)

> ℹ️ The backend is on Render's free tier and sleeps after ~15 min idle, so the first request after a while can take ~30–60 s to wake.

---

## How it works

Given a set of cities, days in each, an origin/return airport, and a flexible start date (±N days), the optimizer evaluates every viable city ordering and date offset and returns the cheapest one.

- **Input:** `cities[]`, `days_per_city`, `origin_airport`, `return_airport`, `start_date`, `flex_days`
- **Output:** the cheapest itinerary `(city order, date offset, per-leg flights, total cost)` + a ranked list of alternatives, each leg labelled with its data source.

**Guardrails:** ≤ 8 cities (keeps the exact search tractable), `flex_days` default ±3 / max ±7, currency fixed to EUR. Flights only in the MVP.

### The algorithm

With fixed days per city, the date of the *k*-th leg depends only on the *set* of cities already visited — so the search collapses to the **Held–Karp** dynamic program over subsets (`O(2ⁿ·n²)`, exact). A brute-force permutation engine doubles as the **test oracle**: every Held–Karp result is checked against brute force, so the fast path can't silently diverge from the correct one.

## Architecture

Monorepo: a pure Python optimization core (no HTTP, no disk) behind a thin FastAPI edge, plus a React frontend. I/O lives only at the boundaries.

```
TripOptimizer/
├─ backend/
│  ├─ tripoptimizer/
│  │  ├─ core/
│  │  │  ├─ optimizer/   # cheapest-route search (pure, no I/O) + test oracle
│  │  │  ├─ fares/       # FareProvider chain: Cached(seed) -> CachingLive(on-demand) -> Synthetic
│  │  │  └─ graph/       # airports/IATA + haversine distance
│  │  ├─ api/            # FastAPI: /optimize, /airports, /health
│  │  └─ ingestion/      # offline: Travelpayouts → normalized Parquet snapshot (idempotent CLI)
│  ├─ data/              # committed fares snapshot (Parquet) + airport reference data
│  └─ tests/             # pytest — oracle, contract, integration
├─ frontend/             # React 18 + TS + Vite + Tailwind + shadcn/ui
├─ render.yaml           # Render blueprint (backend Web Service)
├─ vercel.json           # Vercel build config (frontend, monorepo)
└─ docs/                 # design specs + internal dev guide (PT-BR)
```

### Tech stack

| Layer | Choice |
|---|---|
| Core / API | Python 3.12, FastAPI, Pydantic v2 |
| Data | DuckDB + Parquet (typed, columnar, zero-server) |
| Flight data | Travelpayouts Data API — on-demand live fetch + in-process cache (token-gated), committed snapshot seed, synthetic fallback |
| Frontend | React 18, TypeScript, Vite, Tailwind, shadcn/ui |
| Frontend data/state | TanStack Query, Zod (controlled inputs + parsing), URL search-param state |
| Tests | pytest (backend) · Vitest + RTL + MSW + Playwright (frontend) |

A few deliberate **why-X-not-Y** calls (full rationale in `docs/`):

- **Travelpayouts, not Amadeus/Skyscanner** — Amadeus is decommissioning self-service (2026), Skyscanner is partner-gated; Travelpayouts gives a free token with cheapest-by-date prices.
- **On-demand + cache, not a pre-computed N² grid** — a combinatorial search fires `~N²` price lookups, so pre-computing the whole airport×date grid hits the free API's rate limit hard (46 airports × 30 days ≈ 62k calls). Instead each `/optimize` fetches only the cells *its* trip needs — concurrently, behind a time budget — and caches them in-process; a committed snapshot seeds popular routes. Naive live-per-*request* is still avoided: results are cached and reused, and the source labels stay honest.
- **Synthetic fallback behind a Strategy interface** — any missing `(A, B, date)` cell falls back to a deterministic synthetic fare, so the public demo never returns empty, and each leg honestly reports `cached` vs `synthetic`.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness + deep check (reference data loaded, snapshot store queryable) |
| `GET` | `/airports` | All known airports (IATA, name, city, country, lat/lon) |
| `POST` | `/optimize?engine=bruteforce\|heldkarp` | Cheapest city ordering + date slide for the trip |

```bash
curl -X POST localhost:8000/optimize -H 'content-type: application/json' -d '{
  "cities": ["BCN", "ROM"],
  "days_per_city": {"BCN": 3, "ROM": 2},
  "origin_airport": "LIS",
  "return_airport": "LIS",
  "start_date": "2026-07-01",
  "flex_days": 3
}'
```

The response carries `best`, ranked `alternatives`, a `data_source` (`cached` / `synthetic` / `mixed`), and the `snapshot_date` so the UI can be honest about where each price came from.

## Local development

Requires [uv](https://docs.astral.sh/uv/) (Python) and Node 18+.

**Backend** (serves on `http://localhost:8000`):

```bash
cd backend
uv sync --all-extras
uv run uvicorn tripoptimizer.api.app:app --reload
```

**Frontend** (serves on `http://localhost:5173`, proxies `/api` → `:8000` in dev):

```bash
cd frontend
npm install
npm run dev
```

Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` → `frontend/.env` if you need to override defaults. The app runs with **no API key**: it serves the committed snapshot and falls back to synthetic fares.

## Testing

```bash
# Backend — pytest + coverage + ruff
cd backend && uv run pytest && uv run ruff check .

# Frontend — typecheck + unit/integration + build, then E2E
cd frontend && npm run typecheck && npm run test:cov && npm run build && npm run e2e
```

The Playwright E2E spins up the real backend and frontend (see `frontend/playwright.config.ts`).

## Deployment

> **Live now:** backend on Render (`tripoptimizer-api.onrender.com`), frontend on Vercel (`tripoptimizer-rouge.vercel.app`). The steps below reproduce that setup from a fresh clone.

Backend → **Render** (`render.yaml`), frontend → **Vercel** (`vercel.json`). Both configs are committed, so the deploy is reproducible. Deploy order matters because the two services reference each other's URLs:

1. **Backend on Render** — New ▸ Blueprint, point it at this repo. Render reads `render.yaml`, builds `backend/` with uv, and starts `uvicorn … --host 0.0.0.0 --port $PORT`. Note the service URL (e.g. `https://tripoptimizer-api.onrender.com`).
2. **Frontend on Vercel** — Import the repo. Vercel reads `vercel.json` (root). Set env var **`VITE_API_BASE_URL`** to the Render URL from step 1. Deploy and note the Vercel URL.
3. **Close the loop** — back on Render, set **`FRONTEND_ORIGINS`** to the exact Vercel URL and redeploy. Without this, the live frontend is blocked by CORS (the backend logs a startup warning when it's unset).

## Data & provenance

Fares resolve through a `FallbackFareProvider` chain — **committed snapshot (seed) → on-demand live fetch (cached) → synthetic** — and every leg is labelled with where its price came from (`cached` / `synthetic`, aggregated per trip to `cached` / `synthetic` / `mixed`). The serving universe is **46 European airports**.

- **On-demand (serving).** With `TRAVELPAYOUTS_TOKEN` set, a cache miss is fetched live from Travelpayouts, cached in-process, and reused. Each `/optimize` first warms its trip's `(origin, destination, date)` cells in one concurrent, time-budgeted batch, so the search hits the cache instead of firing hundreds of sequential calls. Without the token the service runs on the snapshot + synthetic fallback only (no behaviour change). The in-process cache resets on restart (e.g. Render's free tier sleeps when idle); a durable cache (Postgres) is the next step toward a wider airport set and a 90-day window.
- **Seed snapshot (offline).** An optional committed Parquet warms popular routes for an instant first response. (Re)generate it from live data (needs the free Travelpayouts token in `backend/.env`):

```bash
cd backend
uv run python -m tripoptimizer.ingestion.build_snapshot \
  --airports LIS OPO MAD BCN CDG FCO BER ATH --start 2026-07-01 --days 30 --workers 8
```

## Roadmap

MVP is flights-only route optimization. Post-MVP: buses/trains as additional legs, and nearby-city recommendations (suggest detours that lower total cost).

---

*Internal dev narrative (PT-BR), design specs, and the full decision log live in [`docs/`](docs/).*
