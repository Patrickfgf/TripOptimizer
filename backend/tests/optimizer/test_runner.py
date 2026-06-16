"""The runner memoizes fare lookups within a single optimize() call."""

from datetime import date

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize


class CountingProvider:
    """Counts how many times the underlying fare source is hit."""

    def __init__(self) -> None:
        self.calls = 0

    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare:
        self.calls += 1
        return Fare(origin, destination, fly_date, price=100.0)


def test_optimize_memoizes_repeated_fare_cells() -> None:
    request = TripRequest(
        cities=("BCN", "CDG", "FCO"),
        days_per_city={"BCN": 2, "CDG": 2, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=1,
    )
    counting = CountingProvider()
    naive = CountingProvider()

    # Run the real (memoized) optimizer.
    optimize(request, counting, engine="bruteforce")

    # Count distinct cells by replaying every lookup the search would make.
    from tripoptimizer.core.optimizer.bruteforce import search_bruteforce

    seen: set[tuple[str, str, str]] = set()

    def record(origin: str, destination: str, fly_date: date) -> float:
        seen.add((origin, destination, fly_date.isoformat()))
        naive.get_fare(origin, destination, fly_date)
        return 100.0

    search_bruteforce(request, record)

    assert counting.calls == len(seen)
    assert counting.calls < naive.calls  # memoization actually saved calls
