"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException, Query

from tripoptimizer.api.dependencies import (
    get_airports,
    get_provider,
    get_snapshot_date,
    live_fares_enabled,
)
from tripoptimizer.api.schemas import (
    AirportSchema,
    IncompleteTripSchema,
    TripRequestSchema,
    TripResultSchema,
)
from tripoptimizer.core.optimizer.models import IncompleteTrip, TripRequest
from tripoptimizer.core.optimizer.prefetch import prefetch
from tripoptimizer.core.optimizer.runner import optimize

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + deep check: reference data loaded and the snapshot store queryable."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    try:
        snapshot_date = get_snapshot_date()  # touches the DuckDB store (None if no snapshot)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail="fare snapshot store unavailable") from exc
    return {
        "status": "ok",
        "airports_loaded": len(airports),
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
    }


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


@router.post("/optimize", response_model=TripResultSchema | IncompleteTripSchema)
def optimize_route(
    request: TripRequestSchema,
    engine: str = Query(default="bruteforce", pattern="^(bruteforce|heldkarp)$"),
) -> TripResultSchema | IncompleteTripSchema:
    """Cheapest city ordering (+ date slide), or an honest 'incomplete' result when no
    fully-real itinerary exists (some route has no real fare in the window)."""
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
    provider = get_provider()
    if live_fares_enabled():
        # Warm the on-demand cache for this trip's cells in one parallel batch,
        # so the engine's per-cell lookups all hit the cache instead of firing
        # hundreds of sequential live calls.
        prefetch(trip, provider)
    result = optimize(trip, provider, engine=engine)
    snapshot_date = get_snapshot_date()
    if isinstance(result, IncompleteTrip):
        return IncompleteTripSchema.from_core(result, snapshot_date=snapshot_date)
    return TripResultSchema.from_core(result, snapshot_date=snapshot_date)
