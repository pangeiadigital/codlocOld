"""Application entry point for the geospatial hashing API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.geo import router as geo_router
from app.core.crs import build_transformers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager.
    Loads transformers for supported CRSs (WGS 84, SIRGAS 2000) at startup.
    """
    # Returns a dict: {'WGS 84': (fwd, inv), 'SIRGAS 2000': (fwd, inv)}
    transformers_dict = build_transformers()
    app.state.transformers = transformers_dict
    yield


def create_application() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="Geospatial Hashing Service",
        description="Encode and decode Gilbert-based Base36 geohashes with Multi-CRS support.",
        version="1.1.0",
        docs_url="/swagger",
        redoc_url="/docs",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(geo_router)
    return app


app = create_application()