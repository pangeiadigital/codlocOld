"""Core constants for the geospatial hashing domain."""

from typing import Dict, Tuple

GRID_BASE: int = 6
MAX_DEPTH: int = 9
X_MIN: float = 607_919.0
Y_MIN: float = 4_528_175.0
X_MAX: float = 10_685_615.0
Y_MAX: float = 14_605_871.0
BASE36_CHARS: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

IDX_TO_CHAR: Dict[int, str] = {index: BASE36_CHARS[index] for index in range(36)}
CHAR_TO_IDX: Dict[str, int] = {char: index for index, char in IDX_TO_CHAR.items()}
GILBERT_TABLE_BOTTOM_UP: Tuple[Tuple[int, ...], ...] = (
    (30, 29, 28, 27, 26, 25),
    (31, 12, 11, 10, 9, 24),
    (32, 13, 2, 1, 8, 23),
    (33, 14, 3, 0, 7, 22),
    (34, 15, 4, 5, 6, 21),
    (35, 16, 17, 18, 19, 20),
)
"""
GILBERT_TABLE_BOTTOM_UP stores the orientation of the Gilbert curve for a six-by-six
matrix, ensuring consistent traversal order across depth levels.
"""
