# TripOptimizer Frontend — Implementation Plan (Plan 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the single-page React frontend that drives the existing FastAPI optimizer — a trip form, a keyless SVG route map, a per-leg itinerary timeline with honest data-provenance labels, total cost, ranked alternatives, and a shareable URL state.

**Architecture:** Layered SPA with I/O only at the edges. Pure/testable `lib/` (Zod schemas mirroring the Pydantic contract, a typed fetch client, a URL⇄trip codec) → TanStack Query `hooks/` → feature `components/` (`trip-form`, `results`, shadcn `ui`). No client-side optimization; the backend does all combinatorial work. Trip state is encoded in URL search-params (shareable, auto-runs on load).

**Tech Stack:** React 18 + TypeScript + Vite · Tailwind CSS + shadcn/ui · TanStack Query v5 · React Hook Form + Zod · react-simple-maps (+ world-atlas, offline) · Vitest + React Testing Library + MSW · Playwright. Backend touch: `CORSMiddleware` on the existing FastAPI app.

**Spec:** `docs/superpowers/specs/2026-06-18-tripoptimizer-frontend-design.md` (parent: `2026-06-15-tripoptimizer-mvp-design.md`).

---

## Context the engineer needs (read first)

- **The backend is done and unchanged except a CORS addition (Task 2).** Run it from `backend/` with `uv run uvicorn tripoptimizer.api.app:app --reload` (serves on `http://localhost:8000`). The exact JSON contract the frontend consumes:
  - `GET /health` → `{ "status": "ok", "airports_loaded": <int>, "snapshot_date": "YYYY-MM-DD" | null }`.
  - `GET /airports` → `[{ "iata": "LIS", "name": "...", "city": "Lisbon", "country": "PT", "lat": 38.77, "lon": -9.13 }, ...]`.
  - `POST /optimize?engine=bruteforce` body `{ "cities": ["BCN","ROM"], "days_per_city": {"BCN":3,"ROM":2}, "origin_airport": "LIS", "return_airport": "BER", "start_date": "2026-07-01", "flex_days": 3 }` → `{ "best": Itinerary, "alternatives": Itinerary[], "data_source": "cached"|"synthetic"|"mixed", "snapshot_date": "YYYY-MM-DD"|null }` where `Itinerary = { "order": string[], "start_offset": int, "legs": Leg[], "total": number }` and `Leg = { "origin": string, "destination": string, "fly_date": "YYYY-MM-DD", "price": number, "source": string }`.
  - **`cities` are IATA codes**, and `days_per_city` is keyed by those same IATA codes (not free-text city names). The form selects airports, not cities.
  - Backend already rejects: empty/>8 cities, `flex_days` outside 0–7, `days_per_city` not covering all cities or ≤ 0, unknown IATA (HTTP 400). The form mirrors these so requests are valid before they leave.
- **Run frontend commands from `frontend/`** (created in Task 1). Node 18+ assumed (`node -v`).
- **Environment gotchas (from prior sessions):**
  - A GateGuard hook fact-forces the first Bash and each new-file Write (state the facts, retry).
  - A ruff `--fix` PostToolUse hook runs on `.py` edits — when editing the backend, add an import in the same edit that uses it.
  - On Windows, the WindowsApps `python` shim is broken — always `uv run python` for backend commands.
  - **Two-docs rule:** update `docs/internal-guide.html` (changelog section, top entry) on every commit. Task 20 is the final consolidation, but add a one-line changelog entry as you go.
- **Conventional commits**, English. Commit after every task (the steps say when).

## File structure (locked decomposition)

```
frontend/
├─ index.html
├─ package.json
├─ vite.config.ts              # @vitejs/plugin-react; dev proxy /api→:8000; test config (jsdom, setup)
├─ vitest.setup.ts             # jest-dom + MSW server lifecycle
├─ playwright.config.ts        # baseURL http://localhost:5173; webServer: vite + uvicorn
├─ tailwind.config.ts          # bento/editorial tokens
├─ postcss.config.js
├─ tsconfig.json / tsconfig.node.json
├─ .env.example                # VITE_API_BASE_URL=
├─ components.json             # shadcn config
├─ src/
│  ├─ main.tsx                 # QueryClientProvider + <App/>
│  ├─ App.tsx                  # single page: <TripForm/> → <Results/>; URL load + auto-run
│  ├─ lib/
│  │  ├─ schemas.ts            # Zod: Airport, Leg, Itinerary, TripResult, TripRequest (+ inferred TS types)
│  │  ├─ api.ts                # apiBaseUrl(), getHealth, getAirports, optimize
│  │  └─ urlState.ts           # encodeTrip(trip)→URLSearchParams string ; decodeTrip(search)→TripInput|null
│  ├─ hooks/
│  │  ├─ useAirports.ts        # useQuery(['airports']) → Airport[]
│  │  └─ useOptimize.ts        # useMutation → TripResult
│  ├─ components/
│  │  ├─ trip-form/
│  │  │  ├─ TripForm.tsx
│  │  │  ├─ AirportCombobox.tsx
│  │  │  ├─ CityList.tsx
│  │  │  └─ DateFlexControls.tsx
│  │  ├─ results/
│  │  │  ├─ Results.tsx
│  │  │  ├─ RouteMap.tsx
│  │  │  ├─ ItineraryTimeline.tsx
│  │  │  ├─ CostSummary.tsx
│  │  │  └─ Alternatives.tsx
│  │  └─ ui/                   # shadcn primitives (button, command, input, popover, slider, label)
│  ├─ styles/
│  │  ├─ tokens.css
│  │  └─ global.css
│  └─ test/
│     ├─ msw-handlers.ts       # shared MSW handlers + fixtures
│     └─ render.tsx            # renderWithClient() helper (QueryClientProvider)
└─ tests/e2e/optimize.spec.ts  # Playwright happy path
```

---

## Task 1: Scaffold the frontend project

**Files:**
- Create: `frontend/` (Vite React-TS), `frontend/vite.config.ts`, `frontend/.env.example`, Tailwind + shadcn config.

- [ ] **Step 1: Scaffold Vite + install deps**

Run from repo root:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install @tanstack/react-query react-hook-form @hookform/resolvers zod react-simple-maps world-atlas
npm install -D tailwindcss postcss autoprefixer @types/react-simple-maps \
  vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event msw \
  @playwright/test
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Vite (dev proxy + vitest)**

Create `frontend/vite.config.ts`:
```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
  test: { environment: "jsdom", globals: true, setupFiles: "./vitest.setup.ts", css: true },
});
```

Create `frontend/.env.example`:
```
# Base URL for the API. Empty → use the Vite dev proxy (/api). In prod set the deployed API origin.
VITE_API_BASE_URL=
```

