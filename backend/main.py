"""Application entry point for the geospatial hashing API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.geo import router as geo_router

def create_application() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="Geospatial Hashing Service",
        description="Encode and decode Gilbert-based Base36 geohashes.",
        version="1.0.0",
        docs_url="/swagger",
        redoc_url="/docs",
    )

    # origins = [
    #     "http://localhost:8080",
    #     "http://127.0.0.1:8080",
    #     "http://192.168.15.189:8080"
    # ]

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
