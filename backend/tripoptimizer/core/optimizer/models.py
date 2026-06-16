"""Immutable models for the optimizer's input and output."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TripRequest:
    cities: tuple[str, ...]          # IATA codes of the destination cities
    days_per_city: Mapping[str, int]  # days spent in each city (read-only)
    origin_airport: str              # IATA where the trip starts
    return_airport: str              # IATA where the trip ends
    start_date: date
    flex_days: int = 3               # slide the whole trip within +/- this many days


@dataclass(frozen=True)
class Leg:
    origin: str
    destination: str
    fly_date: date
    price: float


@dataclass(frozen=True)
class Itinerary:
    order: tuple[str, ...]           # the optimized order of the middle cities
    start_offset: int                # day offset applied to start_date
    legs: tuple[Leg, ...]            # origin -> c1 -> ... -> ck -> return
    total: float                     # total fare in EUR


@dataclass(frozen=True)
class TripResult:
    best: Itinerary
    alternatives: tuple[Itinerary, ...]
