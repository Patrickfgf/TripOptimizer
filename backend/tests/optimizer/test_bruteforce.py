from datetime import date

from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.fares.synthetic import SyntheticProvider
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize

AIRPORTS = {
    "LIS": Airport("LIS", "Humberto Delgado", "Lisbon", "PT", 38.7742, -9.1342),
    "BCN": Airport("BCN", "El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "FCO": Airport("FCO", "Fiumicino", "Rome", "IT", 41.8003, 12.2389),
    "ATH": Airport("ATH", "Venizelos", "Athens", "GR", 37.9364, 23.9445),
}


def _request():
    return TripRequest(
        cities=("BCN", "FCO", "ATH"),
        days_per_city={"BCN": 3, "FCO": 2, "ATH": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=3,
    )


def test_returns_itinerary_visiting_all_cities_once():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    assert set(result.best.order) == {"BCN", "FCO", "ATH"}
    assert len(result.best.order) == 3


def test_legs_start_at_origin_and_end_at_return():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    assert result.best.legs[0].origin == "LIS"
    assert result.best.legs[-1].destination == "LIS"


def test_best_is_cheapest_among_alternatives():
    result = optimize(_request(), SyntheticProvider(AIRPORTS), engine="bruteforce")
    for alt in result.alternatives:
        assert result.best.total <= alt.total
