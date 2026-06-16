"""Held-Karp DP optimizer (implemented in Task 9)."""

from collections.abc import Callable
from datetime import date

from tripoptimizer.core.optimizer.models import TripRequest, TripResult

FareLookup = Callable[[str, str, date], float]


def search_heldkarp(request: TripRequest, fare_lookup: FareLookup) -> TripResult:
    raise NotImplementedError
