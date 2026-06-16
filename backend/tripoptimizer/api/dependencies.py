"""Process-wide singletons for the API: airport reference data + fare provider.

The data path defaults to the committed sample CSV and can be overridden with
the ``TRIPOPTIMIZER_AIRPORTS_CSV`` env var (no hardcoded absolute paths).
"""

import functools
import os
from pathlib import Path

from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.graph.airports import Airport, load_airports

_DEFAULT_AIRPORTS_CSV = Path(__file__).resolve().parents[2] / "data" / "airports_sample.csv"


def _airports_csv_path() -> Path:
    override = os.environ.get("TRIPOPTIMIZER_AIRPORTS_CSV")
    return Path(override) if override else _DEFAULT_AIRPORTS_CSV


@functools.lru_cache(maxsize=1)
def get_airports() -> dict[str, Airport]:
    """Load airports once per process. The CSV path is resolved on the first call;
    tests that override ``TRIPOPTIMIZER_AIRPORTS_CSV`` must call
    ``get_airports.cache_clear()`` first to pick up the new path."""
    return load_airports(_airports_csv_path())


@functools.lru_cache(maxsize=1)
def get_provider() -> SyntheticProvider:
    return SyntheticProvider(get_airports())
