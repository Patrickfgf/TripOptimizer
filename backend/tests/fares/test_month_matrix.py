"""MonthMatrixProvider: parse v2/prices/month-matrix into per-day Fares. No real token."""

import datetime as dt

import httpx
import respx

from tripoptimizer.core.fares.month_matrix import MONTH_MATRIX_URL, MonthMatrixProvider


def _provider() -> MonthMatrixProvider:
    return MonthMatrixProvider(token="dummy", client=httpx.Client())


_PAYLOAD = {
    "success": True,
    "data": [
        {
            "origin": "LON",
            "destination": "LIS",
            "depart_date": "2026-08-10",
            "return_date": "",
            "value": 33,
            "number_of_changes": 0,
            "trip_class": 0,
        },
        {
            "origin": "LON",
            "destination": "LIS",
            "depart_date": "2026-08-12",
            "return_date": "",
            "value": 32,
            "number_of_changes": 1,
            "trip_class": 0,
        },
    ],
}


@respx.mock
def test_maps_each_day_to_a_fare() -> None:
    respx.get(MONTH_MATRIX_URL).respond(200, json=_PAYLOAD)
    fares = _provider().get_month("LON", "LIS", dt.date(2026, 8, 1))
    assert set(fares) == {dt.date(2026, 8, 10), dt.date(2026, 8, 12)}
    aug12 = fares[dt.date(2026, 8, 12)]
    assert aug12.price == 32.0
    assert aug12.currency == "EUR"
    assert aug12.source == "travelpayouts"


@respx.mock
def test_empty_month_returns_empty_dict() -> None:
    respx.get(MONTH_MATRIX_URL).respond(200, json={"success": True, "data": []})
    assert _provider().get_month("MAD", "DUB", dt.date(2026, 8, 1)) == {}


@respx.mock
def test_sends_auth_and_normalizes_to_first_of_month() -> None:
    route = respx.get(MONTH_MATRIX_URL).respond(200, json={"success": True, "data": []})
    _provider().get_month("LON", "LIS", dt.date(2026, 8, 15))  # any day -> first of month
    req = route.calls.last.request
    assert req.headers["x-access-token"] == "dummy"
    assert req.url.params["currency"] == "eur"
    assert req.url.params["month"] == "2026-08-01"
    assert req.url.params["origin"] == "LON"


@respx.mock
def test_retries_on_429_then_succeeds() -> None:
    route = respx.get(MONTH_MATRIX_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=_PAYLOAD),
        ]
    )
    fares = _provider().get_month("LON", "LIS", dt.date(2026, 8, 1))
    assert route.call_count == 2
    assert len(fares) == 2
