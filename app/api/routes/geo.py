"""API routes for geospatial encoding and decoding."""

from typing import Tuple

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pyproj import Transformer
from app.core.security import validate_token
from app.core.config import settings
from app.core.gilbert import math_decode, math_encode
from app.models.schemas import (
    CRSObject,
    CRSProperty,
    DecodeRequest,
    DecodeResponse,
    EncodeRequest,
    EncodeResponse,
    GeoJSONFeature,
    GeoJSONFeatureWithCRS,
    GeoJSONGeometry,
    NeighborRequest,
    NeighborResponse,
    validate_crs_support,
)
from app.services.geospatial_service import find_neighbors, tile_size_at_depth

#router = APIRouter(prefix="/geo", tags=["Geospatial"], dependencies=[Depends(validate_token)])
router = APIRouter(prefix="/geo")

def get_transformer_pair(request: Request, crs_name: str) -> Tuple[Transformer, Transformer]:
    """Retrieves the (forward, inverse) transformer pair for the specified CRS."""
    transformers = request.app.state.transformers
    if crs_name not in transformers:
        return transformers["SIRGAS 2000"]
    return transformers[crs_name]


def build_crs_object(crs_name: str) -> CRSObject:
    """Builds the GeoJSON CRS object with the appropriate EPSG URN."""
    # Map internal names to OGC URNs
    if crs_name == "4674":
        urn = "urn:ogc:def:crs:EPSG::4674"
    elif crs_name == "4326":
        urn = "urn:ogc:def:crs:EPSG::4326"
    else:
        # Fallback to SIRGAS 2000 if unknown
        urn = "urn:ogc:def:crs:EPSG::4674"
        
    return CRSObject(properties=CRSProperty(name=urn))


@router.post(
    "/encode",
    response_model=EncodeResponse,
    tags=["Unitary Mode"],
    summary="Encodes latitude and longitude to discover a CODLOC",
    description=(
        "**Encodes latitude and longitude into a CODLOC using the specified input Coordinate Reference System (CRS)**.\n"
        "\n"
        "Please see the schema and domains on Schemas section."
    ),
    operation_id="post_unitary_encode"
)
def encode(payload: EncodeRequest, request: Request) -> EncodeResponse:
    """Encodes coordinates into a codloc using the specified input CRS."""
    forward, _ = get_transformer_pair(request, payload.crsInput)
    
    projected_x, projected_y = forward.transform(payload.lon, payload.lat)

    is_outside = (
        projected_x < settings.X_MIN or projected_x > settings.X_MAX or
        projected_y < settings.Y_MIN or projected_y > settings.Y_MAX
    )

    if is_outside:
        raise HTTPException(
            status_code=422, 
            detail="Coordinates outside the CODLOC coverage area."
        )

    try:
        codloc_hash, _, _ = math_encode(projected_x, projected_y, payload.precision)
        side_length, _ = tile_size_at_depth(payload.precision)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return EncodeResponse(
        codloc=codloc_hash,
        lat=payload.lat,
        lon=payload.lon,
        crsOutput=payload.crsInput,
        precision=payload.precision,
        tileSideLength=round(side_length, 2),
    )


@router.post(
    "/decode",
    response_model=DecodeResponse,
    tags=["Unitary Mode"],
    summary="Decode CODLOC to discover latitude and longitude coordinates",
    description=(
        "**Decodes CODLOC into latitude and longitude coordinates using the specified output Coordinate Reference System (CRS)**.\n"
        "\n"
        "Please see the schema and domains on Schemas section."
    ),
    operation_id="post_unitary_decode"
)
def decode(payload: DecodeRequest, request: Request) -> DecodeResponse:
    """Decodes a codloc back to coordinates in the specified output CRS."""
    _, inverse = get_transformer_pair(request, payload.crsOutput)
    
    try:
        tile_x, tile_y, width, height = math_decode(payload.codloc)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    
    centroid_x = tile_x + width / 2.0
    centroid_y = tile_y + height / 2.0
    lon, lat = inverse.transform(centroid_x, centroid_y)
    tile_size = min(width, height)
    
    return DecodeResponse(
        codloc=payload.codloc,
        lat=lat,
        lon=lon,
        crsOutput=payload.crsOutput,
        tileSideLength=tile_size,
    )


