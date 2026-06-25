"""Idempotent raw->curated ingestion CLI.

collect_rows() walks a grid of (origin != destination) x dates, querying a
FareProvider concurrently; misses and transient per-cell failures are skipped
(synthetic fallback fills them at serving time). curate() writes the typed,
deduped, stably-sorted Parquet. Re-running on the same collected rows produces a
byte-identical snapshot (the repo's idempotency rule).

Default CLI run (needs `uv sync --extra ingest` + TRAVELPAYOUTS_TOKEN in env):
    uv run python -m tripoptimizer.ingestion.build_snapshot \
        --airports LIS OPO MAD BCN CDG FCO BER ATH \
        --start 2026-07-01 --days 10 --workers 8 \
        --out data/fares_snapshot.parquet
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations
from pathlib import Path

import httpx

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.fares.travelpayouts import RateLimited
from tripoptimizer.ingestion.snapshot import write_snapshot

_DEFAULT_WORKERS = 8
# Per-cell failures we tolerate by skipping the cell (synthetic fills it at
# serving): rate limiting and transport errors (timeouts/connection resets) are
# expected on large grids and must not crash the whole run. A 5xx is also a
# transient per-cell skip; a 4xx (e.g. 401 bad token) is systemic and is left
# to propagate so the run fails loudly instead of writing an empty snapshot.
_SKIP_ERRORS = (RateLimited, httpx.TransportError)


def _fetch_row(
    provider: FareProvider,
    origin: str,
    destination: str,
    fly_date: dt.date,
    snapshot_date: dt.date,
) -> dict | None:
    try:
        fare = provider.get_fare(origin, destination, fly_date)
    except _SKIP_ERRORS:
        return None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            return None  # transient server error on this cell — skip
        raise  # 4xx (e.g. 401 bad token) is systemic — fail loud
    if fare is None:
        return None
    return {
        "origin": fare.origin,
        "destination": fare.destination,
        "fly_date": fare.fly_date,
        "price": fare.price,
        "currency": fare.currency,
        "source": fare.source,
        "snapshot_date": snapshot_date,
    }


def collect_rows(
    provider: FareProvider,
    airports: list[str],
    dates: list[dt.date],
    snapshot_date: dt.date,
    max_workers: int = _DEFAULT_WORKERS,
) -> list[dict]:
    """Fetch every (origin != destination) x date cell concurrently.

    Results are gathered in submit order, so the output is deterministic
    regardless of completion order; misses and transient failures drop out.
    """
    tasks = [
        (origin, destination, fly_date)
        for origin, destination in permutations(airports, 2)
        for fly_date in dates
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_fetch_row, provider, origin, destination, fly_date, snapshot_date)
            for origin, destination, fly_date in tasks
        ]
        rows = [future.result() for future in futures]
    return [row for row in rows if row is not None]


def curate(rows: list[dict], out_path: str | Path) -> None:
    """Write the curated snapshot (dedup + stable sort + typed, via DuckDB)."""
    write_snapshot(rows, out_path)


def _date_window(start: dt.date, days: int) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(days)]


def _build_provider() -> FareProvider:
    from tripoptimizer.core.fares.travelpayouts import TravelpayoutsProvider

    token = os.environ["TRAVELPAYOUTS_TOKEN"]  # KeyError if absent — fail fast
    market = os.environ.get("TRAVELPAYOUTS_MARKET", "es")
    return TravelpayoutsProvider(token, client=httpx.Client(timeout=20.0), market=market)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the curated fares snapshot.")
    parser.add_argument("--airports", nargs="+", required=True)
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--workers", type=int, default=_DEFAULT_WORKERS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    provider = _build_provider()
    today = dt.datetime.now().date()
    rows = collect_rows(
        provider,
        args.airports,
        _date_window(args.start, args.days),
        today,
        max_workers=args.workers,
    )
    curate(rows, args.out)
    print(f"wrote {len(rows)} fares to {args.out}")


if __name__ == "__main__":
    main()
