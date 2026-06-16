import dataclasses
from datetime import date

import pytest

from tripoptimizer.core.optimizer.models import TripRequest

_VALID = TripRequest(
    cities=("BCN", "FCO"),
    days_per_city={"BCN": 3, "FCO": 2},
    origin_airport="LIS",
    return_airport="LIS",
    start_date=date(2026, 7, 1),
    flex_days=3,
)


def test_valid_request_is_accepted():
    assert _VALID.cities == ("BCN", "FCO")


def test_empty_cities_rejected():
    with pytest.raises(ValueError, match="cities must not be empty"):
        dataclasses.replace(_VALID, cities=())


def test_negative_flex_days_rejected():
    with pytest.raises(ValueError, match="flex_days must be >= 0"):
        dataclasses.replace(_VALID, flex_days=-1)


def test_missing_days_per_city_rejected():
    with pytest.raises(ValueError, match="missing entries"):
        dataclasses.replace(_VALID, days_per_city={"BCN": 3})


def test_non_positive_days_rejected():
    with pytest.raises(ValueError, match="must be > 0"):
        dataclasses.replace(_VALID, days_per_city={"BCN": 3, "FCO": 0})
