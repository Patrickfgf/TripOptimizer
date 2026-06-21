"""Typed, idempotent Parquet snapshot I/O over DuckDB."""

import datetime as dt
from pathlib import Path

from tripoptimizer.ingestion.snapshot import (
    latest_snapshot_date,
    read_fare_cell,
    write_snapshot,
)

SNAP = dt.date(2026, 6, 16)


def _rows() -> list[dict]:
    return [
        {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
         "price": 48.9, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP},
        {"origin": "BCN", "destination": "FCO", "fly_date": dt.date(2026, 7, 4),
         "price": 61.5, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP},
    ]


def test_write_then_read_cell(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert out.exists()
    row = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert row is not None
    price, currency, source = row
    assert price == 48.9
    assert currency == "EUR"
    assert source == "travelpayouts"


def test_read_cell_miss_returns_none(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert read_fare_cell(str(out), "LIS", "ATH", dt.date(2026, 7, 1)) is None


def test_latest_snapshot_date(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    write_snapshot(_rows(), out)
    assert latest_snapshot_date(str(out)) == SNAP


def test_write_is_idempotent_byte_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    # Same input, shuffled + duplicated; dedup-on-key + stable sort must yield identical bytes.
    write_snapshot(_rows(), a)
    write_snapshot(list(reversed(_rows())) + _rows(), b)
    assert a.read_bytes() == b.read_bytes()


def test_dedup_keeps_newest_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "fares.parquet"
    older = {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
             "price": 99.0, "currency": "EUR", "source": "travelpayouts",
             "snapshot_date": dt.date(2026, 6, 1)}
    newer = {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1),
             "price": 48.9, "currency": "EUR", "source": "travelpayouts", "snapshot_date": SNAP}
    write_snapshot([older, newer], out)
    price, _, _ = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 48.9  # newer snapshot wins
