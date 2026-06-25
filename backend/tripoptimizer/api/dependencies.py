"""Process-wide singletons for the API: airports, fare provider, snapshot metadata.

The serving provider is a FallbackFareProvider(Cached -> [CachingLive] -> Synthetic):
real cached fares from the committed snapshot first, then on-demand live fares
(fetched once and cached in-process) when a Travelpayouts token is configured,
then deterministic synthetic so the demo never fails. Paths resolve from the
committed data dir or env overrides (no hardcoded absolutes).
"""

import datetime as dt
import functools
import os
from pathlib import Path

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.fares.cached import CachedProvider
from tripoptimizer.core.fares.chain import FallbackFareProvider
from tripoptimizer.core.fares.on_demand import (
    CachingLiveProvider,
    InMemoryFareCache,
    SafeLiveProvider,
)
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


def live_fares_enabled() -> bool:
    """On-demand live fetching is on only when a Travelpayouts token is configured."""
    return bool(os.environ.get("TRAVELPAYOUTS_TOKEN"))


@functools.lru_cache(maxsize=1)
def get_airports() -> dict[str, Airport]:
    return load_airports(_airports_csv_path())


@functools.lru_cache(maxsize=1)
def get_fare_cache() -> InMemoryFareCache:
    """Process-lifetime on-demand fare cache (resets on restart)."""
    return InMemoryFareCache()


def _live_provider() -> FareProvider:
    import atexit

    import httpx

    from tripoptimizer.core.fares.travelpayouts import TravelpayoutsProvider

    token = os.environ["TRAVELPAYOUTS_TOKEN"]
    market = os.environ.get("TRAVELPAYOUTS_MARKET", "es")
    # httpx.Client is thread-safe for concurrent use (prefetch fans out across
    # threads). It's an lru_cache-owned, process-lifetime singleton, so close its
    # connection pool at interpreter exit instead of leaking it.
    client = httpx.Client(timeout=20.0)
    atexit.register(client.close)
    live = TravelpayoutsProvider(token, client=client, market=market)
    return CachingLiveProvider(SafeLiveProvider(live), get_fare_cache())


@functools.lru_cache(maxsize=1)
def get_provider() -> FareProvider:
    providers: list[FareProvider] = [CachedProvider(_snapshot_path())]
    if live_fares_enabled():
        providers.append(_live_provider())
    providers.append(SyntheticProvider(get_airports()))
    return FallbackFareProvider(providers)


@functools.lru_cache(maxsize=1)
def get_snapshot_date() -> dt.date | None:
    path = _snapshot_path()
    return latest_snapshot_date(str(path)) if path.is_file() else None
