"""Boundary validation and core->schema conversion."""

from datetime import date

import pytest
from pydantic import ValidationError

from tripoptimizer.api.schemas import (
    MAX_CITIES,
    MAX_FLEX_DAYS,
    TripRequestSchema,
    TripResultSchema,
)
from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripResult


def _valid_payload() -> dict:
    return {
        "cities": ["BCN", "CDG"],
        "days_per_city": {"BCN": 2, "CDG": 3},
        "origin_airport": "LIS",
        "return_airport": "LIS",
        "start_date": "2026-07-01",
        "flex_days": 2,
    }


def test_valid_request_parses() -> None:
    req = TripRequestSchema(**_valid_payload())
    assert req.cities == ["BCN", "CDG"]
    assert req.flex_days == 2


def test_rejects_more_than_max_cities() -> None:
    payload = _valid_payload()
    payload["cities"] = [f"C{i:02d}" for i in range(MAX_CITIES + 1)]
    payload["days_per_city"] = {c: 1 for c in payload["cities"]}
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_flex_days_over_cap() -> None:
    payload = _valid_payload()
    payload["flex_days"] = MAX_FLEX_DAYS + 1
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_missing_days_for_a_city() -> None:
    payload = _valid_payload()
    payload["days_per_city"] = {"BCN": 2}  # CDG missing
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_rejects_non_positive_days() -> None:
    payload = _valid_payload()
    payload["days_per_city"] = {"BCN": 2, "CDG": 0}
    with pytest.raises(ValidationError):
        TripRequestSchema(**payload)


def test_trip_result_from_core_serializes() -> None:
    best = Itinerary(
        order=("BCN", "CDG"),
        start_offset=0,
        legs=(
            Leg("LIS", "BCN", date(2026, 7, 1), 50.0),
            Leg("BCN", "CDG", date(2026, 7, 3), 60.0),
            Leg("CDG", "LIS", date(2026, 7, 6), 70.0),
        ),
        total=180.0,
    )
    core = TripResult(best=best, alternatives=())
    out = TripResultSchema.from_core(core, data_source="synthetic")

    assert out.data_source == "synthetic"
    assert out.snapshot_date is None
    assert out.best.total == 180.0
    assert out.best.legs[0].fly_date == date(2026, 7, 1)
    assert out.best.legs[0].price == 50.0
    assert out.alternatives == []
