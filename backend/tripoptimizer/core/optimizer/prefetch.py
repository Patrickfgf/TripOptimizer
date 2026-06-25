"""Warm the fare cache for a trip's cells, concurrently, before optimizing.

A trip queries hundreds of (origin, destination, fly_date) cells across every
ordering and date offset. Fetching those one-by-one on a cold cache would stall
the request, so we enumerate the full cell set and fetch the missing ones in
parallel first — turning N sequential live calls into one concurrent batch,
bounded by a wall-clock budget so a slow source can't hold the request open.
"""

from __future__ import annotations

import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from itertools import permutations

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.schedule import build_legs_dates

_DEFAULT_WORKERS = 8
_DEFAULT_TIMEOUT_S = 15.0


def cells_for_request(request: TripRequest) -> set[tuple[str, str, dt.date]]:
    """Every (origin, destination, fly_date) any ordering x offset could query.

    Mirrors the bruteforce engine's enumeration (permutations x +/-flex offsets),
    so the set is a superset of what either engine looks up.
    """
    cells: set[tuple[str, str, dt.date]] = set()
    offsets = range(-request.flex_days, request.flex_days + 1)
    for order in permutations(request.cities):
        for offset in offsets:
            for origin, destination, fly_date in build_legs_dates(order, request, offset):
                cells.add((origin, destination, fly_date))
    return cells


def prefetch(
    request: TripRequest,
    provider: FareProvider,
    max_workers: int = _DEFAULT_WORKERS,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> None:
    """Concurrently call provider.get_fare for every trip cell, warming its cache.

    Pair with a CachingLiveProvider over a SafeLiveProvider: cache hits are cheap,
    misses fetch live + persist, and per-cell source failures degrade to None
    (synthetic fills them at optimize time). Stops at ``timeout_s`` so a slow or
    half-cold batch never holds the request open for cells x latency — cells not
    yet warmed simply fall back to synthetic when the engine runs.
    """
    cells = cells_for_request(request)
    deadline = time.monotonic() + timeout_s
    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = [
            pool.submit(provider.get_fare, origin, destination, fly_date)
            for origin, destination, fly_date in cells
        ]
        for future in futures:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                future.result(timeout=remaining)
            except FuturesTimeout:
                break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
