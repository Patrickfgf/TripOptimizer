"""Ingestion: collect a grid via a provider, build a byte-stable curated snapshot."""

import datetime as dt
import sys
from pathlib import Path

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.travelpayouts import TravelpayoutsProvider
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
