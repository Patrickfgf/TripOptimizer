"""Typed, idempotent Parquet snapshot I/O via DuckDB.

Grain: one row = origin x destination x fly_date. Writing dedups on that grain
(newest snapshot_date wins), casts explicit types (DATE, DOUBLE), and sorts by the
full key so re-running on the same input yields byte-identical Parquet.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb

# Columns/types of the curated snapshot. price MUST be cast DOUBLE (literals infer DECIMAL).
_WRITE_SQL = """
COPY (
    SELECT origin, destination,
           CAST(fly_date AS DATE)        AS fly_date,
           CAST(price AS DOUBLE)         AS price,
           currency, source,
           CAST(snapshot_date AS DATE)   AS snapshot_date
    FROM (
        SELECT *, row_number() OVER (
            PARTITION BY origin, destination, CAST(fly_date AS DATE)
            ORDER BY CAST(snapshot_date AS DATE) DESC, price ASC
        ) AS rn
        FROM raw
    )
    WHERE rn = 1
    ORDER BY origin, destination, fly_date
) TO ? (FORMAT parquet, COMPRESSION zstd)
"""

_READ_CELL_SQL = """
SELECT price, currency, source
FROM read_parquet(?)
WHERE origin = ? AND destination = ? AND fly_date = CAST(? AS DATE)
LIMIT 1
"""

_LATEST_DATE_SQL = "SELECT max(snapshot_date) FROM read_parquet(?)"


def write_snapshot(rows: list[dict], out_path: str | Path) -> None:
    """Write rows to a typed, deduped, stably-sorted Parquet (full overwrite)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        # DuckDB cannot scan a raw list[dict] directly; load it into a typed temp
        # table (DATE/DOUBLE pinned here) so the COPY below stays type-stable.
        con.execute(
            "CREATE TEMP TABLE raw ("
            "origin VARCHAR, destination VARCHAR, fly_date DATE, "
            "price DOUBLE, currency VARCHAR, source VARCHAR, snapshot_date DATE)"
        )
        con.executemany(
            "INSERT INTO raw VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["origin"],
                    r["destination"],
                    r["fly_date"],
                    float(r["price"]),
                    r["currency"],
                    r["source"],
                    r["snapshot_date"],
                )
                for r in rows
            ],
        )
        con.execute(_WRITE_SQL, [str(out).replace("\\", "/")])
    finally:
        con.close()


def read_fare_cell(
    parquet_path: str, origin: str, destination: str, fly_date: dt.date
) -> tuple[float, str, str] | None:
    """Return (price, currency, source) for the cell, or None on a miss."""
    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(
            _READ_CELL_SQL,
            [parquet_path.replace("\\", "/"), origin, destination, fly_date.isoformat()],
        ).fetchone()
    finally:
        con.close()
    return (row[0], row[1], row[2]) if row else None


def latest_snapshot_date(parquet_path: str) -> dt.date | None:
    """Return the newest snapshot_date in the file, or None if empty/absent."""
    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(_LATEST_DATE_SQL, [parquet_path.replace("\\", "/")]).fetchone()
    finally:
        con.close()
    return row[0] if row and row[0] is not None else None
