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
- **Output:** the cheapest itinerary `(city order, date offset, per-leg flights, total cost)` + a ranked list of alternatives, each leg labelled with its data source — or an honest "incomplete" result when a route has no real fare.

**Guardrails:** ≤ 8 cities (keeps the exact search tractable), `flex_days` default ±3 / max ±7, currency fixed to EUR. Flights only in the MVP.

### The algorithm

With fixed days per city, the date of the *k*-th leg depends only on the *set* of cities already visited — so the search collapses to the **Held–Karp** dynamic program over subsets (`O(2ⁿ·n²)`, exact). A brute-force permutation engine doubles as the **test oracle**: every Held–Karp result is checked against brute force, so the fast path can't silently diverge from the correct one. A missing real fare makes an itinerary *infeasible* (skipped), never a crash — the engine returns the cheapest fully-real ordering, or reports that none exists.

## Architecture

Monorepo: a pure Python optimization core (no HTTP, no disk) behind a thin FastAPI edge, plus a React frontend. I/O lives only at the boundaries.

```
TripOptimizer/
├─ backend/
│  ├─ tripoptimizer/
│  │  ├─ core/
│  │  │  ├─ optimizer/   # cheapest-route search (pure, no I/O) + test oracle
│  │  │  ├─ fares/       # FareProvider chain: Cached(seed) -> CachingMonth(on-demand month-matrix)
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
| Data | DuckDB + Parquet (typed, columnar, zero-server) · optional Postgres (durable fare cache) |
| Flight data | Travelpayouts month-matrix — on-demand live fetch (one call warms a whole month) behind a durable cache (token-gated) + committed snapshot seed. **Real-or-nothing: no synthetic fares** |
| Frontend | React 18, TypeScript, Vite, Tailwind, shadcn/ui |
| Frontend data/state | TanStack Query, Zod (controlled inputs + parsing), URL search-param state |
| Tests | pytest (backend) · Vitest + RTL + MSW + Playwright (frontend) |

A few deliberate **why-X-not-Y** calls (full rationale in `docs/`):

- **Travelpayouts, not Amadeus/Skyscanner** — Amadeus decommissioned its self-service portal (shutdown July 2026), and Skyscanner's official API is partner-gated (it needs an established business with ~100k monthly traffic). "Just scrape Skyscanner" is a dead end too: it breaks their ToS, is blocked by Akamai + TLS fingerprinting, and — for an EU-focused project — is contractually enforceable (CJEU *Ryanair v. PR Aviation*, C‑30/14). Travelpayouts gives a free, sanctioned token; its **month-matrix** endpoint returns the cheapest fare per day, a whole month per call.
- **On-demand + cache, not a pre-computed N² grid** — a combinatorial search fires `~N²` price lookups, so pre-computing the whole airport×date grid is infeasible on a free tier. Each `/optimize` fetches only the cells *its* trip needs — concurrently, behind a time budget — and caches them; a committed snapshot seeds popular routes. Measuring real coverage drove the key call: **switching from the per-date endpoint to month-matrix lifted coverage ~31% → ~48% and cut calls ~30×** (one request returns a whole month).
- **Real-or-nothing, no synthetic fares** — every price shown is real (committed snapshot or live Travelpayouts). When a route has no real fare in the window, the API says so (`status: "incomplete"`, listing the unpriced routes) rather than fabricating a number. The provider chain is a Strategy interface, so a paid live-search source can slot in later to close the remaining coverage gaps without a rewrite.

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

The response is either a full result (`status: "ok"`) carrying `best`, ranked `alternatives`, a `data_source` (`cached` / `mixed`), and the `snapshot_date`; or an honest `status: "incomplete"` listing the `missing_routes` that have no real fare — so the UI never shows a fabricated price.

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

Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` → `frontend/.env` if you need to override defaults. The app runs with **no API key**: it serves the committed snapshot, and routes it can't price from real data are reported as unavailable (no synthetic fallback). Set `TRAVELPAYOUTS_TOKEN` to enable on-demand live fares.

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

**Optional — durable fare cache:** create a free **[Neon](https://neon.tech) Postgres** and set **`DATABASE_URL`** on Render (prefer the pooled `-pooler` connection string) to persist on-demand fares across restarts; the `fare_cache` table is created automatically on first use. Leave it unset to keep the in-process cache.

## Data & provenance

Fares resolve through a `FallbackFareProvider` chain — **committed snapshot (seed) → on-demand live fetch (month-matrix, cached)** — and every leg is labelled `cached` (aggregated per trip to `cached` / `mixed`). There is **no synthetic fallback**: a cell with no real fare stays unpriced and the optimizer reports it as an incomplete result. The serving universe is **46 European airports**.

- **On-demand (serving).** With `TRAVELPAYOUTS_TOKEN` set, a cache miss fetches the whole month from Travelpayouts' month-matrix (one call ≈ 30 cells), caches it, and reuses it. Each `/optimize` first warms its trip's `(origin, destination, date)` cells in one concurrent, time-budgeted batch, so the search hits the cache instead of firing hundreds of sequential calls. Without the token the service runs on the committed snapshot only — unpriced routes are reported honestly, never synthesized.
- **Durable cache (optional).** The default cache is in-process and resets on restart (e.g. Render's free tier sleeps when idle), so popular routes re-fetch on every wake. Set `DATABASE_URL` and the same on-demand fares persist in **Postgres** instead — a parameterized UPSERT with a 7-day freshness TTL (`FARE_CACHE_TTL_DAYS`), behind the same `FareCacheStore` interface, so nothing else changes. This survives restarts and is the unlock toward a wider airport set and a 90-day window. A DB outage degrades to a cold cache, never a 500.
- **Seed snapshot (offline).** An optional committed Parquet warms popular routes for an instant first response. (Re)generate it from live data (needs the free Travelpayouts token in `backend/.env`):

```bash
cd backend
uv run python -m tripoptimizer.ingestion.build_snapshot \
  --airports LIS OPO MAD BCN CDG FCO BER ATH --start 2026-07-01 --days 30 --workers 8
```

## Roadmap

MVP is flights-only route optimization. Post-MVP: buses/trains as additional legs, and nearby-city recommendations (suggest detours that lower total cost). A paid live-search source (e.g. Duffel) can later close the coverage gaps that a cached-price API leaves on thin routes.

---

*Internal dev narrative (PT-BR), design specs, and the full decision log live in [`docs/`](docs/).*
