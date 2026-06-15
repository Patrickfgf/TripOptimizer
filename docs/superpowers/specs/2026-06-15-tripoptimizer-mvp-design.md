# TripOptimizer — MVP Design Spec

- **Date:** 2026-06-15
- **Status:** Approved (design) — pending spec review before implementation planning
- **Author:** Patrick Fernandes Godinho Filho
- **Owner doc location:** `docs/superpowers/specs/2026-06-15-tripoptimizer-mvp-design.md`

---

## 1. Problem & Purpose

When planning a multi-city trip across several countries, the cheapest plan is rarely the order you first imagine. The order of the cities changes each flight's date (days accumulate), and the date changes the price. A traveler ends up manually re-checking every permutation of the route **and** every date variation — exactly the pain the author lived during his Erasmus in Portugal (15 countries visited).

**TripOptimizer** takes a set of destination cities, the number of days to spend in each, a departure airport, a return airport, and a start date with a flex window, and computes the **cheapest route ordering** with real(ish) flight prices.

This is also a **portfolio project**: it must demonstrate skills relevant to Data Analyst, Data Scientist, Data Engineer, and general Full-Stack roles, with a public, reproducible live demo and a clear "why X not Y" decision trail.

## 2. MVP Scope

### In scope
- Input: `cities[]`, `days_per_city`, `origin_airport` (IATA), `return_airport` (IATA), `start_date`, `flex_days` (±N).
- Output: cheapest itinerary = best `(city order, start-date offset, per-leg flights, total cost)` + a ranked list of alternatives.
- **Route shape:** `origin_airport → city₁ → … → city_k → return_airport`. Only the order of the middle cities is optimized; the trip always starts at `origin_airport` and ends at `return_airport`.
- **Date model: hybrid** — optimize the city **order** *and* slide the whole itinerary **±N days** around the start date to capture nearby bargains.
- Flights only.
- Public live demo that runs with **no API key** (reads a committed snapshot; synthetic fallback).

### Out of scope (future — see `tripoptimizer-future-roadmap` memory)
- Buses and trains (multimodal intra-country options).
- Itinerary-building assistant (recommend nearby cities/countries, cheaper return hubs).
- Real-time bookable fares / booking flow.
- Multi-passenger optimization (MVP assumes `adults=1`).

### Guardrails
- **Max 8 cities** (brute-force / Held-Karp both tractable). Beyond 8: reject with a clear message in MVP; heuristic is a future enhancement.
- `flex_days` default **±3**, capped (e.g. ±7) to bound the search.
- Currency fixed to **EUR**.

## 3. Key Decisions (with why-X-not-Y)

### 3.1 Stack — Python core + React frontend
FastAPI + a pure-Python optimization engine + a DuckDB/pandas data layer, with a React 18 + TypeScript + Vite frontend.
- **Why:** reuses the author's proven, strongest stack (the "Eldorado" lead-pipeline: FastAPI, Pydantic, DuckDB, pandas, pytest, GitHub Actions) and covers all four target roles in one project (DE + DS + DA + Full-Stack).
- **Discarded:** a pure TypeScript/Supabase-Edge-Functions (Deno) build (as the CV originally described). Trade-off: that maximizes the serverless/full-stack angle but under-uses the data stack and the algorithm showcase. Discarded a pure data-lab (Streamlit only) build too — it would drop the full-stack signal.

