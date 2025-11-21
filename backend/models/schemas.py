"""Pydantic models for request and response payloads."""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from app.core.constants import MAX_DEPTH


class EncodeRequest(BaseModel):
    """Carries latitude, longitude, and depth parameters for encoding."""

    lat: float = Field(..., description="Latitude in WGS84.")
    lon: float = Field(..., description="Longitude in WGS84.")
    depth: int = Field(..., ge=0, le=MAX_DEPTH, description="Depth (0 maps to a single character).")


class EncodeResponse(BaseModel):
    """Represents the resulting hash and projected coordinates."""

    hash: str
    x_proj: float
    y_proj: float


class DecodeRequest(BaseModel):
    """Carries the geospatial hash to be decoded."""

    hash: str


class DecodeResponse(BaseModel):
    """Represents decoded geospatial information for a tile."""

    lat: float
    lon: float
    x_proj_min: float
    y_proj_min: float
    tile_size_m: float


class GeoJSONGeometry(BaseModel):
    """Represents a GeoJSON polygon geometry."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    """Represents a GeoJSON feature for a geohash tile."""

    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]
