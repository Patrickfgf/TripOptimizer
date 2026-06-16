# TripOptimizer FastAPI Layer — Implementation Plan (Plan 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the pure optimizer core over a FastAPI HTTP boundary with three endpoints (`POST /optimize`, `GET /airports`, `GET /health`), wired to the no-key `SyntheticProvider`, so the project has a runnable end-to-end demo.

**Architecture:** A new `tripoptimizer/api/` package adds the HTTP edge only — the `core/` package stays pure (no FastAPI/Pydantic import in core). Pydantic schemas at the boundary validate input (enforcing the spec guardrails: ≤8 cities, `flex_days` ≤ 7) and serialize the core's frozen dataclasses to JSON. `POST /optimize` defaults to the brute-force engine (returns `best` + up to 5 ranked `alternatives`); `?engine=heldkarp` selects the exact best-only DP path. A per-request memoization wrapper around the fare lookup keeps brute-force fast at the 8-city cap.

**Tech Stack:** FastAPI, Pydantic v2, Starlette `TestClient` (httpx), uvicorn, pytest, ruff, uv.

---

## Context the engineer needs (read first)

- **Core is pure and already done (Plan 1).** Do not change its public behavior. The relevant frozen dataclasses live in `backend/tripoptimizer/core/optimizer/models.py`:
  - `TripRequest(cities: tuple[str,...], days_per_city: Mapping[str,int], origin_airport: str, return_airport: str, start_date: date, flex_days: int = 3)` — validates in `__post_init__` (non-empty cities, `flex_days >= 0`, `days_per_city` covers cities, days > 0). It does **NOT** enforce max-8-cities or `flex_days <= 7` — those are demo guardrails added at the API boundary.
  - `Leg(origin, destination, fly_date: date, price: float)` — note the field names are `fly_date` and `price` (not `date`/`fare`).
  - `Itinerary(order: tuple[str,...], start_offset: int, legs: tuple[Leg,...], total: float)`.
  - `TripResult(best: Itinerary, alternatives: tuple[Itinerary,...])`.
- **Engines** (`backend/tripoptimizer/core/optimizer/`):
  - `bruteforce.search_bruteforce(request, fare_lookup) -> TripResult` returns `best` + up to `MAX_ALTERNATIVES` (= 5) ranked alternatives.
  - `heldkarp.search_heldkarp(request, fare_lookup) -> TripResult` returns `best` + `alternatives=()` (exact, no runners-up).
  - `runner.optimize(request, provider, engine="bruteforce") -> TripResult` builds the `fare_lookup` from any `FareProvider` and dispatches by engine string.
- **Provider** (`backend/tripoptimizer/core/fares/`): `SyntheticProvider(airports: dict[str, Airport])` implements `get_fare(origin, destination, fly_date) -> Fare | None` (None for unknown IATA). `Fare` has `.price` and `.source == "synthetic"`.
- **Airports** (`backend/tripoptimizer/core/graph/airports.py`): `Airport(iata, name, city, country, lat, lon)` frozen dataclass; `load_airports(path) -> dict[str, Airport]`. Sample data at `backend/data/airports_sample.csv` (8 EU airports: LIS, OPO, MAD, BCN, CDG, FCO, BER, ATH).
- **Run tests from `backend/`:** `uv run pytest` (the `pyproject.toml` `addopts` already injects `--cov`). Lint: `uv run ruff check .`.
- **Environment gotcha:** a ruff `--fix` PostToolUse hook strips unused imports between edits. Always add an import in the **same edit** that uses it, or it gets removed before the next step.

## File structure (locked decomposition)

