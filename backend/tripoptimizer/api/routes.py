"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException

from tripoptimizer.api.dependencies import get_airports
from tripoptimizer.api.schemas import AirportSchema

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + a shallow check that reference data is available."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    return {"status": "ok", "airports_loaded": len(airports)}


@router.get("/airports", response_model=list[AirportSchema])
def list_airports() -> list[AirportSchema]:
    """All known airports (IATA, name, city, country, lat/lon)."""
    return [
        AirportSchema(
            iata=a.iata,
            name=a.name,
            city=a.city,
            country=a.country,
            lat=a.lat,
            lon=a.lon,
        )
        for a in get_airports().values()
    ]
