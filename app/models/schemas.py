"""Pydantic models for request and response payloads."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

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

def validate_crs_support(v: Optional[str]) -> str:
    """Normalizes CRS input to standard internal names."""
    if not v:
        return "4674"
    
    normalized = v.strip().upper()
    
    if normalized in ["4326"]:
        return "4326"
    if normalized in ["4674"]:
        return "4674"
    
    raise ValueError(f"Coordinate system not supported. Use '4326' (WGS 84) or '4674' (SIRGAS 2000).")

class CRSProperty(BaseModel):
    """Properties for the CRS object."""
    name: str


class CRSObject(BaseModel):
    """GeoJSON CRS object definition."""
    type: Literal["name"] = "name"
    properties: CRSProperty


class EncodeRequest(BaseModel):
    """Carries latitude, longitude, and precision parameters for encoding."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude entre -90 e 90.")
    lon: float = Field(..., ge=-180, le=180, description="Longitude entre -180 e 180.")
    precision: int = Field(..., ge=1, le=settings.MAX_PRECISION)
    crsInput: Optional[str] = Field(default="4674", description="Input CRS 4326 (WGS 84) or 4674 (SIRGAS 2000).")

    @field_validator('crsInput')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return validate_crs_support(v)


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
    crsOutput: Optional[str] = Field(default="4674", description="Output CRS. Defaults to 4674 (SIRGAS 2000).")

    @field_validator('crsOutput')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return validate_crs_support(v)


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

class GeoJSONFeatureWithCRS(BaseModel):
    """Represents a GeoJSON feature for a geohash tile."""

    type: Literal["Feature"] = "Feature"
    crs: CRSObject
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]

class GeoJSONFeature(BaseModel):
    """Represents a GeoJSON feature for a geohash tile inside Neighbor."""

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
    crsOutput: str = Field(default="4674", description="Output CRS. Defaults to 4674 (SIRGAS 2000.")

    @field_validator('crsOutput')
    @classmethod
    def validate_crs(cls, v: Optional[str]) -> str:
        return validate_crs_support(v)

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