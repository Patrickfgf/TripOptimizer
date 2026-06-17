"""CachedProvider serves fares from the committed snapshot, None on a miss."""

import datetime as dt
from pathlib import Path

from tripoptimizer.core.fares.cached import CachedProvider
from tripoptimizer.ingestion.snapshot import write_snapshot

SNAP = dt.date(2026, 6, 16)


def _snapshot(tmp_path: Path) -> Path:
    out = tmp_path / "fares.parquet"
    write_snapshot(
        [
            {
                "origin": "LIS",
                "destination": "BCN",
                "fly_date": dt.date(2026, 7, 1),
                "price": 48.9,
                "currency": "EUR",
                "source": "travelpayouts",
                "snapshot_date": SNAP,
            }
        ],
        out,
    )
    return out


def test_cached_hit_returns_fare_labeled_cached(tmp_path: Path) -> None:
    provider = CachedProvider(_snapshot(tmp_path))
    fare = provider.get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert fare is not None
    assert fare.price == 48.9
    assert fare.currency == "EUR"
    assert fare.source == "cached"  # serving label, not the ingestion provenance


def test_cached_miss_returns_none(tmp_path: Path) -> None:
    provider = CachedProvider(_snapshot(tmp_path))
    assert provider.get_fare("LIS", "ATH", dt.date(2026, 7, 1)) is None


def test_missing_snapshot_file_yields_all_misses(tmp_path: Path) -> None:
    provider = CachedProvider(tmp_path / "does_not_exist.parquet")
    assert provider.get_fare("LIS", "BCN", dt.date(2026, 7, 1)) is None
