"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException, Query

from tripoptimizer.api.dependencies import get_airports, get_provider
from tripoptimizer.api.schemas import AirportSchema, TripRequestSchema, TripResultSchema
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.runner import optimize

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


@router.post("/optimize", response_model=TripResultSchema)
def optimize_route(
    request: TripRequestSchema,
    engine: str = Query(default="bruteforce", pattern="^(bruteforce|heldkarp)$"),
) -> TripResultSchema:
    """Compute the cheapest city ordering (+ date slide) for the trip."""
    airports = get_airports()
    codes = {request.origin_airport, request.return_airport, *request.cities}
    unknown = sorted(code for code in codes if code not in airports)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown airport(s): {', '.join(unknown)}")

    trip = TripRequest(
        cities=tuple(request.cities),
        days_per_city=dict(request.days_per_city),
        origin_airport=request.origin_airport,
        return_airport=request.return_airport,
        start_date=request.start_date,
        flex_days=request.flex_days,
    )
    result = optimize(trip, get_provider(), engine=engine)
    return TripResultSchema.from_core(result, data_source="synthetic")
