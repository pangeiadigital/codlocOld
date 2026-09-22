from typing import Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pyproj import Transformer

from app.core import itacart_engine
from app.services import itacart_neighbors
from app.models.schemas import validate_crs_support
from app.api.routes.geo import build_crs_object
from app.models.schemas_itacart import (
    ITACaRTDecodeRequest,
    ITACaRTDecodeResponse,
    ITACaRTEncodeRequest,
    ITACaRTEncodeResponse,
    ITACaRTGeoJSONResponse,
    ITACaRTNeighborsResponse,
)

router = APIRouter()

# Coordinate transformers between supported CRSs (EPSG:4674 SIRGAS 2000 and EPSG:4326 WGS 84)
_TRANSFORMER_4674_TO_4326 = Transformer.from_crs("EPSG:4674", "EPSG:4326", always_xy=True)
_TRANSFORMER_4326_TO_4674 = Transformer.from_crs("EPSG:4326", "EPSG:4674", always_xy=True)


def transform_coords(lon: float, lat: float, from_crs: str, to_crs: str) -> Tuple[float, float]:
    """Transforms a coordinate pair between 4674 and 4326."""
    if from_crs == to_crs:
        return lon, lat
    if from_crs == "4674" and to_crs == "4326":
        return _TRANSFORMER_4674_TO_4326.transform(lon, lat)
    if from_crs == "4326" and to_crs == "4674":
        return _TRANSFORMER_4326_TO_4674.transform(lon, lat)
    return lon, lat


@router.post("/encode", response_model=ITACaRTEncodeResponse)
async def encode_itacart(request: ITACaRTEncodeRequest):
    """
    Encode geographic coordinates to an ITACaRT hash.
    Supports input and output CRS (4674 SIRGAS 2000 or 4326 WGS 84).
    Returns canonical and compact representations.
    """
    try:
        # Determine effective input and output CRS
        crs_in = request.crsInput or request.crsOutput or "4674"
        crs_out = request.crsOutput or crs_in

        # Transform input to WGS 84 for sinusoidal projection
        lon_wgs, lat_wgs = transform_coords(request.lon, request.lat, from_crs=crs_in, to_crs="4326")

        result = itacart_engine.encode(lat_wgs, lon_wgs, request.depth)

        # Output coordinates in requested crsOutput
        lon_out, lat_out = transform_coords(lon_wgs, lat_wgs, from_crs="4326", to_crs=crs_out)

        return ITACaRTEncodeResponse(
            canonical=result["canonical"],
            compact=result["compact"],
            depth=result["depth"],
            quadrant=result["quadrant"],
            cell_side=result.get("cell_side"),
            cell_area=result.get("cell_area"),
            lat=round(lat_out, 8),
            lon=round(lon_out, 8),
            crsOutput=crs_out,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/decode", response_model=ITACaRTDecodeResponse)
async def decode_itacart(request: ITACaRTDecodeRequest):
    """
    Decode an ITACaRT hash (canonical or compact) to its centroid coordinates
    and boundary polygon, returned in the requested crsOutput (4674 or 4326).
    """
    try:
        crs_out = request.crsOutput or "4674"

        if request.is_compact:
            if request.depth is None:
                raise ValueError("Depth is required when decoding a compact hash.")
            result = itacart_engine.decode_compact(request.hash, request.depth)
        else:
            result = itacart_engine.decode_canonical(request.hash)

        # Centroid coordinates transformed to crsOutput
        lon_out, lat_out = transform_coords(result["lon"], result["lat"], from_crs="4326", to_crs=crs_out)

        # Bounding box coordinates transformed to crsOutput
        bbox_out = [
            list(transform_coords(pt[0], pt[1], from_crs="4326", to_crs=crs_out))
            for pt in result["bbox"]
        ]

        return ITACaRTDecodeResponse(
            lat=round(lat_out, 8),
            lon=round(lon_out, 8),
            canonical=result["canonical"],
            compact=result["compact"],
            depth=result["depth"],
            quadrant=result["quadrant"],
            cell_side=result.get("cell_side"),
            cell_area=result.get("cell_area"),
            bbox=bbox_out,
            crsOutput=crs_out,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/geojson", response_model=ITACaRTGeoJSONResponse)
async def get_geojson(
    hash_str: str = Query(..., alias="hash", description="Canonical ITACaRT hash"),
    crsOutput: str = Query("4674", description="Output CRS: 4674 (SIRGAS 2000) or 4326 (WGS 84)"),
):
    """
    Returns the cell polygon as a standard GeoJSON feature.
    """
    try:
        # Defensive check: if query params were chained with '?' instead of '&'
        if "?" in hash_str:
            parts = hash_str.split("?", 1)
            hash_str = parts[0]
            extra = parts[1]
            if "crsOutput=" in extra:
                crsOutput = extra.split("crsOutput=")[1].split("&")[0]

        norm_crs = validate_crs_support(crsOutput)
        result = itacart_engine.decode_canonical(hash_str)

        bbox_out = [
            list(transform_coords(pt[0], pt[1], from_crs="4326", to_crs=norm_crs))
            for pt in result["bbox"]
        ]
        
        properties = {
            "canonical": result["canonical"],
            "compact": result["compact"],
            "depth": result["depth"],
            "quadrant": result["quadrant"],
            "cell_area": result.get("cell_area"),
            "crsOutput": norm_crs,
        }
        
        geometry = {
            "type": "Polygon",
            "coordinates": [bbox_out]
        }
        
        return ITACaRTGeoJSONResponse(
            type="Feature",
            crs=build_crs_object(norm_crs),
            geometry=geometry,
            properties=properties
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/neighbors", response_model=ITACaRTNeighborsResponse)
async def get_neighbors(
    hash_str: str = Query(..., alias="hash", description="ITACaRT hash"),
    is_compact: bool = Query(False, description="Whether hash is in compact format"),
    method: str = Query(..., description="Method: Queen, Rook, or Radius"),
    threshold: float = Query(..., description="Radius in meters or Queen/Rook depth steps"),
    predicate: str = Query("Centroid", description="Centroid, Intersects, or Within (only used for Radius)"),
    depth: int = Query(None, description="Required only if decoding a compact hash"),
):
    """
    Finds neighbor cells around a central ITACaRT hash based on the given method.
    """
    try:
        neighbors, boundary = itacart_neighbors.find_neighbors(
            center_hash=hash_str,
            is_compact=is_compact,
            method=method,
            threshold=threshold,
            predicate=predicate,
            depth=depth,
        )
        return ITACaRTNeighborsResponse(neighbors=neighbors, search_boundary=boundary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
