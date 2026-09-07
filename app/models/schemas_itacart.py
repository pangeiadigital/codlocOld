"""Pydantic schemas for the ITACaRT API."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings


class ITACaRTEncodeRequest(BaseModel):
    """Request model for encoding coordinates to ITACaRT."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (WGS 84)")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (WGS 84)")
    depth: int = Field(
        default=settings.ITACART_MAX_PRECISION,
        ge=1,
        le=settings.ITACART_MAX_PRECISION,
        description="Hierarchical depth (1-9)",
    )


class ITACaRTEncodeResponse(BaseModel):
    """Response model for ITACaRT encoding."""
    canonical: str = Field(..., description="Human-readable canonical hash with parentheses")
    compact: str = Field(..., description="Compact base36 representation for storage/URLs")
    depth: int = Field(..., description="The precision depth of the hash")
    quadrant: str = Field(..., description="Global quadrant (NE, NW, SE, SW)")
    cell_side: Optional[float] = Field(None, description="Cell side length in metres")
    cell_area: Optional[float] = Field(None, description="Cell area in square metres")


class ITACaRTDecodeRequest(BaseModel):
    """Request model for decoding ITACaRT hashes."""
    hash: str = Field(..., description="The ITACaRT hash (either canonical or compact)")
    is_compact: bool = Field(False, description="Whether the provided hash is in compact format")
    depth: Optional[int] = Field(None, description="Required only if decoding a compact hash")


class ITACaRTDecodeResponse(BaseModel):
    """Response model for ITACaRT decoding."""
    lat: float = Field(..., description="Centroid latitude")
    lon: float = Field(..., description="Centroid longitude")
    canonical: str = Field(..., description="Canonical hash representation")
    compact: str = Field(..., description="Compact hash representation")
    depth: int = Field(..., description="Hierarchical depth")
    quadrant: str = Field(..., description="Global quadrant (NE, NW, SE, SW)")
    cell_side: Optional[float] = Field(None, description="Cell side length in metres")
    cell_area: Optional[float] = Field(None, description="Cell area in square metres")
    bbox: List[List[float]] = Field(..., description="Bounding box polygon as a list of [lon, lat] points")


class ITACaRTGeoJSONResponse(BaseModel):
    """GeoJSON representation of an ITACaRT cell."""
    type: str = "Feature"
    geometry: dict
    properties: dict


class ITACaRTNeighborResponse(BaseModel):
    """Response model for a single neighbor."""
    canonical: str
    compact: str
    neighborLevel: int
    neighborDistance: float
    azimute: float
    bbox: List[List[float]]


class ITACaRTNeighborsResponse(BaseModel):
    """Response model for a neighbor search query."""
    neighbors: List[ITACaRTNeighborResponse]
    search_boundary: Optional[List[List[float]]] = None
