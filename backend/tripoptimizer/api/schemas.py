"""Pydantic models for the HTTP boundary.

Request validation here enforces the MVP guardrails the pure core deliberately
omits (max cities, flex cap). Response models serialize the core's frozen
dataclasses to JSON via ``from_core`` converters, keeping the core Pydantic-free.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from tripoptimizer.core.optimizer.models import Itinerary, TripResult

MAX_CITIES = 8
MAX_FLEX_DAYS = 7


def aggregate_data_source(itinerary: Itinerary) -> str:
    """cached / synthetic when uniform across legs, else 'mixed'."""
    sources = {leg.source for leg in itinerary.legs}
    return next(iter(sources)) if len(sources) == 1 else "mixed"


class TripRequestSchema(BaseModel):
    cities: list[str] = Field(..., min_length=1, max_length=MAX_CITIES)
    days_per_city: dict[str, int]
    origin_airport: str
    return_airport: str
    start_date: date
    flex_days: int = Field(default=3, ge=0, le=MAX_FLEX_DAYS)

    @model_validator(mode="after")
    def _days_cover_cities(self) -> "TripRequestSchema":
        missing = [c for c in self.cities if c not in self.days_per_city]
        if missing:
            raise ValueError(f"days_per_city is missing entries for: {sorted(missing)}")
        for city in self.cities:
            if self.days_per_city[city] <= 0:
                raise ValueError(f"days_per_city[{city!r}] must be > 0")
        return self


class LegSchema(BaseModel):
    origin: str
    destination: str
    fly_date: date
    price: float
    source: str


class ItinerarySchema(BaseModel):
    order: list[str]
    start_offset: int
    legs: list[LegSchema]
    total: float

    @classmethod
    def from_core(cls, itinerary: Itinerary) -> "ItinerarySchema":
        return cls(
            order=list(itinerary.order),
            start_offset=itinerary.start_offset,
            legs=[
                LegSchema(
                    origin=leg.origin,
                    destination=leg.destination,
                    fly_date=leg.fly_date,
                    price=leg.price,
                    source=leg.source,
                )
                for leg in itinerary.legs
            ],
            total=itinerary.total,
        )


class TripResultSchema(BaseModel):
    best: ItinerarySchema
    alternatives: list[ItinerarySchema]
    data_source: str
    snapshot_date: date | None = None

    @classmethod
    def from_core(
        cls,
        result: TripResult,
        *,
        data_source: str | None = None,
        snapshot_date: date | None = None,
    ) -> "TripResultSchema":
        return cls(
            best=ItinerarySchema.from_core(result.best),
            alternatives=[ItinerarySchema.from_core(it) for it in result.alternatives],
            data_source=data_source or aggregate_data_source(result.best),
            snapshot_date=snapshot_date,
        )


class AirportSchema(BaseModel):
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lon: float
