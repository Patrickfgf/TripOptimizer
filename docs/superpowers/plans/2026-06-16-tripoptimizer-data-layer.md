# TripOptimizer Data Layer — Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the real data layer behind the existing `FareProvider` Strategy: a `TravelpayoutsProvider` (offline HTTP client), an idempotent raw→curated **Parquet** snapshot via **DuckDB**, a `CachedProvider` that reads it, and a `FallbackFareProvider` (Cached → Synthetic) — then wire the FastAPI demo to serve from the snapshot with honest per-leg provenance labels.

**Architecture:** The serving path reads a committed Parquet snapshot through DuckDB and falls back to the deterministic `SyntheticProvider` for any missing cell — the demo never calls the network. The `TravelpayoutsProvider` is used **only by the offline ingestion CLI** (raw→curated). Per-leg provenance (`Leg.source`) flows from the winning provider through the optimizer to the API response, where `data_source` is aggregated (`cached` / `synthetic` / `mixed`).

**Tech Stack:** Python 3.11+, DuckDB (snapshot read/write), httpx + tenacity (offline ingestion only), respx (test mocking), pytest + pytest-cov + ruff, uv.

**Spec:** `docs/superpowers/specs/2026-06-15-tripoptimizer-mvp-design.md` (§3.2 Travelpayouts, §3.3 snapshot-not-live, §7 fare grain, §8 graceful synthetic fallback + deep health, §12 DE framing)

---

## Context the engineer needs (read first)

- **Plan 1 core is pure and done.** Relevant frozen dataclasses (`backend/tripoptimizer/core/`):
  - `fares/models.py`: `Fare(origin, destination, fly_date: date, price: float, currency: str = "EUR", source: str = "synthetic")`.
  - `fares/base.py`: `FareProvider` Protocol — `get_fare(origin, destination, fly_date) -> Fare | None` (None = "I have no data for this leg").
  - `fares/synthetic.py`: `SyntheticProvider(airports: dict[str, Airport])` — never None for known airports; stamps `source="synthetic"`.
  - `optimizer/models.py`: `Leg(origin, destination, fly_date, price)` **← Task 5 adds `source: str`**; `Itinerary(order, start_offset, legs, total)`; `TripResult(best, alternatives)`.
  - `optimizer/runner.py`: `optimize(request, provider, engine="bruteforce")` builds a per-request `lru_cache`d `fare_lookup` and dispatches. **← Task 5 changes `fare_lookup` return type to `tuple[float, str]`.**
  - `optimizer/bruteforce.py` & `optimizer/heldkarp.py`: both build `Leg`s and define `FareLookup = Callable[[str, str, date], float]`. **← Task 5 updates both.**
- **Plan 3 API is done.** `api/dependencies.py` exposes lru-cached `get_airports()` / `get_provider()`; `api/routes.py` has `/health`, `/airports`, `/optimize` (passes `data_source="synthetic"` literal — **Task 8 replaces this**); `api/schemas.py` has `LegSchema` / `TripResultSchema.from_core(...)`.
- **Travelpayouts Data API (verified 2026-06-16, confidence high):**
  - `GET https://api.travelpayouts.com/aviasales/v3/prices_for_dates` — auth header `X-Access-Token: <token>`.
  - Key params: `origin`, `destination` (IATA), `departure_at=YYYY-MM-DD`, `one_way=true`, `direct=false`, `currency=eur` (default is **RUB** — always force it), `market=es` (default `ru` has sparse EU data — pass an EU market), `sorting=price`, `limit=1`, `token`.
  - Response envelope: `{"success": true, "data": [ {…ticket…}, … ], "error": null, "currency": "eur"}`. `data` is a **JSON array**; cheapest = `data[0]` when `sorting=price`. Ticket fields: `price` (number, EUR), `airline` (IATA str), `flight_number` (str), `departure_at` (ISO8601 w/ offset), `transfers` (int), `link` (relative path).
  - **Empty `data` (`[]`) is normal** for unsearched/old pairs — return `None`, not an error.
  - Rate limit **600 req/min**; on 429 the headers `X-Rate-Limit-Reset` (seconds to reset) / `Retry-After` are returned — back off and retry.
  - Prices are a **48h-search cache** stored up to 7 days: indicative, not live-bookable. Always label as `cached (as of snapshot_date)`.
- **Run tests from `backend/`:** `uv run pytest` (the `pyproject.toml` `addopts` injects `--cov` + `--import-mode=importlib`). Lint: `uv run ruff check .`.
- **Environment gotchas (from prior sessions):**
  - A GateGuard hook fact-forces the first Bash/Edit/Write per file (state the facts, retry).
  - A ruff `--fix` PostToolUse hook strips unused imports between edits — **add an import in the same edit that uses it.**
  - The WindowsApps `python` shim is broken (permission denied); always use `uv run python`.
  - DuckDB on Windows: in SQL string literals use forward slashes (`'C:/path/x.parquet'`); prefer a config-resolved **relative** path, never a hardcoded absolute one.

## Locked decisions (with why-X-not-Y)

- **DuckDB-only for the snapshot** (write `COPY … TO … (FORMAT parquet)`, read `read_parquet(?)` + parameterized `WHERE`). One dep does both jobs and matches spec §7/§8 + the DE narrative. *Discarded:* pyarrow + in-memory dict — slightly faster per cell and "lighter" conceptually, but discards the DuckDB angle the project exists to show and needs a second piece to write Parquet.
- **Per-leg provenance** (`Leg.source`) propagated through the optimizer; `data_source` aggregated at the top (`cached`/`synthetic`/`mixed`). *Discarded:* a single top-level constant — less honest and doesn't demonstrate data-provenance care.
- **`CachedProvider` stamps `source="cached"`** on served fares (per spec §3.2 "labeled cached (as of snapshot_date)"). The original `travelpayouts` provenance is preserved in the Parquet `source` column (ingestion provenance), distinct from the serving label.
- **Ingestion deps isolated** in an optional `[ingest]` extra (`httpx`, `tenacity`) so the serving image stays `fastapi + uvicorn + duckdb`. *Discarded:* everything in runtime deps — simpler but bloats the deploy with libs the demo never imports.
- **`TravelpayoutsProvider` takes an injected `httpx.Client`** (dependency injection) so tests mock at the transport layer with a dummy token — no real credential in CI.

