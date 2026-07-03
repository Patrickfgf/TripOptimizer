import random
from datetime import date

from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize


def test_heldkarp_matches_bruteforce_on_random_cases(fake_provider):
    rng = random.Random(42)
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
        bf = optimize(request, fake_provider, engine="bruteforce").best
        dp = optimize(request, fake_provider, engine="heldkarp").best
        assert abs(bf.total - dp.total) < 1e-6
        assert dp.legs[0].origin == "LIS"
        assert dp.legs[-1].destination == "LIS"
        assert set(dp.order) == set(cities)


def test_heldkarp_legs_carry_source(fake_provider) -> None:
    request = TripRequest(
        cities=("BCN", "FCO"),
        days_per_city={"BCN": 2, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=1,
    )
    result = optimize(request, fake_provider, engine="heldkarp")
    assert all(leg.source == "test" for leg in result.best.legs)