```
backend/
├─ pyproject.toml                         # MODIFY: add fastapi, uvicorn[standard]; dev: httpx
├─ tripoptimizer/
│  ├─ core/optimizer/runner.py            # MODIFY: memoize the per-request fare_lookup
│  └─ api/                                # NEW package — the HTTP edge
│     ├─ __init__.py                      # empty
│     ├─ schemas.py                       # Pydantic request/response models + from_core converters
│     ├─ dependencies.py                  # cached airports dict + SyntheticProvider singletons
│     ├─ routes.py                        # APIRouter: /health, /airports, /optimize
│     └─ app.py                           # create_app() factory + module-level `app`
└─ tests/api/
   ├─ __init__.py                         # empty
   ├─ test_schemas.py
   ├─ test_dependencies.py
   ├─ test_health.py
   ├─ test_airports.py
   └─ test_optimize.py
```

**Why this split:** `schemas` (serialization contract), `dependencies` (data/provider wiring + caching), `routes` (HTTP orchestration), `app` (assembly) each have one responsibility and stay small. `core/` is untouched except a benign perf wrapper in `runner`.

**Deferred (out of scope for Plan 3, noted so nobody adds it now):** CORS middleware (Plan 4 knows the real frontend origins), DuckDB-deep `/health` (no DuckDB until Plan 2 — `/health` touches the only data layer that exists: airport reference data), `data_source` derivation per-leg (constant `"synthetic"` until the cached provider lands in Plan 2).

---

### Task 1: Add API dependencies to the project

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add runtime + test deps**

In `backend/pyproject.toml`, change the `dependencies` and `dev` extras:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.5", "httpx>=0.27"]
```

- [ ] **Step 2: Sync the environment**

Run (from `backend/`): `uv sync --extra dev`
Expected: resolves and installs fastapi, starlette, uvicorn, httpx; updates `uv.lock`.

- [ ] **Step 3: Verify the import works**

Run (from `backend/`): `uv run python -c "import fastapi, httpx, uvicorn; print(fastapi.__version__)"`
Expected: prints a version like `0.115.x` with no ImportError.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add fastapi, uvicorn, httpx deps for the API layer"
```

---

### Task 2: Memoize the per-request fare lookup in the runner

Brute-force queries the same `(origin, destination, fly_date)` cell across many permutations. A per-request `lru_cache` collapses those to one provider call each, keeping the 8-city worst case fast. The cache is created fresh inside `optimize` (per request), so it never leaks across requests and stays correct for any provider.

**Files:**
- Modify: `backend/tripoptimizer/core/optimizer/runner.py`
- Test: `backend/tests/optimizer/test_runner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/optimizer/test_runner.py`:

```python
"""The runner memoizes fare lookups within a single optimize() call."""

from datetime import date

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize


class CountingProvider:
    """Counts how many times the underlying fare source is hit."""

    def __init__(self) -> None:
        self.calls = 0

    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare:
        self.calls += 1
        return Fare(origin, destination, fly_date, price=100.0)


def test_optimize_memoizes_repeated_fare_cells() -> None:
    request = TripRequest(
        cities=("BCN", "CDG", "FCO"),
        days_per_city={"BCN": 2, "CDG": 2, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=1,
    )
    counting = CountingProvider()
    naive = CountingProvider()

    # Run the real (memoized) optimizer.
    optimize(request, counting, engine="bruteforce")

    # Count distinct cells by replaying every lookup the search would make.
    from tripoptimizer.core.optimizer.bruteforce import search_bruteforce

    seen: set[tuple[str, str, str]] = set()

    def record(origin: str, destination: str, fly_date: date) -> float:
        seen.add((origin, destination, fly_date.isoformat()))
        naive.get_fare(origin, destination, fly_date)
        return 100.0

    search_bruteforce(request, record)

    assert counting.calls == len(seen)
    assert counting.calls < naive.calls  # memoization actually saved calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/optimizer/test_runner.py -v`
Expected: FAIL — `counting.calls` equals `naive.calls` (no memoization yet), so `counting.calls < naive.calls` is False.

- [ ] **Step 3: Wrap the fare lookup in an lru_cache**

Replace the body of `backend/tripoptimizer/core/optimizer/runner.py` with:

