"""Point the API at a non-existent snapshot so tests see synthetic-only fallback,
regardless of any committed data/fares_snapshot.parquet."""

import pytest

from tripoptimizer.api import dependencies


@pytest.fixture(autouse=True)
def _no_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIPOPTIMIZER_SNAPSHOT", str(tmp_path / "absent.parquet"))
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)  # deterministic: no live layer
    dependencies.get_provider.cache_clear()
    dependencies.get_snapshot_date.cache_clear()
    yield
    dependencies.get_provider.cache_clear()
    dependencies.get_snapshot_date.cache_clear()
