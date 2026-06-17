"""Chain-of-Responsibility fare provider. Is itself a FareProvider, so it composes
recursively and callers never learn how many sources exist. Each provider stamps
its own Fare.source, so provenance rides on the value object, not on control flow.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.fares.models import Fare


class FallbackFareProvider:
    def __init__(self, providers: Sequence[FareProvider]):
        self._providers = tuple(providers)  # immutable; order = priority

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        for provider in self._providers:
            fare = provider.get_fare(origin, destination, fly_date)
            if fare is not None:
                return fare
        return None
