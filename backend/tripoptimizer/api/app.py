"""FastAPI application assembly."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tripoptimizer.api.routes import router

DEFAULT_ORIGINS = "http://localhost:5173"


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripOptimizer API",
        version="0.1.0",
        description="Cheapest multi-city trip-ordering optimizer.",
    )
    origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
