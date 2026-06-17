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
    assert "snapshot_date" in body  # None when no snapshot committed yet


def test_health_degraded_when_reference_data_missing(monkeypatch) -> None:
    # Simulate the data layer being unavailable: the deep check must return 503.
    monkeypatch.setattr("tripoptimizer.api.routes.get_airports", dict)
    response = client.get("/health")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
