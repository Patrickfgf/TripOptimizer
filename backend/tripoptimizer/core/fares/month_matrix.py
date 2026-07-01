"""Travelpayouts v2 prices/month-matrix fare source: one call returns a whole month.

For an (origin, destination) it returns the cheapest ONE-WAY price per day of the month
(``value`` in EUR; ``return_date`` is empty). Denser and ~30x cheaper in calls than v3
prices_for_dates -- measured coverage ~48% vs ~31%. Reuses the 429 backoff/retry from the
per-date provider; the httpx.Client is injected so tests mock the transport with a dummy
token.
"""

from __future__ import annotations

import datetime as dt

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.travelpayouts import (
    _MAX_ATTEMPTS,
    RateLimited,
    _parse_retry_after,
    _wait_backoff,
)

MONTH_MATRIX_URL = "https://api.travelpayouts.com/v2/prices/month-matrix"
TRAVELPAYOUTS_SOURCE = "travelpayouts"


class MonthMatrixProvider:
    """Fetches a month of cheapest one-way fares from Travelpayouts' month-matrix."""

    def __init__(self, token: str, *, client: httpx.Client, currency: str = "eur") -> None:
        self._token = token
        self._client = client
        self._currency = currency

    def get_month(self, origin: str, destination: str, month: dt.date) -> dict[dt.date, Fare]:
        payload = self._fetch(origin, destination, month)
        fares: dict[dt.date, Fare] = {}
        for row in payload.get("data") or []:
            raw = row.get("depart_date")
            value = row.get("value")
            if not raw or value is None:
                continue
            day = dt.date.fromisoformat(raw[:10])
            fares[day] = Fare(origin, destination, day, float(value), "EUR", TRAVELPAYOUTS_SOURCE)
        return fares

    @retry(
        retry=retry_if_exception_type(RateLimited),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=_wait_backoff,
        reraise=True,
    )
    def _fetch(self, origin: str, destination: str, month: dt.date) -> dict:
        response = self._client.get(
            MONTH_MATRIX_URL,
            headers={"X-Access-Token": self._token, "Accept-Encoding": "gzip, deflate"},
            params={
                "currency": self._currency,
                "origin": origin,
                "destination": destination,
                "month": month.replace(day=1).isoformat(),
                "show_to_affiliates": "true",
            },
        )
        if response.status_code == 429:
            raise RateLimited(_parse_retry_after(response.headers.get("Retry-After")))
        response.raise_for_status()
        return response.json()
