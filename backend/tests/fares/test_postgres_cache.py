"""Durable Postgres FareCacheStore tests.

Hermetic by default: a fake pool/connection records the SQL + params and feeds
canned rows, so the store's logic (get/put, TTL staleness, parameterization,
degrade-on-DB-error) is tested without any database. One opt-in integration test
exercises real UPSERT round-trip against TEST_DATABASE_URL (skipped otherwise).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import os

import pytest

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.postgres_cache import DEFAULT_TTL, PostgresFareCache

DATE = dt.date(2026, 7, 1)
NOW = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)


class _FakeConn:
    """Stand-in for a psycopg connection: records execute() calls, returns a
    canned fetchone() row, and can be flipped to raise to simulate a dead DB."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple | None]] = []
        self.row: tuple | None = None
        self.fail = False

    def execute(self, sql: str, params: tuple | None = None) -> "_FakeConn":
        self.calls.append((sql, params))
        if self.fail:
            raise RuntimeError("db down")
        return self  # acts as its own cursor for .fetchone()

    def fetchone(self) -> tuple | None:
        return self.row


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    @contextlib.contextmanager
    def connection(self):
        yield self.conn


def _cache(conn: _FakeConn, *, ttl: dt.timedelta | None = DEFAULT_TTL) -> PostgresFareCache:
    return PostgresFareCache(_FakePool(conn), ttl=ttl, now=lambda: NOW)


def _last_relevant_call(conn: _FakeConn, needle: str) -> tuple[str, tuple | None]:
    """The most recent recorded call whose SQL contains `needle` (skips schema DDL)."""
    for sql, params in reversed(conn.calls):
        if needle.lower() in sql.lower():
            return sql, params
    raise AssertionError(f"no call containing {needle!r} was recorded")


def test_get_returns_none_on_miss() -> None:
    conn = _FakeConn()
    conn.row = None
    assert _cache(conn).get("LIS", "BCN", DATE) is None


def test_get_returns_fare_for_fresh_row() -> None:
    conn = _FakeConn()
    conn.row = (50.0, "EUR", "cached", NOW - dt.timedelta(days=1))

    got = _cache(conn).get("LIS", "BCN", DATE)

    assert got == Fare("LIS", "BCN", DATE, 50.0, "EUR", "cached")


def test_get_treats_stale_row_as_miss() -> None:
    conn = _FakeConn()
    conn.row = (50.0, "EUR", "cached", NOW - dt.timedelta(days=10))  # older than 7d TTL

    assert _cache(conn).get("LIS", "BCN", DATE) is None


def test_get_keeps_row_on_the_ttl_boundary() -> None:
    conn = _FakeConn()
    conn.row = (50.0, "EUR", "cached", NOW - DEFAULT_TTL + dt.timedelta(seconds=1))

    assert _cache(conn).get("LIS", "BCN", DATE) is not None


def test_ttl_none_never_expires() -> None:
    conn = _FakeConn()
    conn.row = (50.0, "EUR", "cached", NOW - dt.timedelta(days=999))

    assert _cache(conn, ttl=None).get("LIS", "BCN", DATE) is not None


def test_get_passes_key_as_parameters_not_interpolated() -> None:
    conn = _FakeConn()
    conn.row = None

    _cache(conn).get("LIS", "BCN", DATE)

    sql, params = _last_relevant_call(conn, "select")
    assert params == ("LIS", "BCN", DATE)
    assert "LIS" not in sql  # value bound as a parameter, never spliced into SQL


def test_put_issues_parameterized_upsert() -> None:
    conn = _FakeConn()
    cache = _cache(conn)

    cache.put(Fare("LIS", "BCN", DATE, 42.0, "EUR", "cached"))

    sql, params = _last_relevant_call(conn, "on conflict")
    assert params == ("LIS", "BCN", DATE, 42.0, "EUR", "cached")
    assert "42.0" not in sql  # price bound as a parameter, not f-stringed in


def test_get_degrades_to_none_on_db_error() -> None:
    conn = _FakeConn()
    conn.fail = True  # schema init also fails here, and must be swallowed too
    cache = PostgresFareCache(_FakePool(conn), now=lambda: NOW)

    assert cache.get("LIS", "BCN", DATE) is None  # degrade, do not raise


def test_put_swallows_db_error() -> None:
    conn = _FakeConn()
    conn.fail = True
    cache = PostgresFareCache(_FakePool(conn), now=lambda: NOW)

    cache.put(Fare("LIS", "BCN", DATE, 42.0, "EUR", "cached"))  # must not raise


def test_construction_survives_schema_error() -> None:
    conn = _FakeConn()
    conn.fail = True

    PostgresFareCache(_FakePool(conn), now=lambda: NOW)  # must not raise


@pytest.mark.integration
def test_roundtrip_against_real_postgres() -> None:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("set TEST_DATABASE_URL to run the Postgres integration test")
    psycopg_pool = pytest.importorskip("psycopg_pool")

    pool = psycopg_pool.ConnectionPool(dsn, min_size=0, max_size=2, open=False)
    pool.open()
    try:
        cache = PostgresFareCache(pool)
        cache.put(Fare("LIS", "BCN", DATE, 77.0, "EUR", "cached"))

        got = cache.get("LIS", "BCN", DATE)

        assert got is not None and got.price == 77.0 and got.source == "cached"
    finally:
        with pool.connection() as conn:
            conn.execute(
                "DELETE FROM fare_cache WHERE origin=%s AND destination=%s AND fly_date=%s",
                ("LIS", "BCN", DATE),
            )
        pool.close()


def test_get_logs_warning_on_db_error(caplog) -> None:
    import logging

    conn = _FakeConn()
    conn.fail = True
    with caplog.at_level(logging.WARNING, logger="tripoptimizer.core.fares.postgres_cache"):
        cache = PostgresFareCache(_FakePool(conn), now=lambda: NOW)
        cache.get("LIS", "BCN", DATE)
    assert any("get failed" in r.getMessage() for r in caplog.records)


def test_construction_reraises_on_insufficient_privilege() -> None:
    # A permanent DDL-permission error (SQLSTATE 42501) must fail loud, not be
    # swallowed like a transient outage — else the cache silently never works.
    class _PermissionError(Exception):
        pgcode = "42501"

    class _DenyingConn(_FakeConn):
        def execute(self, sql: str, params: tuple | None = None) -> "_FakeConn":
            raise _PermissionError("permission denied")

    with pytest.raises(_PermissionError):
        PostgresFareCache(_FakePool(_DenyingConn()), now=lambda: NOW)


def test_get_handles_timezone_naive_fetched_at() -> None:
    # Defensive: if a driver ever returns a tz-naive TIMESTAMPTZ, treat it as UTC
    # instead of raising a TypeError that would degrade into a silent miss.
    conn = _FakeConn()
    conn.row = (50.0, "EUR", "cached", (NOW - dt.timedelta(days=1)).replace(tzinfo=None))

    assert _cache(conn).get("LIS", "BCN", DATE) is not None
