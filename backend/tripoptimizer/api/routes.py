"""HTTP endpoints orchestrating the pure core."""

from fastapi import APIRouter, HTTPException

from tripoptimizer.api.dependencies import get_airports

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness + a shallow check that reference data is available."""
    airports = get_airports()
    if not airports:
        raise HTTPException(status_code=503, detail="airport reference data unavailable")
    return {"status": "ok", "airports_loaded": len(airports)}
