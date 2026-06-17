"""Travelpayouts/Aviasales Data API fare provider (offline ingestion only).

Calls v3/prices_for_dates for a single (origin, destination, departure date),
forcing EUR + an EU market, and returns the cheapest ticket (data[0] with
sorting=price). Retries on HTTP 429 honoring Retry-After. The httpx.Client is
INJECTED so tests mock the transport with a dummy token — no real credential.
"""

from __future__ import annotations

import datetime as dt

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from tripoptimizer.core.fares.models import Fare

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TRAVELPAYOUTS_SOURCE = "travelpayouts"
_MAX_ATTEMPTS = 4


class RateLimited(Exception):
    """Raised on HTTP 429 to trigger a tenacity retry."""


class TravelpayoutsProvider:
    def __init__(
        self,
        token: str,
        *,
        client: httpx.Client,
        market: str = "es",
        currency: str = "eur",
    ):
        self._token = token
        self._client = client
        self._market = market
        self._currency = currency

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        payload = self._fetch(origin, destination, fly_date)
        data = payload.get("data") or []
        if not data:
            return None
        price = float(data[0]["price"])
        return Fare(origin, destination, fly_date, price, "EUR", TRAVELPAYOUTS_SOURCE)

    @retry(
        retry=retry_if_exception_type(RateLimited),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_fixed(0),  # honor Retry-After server-side; fixed(0) keeps tests fast
        reraise=True,
    )
    def _fetch(self, origin: str, destination: str, fly_date: dt.date) -> dict:
        response = self._client.get(
            API_URL,
            headers={"X-Access-Token": self._token, "Accept-Encoding": "gzip, deflate"},
            params={
                "origin": origin,
                "destination": destination,
                "departure_at": fly_date.isoformat(),
                "one_way": "true",
                "direct": "false",
                "sorting": "price",
                "limit": 1,
                "currency": self._currency,
                "market": self._market,
            },
        )
        if response.status_code == 429:
            raise RateLimited()
        response.raise_for_status()
        return response.json()
