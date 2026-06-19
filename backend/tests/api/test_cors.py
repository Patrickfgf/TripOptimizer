import logging

from fastapi.testclient import TestClient

from tripoptimizer.api.app import create_app


def test_warns_when_frontend_origins_unset(monkeypatch, caplog):
    monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)
    with caplog.at_level(logging.WARNING, logger="tripoptimizer.api"):
        create_app()
    assert any("FRONTEND_ORIGINS" in record.message for record in caplog.records)


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
