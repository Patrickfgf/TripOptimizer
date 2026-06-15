from datetime import date

from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.fares.synthetic import SyntheticProvider

AIRPORTS = {
    "LIS": Airport("LIS", "Humberto Delgado", "Lisbon", "PT", 38.7742, -9.1342),
    "BCN": Airport("BCN", "El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "ATH": Airport("ATH", "Venizelos", "Athens", "GR", 37.9364, 23.9445),
}


def test_fare_is_positive():
    provider = SyntheticProvider(AIRPORTS)
    fare = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    assert fare is not None
    assert fare.price > 0
    assert fare.currency == "EUR"
    assert fare.source == "synthetic"


def test_fare_is_deterministic():
    provider = SyntheticProvider(AIRPORTS)
    a = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    b = provider.get_fare("LIS", "BCN", date(2026, 7, 3))
    assert a.price == b.price


def test_longer_distance_costs_more_on_same_date():
    provider = SyntheticProvider(AIRPORTS)
    near = provider.get_fare("LIS", "BCN", date(2026, 7, 3)).price
    far = provider.get_fare("LIS", "ATH", date(2026, 7, 3)).price
    assert far > near


def test_unknown_airport_returns_none():
    provider = SyntheticProvider(AIRPORTS)
    assert provider.get_fare("LIS", "ZZZ", date(2026, 7, 3)) is None


def test_summer_costs_more_than_winter():
    # July (European summer peak) must beat January (winter trough) on the same
    # route; the seasonality gap (1.25 vs 0.75) dominates the noise band.
    provider = SyntheticProvider(AIRPORTS)
    summer = provider.get_fare("LIS", "BCN", date(2026, 7, 15)).price
    winter = provider.get_fare("LIS", "BCN", date(2026, 1, 15)).price
    assert summer > winter
