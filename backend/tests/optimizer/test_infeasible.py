"""Real-or-nothing: a missing fare makes an itinerary infeasible, not a crash.

With the synthetic fallback removed, a cell (origin, destination, date) can have no
real fare. The optimizer must skip infeasible orderings and, when none is fully
priceable, return an IncompleteTrip naming the blocking routes -- never a KeyError,
never a fabricated total.
"""

from datetime import date

import pytest

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.optimizer.models import IncompleteTrip, TripRequest, TripResult
from tripoptimizer.core.optimizer.runner import optimize


class DictProvider:
    """Fare source with per-route control; date-independent for deterministic tests.

    ``routes`` is the set of (origin, destination) pairs that have a (flat) fare. Any
    pair not in the set returns None -- exercising the infeasible path.
    """

    PRICE = 100.0

    def __init__(self, routes: set[tuple[str, str]]) -> None:
        self._routes = set(routes)

    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare | None:
        if (origin, destination) in self._routes:
            return Fare(origin, destination, fly_date, self.PRICE, "EUR", "cached")
        return None


def _request(cities: tuple[str, ...] = ("BCN", "FCO")) -> TripRequest:
    return TripRequest(
        cities=cities,
        days_per_city={c: 2 for c in cities},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=0,
    )


# Every directed pair the 2-city trip (LIS origin/return) can query.
_ALL = {
    ("LIS", "BCN"),
    ("BCN", "FCO"),
    ("FCO", "LIS"),
    ("LIS", "FCO"),
    ("FCO", "BCN"),
    ("BCN", "LIS"),
}


@pytest.mark.parametrize("engine", ["bruteforce", "heldkarp"])
def test_skips_infeasible_ordering_and_returns_cheapest_real(engine: str) -> None:
    # Drop BCN->FCO: LIS->BCN->FCO->LIS is infeasible; LIS->FCO->BCN->LIS survives.
    provider = DictProvider(_ALL - {("BCN", "FCO")})
    result = optimize(_request(), provider, engine=engine)
    assert isinstance(result, TripResult)
    assert result.best.order == ("FCO", "BCN")
    assert all(leg.source == "cached" for leg in result.best.legs)


@pytest.mark.parametrize("engine", ["bruteforce", "heldkarp"])
def test_all_infeasible_yields_incomplete_trip(engine: str) -> None:
    result = optimize(_request(), DictProvider(set()), engine=engine)
    assert isinstance(result, IncompleteTrip)
    assert result.missing_routes  # non-empty


@pytest.mark.parametrize("engine", ["bruteforce", "heldkarp"])
def test_incomplete_trip_lists_only_the_blocking_routes(engine: str) -> None:
    # Both inter-city legs gone -> every ordering blocked; origin/return legs are fine.
    provider = DictProvider(_ALL - {("BCN", "FCO"), ("FCO", "BCN")})
    result = optimize(_request(), provider, engine=engine)
    assert isinstance(result, IncompleteTrip)
    assert set(result.missing_routes) == {("BCN", "FCO"), ("FCO", "BCN")}
