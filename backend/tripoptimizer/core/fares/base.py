"""Strategy interface for fare sources (synthetic, cached, travelpayouts...)."""
from datetime import date
from typing import Protocol

from tripoptimizer.core.fares.models import Fare


class FareProvider(Protocol):
    def get_fare(self, origin: str, destination: str, fly_date: date) -> Fare | None:
        """Return a Fare for the leg, or None if this provider has no data for it."""
        ...
