"""Service layer for ITACaRT geospatial operations (neighbors, radius search).

This module utilizes vectorized computations (NumPy) in the sinusoidal projection
space to find neighbors efficiently.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Point, box

from app.core import itacart_engine
from app.core.config import settings
from app.core.itacart_constants import MAX_BASE_IX, MAX_BASE_IY, BASE_CELL_SIZE


def _get_max_sinu_coords() -> Tuple[float, float]:
    """Return the maximum valid sinusoidal coordinates (X, Y) in metres."""
    max_x = MAX_BASE_IX * BASE_CELL_SIZE
    max_y = MAX_BASE_IY * BASE_CELL_SIZE
    return max_x, max_y


def find_neighbors(
    center_hash: str,
    is_compact: bool,
    method: str,
    threshold: float,
    predicate: str,
    depth: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Optional[List[Tuple[float, float]]]]:
    """
    Calculates neighbors using vectorized operations in sinusoidal space.
    """
    
    # 1. Decode Center
    if is_compact:
        if depth is None:
            raise ValueError("Depth is required when decoding a compact hash.")
        center_info = itacart_engine.decode_compact(center_hash, depth)
    else:
        center_info = itacart_engine.decode_canonical(center_hash)
        depth = center_info["depth"]

    cell_side = center_info["cell_side"]
    if cell_side is None:
        raise ValueError("Cannot find neighbors for level 0 (quadrants).")

    # Get center centroid in geographic and sinusoidal
    center_lat = center_info["lat"]
    center_lon = center_info["lon"]
    center_cx, center_cy = itacart_engine._latlon_to_sinu(center_lon, center_lat)

    # Calculate global cell indices in a hypothetical global continuous sinusoidal space
    # For simplicity across quadrants, we use continuous coords where (0,0) is Equator/Prime Meridian
    center_ix = int(math.floor(center_cx / cell_side))
    center_iy = int(math.floor(center_cy / cell_side))

    search_boundary_latlon = None
    
    # 2. Define Bounds (Bounding Box in continuous indices)
    if method == "Radius":
        radius = threshold
        steps_x = int(math.ceil(radius / cell_side))
        steps_y = int(math.ceil(radius / cell_side))
        
        # Create search boundary geometry (in sinusoidal)
        ref_point = Point(center_cx, center_cy)
        search_area = ref_point.buffer(radius)
        
        # Convert search boundary to lat/lon for the response
        search_boundary_latlon = []
        for x, y in search_area.exterior.coords:
            lon, lat = itacart_engine._sinu_to_latlon(x, y)
            search_boundary_latlon.append((lon, lat))
    else:
        # Queen/Rook: threshold is steps
        steps = int(threshold)
        steps_x = steps
        steps_y = steps

    # Calculate index boundaries
    min_ix = center_ix - steps_x
    max_ix = center_ix + steps_x
    min_iy = center_iy - steps_y
    max_iy = center_iy + steps_y

    # Limit by global extent
    max_bound_x = int((MAX_BASE_IX * BASE_CELL_SIZE) / cell_side)
    max_bound_y = int((MAX_BASE_IY * BASE_CELL_SIZE) / cell_side)
    
    min_ix = max(-max_bound_x, min_ix)
    max_ix = min(max_bound_x - 1, max_ix)
    min_iy = max(-max_bound_y, min_iy)
    max_iy = min(max_bound_y - 1, max_iy)

    # 3. Vectorized Grid Generation
    ix_range = np.arange(min_ix, max_ix + 1)
    iy_range = np.arange(min_iy, max_iy + 1)
    
    xv, yv = np.meshgrid(ix_range, iy_range)
    
    ix_flat = xv.flatten()
    iy_flat = yv.flatten()

    # Calculate candidate centroids in sinusoidal
    cand_centroid_x = (ix_flat + 0.5) * cell_side
    cand_centroid_y = (iy_flat + 0.5) * cell_side

    # Deltas
    dx = cand_centroid_x - center_cx
    dy = cand_centroid_y - center_cy
    
    # Distances (Euclidean in sinusoidal)
    dist_meters = np.sqrt(dx**2 + dy**2)
    
    # Levels (Chebyshev for Queen, Manhattan for Rook)
    diff_x = np.abs(ix_flat - center_ix)
    diff_y = np.abs(iy_flat - center_iy)
    chebyshev = np.maximum(diff_x, diff_y)
    manhattan = diff_x + diff_y

    # 4. Filtering (Vector Masking)
    if method == "Queen":
        mask = chebyshev <= threshold
    elif method == "Rook":
        mask = manhattan <= threshold
    elif method == "Radius":
        if predicate == "Centroid":
            mask = dist_meters <= threshold
        else:
            mask = np.ones_like(dist_meters, dtype=bool)

    valid_indices = np.where(mask)[0]
    
    # Enforce MAX_NEIGHBOR_TILES limit to prevent server crash
    if len(valid_indices) > settings.MAX_NEIGHBOR_TILES:
        # If it's radius, sort by distance. Otherwise, take first N (or sort by level)
        if method == "Radius":
            sorted_by_dist = np.argsort(dist_meters[valid_indices])
            valid_indices = valid_indices[sorted_by_dist[:settings.MAX_NEIGHBOR_TILES]]
        else:
            valid_indices = valid_indices[:settings.MAX_NEIGHBOR_TILES]
    
    neighbors = []
    
    # 5. Result Construction
    for i in valid_indices:
        d_meter = float(dist_meters[i])
        lvl = int(chebyshev[i])
        
        c_cx = float(cand_centroid_x[i])
        c_cy = float(cand_centroid_y[i])
        
        # Double check for Radius geometric predicates
        if method == "Radius" and predicate in ["Intersects", "Within"]:
            c_min_x = c_cx - cell_side / 2.0
            c_min_y = c_cy - cell_side / 2.0
            cell_poly = box(c_min_x, c_min_y, c_min_x + cell_side, c_min_y + cell_side)
            
            if predicate == "Intersects" and not cell_poly.intersects(search_area):
                continue
            if predicate == "Within" and not search_area.contains(cell_poly):
                continue

        # Calculate Azimuth (in sinusoidal space)
        dx_val = float(dx[i])
        dy_val = float(dy[i])
        azimute = (math.degrees(math.atan2(dx_val, dy_val)) + 360) % 360

        # Back to geographic to encode properly
        cand_lon, cand_lat = itacart_engine._sinu_to_latlon(c_cx, c_cy)
        
        # Clamp just in case due to float inaccuracies near boundaries
        cand_lon = max(-180.0, min(180.0, cand_lon))
        cand_lat = max(-90.0, min(90.0, cand_lat))

        c_info = itacart_engine.encode(cand_lat, cand_lon, depth)

        neighbors.append({
            "canonical": c_info["canonical"],
            "compact": c_info["compact"],
            "neighborLevel": lvl,
            "neighborDistance": d_meter,
            "azimute": azimute,
            "bbox": itacart_engine.cell_geometry_latlon(itacart_engine._parse_canonical(c_info["canonical"]))
        })

    return neighbors, search_boundary_latlon
