# TripOptimizer — Plan 1: Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python core of TripOptimizer — airport graph, a deterministic synthetic fare provider, and the cheapest-route optimizer (brute-force engine validated by a Held-Karp DP) — so that `optimize(request, SyntheticProvider(airports))` returns a correct ranked itinerary, fully tested.

**Architecture:** Dependency-light, pure core under `tripoptimizer.core`. The optimizer never does I/O: it receives a `fare_lookup` callable; a thin runner builds that callable from any `FareProvider`. Fares come from a `FareProvider` Strategy interface — Plan 1 ships the `SyntheticProvider` (deterministic over real airport geography); `Cached`/`Travelpayouts` providers arrive in Plan 2 without touching the optimizer.

**Tech Stack:** Python 3.11+, stdlib only for the core (math, hashlib, itertools, datetime, csv, dataclasses), `pytest` + `pytest-cov` + `ruff` for dev, `uv` for env/deps.

**Spec:** `docs/superpowers/specs/2026-06-15-tripoptimizer-mvp-design.md`

---

## File Structure (Plan 1)

```
backend/
├─ pyproject.toml                              # project + dev deps + tool config
├─ .gitignore
├─ .env.example
├─ data/
│  └─ airports_sample.csv                      # small EU airport fixture (committed)
├─ tripoptimizer/
│  ├─ __init__.py
│  └─ core/
│     ├─ __init__.py
│     ├─ graph/
│     │  ├─ __init__.py
│     │  ├─ distance.py                         # haversine_km
│     │  └─ airports.py                         # Airport model + load_airports
│     ├─ fares/
│     │  ├─ __init__.py
│     │  ├─ models.py                           # Fare
│     │  ├─ base.py                             # FareProvider Protocol
│     │  └─ synthetic.py                        # SyntheticProvider
│     └─ optimizer/
│        ├─ __init__.py
│        ├─ models.py                           # TripRequest, Leg, Itinerary, TripResult
│        ├─ schedule.py                         # build_legs_dates
│        ├─ bruteforce.py                       # search_bruteforce
│        ├─ heldkarp.py                         # search_heldkarp (DP)
│        └─ runner.py                           # optimize(request, provider, engine)
└─ tests/
   ├─ graph/test_distance.py
   ├─ graph/test_airports.py
   ├─ fares/test_synthetic.py
   ├─ optimizer/test_schedule.py
   ├─ optimizer/test_bruteforce.py
   └─ optimizer/test_heldkarp.py
```

Responsibilities: `graph` = geography (pure), `fares` = price source behind a Strategy interface, `optimizer` = combinatorial search (pure) + a thin I/O runner. Files split by responsibility, each small enough to hold in context.

---

### Task 1: Project scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.gitignore`
- Create: `backend/.env.example`
- Create: `backend/tripoptimizer/__init__.py`
- Create: `backend/tripoptimizer/core/__init__.py`
- Create: `backend/tripoptimizer/core/graph/__init__.py`
- Create: `backend/tripoptimizer/core/fares/__init__.py`
- Create: `backend/tripoptimizer/core/optimizer/__init__.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "tripoptimizer"
version = "0.1.0"
description = "Cheapest multi-city trip-ordering optimizer"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.5"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["tripoptimizer"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --cov=tripoptimizer --cov-report=term-missing"

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Create `backend/.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
*.duckdb
```

- [ ] **Step 3: Create `backend/.env.example`**

```dotenv
# Travelpayouts Data API token (used only by the offline ingestion in Plan 2)
TRAVELPAYOUTS_TOKEN=
# When true, the app reads the committed snapshot / synthetic data and needs no key
DEMO_MODE=true
```

- [ ] **Step 4: Create the empty package `__init__.py` files**

Create these five files.

`backend/tripoptimizer/__init__.py`:
```python
"""TripOptimizer — cheapest multi-city trip-ordering optimizer."""
```

`backend/tripoptimizer/core/__init__.py`, `core/graph/__init__.py`, `core/fares/__init__.py`, `core/optimizer/__init__.py` — each is an empty file (create with no content).

- [ ] **Step 5: Create the virtualenv and install dev deps**

Run:
```bash
cd backend && uv venv && uv pip install -e ".[dev]"
```
Expected: env created, `tripoptimizer` installed editable, pytest/ruff available.

- [ ] **Step 6: Verify the toolchain runs**

Run: `cd backend && uv run pytest -q`
Expected: `no tests ran` (exit code 5) — confirms pytest is wired before any test exists.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/.gitignore backend/.env.example backend/tripoptimizer
git commit -m "chore: scaffold backend package and tooling"
```

