import random
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
    "CDG": Airport("CDG", "Charles de Gaulle", "Paris", "FR", 49.0097, 2.5479),
    "BER": Airport("BER", "Brandenburg", "Berlin", "DE", 52.3667, 13.5033),
}


def test_heldkarp_matches_bruteforce_on_random_cases():
    rng = random.Random(42)
    provider = SyntheticProvider(AIRPORTS)
    cities_pool = ["BCN", "FCO", "ATH", "CDG", "BER"]
    for _ in range(20):
        k = rng.randint(2, 5)
        cities = tuple(rng.sample(cities_pool, k))
        request = TripRequest(
            cities=cities,
            days_per_city={c: rng.randint(1, 4) for c in cities},
            origin_airport="LIS",
            return_airport="LIS",
            start_date=date(2026, 7, 1),
            flex_days=rng.randint(0, 3),
        )
        bf = optimize(request, provider, engine="bruteforce").best
        dp = optimize(request, provider, engine="heldkarp").best
        assert abs(bf.total - dp.total) < 1e-6
        assert dp.legs[0].origin == "LIS"
        assert dp.legs[-1].destination == "LIS"
        assert set(dp.order) == set(cities)
