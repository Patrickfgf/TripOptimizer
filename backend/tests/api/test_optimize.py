"""Optimize endpoint: happy path (injected real provider) + honest incomplete result."""

import pytest
from fastapi.testclient import TestClient

from tripoptimizer.api import routes
from tripoptimizer.api.app import app
from tripoptimizer.core.fares.models import Fare

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


class _CompleteProvider:
    """Prices every leg with a real 'cached' fare, varied by endpoints so orderings differ."""

    def get_fare(self, origin, destination, fly_date):
        price = 50.0 + 10.0 * abs(ord(origin[0]) - ord(destination[0]))
        return Fare(origin, destination, fly_date, price, "EUR", "cached")


@pytest.fixture
def real_fares(monkeypatch):
    """Inject a provider that prices every leg, so the endpoint returns a full itinerary
    (the test env has an absent snapshot and no token, i.e. no real fares by default)."""
    monkeypatch.setattr(routes, "get_provider", lambda: _CompleteProvider())


def test_optimize_happy_path(real_fares) -> None:
    response = client.post("/optimize", json=_payload())
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert body["data_source"] == "cached"  # every leg real + uniform
    assert body["snapshot_date"] is None

    best = body["best"]
    assert sorted(best["order"]) == ["BCN", "CDG", "FCO"]
    assert best["total"] > 0
    # legs form a chain LIS -> ... -> LIS (3 cities => 4 legs)
    assert len(best["legs"]) == 4
    assert all(leg["source"] == "cached" for leg in best["legs"])
    assert best["legs"][0]["origin"] == "LIS"
    assert best["legs"][-1]["destination"] == "LIS"
    # total equals the sum of leg prices (within float tolerance)
    assert abs(best["total"] - sum(leg["price"] for leg in best["legs"])) < 1e-6

    # brute-force returns ranked alternatives, each >= best
    assert len(body["alternatives"]) >= 1
    assert all(alt["total"] >= best["total"] for alt in body["alternatives"])


def test_heldkarp_engine_returns_no_alternatives(real_fares) -> None:
    response = client.post("/optimize?engine=heldkarp", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["alternatives"] == []
    assert sorted(body["best"]["order"]) == ["BCN", "CDG", "FCO"]


def test_both_engines_agree_on_best_total(real_fares) -> None:
    bf = client.post("/optimize?engine=bruteforce", json=_payload()).json()
    hk = client.post("/optimize?engine=heldkarp", json=_payload()).json()
    assert abs(bf["best"]["total"] - hk["best"]["total"]) < 1e-6


def test_optimize_incomplete_when_no_real_fares() -> None:
    # No injected provider: absent snapshot + no token -> every cell unpriced. The API is
    # honest about it (status "incomplete") instead of fabricating a synthetic price.
    response = client.post("/optimize", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["missing_routes"]  # non-empty list of [origin, destination] pairs


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
