"""The API loads airport reference data and a synthetic provider once."""

from datetime import date

from tripoptimizer.api.dependencies import get_airports, get_provider


def test_get_airports_loads_sample_set() -> None:
    airports = get_airports()
    assert "LIS" in airports
    assert airports["LIS"].city == "Lisbon"
    assert len(airports) >= 8


def test_get_airports_is_cached() -> None:
    assert get_airports() is get_airports()


def test_get_provider_prices_a_known_leg() -> None:
    provider = get_provider()
    fare = provider.get_fare("LIS", "BCN", date(2026, 7, 1))
    assert fare is not None
    assert fare.price > 0
    assert fare.source == "synthetic"
