from datetime import date

from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.schedule import build_legs_dates


def _request():
    return TripRequest(
        cities=("BCN", "FCO"),
        days_per_city={"BCN": 3, "FCO": 2},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=date(2026, 7, 1),
        flex_days=3,
    )


def test_legs_form_a_full_chain_origin_to_return():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=0)
    chain = [(o, d) for (o, d, _) in legs]
    assert chain == [("LIS", "BCN"), ("BCN", "FCO"), ("FCO", "LIS")]


def test_dates_accumulate_days_per_city():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=0)
    dates = [dt for (_, _, dt) in legs]
    assert dates == [date(2026, 7, 1), date(2026, 7, 4), date(2026, 7, 6)]


def test_offset_shifts_every_date():
    legs = build_legs_dates(("BCN", "FCO"), _request(), start_offset=-2)
    assert [dt for (_, _, dt) in legs][0] == date(2026, 6, 29)
