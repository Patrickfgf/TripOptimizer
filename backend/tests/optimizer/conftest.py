"""Shared fare fixture for the optimizer tests.

FakeFareProvider prices every cell as a pure hash of (origin, destination,
fly_date): deterministic across runs, yet different per cell. The variance is
load-bearing — with constant prices every ordering would tie, making the
Held-Karp-vs-bruteforce oracle and the cheapest-alternative assertions vacuous.
"""

import datetime as dt
import hashlib

import pytest

from tripoptimizer.core.fares.models import Fare


class FakeFareProvider:
    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        cell = f"{origin}|{destination}|{fly_date.isoformat()}"
        digest = hashlib.sha256(cell.encode()).hexdigest()
        price = 50.0 + (int(digest[:8], 16) % 40_000) / 100.0  # 50.00 .. 449.99
        return Fare(origin, destination, fly_date, price, "EUR", "test")


@pytest.fixture
def fake_provider() -> FakeFareProvider:
    return FakeFareProvider()
