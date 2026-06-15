from pathlib import Path

from tripoptimizer.core.graph.airports import Airport, load_airports


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "iata,name,city,country,lat,lon\n"
        "LIS,Humberto Delgado,Lisbon,PT,38.7742,-9.1342\n"
        "BCN,El Prat,Barcelona,ES,41.2974,2.0833\n",
        encoding="utf-8",
    )
    return csv_path


def test_load_airports_returns_dict_keyed_by_iata(tmp_path):
    airports = load_airports(_write_csv(tmp_path))
    assert set(airports) == {"LIS", "BCN"}
    assert isinstance(airports["LIS"], Airport)


def test_airport_fields_are_typed(tmp_path):
    airports = load_airports(_write_csv(tmp_path))
    lis = airports["LIS"]
    assert lis.iata == "LIS"
    assert lis.city == "Lisbon"
    assert lis.country == "PT"
    assert lis.lat == 38.7742
    assert lis.lon == -9.1342
