"""Durable Postgres-backed FareCacheStore.

A drop-in alternative to InMemoryFareCache (same FareCacheStore Protocol) that
survives process restarts — the unlock for serving 90-day / all-Europe grids
without re-paying the live API cost on every Render cold start.

Resilient by design: every DB error in get/put/schema-init is logged and
swallowed, so a database outage degrades serving to a *cold* cache (each request
falls through to the live provider) instead of 500ing. FallbackFareProvider does
not catch store errors, so the store must contain its own failures — the same
degrade-don't-crash contract SafeLiveProvider gives the live fetch layer.

Staleness (TTL) is evaluated in Python against an injected clock, not in SQL, so
it is trivially unit-testable and TTL=None means "never expire". App/DB clock
skew is immaterial at the day-scale TTL this cache uses. Discarded alternative:
filtering `fetched_at > now() - interval` in SQL (one authoritative clock, one
round-trip) — rejected because it complicates the None-TTL case and the hermetic
fake, for a correctness gain that doesn't matter at 7-day granularity.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from tripoptimizer.core.fares.models import Fare

logger = logging.getLogger(__name__)

DEFAULT_TTL = dt.timedelta(days=7)  # matches Travelpayouts' ~48h-fresh / up-to-7-day cache

# PostgreSQL SQLSTATE for "insufficient_privilege" — a permanent misconfig (the DB
# user lacks CREATE), distinct from a transient outage. Checked via getattr(exc,
# "pgcode") so the module stays psycopg-import-free.
_INSUFFICIENT_PRIVILEGE = "42501"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fare_cache (
    origin       TEXT NOT NULL,
    destination  TEXT NOT NULL,
    fly_date     DATE NOT NULL,
    price        DOUBLE PRECISION NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'EUR',
    source       TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (origin, destination, fly_date)
)
"""

_SELECT_SQL = (
    "SELECT price, currency, source, fetched_at FROM fare_cache "
    "WHERE origin = %s AND destination = %s AND fly_date = %s"
)

_UPSERT_SQL = (
    "INSERT INTO fare_cache "
    "(origin, destination, fly_date, price, currency, source, fetched_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, now()) "
    "ON CONFLICT (origin, destination, fly_date) DO UPDATE SET "
    "price = EXCLUDED.price, currency = EXCLUDED.currency, "
    "source = EXCLUDED.source, fetched_at = now()"
)


class _Result(Protocol):
    def fetchone(self) -> tuple | None: ...


class _Connection(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> _Result: ...


class _ConnectionPool(Protocol):
    """The slice of psycopg_pool.ConnectionPool this store needs (kept narrow so
    tests can pass a fake and the module never imports psycopg)."""

    def connection(self) -> AbstractContextManager[_Connection]: ...


class PostgresFareCache:
    def __init__(
        self,
        pool: _ConnectionPool,
        *,
        ttl: dt.timedelta | None = DEFAULT_TTL,
        now: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._pool = pool
        self._ttl = ttl
        self._now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._ensure_schema()

    def get(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_SELECT_SQL, (origin, destination, fly_date)).fetchone()
        except Exception as exc:  # noqa: BLE001 - serving degrades to a cold cache, never crashes
            # No exc_info: psycopg connection errors can embed the DSN (with the
            # password) in their traceback/repr — log only the exception type.
            logger.warning(
                "fare_cache get failed for %s->%s on %s: %s",
                origin,
                destination,
                fly_date,
                type(exc).__name__,
            )
            return None
        if row is None:
            return None
        price, currency, source, fetched_at = row
        if self._is_stale(fetched_at):
            return None
        return Fare(origin, destination, fly_date, float(price), currency, source)

    def put(self, fare: Fare) -> None:
        try:
            with self._pool.connection() as conn:
                conn.execute(
                    _UPSERT_SQL,
                    (
                        fare.origin,
                        fare.destination,
                        fare.fly_date,
                        fare.price,
                        fare.currency,
                        fare.source,
                    ),
                )
        except Exception as exc:  # noqa: BLE001 - a cache write failure must never break serving
            logger.warning(
                "fare_cache put failed for %s->%s on %s: %s",
                fare.origin,
                fare.destination,
                fare.fly_date,
                type(exc).__name__,
            )

    def _ensure_schema(self) -> None:
        # Idempotent (CREATE TABLE IF NOT EXISTS). Run once at construction; a
        # transient DB outage here degrades safely (get/put miss until restart),
        # but a *permanent* misconfig (no CREATE privilege) is re-raised so the
        # deploy fails loud instead of silently never caching.
        try:
            with self._pool.connection() as conn:
                conn.execute(_SCHEMA_SQL)
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "pgcode", None) == _INSUFFICIENT_PRIVILEGE:
                raise
            logger.warning("fare_cache schema init failed: %s", type(exc).__name__)

    def _is_stale(self, fetched_at: dt.datetime | None) -> bool:
        if self._ttl is None or fetched_at is None:
            return False
        if fetched_at.tzinfo is None:  # TIMESTAMPTZ is tz-aware in psycopg3; normalize defensively
            fetched_at = fetched_at.replace(tzinfo=dt.timezone.utc)
        return self._now() - fetched_at > self._ttl
