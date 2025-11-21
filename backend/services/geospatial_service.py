"""Business logic for encoding and decoding Gilbert-based geospatial hashes."""

from typing import Dict, List, Tuple

from app.core.constants import (
    CHAR_TO_IDX,
    GILBERT_TABLE_BOTTOM_UP,
    GRID_BASE,
    IDX_TO_CHAR,
    MAX_DEPTH,
    X_MAX,
    X_MIN,
    Y_MAX,
    Y_MIN,
)

AOI_WIDTH: float = X_MAX - X_MIN
AOI_HEIGHT: float = Y_MAX - Y_MIN
IDX_TO_POS: Dict[int, Tuple[int, int]] = {}
for iy, row in enumerate(GILBERT_TABLE_BOTTOM_UP):
    for ix, index in enumerate(row):
        IDX_TO_POS[index] = (ix, iy)


def clamp(value: float, lower: float, upper: float) -> float:
    """Constrains a numeric value to the inclusive interval [lower, upper]."""
    return max(lower, min(value, upper))


def tile_size_at_depth(depth: int) -> Tuple[float, float]:
    """Computes the tile width and height for a given depth level."""
    scale = GRID_BASE ** depth
    return AOI_WIDTH / scale, AOI_HEIGHT / scale


def pos_to_index(ix: int, iy: int) -> int:
    """Maps a grid coordinate to its Gilbert-order index."""
    return GILBERT_TABLE_BOTTOM_UP[iy][ix]


def index_to_pos(idx: int) -> Tuple[int, int]:
    """Maps a Gilbert-order index to its grid coordinate."""
    return IDX_TO_POS[idx]


def encode_xy(x: float, y: float, depth: int) -> Tuple[str, float, float]:
    """Encodes projected coordinates into a Gilbert-based geohash string."""
    if depth < 1:
        depth = 1
    if depth > MAX_DEPTH:
        raise ValueError(f"depth must be between 1 and {MAX_DEPTH}")
    x = clamp(x, X_MIN, X_MAX - 1e-9)
    y = clamp(y, Y_MIN, Y_MAX - 1e-9)
    origin_x = X_MIN
    origin_y = Y_MIN
    width = AOI_WIDTH
    height = AOI_HEIGHT
    chars: List[str] = []
    for _ in range(depth):
        cell_width = width / GRID_BASE
        cell_height = height / GRID_BASE
        ix = int((x - origin_x) // cell_width)
        ix = min(ix, GRID_BASE - 1)
        iy = int((y - origin_y) // cell_height)
        iy = min(iy, GRID_BASE - 1)
        idx = pos_to_index(ix, iy)
        chars.append(IDX_TO_CHAR[idx])
        origin_x += ix * cell_width
        origin_y += iy * cell_height
        width = cell_width
        height = cell_height
    return "".join(chars), origin_x, origin_y


def decode_to_xy(hash_str: str) -> Tuple[float, float, float, float]:
    """Decodes a Gilbert-based geohash into tile origin and size."""
    if not hash_str:
        raise ValueError("hash cannot be empty")
    normalized = hash_str.strip().upper()
    for char in normalized:
        if char not in CHAR_TO_IDX:
            raise ValueError(f"invalid character in hash: {char}")
    origin_x = X_MIN
    origin_y = Y_MIN
    width = AOI_WIDTH
    height = AOI_HEIGHT
    for char in normalized:
        idx = CHAR_TO_IDX[char]
        ix, iy = index_to_pos(idx)
        cell_width = width / GRID_BASE
        cell_height = height / GRID_BASE
        origin_x += ix * cell_width
        origin_y += iy * cell_height
        width = cell_width
        height = cell_height
    return origin_x, origin_y, width, height
