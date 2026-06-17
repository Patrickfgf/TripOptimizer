"""Idempotent raw->curated ingestion CLI.

collect_rows() walks a grid of (origin != destination) x dates, querying a
FareProvider; misses are skipped (synthetic fallback fills them at serving time).
curate() writes the typed, deduped, stably-sorted Parquet. Re-running on the same
collected rows produces a byte-identical snapshot (the repo's idempotency rule).

Default CLI run (needs `uv sync --extra ingest` + TRAVELPAYOUTS_TOKEN in env):
    uv run python -m tripoptimizer.ingestion.build_snapshot \
        --airports LIS OPO MAD BCN CDG FCO BER ATH \
        --start 2026-07-01 --days 10 \
        --out data/fares_snapshot.parquet
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from itertools import permutations
from pathlib import Path

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.ingestion.snapshot import write_snapshot


def collect_rows(
    provider: FareProvider,
    airports: list[str],
    dates: list[dt.date],
    snapshot_date: dt.date,
) -> list[dict]:
    rows: list[dict] = []
    for origin, destination in permutations(airports, 2):
        for fly_date in dates:
            fare = provider.get_fare(origin, destination, fly_date)
            if fare is None:
                continue
            rows.append(
                {
                    "origin": fare.origin,
                    "destination": fare.destination,
                    "fly_date": fare.fly_date,
                    "price": fare.price,
                    "currency": fare.currency,
                    "source": fare.source,
                    "snapshot_date": snapshot_date,
                }
            )
    return rows


def curate(rows: list[dict], out_path: str | Path) -> None:
    """Write the curated snapshot (dedup + stable sort + typed, via DuckDB)."""
    write_snapshot(rows, out_path)


def _date_window(start: dt.date, days: int) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(days)]


def _build_provider() -> FareProvider:
    import httpx

    from tripoptimizer.core.fares.travelpayouts import TravelpayoutsProvider

    token = os.environ["TRAVELPAYOUTS_TOKEN"]  # KeyError if absent — fail fast
    market = os.environ.get("TRAVELPAYOUTS_MARKET", "es")
    return TravelpayoutsProvider(token, client=httpx.Client(timeout=20.0), market=market)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the curated fares snapshot.")
    parser.add_argument("--airports", nargs="+", required=True)
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    provider = _build_provider()
    today = dt.datetime.now().date()
    rows = collect_rows(provider, args.airports, _date_window(args.start, args.days), today)
    curate(rows, args.out)
    print(f"wrote {len(rows)} fares to {args.out}")


if __name__ == "__main__":
    main()