```python
"""Thin orchestrator: build a memoized fare_lookup from a FareProvider, run an engine."""

import functools
from datetime import date

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.optimizer.bruteforce import search_bruteforce
from tripoptimizer.core.optimizer.heldkarp import search_heldkarp
from tripoptimizer.core.optimizer.models import TripRequest, TripResult


def optimize(
    request: TripRequest, provider: FareProvider, engine: str = "bruteforce"
) -> TripResult:
    # Per-request cache: the same (origin, dest, date) cell recurs across
    # permutations and offsets; memoizing collapses those to one provider call.
    @functools.lru_cache(maxsize=None)
    def fare_lookup(origin: str, destination: str, fly_date: date) -> float:
        fare = provider.get_fare(origin, destination, fly_date)
        if fare is None:
            raise KeyError(f"no fare for {origin}->{destination} on {fly_date.isoformat()}")
        return fare.price

    if engine == "heldkarp":
        return search_heldkarp(request, fare_lookup)
    return search_bruteforce(request, fare_lookup)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/optimizer/ -v`
Expected: PASS (new memoization test + all existing optimizer tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/runner.py backend/tests/optimizer/test_runner.py
git commit -m "perf: memoize per-request fare lookups in the optimizer runner"
```

---

### Task 3: Pydantic schemas (request validation + response serialization)

**Files:**
- Create: `backend/tripoptimizer/api/__init__.py` (empty)
- Create: `backend/tripoptimizer/api/schemas.py`
- Create: `backend/tests/api/__init__.py` (empty)
- Test: `backend/tests/api/test_schemas.py`

- [ ] **Step 1: Create the empty package markers**

Create `backend/tripoptimizer/api/__init__.py` with a single line:

```python
"""HTTP edge for TripOptimizer (FastAPI)."""
```

Create `backend/tests/api/__init__.py` as an empty file (0 bytes).

- [ ] **Step 2: Write the failing test**

Create `backend/tests/api/test_schemas.py`:

```python
"""Boundary validation and core->schema conversion."""

from datetime import date

import pytest
from pydantic import ValidationError

from tripoptimizer.api.schemas import (
    MAX_CITIES,
    MAX_FLEX_DAYS,
    TripRequestSchema,
    TripResultSchema,
)
from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripResult


def _valid_payload() -> dict:
    return {
        "cities": ["BCN", "CDG"],
        "days_per_city": {"BCN": 2, "CDG": 3},
        "origin_airport": "LIS",
        "return_airport": "LIS",
        "start_date": "2026-07-01",
        "flex_days": 2,
    }


def test_valid_request_parses() -> None:
    req = TripRequestSchema(**_valid_payload())
    assert req.cities == ["BCN", "CDG"]
    assert req.flex_days == 2


def test_rejects_more_than_max_cities() -> None:
    payload = _valid_payload()
    payload["cities"] = [f"C{i:02d}" for i in range(MAX_CITIES + 1)]
    payload["days_per_city"] = {c: 1 for c in payload["cities"]}
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_flex_days_over_cap() -> None:
    payload = _valid_payload()
    payload["flex_days"] = MAX_FLEX_DAYS + 1
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_missing_days_for_a_city() -> None:
    payload = _valid_payload()
    payload["days_per_city"] = {"BCN": 2}  # CDG missing
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_non_positive_days() -> None:
    payload = _valid_payload()
    payload["days_per_city"] = {"BCN": 2, "CDG": 0}
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_trip_result_from_core_serializes() -> None:
    best = Itinerary(
        order=("BCN", "CDG"),
        start_offset=0,
        legs=(
            Leg("LIS", "BCN", date(2026, 7, 1), 50.0),
            Leg("BCN", "CDG", date(2026, 7, 3), 60.0),
            Leg("CDG", "LIS", date(2026, 7, 6), 70.0),
        ),
        total=180.0,
    )
    core = TripResult(best=best, alternatives=())
    out = TripResultSchema.from_core(core, data_source="synthetic")

    assert out.data_source == "synthetic"
    assert out.snapshot_date is None
    assert out.best.total == 180.0
    assert out.best.legs[0].fly_date == date(2026, 7, 1)
    assert out.best.legs[0].price == 50.0
    assert out.alternatives == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/api/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.api.schemas`.

- [ ] **Step 4: Implement the schemas**

Create `backend/tripoptimizer/api/schemas.py`:

```python
"""Pydantic models for the HTTP boundary.

Request validation here enforces the MVP guardrails the pure core deliberately
omits (max cities, flex cap). Response models serialize the core's frozen
dataclasses to JSON via ``from_core`` converters, keeping the core Pydantic-free.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from tripoptimizer.core.optimizer.models import Itinerary, TripResult

MAX_CITIES = 8
MAX_FLEX_DAYS = 7


class TripRequestSchema(BaseModel):
    cities: list[str] = Field(..., min_length=1, max_length=MAX_CITIES)
    days_per_city: dict[str, int]
    origin_airport: str
    return_airport: str
    start_date: date
    flex_days: int = Field(default=3, ge=0, le=MAX_FLEX_DAYS)

    @model_validator(mode="after")
    def _days_cover_cities(self) -> "TripRequestSchema":
        missing = [c for c in self.cities if c not in self.days_per_city]
        if missing:
            raise ValueError(f"days_per_city is missing entries for: {sorted(missing)}")
        for city in self.cities:
            if self.days_per_city[city] <= 0:
                raise ValueError(f"days_per_city[{city!r}] must be > 0")
        return self


class LegSchema(BaseModel):
    origin: str
    destination: str
    fly_date: date
    price: float


class ItinerarySchema(BaseModel):
    order: list[str]
    start_offset: int
    legs: list[LegSchema]
    total: float

    @classmethod
    def from_core(cls, itinerary: Itinerary) -> "ItinerarySchema":
        return cls(
            order=list(itinerary.order),
            start_offset=itinerary.start_offset,
            legs=[
                LegSchema(
                    origin=leg.origin,
                    destination=leg.destination,
                    fly_date=leg.fly_date,
                    price=leg.price,
                )
                for leg in itinerary.legs
            ],
            total=itinerary.total,
        )


class TripResultSchema(BaseModel):
    best: ItinerarySchema
    alternatives: list[ItinerarySchema]
    data_source: str
    snapshot_date: date | None = None

    @classmethod
    def from_core(
        cls,
        result: TripResult,
        *,
        data_source: str,
        snapshot_date: date | None = None,
    ) -> "TripResultSchema":
        return cls(
            best=ItinerarySchema.from_core(result.best),
            alternatives=[ItinerarySchema.from_core(it) for it in result.alternatives],
            data_source=data_source,
            snapshot_date=snapshot_date,
        )


class AirportSchema(BaseModel):
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lon: float
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_schemas.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/api/__init__.py backend/tripoptimizer/api/schemas.py backend/tests/api/__init__.py backend/tests/api/test_schemas.py
git commit -m "feat: add Pydantic API schemas with boundary guardrails"
```

---

### Task 4: Dependencies module (cached airports + provider)

**Files:**
- Create: `backend/tripoptimizer/api/dependencies.py`
- Test: `backend/tests/api/test_dependencies.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_dependencies.py`:

```python
"""The API loads airport reference data and a synthetic provider once."""

from datetime import date

from tripoptimizer.api.dependencies import get_airports, get_provider


def test_get_airports_loads_sample_set() -> None:
    airports = get_airports()
    assert "LIS" in airports
    assert airports["LIS"].city == "Lisbon"
    assert len(airports) >= 8


def test_get_airports_is_cached() -> None:
    assert get_airports() is get_airports()


def test_get_provider_prices_a_known_leg() -> None:
    provider = get_provider()
    fare = provider.get_fare("LIS", "BCN", date(2026, 7, 1))
    assert fare is not None
    assert fare.price > 0
    assert fare.source == "synthetic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_dependencies.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.api.dependencies`.

- [ ] **Step 3: Implement the dependencies**

Create `backend/tripoptimizer/api/dependencies.py`:

```python
"""Process-wide singletons for the API: airport reference data + fare provider.

The data path defaults to the committed sample CSV and can be overridden with
the ``TRIPOPTIMIZER_AIRPORTS_CSV`` env var (no hardcoded absolute paths).
"""

import functools
import os
from pathlib import Path

from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.graph.airports import Airport, load_airports

_DEFAULT_AIRPORTS_CSV = Path(__file__).resolve().parents[2] / "data" / "airports_sample.csv"


def _airports_csv_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_AIRPORTS_CSV")
    return Path(override) if override else _DEFAULT_AIRPORTS_CSV


@functools.lru_cache(maxsize=1)
def get_airports() -> dict[str, Airport]:
    return load_airports(_airports_csv_path())


@functools.lru_cache(maxsize=1)
def get_provider() -> SyntheticProvider:
    return SyntheticProvider(get_airports())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_dependencies.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/api/dependencies.py backend/tests/api/test_dependencies.py
git commit -m "feat: add cached airports + synthetic provider API dependencies"
```

---

### Task 5: App factory + health endpoint

**Files:**
- Create: `backend/tripoptimizer/api/routes.py`
- Create: `backend/tripoptimizer/api/app.py`
- Test: `backend/tests/api/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_health.py`:

```python
"""Health endpoint reports liveness + that reference data loaded."""

from fastapi.testclient import TestClient

from tripoptimizer.api.app import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["airports_loaded"] >= 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.api.app`.

- [ ] **Step 3: Implement the router (health only for now)**

Create `backend/tripoptimizer/api/routes.py`:

```python
"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException

from tripoptimizer.api.dependencies import get_airports

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + a shallow check that reference data is available."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    return {"status": "ok", "airports_loaded": len(airports)}
```

- [ ] **Step 4: Implement the app factory**

Create `backend/tripoptimizer/api/app.py`:

```python
"""FastAPI application assembly."""

from fastapi import FastAPI

from tripoptimizer.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripOptimizer API",
        version="0.1.0",
        description="Cheapest multi-city trip-ordering optimizer.",
    )
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/api/routes.py backend/tripoptimizer/api/app.py backend/tests/api/test_health.py
git commit -m "feat: add FastAPI app factory and /health endpoint"
```

---

### Task 6: Airports endpoint

**Files:**
- Modify: `backend/tripoptimizer/api/routes.py`
- Test: `backend/tests/api/test_airports.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_airports.py`:

```python
"""Airports endpoint returns the reference set for the frontend picker."""

from fastapi.testclient import TestClient

from tripoptimizer.api.app import app

client = TestClient(app)


def test_airports_list() -> None:
    response = client.get("/airports")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 8
    lis = next(a for a in body if a["iata"] == "LIS")
    assert lis["city"] == "Lisbon"
    assert lis["country"] == "PT"
    assert "lat" in lis and "lon" in lis
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_airports.py -v`
Expected: FAIL — 404 (route not defined yet).

- [ ] **Step 3: Add the airports route**

In `backend/tripoptimizer/api/routes.py`, update the imports and append the route. The file becomes:

```python
"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException

from tripoptimizer.api.dependencies import get_airports
from tripoptimizer.api.schemas import AirportSchema

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + a shallow check that reference data is available."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    return {"status": "ok", "airports_loaded": len(airports)}


@router.get("/airports", response_model=list[AirportSchema])
def list_airports() -> list[AirportSchema]:
    """All known airports (IATA, name, city, country, lat/lon)."""
    return [
        AirportSchema(
            iata=a.iata,
            name=a.name,
            city=a.city,
            country=a.country,
            lat=a.lat,
            lon=a.lon,
        )
        for a in get_airports().values()
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_airports.py tests/api/test_health.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/api/routes.py backend/tests/api/test_airports.py
git commit -m "feat: add /airports endpoint"
```

---

### Task 7: Optimize endpoint — happy path (brute-force default)

**Files:**
- Modify: `backend/tripoptimizer/api/routes.py`
- Test: `backend/tests/api/test_optimize.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_optimize.py`:

```python
"""Optimize endpoint: happy path with the default brute-force engine."""

from fastapi.testclient import TestClient

from tripoptimizer.api.app import app

client = TestClient(app)


def _payload() -> dict:
    return {
        "cities": ["BCN", "CDG", "FCO"],
        "days_per_city": {"BCN": 2, "CDG": 2, "FCO": 3},
        "origin_airport": "LIS",
        "return_airport": "LIS",
        "start_date": "2026-07-01",
        "flex_days": 2,
    }


def test_optimize_happy_path() -> None:
    response = client.post("/optimize", json=_payload())
    assert response.status_code == 200
    body = response.json()

    assert body["data_source"] == "synthetic"
    assert body["snapshot_date"] is None

    best = body["best"]
    assert sorted(best["order"]) == ["BCN", "CDG", "FCO"]
    assert best["total"] > 0
    # legs form a chain LIS -> ... -> LIS (3 cities => 4 legs)
    assert len(best["legs"]) == 4
    assert best["legs"][0]["origin"] == "LIS"
    assert best["legs"][-1]["destination"] == "LIS"
    # total equals the sum of leg prices (within float tolerance)
    assert abs(best["total"] - sum(leg["price"] for leg in best["legs"])) < 1e-6

    # brute-force returns ranked alternatives, each >= best
    assert len(body["alternatives"]) >= 1
    assert all(alt["total"] >= best["total"] for alt in body["alternatives"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_optimize.py -v`
Expected: FAIL — 404 (route not defined yet).

- [ ] **Step 3: Add the optimize route**

In `backend/tripoptimizer/api/routes.py`, update imports and append the optimize route. Final file:

```python
"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException, Query

from tripoptimizer.api.dependencies import get_airports, get_provider
from tripoptimizer.api.schemas import AirportSchema, TripRequestSchema, TripResultSchema
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + a shallow check that reference data is available."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    return {"status": "ok", "airports_loaded": len(airports)}


@router.get("/airports", response_model=list[AirportSchema])
def list_airports() -> list[AirportSchema]:
    """All known airports (IATA, name, city, country, lat/lon)."""
    return [
        AirportSchema(
            iata=a.iata,
            name=a.name,
            city=a.city,
            country=a.country,
            lat=a.lat,
            lon=a.lon,
        )
        for a in get_airports().values()
    ]


@router.post("/optimize", response_model=TripResultSchema)
def optimize_route(
    request: TripRequestSchema,
    engine: str = Query(default="bruteforce", pattern="^(bruteforce|heldkarp)$"),
) -> TripResultSchema:
    """Compute the cheapest city ordering (+ date slide) for the trip."""
    airports = get_airports()
    codes = {request.origin_airport, request.return_airport, *request.cities}
    unknown = sorted(code for code in codes if code not in airports)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown airport(s): {unknown}")

    trip = TripRequest(
        cities=tuple(request.cities),
        days_per_city=dict(request.days_per_city),
        origin_airport=request.origin_airport,
        return_airport=request.return_airport,
        start_date=request.start_date,
        flex_days=request.flex_days,
    )
    result = optimize(trip, get_provider(), engine=engine)
    return TripResultSchema.from_core(result, data_source="synthetic")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/ -v`
Expected: PASS (all API tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/api/routes.py backend/tests/api/test_optimize.py
git commit -m "feat: add /optimize endpoint (brute-force default)"
```

---

### Task 8: Optimize endpoint — engine switch + error paths

**Files:**
- Modify: `backend/tests/api/test_optimize.py`

The route already implements these behaviors; this task adds the tests that lock them in. (If any test fails, fix the route to match — do not weaken the test.)

- [ ] **Step 1: Append the failing tests**

Append to `backend/tests/api/test_optimize.py`:

```python
def test_heldkarp_engine_returns_no_alternatives() -> None:
    response = client.post("/optimize?engine=heldkarp", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["alternatives"] == []
    assert sorted(body["best"]["order"]) == ["BCN", "CDG", "FCO"]


def test_both_engines_agree_on_best_total() -> None:
    bf = client.post("/optimize?engine=bruteforce", json=_payload()).json()
    hk = client.post("/optimize?engine=heldkarp", json=_payload()).json()
    assert abs(bf["best"]["total"] - hk["best"]["total"]) < 1e-6


def test_unknown_airport_returns_400() -> None:
    payload = _payload()
    payload["origin_airport"] = "ZZZ"
    response = client.post("/optimize", json=payload)
    assert response.status_code == 400
    assert "ZZZ" in response.json()["detail"]


def test_too_many_cities_returns_422() -> None:
    payload = _payload()
    payload["cities"] = [f"C{i:02d}" for i in range(9)]
    payload["days_per_city"] = {c: 1 for c in payload["cities"]}
    response = client.post("/optimize", json=payload)
    assert response.status_code == 422


def test_missing_days_returns_422() -> None:
    payload = _payload()
    payload["days_per_city"] = {"BCN": 2, "CDG": 2}  # FCO missing
    response = client.post("/optimize", json=payload)
    assert response.status_code == 422


def test_invalid_engine_returns_422() -> None:
    response = client.post("/optimize?engine=astar", json=_payload())
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/api/test_optimize.py -v`
Expected: PASS (all 7 optimize tests). If `test_unknown_airport_returns_400` or others fail, the route's guard/engine handling is wrong — fix `routes.py`, not the test.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/api/test_optimize.py
git commit -m "test: cover optimize engine switch and error paths"
```

---

### Task 9: Full-suite gate (coverage + lint)

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite with coverage**

Run (from `backend/`): `uv run pytest`
Expected: all tests pass; total coverage ≥ 90% (target floor is 80%). If any `api/*.py` line is uncovered, add a focused test for it.

- [ ] **Step 2: Lint**

Run (from `backend/`): `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Smoke-run the server manually (optional but recommended)**

Run (from `backend/`): `uv run uvicorn tripoptimizer.api.app:app --port 8000`
Then in another shell: `curl http://127.0.0.1:8000/health` → `{"status":"ok","airports_loaded":8}`; open `http://127.0.0.1:8000/docs` to see the OpenAPI UI. Stop the server with Ctrl+C.

- [ ] **Step 4: Push the branch**

```bash
git push origin feat/backend-foundation
```

---

## Self-review against the spec

- **§2 / §6 endpoints** `POST /optimize`, `GET /airports`, `GET /health` → Tasks 5–8. ✅
- **§2 guardrails** max 8 cities, `flex_days` cap → enforced in `TripRequestSchema` (Task 3), tested in Tasks 3 & 8. ✅
- **§7 API schemas** `TripRequest/TripResult/Itinerary/Leg` → `schemas.py` (Task 3); field names match the *actual* core dataclasses (`fly_date`/`price`), not the spec's draft table. ✅
- **§3.4 algorithm** brute-force default + Held-Karp via `?engine=` + oracle-agreement test (Task 8 `test_both_engines_agree_on_best_total`). ✅
- **§8 error handling** Pydantic 422 at boundary; 400 for unknown IATA; 503 health when data missing. ✅
- **§2 no-key demo** wired to `SyntheticProvider` only; `data_source="synthetic"`, `snapshot_date=None` anticipates Plan 2's cached source. ✅
- **§9 testing ≥80%** Task 9 gate. ✅
- **Deferred & flagged:** CORS (Plan 4), DuckDB-deep health + per-leg `data_source` (Plan 2). ✅

**Open follow-up (decide at handoff, not silently):** the standing author rule is "update the internal HTML guide on every commit," but the project status decision deferred starting it. This plan does not touch the guide — confirm whether to begin it now or keep it deferred to Plan 5.
