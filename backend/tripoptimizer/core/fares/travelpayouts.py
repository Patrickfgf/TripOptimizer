"""Travelpayouts/Aviasales Data API fare provider (offline ingestion only).

Calls v3/prices_for_dates for a single (origin, destination, departure date),
forcing EUR + an EU market, and returns the cheapest ticket (data[0] with
sorting=price). On HTTP 429 it backs off honoring Retry-After (else exponential,
both capped) and retries; after the attempt budget it raises RateLimited for the
caller to skip the cell. The httpx.Client is INJECTED so tests mock the transport
with a dummy token — no real credential.
"""

from __future__ import annotations

import datetime as dt

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from tripoptimizer.core.fares.models import Fare

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TRAVELPAYOUTS_SOURCE = "travelpayouts"
_MAX_ATTEMPTS = 4
_BACKOFF_BASE_S = 0.5
_BACKOFF_CAP_S = 30.0


class RateLimited(Exception):
    """Raised on HTTP 429 to trigger a backoff retry; carries Retry-After (s)."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


def compute_backoff(attempt: int, retry_after: float | None = None) -> float:
    """Seconds to wait before retry ``attempt`` (1-based).

    Honors a server Retry-After when present, else exponential backoff
    (base * 2**(attempt-1)). Both are capped so a hostile/large value can't
    stall the ingestion.
    """
    if retry_after is not None:
        return min(float(retry_after), _BACKOFF_CAP_S)
    return min(_BACKOFF_CAP_S, _BACKOFF_BASE_S * (2 ** (attempt - 1)))


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header given in seconds; None if absent/non-numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _wait_backoff(retry_state) -> float:
    """tenacity wait: derive the delay from the RateLimited exception's Retry-After."""
    exc = retry_state.outcome.exception()
    retry_after = getattr(exc, "retry_after", None)
    return compute_backoff(retry_state.attempt_number, retry_after)


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
        wait=_wait_backoff,
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
            raise RateLimited(_parse_retry_after(response.headers.get("Retry-After")))
        response.raise_for_status()
        return response.json()
