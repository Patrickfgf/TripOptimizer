"""Turn a city order + start offset into the dated leg chain."""

from datetime import date, timedelta

from tripoptimizer.core.optimizer.models import TripRequest


def build_legs_dates(
    order: tuple[str, ...], request: TripRequest, start_offset: int
) -> list[tuple[str, str, date]]:
    """Return [(origin, destination, fly_date), ...] from origin through return."""
    current_date = request.start_date + timedelta(days=start_offset)
    current_place = request.origin_airport
    legs: list[tuple[str, str, date]] = []
    for city in order:
        legs.append((current_place, city, current_date))
        current_date += timedelta(days=request.days_per_city[city])
        current_place = city
    legs.append((current_place, request.return_airport, current_date))
    return legs