---

### Task 2: Haversine distance

**Files:**
- Create: `backend/tripoptimizer/core/graph/distance.py`
- Test: `backend/tests/graph/test_distance.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/graph/test_distance.py`:
```python
from tripoptimizer.core.graph.distance import haversine_km


def test_distance_is_zero_for_same_point():
    assert haversine_km(38.77, -9.13, 38.77, -9.13) == 0.0


def test_lisbon_to_barcelona_is_about_1000_km():
    # LIS (38.7742, -9.1342) -> BCN (41.2974, 2.0833)
    d = haversine_km(38.7742, -9.1342, 41.2974, 2.0833)
    assert 950 < d < 1050


def test_longer_route_is_greater():
    lis_bcn = haversine_km(38.7742, -9.1342, 41.2974, 2.0833)
    lis_ath = haversine_km(38.7742, -9.1342, 37.9364, 23.9445)  # Athens, much farther
    assert lis_ath > lis_bcn
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/graph/test_distance.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.graph.distance`.

- [ ] **Step 3: Write minimal implementation**

`backend/tripoptimizer/core/graph/distance.py`:
```python
"""Great-circle distance between two lat/lon points."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometers."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/graph/test_distance.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/graph/distance.py backend/tests/graph/test_distance.py
git commit -m "feat: add haversine distance for airport graph"
```

---

### Task 3: Airport model + loader

**Files:**
- Create: `backend/tripoptimizer/core/graph/airports.py`
- Create: `backend/data/airports_sample.csv`
- Test: `backend/tests/graph/test_airports.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/graph/test_airports.py`:
```python
from pathlib import Path

from tripoptimizer.core.graph.airports import Airport, load_airports


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "iata,name,city,country,lat,lon\n"
        "LIS,Humberto Delgado,Lisbon,PT,38.7742,-9.1342\n"
        "BCN,El Prat,Barcelona,ES,41.2974,2.0833\n"
    )
    return csv_path


def test_load_airports_returns_dict_keyed_by_iata(tmp_path):
    airports = load_airports(_write_csv(tmp_path))
    assert set(airports) == {"LIS", "BCN"}
    assert isinstance(airports["LIS"], Airport)


def test_airport_fields_are_typed(tmp_path):
    airports = load_airports(_write_csv(tmp_path))
    lis = airports["LIS"]
    assert lis.city == "Lisbon"
    assert lis.country == "PT"
    assert lis.lat == 38.7742
    assert lis.lon == -9.1342
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/graph/test_airports.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.graph.airports`.

- [ ] **Step 3: Write minimal implementation**

`backend/tripoptimizer/core/graph/airports.py`:
```python
"""Airport reference data: an immutable model and a CSV loader."""
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lon: float


def load_airports(path: str | Path) -> dict[str, Airport]:
    """Load airports from a CSV (columns: iata,name,city,country,lat,lon)."""
    airports: dict[str, Airport] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            airports[row["iata"]] = Airport(
                iata=row["iata"],
                name=row["name"],
                city=row["city"],
                country=row["country"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
            )
    return airports
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/graph/test_airports.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Create the committed sample airport fixture**

`backend/data/airports_sample.csv`:
```csv
iata,name,city,country,lat,lon
LIS,Humberto Delgado,Lisbon,PT,38.7742,-9.1342
OPO,Francisco Sa Carneiro,Porto,PT,41.2481,-8.6814
MAD,Adolfo Suarez Barajas,Madrid,ES,40.4983,-3.5676
BCN,Josep Tarradellas El Prat,Barcelona,ES,41.2974,2.0833
CDG,Charles de Gaulle,Paris,FR,49.0097,2.5479
FCO,Leonardo da Vinci Fiumicino,Rome,IT,41.8003,12.2389
BER,Brandenburg,Berlin,DE,52.3667,13.5033
ATH,Eleftherios Venizelos,Athens,GR,37.9364,23.9445
```

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/core/graph/airports.py backend/tests/graph/test_airports.py backend/data/airports_sample.csv
git commit -m "feat: add airport model, CSV loader, and EU sample fixture"
```

