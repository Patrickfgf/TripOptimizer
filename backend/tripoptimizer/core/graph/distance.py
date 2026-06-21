"""Great-circle distance between two lat/lon points."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometers."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    # clamp to [0, 1]: float rounding can push `a` just past 1.0 on near-antipodal
    # points, which would make asin() raise a math domain error.
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, a)))
