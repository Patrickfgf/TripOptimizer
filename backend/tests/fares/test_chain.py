"""FallbackFareProvider tries providers in order; first non-None Fare wins."""

import datetime as dt

from tripoptimizer.core.fares.chain import FallbackFareProvider
from tripoptimizer.core.fares.models import Fare


class _Fixed:
    """A provider that returns a fixed Fare for one cell, None otherwise."""

    def __init__(self, cell, fare):
        self._cell, self._fare = cell, fare

    def get_fare(self, origin, destination, fly_date):
        return self._fare if (origin, destination, fly_date) == self._cell else None


CELL = ("LIS", "BCN", dt.date(2026, 7, 1))


def test_first_provider_wins() -> None:
    cached = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 40.0, "EUR", "cached"))
    synth = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 99.0, "EUR", "synthetic"))
    chain = FallbackFareProvider([cached, synth])
    fare = chain.get_fare(*CELL)
    assert fare.price == 40.0 and fare.source == "cached"


def test_falls_through_to_second_on_miss() -> None:
    cached = _Fixed(("X", "Y", dt.date(2026, 7, 1)), None)  # never matches CELL
    synth = _Fixed(CELL, Fare("LIS", "BCN", dt.date(2026, 7, 1), 99.0, "EUR", "synthetic"))
    chain = FallbackFareProvider([cached, synth])
    fare = chain.get_fare(*CELL)
    assert fare.price == 99.0 and fare.source == "synthetic"


def test_all_miss_returns_none() -> None:
    chain = FallbackFareProvider([_Fixed(None, None), _Fixed(None, None)])
    assert chain.get_fare(*CELL) is None