- [ ] **Step 3: Tailwind content globs + shadcn init**

Edit `frontend/tailwind.config.ts` `content` to `["./index.html", "./src/**/*.{ts,tsx}"]`. Add to `src/index.css` the three `@tailwind base; @tailwind components; @tailwind utilities;` lines (keep file; tokens come in Task 6). Then:
```bash
npx shadcn@latest init -d
npx shadcn@latest add button input label command popover slider
```
(Accept defaults; `-d` uses defaults. This creates `components.json`, `src/components/ui/*`, and `src/lib/utils.ts`.)

- [ ] **Step 4: Verify it builds and dev-runs**

Run: `npm run build`
Expected: build succeeds (TypeScript compiles, Vite bundles).

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend .gitignore
git commit -m "feat(frontend): scaffold Vite React-TS app with Tailwind, shadcn, test tooling"
```
(Confirm the Vite template's `.gitignore` ignores `frontend/node_modules` and `frontend/dist`; add a root-level ignore if needed.)

---

## Task 2: Add CORS to the backend

**Files:**
- Modify: `backend/tripoptimizer/api/app.py`
- Test: `backend/tests/api/test_cors.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_cors.py`:
```python
from fastapi.testclient import TestClient
from tripoptimizer.api.app import create_app


def test_cors_preflight_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:5173")
    client = TestClient(create_app())
    resp = client.options(
        "/optimize",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_cors.py -v`
Expected: FAIL (no `access-control-allow-origin` header).

- [ ] **Step 3: Implement CORS in `app.py`**

Replace `backend/tripoptimizer/api/app.py` with:
```python
"""FastAPI application assembly."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tripoptimizer.api.routes import router

DEFAULT_ORIGINS = "http://localhost:5173"


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripOptimizer API",
        version="0.1.0",
        description="Cheapest multi-city trip-ordering optimizer.",
    )
    origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_cors.py -v`
Expected: PASS. Also run `uv run pytest` to confirm no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/api/app.py backend/tests/api/test_cors.py
git commit -m "feat(api): allow configurable frontend CORS origins"
```

---

## Task 3: Zod schemas mirroring the contract

**Files:**
- Create: `frontend/src/lib/schemas.ts`
- Test: `frontend/src/lib/schemas.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/schemas.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { AirportSchema, TripResultSchema } from "./schemas";

describe("AirportSchema", () => {
  it("parses a valid airport", () => {
    const a = AirportSchema.parse({ iata: "LIS", name: "Lisbon", city: "Lisbon", country: "PT", lat: 38.7, lon: -9.1 });
    expect(a.iata).toBe("LIS");
  });
  it("rejects a missing field", () => {
    expect(() => AirportSchema.parse({ iata: "LIS" })).toThrow();
  });
});

describe("TripResultSchema", () => {
  it("parses a full result", () => {
    const r = TripResultSchema.parse({
      best: { order: ["BCN"], start_offset: 0, total: 48, legs: [
        { origin: "LIS", destination: "BCN", fly_date: "2026-07-01", price: 48, source: "cached" },
      ] },
      alternatives: [],
      data_source: "cached",
      snapshot_date: "2026-06-15",
    });
    expect(r.best.total).toBe(48);
    expect(r.data_source).toBe("cached");
  });
  it("accepts null snapshot_date", () => {
    const r = TripResultSchema.parse({
      best: { order: [], start_offset: 0, total: 0, legs: [] },
      alternatives: [], data_source: "synthetic", snapshot_date: null,
    });
    expect(r.snapshot_date).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/schemas.test.ts`
Expected: FAIL (`./schemas` not found).

- [ ] **Step 3: Implement `schemas.ts`**

Create `frontend/src/lib/schemas.ts`:
```ts
import { z } from "zod";

export const AirportSchema = z.object({
  iata: z.string(),
  name: z.string(),
  city: z.string(),
  country: z.string(),
  lat: z.number(),
  lon: z.number(),
});
export type Airport = z.infer<typeof AirportSchema>;

export const LegSchema = z.object({
  origin: z.string(),
  destination: z.string(),
  fly_date: z.string(),
  price: z.number(),
  source: z.string(),
});
export type Leg = z.infer<typeof LegSchema>;

export const ItinerarySchema = z.object({
  order: z.array(z.string()),
  start_offset: z.number(),
  legs: z.array(LegSchema),
  total: z.number(),
});
export type Itinerary = z.infer<typeof ItinerarySchema>;

export const TripResultSchema = z.object({
  best: ItinerarySchema,
  alternatives: z.array(ItinerarySchema),
  data_source: z.enum(["cached", "synthetic", "mixed"]),
  snapshot_date: z.string().nullable(),
});
export type TripResult = z.infer<typeof TripResultSchema>;

// Client-side form/request model. Mirrors the backend guardrails so requests are valid before sending.
export const TripRequestSchema = z
  .object({
    origin_airport: z.string().length(3),
    return_airport: z.string().length(3),
    cities: z.array(z.string().length(3)).min(1).max(8),
    days_per_city: z.record(z.string(), z.number().int().positive()),
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    flex_days: z.number().int().min(0).max(7),
  })
  .refine((r) => r.cities.every((c) => r.days_per_city[c] > 0), {
    message: "Every city needs days > 0",
    path: ["days_per_city"],
  });
export type TripRequest = z.infer<typeof TripRequestSchema>;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/schemas.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/lib/schemas.ts frontend/src/lib/schemas.test.ts
git commit -m "feat(frontend): add Zod schemas mirroring the API contract"
```

---

## Task 4: Typed API client

**Files:**
- Create: `frontend/src/lib/api.ts`, `frontend/src/test/msw-handlers.ts`, `frontend/vitest.setup.ts`
- Test: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Add the MSW setup + shared handlers/fixtures**

Create `frontend/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./src/test/msw-handlers";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

Create `frontend/src/test/msw-handlers.ts`:
```ts
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

export const AIRPORTS = [
  { iata: "LIS", name: "Lisbon", city: "Lisbon", country: "PT", lat: 38.77, lon: -9.13 },
  { iata: "BCN", name: "Barcelona", city: "Barcelona", country: "ES", lat: 41.3, lon: 2.08 },
  { iata: "ROM", name: "Rome FCO", city: "Rome", country: "IT", lat: 41.8, lon: 12.25 },
  { iata: "BER", name: "Berlin BER", city: "Berlin", country: "DE", lat: 52.36, lon: 13.5 },
];

export const RESULT = {
  best: {
    order: ["BCN", "ROM"], start_offset: 0, total: 214,
    legs: [
      { origin: "LIS", destination: "BCN", fly_date: "2026-07-01", price: 48, source: "cached" },
      { origin: "BCN", destination: "ROM", fly_date: "2026-07-04", price: 92, source: "cached" },
      { origin: "ROM", destination: "BER", fly_date: "2026-07-06", price: 74, source: "synthetic" },
    ],
  },
  alternatives: [
    { order: ["ROM", "BCN"], start_offset: 0, total: 251, legs: [] },
  ],
  data_source: "mixed",
  snapshot_date: "2026-06-15",
};

export const handlers = [
  http.get("*/airports", () => HttpResponse.json(AIRPORTS)),
  http.post("*/optimize", () => HttpResponse.json(RESULT)),
  http.get("*/health", () => HttpResponse.json({ status: "ok", airports_loaded: 4, snapshot_date: "2026-06-15" })),
];

export const server = setupServer(...handlers);
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/api.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { getAirports, optimize } from "./api";

describe("api client", () => {
  it("getAirports returns parsed airports", async () => {
    const airports = await getAirports();
    expect(airports).toHaveLength(4);
    expect(airports[0].iata).toBe("LIS");
  });
  it("optimize returns a parsed TripResult", async () => {
    const res = await optimize({
      origin_airport: "LIS", return_airport: "BER", cities: ["BCN", "ROM"],
      days_per_city: { BCN: 3, ROM: 2 }, start_date: "2026-07-01", flex_days: 3,
    });
    expect(res.best.total).toBe(214);
    expect(res.data_source).toBe("mixed");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/lib/api.test.ts`
Expected: FAIL (`./api` not found).

- [ ] **Step 4: Implement `api.ts`**

Create `frontend/src/lib/api.ts`:
```ts
import { AirportSchema, TripResultSchema, type Airport, type TripRequest, type TripResult } from "./schemas";
import { z } from "zod";

// Empty base URL → relative paths hit the Vite dev proxy (/api). Set VITE_API_BASE_URL in prod.
export function apiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  return base ? base.replace(/\/$/, "") : "/api";
}

async function getJson<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${apiBaseUrl()}${path}`, init);
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try { detail = (await resp.json()).detail ?? detail; } catch { /* non-JSON body */ }
    throw new Error(detail);
  }
  return schema.parse(await resp.json());
}

export function getAirports(): Promise<Airport[]> {
  return getJson("/airports", z.array(AirportSchema));
}

export function getHealth() {
  return getJson("/health", z.object({
    status: z.string(), airports_loaded: z.number(), snapshot_date: z.string().nullable(),
  }));
}

export function optimize(req: TripRequest): Promise<TripResult> {
  return getJson("/optimize?engine=bruteforce", TripResultSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/lib/api.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts frontend/src/test/msw-handlers.ts frontend/vitest.setup.ts
git commit -m "feat(frontend): typed API client with MSW-backed tests"
```

---

## Task 5: URL ⇄ trip codec

**Files:**
- Create: `frontend/src/lib/urlState.ts`
- Test: `frontend/src/lib/urlState.test.ts`

The form's working model (`TripInput`) keeps cities as an ordered list of `{ iata, days }` for ergonomics; the codec flattens it to/from URL params and to the API's `{ cities, days_per_city }` shape.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/urlState.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { encodeTrip, decodeTrip, type TripInput } from "./urlState";

const TRIP: TripInput = {
  origin_airport: "LIS", return_airport: "BER",
  cities: [{ iata: "BCN", days: 3 }, { iata: "ROM", days: 2 }],
  start_date: "2026-07-01", flex_days: 3,
};

describe("urlState", () => {
  it("round-trips a valid trip", () => {
    const decoded = decodeTrip(encodeTrip(TRIP));
    expect(decoded).toEqual(TRIP);
  });
  it("returns null for junk", () => {
    expect(decodeTrip("?from=LIS")).toBeNull();
  });
  it("returns null for empty search", () => {
    expect(decodeTrip("")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/urlState.test.ts`
Expected: FAIL (`./urlState` not found).

- [ ] **Step 3: Implement `urlState.ts`**

Create `frontend/src/lib/urlState.ts`:
```ts
export type CityInput = { iata: string; days: number };
export type TripInput = {
  origin_airport: string;
  return_airport: string;
  cities: CityInput[];
  start_date: string;
  flex_days: number;
};

// URL shape: ?from=LIS&to=BER&cities=BCN:3,ROM:2&start=2026-07-01&flex=3
export function encodeTrip(trip: TripInput): string {
  const params = new URLSearchParams({
    from: trip.origin_airport,
    to: trip.return_airport,
    cities: trip.cities.map((c) => `${c.iata}:${c.days}`).join(","),
    start: trip.start_date,
    flex: String(trip.flex_days),
  });
  return `?${params.toString()}`;
}

export function decodeTrip(search: string): TripInput | null {
  const p = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const from = p.get("from");
  const to = p.get("to");
  const citiesRaw = p.get("cities");
  const start = p.get("start");
  const flexRaw = p.get("flex");
  if (!from || !to || !citiesRaw || !start || flexRaw === null) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return null;
  const flex = Number(flexRaw);
  if (!Number.isInteger(flex) || flex < 0 || flex > 7) return null;

  const cities: CityInput[] = [];
  for (const token of citiesRaw.split(",")) {
    const [iata, daysRaw] = token.split(":");
    const days = Number(daysRaw);
    if (!iata || iata.length !== 3 || !Number.isInteger(days) || days <= 0) return null;
    cities.push({ iata, days });
  }
  if (cities.length < 1 || cities.length > 8) return null;
  return { origin_airport: from, return_airport: to, cities, start_date: start, flex_days: flex };
}

// Adapter to the API request shape.
export function toApiRequest(trip: TripInput) {
  return {
    origin_airport: trip.origin_airport,
    return_airport: trip.return_airport,
    cities: trip.cities.map((c) => c.iata),
    days_per_city: Object.fromEntries(trip.cities.map((c) => [c.iata, c.days])),
    start_date: trip.start_date,
    flex_days: trip.flex_days,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/urlState.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/lib/urlState.ts frontend/src/lib/urlState.test.ts
git commit -m "feat(frontend): URL<->trip codec with round-trip tests"
```

---

## Task 6: Design tokens (Warm Bento / Editorial)

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css`
- Modify: `frontend/tailwind.config.ts`, `frontend/src/main.tsx` (import styles)

- [ ] **Step 1: Create the token files**

Create `frontend/src/styles/tokens.css`:
```css
:root {
  --surface: #f6f1e7;
  --surface-2: #fffdf8;
  --ink: #1a1410;
  --muted: #6b6256;
  --accent: #e08a00;
  --accent-soft: #fbe9c8;
  --line: #e7ddc9;
  --radius: 14px;
  --font-display: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
```

Create `frontend/src/styles/global.css`:
```css
@import "./tokens.css";
@tailwind base;
@tailwind components;
@tailwind utilities;

body { background: var(--surface); color: var(--ink); font-family: var(--font-display); }
.tabular { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
```

- [ ] **Step 2: Wire tokens into Tailwind + import global**

Replace `frontend/tailwind.config.ts` with:
```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        line: "var(--line)",
      },
      borderRadius: { bento: "var(--radius)" },
      fontFamily: { display: "var(--font-display)", mono: "var(--font-mono)" },
    },
  },
  plugins: [],
} satisfies Config;
```

In `frontend/src/main.tsx`, replace the default `import "./index.css"` with `import "./styles/global.css"` and delete `src/index.css` and `src/App.css` if present.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/styles frontend/tailwind.config.ts frontend/src/main.tsx
git commit -m "feat(frontend): warm bento/editorial design tokens"
```

---

## Task 7: TanStack Query hooks + render helper

**Files:**
- Create: `frontend/src/hooks/useAirports.ts`, `frontend/src/hooks/useOptimize.ts`, `frontend/src/test/render.tsx`
- Modify: `frontend/src/main.tsx` (QueryClientProvider)
- Test: `frontend/src/hooks/hooks.test.tsx`

- [ ] **Step 1: Add the render helper**

Create `frontend/src/test/render.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(ui, { wrapper });
}
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/hooks/hooks.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithClient } from "../test/render";
import { useAirports } from "./useAirports";

function Probe() {
  const { data, isLoading } = useAirports();
  if (isLoading) return <p>loading</p>;
  return <p>count:{data?.length}</p>;
}

describe("useAirports", () => {
  it("loads airports from the API", async () => {
    renderWithClient(<Probe />);
    expect(await screen.findByText("count:4")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/hooks.test.tsx`
Expected: FAIL (`./useAirports` not found).

- [ ] **Step 4: Implement the hooks + provider**

Create `frontend/src/hooks/useAirports.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { getAirports } from "../lib/api";

export function useAirports() {
  return useQuery({ queryKey: ["airports"], queryFn: getAirports, staleTime: Infinity });
}
```

Create `frontend/src/hooks/useOptimize.ts`:
```ts
import { useMutation } from "@tanstack/react-query";
import { optimize } from "../lib/api";
import type { TripRequest } from "../lib/schemas";

export function useOptimize() {
  return useMutation({ mutationFn: (req: TripRequest) => optimize(req) });
}
```

Replace `frontend/src/main.tsx` with:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles/global.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
```
(If `App.tsx` from the template still has demo content, that is fine for now — Task 17 rewrites it. If the build breaks because `App.css` was deleted in Task 6, remove its import from `App.tsx`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/hooks/hooks.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/hooks frontend/src/test/render.tsx frontend/src/main.tsx
git commit -m "feat(frontend): TanStack Query hooks for airports and optimize"
```

---

## Task 8: AirportCombobox

**Files:**
- Create: `frontend/src/components/trip-form/AirportCombobox.tsx`
- Test: `frontend/src/components/trip-form/AirportCombobox.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/trip-form/AirportCombobox.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AirportCombobox } from "./AirportCombobox";
import { AIRPORTS } from "../../test/msw-handlers";

describe("AirportCombobox", () => {
  it("selects an airport and calls onChange with its IATA", async () => {
    const onChange = vi.fn();
    render(<AirportCombobox airports={AIRPORTS} value={null} onChange={onChange} label="Origin" />);
    await userEvent.click(screen.getByRole("combobox", { name: /origin/i }));
    await userEvent.click(await screen.findByText(/Barcelona/i));
    expect(onChange).toHaveBeenCalledWith("BCN");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/trip-form/AirportCombobox.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `AirportCombobox.tsx`**

Create `frontend/src/components/trip-form/AirportCombobox.tsx`:
```tsx
import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import type { Airport } from "../../lib/schemas";

type Props = {
  airports: Airport[];
  value: string | null;
  onChange: (iata: string) => void;
  label: string;
};

export function AirportCombobox({ airports, value, onChange, label }: Props) {
  const [open, setOpen] = useState(false);
  const selected = airports.find((a) => a.iata === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-label={label} className="w-full justify-between">
          {selected ? `${selected.city} (${selected.iata})` : label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0">
        <Command>
          <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          <CommandList>
            <CommandEmpty>No airport found.</CommandEmpty>
            <CommandGroup>
              {airports.map((a) => (
                <CommandItem
                  key={a.iata}
                  value={`${a.city} ${a.name} ${a.iata}`}
                  onSelect={() => { onChange(a.iata); setOpen(false); }}
                >
                  {a.city} ({a.iata}) — {a.country}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/trip-form/AirportCombobox.test.tsx`
Expected: PASS. (If the shadcn `Command`/`Popover` need `cmdk`/Radix peer deps, they were installed by `shadcn add` in Task 1.)

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/trip-form/AirportCombobox.tsx frontend/src/components/trip-form/AirportCombobox.test.tsx
git commit -m "feat(frontend): searchable airport combobox"
```

---

## Task 9: CityList (ordered cities + days)

**Files:**
- Create: `frontend/src/components/trip-form/CityList.tsx`
- Test: `frontend/src/components/trip-form/CityList.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/trip-form/CityList.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CityList } from "./CityList";

const CITIES = [{ iata: "BCN", days: 3 }, { iata: "ROM", days: 2 }];

describe("CityList", () => {
  it("renders each city with its days", () => {
    render(<CityList cities={CITIES} onChange={vi.fn()} />);
    expect(screen.getByText("BCN")).toBeInTheDocument();
    expect(screen.getByLabelText("days for BCN")).toHaveValue(3);
  });
  it("removes a city", async () => {
    const onChange = vi.fn();
    render(<CityList cities={CITIES} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "remove ROM" }));
    expect(onChange).toHaveBeenCalledWith([{ iata: "BCN", days: 3 }]);
  });
  it("changes days for a city", async () => {
    const onChange = vi.fn();
    render(<CityList cities={CITIES} onChange={onChange} />);
    const input = screen.getByLabelText("days for BCN");
    await userEvent.clear(input);
    await userEvent.type(input, "5");
    expect(onChange).toHaveBeenLastCalledWith([{ iata: "BCN", days: 5 }, { iata: "ROM", days: 2 }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/trip-form/CityList.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `CityList.tsx`**

Create `frontend/src/components/trip-form/CityList.tsx`:
```tsx
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { CityInput } from "../../lib/urlState";

type Props = { cities: CityInput[]; onChange: (cities: CityInput[]) => void };

export function CityList({ cities, onChange }: Props) {
  const setDays = (iata: string, days: number) =>
    onChange(cities.map((c) => (c.iata === iata ? { ...c, days } : c)));
  const remove = (iata: string) => onChange(cities.filter((c) => c.iata !== iata));

  return (
    <ul className="flex flex-col gap-2">
      {cities.map((c, i) => (
        <li key={c.iata} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-2">
          <span className="tabular text-muted w-6">{i + 1}.</span>
          <span className="font-medium">{c.iata}</span>
          <Input
            type="number"
            min={1}
            aria-label={`days for ${c.iata}`}
            className="w-20 tabular"
            value={c.days}
            onChange={(e) => setDays(c.iata, Number(e.target.value))}
          />
          <span className="text-muted text-sm">days</span>
          <Button variant="ghost" size="sm" className="ml-auto" aria-label={`remove ${c.iata}`} onClick={() => remove(c.iata)}>
            ✕
          </Button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/trip-form/CityList.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/trip-form/CityList.tsx frontend/src/components/trip-form/CityList.test.tsx
git commit -m "feat(frontend): city list with per-city days editing"
```

---

## Task 10: DateFlexControls

**Files:**
- Create: `frontend/src/components/trip-form/DateFlexControls.tsx`
- Test: `frontend/src/components/trip-form/DateFlexControls.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/trip-form/DateFlexControls.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DateFlexControls } from "./DateFlexControls";

describe("DateFlexControls", () => {
  it("emits the chosen start date", async () => {
    const onStartDate = vi.fn();
    render(<DateFlexControls startDate="2026-07-01" flexDays={3} onStartDate={onStartDate} onFlexDays={vi.fn()} />);
    const input = screen.getByLabelText(/start date/i);
    await userEvent.clear(input);
    await userEvent.type(input, "2026-08-15");
    expect(onStartDate).toHaveBeenLastCalledWith("2026-08-15");
  });
  it("shows the current flex value", () => {
    render(<DateFlexControls startDate="2026-07-01" flexDays={5} onStartDate={vi.fn()} onFlexDays={vi.fn()} />);
    expect(screen.getByText(/±5/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/trip-form/DateFlexControls.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `DateFlexControls.tsx`**

Create `frontend/src/components/trip-form/DateFlexControls.tsx`:
```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  startDate: string;
  flexDays: number;
  onStartDate: (d: string) => void;
  onFlexDays: (n: number) => void;
};

export function DateFlexControls({ startDate, flexDays, onStartDate, onFlexDays }: Props) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="flex flex-col gap-1">
        <Label htmlFor="start-date">Start date</Label>
        <Input id="start-date" type="date" value={startDate} onChange={(e) => onStartDate(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="flex">Flex window <span className="tabular text-accent">±{flexDays}</span></Label>
        <input
          id="flex" type="range" min={0} max={7} value={flexDays}
          onChange={(e) => onFlexDays(Number(e.target.value))}
          aria-label="flex days"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/trip-form/DateFlexControls.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/trip-form/DateFlexControls.tsx frontend/src/components/trip-form/DateFlexControls.test.tsx
git commit -m "feat(frontend): start-date and flex-window controls"
```

---

## Task 11: TripForm (compose + validate + submit)

**Files:**
- Create: `frontend/src/components/trip-form/TripForm.tsx`
- Test: `frontend/src/components/trip-form/TripForm.test.tsx`

`TripForm` is controlled by a `TripInput` value + `onChange`, plus `onSubmit(trip)`. It owns the "add city" combobox and disables submit when the trip is invalid (per `TripRequestSchema`).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/trip-form/TripForm.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithClient } from "../../test/render";
import { TripForm } from "./TripForm";
import type { TripInput } from "../../lib/urlState";

const TRIP: TripInput = {
  origin_airport: "LIS", return_airport: "BER",
  cities: [{ iata: "BCN", days: 3 }], start_date: "2026-07-01", flex_days: 3,
};

describe("TripForm", () => {
  it("submits a valid trip", async () => {
    const onSubmit = vi.fn();
    renderWithClient(<TripForm value={TRIP} onChange={vi.fn()} onSubmit={onSubmit} />);
    await userEvent.click(await screen.findByRole("button", { name: /optimize route/i }));
    expect(onSubmit).toHaveBeenCalledWith(TRIP);
  });

  it("disables submit when there are no cities", async () => {
    renderWithClient(<TripForm value={{ ...TRIP, cities: [] }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /optimize route/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/trip-form/TripForm.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `TripForm.tsx`**

Create `frontend/src/components/trip-form/TripForm.tsx`:
```tsx
import { useAirports } from "../../hooks/useAirports";
import { AirportCombobox } from "./AirportCombobox";
import { CityList } from "./CityList";
import { DateFlexControls } from "./DateFlexControls";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { TripRequestSchema } from "../../lib/schemas";
import { toApiRequest, type TripInput } from "../../lib/urlState";

type Props = {
  value: TripInput;
  onChange: (trip: TripInput) => void;
  onSubmit: (trip: TripInput) => void;
};

export function TripForm({ value, onChange, onSubmit }: Props) {
  const { data: airports = [] } = useAirports();
  const patch = (p: Partial<TripInput>) => onChange({ ...value, ...p });
  const isValid = TripRequestSchema.safeParse(toApiRequest(value)).success;

  const addCity = (iata: string) => {
    if (value.cities.some((c) => c.iata === iata)) return;
    patch({ cities: [...value.cities, { iata, days: 2 }] });
  };

  return (
    <form
      className="flex flex-col gap-5 rounded-bento border border-line bg-surface-2 p-5"
      onSubmit={(e) => { e.preventDefault(); if (isValid) onSubmit(value); }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <Label>Origin</Label>
          <AirportCombobox airports={airports} value={value.origin_airport} onChange={(i) => patch({ origin_airport: i })} label="Origin" />
        </div>
        <div className="flex flex-col gap-1">
          <Label>Return</Label>
          <AirportCombobox airports={airports} value={value.return_airport} onChange={(i) => patch({ return_airport: i })} label="Return" />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label>Destinations (in any order — we reorder for the cheapest)</Label>
        <CityList cities={value.cities} onChange={(c) => patch({ cities: c })} />
        <AirportCombobox airports={airports} value={null} onChange={addCity} label="Add a city" />
      </div>

      <DateFlexControls
        startDate={value.start_date}
        flexDays={value.flex_days}
        onStartDate={(d) => patch({ start_date: d })}
        onFlexDays={(n) => patch({ flex_days: n })}
      />

      <Button type="submit" disabled={!isValid} className="bg-accent text-ink hover:bg-accent/90">
        Optimize route
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/trip-form/TripForm.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/trip-form/TripForm.tsx frontend/src/components/trip-form/TripForm.test.tsx
git commit -m "feat(frontend): trip form composing inputs with boundary validation"
```

---

## Task 12: ItineraryTimeline (per-leg + provenance chips)

**Files:**
- Create: `frontend/src/components/results/ItineraryTimeline.tsx`
- Test: `frontend/src/components/results/ItineraryTimeline.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/ItineraryTimeline.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItineraryTimeline } from "./ItineraryTimeline";
import { RESULT } from "../../test/msw-handlers";

describe("ItineraryTimeline", () => {
  it("renders one row per leg with route, fare and source label", () => {
    render(<ItineraryTimeline legs={RESULT.best.legs} />);
    expect(screen.getByText("LIS → BCN")).toBeInTheDocument();
    expect(screen.getByText("€48")).toBeInTheDocument();
    expect(screen.getAllByText(/cached/i)).toHaveLength(2);
    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/ItineraryTimeline.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `ItineraryTimeline.tsx`**

Create `frontend/src/components/results/ItineraryTimeline.tsx`:
```tsx
import type { Leg } from "../../lib/schemas";

function SourceChip({ source }: { source: string }) {
  const cls = source === "synthetic"
    ? "bg-accent-soft text-accent"
    : "bg-line text-muted";
  return <span className={`tabular rounded-full px-2 py-0.5 text-xs ${cls}`}>{source}</span>;
}

export function ItineraryTimeline({ legs }: { legs: Leg[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {legs.map((leg, i) => (
        <li key={i} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-3">
          <span className="tabular text-muted text-sm">{leg.fly_date}</span>
          <span className="font-medium">{leg.origin} → {leg.destination}</span>
          <span className="tabular ml-auto font-semibold">€{leg.price}</span>
          <SourceChip source={leg.source} />
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/results/ItineraryTimeline.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/results/ItineraryTimeline.tsx frontend/src/components/results/ItineraryTimeline.test.tsx
git commit -m "feat(frontend): itinerary timeline with per-leg provenance chips"
```

---

## Task 13: CostSummary

**Files:**
- Create: `frontend/src/components/results/CostSummary.tsx`
- Test: `frontend/src/components/results/CostSummary.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/CostSummary.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CostSummary } from "./CostSummary";

describe("CostSummary", () => {
  it("shows total, data source and snapshot date", () => {
    render(<CostSummary total={214} dataSource="mixed" snapshotDate="2026-06-15" />);
    expect(screen.getByText("€214")).toBeInTheDocument();
    expect(screen.getByText(/mixed/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-06-15/)).toBeInTheDocument();
  });
  it("handles a null snapshot date", () => {
    render(<CostSummary total={0} dataSource="synthetic" snapshotDate={null} />);
    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/CostSummary.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `CostSummary.tsx`**

Create `frontend/src/components/results/CostSummary.tsx`:
```tsx
type Props = { total: number; dataSource: "cached" | "synthetic" | "mixed"; snapshotDate: string | null };

export function CostSummary({ total, dataSource, snapshotDate }: Props) {
  return (
    <div className="flex flex-col gap-2 rounded-bento bg-ink p-5 text-surface">
      <span className="text-sm uppercase tracking-wide text-surface/70">Cheapest total</span>
      <span className="tabular text-4xl font-bold text-accent">€{total}</span>
      <p className="text-sm text-surface/80">
        Data: <span className="tabular">{dataSource}</span>
        {snapshotDate ? <> · snapshot <span className="tabular">{snapshotDate}</span></> : null}
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/results/CostSummary.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/results/CostSummary.tsx frontend/src/components/results/CostSummary.test.tsx
git commit -m "feat(frontend): cost summary with honest data-source labels"
```

---

## Task 14: Alternatives (ranked, with Δ vs best)

**Files:**
- Create: `frontend/src/components/results/Alternatives.tsx`
- Test: `frontend/src/components/results/Alternatives.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/Alternatives.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alternatives } from "./Alternatives";
import type { Itinerary } from "../../lib/schemas";

const ALTS: Itinerary[] = [
  { order: ["ROM", "BCN"], start_offset: 0, total: 251, legs: [] },
  { order: ["BCN", "ROM"], start_offset: 1, total: 268, legs: [] },
];

describe("Alternatives", () => {
  it("lists alternatives with the delta vs the best total", () => {
    render(<Alternatives alternatives={ALTS} bestTotal={214} />);
    expect(screen.getByText(/ROM → BCN/)).toBeInTheDocument();
    expect(screen.getByText("+€37")).toBeInTheDocument(); // 251 - 214
    expect(screen.getByText("+€54")).toBeInTheDocument(); // 268 - 214
  });
  it("renders nothing when there are no alternatives", () => {
    const { container } = render(<Alternatives alternatives={[]} bestTotal={214} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/Alternatives.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `Alternatives.tsx`**

Create `frontend/src/components/results/Alternatives.tsx`:
```tsx
import type { Itinerary } from "../../lib/schemas";

type Props = { alternatives: Itinerary[]; bestTotal: number };

export function Alternatives({ alternatives, bestTotal }: Props) {
  if (alternatives.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm uppercase tracking-wide text-muted">Other orderings</h3>
      {alternatives.map((alt, i) => (
        <div key={i} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-3">
          <span className="font-medium">{alt.order.join(" → ")}</span>
          <span className="tabular ml-auto text-muted">€{alt.total}</span>
          <span className="tabular text-accent">+€{alt.total - bestTotal}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/results/Alternatives.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/results/Alternatives.tsx frontend/src/components/results/Alternatives.test.tsx
git commit -m "feat(frontend): ranked alternatives with cost delta"
```

---

## Task 15: RouteMap (keyless SVG)

**Files:**
- Create: `frontend/src/components/results/RouteMap.tsx`
- Test: `frontend/src/components/results/RouteMap.test.tsx`

Uses `react-simple-maps` with the offline `world-atlas/countries-110m.json` geography (no network, no key). Markers/lines come from joining each leg's IATA to the airport coordinate lookup.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/RouteMap.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouteMap } from "./RouteMap";
import { AIRPORTS, RESULT } from "../../test/msw-handlers";

// react-simple-maps renders SVG geographies from a topojson; stub it so the test stays unit-level.
vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: any) => <svg>{children}</svg>,
  Geographies: ({ children }: any) => <g>{children({ geographies: [] })}</g>,
  Geography: () => null,
  Line: (props: any) => <line data-testid="leg-line" {...props} />,
  Marker: ({ children }: any) => <g data-testid="marker">{children}</g>,
}));

describe("RouteMap", () => {
  it("draws a marker per distinct airport and a line per leg", () => {
    render(<RouteMap legs={RESULT.best.legs} airports={AIRPORTS} />);
    expect(screen.getAllByTestId("leg-line")).toHaveLength(RESULT.best.legs.length);
    // distinct airports in LIS→BCN→ROM→BER = 4
    expect(screen.getAllByTestId("marker")).toHaveLength(4);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/RouteMap.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `RouteMap.tsx`**

Create `frontend/src/components/results/RouteMap.tsx`:
```tsx
import { ComposableMap, Geographies, Geography, Line, Marker } from "react-simple-maps";
import geoData from "world-atlas/countries-110m.json";
import type { Airport, Leg } from "../../lib/schemas";

type Props = { legs: Leg[]; airports: Airport[] };

export function RouteMap({ legs, airports }: Props) {
  const byIata = new Map(airports.map((a) => [a.iata, a]));
  const coord = (iata: string): [number, number] | null => {
    const a = byIata.get(iata);
    return a ? [a.lon, a.lat] : null;
  };
  const distinct = Array.from(new Set(legs.flatMap((l) => [l.origin, l.destination])));

  return (
    <div className="overflow-hidden rounded-bento border border-line bg-surface-2">
      <ComposableMap projection="geoAzimuthalEqualArea" projectionConfig={{ rotate: [-10, -52, 0], scale: 700 }}>
        <Geographies geography={geoData as object}>
          {({ geographies }) =>
            geographies.map((geo: any) => (
              <Geography key={geo.rsmKey} geography={geo} fill="#efe6d4" stroke="#e7ddc9" />
            ))
          }
        </Geographies>
        {legs.map((leg, i) => {
          const from = coord(leg.origin);
          const to = coord(leg.destination);
          if (!from || !to) return null;
          return <Line key={i} from={from} to={to} stroke="#e08a00" strokeWidth={1.6} />;
        })}
        {distinct.map((iata) => {
          const c = coord(iata);
          if (!c) return null;
          return (
            <Marker key={iata} coordinates={c}>
              <circle r={3} fill="#1a1410" />
            </Marker>
          );
        })}
      </ComposableMap>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/results/RouteMap.test.tsx`
Expected: PASS.

- [ ] **Step 5: Add the TS module declaration for the JSON import (if build complains)**

If `npm run build` errors on importing `world-atlas/countries-110m.json`, create `frontend/src/world-atlas.d.ts`:
```ts
declare module "world-atlas/countries-110m.json" {
  const value: object;
  export default value;
}
```

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/components/results/RouteMap.tsx frontend/src/components/results/RouteMap.test.tsx frontend/src/world-atlas.d.ts
git commit -m "feat(frontend): keyless SVG route map"
```

---

## Task 16: Results (bento assembly)

**Files:**
- Create: `frontend/src/components/results/Results.tsx`
- Test: `frontend/src/components/results/Results.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/Results.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Results } from "./Results";
import { AIRPORTS, RESULT } from "../../test/msw-handlers";

vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: any) => <svg>{children}</svg>,
  Geographies: ({ children }: any) => <g>{children({ geographies: [] })}</g>,
  Geography: () => null,
  Line: (p: any) => <line {...p} />,
  Marker: ({ children }: any) => <g>{children}</g>,
}));

describe("Results", () => {
  it("renders the best total, timeline and alternatives", () => {
    render(<Results result={RESULT as any} airports={AIRPORTS} />);
    expect(screen.getByText("€214")).toBeInTheDocument();
    expect(screen.getByText("LIS → BCN")).toBeInTheDocument();
    expect(screen.getByText(/ROM → BCN/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/Results.test.tsx`
Expected: FAIL (component not found).

- [ ] **Step 3: Implement `Results.tsx`**

Create `frontend/src/components/results/Results.tsx`:
```tsx
import type { Airport, TripResult } from "../../lib/schemas";
import { RouteMap } from "./RouteMap";
import { ItineraryTimeline } from "./ItineraryTimeline";
import { CostSummary } from "./CostSummary";
import { Alternatives } from "./Alternatives";

type Props = { result: TripResult; airports: Airport[] };

export function Results({ result, airports }: Props) {
  return (
    <section className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
      <div className="md:row-span-2">
        <RouteMap legs={result.best.legs} airports={airports} />
      </div>
      <CostSummary total={result.best.total} dataSource={result.data_source} snapshotDate={result.snapshot_date} />
      <div className="flex flex-col gap-4 md:col-span-2">
        <ItineraryTimeline legs={result.best.legs} />
        <Alternatives alternatives={result.alternatives} bestTotal={result.best.total} />
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/results/Results.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/results/Results.tsx frontend/src/components/results/Results.test.tsx
git commit -m "feat(frontend): bento results layout"
```

---

## Task 17: App wiring (URL load + auto-run + render)

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/App.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithClient } from "./test/render";
import App from "./App";

vi.mock("react-simple-maps", () => ({
  ComposableMap: ({ children }: any) => <svg>{children}</svg>,
  Geographies: ({ children }: any) => <g>{children({ geographies: [] })}</g>,
  Geography: () => null, Line: (p: any) => <line {...p} />, Marker: ({ children }: any) => <g>{children}</g>,
}));

beforeEach(() => { window.history.replaceState({}, "", "/"); });

describe("App", () => {
  it("optimizes after the user fills the form and shows the result", async () => {
    renderWithClient(<App />);
    // pick origin
    await userEvent.click(await screen.findByRole("combobox", { name: /^origin$/i }));
    await userEvent.click(await screen.findByText(/Lisbon/i));
    // pick return
    await userEvent.click(screen.getByRole("combobox", { name: /^return$/i }));
    await userEvent.click(await screen.findByText(/Berlin/i));
    // add a city
    await userEvent.click(screen.getByRole("combobox", { name: /add a city/i }));
    await userEvent.click(await screen.findByText(/Barcelona/i));
    // set start date
    await userEvent.clear(screen.getByLabelText(/start date/i));
    await userEvent.type(screen.getByLabelText(/start date/i), "2026-07-01");
    // optimize
    await userEvent.click(screen.getByRole("button", { name: /optimize route/i }));
    expect(await screen.findByText("€214")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: FAIL (App still has template content).

- [ ] **Step 3: Implement `App.tsx`**

Replace `frontend/src/App.tsx` with:
```tsx
import { useEffect, useState } from "react";
import { TripForm } from "./components/trip-form/TripForm";
import { Results } from "./components/results/Results";
import { useAirports } from "./hooks/useAirports";
import { useOptimize } from "./hooks/useOptimize";
import { decodeTrip, encodeTrip, toApiRequest, type TripInput } from "./lib/urlState";

const EMPTY: TripInput = {
  origin_airport: "", return_airport: "", cities: [], start_date: "", flex_days: 3,
};

export default function App() {
  const { data: airports = [] } = useAirports();
  const optimize = useOptimize();
  const [trip, setTrip] = useState<TripInput>(() => decodeTrip(window.location.search) ?? EMPTY);

  const runOptimize = (t: TripInput) => {
    window.history.replaceState({}, "", encodeTrip(t));
    optimize.mutate(toApiRequest(t));
  };

  // Auto-run once if the URL carried a complete trip.
  useEffect(() => {
    if (decodeTrip(window.location.search)) runOptimize(trip);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-2">
        <span className="font-mono text-sm uppercase tracking-widest text-accent">TripOptimizer</span>
        <h1 className="text-4xl font-bold tracking-tight">Cheapest order for your multi-city trip</h1>
        <p className="text-muted">We reorder your cities and slide the dates to find the lowest total airfare.</p>
      </header>

      <TripForm value={trip} onChange={setTrip} onSubmit={runOptimize} />

      {optimize.isPending && <p className="text-muted">Optimizing…</p>}
      {optimize.isError && <p className="text-red-700">{(optimize.error as Error).message}</p>}
      {optimize.data && <Results result={optimize.data} airports={airports} />}
    </main>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/App.test.tsx`
Expected: PASS. Then run the whole suite: `npx vitest run` → all green.

- [ ] **Step 5: Verify production build**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): wire form to optimizer with shareable URL state"
```

---

## Task 18: Playwright E2E happy path

**Files:**
- Create: `frontend/playwright.config.ts`, `frontend/tests/e2e/optimize.spec.ts`

This runs against the **real backend** (snapshot + synthetic fallback) so it proves the full stack.

- [ ] **Step 1: Add Playwright config (starts both servers)**

Create `frontend/playwright.config.ts`:
```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    { command: "uv run uvicorn tripoptimizer.api.app:app --port 8000", cwd: "../backend", url: "http://localhost:8000/health", reuseExistingServer: true },
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true },
  ],
});
```

- [ ] **Step 2: Write the E2E test**

Create `frontend/tests/e2e/optimize.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("optimizes a 2-city trip end to end", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("combobox", { name: /^origin$/i }).click();
  await page.getByText(/Lisbon/i).first().click();
  await page.getByRole("combobox", { name: /^return$/i }).click();
  await page.getByText(/Berlin/i).first().click();
  await page.getByRole("combobox", { name: /add a city/i }).click();
  await page.getByText(/Barcelona/i).first().click();
  await page.getByLabel(/start date/i).fill("2026-07-01");
  await page.getByRole("button", { name: /optimize route/i }).click();

  await expect(page.getByText(/Cheapest total/i)).toBeVisible();
  await expect(page.getByText(/€\d+/).first()).toBeVisible();
  // URL became shareable
  await expect(page).toHaveURL(/cities=/);
});
```

- [ ] **Step 3: Install browsers and run**

Run: `cd frontend && npx playwright install --with-deps chromium && npx playwright test`
Expected: 1 passed. (The airport names must exist in the committed snapshot; if Lisbon/Berlin/Barcelona aren't present, substitute three cities that are — check `GET /airports`.)

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/playwright.config.ts frontend/tests/e2e/optimize.spec.ts
git commit -m "test(frontend): Playwright end-to-end optimize happy path"
```

---

## Task 19: Coverage gate + scripts

**Files:**
- Modify: `frontend/package.json` (test scripts), `frontend/vite.config.ts` (coverage)

- [ ] **Step 1: Add scripts + coverage config**

In `frontend/package.json` `scripts`, add: `"test": "vitest run"`, `"test:cov": "vitest run --coverage"`, `"e2e": "playwright test"`. Install: `npm install -D @vitest/coverage-v8`. In `vite.config.ts` `test`, add `coverage: { provider: "v8", reportsDirectory: "./coverage", exclude: ["src/components/ui/**", "src/main.tsx", "**/*.config.*", "src/test/**"], thresholds: { lines: 80, functions: 80 } }`.

- [ ] **Step 2: Run coverage**

Run: `cd frontend && npm run test:cov`
Expected: all tests pass; coverage on `src/lib`, `src/hooks`, and `src/components` (excluding shadcn `ui/*`) ≥ 80% lines/functions.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/package.json frontend/vite.config.ts
git commit -m "test(frontend): enforce 80% coverage threshold"
```

---

## Task 20: Update the internal guide (two-docs rule)

**Files:**
- Modify: `docs/internal-guide.html`

- [ ] **Step 1: Flip the Plan 4 status and add a changelog entry**

In `docs/internal-guide.html`: change the Plan 4 row status from `em andamento` to `feito` in the status table, and add a top changelog entry dated today summarizing the frontend build (scaffold → schemas/api/urlState → hooks → form components → results components → keyless map → App wiring → Playwright E2E → 80% coverage). Mention the backend CORS addition.

- [ ] **Step 2: Verify it opens**

Open `docs/internal-guide.html` in a browser; confirm the status table and changelog render and the Plan 4 entry is present.

- [ ] **Step 3: Commit**

```bash
git add docs/internal-guide.html
git commit -m "docs: mark Plan 4 frontend done in internal guide"
```

---

## Self-Review

**Spec coverage:**
- Form (origin/return/cities/days/date/flex) → Tasks 8–11. ✓
- Best itinerary timeline + provenance labels → Task 12. ✓
- Total + data_source + snapshot_date honesty → Task 13. ✓
- Ranked alternatives → Task 14. ✓
- Keyless SVG map from lat/lon → Task 15. ✓
- Shareable URL state + auto-run on load → Tasks 5 + 17. ✓
- Zod schemas mirroring contract → Task 3. ✓
- Typed API client → Task 4. ✓
- TanStack Query hooks → Task 7. ✓
- Warm Bento / Editorial tokens → Task 6. ✓
- Backend CORS → Task 2. ✓
- Tests (Vitest+RTL+MSW + 1 Playwright, ≥80%) → Tasks 3–19. ✓
- Internal guide created (done earlier) + updated each commit → Task 20 + per-commit. ✓
- Out of scope (deploy/CI/README) → left to Plan 5. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code; every command has expected output.

**Type consistency:** `TripInput`/`CityInput` (urlState) used consistently in Tasks 5, 9, 11, 17; `TripRequest`/`TripResult`/`Itinerary`/`Leg`/`Airport` (schemas) used consistently in Tasks 3, 4, 7, 12–17; `toApiRequest` defined in Task 5 and used in Tasks 11 + 17; `optimize`/`getAirports` defined in Task 4 and consumed in Task 7; `renderWithClient` defined in Task 7 and used in Tasks 11, 17; the `AirportCombobox` trigger exposes `role="combobox"` + `aria-label`, matched by selectors in Tasks 8, 11, 17, 18.

---

## Execution Handoff

Plan complete. Recommended next step: **subagent-driven execution** (fresh subagent per task + review between tasks), or inline execution with checkpoints.
