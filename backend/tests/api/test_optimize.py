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
