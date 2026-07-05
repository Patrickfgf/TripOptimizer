"""Ingestion: collect a (pair x month) grid via a month source, build a byte-stable snapshot."""

import datetime as dt
import sys
import threading
from pathlib import Path

import httpx
import pytest

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.month_matrix import MonthMatrixProvider
from tripoptimizer.core.fares.travelpayouts import RateLimited
from tripoptimizer.ingestion import build_snapshot
from tripoptimizer.ingestion.build_snapshot import collect_rows, coverage_line, curate
from tripoptimizer.ingestion.snapshot import read_fare_cell

SNAP = dt.date(2026, 6, 16)


def _whole_month(origin: str, destination: str, month: dt.date, price: float = 50.0):
    """Every day of ``month`` priced — what a dense month-matrix payload yields."""
    next_month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return {
        day: Fare(origin, destination, day, price, "EUR", "travelpayouts")
        for i in range((next_month - month).days)
        for day in [month + dt.timedelta(days=i)]
    }


class _FakeMonthSource:
    """A whole month of fares for known pairs; empty (a miss) for one blacklisted pair."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dt.date]] = []

    def get_month(self, origin, destination, month):
        self.calls.append((origin, destination, month))
        if (origin, destination) == ("LIS", "ZZZ"):
            return {}
        return _whole_month(origin, destination, month)


def test_collect_rows_skips_self_pairs() -> None:
    rows = collect_rows(
        _FakeMonthSource(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "LIS") not in pairs  # no self-pairs
    assert ("LIS", "BCN") in pairs and ("BCN", "LIS") in pairs
    assert all(r["snapshot_date"] == SNAP for r in rows)


def test_collect_rows_filters_to_requested_window() -> None:
    # The month source returns the WHOLE month; only the requested days survive.
    window = [dt.date(2026, 7, 1), dt.date(2026, 7, 2)]
    rows = collect_rows(
        _FakeMonthSource(), airports=["LIS", "BCN"], dates=window, snapshot_date=SNAP
    )
    assert {r["fly_date"] for r in rows} == set(window)
    assert len(rows) == 4  # 2 ordered pairs x 2 days


def test_collect_rows_makes_one_call_per_pair_month() -> None:
    source = _FakeMonthSource()
    window = build_snapshot._date_window(dt.date(2026, 7, 30), 4)  # Jul 30 .. Aug 2
    rows = collect_rows(source, airports=["LIS", "BCN"], dates=window, snapshot_date=SNAP)
    assert len(source.calls) == 4  # 2 ordered pairs x 2 months
    assert {m for _, _, m in source.calls} == {dt.date(2026, 7, 1), dt.date(2026, 8, 1)}
    # Both month payloads are full months; only the window survives from EACH side
    # of the boundary — no leakage of Jul 1-29 or Aug 3-31 into the snapshot.
    assert {r["fly_date"] for r in rows} == set(window)
    assert len(rows) == 2 * len(window)  # 2 ordered pairs x 4 days


def test_collect_rows_skips_misses() -> None:
    rows = collect_rows(
        _FakeMonthSource(),
        airports=["LIS", "ZZZ"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "ZZZ") not in pairs  # empty month payload -> skipped
    assert ("ZZZ", "LIS") in pairs  # the reverse pair is not blacklisted


def test_curate_is_idempotent_byte_identical(tmp_path: Path) -> None:
    rows = collect_rows(
        _FakeMonthSource(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
    )
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    curate(rows, a)
    curate(rows, b)
    assert a.read_bytes() == b.read_bytes()
    price, _, source = read_fare_cell(str(a), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 50.0 and source == "travelpayouts"


def test_date_window_is_contiguous() -> None:
    window = build_snapshot._date_window(dt.date(2026, 7, 1), 3)
    assert window == [dt.date(2026, 7, 1), dt.date(2026, 7, 2), dt.date(2026, 7, 3)]


def test_coverage_line_reports_priced_share() -> None:
    rows = [
        {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 1)},
        {"origin": "LIS", "destination": "BCN", "fly_date": dt.date(2026, 7, 2)},
    ]
    line = coverage_line(
        rows, airports=["LIS", "BCN"], dates=[dt.date(2026, 7, 1), dt.date(2026, 7, 2)]
    )
    assert "2/4 cells (50.0%)" in line
    assert "1/2 routes" in line


def test_build_source_reads_token_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "dummy")
    source = build_snapshot._build_source()
    assert isinstance(source, MonthMatrixProvider)


def test_main_writes_snapshot_via_injected_source(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "snap.parquet"
    monkeypatch.setattr(build_snapshot, "_build_source", lambda: _FakeMonthSource())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_snapshot",
            "--airports",
            "LIS",
            "BCN",
            "--start",
            "2026-07-01",
            "--days",
            "1",
            "--out",
            str(out),
        ],
    )
    build_snapshot.main()
    assert out.exists()
    price, _, source = read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1))
    assert price == 50.0 and source == "travelpayouts"


def test_main_defaults_airports_to_the_serving_csv(tmp_path: Path, monkeypatch) -> None:
    # Without --airports, the universe comes from a CSV (default: the serving list).
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "iata,name,city,country,lat,lon\n"
        "LIS,Humberto Delgado,Lisbon,PT,38.7742,-9.1342\n"
        "BCN,El Prat,Barcelona,ES,41.2974,2.0833\n",
        encoding="utf-8",
    )
    out = tmp_path / "snap.parquet"
    monkeypatch.setattr(build_snapshot, "_build_source", lambda: _FakeMonthSource())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_snapshot",
            "--airports-csv",
            str(csv_path),
            "--start",
            "2026-07-01",
            "--days",
            "1",
            "--out",
            str(out),
        ],
    )
    build_snapshot.main()
    assert read_fare_cell(str(out), "LIS", "BCN", dt.date(2026, 7, 1)) is not None
    assert read_fare_cell(str(out), "BCN", "LIS", dt.date(2026, 7, 1)) is not None


class _RaisingMonthSource:
    """Raises a transient RateLimited for one pair; returns a full month otherwise."""

    def get_month(self, origin, destination, month):
        if (origin, destination) == ("LIS", "BCN"):
            raise RateLimited()
        return _whole_month(origin, destination, month)


def test_collect_rows_skips_pair_months_that_raise_transient_errors() -> None:
    rows = collect_rows(
        _RaisingMonthSource(),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=2,
    )
    pairs = {(r["origin"], r["destination"]) for r in rows}
    assert ("LIS", "BCN") not in pairs  # raised -> skipped, the run is not crashed
    assert ("BCN", "LIS") in pairs


class _ConcurrencyProbe:
    """Proves >1 pair-month is fetched at once: a barrier that releases in pairs."""

    def __init__(self, parties: int) -> None:
        self._barrier = threading.Barrier(parties, timeout=3)
        self.ran_concurrently = False

    def get_month(self, origin, destination, month):
        try:
            self._barrier.wait()
            self.ran_concurrently = True
        except threading.BrokenBarrierError:
            pass
        return _whole_month(origin, destination, month)


def test_collect_rows_runs_pair_months_concurrently() -> None:
    probe = _ConcurrencyProbe(parties=2)
    rows = collect_rows(
        probe,
        airports=["LIS", "BCN", "ROM"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=4,
    )
    assert probe.ran_concurrently is True  # two get_month calls overlapped
    assert len(rows) == 6  # 3 airports -> 6 ordered pairs, all collected


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test")
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(code, request=request)
    )


class _StatusErrorMonthSource:
    def __init__(self, code: int) -> None:
        self._code = code

    def get_month(self, origin, destination, month):
        raise _status_error(self._code)


def test_collect_rows_skips_server_errors() -> None:
    rows = collect_rows(
        _StatusErrorMonthSource(503),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=2,
    )
    assert rows == []  # 5xx is a transient per-pair-month error -> skipped, no crash


def test_collect_rows_skips_invalid_route_400() -> None:
    # The API 400s pairs it considers invalid routes (e.g. same-city CDG->ORY,
    # observed live). That is a per-pair condition, not a systemic one: skip
    # the block, don't crash a 38k-call run on one bad pair.
    rows = collect_rows(
        _StatusErrorMonthSource(400),
        airports=["LIS", "BCN"],
        dates=[dt.date(2026, 7, 1)],
        snapshot_date=SNAP,
        max_workers=2,
    )
    assert rows == []


@pytest.mark.parametrize("status", [401, 403])
def test_collect_rows_fails_loud_on_auth_error(status: int) -> None:
    # A 401/403 is systemic (bad token): it must crash the run, not silently
    # produce an empty snapshot.
    with pytest.raises(httpx.HTTPStatusError):
        collect_rows(
            _StatusErrorMonthSource(status),
            airports=["LIS", "BCN"],
            dates=[dt.date(2026, 7, 1)],
            snapshot_date=SNAP,
            max_workers=2,
        )


# --- overwrite guard: don't clobber a good seed when upstream yields few/zero rows ---
from tripoptimizer.ingestion.build_snapshot import refuse_overwrite_reason  # noqa: E402
from tripoptimizer.ingestion.snapshot import count_rows  # noqa: E402


def _seed_snapshot(out: Path) -> int:
    """Write a small good snapshot to ``out`` and return its row count."""
    rows = collect_rows(
        _FakeMonthSource(), airports=["LIS", "BCN"], dates=[dt.date(2026, 7, 1)], snapshot_date=SNAP
    )
    curate(rows, out)
    return count_rows(out)


def test_count_rows_absent_is_zero(tmp_path: Path) -> None:
    assert count_rows(tmp_path / "nope.parquet") == 0


def test_count_rows_matches_written_rows(tmp_path: Path) -> None:
    out = tmp_path / "snap.parquet"
    assert _seed_snapshot(out) == 2  # 2 ordered pairs x 1 day


def test_refuse_overwrite_allows_first_build_and_normal_variation() -> None:
    assert refuse_overwrite_reason(0, 0) is None  # nothing to protect
    assert refuse_overwrite_reason(500, 0) is None  # first build over an absent seed
    assert refuse_overwrite_reason(900, 1000) is None  # 10% drop is fine
    assert refuse_overwrite_reason(1500, 1000) is None  # grew


def test_refuse_overwrite_blocks_empty_and_drastic_drop() -> None:
    assert refuse_overwrite_reason(0, 500) is not None  # empty over a good seed
    assert refuse_overwrite_reason(100, 1000) is not None  # >50% drop


def test_main_refuses_empty_overwrite_and_leaves_seed_intact(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "snap.parquet"
    original = _seed_snapshot(out)
    assert original > 0
    # An all-failing upstream (every pair 5xx -> 0 rows) must NOT clobber the seed.
    monkeypatch.setattr(build_snapshot, "_build_source", lambda: _StatusErrorMonthSource(503))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_snapshot",
            "--airports",
            "LIS",
            "BCN",
            "--start",
            "2026-07-01",
            "--days",
            "1",
            "--out",
            str(out),
        ],
    )
    with pytest.raises(SystemExit):
        build_snapshot.main()
    assert count_rows(out) == original  # untouched


def test_main_force_overrides_the_guard(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "snap.parquet"
    _seed_snapshot(out)
    monkeypatch.setattr(build_snapshot, "_build_source", lambda: _StatusErrorMonthSource(503))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_snapshot",
            "--airports",
            "LIS",
            "BCN",
            "--start",
            "2026-07-01",
            "--days",
            "1",
            "--out",
            str(out),
            "--force",
        ],
    )
    build_snapshot.main()  # --force -> no raise
    assert count_rows(out) == 0  # forced empty overwrite went through
