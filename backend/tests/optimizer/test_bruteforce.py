from datetime import date

from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize


def _request():
    return TripRequest(
        cities=("BCN", "FCO", "ATH"),
        days_per_city={"BCN": 3, "FCO": 2, "ATH": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=3,
    )


def test_returns_itinerary_visiting_all_cities_once(fake_provider):
    result = optimize(_request(), fake_provider, engine="bruteforce")
    assert set(result.best.order) == {"BCN", "FCO", "ATH"}
    assert len(result.best.order) == 3


def test_legs_start_at_origin_and_end_at_return(fake_provider):
    result = optimize(_request(), fake_provider, engine="bruteforce")
    assert result.best.legs[0].origin == "LIS"
    assert result.best.legs[-1].destination == "LIS"


def test_best_is_cheapest_among_alternatives(fake_provider):
    result = optimize(_request(), fake_provider, engine="bruteforce")
    for alt in result.alternatives:
        assert result.best.total <= alt.total


def test_legs_carry_provider_source(fake_provider) -> None:
    result = optimize(_request(), fake_provider, engine="bruteforce")
    assert all(leg.source == "test" for leg in result.best.legs)
