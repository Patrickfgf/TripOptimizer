"""Ingestion: collect a grid via a provider, build a byte-stable curated snapshot."""

import datetime as dt
import sys
import threading
from pathlib import Path

import httpx
import pytest

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.travelpayouts import RateLimited, TravelpayoutsProvider
from tripoptimizer.ingestion import build_snapshot
from tripoptimizer.ingestion.build_snapshot import collect_rows, curate
from tripoptimizer.ingestion.snapshot import read_fare_cell

SNAP = dt.date(2026, 6, 16)


class _FakeProvider:
    """Returns a deterministic fare for known pairs, None for one blacklisted pair."""

    def get_fare(self, origin, destination, fly_date):
        if (origin, destination) == ("LIS", "ZZZ"):
            return None
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_collect_rows_skips_self_pairs() -> None:
    rows = collect_rows(
        _FakeProvider(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "LIS") not in pairs  # no self-pairs
    assert ("LIS", "BCN") in pairs and ("BCN", "LIS") in pairs
    assert all(r["snapshot_date"] == SNAP for r in rows)


def test_collect_rows_skips_misses() -> None:
    rows = collect_rows(
        _FakeProvider(),
        airports=["LIS", "ZZZ"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "ZZZ") not in pairs  # provider returned None -> skipped
    assert ("ZZZ", "LIS") in pairs  # the reverse pair is not blacklisted


def test_curate_is_idempotent_byte_identical(tmp_path: Path) -> None:
    rows = collect_rows(
        _FakeProvider(), airports=["LIS", "BCN"], dates=[dt.date(2026, 7, 1)], snapshot_date=SNAP
    )
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    curate(rows, a)
    curate(rows, b)
    assert a.read_bytes() == b.read_bytes()
    price, _, source = read_fare_cell(str(a), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 50.0 and source == "travelpayouts"


def test_date_window_is_contiguous() -> None:
    window = build_snapshot._date_window(dt.date(2026, 7, 1), 3)
    assert window == [dt.date(2026, 7, 1), dt.date(2026, 7, 2), dt.date(2026, 7, 3)]


def test_build_provider_reads_token_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "dummy")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKET", "fr")
    provider = build_snapshot._build_provider()
    assert isinstance(provider, TravelpayoutsProvider)


def test_main_writes_snapshot_via_injected_provider(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "snap.parquet"
    monkeypatch.setattr(build_snapshot, "_build_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_snapshot",
            "--airports",
            "LIS",
            "BCN",
            "--start",
            "2026-07-01",
            "--days",
            "1",
            "--out",
            str(out),
        ],
    )
    build_snapshot.main()
    assert out.exists()
    price, _, source = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 50.0 and source == "travelpayouts"


class _RaisingProvider:
    """Raises a transient RateLimited for one pair; returns a fare otherwise."""

    def get_fare(self, origin, destination, fly_date):
        if (origin, destination) == ("LIS", "BCN"):
            raise RateLimited()
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_collect_rows_skips_cells_that_raise_transient_errors() -> None:
    rows = collect_rows(
        _RaisingProvider(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=2,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "BCN") not in pairs  # raised -> skipped, the run is not crashed
    assert ("BCN", "LIS") in pairs


class _ConcurrencyProbe:
    """Proves >1 fare is fetched at once: a barrier that only releases in pairs."""

    def __init__(self, parties: int) -> None:
        self._barrier = threading.Barrier(parties, timeout=3)
        self.ran_concurrently = False

    def get_fare(self, origin, destination, fly_date):
        try:
            self._barrier.wait()
            self.ran_concurrently = True
        except threading.BrokenBarrierError:
            pass
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_collect_rows_runs_cells_concurrently() -> None:
    probe = _ConcurrencyProbe(parties=2)
    rows = collect_rows(
        probe,
        airports=["LIS", "BCN", "ROM"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=4,
    )
    assert probe.ran_concurrently is True  # two get_fare calls overlapped
    assert len(rows) == 6  # 3 airports -> 6 ordered pairs, all collected


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test")
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(code, request=request)
    )


class _StatusErrorProvider:
    def __init__(self, code: int) -> None:
        self._code = code

    def get_fare(self, origin, destination, fly_date):
        raise _status_error(self._code)


def test_collect_rows_skips_server_errors() -> None:
    rows = collect_rows(
        _StatusErrorProvider(503),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=2,
    )
    assert rows == []  # 5xx is a transient per-cell error -> skipped, no crash


def test_collect_rows_fails_loud_on_auth_error() -> None:
    # A 401/403 is systemic (bad token): it must crash the run, not silently
    # produce an empty snapshot.
    with pytest.raises(httpx.HTTPStatusError):
        collect_rows(
            _StatusErrorProvider(401),
            airports=["LIS", "BCN"],
            dates=[dt.date(2026, 7, 1)],
            snapshot_date=SNAP,
            max_workers=2,
        )