## File structure (locked decomposition)

```
backend/
├─ pyproject.toml                         # MODIFY: +duckdb (runtime); +[ingest] extra (httpx,tenacity); +respx (dev)
├─ .env.example                           # MODIFY: document TRAVELPAYOUTS_MARKET
├─ data/
│  ├─ raw/                                # NEW (gitignored): raw Travelpayouts pulls — read-only source of truth
│  └─ fares_snapshot.parquet             # NEW (committed): curated snapshot
├─ tripoptimizer/
│  ├─ core/
│  │  ├─ fares/
│  │  │  ├─ cached.py                     # NEW: CachedProvider (reads snapshot via DuckDB)
│  │  │  ├─ chain.py                      # NEW: FallbackFareProvider (Cached → Synthetic)
│  │  │  └─ travelpayouts.py              # NEW: TravelpayoutsProvider (httpx, offline, retry 429)
│  │  └─ optimizer/
│  │     ├─ models.py                     # MODIFY: Leg gains `source: str`
│  │     ├─ bruteforce.py                 # MODIFY: FareLookup -> tuple[float,str]; Leg(...source)
│  │     ├─ heldkarp.py                   # MODIFY: FareLookup -> tuple[float,str]; Leg(...source)
│  │     └─ runner.py                     # MODIFY: fare_lookup returns (price, source)
│  ├─ ingestion/
│  │  ├─ __init__.py                      # NEW (empty)
│  │  ├─ snapshot.py                      # NEW: DuckDB write/read/latest-date helpers
│  │  └─ build_snapshot.py                # NEW: idempotent raw->curated CLI
│  └─ api/
│     ├─ dependencies.py                  # MODIFY: snapshot path + FallbackFareProvider + snapshot_date
│     ├─ routes.py                        # MODIFY: /health deep DuckDB; /optimize real data_source
│     └─ schemas.py                       # MODIFY: LegSchema.source; from_core derives data_source
└─ tests/
   ├─ fares/test_cached.py                # NEW
   ├─ fares/test_chain.py                 # NEW
   ├─ fares/test_travelpayouts.py         # NEW (respx, dummy token)
   ├─ ingestion/test_snapshot.py          # NEW
   ├─ ingestion/test_build_snapshot.py    # NEW (idempotency: re-run == byte-identical)
   ├─ optimizer/ (test_bruteforce, test_heldkarp, test_runner)  # MODIFY: assert leg.source
   └─ api/ (test_health, test_optimize, test_schemas)           # MODIFY: deep health, data_source
```

---

### Task 1: Add DuckDB + ingestion deps

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/.env.example`

- [ ] **Step 1: Edit `backend/pyproject.toml` deps**

Set `[project].dependencies` and the extras to:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "duckdb>=1.1",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.5", "httpx>=0.27", "respx>=0.21"]
ingest = ["httpx>=0.27", "tenacity>=9.0"]
```

- [ ] **Step 2: Document the market env var in `backend/.env.example`**

Append:

```dotenv
# Travelpayouts market (cache is market-specific; default 'ru' is sparse for EU). Use an EU market.
TRAVELPAYOUTS_MARKET=es
```

- [ ] **Step 3: Sync the environment (dev + ingest)**

Run (from `backend/`): `uv sync --extra dev --extra ingest`
Expected: resolves and installs duckdb, httpx, tenacity, respx; updates `uv.lock`.

- [ ] **Step 4: Verify imports**

Run (from `backend/`): `uv run python -c "import duckdb, httpx, tenacity, respx; print(duckdb.__version__)"`
Expected: prints a version like `1.1.x` with no ImportError.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/uv.lock
git commit -m "chore: add duckdb runtime dep and httpx/tenacity ingest extra"
```

---

### Task 2: Snapshot I/O helpers (DuckDB)

Pure data-layer module: write a typed, idempotent Parquet from row dicts; read one cell; read the snapshot date. No optimizer/API imports.

**Files:**
- Create: `backend/tripoptimizer/ingestion/__init__.py` (empty)
- Create: `backend/tripoptimizer/ingestion/snapshot.py`
- Create: `backend/tests/ingestion/__init__.py` (empty)
- Test: `backend/tests/ingestion/test_snapshot.py`

- [ ] **Step 1: Create the empty package markers**

`backend/tripoptimizer/ingestion/__init__.py` — single line:
```python
"""Offline ingestion: raw Travelpayouts pulls -> curated Parquet snapshot."""
```
`backend/tests/ingestion/__init__.py` — empty file (0 bytes).

- [ ] **Step 2: Write the failing test**

`backend/tests/ingestion/test_snapshot.py`:
```python
"""Typed, idempotent Parquet snapshot I/O over DuckDB."""

import datetime as dt
from pathlib import Path

from tripoptimizer.ingestion.snapshot import (
    latest_snapshot_date,
    read_fare_cell,
    write_snapshot,
)

SNAP = dt.date(2026, 6, 16)


def _rows() -> list[dict]:
    return [
        {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
         "price": 48.9, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP},
        {"origin": "BCN", "destination": "FCO", "fly_date": dt.date(2026, 7, 4),
         "price": 61.5, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP},
    ]


