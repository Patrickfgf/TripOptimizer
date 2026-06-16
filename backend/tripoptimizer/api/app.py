"""FastAPI application assembly."""

from fastapi import FastAPI

from tripoptimizer.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripOptimizer API",
        version="0.1.0",
        description="Cheapest multi-city trip-ordering optimizer.",
    )
    app.include_router(router)
    return app


app = create_app()
