"""Application entry point for the geospatial hashing API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.geo import router as geo_router
from app.api.routes.itacart import router as itacart_router
from app.core.crs import build_transformers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager.
    Loads transformers for supported CRSs (WGS 84, SIRGAS 2000) at startup.
    """
    transformers_dict = build_transformers()
    app.state.transformers = transformers_dict
    yield


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler to simplify Pydantic validation errors.
    Converts the complex default JSON into a simple {'detail': '...'} format.
    """
    error_messages = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field_name = str(loc[-1]) if loc else "body"
        message = error.get("msg", "Invalid input")
        
        error_messages.append(f"{field_name}: {message}")
    
    final_detail = "; ".join(error_messages)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": final_detail},
    )


def create_application() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    
    description = """
## What is CODLOC?

CODLOC<sup>&reg;</sup> is a system of codes and short names for geographic locations transformed from GNSS coordinates. For more information, visit [codloc.com](https://codloc.com).

## Personas

For individual users, an APP and a connected [webpage](https://app.codloc.com) are available for simple one-off queries, without the need for registration and/or authentication.

For users representing legal entities, access is controlled through authentication.

## Copyright &copy;

O CODLOC<sup>&reg;</sup> is a registered trademark of [PangeIA Digital](https://pangeia.digital)
    """

    app = FastAPI(
        title="CODLOC API Service",
        description=description.strip(),
        version="1.0.0",
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
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    app.include_router(geo_router)
    app.include_router(itacart_router, prefix="/v2/itacart", tags=["ITACaRT"])
    return app


app = create_application()