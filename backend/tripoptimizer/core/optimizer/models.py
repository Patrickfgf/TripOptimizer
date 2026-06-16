"""Immutable models for the optimizer's input and output."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TripRequest:
    cities: tuple[str, ...]  # IATA codes of the destination cities
    days_per_city: Mapping[str, int]  # days spent in each city (read-only)
    origin_airport: str  # IATA where the trip starts
    return_airport: str  # IATA where the trip ends
    start_date: date
    flex_days: int = 3  # slide the whole trip within +/- this many days

    def __post_init__(self) -> None:
        """Fail fast on invalid input at the system boundary."""
        if not self.cities:
            raise ValueError("cities must not be empty")
        if self.flex_days < 0:
            raise ValueError(f"flex_days must be >= 0, got {self.flex_days}")
        missing = set(self.cities) - set(self.days_per_city)
        if missing:
            raise ValueError(f"days_per_city is missing entries for: {sorted(missing)}")
        for city in self.cities:
            if self.days_per_city[city] <= 0:
                raise ValueError(
                    f"days_per_city[{city!r}] must be > 0, got {self.days_per_city[city]}"
                )


@dataclass(frozen=True)
class Leg:
    origin: str
    destination: str
    fly_date: date
    price: float


@dataclass(frozen=True)
class Itinerary:
    order: tuple[str, ...]  # the optimized order of the middle cities
    start_offset: int  # day offset applied to start_date
    legs: tuple[Leg, ...]  # origin -> c1 -> ... -> ck -> return
    total: float  # total fare in EUR


@dataclass(frozen=True)
class TripResult:
    best: Itinerary
    alternatives: tuple[Itinerary, ...]
