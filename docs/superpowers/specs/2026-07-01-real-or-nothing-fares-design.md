# Real-or-Nothing Fares — Design Spec

- **Date:** 2026-07-01
- **Status:** Approved (design), pending implementation plan
- **Sub-project:** #1 of the "100% real fares" program (Tier 1). Free MVP foundation.
- **Supersedes assumption:** the earlier "~62k API-call ceiling" framing — see Evidence.

## Objective

Serve **only real fares, never synthetic**. Every price shown to the user must come
from a real source (committed snapshot or live Travelpayouts), or be honestly shown
as unavailable. No fabricated numbers anywhere in the serving path.

This is Tier 1 of a larger program. It is **free** (no paid API) and is the MVP bar.

### In scope
1. Switch the live source from Travelpayouts `prices_for_dates` to `month-matrix`.
2. Remove the `SyntheticProvider` from the serving chain.
3. Make the optimizer treat a missing fare as an **infeasible itinerary**, not a crash.
4. Honest "incomplete trip" API result + UX when no fully-real itinerary exists.
5. Cleanups: remove the dead `DEMO_MODE` var; document local mode without synthetic.

### Out of scope (later sub-projects)
- Duffel / any paid live-search source (Tier 2).
- Expanding the 46-airport list; rebuilding `fares_snapshot.parquet` with month-matrix.
- Bus/train multimodal (Tier 4).

## Evidence (measured 2026-07-01)

Empirical probes against the real Travelpayouts token drove this design:

- `prices_for_dates` (endpoint used today): **31% HIT**, 69% empty, **0% throttled**
  on a 16-pair × 3-date EU sample. The wall is **coverage, not quota**.
- City-code aggregation on `prices_for_dates`: **no improvement** (still 31%).
- `month-matrix` on the same routes: **~48% of days have a real price** (16 pairs ×
  3 months), **76%+ on hub routes**, and **1 API call returns a whole month** (~30×
  fewer calls). Coverage is **bimodal** — popular routes near-full, thin routes ~empty.
- `month-matrix` record fields confirmed: `value` is **one-way** (`return_date` empty),
  EUR, with `number_of_changes` (stops) and `found_at` (freshness timestamp).

Conclusion: Travelpayouts via `month-matrix` gives ~50% real coverage for free; the
remaining gap is thin/secondary routes that need a paid live source (Tier 2, deferred).

## Design by layer

### 1. Live source — month-granular fetch

Replace the per-date provider with a month-matrix fetch that warms a whole month into
the cache per API call.

- `MonthMatrixProvider` — pure fetch. `get_month(origin, destination, month) ->
  dict[date, Fare]` calls `GET v2/prices/month-matrix` (currency=eur, market, month),
  maps each `data[]` row to a `Fare(origin, destination, depart_date, value, "EUR",
  source="travelpayouts")`. Stateless; httpx.Client injected so tests mock transport.
  Keeps the existing 429 backoff/`RateLimited` behavior.
- `CachingMonthProvider(month_source, store: FareCacheStore)` — implements
  `FareProvider.get_fare(o, d, fly_date)`:
  1. `store.get(o, d, fly_date)` → return on hit.
  2. Miss → fetch `month_source.get_month(o, d, month_of(fly_date))`, `store.put` every
     returned day, then return `store.get(o, d, fly_date)` (the requested day, or `None`
     if that day has no price).
  - An in-flight guard keyed by `(o, d, month)` prevents concurrent prefetch threads
    from double-fetching the same month. Store TTL governs staleness uniformly.

This preserves the existing durable Postgres cache (`FareCacheStore`, keyed by
`(o, d, date)`) untouched — one live call now warms ~30 cells instead of 1.

**Note:** the offline ingester (`build_snapshot.py`) keeps using the per-date
`TravelpayoutsProvider` for now; rebuilding the snapshot with month-matrix is sub-project #2.

### 2. Serving chain — remove synthetic

`dependencies.get_provider()` becomes `Cached(snapshot) → [Safe(CachingMonth) if token]`.
No `SyntheticProvider`. A full miss returns `None`. `SafeLiveProvider` still wraps the
live layer so a fetch error degrades to `None` (a miss), never a 500.

