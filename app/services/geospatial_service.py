"""Service layer for geospatial operations utilizing vectorized computations."""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Point, box

from app.core.config import settings
from app.core.gilbert import math_decode, math_encode


def tile_size_at_depth(depth: int) -> Tuple[float, float]:
    """Computes the tile width and height for a given depth level."""
    aoi_w = settings.X_MAX - settings.X_MIN
    aoi_h = settings.Y_MAX - settings.Y_MIN
    scale = settings.GRID_BASE ** depth
    return aoi_w / scale, aoi_h / scale


def find_neighbors(
    center_codloc: str,
    method: str,
    threshold: float,
    predicate: str,
    precision: int,
) -> Tuple[List[Dict[str, Any]], Optional[List[Tuple[float, float]]]]:
    """
    Calculates neighbors using vectorized operations (NumPy) for high performance.
    """
    
    # 1. Decode Center
    cx_min, cy_min, cw, ch = math_decode(center_codloc)
    center_centroid_x = cx_min + cw / 2.0
    center_centroid_y = cy_min + ch / 2.0

    # 2. Grid Setup
    grid_width, grid_height = tile_size_at_depth(precision)
    grid_max_idx = (settings.GRID_BASE ** precision) - 1

    center_ix = int((center_centroid_x - settings.X_MIN) // grid_width)
    center_iy = int((center_centroid_y - settings.Y_MIN) // grid_height)
    
    # Clamp center index
    center_ix = min(max(0, center_ix), grid_max_idx)
    center_iy = min(max(0, center_iy), grid_max_idx)

    search_boundary = None
    
    # 3. Define Bounds (Bounding Box)
    if method == "Radius":
        radius = threshold
        steps_x = int(math.ceil(radius / grid_width))
        steps_y = int(math.ceil(radius / grid_height))
        
        # Create search boundary geometry
        ref_point = Point(center_centroid_x, center_centroid_y)
        search_area = ref_point.buffer(radius)
        search_boundary = list(search_area.exterior.coords)
    else:
        # Queen/Rook: threshold is steps
        steps = int(threshold)
        steps_x = steps
        steps_y = steps

    min_ix = max(0, center_ix - steps_x)
    max_ix = min(grid_max_idx, center_ix + steps_x)
    min_iy = max(0, center_iy - steps_y)
    max_iy = min(grid_max_idx, center_iy + steps_y)

    # 4. Vectorized Grid Generation
    # Create arrays of indices
    ix_range = np.arange(min_ix, max_ix + 1)
    iy_range = np.arange(min_iy, max_iy + 1)
    
    # Meshgrid to get all combinations of (ix, iy)
    xv, yv = np.meshgrid(ix_range, iy_range)
    
    # Flatten for vectorized processing
    ix_flat = xv.flatten()
    iy_flat = yv.flatten()

    # Calculate coordinates for all candidates at once
    cand_min_x = settings.X_MIN + ix_flat * grid_width
    cand_min_y = settings.Y_MIN + iy_flat * grid_height
    cand_centroid_x = cand_min_x + grid_width / 2.0
    cand_centroid_y = cand_min_y + grid_height / 2.0

    # Calculate Deltas
    dx = cand_centroid_x - center_centroid_x
    dy = cand_centroid_y - center_centroid_y
    
    # Calculate Distances (Euclidean)
    dist_meters = np.sqrt(dx**2 + dy**2)
    
    # Calculate Levels (Chebyshev for Queen, Manhattan for Rook)
    diff_x = np.abs(ix_flat - center_ix)
    diff_y = np.abs(iy_flat - center_iy)
    chebyshev = np.maximum(diff_x, diff_y)
    manhattan = diff_x + diff_y

    # 5. Filtering (Vector Masking)
    if method == "Queen":
        mask = chebyshev <= threshold
    elif method == "Rook":
        mask = manhattan <= threshold
    elif method == "Radius":
        if predicate == "Centroid":
            mask = dist_meters <= threshold
        else:
            # For geometric predicates (Intersects, Within), we must filter crudely first
            # to avoid creating shapely objects for thousands of points.
            # We use the bounding box mask first (implicit in grid gen), 
            # then checking if distance < radius + diagonal/2 for "Intersects" approximation?
            # For strict correctness with Shapely, we iterate only over the masked potential candidates.
            # Here we accept all within the bounding box for the loop check below.
            mask = np.ones_like(dist_meters, dtype=bool)

    # Apply mask to reduce dataset
    valid_indices = np.where(mask)[0]
    
    neighbors = []
    
    # 6. Result Construction
    # We iterate only over valid candidates. 
    # Note: For complex predicates (Intersects/Within), we still need the loop check.
    
    for i in valid_indices:
        ix = int(ix_flat[i])
        iy = int(iy_flat[i])
        
        d_meter = float(dist_meters[i])
        lvl = int(chebyshev[i]) # Using Chebyshev as general level indicator
        
        # Double check for Radius geometric predicates
        if method == "Radius" and predicate in ["Intersects", "Within"]:
            c_min_x = float(cand_min_x[i])
            c_min_y = float(cand_min_y[i])
            cell_poly = box(c_min_x, c_min_y, c_min_x + grid_width, c_min_y + grid_height)
            
            if predicate == "Intersects" and not cell_poly.intersects(search_area):
                continue
            if predicate == "Within" and not search_area.contains(cell_poly):
                continue

        # Calculate Azimuth
        dx_val = float(dx[i])
        dy_val = float(dy[i])
        azimute = (math.degrees(math.atan2(dx_val, dy_val)) + 360) % 360

        # Encode (This part is still scalar due to the recursive nature of Gilbert, 
        # but efficient enough for the filtered set)
        c_code, _, _ = math_encode(float(cand_centroid_x[i]), float(cand_centroid_y[i]), precision)

        neighbors.append({
            "codloc": c_code,
            "neighborLevel": lvl,
            "neighborDistance": d_meter,
            "azimute": azimute,
            "projected_geometry": [
                (float(cand_min_x[i]), float(cand_min_y[i])),
                (float(cand_min_x[i]) + grid_width, float(cand_min_y[i])),
                (float(cand_min_x[i]) + grid_width, float(cand_min_y[i]) + grid_height),
                (float(cand_min_x[i]), float(cand_min_y[i]) + grid_height),
                (float(cand_min_x[i]), float(cand_min_y[i]))
            ]
        })

    return neighbors, search_boundary