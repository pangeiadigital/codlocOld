"""API routes for the ITACaRT DGGS implementation."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core import itacart_engine
from app.services import itacart_neighbors
from app.models.schemas_itacart import (
    ITACaRTDecodeRequest,
    ITACaRTDecodeResponse,
    ITACaRTEncodeRequest,
    ITACaRTEncodeResponse,
    ITACaRTGeoJSONResponse,
    ITACaRTNeighborsResponse,
)

router = APIRouter()


@router.post("/encode", response_model=ITACaRTEncodeResponse)
async def encode_itacart(request: ITACaRTEncodeRequest):
    """
    Encode geographic coordinates (WGS 84) to an ITACaRT hash.
    Returns canonical and compact representations.
    """
    try:
        result = itacart_engine.encode(request.lat, request.lon, request.depth)
        return ITACaRTEncodeResponse(
            canonical=result["canonical"],
            compact=result["compact"],
            depth=result["depth"],
            quadrant=result["quadrant"],
            cell_side=result.get("cell_side"),
            cell_area=result.get("cell_area"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/decode", response_model=ITACaRTDecodeResponse)
async def decode_itacart(request: ITACaRTDecodeRequest):
    """
    Decode an ITACaRT hash (canonical or compact) to its centroid coordinates
    and boundary polygon.
    """
    try:
        if request.is_compact:
            if request.depth is None:
                raise ValueError("Depth is required when decoding a compact hash.")
            result = itacart_engine.decode_compact(request.hash, request.depth)
        else:
            result = itacart_engine.decode_canonical(request.hash)

        return ITACaRTDecodeResponse(
            lat=result["lat"],
            lon=result["lon"],
            canonical=result["canonical"],
            compact=result["compact"],
            depth=result["depth"],
            quadrant=result["quadrant"],
            cell_side=result.get("cell_side"),
            cell_area=result.get("cell_area"),
            bbox=result["bbox"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/geojson", response_model=ITACaRTGeoJSONResponse)
async def get_geojson(
    hash_str: str = Query(..., alias="hash", description="Canonical ITACaRT hash"),
):
    """
    Returns the cell polygon as a standard GeoJSON feature.
    """
    try:
        result = itacart_engine.decode_canonical(hash_str)
        
        properties = {
            "canonical": result["canonical"],
            "compact": result["compact"],
            "depth": result["depth"],
            "quadrant": result["quadrant"],
            "cell_area": result.get("cell_area"),
        }
        
        geometry = {
            "type": "Polygon",
            "coordinates": [result["bbox"]]
        }
        
        return ITACaRTGeoJSONResponse(
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