### 3.2 Flight data source — Travelpayouts (real cached) + synthetic fallback
The optimizer talks only to a `FareProvider` abstraction. Real fares are seeded **offline** from the **Travelpayouts/Aviasales Data API** into a committed snapshot; missing pairs fall back to **deterministic synthetic fares** over the real **OurAirports** graph.
- **Why Travelpayouts:** free, instant self-service token (`X-Access-Token`), no MAU gate for the cached Data API, has the two needed queries — `prices_for_dates` (one-way) and `grouped_prices` (cheapest-by-date) — and surfaces low-cost carriers (Ryanair/easyJet/Wizz) relevant to budget intra-Europe travel.
- **Why NOT Amadeus (originally chosen):** Amadeus is **decommissioning its Self-Service portal on 2026-07-17**; new registrations are already paused. A recruiter could not even register to reproduce the project. Verified live (PhocusWire + corroborating sources, 2026).
- **Why NOT Skyscanner (author's first instinct):** the official API is **partner-gated** to established businesses with no public sandbox; the self-serve "Skyscanner" listings on RapidAPI/Apify are **unofficial scrapers that violate Skyscanner's ToS** and break frequently.
- **Why NOT Kiwi.com Tequila:** public self-service was **closed in May 2024** (invitation-only now). Cited as design inspiration (its NOMAD endpoint is literally "cheapest ordering") but unusable.
- **Why NOT Duffel:** free sandbox returns only synthetic "Duffel Airways" data; real fares require a funded account; no cheapest-date endpoint.
- **Reproducibility caveat (documented honestly):** Travelpayouts prices are **cached/indicative** (2–7 days old, not live-bookable), default currency is RUB (we force EUR), coverage is search-driven (popular pairs reliable; obscure pairs may be empty → synthetic fallback), and access is under an affiliate ToS (tolerated for a non-monetized demo). Data is always labeled `cached (as of <snapshot_date>)` or `synthetic` in the UI.

### 3.3 Reproducibility — snapshot, never live-per-request
The deployed demo reads a **committed Parquet/DuckDB snapshot** (+ synthetic fallback), so it is deterministic, offline-capable, free, and reproducible (Restart & Run All). Live API calls are an **offline ingestion step**, never a per-visitor call.
- **Discarded:** calling the API per request. Trade-off: simpler conceptually, but combinatorial search (~N² pair×date lookups) burns any quota, is non-reproducible, and makes the demo depend on a private key. Snapshot + cache-by-`(origin,dest,date)` fixes all three. Mirrors the author's existing synthetic-data pattern (Faker on Eldorado).

### 3.4 Algorithm — brute-force engine, Held-Karp as the documented optimization
For each start offset `s ∈ [-N, +N]` and each city permutation, derive each flight's date from accumulated days, sum fares, keep the global minimum (≤ 8 cities → `n!` tractable).
- **Key structural insight:** because days-per-city are fixed, the date you fly the k-th leg depends only on the **set** of already-visited cities (their total days), not their internal order → **Held-Karp DP over subsets (2ⁿ·n²)** is exact. Plan: brute-force is the MVP engine (matches "test all permutations") *and* the **test oracle** validating the DP version.

## 4. Architecture

Monorepo, Python core + React edge:

```
tripoptimizer/
├─ backend/
│  ├─ core/
│  │  ├─ optimizer/     # cheapest-route search (pure, no I/O)
│  │  ├─ fares/         # FareProvider: Travelpayouts | Cached | Synthetic
│  │  └─ graph/         # airports/IATA (OurAirports) + haversine distance
│  ├─ api/              # FastAPI: /optimize, /airports, /health
│  ├─ ingestion/        # offline: Travelpayouts → normalized snapshot
│  └─ tests/            # pytest
├─ frontend/            # React 18 + TS + Vite + Tailwind + shadcn/ui
├─ data/                # committed snapshot (Parquet/DuckDB) + airport graph
├─ notebooks/           # narrated EDA of collected fares
└─ docs/                # this spec + internal guide (HTML) + README
```

- **Discarded:** two separate repos. Trade-off: cleaner decoupling, but for a solo portfolio piece one clone / one CI / one end-to-end narrative wins.

## 5. Components (each independently testable)

| Component | Responsibility | Depends on | Boundary |
|---|---|---|---|
| `core/optimizer` | Given a fare matrix + trip spec → best `(order, offset, legs, total)` + alternatives | nothing (pure) | functions only, zero I/O |
| `core/fares` | `FareProvider.get_fare(origin, dest, date)` | provider impls | interface; impls: `TravelpayoutsProvider`, `CachedProvider`, `SyntheticProvider` |
| `core/graph` | IATA, lat/long, country; haversine distance | OurAirports files | read-only reference data |
| `api` | HTTP boundary; validation; orchestration | core/* | FastAPI + Pydantic |
| `ingestion` | Offline raw→curated fare snapshot | Travelpayouts, core/graph | CLI script, idempotent |
| `frontend` | Input form + results (timeline, per-leg fares, total, map) | api | React SPA |

## 6. Data Flow

`Form (React)` → `POST /optimize` → **Pydantic validation** → API builds candidate date set (`start ± N` + day accumulation) → requests only the needed `(A,B,date)` cells from the `FareProvider` (demo: `Cached`, falls back to `Synthetic`) → `optimizer` searches → ranked `TripResult` → rendered in the frontend.

## 7. Data Model (explicit grain)

**Fare row** — *grain: 1 row = origin × destination × date × fare*:

| field | type | example |
|---|---|---|
| `origin` | str (IATA) | `LIS` |
| `destination` | str (IATA) | `BCN` |
| `date` | date (ISO `YYYY-MM-DD`) | `2026-07-03` |
| `fare` | float (EUR) | `48.99` |
| `currency` | str | `EUR` |
| `source` | enum | `travelpayouts` \| `cached` \| `synthetic` |
| `snapshot_date` | date (ISO) | `2026-06-15` |

Persisted as **Parquet** (typed, columnar). Queried/aggregated via **DuckDB**.

**API schemas (Pydantic):**
- `TripRequest`: `cities: list[str]`, `days_per_city: dict[str,int]`, `origin_airport: str`, `return_airport: str`, `start_date: date`, `flex_days: int = 3`.
- `TripResult`: `best: Itinerary`, `alternatives: list[Itinerary]`, `data_source: str`, `snapshot_date: date`.
- `Itinerary`: `order: list[str]`, `start_offset: int`, `legs: list[Leg]`, `total: float`.
- `Leg`: `origin: str`, `destination: str`, `date: date`, `fare: float`.

## 8. Error Handling & Validation
- Pydantic validates input at the boundary (reject empty cities, unknown IATA, `days_per_city` mismatch, > 8 cities, `flex_days` out of range) with clear messages.
- `TravelpayoutsProvider`: retry + exponential backoff on HTTP 429; force `currency=eur`.
- **Graceful synthetic fallback:** any missing `(A,B,date)` cell → deterministic synthetic fare; the demo never returns empty. Result is labeled with its `data_source`.
- Deep `GET /health` touches the DuckDB store and returns 503 if unavailable (mirrors Eldorado).

## 9. Testing (target ≥ 80%)
- **Optimizer:** correctness via **DP vs brute-force oracle** on small known cases; property-based tests (best ≤ any specific permutation); edge cases (1 city, identical days).
- **FareProvider:** contract tests shared across all implementations; `SyntheticProvider` determinism (fixed seed).
- **API:** `httpx` integration tests; schema validation; error paths.
- **Frontend:** component smoke test + one happy-path E2E (Playwright).
- **CI:** GitHub Actions — Ruff + pytest on 3 Python versions; secret scan; fail under coverage threshold.

## 10. Reproducibility & Deployment
- `DEMO_MODE` reads the committed snapshot → repo runs with **no key**; secrets in `.env` (gitignored).
- Environment via **`uv`** + `pyproject.toml` (pinned).
- **Ingestion is idempotent**: re-running produces the same curated snapshot (raw read-only → curated).
- Deploy: **backend on Render/Fly + frontend on Vercel**, with a live demo URL for the CV. Simpler alternative: single service where FastAPI serves the built frontend.

## 11. The Two Docs (author's standing rule)
- **Internal guide (HTML, PT-BR)** in `docs/` — extensive: decisions, stack, why-X-not-Y, dev narrative. **Updated on every commit.**
- **Public README (EN)** — normal, written at the end.

## 12. CV Framing (what each part sells)
- **DE:** raw→curated ingestion, Parquet/DuckDB snapshot, `FareProvider` abstraction, CI, deep healthcheck, provider-swap resilience story.
- **DS:** the optimizer (date-dependent TSP, Held-Karp over subsets, DP-vs-brute-force oracle).
- **DA:** narrated EDA of collected fares (Jupyter) + frontend visualizations (route map, cost breakdown).
- **Full-Stack:** FastAPI + React/TS + live deploy + external API integration (OAuth/token, retry/backoff).

## 13. Risks
- Travelpayouts coverage gaps for obscure pairs → synthetic fallback mandatory.
- Cached/indicative prices must be clearly labeled to stay credible.
- Combinatorial cost → cache by `(origin,dest,date)`; cap cities at 8.
- Token leakage → env vars + `.gitignore` + CI secret scan.
- Travelpayouts default RUB/market → always set `currency=eur` and an appropriate market.

## 14. Open Questions (resolve during planning)
- Exact deploy target (Render vs Fly vs single-service) — defer to plan.
- Whether the map view is MVP or fast-follow (low cost via OurAirports lat/long; lean toward MVP).