---

### Task 4: Fare model + FareProvider interface

**Files:**
- Create: `backend/tripoptimizer/core/fares/models.py`
- Create: `backend/tripoptimizer/core/fares/base.py`

(No dedicated test file — exercised by Task 5's provider tests. This task defines the shared types.)

- [ ] **Step 1: Create the Fare model**

`backend/tripoptimizer/core/fares/models.py`:
```python
"""Fare value object. Grain: one fare = origin x destination x fly_date."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Fare:
    origin: str
    destination: str
    fly_date: date
    price: float
    currency: str = "EUR"
    source: str = "synthetic"
```

- [ ] **Step 2: Create the FareProvider Protocol**

`backend/tripoptimizer/core/fares/base.py`:
```python
"""Strategy interface for fare sources (synthetic, cached, travelpayouts...)."""
from datetime import date
from typing import Protocol

from tripoptimizer.core.fares.models import Fare


class FareProvider(Protocol):
    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare | None:
        """Return a Fare for the leg, or None if this provider has no data for it."""
        ...
```

- [ ] **Step 3: Verify it imports**

Run: `cd backend && uv run python -c "from tripoptimizer.core.fares.base import FareProvider; from tripoptimizer.core.fares.models import Fare; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/tripoptimizer/core/fares/models.py backend/tripoptimizer/core/fares/base.py
git commit -m "feat: add Fare model and FareProvider strategy interface"
```

---

### Task 5: SyntheticProvider (deterministic fares)

**Files:**
- Create: `backend/tripoptimizer/core/fares/synthetic.py`
- Test: `backend/tests/fares/test_synthetic.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/fares/test_synthetic.py`:
```python
from datetime import date

from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.fares.synthetic import SyntheticProvider

AIRPORTS = {
    "LIS": Airport("LIS", "Humberto Delgado", "Lisbon", "PT", 38.7742, -9.1342),
    "BCN": Airport("BCN", "El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "ATH": Airport("ATH", "Venizelos", "Athens", "GR", 37.9364, 23.9445),
}


def test_fare_is_positive():
    provider = SyntheticProvider(AIRPORTS)
    fare = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    assert fare is not None
    assert fare.price > 0
    assert fare.currency == "EUR"
    assert fare.source == "synthetic"


def test_fare_is_deterministic():
    provider = SyntheticProvider(AIRPORTS)
    a = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    b = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    assert a.price == b.price


def test_longer_distance_costs_more_on_same_date():
    provider = SyntheticProvider(AIRPORTS)
    near = provider.get_fare("LIS", "BCN", date(2026, 7, 3)).price
    far = provider.get_fare("LIS", "ATH", date(2026, 7, 3)).price
    assert far > near


def test_unknown_airport_returns_none():
    provider = SyntheticProvider(AIRPORTS)
    assert provider.get_fare("LIS", "ZZZ", date(2026, 7, 3)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/fares/test_synthetic.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.fares.synthetic`.

- [ ] **Step 3: Write minimal implementation**

`backend/tripoptimizer/core/fares/synthetic.py`:
```python
"""Deterministic synthetic fares over real airport geography.

Price model (defensible, documented): base = BASE + PER_KM * haversine,
multiplied by month seasonality, a weekend surcharge, and a deterministic
per-(leg, date) noise factor so the SAME leg always returns the SAME price.
"""
import hashlib
from datetime import date
from math import pi, sin

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.graph.distance import haversine_km

BASE_FARE_EUR = 20.0
PER_KM_EUR = 0.07


def _unit_noise(origin: str, destination: str, fly_date: date) -> float:
    """Deterministic value in [0, 1) derived from the leg + date."""
    key = f"{origin}|{destination}|{fly_date.isoformat()}".encode()
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:8], 16) / 0x100000000


class SyntheticProvider:
    def __init__(self, airports: dict[str, Airport]):
        self._airports = airports

    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare | None:
        if origin not in self._airports or destination not in self._airports:
            return None
        a, b = self._airports[origin], self._airports[destination]
        dist = haversine_km(a.lat, a.lon, b.lat, b.lon)
        base = BASE_FARE_EUR + PER_KM_EUR * dist
        season = 1.0 + 0.25 * sin(2 * pi * (fly_date.month - 1) / 12)
        weekend = 1.15 if fly_date.weekday() >= 5 else 1.0
        noise = 0.85 + 0.30 * _unit_noise(origin, destination, fly_date)
        price = round(base * season * weekend * noise, 2)
        return Fare(origin, destination, fly_date, price, "EUR", "synthetic")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/fares/test_synthetic.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/fares/synthetic.py backend/tests/fares/test_synthetic.py
git commit -m "feat: add deterministic synthetic fare provider"
```

---

### Task 6: Optimizer models

**Files:**
- Create: `backend/tripoptimizer/core/optimizer/models.py`

(Exercised by Tasks 7–9.)

- [ ] **Step 1: Create the models**

`backend/tripoptimizer/core/optimizer/models.py`:
```python
"""Immutable models for the optimizer's input and output."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TripRequest:
    cities: tuple[str, ...]          # IATA codes of the destination cities
    days_per_city: dict[str, int]    # days spent in each city
    origin_airport: str              # IATA where the trip starts
    return_airport: str              # IATA where the trip ends
    start_date: date
    flex_days: int = 3               # slide the whole trip within +/- this many days


@dataclass(frozen=True)
class Leg:
    origin: str
    destination: str
    fly_date: date
    price: float


@dataclass(frozen=True)
class Itinerary:
    order: tuple[str, ...]           # the optimized order of the middle cities
    start_offset: int                # day offset applied to start_date
    legs: tuple[Leg, ...]            # origin -> c1 -> ... -> ck -> return
    total: float


@dataclass(frozen=True)
class TripResult:
    best: Itinerary
    alternatives: tuple[Itinerary, ...]
```

- [ ] **Step 2: Verify it imports**

Run: `cd backend && uv run python -c "from tripoptimizer.core.optimizer.models import TripRequest, Itinerary, Leg, TripResult; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/models.py
git commit -m "feat: add optimizer input/output models"
```

---

### Task 7: Schedule (derive leg dates from order + offset)

**Files:**
- Create: `backend/tripoptimizer/core/optimizer/schedule.py`
- Test: `backend/tests/optimizer/test_schedule.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/optimizer/test_schedule.py`:
```python
from datetime import date

from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.schedule import build_legs_dates


def _request():
    return TripRequest(
        cities=("BCN", "FCO"),
        days_per_city={"BCN": 3, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=3,
    )


def test_legs_form_a_full_chain_origin_to_return():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=0)
    chain = [(o, d) for (o, d, _) in legs]
    assert chain == [("LIS", "BCN"), ("BCN", "FCO"), ("FCO", "LIS")]


def test_dates_accumulate_days_per_city():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=0)
    dates = [dt for (_, _, dt) in legs]
    assert dates == [date(2026, 7, 1), date(2026, 7, 4), date(2026, 7, 6)]


def test_offset_shifts_every_date():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=-2)
    assert [dt for (_, _, dt) in legs][0] == date(2026, 6, 29)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/optimizer/test_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.optimizer.schedule`.

- [ ] **Step 3: Write minimal implementation**

`backend/tripoptimizer/core/optimizer/schedule.py`:
```python
"""Turn a city order + start offset into the dated leg chain."""
from datetime import date, timedelta

from tripoptimizer.core.optimizer.models import TripRequest


def build_legs_dates(
    order: tuple[str, ...], request: TripRequest, start_offset: int
) -> list[tuple[str, str, date]]:
    """Return [(origin, destination, fly_date), ...] from origin through return."""
    current_date = request.start_date + timedelta(days=start_offset)
    current_place = request.origin_airport
    legs: list[tuple[str, str, date]] = []
    for city in order:
        legs.append((current_place, city, current_date))
        current_date += timedelta(days=request.days_per_city[city])
        current_place = city
    legs.append((current_place, request.return_airport, current_date))
    return legs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/optimizer/test_schedule.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/schedule.py backend/tests/optimizer/test_schedule.py
git commit -m "feat: add leg-date scheduling from order and offset"
```

---

### Task 8: Brute-force engine + runner

**Files:**
- Create: `backend/tripoptimizer/core/optimizer/bruteforce.py`
- Create: `backend/tripoptimizer/core/optimizer/runner.py`
- Test: `backend/tests/optimizer/test_bruteforce.py`

> **Ordering note:** `runner.py` imports `search_heldkarp` from Task 9. Create Task 9's `heldkarp.py` BEFORE running this task's tests (do Task 8 then Task 9, verifying both at Task 9 Step 4), or drop a one-line stub `def search_heldkarp(request, fare_lookup): raise NotImplementedError` first and replace it in Task 9.

- [ ] **Step 1: Write the failing test**

`backend/tests/optimizer/test_bruteforce.py`:
```python
from datetime import date

from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize

AIRPORTS = {
    "LIS": Airport("LIS", "Humberto Delgado", "Lisbon", "PT", 38.7742, -9.1342),
    "BCN": Airport("BCN", "El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "FCO": Airport("FCO", "Fiumicino", "Rome", "IT", 41.8003, 12.2389),
    "ATH": Airport("ATH", "Venizelos", "Athens", "GR", 37.9364, 23.9445),
}


def _request():
    return TripRequest(
        cities=("BCN", "FCO", "ATH"),
        days_per_city={"BCN": 3, "FCO": 2, "ATH": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=3,
    )


def test_returns_itinerary_visiting_all_cities_once():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    assert set(result.best.order) == {"BCN", "FCO", "ATH"}
    assert len(result.best.order) == 3


def test_legs_start_at_origin_and_end_at_return():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    assert result.best.legs[0].origin == "LIS"
    assert result.best.legs[-1].destination == "LIS"


def test_best_is_cheapest_among_alternatives():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    for alt in result.alternatives:
        assert result.best.total <= alt.total
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/optimizer/test_bruteforce.py -v`
Expected: FAIL — `ModuleNotFoundError: tripoptimizer.core.optimizer.runner`.

- [ ] **Step 3: Write the brute-force engine**

`backend/tripoptimizer/core/optimizer/bruteforce.py`:
```python
"""Exhaustive search over city permutations x date offsets."""
from collections.abc import Callable
from datetime import date
from itertools import permutations

from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripRequest, TripResult
from tripoptimizer.core.optimizer.schedule import build_legs_dates

FareLookup = Callable[[str, str, date], float]
MAX_ALTERNATIVES = 5


def _itinerary(order, request, offset, fare_lookup) -> Itinerary:
    legs: list[Leg] = []
    total = 0.0
    for origin, destination, fly_date in build_legs_dates(order, request, offset):
        price = fare_lookup(origin, destination, fly_date)
        legs.append(Leg(origin, destination, fly_date, price))
        total += price
    return Itinerary(tuple(order), offset, tuple(legs), total)


def search_bruteforce(request: TripRequest, fare_lookup: FareLookup) -> TripResult:
    offsets = range(-request.flex_days, request.flex_days + 1)
    candidates = [
        _itinerary(order, request, offset, fare_lookup)
        for order in permutations(request.cities)
        for offset in offsets
    ]
    candidates.sort(key=lambda it: it.total)
    return TripResult(best=candidates[0], alternatives=tuple(candidates[1 : 1 + MAX_ALTERNATIVES]))
```

- [ ] **Step 4: Write the runner**

`backend/tripoptimizer/core/optimizer/runner.py`:
```python
"""Thin orchestrator: build a fare_lookup from a FareProvider, run an engine."""
from datetime import date

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.optimizer.bruteforce import search_bruteforce
from tripoptimizer.core.optimizer.heldkarp import search_heldkarp
from tripoptimizer.core.optimizer.models import TripRequest, TripResult


def optimize(
    request: TripRequest, provider: FareProvider, engine: str = "bruteforce"
) -> TripResult:
    def fare_lookup(origin: str, destination: str, fly_date: date) -> float:
        fare = provider.get_fare(origin, destination, fly_date)
        if fare is None:
            raise KeyError(f"no fare for {origin}->{destination} on {fly_date.isoformat()}")
        return fare.price

    if engine == "heldkarp":
        return search_heldkarp(request, fare_lookup)
    return search_bruteforce(request, fare_lookup)
```

- [ ] **Step 5: Run test to verify it passes**

Create Task 9's `heldkarp.py` first (or the stub from the ordering note), then run:
`cd backend && uv run pytest tests/optimizer/test_bruteforce.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/bruteforce.py backend/tripoptimizer/core/optimizer/runner.py backend/tests/optimizer/test_bruteforce.py
git commit -m "feat: add brute-force route optimizer and provider runner"
```

---

### Task 9: Held-Karp DP + oracle test

**Files:**
- Create: `backend/tripoptimizer/core/optimizer/heldkarp.py`
- Test: `backend/tests/optimizer/test_heldkarp.py`

**Why:** the date you fly the k-th leg depends only on the *set* of cities already visited (their total days), not their order — so a DP over subsets `(visited_set, last_city)` is exact. This task implements it and proves equivalence to brute-force (the oracle).

- [ ] **Step 1: Write the failing oracle test**

`backend/tests/optimizer/test_heldkarp.py`:
```python
import random
from datetime import date

from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize

AIRPORTS = {
    "LIS": Airport("LIS", "Humberto Delgado", "Lisbon", "PT", 38.7742, -9.1342),
    "BCN": Airport("BCN", "El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "FCO": Airport("FCO", "Fiumicino", "Rome", "IT", 41.8003, 12.2389),
    "ATH": Airport("ATH", "Venizelos", "Athens", "GR", 37.9364, 23.9445),
    "CDG": Airport("CDG", "Charles de Gaulle", "Paris", "FR", 49.0097, 2.5479),
    "BER": Airport("BER", "Brandenburg", "Berlin", "DE", 52.3667, 13.5033),
}


def test_heldkarp_matches_bruteforce_on_random_cases():
    rng = random.Random(42)
    provider = SyntheticProvider(AIRPORTS)
    cities_pool = ["BCN", "FCO", "ATH", "CDG", "BER"]
    for _ in range(20):
        k = rng.randint(2, 5)
        cities = tuple(rng.sample(cities_pool, k))
        request = TripRequest(
            cities=cities,
            days_per_city={c: rng.randint(1, 4) for c in cities},
            origin_airport="LIS",
            return_airport="LIS",
            start_date=date(2026, 7, 1),
            flex_days=rng.randint(0, 3),
        )
        bf = optimize(request, provider, engine="bruteforce").best
        dp = optimize(request, provider, engine="heldkarp").best
        assert abs(bf.total - dp.total) < 1e-6
        assert dp.legs[0].origin == "LIS"
        assert dp.legs[-1].destination == "LIS"
        assert set(dp.order) == set(cities)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/optimizer/test_heldkarp.py -v`
Expected: FAIL — `ImportError`/`NotImplementedError` for `search_heldkarp` (or `ModuleNotFoundError` if no stub exists).

- [ ] **Step 3: Write the DP implementation**

`backend/tripoptimizer/core/optimizer/heldkarp.py`:
```python
"""Held-Karp DP over (visited_set, last_city). Exact because leg dates depend
only on the set of already-visited cities (fixed days), not their order."""
from collections.abc import Callable
from datetime import date, timedelta

from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripRequest, TripResult
from tripoptimizer.core.optimizer.schedule import build_legs_dates

FareLookup = Callable[[str, str, date], float]


def _best_for_offset(request: TripRequest, fare_lookup: FareLookup, offset: int) -> Itinerary:
    cities = list(request.cities)
    n = len(cities)
    start = request.start_date + timedelta(days=offset)
    days = [request.days_per_city[c] for c in cities]
    full = (1 << n) - 1

    # dp[mask][last] = (cost to be AT `last` having visited exactly `mask`, prev_last)
    dp: list[list[tuple[float, int] | None]] = [[None] * n for _ in range(1 << n)]
    for i, city in enumerate(cities):
        dp[1 << i][i] = (fare_lookup(request.origin_airport, city, start), -1)

    for mask in range(1 << n):
        days_spent = sum(days[i] for i in range(n) if mask & (1 << i))
        fly_date = start + timedelta(days=days_spent)
        for last in range(n):
            state = dp[mask][last]
            if state is None:
                continue
            cost = state[0]
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                ncost = cost + fare_lookup(cities[last], cities[nxt], fly_date)
                nmask = mask | (1 << nxt)
                current = dp[nmask][nxt]
                if current is None or ncost < current[0]:
                    dp[nmask][nxt] = (ncost, last)

    return_date = start + timedelta(days=sum(days))
    best_total: float | None = None
    best_last = -1
    for last in range(n):
        state = dp[full][last]
        if state is None:
            continue
        total = state[0] + fare_lookup(cities[last], request.return_airport, return_date)
        if best_total is None or total < best_total:
            best_total, best_last = total, last

    # reconstruct the order from parent pointers
    order_rev: list[str] = []
    mask, last = full, best_last
    while last != -1:
        order_rev.append(cities[last])
        prev = dp[mask][last][1]
        mask ^= 1 << last
        last = prev
    order = tuple(reversed(order_rev))

    legs = tuple(
        Leg(o, d, dt, fare_lookup(o, d, dt))
        for (o, d, dt) in build_legs_dates(order, request, offset)
    )
    return Itinerary(order, offset, legs, sum(leg.price for leg in legs))


def search_heldkarp(request: TripRequest, fare_lookup: FareLookup) -> TripResult:
    best: Itinerary | None = None
    for offset in range(-request.flex_days, request.flex_days + 1):
        candidate = _best_for_offset(request, fare_lookup, offset)
        if best is None or candidate.total < best.total:
            best = candidate
    return TripResult(best=best, alternatives=())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/optimizer/test_heldkarp.py tests/optimizer/test_bruteforce.py -v`
Expected: PASS (oracle case + brute-force tests all green).

- [ ] **Step 5: Run the full suite + coverage + lint**

Run: `cd backend && uv run pytest && uv run ruff check .`
Expected: all tests PASS, coverage ≥ 80%, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add backend/tripoptimizer/core/optimizer/heldkarp.py backend/tests/optimizer/test_heldkarp.py
git commit -m "feat: add Held-Karp DP optimizer validated against brute-force oracle"
```

---

## Self-Review

**1. Spec coverage (Plan 1's slice):**
- Stack / pure core (spec 3.1, 4): Tasks 1–9 build `tripoptimizer.core`, stdlib-only. ✓
- `FareProvider` Strategy (spec 3.2, 5): Task 4 interface + Task 5 `SyntheticProvider`; `Cached`/`Travelpayouts` deferred to Plan 2 (explicitly out of this slice). ✓
- Hybrid date model — order + ±N offset (spec 2, 3.4): Task 7 schedule + Tasks 8/9 iterate offsets. ✓
- Brute-force engine + Held-Karp + oracle (spec 3.4): Tasks 8, 9. ✓
- Route shape origin→cities→return (spec 2): Task 7 test asserts the chain. ✓
- Data model grain / Fare fields (spec 7): Task 4 `Fare`. ✓ (Parquet persistence is Plan 2.)
- Guardrail "max 8 cities" / synthetic fallback / Travelpayouts / API / frontend / CI / deploy: **deferred to Plans 2–5** (intentional; not gaps in this plan).

**2. Placeholder scan:** No "TBD/TODO/handle later". The only forward reference is `runner.py` → `heldkarp.py`, called out explicitly with a stub workaround (Task 8 ordering note). ✓

**3. Type consistency:** `Fare(origin, destination, fly_date, price, currency, source)` used consistently; `build_legs_dates` returns `(origin, destination, fly_date)` tuples consumed identically in bruteforce and heldkarp; `optimize(request, provider, engine)` signature matches both test files; `TripResult(best, alternatives)` and `Itinerary(order, start_offset, legs, total)` consistent across Tasks 6/8/9. ✓

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session with checkpoints for review.
