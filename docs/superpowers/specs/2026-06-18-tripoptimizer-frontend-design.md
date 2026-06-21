# TripOptimizer Frontend — Design Spec (Plan 4)

- **Date:** 2026-06-18
- **Status:** Approved (design) — pending spec review before implementation planning
- **Author:** Patrick Fernandes Godinho Filho
- **Owner doc location:** `docs/superpowers/specs/2026-06-18-tripoptimizer-frontend-design.md`
- **Parent spec:** `docs/superpowers/specs/2026-06-15-tripoptimizer-mvp-design.md` (§4 architecture, §5 frontend component, §6 data flow, §7 schemas, §11 two-docs rule)

---

## 1. Purpose & Scope

Build the **frontend** of TripOptimizer: a single-page React app that lets a user describe a multi-city trip, calls the existing FastAPI `/optimize` endpoint, and renders the cheapest itinerary — route map, per-leg flights with honest data-provenance labels, total cost, and ranked alternatives.

This is **Plan 4** of the project. Backend (Plans 1–3) and the data layer (Plan 2, minus the token-gated ingestion Task 9) are done and pushed. **Deploy + public README are Plan 5** and are out of scope here — except the minimal backend CORS change the frontend needs to talk to the API.

### In scope
- Input form: origin airport, return airport, ordered list of destination cities (IATA) with days each, start date, flex window.
- Result: best itinerary (route map + timeline of legs with dates/fares/source labels + total) + ranked alternatives with cost deltas.
- **Shareable URL state:** the trip is encoded in `?search-params` so a result is linkable and reproducible on load.
- **Interactive route map:** keyless SVG (react-simple-maps) plotting real airport lat/lon.
- Honest data labels: per-leg `cached`/`synthetic` chips and a top-level `data_source` + `snapshot_date`.
- A minimal `CORSMiddleware` addition to the backend (`api/app.py`).
- The project's **internal guide HTML** (`docs/internal-guide.html`), created here and updated on every commit (author's standing two-docs rule, spec §11).

### Out of scope (Plan 5)
- Deployment (Vercel/Render), frontend CI, public README.
- Engine toggle in the UI (Held-Karp vs brute-force) — the backend default is used; the algorithm story lives in docs/notebook, not a UI control.
- Multi-passenger, booking, real-time fares (MVP-wide out of scope).

## 2. Locked Decisions (with why-X-not-Y)

