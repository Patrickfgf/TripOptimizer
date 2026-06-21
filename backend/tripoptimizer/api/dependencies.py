"""Process-wide singletons for the API: airports, fare provider, snapshot metadata.

The serving provider is a FallbackFareProvider(Cached -> Synthetic): real cached
fares when present, deterministic synthetic otherwise, so the demo never fails.
Paths resolve from the committed data dir or env overrides (no hardcoded absolutes).
"""

import datetime as dt
import functools
import os
from pathlib import Path

from tripoptimizer.core.fares.cached import CachedProvider
from tripoptimizer.core.fares.chain import FallbackFareProvider
from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.graph.airports import Airport, load_airports
from tripoptimizer.ingestion.snapshot import latest_snapshot_date

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_AIRPORTS_CSV = _DATA_DIR / "airports_sample.csv"
_DEFAULT_SNAPSHOT = _DATA_DIR / "fares_snapshot.parquet"


def _airports_csv_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_AIRPORTS_CSV")
    return Path(override) if override else _DEFAULT_AIRPORTS_CSV


def _snapshot_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_SNAPSHOT")
    return Path(override) if override else _DEFAULT_SNAPSHOT


@functools.lru_cache(maxsize=1)
def get_airports() -> dict[str, Airport]:
    return load_airports(_airports_csv_path())


@functools.lru_cache(maxsize=1)
def get_provider() -> FallbackFareProvider:
    return FallbackFareProvider(
        [
            CachedProvider(_snapshot_path()),
            SyntheticProvider(get_airports()),
        ]
    )


@functools.lru_cache(maxsize=1)
def get_snapshot_date() -> dt.date | None:
    path = _snapshot_path()
    return latest_snapshot_date(str(path)) if path.is_file() else None
