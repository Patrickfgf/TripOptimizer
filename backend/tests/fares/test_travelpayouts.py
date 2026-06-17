"""TravelpayoutsProvider: parse prices_for_dates, force EUR, retry 429. No real token."""

import datetime as dt

import httpx
import respx

from tripoptimizer.core.fares.travelpayouts import API_URL, TravelpayoutsProvider


def _provider() -> TravelpayoutsProvider:
    return TravelpayoutsProvider(token="dummy", client=httpx.Client(), market="es")


@respx.mock
def test_parses_cheapest_from_data_array() -> None:
    respx.get(API_URL).respond(
        200,
        json={
            "success": True,
            "currency": "eur",
            "error": None,
            "data": [
                {
                    "origin": "LIS",
                    "destination": "BCN",
                    "price": 48.9,
                    "airline": "TP",
                    "flight_number": "1042",
                    "departure_at": "2026-07-01T07:00:00+01:00",
                    "transfers": 0,
                }
            ],
        },
    )
    fare = _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert fare is not None
    assert fare.price == 48.9
    assert fare.currency == "EUR"
    assert fare.source == "travelpayouts"


@respx.mock
def test_empty_data_returns_none() -> None:
    respx.get(API_URL).respond(200, json={"success": True, "data": [], "error": None})
    assert _provider().get_fare("LIS", "ZZZ", dt.date(2026, 7, 1)) is None


@respx.mock
def test_sends_auth_header_and_forces_eur() -> None:
    route = respx.get(API_URL).respond(200, json={"success": True, "data": [], "error": None})
    _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    req = route.calls.last.request
    assert req.headers["x-access-token"] == "dummy"
    assert req.url.params["currency"] == "eur"
    assert req.url.params["market"] == "es"
    assert req.url.params["one_way"] == "true"


@respx.mock
def test_retries_on_429_then_succeeds() -> None:
    route = respx.get(API_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"success": True, "error": None, "data": [{"price": 50.0}]}),
        ]
    )
    fare = _provider().get_fare("LIS", "BCN", dt.date(2026, 7, 1))
    assert route.call_count == 2
    assert fare.price == 50.0
