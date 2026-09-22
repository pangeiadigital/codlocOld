"""Pydantic schemas for the ITACaRT API."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.models.schemas import CRSObject, validate_crs_support


class ITACaRTEncodeRequest(BaseModel):
    """Request model for encoding coordinates to ITACaRT."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    depth: int = Field(
        default=settings.ITACART_MAX_PRECISION,
        ge=1,
        le=settings.ITACART_MAX_PRECISION,
        description="Hierarchical depth (1-9)",
    )
    crsOutput: Optional[str] = Field(
        default="4674",
        description="Output CRS 4326 (WGS 84) or 4674 (SIRGAS 2000). Defaults to 4674 (SIRGAS 2000).",
    )
    crsInput: Optional[str] = Field(
        default=None,
        description="Input CRS 4326 (WGS 84) or 4674 (SIRGAS 2000). If specified, overrides default.",
    )

    @field_validator('crsOutput')
    @classmethod
    def validate_crs_out(cls, v: Optional[str]) -> str:
        return validate_crs_support(v)

    @field_validator('crsInput')
    @classmethod
    def validate_crs_in(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_crs_support(v)
        return v


class ITACaRTEncodeResponse(BaseModel):
    """Response model for ITACaRT encoding."""
    canonical: str = Field(..., description="Human-readable canonical hash with parentheses")
    compact: str = Field(..., description="Compact base36 representation for storage/URLs")
    depth: int = Field(..., description="The precision depth of the hash")
    quadrant: str = Field(..., description="Global quadrant (NE, NW, SE, SW)")
    cell_side: Optional[float] = Field(None, description="Cell side length in metres")
    cell_area: Optional[float] = Field(None, description="Cell area in square metres")
    lat: float = Field(..., description="Latitude in the output CRS")
    lon: float = Field(..., description="Longitude in the output CRS")
    crsOutput: str = Field(default="4674", description="Output CRS (4674 or 4326)")


class ITACaRTDecodeRequest(BaseModel):
    """Request model for decoding ITACaRT hashes."""
    hash: str = Field(..., description="The ITACaRT hash (either canonical or compact)")
    is_compact: bool = Field(False, description="Whether the provided hash is in compact format")
    depth: Optional[int] = Field(None, description="Required only if decoding a compact hash")
    crsOutput: Optional[str] = Field(
        default="4674",
        description="Output CRS 4326 (WGS 84) or 4674 (SIRGAS 2000). Defaults to 4674 (SIRGAS 2000).",
    )

    @field_validator('crsOutput')
    @classmethod
    def validate_crs_out(cls, v: Optional[str]) -> str:
        return validate_crs_support(v)


class ITACaRTDecodeResponse(BaseModel):
    """Response model for ITACaRT decoding."""
    lat: float = Field(..., description="Centroid latitude in the output CRS")
    lon: float = Field(..., description="Centroid longitude in the output CRS")
    canonical: str = Field(..., description="Canonical hash representation")
    compact: str = Field(..., description="Compact hash representation")
    depth: int = Field(..., description="Hierarchical depth")
    quadrant: str = Field(..., description="Global quadrant (NE, NW, SE, SW)")
    cell_side: Optional[float] = Field(None, description="Cell side length in metres")
    cell_area: Optional[float] = Field(None, description="Cell area in square metres")
    bbox: List[List[float]] = Field(..., description="Bounding box polygon as a list of [lon, lat] points")
    crsOutput: str = Field(default="4674", description="Output CRS (4674 or 4326)")


class ITACaRTGeoJSONResponse(BaseModel):
    """GeoJSON representation of an ITACaRT cell."""
    type: str = "Feature"
    crs: CRSObject
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