@router.get(
    "/geojson/{codloc_value}",
    response_model=GeoJSONFeatureWithCRS,
    tags=["Unitary Mode"],
    summary="Returns a single geo-object tile given a CODLOC",
    description=(
        "**Returns a geo-object as GeoJSON format describing the tile using the specified output Coordinate Reference System (CRS)**.\n"
        "\n"
        "Please see the schema and domains on Schemas section."
    ),
    operation_id="get_unitary_tile"
)
def geojson(
    codloc_value: str, 
    request: Request,
    crsOutput: str = Query(default="4674", description="Output CRS 4326 (WGS 84) or 4674 (SIRGAS 2000)")
) -> GeoJSONFeatureWithCRS:
    """Returns a GeoJSON feature describing the tile using the specified output CRS."""

    normalized_crs = validate_crs_support(crsOutput)
    _, inverse = get_transformer_pair(request, normalized_crs)

    try:
        tile_x, tile_y, width, height = math_decode(codloc_value)
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

    normalized_hash = codloc_value.strip().upper()
    geometry = GeoJSONGeometry(coordinates=[ring_lon_lat])
    
    # Generate CRS Object
    crs_obj = build_crs_object(normalized_crs)

    properties = {
        "codloc": normalized_hash,
        "lat": lat,
        "lon": lon,
    }
    
    return GeoJSONFeatureWithCRS(geometry=geometry, crs=crs_obj, properties=properties)


@router.post(
    "/neighbors",
    response_model=NeighborResponse,
    tags=["Multiple Mode"],
    summary="Neighbors Search",
    description=(
        "**Finds neighboring CODLOCs and returns coordinates and its tiles in the specified output Coordinate Reference System (CRS)**.\n"
        "\n"
        "- For search neighbors by **proximity/distance**, use the combination _neighborMethod_ = _**'Radius'**_ and _neighborPredicate_ = _**'Centroid'**_ and _neighborThreshold_ = _**'[values greater than zero]'**_ to radius in meters\n"
        "\n"
        "- For search neighbors by **location/shared boundaries**, use the combination _neighborMethod_ = _**'Queen'**_ or _**'Rook'**_ and _neighborPredicate_ = _**'Intersects'**_ or _**'Within'**_ and _neighborThreshold_ = _**'[values greater than zero]'**_ to number of neighbors desired to reach\n"
        "\n"
        "**OBS**: Note that the choice of precision can affect the result. It is advisable to search for neighbors at the same level or lower with respect to the reference/input CODLOC.\n"
        "\n"
        "Please see the schema and domains on Schemas section."
    ),
    operation_id="post_multiple_neighbors"
)
def neighbors(payload: NeighborRequest, request: Request) -> NeighborResponse:
    """Finds neighboring tiles and returns coordinates in the specified output CRS."""
    _, inverse = get_transformer_pair(request, payload.crsOutput)
    
    try:
        results, boundary_coords = find_neighbors(
            center_codloc=payload.codloc,
            method=payload.neighborMethod.value,
            threshold=payload.neighborThreshold,
            predicate=payload.neighborPredicate.value,
            precision=payload.neighborPrecision,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    features = []
    
    if boundary_coords:
        boundary_lon_lat = []
        for x_coord, y_coord in boundary_coords:
            lon, lat = inverse.transform(x_coord, y_coord)
            boundary_lon_lat.append([lon, lat])
        
        boundary_feature = GeoJSONFeature(
            geometry=GeoJSONGeometry(coordinates=[boundary_lon_lat]),
            properties={
                "type": "search_boundary",
                "method": payload.neighborMethod.value,
                "threshold": payload.neighborThreshold,
                "crs": payload.crsOutput
            }
        )
        features.append(boundary_feature)

    for res in results:
        ring_proj = res["projected_geometry"]
        ring_lon_lat = []
        for x_coord, y_coord in ring_proj:
            lon, lat = inverse.transform(x_coord, y_coord)
            ring_lon_lat.append([lon, lat])
            
        geometry = GeoJSONGeometry(coordinates=[ring_lon_lat])
        
        properties = {
            "codloc": res["codloc"],
            "neighborLevel": res["neighborLevel"],
            "neighborDistance": res["neighborDistance"],
            "azimute": res["azimute"]
        }
        
        features.append(GeoJSONFeature(geometry=geometry, properties=properties))

    # Generate CRS Object for the FeatureCollection
    crs_obj = build_crs_object(payload.crsOutput)

    return NeighborResponse(
        codloc=payload.codloc,
        neighborMethod=payload.neighborMethod,
        neighborThreshold=payload.neighborThreshold,
        neighborPredicate=payload.neighborPredicate,
        neighborPrecision=payload.neighborPrecision,
        crsOutput=payload.crsOutput,
        crs=crs_obj,
        features=features
    )