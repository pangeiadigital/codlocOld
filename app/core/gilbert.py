"""Mathematical core for Gilbert Space-Filling Curve operations."""

from typing import Dict, List, Tuple

from app.core.config import settings
from app.core.constants import (
    CHAR_TO_IDX,
    GILBERT_TABLE_BOTTOM_UP,
    IDX_TO_CHAR,
)

# pre-compute index to position map for faster lookups
IDX_TO_POS: Dict[int, Tuple[int, int]] = {}
for iy, row in enumerate(GILBERT_TABLE_BOTTOM_UP):
    for ix, index in enumerate(row):
        IDX_TO_POS[index] = (ix, iy)


def pos_to_index(ix: int, iy: int) -> int:
    """Maps a grid coordinate (ix, iy) to its Gilbert-order index."""
    return GILBERT_TABLE_BOTTOM_UP[iy][ix]


def index_to_pos(idx: int) -> Tuple[int, int]:
    """Maps a Gilbert-order index to its grid coordinate (ix, iy)."""
    return IDX_TO_POS[idx]


def get_aoi_dimensions() -> Tuple[float, float]:
    """Returns the width and height of the Area of Interest."""
    return settings.X_MAX - settings.X_MIN, settings.Y_MAX - settings.Y_MIN


def clamp(value: float, lower: float, upper: float) -> float:
    """Constrains a numeric value to the inclusive interval."""
    return max(lower, min(value, upper))


def math_encode(x: float, y: float, depth: int) -> Tuple[str, float, float]:
    """
    Pure math implementation of Gilbert encoding.
    Returns: (codloc_string, origin_x, origin_y)
    """
    if depth < 1:
        depth = 1
    if depth > settings.MAX_PRECISION:
        raise ValueError(f"depth must be between 1 and {settings.MAX_PRECISION}")

    x = clamp(x, settings.X_MIN, settings.X_MAX - 1e-9)
    y = clamp(y, settings.Y_MIN, settings.Y_MAX - 1e-9)

    origin_x = settings.X_MIN
    origin_y = settings.Y_MIN
    
    aoi_w, aoi_h = get_aoi_dimensions()
    width = aoi_w
    height = aoi_h
    
    chars: List[str] = []

    for _ in range(depth):
        cell_width = width / settings.GRID_BASE
        cell_height = height / settings.GRID_BASE

        ix = int((x - origin_x) // cell_width)
        ix = min(ix, settings.GRID_BASE - 1)

        iy = int((y - origin_y) // cell_height)
        iy = min(iy, settings.GRID_BASE - 1)

        idx = pos_to_index(ix, iy)
        chars.append(IDX_TO_CHAR[idx])

        origin_x += ix * cell_width
        origin_y += iy * cell_height
        width = cell_width
        height = cell_height

    return "".join(chars), origin_x, origin_y


def math_decode(hash_str: str) -> Tuple[float, float, float, float]:
    """
    Pure math implementation of Gilbert decoding.
    Returns: (origin_x, origin_y, width, height)
    """
    if not hash_str:
        raise ValueError("hash cannot be empty")
    
    normalized = hash_str.strip().upper()
    
    origin_x = settings.X_MIN
    origin_y = settings.Y_MIN
    
    aoi_w, aoi_h = get_aoi_dimensions()
    width = aoi_w
    height = aoi_h

    for char in normalized:
        if char not in CHAR_TO_IDX:
            raise ValueError(f"invalid character in codloc: {char}")
        
        idx = CHAR_TO_IDX[char]
        ix, iy = index_to_pos(idx)

        cell_width = width / settings.GRID_BASE
        cell_height = height / settings.GRID_BASE

        origin_x += ix * cell_width
        origin_y += iy * cell_height
        
        width = cell_width
        height = cell_height

    return origin_x, origin_y, width, height