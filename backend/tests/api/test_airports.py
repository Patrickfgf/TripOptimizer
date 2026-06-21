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
