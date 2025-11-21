"""API routes for geospatial encoding and decoding."""

from fastapi import APIRouter, HTTPException

from app.core.crs import build_transformers
from app.models.schemas import (
    DecodeRequest,
    DecodeResponse,
    EncodeRequest,
    EncodeResponse,
    GeoJSONFeature,
    GeoJSONGeometry,
)
from app.services.geospatial_service import decode_to_xy, encode_xy

router = APIRouter(prefix="/geo", tags=["Geospatial"])


@router.post("/encode", response_model=EncodeResponse)
def encode(payload: EncodeRequest) -> EncodeResponse:
    """Encodes geographic coordinates into a geohash."""
    forward, _ = build_transformers()
    depth = max(1, payload.depth)
    projected_x, projected_y = forward.transform(payload.lon, payload.lat)
    try:
        geo_hash, tile_x, tile_y = encode_xy(projected_x, projected_y, depth)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return EncodeResponse(hash=geo_hash, x_proj=projected_x, y_proj=projected_y)


@router.post("/decode", response_model=DecodeResponse)
def decode(payload: DecodeRequest) -> DecodeResponse:
    """Decodes a geohash back to geographic coordinates."""
    _, inverse = build_transformers()
    try:
        tile_x, tile_y, width, height = decode_to_xy(payload.hash)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    centroid_x = tile_x + width / 2.0
    centroid_y = tile_y + height / 2.0
    lon, lat = inverse.transform(centroid_x, centroid_y)
    tile_size = min(width, height)
    return DecodeResponse(
        lat=lat,
        lon=lon,
        x_proj_min=tile_x,
        y_proj_min=tile_y,
        tile_size_m=tile_size,
    )


@router.get("/geojson/{hash_value}", response_model=GeoJSONFeature)
def geojson(hash_value: str) -> GeoJSONFeature:
    """Returns a GeoJSON feature describing the tile for the given hash."""

    _, inverse = build_transformers()
    try:
        tile_x, tile_y, width, height = decode_to_xy(hash_value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    ring_proj = [
        (tile_x, tile_y),
        (tile_x + width, tile_y),
        (tile_x + width, tile_y + height),
        (tile_x, tile_y + height),
        (tile_x, tile_y),
    ]
    ring_lon_lat = []
    for x_coord, y_coord in ring_proj:
        lon, lat = inverse.transform(x_coord, y_coord)
        ring_lon_lat.append([lon, lat])

    normalized_hash = hash_value.strip().upper()
    geometry = GeoJSONGeometry(coordinates=[ring_lon_lat])
    properties = {
        "hash": normalized_hash,
        "x_proj_min": tile_x,
        "y_proj_min": tile_y,
        "width_m": width,
        "height_m": height,
    }
    return GeoJSONFeature(geometry=geometry, properties=properties)
