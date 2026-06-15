from tripoptimizer.core.graph.distance import haversine_km


def test_distance_is_zero_for_same_point():
    assert haversine_km(38.77, -9.13, 38.77, -9.13) == 0.0


def test_lisbon_to_barcelona_is_about_1000_km():
    # LIS (38.7742, -9.1342) -> BCN (41.2974, 2.0833)
    d = haversine_km(38.7742, -9.1342, 41.2974, 2.0833)
    assert 950 < d < 1050


def test_longer_route_is_greater():
    lis_bcn = haversine_km(38.7742, -9.1342, 41.2974, 2.0833)
    lis_ath = haversine_km(38.7742, -9.1342, 37.9364, 23.9445)  # Athens, much farther
    assert lis_ath > lis_bcn
