"""Fare value object. Grain: one fare = origin x destination x fly_date."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Fare:
    origin: str
    destination: str
    fly_date: date
    price: float
    currency: str = "EUR"
    source: str = "synthetic"