### 3. Optimizer — missing cell = infeasible itinerary

Today `runner.fare_lookup` raises `KeyError` on a `None` fare (`runner.py:20-21`); with
synthetic gone, a single missing cell would crash the whole request. Change:

- `fare_lookup(o, d, date) -> tuple[float, str] | None` returns `None` on a missing fare
  (no raise).
- `bruteforce._itinerary(...) -> Itinerary | None` returns `None` if any leg is missing.
- `search_bruteforce` builds candidates, **drops the `None` (infeasible) ones**, sorts
  the feasible remainder by total, returns cheapest + up to `MAX_ALTERNATIVES`.
- `heldkarp`: a missing edge is treated as unavailable (infinite cost) so the DP never
  selects it; if every path is blocked the engine reports no feasible result.
- If **zero** itineraries are feasible → `optimize()` returns an `IncompleteTrip`
  (see §4), not a `TripResult`.

### 4. Incomplete result (decision: option **a**)

When no fully-real itinerary exists, return an explicit incomplete result — never a
partial total, never a synthetic fill.

- New model: `@dataclass(frozen=True) class IncompleteTrip: missing_routes:
  tuple[tuple[str, str], ...]` — the `(origin, destination)` pairs that had **no fare on
  any queried date** in the window (the structural gaps that block every ordering).
- `optimize(request, provider, engine) -> TripResult | IncompleteTrip`.
- If no itinerary is feasible yet `missing_routes` is empty (only date-specific gaps),
  include all pairs whose cells were entirely missing; the message stays generic
  ("no complete real-fare route for these dates").

### 5. API schema + UX

- `aggregate_data_source` drops `"synthetic"`; a leg's source is `"cached"` (real).
- Response envelope expresses either a normal `TripResult` or an incomplete result:
  `{ "status": "ok", ... }` vs `{ "status": "incomplete", "missing_routes":
  [["MAD","DUB"], ...] }` (HTTP 200 in both cases — an incomplete answer is a valid,
  honest answer, not an error).
- Frontend renders missing routes as **"sem tarifa real disponível"**, never a number.

### 6. Cleanups (folded from A + B)

- Remove `DEMO_MODE` from `backend/.env` and from `docs/superpowers/**` (dead var — read
  by no code; superseded by the token-presence check in `live_fares_enabled()`).
- Local mode: with no token, serving = committed snapshot only (real, partial); with a
  token, live month-matrix. Document in `.env.example`. No behavior toggle is added.

## Pluggability (Tier 2 hook, not built now)

The `FallbackFareProvider` chain stays `Cached → Safe(CachingMonth) → [Duffel] → None`.
Adding Duffel later is inserting one `FareProvider` — no rewrite. Designing Tier 1 this
way costs nothing and preserves the path to ~100% coverage.

## Error handling

- Live fetch errors (429/auth/transport) → `SafeLiveProvider` logs + returns `None`
  (a miss). Serving never 500s on a source failure.
- Bad operator config (e.g. malformed `FARE_CACHE_TTL_DAYS`) keeps failing loud at
  startup (unchanged).

## Testing plan

- Update/remove tests that assert synthetic fallback behavior (testing removed code).
- `MonthMatrixProvider`: maps a mocked month-matrix payload to per-day `Fare`s; honors
  429 backoff.
- `CachingMonthProvider`: one `get_fare` miss triggers one `get_month` and populates the
  store for every returned day; second lookup in the same month is a cache hit (no 2nd
  fetch); a day absent from the payload returns `None`.
- Optimizer: infeasible itineraries are skipped; cheapest fully-real itinerary wins;
  when all orderings are infeasible, `IncompleteTrip` lists the blocking routes.
- API: incomplete result serializes to the `status: "incomplete"` envelope.

## Risks / open items

- **month-matrix freshness/price drift:** `found_at` can be days old; acceptable for MVP
  (still real observed prices). Store TTL already re-fetches stale cells.
- **Thin-route coverage stays ~0** even on month-matrix (bimodal). Expected; this is what
  Tier 2 (Duffel) would address. Tier 1 makes those gaps honest instead of synthetic.
- **In-flight month guard** must be thread-safe (prefetch fans out). Simple lock per
  `(o, d, month)` or accept rare double-fetch.
