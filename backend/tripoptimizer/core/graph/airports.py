"""Airport reference data: an immutable model and a CSV loader."""
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lon: float


def load_airports(path: str | Path) -> dict[str, Airport]:
    """Load airports from a CSV (columns: iata,name,city,country,lat,lon)."""
    airports: dict[str, Airport] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            airports[row["iata"]] = Airport(
                iata=row["iata"],
                name=row["name"],
                city=row["city"],
                country=row["country"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
            )
    return airports
