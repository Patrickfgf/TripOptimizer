"""Deterministic synthetic fares over real airport geography.

Price model (defensible, documented): base = BASE + PER_KM * haversine,
multiplied by month seasonality, a weekend surcharge, and a deterministic
per-(leg, date) noise factor so the SAME leg always returns the SAME price.
"""
import hashlib
from datetime import date
from math import pi, sin

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.graph.airports import Airport
from tripoptimizer.core.graph.distance import haversine_km

BASE_FARE_EUR = 20.0
PER_KM_EUR = 0.07


def _unit_noise(origin: str, destination: str, fly_date: date) -> float:
    """Deterministic value in [0, 1) derived from the leg + date."""
    key = f"{origin}|{destination}|{fly_date.isoformat()}".encode()
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:8], 16) / 0x100000000


class SyntheticProvider:
    def __init__(self, airports: dict[str, Airport]):
        self._airports = airports

    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare | None:
        if origin not in self._airports or destination not in self._airports:
            return None
        a, b = self._airports[origin], self._airports[destination]
        dist = haversine_km(a.lat, a.lon, b.lat, b.lon)
        base = BASE_FARE_EUR + PER_KM_EUR * dist
        season = 1.0 + 0.25 * sin(2 * pi * (fly_date.month - 1) / 12)
        weekend = 1.15 if fly_date.weekday() >= 5 else 1.0
        noise = 0.85 + 0.30 * _unit_noise(origin, destination, fly_date)
        price = round(base * season * weekend * noise, 2)
        return Fare(origin, destination, fly_date, price, "EUR", "synthetic")
