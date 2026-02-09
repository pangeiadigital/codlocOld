"""Pydantic models for request and response payloads."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings


class NeighborMethod(str, Enum):
    """Available methods for neighbor search."""
    QUEEN = "Queen"
    ROOK = "Rook"
    RADIUS = "Radius"


class NeighborPredicate(str, Enum):
    """Spatial predicates for Radius search."""
    CENTROID = "Centroid"
    INTERSECTS = "Intersects"
    WITHIN = "Within"


def normalize_crs(v: Optional[str]) -> str:
    """Normalizes CRS input to standard internal names. Defaults to SIRGAS 2000."""
    if not v:
        return "SIRGAS 2000"
    
    normalized = v.strip().upper()
    
    if normalized in ["WGS 84", "4326", "WGS84"]:
        return "WGS 84"
    if normalized in ["SIRGAS 2000", "SIRGAS2000", "4674", "SIRGAS"]:
        return "SIRGAS 2000"
        
    return "SIRGAS 2000"


class CRSProperty(BaseModel):
    """Properties for the CRS object."""
    name: str


class CRSObject(BaseModel):
    """GeoJSON CRS object definition."""
    type: Literal["name"] = "name"
    properties: CRSProperty


class EncodeRequest(BaseModel):
    """Carries latitude, longitude, and precision parameters for encoding."""

    lat: float = Field(..., description="Latitude.")
    lon: float = Field(..., description="Longitude.")
    precision: int = Field(..., ge=1, le=settings.MAX_PRECISION, description="Precision level.")
    crsInput: Optional[str] = Field(default="SIRGAS 2000", description="Input CRS (WGS 84 or SIRGAS 2000). Defaults to SIRGAS 2000.")

    @field_validator('crsInput', mode='before')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return normalize_crs(v)


class EncodeResponse(BaseModel):
    """Represents the resulting hash and projected coordinates."""

    codloc: str
    lat: float
    lon: float
    crsOutput: str
    precision: int
    tileSideLength: float


class DecodeRequest(BaseModel):
    """Carries the geospatial hash to be decoded."""

    codloc: str
    crsOutput: Optional[str] = Field(default="SIRGAS 2000", description="Output CRS. Defaults to SIRGAS 2000.")

    @field_validator('crsOutput', mode='before')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return normalize_crs(v)


class DecodeResponse(BaseModel):
    """Represents decoded geospatial information for a tile."""

    codloc: str
    lat: float
    lon: float
    crsOutput: str
    tileSideLength: float


class GeoJSONGeometry(BaseModel):
    """Represents a GeoJSON polygon geometry."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    """Represents a GeoJSON feature for a geohash tile."""

    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class NeighborRequest(BaseModel):
    """Parameters for finding neighbors of a given CodLoc."""

    codloc: str = Field(..., description="CODLOC value")
    neighborMethod: NeighborMethod
    neighborThreshold: float
    neighborPredicate: NeighborPredicate = NeighborPredicate.CENTROID
    neighborPrecision: int = Field(..., ge=1, le=settings.MAX_PRECISION)
    crsOutput: Optional[str] = Field(default="SIRGAS 2000", description="Output CRS. Defaults to SIRGAS 2000.")

    @field_validator('crsOutput', mode='before')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return normalize_crs(v)

    @field_validator('neighborThreshold')
    @classmethod
    def validate_complexity(cls, v: float, info: Any) -> float:
        if not info.data or 'neighborPrecision' not in info.data:
            return v
            
        precision = info.data['neighborPrecision']
        
        aoi_width = settings.X_MAX - settings.X_MIN
        tile_width = aoi_width / (settings.GRID_BASE ** precision)
        
        if info.data.get('neighborMethod') == NeighborMethod.RADIUS:
            span = (v * 2) / tile_width
        else:
            span = v * 2
            
        estimated_tiles = span * span
        
        if estimated_tiles > settings.MAX_NEIGHBOR_TILES:
            raise ValueError(
                f"Complexity limit exceeded. Approx {int(estimated_tiles)} tiles."
            )
        
        return v


class NeighborResponse(BaseModel):
    """Response containing the collection of neighboring features."""

    codloc: str
    neighborMethod: NeighborMethod
    neighborThreshold: float
    neighborPredicate: NeighborPredicate
    neighborPrecision: int
    type: Literal["FeatureCollection"] = "FeatureCollection"
    crs: CRSObject
    features: List[GeoJSONFeature]