- **Single page + URL state, no router.** Form and results live on one scrolling page; `optimize` reveals the results; the trip is encoded in search-params (read on load → optional auto-run). *Discarded:* two routes with React Router (cleaner separation but more scaffolding for an essentially single flow); multi-step wizard (the input is small — a wizard adds friction without payoff).
- **Visual direction: Warm Bento / Editorial.** Cream surface, amber accent, bold display type + tabular mono for numbers, results in a bento grid. *Discarded:* Dark Analytics (the most "expected" SaaS look; the project's design rules warn against defaulting to dark mode) and Swiss/Data-Editorial (credible but more conservative). Bento treats data-viz as a design system — a stronger DA signal and more distinctive for a portfolio piece.
- **Map: keyless SVG via react-simple-maps** + a Europe topojson, plotting lat/lon from `/airports`. *Discarded:* tile-based MapLibre/Leaflet+OSM (real pan/zoom but adds a tile dependency, bigger bundle, breaks the "runs with no API key" identity) and an abstract no-geography diagram (cheapest but throws away the real-coordinates DA payoff).
- **React 18 + TS + Vite + Tailwind + shadcn/ui** (parent spec §4, locked). **TanStack Query** for server state, **React Hook Form + Zod** for the form, **Vitest + RTL + MSW** and **Playwright** for tests.
- **Zod schemas mirror the Pydantic contract** so validation and types are enforced at the client boundary (parent spec §8 "validate at boundaries").
- **No client-side optimization.** All combinatorial work stays in the backend; the frontend is presentation + orchestration only.

## 3. Backend API Contract (already implemented — the frontend consumes this verbatim)

- `GET /health` → `{ status, airports_loaded, snapshot_date | null }`.
- `GET /airports` → `Array<{ iata, name, city, country, lat, lon }>`.
- `POST /optimize?engine=bruteforce|heldkarp`
  - body `TripRequest`: `{ cities: string[], days_per_city: Record<string,int>, origin_airport: string, return_airport: string, start_date: ISO-date, flex_days: int }`
  - → `TripResult`: `{ best: Itinerary, alternatives: Itinerary[], data_source: "cached"|"synthetic"|"mixed", snapshot_date: ISO-date | null }`
  - `Itinerary`: `{ order: string[], start_offset: int, legs: Leg[], total: number }`
  - `Leg`: `{ origin, destination, fly_date: ISO-date, price: number, source: string }`
- Backend validation already enforces: 1–8 cities, `flex_days` 0–7, `days_per_city` covers all cities with values > 0, known IATA only (400 on unknown). The form mirrors these so most errors are caught before the request.

## 4. Architecture & File Structure

Layered, I/O at the edges (mirrors the backend ethos):
- `lib/` — pure, testable: typed HTTP client, Zod schemas, URL ⇄ trip codec.
- `hooks/` — TanStack Query wrappers (the only place network I/O lives).
- `components/` — feature folders; presentational components stay pure.

```
frontend/
├─ index.html
├─ package.json
├─ vite.config.ts            # dev proxy /api → http://localhost:8000; reads VITE_API_BASE_URL
├─ tailwind.config.ts        # bento/editorial design tokens
├─ tsconfig*.json
├─ src/
│  ├─ main.tsx               # QueryClientProvider + App
│  ├─ App.tsx                # single page: <TripForm/> then <Results/>
│  ├─ lib/
│  │  ├─ api.ts              # getHealth / getAirports / optimize (fetch + base URL)
│  │  ├─ schemas.ts          # Zod: TripRequest, TripResult, Itinerary, Leg, Airport
│  │  └─ urlState.ts         # encode(trip) → search-params ; decode(search) → trip | null
│  ├─ hooks/
│  │  ├─ useAirports.ts      # useQuery GET /airports (also feeds map coords)
│  │  └─ useOptimize.ts      # useMutation POST /optimize
│  ├─ components/
│  │  ├─ trip-form/
│  │  │  ├─ TripForm.tsx           # RHF + zodResolver; orchestrates submit
│  │  │  ├─ AirportCombobox.tsx    # shadcn Command search over /airports
│  │  │  ├─ CityList.tsx           # ordered cities + per-city days stepper + remove/reorder
│  │  │  └─ DateFlexControls.tsx   # start_date picker + flex_days slider
│  │  ├─ results/
│  │  │  ├─ Results.tsx            # bento grid layout
│  │  │  ├─ RouteMap.tsx           # react-simple-maps + plotted legs
│  │  │  ├─ ItineraryTimeline.tsx  # legs: date, route, fare, source chip
│  │  │  ├─ CostSummary.tsx        # total + data_source + snapshot_date honesty block
│  │  │  └─ Alternatives.tsx       # ranked alternatives with Δ vs best
│  │  └─ ui/                       # shadcn primitives (button, command, input, slider, …)
│  └─ styles/{tokens.css, global.css}
└─ tests/
   ├─ unit/ …                # Vitest + RTL + MSW
   └─ e2e/optimize.spec.ts   # Playwright happy path
```

## 5. Data Flow

1. **Load:** `useAirports()` fetches `/airports` once (combobox options + a lookup `iata → {lat,lon,name,city}` for the map). `urlState.decode(location.search)` → if a valid trip is present, prefill the form and auto-run `optimize` (so a shared link reproduces the result).
2. **Submit:** RHF + Zod validate → build `TripRequest` → `useOptimize` mutation `POST /optimize` → on success render `Results`; `urlState.encode(trip)` written back via `history.replaceState` (shareable, no extra history entries).
3. **Map join:** for each `leg`, resolve `origin`/`destination` IATA → lat/lon from the `/airports` cache; draw great-circle-ish polylines + city markers.

## 6. Visual System (Warm Bento / Editorial)

- **Tokens** (`tokens.css`, also surfaced in `tailwind.config.ts`): `--surface` cream, `--ink` near-black, `--accent` amber, one secondary; type scale with a strong **display** family for headings and **tabular mono** for prices/dates; generous, non-uniform rhythm.
- **Results layout:** bento grid — large map cell, timeline cell, cost-summary cell, alternatives cell — with intentional hierarchy (not a uniform card grid).
- **Provenance as design:** per-leg chips — `cached` (neutral), `synthetic` (amber) — and a top-level `data_source` badge (`mixed` when legs differ) + `snapshot_date`. Data honesty is a first-class visual element (parent spec §3.2, §8).
- States are designed: hover/focus/active on interactive elements; a bento **skeleton** while `optimize` is pending.

## 7. Error Handling & States

- **Form invalid:** inline Zod messages; submit disabled until valid. UI enforces the backend guardrails (≤ 8 cities, `flex_days` 0–7, days > 0, every city has days) so the request is almost always valid.
- **Pending:** bento skeleton.
- **Network / 5xx:** error surface (toast/inline) + retry (TanStack Query retry).
- **400 unknown airport:** map the backend message to the offending field.
- **Never empty:** the backend's synthetic fallback guarantees a result; it is always labeled with its source.

## 8. Backend Change (minimal, part of Plan 4)

Add `CORSMiddleware` to `backend/tripoptimizer/api/app.py`, allow-origins from an env var (default `http://localhost:5173`). In local dev the Vite proxy already routes `/api` → `:8000`; CORS lets the deployed frontend (Plan 5) reach the published API. No other backend change.

## 9. Internal Guide (two-docs rule, spec §11)

Create `docs/internal-guide.html` (PT-BR, single self-contained file): purpose, stack, architecture, the why-X-not-Y decision trail (incl. this frontend's choices), and a running dev narrative. It is **updated on every commit** from this point on (author's standing rule; CV-framing memory). The public README stays a Plan 5 deliverable.

## 10. Testing (target ≥ 80% on logic)

- **Vitest + RTL + MSW:** `urlState` round-trip (encode∘decode = identity for valid trips, `null` for junk); `schemas` (accept valid, reject malformed payloads); `AirportCombobox` (search/select); `CityList` (days validation, reorder/remove); `CostSummary` & `ItineraryTimeline` (correct provenance labels per `source`).
- **Playwright (1 happy path):** load → fill origin/return + 3 cities/days + date → optimize → assert best route, total, map markers, and a provenance label are visible.
- Component tests mock the API at the network layer (MSW), never the real backend.

## 11. Risks

- **Airport coordinate gaps** for a city in the snapshot but missing from the airport reference → guard the map join (skip/segment gracefully); never crash the render.
- **URL state drift** vs the schema as fields evolve → `urlState.decode` is schema-validated and returns `null` on mismatch (graceful, no broken prefill).
- **shadcn/ui + React 18 version skew** → pin versions; shadcn components are copied in, not a runtime dep.
- **Bundle weight** (map topojson + shadcn) → lazy-load the map; keep the Europe topojson subset small (parent project is an EU sample).

## 12. CV Framing (what the frontend sells)

- **Full-Stack:** React 18 + TS + Vite, typed API integration, RHF + Zod boundary validation, URL-as-state, TanStack Query.
- **DA / visualization:** keyless geospatial route map from real lat/lon, cost breakdown, alternatives comparison — data-viz treated as a design system.
- **Engineering rigor:** layered/testable structure, MSW-mocked component tests + a Playwright E2E, honest data-provenance labeling end-to-end.
