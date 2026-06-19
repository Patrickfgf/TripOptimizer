"""FastAPI application assembly."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tripoptimizer.api.routes import router

DEFAULT_ORIGINS = "http://localhost:5173"

logger = logging.getLogger("tripoptimizer.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripOptimizer API",
        version="0.1.0",
        description="Cheapest multi-city trip-ordering optimizer.",
    )
    raw_origins = os.getenv("FRONTEND_ORIGINS")
    if raw_origins is None:
        logger.warning(
            "FRONTEND_ORIGINS is not set; CORS allows only %s. "
            "Set it to your deployed frontend origin in production.",
            DEFAULT_ORIGINS,
        )
    origins = [o.strip() for o in (raw_origins or DEFAULT_ORIGINS).split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
