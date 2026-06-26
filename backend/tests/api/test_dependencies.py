"""The API loads airport reference data and composes the serving fare chain."""

from datetime import date

from tripoptimizer.api import dependencies
from tripoptimizer.api.dependencies import get_airports, get_provider, live_fares_enabled
from tripoptimizer.core.fares.on_demand import CachingLiveProvider


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
    assert fare.source == "synthetic"  # no token in tests -> Cached(absent) -> Synthetic


def test_live_fares_disabled_without_token(monkeypatch) -> None:
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
    assert live_fares_enabled() is False


def test_live_fares_enabled_with_token(monkeypatch) -> None:
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "dummy")
    assert live_fares_enabled() is True


def test_get_provider_inserts_caching_live_layer_with_token(monkeypatch) -> None:
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "dummy")
    dependencies.get_provider.cache_clear()
    dependencies.get_fare_cache.cache_clear()
    try:
        provider = get_provider()
        assert any(isinstance(p, CachingLiveProvider) for p in provider._providers)
    finally:
        dependencies.get_provider.cache_clear()
        dependencies.get_fare_cache.cache_clear()


def test_get_fare_cache_uses_postgres_when_database_url_set(monkeypatch) -> None:
    """With DATABASE_URL set, get_fare_cache builds a PostgresFareCache, honors
    FARE_CACHE_TTL_DAYS, and registers pool.close at exit (no leaked pool)."""
    import contextlib
    import datetime as dt

    import psycopg_pool

    from tripoptimizer.core.fares.postgres_cache import PostgresFareCache

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setenv("FARE_CACHE_TTL_DAYS", "3")
    registered: list = []

    class _FakeConn:
        def execute(self, sql, params=None):
            return self

        def fetchone(self):
            return None

    class _FakePool:
        def __init__(self, dsn, **kwargs):
            self.opened = False

        def open(self):
            self.opened = True

        @contextlib.contextmanager
        def connection(self):
            yield _FakeConn()

        def close(self):
            pass

    monkeypatch.setattr(psycopg_pool, "ConnectionPool", _FakePool)
    monkeypatch.setattr("atexit.register", registered.append)
    dependencies.get_fare_cache.cache_clear()
    try:
        cache = dependencies.get_fare_cache()
        assert isinstance(cache, PostgresFareCache)
        assert cache._ttl == dt.timedelta(days=3)  # FARE_CACHE_TTL_DAYS honored
        assert registered  # pool.close registered for cleanup -> no leaked pool
    finally:
        dependencies.get_fare_cache.cache_clear()