def test_write_then_read_cell(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert out.exists()
    row = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert row is not None
    price, currency, source = row
    assert price == 48.9
    assert currency == "EUR"
    assert source == "travelpayouts"


def test_read_cell_miss_returns_none(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert read_fare_cell(str(out), "LIS", "ATH", dt.date(2026, 7, 1)) is None


def test_latest_snapshot_date(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert latest_snapshot_date(str(out)) == SNAP


def test_write_is_idempotent_byte_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    # Same input, shuffled + duplicated; dedup-on-key + stable sort must yield identical bytes.
    write_snapshot(_rows(), a)
    write_snapshot(list(reversed(_rows())) + _rows(), b)
    assert a.read_bytes() == b.read_bytes()


def test_dedup_keeps_newest_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    older = {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
             "price": 99.0, "currency": "EUR", "source": "travelpayouts",
             "snapshot_date": dt.date(2026, 6, 1)}
    newer = {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
             "price": 48.9, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP}
    write_snapshot([older, newer], out)
    price, _, _ = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 48.9  # newer snapshot wins
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/ingestion/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.ingestion.snapshot`.

- [ ] **Step 4: Implement `snapshot.py`**

`backend/tripoptimizer/ingestion/snapshot.py`:
```python
"""Typed, idempotent Parquet snapshot I/O via DuckDB.

Grain: one row = origin x destination x fly_date. Writing dedups on that grain
(newest snapshot_date wins), casts explicit types (DATE, DOUBLE), and sorts by the
full key so re-running on the same input yields byte-identical Parquet.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb

# Columns/types of the curated snapshot. price MUST be cast DOUBLE (literals infer DECIMAL).
_WRITE_SQL = """
COPY (
    SELECT origin, destination,
           CAST(fly_date AS DATE)        AS fly_date,
           CAST(price AS DOUBLE)         AS price,
           currency, source,
           CAST(snapshot_date AS DATE)   AS snapshot_date
    FROM (
        SELECT *, row_number() OVER (
            PARTITION BY origin, destination, CAST(fly_date AS DATE)
            ORDER BY CAST(snapshot_date AS DATE) DESC, price ASC
        ) AS rn
        FROM raw
    )
    WHERE rn = 1
    ORDER BY origin, destination, fly_date
) TO ? (FORMAT parquet, COMPRESSION zstd)
"""

_READ_CELL_SQL = """
SELECT price, currency, source
FROM read_parquet(?)
WHERE origin = ? AND destination = ? AND fly_date = CAST(? AS DATE)
LIMIT 1
"""

_LATEST_DATE_SQL = "SELECT max(snapshot_date) FROM read_parquet(?)"


def write_snapshot(rows: list[dict], out_path: str | Path) -> None:
    """Write rows to a typed, deduped, stably-sorted Parquet (full overwrite)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.register("raw", rows)
        con.execute(_WRITE_SQL, [str(out).replace("\\", "/")])
    finally:
        con.close()


def read_fare_cell(
    parquet_path: str, origin: str, destination: str, fly_date: dt.date
) -> tuple[float, str, str] | None:
    """Return (price, currency, source) for the cell, or None on a miss."""
    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(
            _READ_CELL_SQL,
            [parquet_path.replace("\\", "/"), origin, destination, fly_date.isoformat()],
        ).fetchone()
    finally:
        con.close()
    return (row[0], row[1], row[2]) if row else None


def latest_snapshot_date(parquet_path: str) -> dt.date | None:
    """Return the newest snapshot_date in the file, or None if empty/absent."""
    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(_LATEST_DATE_SQL, [parquet_path.replace("\\", "/")]).fetchone()
    finally:
        con.close()
    return row[0] if row and row[0] is not None else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/ingestion/test_snapshot.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/ingestion/__init__.py backend/tripoptimizer/ingestion/snapshot.py backend/tests/ingestion/__init__.py backend/tests/ingestion/test_snapshot.py
git commit -m "feat: add typed idempotent DuckDB Parquet snapshot I/O"
```

---

### Task 3: CachedProvider (reads snapshot via DuckDB)

**Files:**
- Create: `backend/tripoptimizer/core/fares/cached.py`
- Test: `backend/tests/fares/test_cached.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/fares/test_cached.py`:
```python
"""CachedProvider serves fares from the committed snapshot, None on a miss."""

import datetime as dt
from pathlib import Path

from tripoptimizer.core.fares.cached import CachedProvider
from tripoptimizer.ingestion.snapshot import write_snapshot

SNAP = dt.date(2026, 6, 16)


def _snapshot(tmp_path: Path) -> Path:
    out = tmp_path / "fares.parquet"
    write_snapshot(
        [{"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
          "price": 48.9, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP}],
        out,
    )
    return out


def test_cached_hit_returns_fare_labeled_cached(tmp_path: Path) -> None:
    provider = CachedProvider(_snapshot(tmp_path))
    fare = provider.get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert fare is not None
    assert fare.price == 48.9
    assert fare.currency == "EUR"
    assert fare.source == "cached"  # serving label, not the ingestion provenance


def test_cached_miss_returns_none(tmp_path: Path) -> None:
    provider = CachedProvider(_snapshot(tmp_path))
    assert provider.get_fare("LIS", "ATH", dt.date(2026, 7, 1)) is None


def test_missing_snapshot_file_yields_all_misses(tmp_path: Path) -> None:
    provider = CachedProvider(tmp_path / "does_not_exist.parquet")
    assert provider.get_fare("LIS", "BCN", dt.date(2026, 7, 1)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/fares/test_cached.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.fares.cached`.

- [ ] **Step 3: Implement `cached.py`**

`backend/tripoptimizer/core/fares/cached.py`:
```python
"""Fare provider backed by the committed Parquet snapshot (read via DuckDB).

Returns Fare(source="cached") on a hit (the spec's serving label), or None on a
miss so a FallbackFareProvider can fall through to the synthetic source. A missing
snapshot file is treated as all-misses (not an error) — the demo still works.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.ingestion.snapshot import read_fare_cell

CACHED_SOURCE = "cached"


class CachedProvider:
    def __init__(self, snapshot_path: str | Path):
        self._path = str(snapshot_path)
        self._exists = Path(snapshot_path).is_file()

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        if not self._exists:
            return None
        cell = read_fare_cell(self._path, origin, destination, fly_date)
        if cell is None:
            return None
        price, currency, _ingestion_source = cell
        return Fare(origin, destination, fly_date, price, currency, CACHED_SOURCE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/fares/test_cached.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/fares/cached.py backend/tests/fares/test_cached.py
git commit -m "feat: add CachedProvider reading the DuckDB Parquet snapshot"
```

---

### Task 4: FallbackFareProvider (Cached → Synthetic)

**Files:**
- Create: `backend/tripoptimizer/core/fares/chain.py`
- Test: `backend/tests/fares/test_chain.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/fares/test_chain.py`:
```python
"""FallbackFareProvider tries providers in order; first non-None Fare wins."""

import datetime as dt

from tripoptimizer.core.fares.chain import FallbackFareProvider
from tripoptimizer.core.fares.models import Fare


class _Fixed:
    """A provider that returns a fixed Fare for one cell, None otherwise."""

    def __init__(self, cell, fare):
        self._cell, self._fare = cell, fare

    def get_fare(self, origin, destination, fly_date):
        return self._fare if (origin, destination, fly_date) == self._cell else None


CELL = ("LIS", "BCN", dt.date(2026, 7, 1))


def test_first_provider_wins() -> None:
    cached = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 40.0, "EUR", "cached"))
    synth = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 99.0, "EUR", "synthetic"))
    chain = FallbackFareProvider([cached, synth])
    fare = chain.get_fare(*CELL)
    assert fare.price == 40.0 and fare.source == "cached"


def test_falls_through_to_second_on_miss() -> None:
    cached = _Fixed(("X", "Y", dt.date(2026, 7, 1)), None)  # never matches CELL
    synth = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 99.0, "EUR", "synthetic"))
    chain = FallbackFareProvider([cached, synth])
    fare = chain.get_fare(*CELL)
    assert fare.price == 99.0 and fare.source == "synthetic"


def test_all_miss_returns_none() -> None:
    chain = FallbackFareProvider([_Fixed(None, None), _Fixed(None, None)])
    assert chain.get_fare(*CELL) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/fares/test_chain.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.fares.chain`.

- [ ] **Step 3: Implement `chain.py`**

`backend/tripoptimizer/core/fares/chain.py`:
```python
"""Chain-of-Responsibility fare provider. Is itself a FareProvider, so it composes
recursively and callers never learn how many sources exist. Each provider stamps
its own Fare.source, so provenance rides on the value object, not on control flow.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.fares.models import Fare


class FallbackFareProvider:
    def __init__(self, providers: Sequence[FareProvider]):
        self._providers = tuple(providers)  # immutable; order = priority

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        for provider in self._providers:
            fare = provider.get_fare(origin, destination, fly_date)
            if fare is not None:
                return fare
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/fares/test_chain.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/fares/chain.py backend/tests/fares/test_chain.py
git commit -m "feat: add FallbackFareProvider chaining cached then synthetic"
```

---

### Task 5: Per-leg provenance through the optimizer (touches Plan 1 core)

The `fare_lookup` callable now returns `(price, source)`; `Leg` gains `source`; both engines and the runner are updated. This is the only task that changes the pure core — it stays mechanical and fully covered by the existing oracle tests plus new `leg.source` assertions.

**Files:**
- Modify: `backend/tripoptimizer/core/optimizer/models.py`
- Modify: `backend/tripoptimizer/core/optimizer/runner.py`
- Modify: `backend/tripoptimizer/core/optimizer/bruteforce.py`
- Modify: `backend/tripoptimizer/core/optimizer/heldkarp.py`
- Modify: `backend/tests/optimizer/test_bruteforce.py`
- Modify: `backend/tests/optimizer/test_heldkarp.py`

- [ ] **Step 1: Add `source` to `Leg`**

In `backend/tripoptimizer/core/optimizer/models.py`, replace the `Leg` dataclass with:
```python
@dataclass(frozen=True)
class Leg:
    origin: str
    destination: str
    fly_date: date
    price: float
    source: str  # provenance of THIS leg's fare: "cached" | "synthetic" | ...
```

- [ ] **Step 2: Change the runner's `fare_lookup` to return `(price, source)`**

In `backend/tripoptimizer/core/optimizer/runner.py`, replace the inner `fare_lookup` (keep the rest of `optimize` identical):
```python
    @functools.lru_cache(maxsize=None)
    def fare_lookup(origin: str, destination: str, fly_date: date) -> tuple[float, str]:
        fare = provider.get_fare(origin, destination, fly_date)
        if fare is None:
            raise KeyError(f"no fare for {origin}->{destination} on {fly_date.isoformat()}")
        return (fare.price, fare.source)
```

- [ ] **Step 3: Update the brute-force engine**

In `backend/tripoptimizer/core/optimizer/bruteforce.py`, change the type alias and `_itinerary`:
```python
FareLookup = Callable[[str, str, date], tuple[float, str]]
```
```python
def _itinerary(
    order: tuple[str, ...],
    request: TripRequest,
    offset: int,
    fare_lookup: FareLookup,
) -> Itinerary:
    legs: list[Leg] = []
    total = 0.0
    for origin, destination, fly_date in build_legs_dates(order, request, offset):
        price, source = fare_lookup(origin, destination, fly_date)
        legs.append(Leg(origin, destination, fly_date, price, source))
        total += price
    return Itinerary(tuple(order), offset, tuple(legs), total)
```

- [ ] **Step 4: Update the Held-Karp engine**

In `backend/tripoptimizer/core/optimizer/heldkarp.py`, change the type alias and the three lookup sites. The DP only needs the price (`[0]`); the leg reconstruction needs both:
```python
FareLookup = Callable[[str, str, date], tuple[float, str]]
```
- Initial states (`for i, city in enumerate(cities)`):
```python
        dp[1 << i][i] = (fare_lookup(request.origin_airport, city, start)[0], -1)
```
- Transition (`ncost = …`):
```python
                ncost = cost + fare_lookup(cities[last], cities[nxt], fly_date)[0]
```
- Close to return (`total = …`):
```python
        total = state[0] + fare_lookup(cities[last], request.return_airport, return_date)[0]
```
- Leg reconstruction (replace the `legs = tuple(...)` comprehension and the `Itinerary(...)` return):
```python
    legs_list: list[Leg] = []
    for o, d, dt_ in build_legs_dates(order, request, offset):
        price, source = fare_lookup(o, d, dt_)
        legs_list.append(Leg(o, d, dt_, price, source))
    legs = tuple(legs_list)
    return Itinerary(order, offset, legs, sum(leg.price for leg in legs))
```

- [ ] **Step 5: Add `leg.source` assertions to the engine tests**

In `backend/tests/optimizer/test_bruteforce.py`, append:
```python
def test_legs_carry_synthetic_source() -> None:
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    assert all(leg.source == "synthetic" for leg in result.best.legs)
```
In `backend/tests/optimizer/test_heldkarp.py`, append:
```python
def test_heldkarp_legs_carry_source() -> None:
    request = TripRequest(
        cities=("BCN", "FCO"),
        days_per_city={"BCN": 2, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=1,
    )
    result = optimize(request, SyntheticProvider(AIRPORTS), engine="heldkarp")
    assert all(leg.source == "synthetic" for leg in result.best.legs)
```
(`optimize`, `TripRequest`, `SyntheticProvider`, `AIRPORTS`, and `date` are already imported in `test_heldkarp.py`.)

- [ ] **Step 6: Run the optimizer suite**

Run: `uv run pytest tests/optimizer/ -v`
Expected: PASS — the DP-vs-brute-force oracle still agrees (source doesn't affect totals) and the new source assertions pass.

- [ ] **Step 7: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/ backend/tests/optimizer/
git commit -m "feat: propagate per-leg fare source through the optimizer"
```

---

### Task 6: TravelpayoutsProvider (offline HTTP client)

Implements the `FareProvider` Protocol over `prices_for_dates`, with an **injected** `httpx.Client` (so tests mock it with a dummy token) and tenacity retry on HTTP 429. Used only by the ingestion CLI.

**Files:**
- Create: `backend/tripoptimizer/core/fares/travelpayouts.py`
- Test: `backend/tests/fares/test_travelpayouts.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/fares/test_travelpayouts.py`:
```python
"""TravelpayoutsProvider: parse prices_for_dates, force EUR, retry 429. No real token."""

import datetime as dt

import httpx
import respx

from tripoptimizer.core.fares.travelpayouts import API_URL, TravelpayoutsProvider


def _provider() -> TravelpayoutsProvider:
    return TravelpayoutsProvider(token="dummy", client=httpx.Client(), market="es")


@respx.mock
def test_parses_cheapest_from_data_array() -> None:
    respx.get(API_URL).respond(
        200,
        json={"success": True, "currency": "eur", "error": None,
              "data": [{"origin": "LIS", "destination": "BCN", "price": 48.9,
                        "airline": "TP", "flight_number": "1042",
                        "departure_at": "2026-07-01T07:00:00+01:00", "transfers": 0}]},
    )
    fare = _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert fare is not None
    assert fare.price == 48.9
    assert fare.currency == "EUR"
    assert fare.source == "travelpayouts"


@respx.mock
def test_empty_data_returns_none() -> None:
    respx.get(API_URL).respond(200, json={"success": True, "data": [], "error": None})
    assert _provider().get_fare("LIS", "ZZZ", dt.date(2026, 7, 1)) is None


@respx.mock
def test_sends_auth_header_and_forces_eur() -> None:
    route = respx.get(API_URL).respond(200, json={"success": True, "data": [], "error": None})
    _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    req = route.calls.last.request
    assert req.headers["x-access-token"] == "dummy"
    assert req.url.params["currency"] == "eur"
    assert req.url.params["market"] == "es"
    assert req.url.params["one_way"] == "true"


@respx.mock
def test_retries_on_429_then_succeeds() -> None:
    route = respx.get(API_URL).mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"success": True, "error": None,
                                  "data": [{"price": 50.0}]}),
    ])
    fare = _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert route.call_count == 2
    assert fare.price == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/fares/test_travelpayouts.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.fares.travelpayouts`.

- [ ] **Step 3: Implement `travelpayouts.py`**

`backend/tripoptimizer/core/fares/travelpayouts.py`:
```python
"""Travelpayouts/Aviasales Data API fare provider (offline ingestion only).

Calls v3/prices_for_dates for a single (origin, destination, departure date),
forcing EUR + an EU market, and returns the cheapest ticket (data[0] with
sorting=price). Retries on HTTP 429 honoring Retry-After. The httpx.Client is
INJECTED so tests mock the transport with a dummy token — no real credential.
"""

from __future__ import annotations

import datetime as dt

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from tripoptimizer.core.fares.models import Fare

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TRAVELPAYOUTS_SOURCE = "travelpayouts"
_MAX_ATTEMPTS = 4


class RateLimited(Exception):
    """Raised on HTTP 429 to trigger a tenacity retry."""


class TravelpayoutsProvider:
    def __init__(
        self,
        token: str,
        *,
        client: httpx.Client,
        market: str = "es",
        currency: str = "eur",
    ):
        self._token = token
        self._client = client
        self._market = market
        self._currency = currency

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        payload = self._fetch(origin, destination, fly_date)
        data = payload.get("data") or []
        if not data:
            return None
        price = float(data[0]["price"])
        return Fare(origin, destination, fly_date, price, "EUR", TRAVELPAYOUTS_SOURCE)

    @retry(
        retry=retry_if_exception_type(RateLimited),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_fixed(0),  # honor Retry-After server-side; fixed(0) keeps tests fast
        reraise=True,
    )
    def _fetch(self, origin: str, destination: str, fly_date: dt.date) -> dict:
        response = self._client.get(
            API_URL,
            headers={"X-Access-Token": self._token, "Accept-Encoding": "gzip, deflate"},
            params={
                "origin": origin,
                "destination": destination,
                "departure_at": fly_date.isoformat(),
                "one_way": "true",
                "direct": "false",
                "sorting": "price",
                "limit": 1,
                "currency": self._currency,
                "market": self._market,
            },
        )
        if response.status_code == 429:
            raise RateLimited()
        response.raise_for_status()
        return response.json()
```

> **Test note:** the test imports `API_URL` from the module so the route matcher and the client target the same URL. `respx.get(API_URL)` matches regardless of query params.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/fares/test_travelpayouts.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/fares/travelpayouts.py backend/tests/fares/test_travelpayouts.py
git commit -m "feat: add Travelpayouts fare provider with 429 retry (offline)"
```

---

### Task 7: Idempotent ingestion CLI (raw → curated)

A CLI that collects a configurable grid of (pair × date) fares via a provider, then transforms collected rows → curated Parquet. Re-running on the same rows yields a byte-identical snapshot. The provider is a function arg so tests inject a fake (no network).

**Files:**
- Create: `backend/tripoptimizer/ingestion/build_snapshot.py`
- Test: `backend/tests/ingestion/test_build_snapshot.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/ingestion/test_build_snapshot.py`:
```python
"""Ingestion: collect a grid via a provider, build a byte-stable curated snapshot."""

import datetime as dt
from pathlib import Path

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.ingestion.build_snapshot import collect_rows, curate
from tripoptimizer.ingestion.snapshot import read_fare_cell

SNAP = dt.date(2026, 6, 16)


class _FakeProvider:
    """Returns a deterministic fare for known pairs, None for one blacklisted pair."""

    def get_fare(self, origin, destination, fly_date):
        if (origin, destination) == ("LIS", "ZZZ"):
            return None
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_collect_rows_skips_self_pairs() -> None:
    rows = collect_rows(
        _FakeProvider(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "LIS") not in pairs  # no self-pairs
    assert ("LIS", "BCN") in pairs and ("BCN", "LIS") in pairs
    assert all(r["snapshot_date"] == SNAP for r in rows)


def test_collect_rows_skips_misses() -> None:
    rows = collect_rows(
        _FakeProvider(),
        airports=["LIS", "ZZZ"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "ZZZ") not in pairs  # provider returned None -> skipped
    assert ("ZZZ", "LIS") in pairs       # the reverse pair is not blacklisted


def test_curate_is_idempotent_byte_identical(tmp_path: Path) -> None:
    rows = collect_rows(
        _FakeProvider(), airports=["LIS", "BCN"], dates=[dt.date(2026, 7, 1)], snapshot_date=SNAP
    )
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    curate(rows, a)
    curate(rows, b)
    assert a.read_bytes() == b.read_bytes()
    price, _, source = read_fare_cell(str(a), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 50.0 and source == "travelpayouts"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ingestion/test_build_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.ingestion.build_snapshot`.

- [ ] **Step 3: Implement `build_snapshot.py`**

`backend/tripoptimizer/ingestion/build_snapshot.py`:
```python
"""Idempotent raw->curated ingestion CLI.

collect_rows() walks a grid of (origin != destination) x dates, querying a
FareProvider; misses are skipped (synthetic fallback fills them at serving time).
curate() writes the typed, deduped, stably-sorted Parquet. Re-running on the same
collected rows produces a byte-identical snapshot (the repo's idempotency rule).

Default CLI run (needs `uv sync --extra ingest` + TRAVELPAYOUTS_TOKEN in env):
    uv run python -m tripoptimizer.ingestion.build_snapshot \
        --airports LIS OPO MAD BCN CDG FCO BER ATH \
        --start 2026-07-01 --days 10 \
        --out data/fares_snapshot.parquet
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from itertools import permutations
from pathlib import Path

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.ingestion.snapshot import write_snapshot


def collect_rows(
    provider: FareProvider,
    airports: list[str],
    dates: list[dt.date],
    snapshot_date: dt.date,
) -> list[dict]:
    rows: list[dict] = []
    for origin, destination in permutations(airports, 2):
        for fly_date in dates:
            fare = provider.get_fare(origin, destination, fly_date)
            if fare is None:
                continue
            rows.append({
                "origin": fare.origin,
                "destination": fare.destination,
                "fly_date": fare.fly_date,
                "price": fare.price,
                "currency": fare.currency,
                "source": fare.source,
                "snapshot_date": snapshot_date,
            })
    return rows


def curate(rows: list[dict], out_path: str | Path) -> None:
    """Write the curated snapshot (dedup + stable sort + typed, via DuckDB)."""
    write_snapshot(rows, out_path)


def _date_window(start: dt.date, days: int) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(days)]


def _build_provider() -> FareProvider:
    import httpx

    from tripoptimizer.core.fares.travelpayouts import TravelpayoutsProvider

    token = os.environ["TRAVELPAYOUTS_TOKEN"]  # KeyError if absent — fail fast
    market = os.environ.get("TRAVELPAYOUTS_MARKET", "es")
    return TravelpayoutsProvider(token, client=httpx.Client(timeout=20.0), market=market)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the curated fares snapshot.")
    parser.add_argument("--airports", nargs="+", required=True)
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    provider = _build_provider()
    today = dt.datetime.now().date()
    rows = collect_rows(provider, args.airports, _date_window(args.start, args.days), today)
    curate(rows, args.out)
    print(f"wrote {len(rows)} fares to {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ingestion/test_build_snapshot.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/ingestion/build_snapshot.py backend/tests/ingestion/test_build_snapshot.py
git commit -m "feat: add idempotent raw->curated ingestion CLI"
```

---

### Task 8: Wire the API to the snapshot + honest provenance

Swap the serving provider to `FallbackFareProvider(Cached → Synthetic)`, make `/health` deep-check the DuckDB store, and derive `data_source` + `snapshot_date` from the result instead of the `"synthetic"` literal.

**Files:**
- Modify: `backend/tripoptimizer/api/dependencies.py`
- Modify: `backend/tripoptimizer/api/schemas.py`
- Modify: `backend/tripoptimizer/api/routes.py`
- Create: `backend/tests/api/conftest.py` (snapshot isolation)
- Modify: `backend/tests/api/test_schemas.py`
- Modify: `backend/tests/api/test_health.py`
- Modify: `backend/tests/api/test_optimize.py`

- [ ] **Step 1: Extend dependencies (snapshot path + fallback provider + snapshot date)**

Replace `backend/tripoptimizer/api/dependencies.py` with:
```python
"""Process-wide singletons for the API: airports, fare provider, snapshot metadata.

The serving provider is a FallbackFareProvider(Cached -> Synthetic): real cached
fares when present, deterministic synthetic otherwise, so the demo never fails.
Paths resolve from the committed data dir or env overrides (no hardcoded absolutes).
"""

import datetime as dt
import functools
import os
from pathlib import Path

from tripoptimizer.core.fares.cached import CachedProvider
from tripoptimizer.core.fares.chain import FallbackFareProvider
from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.graph.airports import Airport, load_airports
from tripoptimizer.ingestion.snapshot import latest_snapshot_date

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_AIRPORTS_CSV = _DATA_DIR / "airports_sample.csv"
_DEFAULT_SNAPSHOT = _DATA_DIR / "fares_snapshot.parquet"


def _airports_csv_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_AIRPORTS_CSV")
    return Path(override) if override else _DEFAULT_AIRPORTS_CSV


def _snapshot_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_SNAPSHOT")
    return Path(override) if override else _DEFAULT_SNAPSHOT


@functools.lru_cache(maxsize=1)
def get_airports() -> dict[str, Airport]:
    return load_airports(_airports_csv_path())


@functools.lru_cache(maxsize=1)
def get_provider() -> FallbackFareProvider:
    return FallbackFareProvider([
        CachedProvider(_snapshot_path()),
        SyntheticProvider(get_airports()),
    ])


@functools.lru_cache(maxsize=1)
def get_snapshot_date() -> dt.date | None:
    path = _snapshot_path()
    return latest_snapshot_date(str(path)) if path.is_file() else None
```

- [ ] **Step 2: Derive `data_source` in schemas + add `LegSchema.source`**

In `backend/tripoptimizer/api/schemas.py`: add `source: str` to `LegSchema`, pass it in `ItinerarySchema.from_core`, and add a `data_source` aggregator.

`LegSchema`:
```python
class LegSchema(BaseModel):
    origin: str
    destination: str
    fly_date: date
    price: float
    source: str
```
In `ItinerarySchema.from_core`, each `LegSchema(...)` gains `source=leg.source`:
```python
                LegSchema(
                    origin=leg.origin,
                    destination=leg.destination,
                    fly_date=leg.fly_date,
                    price=leg.price,
                    source=leg.source,
                )
```
Add a module-level helper (after the `MAX_FLEX_DAYS` constant):
```python
def aggregate_data_source(itinerary: Itinerary) -> str:
    """cached / synthetic when uniform across legs, else 'mixed'."""
    sources = {leg.source for leg in itinerary.legs}
    return next(iter(sources)) if len(sources) == 1 else "mixed"
```
Change `TripResultSchema.from_core` to default `data_source` from the best itinerary when not provided:
```python
    @classmethod
    def from_core(
        cls,
        result: TripResult,
        *,
        data_source: str | None = None,
        snapshot_date: date | None = None,
    ) -> "TripResultSchema":
        return cls(
            best=ItinerarySchema.from_core(result.best),
            alternatives=[ItinerarySchema.from_core(it) for it in result.alternatives],
            data_source=data_source or aggregate_data_source(result.best),
            snapshot_date=snapshot_date,
        )
```

- [ ] **Step 3: Deep `/health` + real `data_source`/`snapshot_date` in routes**

In `backend/tripoptimizer/api/routes.py`, update the import line and the two endpoints:
```python
from tripoptimizer.api.dependencies import (
    get_airports,
    get_provider,
    get_snapshot_date,
)
```
`/health` (deep-check that the snapshot store is queryable):
```python
@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + deep check: reference data loaded and the snapshot store queryable."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    try:
        snapshot_date = get_snapshot_date()  # touches the DuckDB store (None if no snapshot)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail="fare snapshot store unavailable") from exc
    return {
        "status": "ok",
        "airports_loaded": len(airports),
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
    }
```
`/optimize` (drop the `"synthetic"` literal; let `from_core` aggregate + attach `snapshot_date`):
```python
    result = optimize(trip, get_provider(), engine=engine)
    return TripResultSchema.from_core(result, snapshot_date=get_snapshot_date())
```

- [ ] **Step 4: Isolate API tests from the committed snapshot**

So API tests stay deterministic whether or not a snapshot is committed, create `backend/tests/api/conftest.py`:
```python
"""Point the API at a non-existent snapshot so tests see synthetic-only fallback,
regardless of any committed data/fares_snapshot.parquet."""

import pytest

from tripoptimizer.api import dependencies


@pytest.fixture(autouse=True)
def _no_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIPOPTIMIZER_SNAPSHOT", str(tmp_path / "absent.parquet"))
    dependencies.get_provider.cache_clear()
    dependencies.get_snapshot_date.cache_clear()
    yield
    dependencies.get_provider.cache_clear()
    dependencies.get_snapshot_date.cache_clear()
```

- [ ] **Step 5: Update affected tests**

In `backend/tests/api/test_schemas.py`, the hand-built `Leg(...)` calls now need a `source`; and the result now auto-aggregates `data_source`. Replace the legs tuple and assertions in `test_trip_result_from_core_serializes`:
```python
        legs=(
            Leg("LIS", "BCN", date(2026, 7, 1), 50.0, "cached"),
            Leg("BCN", "CDG", date(2026, 7, 3), 60.0, "cached"),
            Leg("CDG", "LIS", date(2026, 7, 6), 70.0, "synthetic"),
        ),
```
```python
    core = TripResult(best=best, alternatives=())
    out = TripResultSchema.from_core(core)  # data_source auto-derived
    assert out.data_source == "mixed"       # cached + synthetic legs
    assert out.best.legs[0].source == "cached"
    assert out.best.legs[0].fly_date == date(2026, 7, 1)
    assert out.best.legs[0].price == 50.0
    assert out.alternatives == []
```
In `backend/tests/api/test_health.py`, allow the new field:
```python
def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["airports_loaded"] >= 8
    assert "snapshot_date" in body  # None when no snapshot committed yet
```
In `backend/tests/api/test_optimize.py`, the conftest forces synthetic-only, so update `test_optimize_happy_path`:
```python
    assert body["data_source"] == "synthetic"  # conftest points at an absent snapshot
    assert body["snapshot_date"] is None
    assert all(leg["source"] == "synthetic" for leg in best["legs"])
```

- [ ] **Step 6: Run the API + schema suites**

Run: `uv run pytest tests/api/ -v`
Expected: PASS (health, airports, optimize, schemas, dependencies).

- [ ] **Step 7: Commit**

```bash
git add backend/tripoptimizer/api/ backend/tests/api/
git commit -m "feat: serve from snapshot with fallback + per-leg provenance; deep health"
```

---

### Task 9: Run the real ingestion + commit the snapshot

**Requires:** `TRAVELPAYOUTS_TOKEN` in `backend/.env` (free, instant: travelpayouts.com → Profile → API token). This task is the only one that needs the token; everything above is testable without it.

**Files:**
- Modify: `backend/.gitignore` (ignore `data/raw/`)
- Create (committed): `backend/data/fares_snapshot.parquet`

- [ ] **Step 1: Ignore raw pulls**

Append to `backend/.gitignore`:
```gitignore
data/raw/
```

- [ ] **Step 2: Confirm the token is loaded**

Run (from `backend/`): `uv run python -c "import os; print('TOKEN set:', bool(os.environ.get('TRAVELPAYOUTS_TOKEN')))"`
(If using a `.env`, export the var in the shell first, e.g. via `set -a; . ./.env; set +a` in bash.)
Expected: `TOKEN set: True`.

- [ ] **Step 3: Run the ingestion over the 8 sample EU airports**

Run (from `backend/`):
```bash
uv run python -m tripoptimizer.ingestion.build_snapshot \
    --airports LIS OPO MAD BCN CDG FCO BER ATH \
    --start 2026-07-01 --days 10 \
    --out data/fares_snapshot.parquet
```
Expected: prints `wrote N fares to data/fares_snapshot.parquet` (N up to 8·7·10=560; fewer if some pairs have no cached data — expected, synthetic fills them at serving time). Stays under 600 req/min.

- [ ] **Step 4: Sanity-check the snapshot**

Run (from `backend/`):
```bash
uv run python -c "from tripoptimizer.ingestion.snapshot import latest_snapshot_date; print(latest_snapshot_date('data/fares_snapshot.parquet'))"
```
Expected: prints today's date.

- [ ] **Step 5: Verify the API serves cached fares (manual smoke)**

Run (from `backend/`): `uv run uvicorn tripoptimizer.api.app:app --port 8000`, then in another shell:
```bash
curl -s -X POST localhost:8000/optimize -H 'content-type: application/json' \
  -d '{"cities":["BCN","CDG","FCO"],"days_per_city":{"BCN":2,"CDG":2,"FCO":3},"origin_airport":"LIS","return_airport":"LIS","start_date":"2026-07-01","flex_days":2}'
```
Expected: `data_source` is `cached` or `mixed` (some legs from the snapshot), `snapshot_date` populated. Stop the server with Ctrl+C. (Note: the `tests/api/conftest.py` fixture keeps the automated suite on synthetic-only regardless of this committed snapshot.)

- [ ] **Step 6: Commit the snapshot**

```bash
git add backend/.gitignore backend/data/fares_snapshot.parquet
git commit -m "data: commit curated Travelpayouts fares snapshot (EU sample, EUR)"
```

---

### Task 10: Full-suite gate (coverage + lint)

**Files:** none (verification only).

- [ ] **Step 1: Whole suite with coverage**

Run (from `backend/`): `uv run pytest`
Expected: all tests pass; total coverage ≥ 80% (the project has been ~99%). Add focused tests for any uncovered `cached.py` / `chain.py` / `travelpayouts.py` / `snapshot.py` / `build_snapshot.py` line.

- [ ] **Step 2: Lint**

Run (from `backend/`): `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Push the branch**

```bash
git push origin feat/backend-foundation
```

---

## Self-Review

**1. Spec coverage (Plan 2's slice):**
- §3.2 Travelpayouts provider (token header, force EUR, prices_for_dates, retry/backoff): Task 6. ✓
- §3.3 snapshot-not-live + idempotent ingestion (raw→curated, re-run = same): Tasks 2, 7 (byte-identical tests). ✓
- §3.2 `CachedProvider` + graceful synthetic fallback: Tasks 3, 4, 8. ✓
- §7 fare grain (origin×destination×fly_date) + Parquet/DuckDB persistence: Tasks 2, 9. ✓
- §8 deep `/health` touching the store; missing cell → synthetic; labeled `data_source`: Task 8. ✓
- §12 DE framing (raw→curated, Parquet/DuckDB, provider swap, deep health): Tasks 2–9. ✓
- Out of this slice (correct, not gaps): frontend (Plan 4), CI + deploy + docs (Plan 5), EDA notebook (Plan 4/5, needs this snapshot).

**2. Placeholder scan:** No "TBD/handle later". Task 9's note about the committed snapshot is resolved by the Task 8 conftest fixture, not left open.

**3. Type consistency:** `fare_lookup: Callable[[str,str,date], tuple[float,str]]` used identically in `runner` (returns `(fare.price, fare.source)`), `bruteforce` (`price, source = fare_lookup(...)`), `heldkarp` (`[0]` in the DP, unpack in reconstruction). `Leg(origin, destination, fly_date, price, source)` consistent across engines + `schemas.LegSchema(..., source=leg.source)`. `Fare(origin, destination, fly_date, price, currency, source)` consistent in `cached`/`travelpayouts`/`synthetic`. `read_fare_cell -> tuple[float,str,str] | None` consumed in `cached`. `write_snapshot(rows, path)` / `curate(rows, path)` / `collect_rows(provider, airports, dates, snapshot_date)` signatures match their tests.

**4. Open follow-up (decide at handoff, not silently):** Task 9 commits a binary Parquet to git — at hundreds of rows it's a few KB (fine), but review it via regenerate-and-compare, not line diff. If Patrick prefers zero binaries in git, the alternative is a CI/ingestion step that regenerates it — defer to Plan 5 (deploy).

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task + two-stage review (the method used for Plan 3).
2. **Inline Execution** — execute tasks in this session with checkpoints for review (the cheap fallback if subagent dispatch flakes, per the prior-session note).

Note: Tasks 1–8 + 10 need no token; **Task 9 is gated on `TRAVELPAYOUTS_TOKEN`** and can run last, once the token is in `backend/.env`.
