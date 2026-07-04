"""Idempotent raw->curated ingestion CLI.

collect_rows() walks a grid of (origin != destination) x months covering the
requested date window, querying a MonthFareSource concurrently — one call
returns a whole month of fares (~30x fewer calls than the old per-date grid,
and measured ~48% vs ~31% coverage); misses and transient per-pair-month
failures are skipped (those cells simply stay unpriced at serving). curate()
writes the typed, deduped, stably-sorted Parquet. Re-running on the same
collected rows produces a byte-identical snapshot (the repo's idempotency rule).

Default CLI run (needs `uv sync --extra ingest` + TRAVELPAYOUTS_TOKEN in env):
    uv run python -m tripoptimizer.ingestion.build_snapshot \
        --start 2026-07-01 --days 90 --workers 8 \
        --out data/fares_snapshot.parquet

The airport universe defaults to data/airports_sample.csv (the serving list),
so snapshot and serving cannot silently diverge; --airports overrides it for
ad-hoc runs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations
from pathlib import Path

import httpx

from tripoptimizer.core.fares.on_demand import MonthFareSource
from tripoptimizer.core.fares.travelpayouts import RateLimited
from tripoptimizer.core.graph.airports import load_airports
from tripoptimizer.ingestion.snapshot import write_snapshot

_DEFAULT_WORKERS = 8
_DEFAULT_AIRPORTS_CSV = Path(__file__).resolve().parents[2] / "data" / "airports_sample.csv"
# Per-pair-month failures we tolerate by skipping the block (its cells stay
# unpriced at serving): rate limiting, transport errors, 5xx, and 400-invalid
# routes (the API rejects e.g. same-city pairs) are all expected on large grids
# and must not crash the whole run. Only 401/403 (auth) is systemic and is left
# to propagate so the run fails loudly instead of writing an empty snapshot.
_SKIP_ERRORS = (RateLimited, httpx.TransportError)


def _fetch_pair_month(
    source: MonthFareSource,
    origin: str,
    destination: str,
    month: dt.date,
    window: set[dt.date],
    snapshot_date: dt.date,
) -> list[dict]:
    try:
        fares = source.get_month(origin, destination, month)
    except _SKIP_ERRORS:
        return []
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise  # auth is systemic — fail loud instead of writing an empty snapshot
        # Anything else is a per-pair-month condition — skip the block: 5xx is
        # transient, and the API 400s pairs it considers invalid routes (e.g.
        # same-city CDG->ORY, observed live on the 98-airport grid).
        return []
    return [
        {
            "origin": fare.origin,
            "destination": fare.destination,
            "fly_date": fare.fly_date,
            "price": fare.price,
            "currency": fare.currency,
            "source": fare.source,
            "snapshot_date": snapshot_date,
        }
        for day, fare in sorted(fares.items())
        if day in window
    ]


def _months(dates: list[dt.date]) -> list[dt.date]:
    """The sorted first-of-month dates covering the window."""
    return sorted({d.replace(day=1) for d in dates})


def collect_rows(
    source: MonthFareSource,
    airports: list[str],
    dates: list[dt.date],
    snapshot_date: dt.date,
    max_workers: int = _DEFAULT_WORKERS,
) -> list[dict]:
    """Fetch every (origin != destination) x month block concurrently.

    The month payload is filtered to the requested window; results are gathered
    in submit order, so the output is deterministic regardless of completion
    order. Misses and transient failures drop out.
    """
    window = set(dates)
    tasks = [
        (origin, destination, month)
        for origin, destination in permutations(airports, 2)
        for month in _months(dates)
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(
                _fetch_pair_month, source, origin, destination, month, window, snapshot_date
            )
            for origin, destination, month in tasks
        ]
        blocks = [future.result() for future in futures]
    return [row for block in blocks for row in block]


def curate(rows: list[dict], out_path: str | Path) -> None:
    """Write the curated snapshot (dedup + stable sort + typed, via DuckDB)."""
    write_snapshot(rows, out_path)


def coverage_line(rows: list[dict], airports: list[str], dates: list[dt.date]) -> str:
    """One-line HIT summary — quantifies the real-fare gap a Tier 2 source would fill."""
    routes = len(airports) * (len(airports) - 1)
    cells = routes * len(dates)
    priced_routes = {(row["origin"], row["destination"]) for row in rows}
    pct = 100.0 * len(rows) / cells if cells else 0.0
    return (
        f"coverage: {len(rows)}/{cells} cells ({pct:.1f}%), "
        f"{len(priced_routes)}/{routes} routes with >=1 fare"
    )


def _date_window(start: dt.date, days: int) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(days)]


def _build_source() -> MonthFareSource:
    from tripoptimizer.core.fares.month_matrix import MonthMatrixProvider

    token = os.environ["TRAVELPAYOUTS_TOKEN"]  # KeyError if absent — fail fast
    return MonthMatrixProvider(token, client=httpx.Client(timeout=20.0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the curated fares snapshot.")
    parser.add_argument(
        "--airports", nargs="+", help="explicit IATA list; overrides --airports-csv"
    )
    parser.add_argument(
        "--airports-csv",
        type=Path,
        default=_DEFAULT_AIRPORTS_CSV,
        help="CSV defining the airport universe (default: the serving list)",
    )
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--workers", type=int, default=_DEFAULT_WORKERS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    airports = args.airports or list(load_airports(args.airports_csv))
    source = _build_source()
    today = dt.datetime.now().date()
    dates = _date_window(args.start, args.days)
    rows = collect_rows(source, airports, dates, today, max_workers=args.workers)
    curate(rows, args.out)
    print(f"wrote {len(rows)} fares to {args.out}")
    print(coverage_line(rows, airports, dates))


if __name__ == "__main__":
    main()
