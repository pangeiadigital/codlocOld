"""Immutable mathematical constants for the Gilbert Curve."""

from typing import Dict, Tuple

# base36 character map
BASE36_CHARS: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

IDX_TO_CHAR: Dict[int, str] = {index: BASE36_CHARS[index] for index in range(36)}
CHAR_TO_IDX: Dict[str, int] = {char: index for index, char in IDX_TO_CHAR.items()}

# Gilbert curve orientation table (6x6)
GILBERT_TABLE_BOTTOM_UP: Tuple[Tuple[int, ...], ...] = (
    (30, 29, 28, 27, 26, 25),
    (31, 12, 11, 10, 9, 24),
    (32, 13, 2, 1, 8, 23),
    (33, 14, 3, 0, 7, 22),
    (34, 15, 4, 5, 6, 21),
    (35, 16, 17, 18, 19, 20),
)