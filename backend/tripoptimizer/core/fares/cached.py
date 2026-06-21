"""Fare provider backed by the committed Parquet snapshot (read via DuckDB).

Returns Fare(source="cached") on a hit (the spec's serving label), or None on a
miss so a FallbackFareProvider can fall through to the synthetic source. A missing
snapshot file is treated as all-misses (not an error) — the demo still works.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.ingestion.snapshot import read_fare_cell

CACHED_SOURCE = "cached"


class CachedProvider:
    def __init__(self, snapshot_path: str | Path):
        self._path = str(snapshot_path)
        self._exists = Path(snapshot_path).is_file()

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        if not self._exists:
            return None
        cell = read_fare_cell(self._path, origin, destination, fly_date)
        if cell is None:
            return None
        price, currency, _ingestion_source = cell
        return Fare(origin, destination, fly_date, price, currency, CACHED_SOURCE)
