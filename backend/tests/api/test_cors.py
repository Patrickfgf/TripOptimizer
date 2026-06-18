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
