"""Constants and lookup tables for the ITACaRT DGGS engine.

Defines the two subdivision matrices (2×2 and 5×5), quadrant geometry,
base36 compact encoding tables, and pre-computed resolution data for
each hierarchical level (0–9).
"""

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Quadrant definitions (Level 0)
# ---------------------------------------------------------------------------
# The globe is partitioned into four quadrants by the Equator (lat=0)
# and the Prime Meridian (lon=0).

QUADRANTS: Dict[str, int] = {"NE": 0, "NW": 1, "SE": 2, "SW": 3}
QUADRANT_NAMES: Dict[int, str] = {v: k for k, v in QUADRANTS.items()}

# Sign of sinusoidal (x, y) coordinates per quadrant.
QUADRANT_SIGNS: Dict[str, Tuple[int, int]] = {
    "NE": (1, 1),    # x >= 0, y >= 0
    "NW": (-1, 1),   # x <  0, y >= 0
    "SE": (1, -1),   # x >= 0, y <  0
    "SW": (-1, -1),  # x <  0, y <  0
}

# ---------------------------------------------------------------------------
# Base cell (Level 1) — 10 km × 10 km
# ---------------------------------------------------------------------------
BASE_CELL_SIZE: float = 10_000.0  # metres

# Maximum base-cell indices derived from the WGS 84 sinusoidal projection.
# Equatorial half-circumference ≈ 20 037 508 m  →  2004 cells (0-2003)
# Meridional half-distance      ≈ 10 001 966 m  →  1001 cells (0-1000)
MAX_BASE_IX: int = 2004
MAX_BASE_IY: int = 1001

# ---------------------------------------------------------------------------
# 2×2 subdivision matrix  (even levels: 2, 4, 6, 8)
# ---------------------------------------------------------------------------
#   +---+---+
#   | 3 | 4 |
#   +---+---+
#   | 1 | 2 |
#   +---+---+

MATRIX_2X2_SIZE: int = 2
MATRIX_2X2_CELLS: int = 4  # 2 × 2

MATRIX_2X2_POS_TO_IDX: Dict[Tuple[int, int], int] = {
    (0, 0): 1, (1, 0): 2,
    (0, 1): 3, (1, 1): 4,
}
MATRIX_2X2_IDX_TO_POS: Dict[int, Tuple[int, int]] = {
    v: k for k, v in MATRIX_2X2_POS_TO_IDX.items()
}

# ---------------------------------------------------------------------------
# 5×5 subdivision matrix  (odd levels: 3, 5, 7, 9)
# ---------------------------------------------------------------------------
#   +----+----+----+----+----+
#   | E1 | E2 | E3 | E4 | E5 |
#   +----+----+----+----+----+
#   | D1 | D2 | D3 | D4 | D5 |
#   +----+----+----+----+----+
#   | C1 | C2 | C3 | C4 | C5 |
#   +----+----+----+----+----+
#   | B1 | B2 | B3 | B4 | B5 |
#   +----+----+----+----+----+
#   | A1 | A2 | A3 | A4 | A5 |
#   +----+----+----+----+----+

MATRIX_5X5_SIZE: int = 5
MATRIX_5X5_CELLS: int = 25  # 5 × 5

ROWS_5X5 = ("A", "B", "C", "D", "E")
COLS_5X5 = ("1", "2", "3", "4", "5")

MATRIX_5X5_POS_TO_LABEL: Dict[Tuple[int, int], str] = {}
MATRIX_5X5_LABEL_TO_POS: Dict[str, Tuple[int, int]] = {}
MATRIX_5X5_LABEL_TO_LINEAR: Dict[str, int] = {}
MATRIX_5X5_LINEAR_TO_LABEL: Dict[int, str] = {}

for _iy, _row in enumerate(ROWS_5X5):
    for _ix, _col in enumerate(COLS_5X5):
        _label = f"{_row}{_col}"
        _linear = _iy * 5 + _ix
        MATRIX_5X5_POS_TO_LABEL[(_ix, _iy)] = _label
        MATRIX_5X5_LABEL_TO_POS[_label] = (_ix, _iy)
        MATRIX_5X5_LABEL_TO_LINEAR[_label] = _linear
        MATRIX_5X5_LINEAR_TO_LABEL[_linear] = _label

# ---------------------------------------------------------------------------
# Compact encoding — base36 alphabet (case-insensitive, 10 chars at depth 9)
# ---------------------------------------------------------------------------
BASE36_CHARS: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE36_CHAR_TO_IDX: Dict[str, int] = {c: i for i, c in enumerate(BASE36_CHARS)}

# ---------------------------------------------------------------------------
# Per-level metadata
# ---------------------------------------------------------------------------
# Cell side length (in metres) and area (in m²) at each depth.
LEVEL_CELL_SIDE: Dict[int, float] = {
    0: None,      # Quadrant — variable
    1: 10_000.0,  # 10 km
    2: 5_000.0,   # 5 km
    3: 1_000.0,   # 1 km
    4: 500.0,     # 500 m
    5: 100.0,     # 100 m
    6: 50.0,      # 50 m
    7: 10.0,      # 10 m
    8: 5.0,       # 5 m
    9: 1.0,       # 1 m
}

LEVEL_CELL_AREA: Dict[int, float] = {
    0: None,
    1: 100_000_000.0,  # 100 km²
    2: 25_000_000.0,   # 25 km²
    3: 1_000_000.0,    # 1 km²
    4: 250_000.0,
    5: 10_000.0,       # 1 ha
    6: 2_500.0,
    7: 100.0,
    8: 25.0,
    9: 1.0,            # 1 m²
}

# Pre-computed compact hash length (base36 chars) per depth.
# Calculated from: ceil(log36(total_cells_at_depth))
COMPACT_LENGTHS: Dict[int, int] = {
    0: 1,   # 4 cells
    1: 5,   # ~8 M cells
    2: 5,   # ~32 M cells
    3: 6,   # ~802 M cells
    4: 7,   # ~3.2 B cells
    5: 8,   # ~80 B cells
    6: 8,   # ~321 B cells
    7: 9,   # ~8 T cells
    8: 9,   # ~32 T cells
    9: 10,  # ~802 T cells
}
