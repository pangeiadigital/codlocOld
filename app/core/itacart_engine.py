"""ITACaRT DGGS Engine — Top-Down encode / decode implementation.

Implements the ITACaRT (ITA Cadastral Ellipsoidal Reference Tessellation)
hierarchical encoding scheme: sinusoidal projection on WGS 84, quadrant
partitioning, base cells at 10 km, and alternating 2×2 / 5×5 subdivision
down to 1 m² (depth 9).

Three hash representations are produced:
  • **Canonical** — human-readable, with parentheses:
        ``SW(0513/0174(3(C2(1(B4(4(D5(2(A1)))))))))``
  • **Compact**  — 10-char base36 string for URLs / sharing:
        ``A7G3K0X2P1``
  • **Storage**  — 64-bit integer packed representation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from pyproj import CRS, Transformer

from app.core.itacart_constants import (
    BASE36_CHAR_TO_IDX,
    BASE36_CHARS,
    BASE_CELL_SIZE,
    COMPACT_LENGTHS,
    LEVEL_CELL_AREA,
    LEVEL_CELL_SIDE,
    MATRIX_2X2_CELLS,
    MATRIX_2X2_IDX_TO_POS,
    MATRIX_2X2_POS_TO_IDX,
    MATRIX_2X2_SIZE,
    MATRIX_5X5_CELLS,
    MATRIX_5X5_LABEL_TO_LINEAR,
    MATRIX_5X5_LABEL_TO_POS,
    MATRIX_5X5_LINEAR_TO_LABEL,
    MATRIX_5X5_POS_TO_LABEL,
    MATRIX_5X5_SIZE,
    MAX_BASE_IX,
    MAX_BASE_IY,
    QUADRANT_NAMES,
    QUADRANT_SIGNS,
    QUADRANTS,
)

# ── Projection Setup ────────────────────────────────────────────────────────
# Sinusoidal equal-area projection centred at the Prime Meridian.
_SINU_CRS = CRS.from_proj4(
    "+proj=sinu +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)
_WGS84_CRS = CRS.from_epsg(4326)

# Transformers (always_xy=True → input order is longitude, latitude)
_FWD = Transformer.from_crs(_WGS84_CRS, _SINU_CRS, always_xy=True)
_INV = Transformer.from_crs(_SINU_CRS, _WGS84_CRS, always_xy=True)


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def encode(
    lat: float,
    lon: float,
    depth: int,
) -> Dict:
    """Encode a geographic coordinate into an ITACaRT hash.

    Parameters
    ----------
    lat : float
        Latitude in degrees (WGS 84 / SIRGAS 2000).
    lon : float
        Longitude in degrees.
    depth : int
        Hierarchical depth (1–9).  Depth 9 ≈ 1 m².

    Returns
    -------
    dict
        ``canonical``, ``compact``, ``storage``, ``depth``,
        ``cell_side``, ``cell_area``, ``origin_x``, ``origin_y``.
    """
    _validate_depth(depth)

    # 1. Project to sinusoidal
    sx, sy = _latlon_to_sinu(lon, lat)

    # 2. Quadrant
    quadrant = _determine_quadrant(sx, sy)

    # 3. Quadrant-relative positive coordinates
    qx, qy = abs(sx), abs(sy)

    # 4. Base cell (Level 1)
    base_ix = int(qx // BASE_CELL_SIZE)
    base_iy = int(qy // BASE_CELL_SIZE)
    base_ix = min(base_ix, MAX_BASE_IX - 1)
    base_iy = min(base_iy, MAX_BASE_IY - 1)

    # 5. Remainder within the base cell
    rem_x = qx - base_ix * BASE_CELL_SIZE
    rem_y = qy - base_iy * BASE_CELL_SIZE
    cell_w = BASE_CELL_SIZE
    cell_h = BASE_CELL_SIZE

    # Track cell origin in sinusoidal metres (quadrant-relative)
    origin_x = base_ix * BASE_CELL_SIZE
    origin_y = base_iy * BASE_CELL_SIZE

    # 6. Build canonical parts and collect subdivision indices
    canonical_parts: List[str] = [f"{quadrant}({base_ix:04d}/{base_iy:04d}"]
    subdivisions: Dict[int, int] = {}  # level → linear index (0-based)

    for level in range(2, depth + 1):
        if level % 2 == 0:
            # Even level → 2×2
            sub_ix = min(int(rem_x // (cell_w / MATRIX_2X2_SIZE)), MATRIX_2X2_SIZE - 1)
            sub_iy = min(int(rem_y // (cell_h / MATRIX_2X2_SIZE)), MATRIX_2X2_SIZE - 1)

            idx_1based = MATRIX_2X2_POS_TO_IDX[(sub_ix, sub_iy)]
            subdivisions[level] = idx_1based - 1  # store 0-based for packing

            new_w = cell_w / MATRIX_2X2_SIZE
            new_h = cell_h / MATRIX_2X2_SIZE
            origin_x += sub_ix * new_w
            origin_y += sub_iy * new_h
            rem_x -= sub_ix * new_w
            rem_y -= sub_iy * new_h
            cell_w, cell_h = new_w, new_h

            canonical_parts.append(f"({idx_1based}")
        else:
            # Odd level → 5×5
            sub_ix = min(int(rem_x // (cell_w / MATRIX_5X5_SIZE)), MATRIX_5X5_SIZE - 1)
            sub_iy = min(int(rem_y // (cell_h / MATRIX_5X5_SIZE)), MATRIX_5X5_SIZE - 1)

            label = MATRIX_5X5_POS_TO_LABEL[(sub_ix, sub_iy)]
            subdivisions[level] = MATRIX_5X5_LABEL_TO_LINEAR[label]

            new_w = cell_w / MATRIX_5X5_SIZE
            new_h = cell_h / MATRIX_5X5_SIZE
            origin_x += sub_ix * new_w
            origin_y += sub_iy * new_h
            rem_x -= sub_ix * new_w
            rem_y -= sub_iy * new_h
            cell_w, cell_h = new_w, new_h

            canonical_parts.append(f"({label}")

    # Close parentheses: one for base cell + one per subdivision level
    close_count = 1 + max(0, depth - 1)
    canonical = "".join(canonical_parts) + ")" * close_count

    # 7. Compact and storage encodings
    packed = _pack_index(QUADRANTS[quadrant], base_ix, base_iy, subdivisions, depth)
    compact = _encode_base36(packed, COMPACT_LENGTHS[depth])
    storage = packed  # 64-bit integer

    return {
        "canonical": canonical,
        "compact": compact,
        "storage": storage,
        "depth": depth,
        "quadrant": quadrant,
        "base_ix": base_ix,
        "base_iy": base_iy,
        "cell_side": LEVEL_CELL_SIDE.get(depth),
        "cell_area": LEVEL_CELL_AREA.get(depth),
    }


def decode_canonical(hash_str: str) -> Dict:
    """Decode a canonical ITACaRT hash to geographic coordinates.

    Parameters
    ----------
    hash_str : str
        Canonical hash, e.g. ``SW(0513/0174(3(C2)))``.

    Returns
    -------
    dict
        ``lat``, ``lon``, ``canonical``, ``compact``, ``depth``,
        ``cell_side``, ``cell_area``, ``bbox`` (lon/lat ring).
    """
    parsed = _parse_canonical(hash_str)
    return _decoded_result(parsed)


def decode_compact(compact_str: str, depth: int) -> Dict:
    """Decode a compact (base36) ITACaRT hash.

    Parameters
    ----------
    compact_str : str
        10-char (max) base36 string.
    depth : int
        The depth/precision of this hash (1–9).

    Returns
    -------
    dict
        Same structure as ``decode_canonical``.
    """
    _validate_depth(depth)
    packed = _decode_base36(compact_str.strip().upper())
    parsed = _unpack_index(packed, depth)
    return _decoded_result(parsed)


def canonical_to_compact(hash_str: str) -> str:
    """Convert a canonical hash to its compact base36 representation."""
    parsed = _parse_canonical(hash_str)
    packed = _pack_index(
        QUADRANTS[parsed["quadrant"]],
        parsed["base_ix"],
        parsed["base_iy"],
        parsed["subdivisions"],
        parsed["depth"],
    )
    return _encode_base36(packed, COMPACT_LENGTHS[parsed["depth"]])


def compact_to_canonical(compact_str: str, depth: int) -> str:
    """Convert a compact base36 hash to its canonical representation."""
    result = decode_compact(compact_str, depth)
    return result["canonical"]


def cell_geometry_latlon(parsed: Dict) -> List[List[float]]:
    """Return the cell boundary as a closed [lon, lat] ring in WGS 84."""
    quadrant = parsed["quadrant"]
    sign_x, sign_y = QUADRANT_SIGNS[quadrant]

    origin_x, origin_y, cell_w, cell_h = _compute_cell_bounds(parsed)

    # Cell corners in sinusoidal metres (absolute, quadrant-relative)
    corners_qrel = [
        (origin_x, origin_y),
        (origin_x + cell_w, origin_y),
        (origin_x + cell_w, origin_y + cell_h),
        (origin_x, origin_y + cell_h),
        (origin_x, origin_y),  # close ring
    ]

    # Apply quadrant sign to get global sinusoidal coordinates
    ring = []
    for qx, qy in corners_qrel:
        sx = sign_x * qx
        sy = sign_y * qy
        lon, lat = _sinu_to_latlon(sx, sy)
        ring.append([lon, lat])

    return ring


# ═══════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _validate_depth(depth: int) -> None:
    if depth < 1 or depth > 9:
        raise ValueError(f"depth must be between 1 and 9, got {depth}")


def _latlon_to_sinu(lon: float, lat: float) -> Tuple[float, float]:
    """Geographic (lon, lat) → sinusoidal (x, y) in metres."""
    return _FWD.transform(lon, lat)


def _sinu_to_latlon(sx: float, sy: float) -> Tuple[float, float]:
    """Sinusoidal (x, y) → geographic (lon, lat)."""
    return _INV.transform(sx, sy)


def _determine_quadrant(sx: float, sy: float) -> str:
    """Map sinusoidal coordinates to a quadrant name."""
    if sx >= 0 and sy >= 0:
        return "NE"
    if sx < 0 and sy >= 0:
        return "NW"
    if sx >= 0 and sy < 0:
        return "SE"
    return "SW"


# ── Canonical parsing ────────────────────────────────────────────────────

def _parse_canonical(hash_str: str) -> Dict:
    """Parse a canonical ITACaRT hash into its components."""
    s = hash_str.strip().upper()

    # Quadrant
    quadrant = s[:2]
    if quadrant not in QUADRANTS:
        raise ValueError(f"Invalid quadrant: '{quadrant}'")

    rest = s[2:]

    # Depth 0 — quadrant only (not exposed via API, but handled)
    if not rest or rest == "":
        return {"quadrant": quadrant, "depth": 0, "base_ix": 0, "base_iy": 0, "subdivisions": {}}

    if not rest.startswith("("):
        raise ValueError(f"Expected '(' after quadrant, got: '{rest[:10]}'")

    # Strip all closing parens from the end
    inner = rest.lstrip("(").rstrip(")")

    # Base cell: XXXX/YYYY
    slash_pos = inner.index("/")
    base_ix = int(inner[:slash_pos])

    remaining = inner[slash_pos + 1:]

    # Parse base_iy (digits until '(' or end)
    iy_end = 0
    while iy_end < len(remaining) and remaining[iy_end].isdigit():
        iy_end += 1
    base_iy = int(remaining[:iy_end])
    remaining = remaining[iy_end:]

    result = {
        "quadrant": quadrant,
        "base_ix": base_ix,
        "base_iy": base_iy,
        "depth": 1,
        "subdivisions": {},
    }

    # Parse subdivision levels
    level = 2
    while remaining:
        if remaining[0] == "(":
            remaining = remaining[1:]
        elif remaining[0] == ")":
            remaining = remaining[1:]
            continue
        else:
            break

        if not remaining:
            break

        if level % 2 == 0:
            # 2×2: single digit 1-4
            char = remaining[0]
            remaining = remaining[1:]
            idx_1based = int(char)
            if idx_1based < 1 or idx_1based > 4:
                raise ValueError(f"Invalid 2×2 index at level {level}: {char}")
            result["subdivisions"][level] = idx_1based - 1  # 0-based
        else:
            # 5×5: two chars like "C2"
            label = remaining[:2]
            remaining = remaining[2:]
            if label not in MATRIX_5X5_LABEL_TO_LINEAR:
                raise ValueError(f"Invalid 5×5 label at level {level}: {label}")
            result["subdivisions"][level] = MATRIX_5X5_LABEL_TO_LINEAR[label]

        result["depth"] = level
        level += 1

    return result


# ── Cell geometry ────────────────────────────────────────────────────────

def _compute_cell_bounds(parsed: Dict) -> Tuple[float, float, float, float]:
    """Compute (origin_x, origin_y, width, height) in quadrant-relative sinusoidal metres."""
    origin_x = parsed["base_ix"] * BASE_CELL_SIZE
    origin_y = parsed["base_iy"] * BASE_CELL_SIZE
    cell_w = BASE_CELL_SIZE
    cell_h = BASE_CELL_SIZE

    for level in range(2, parsed["depth"] + 1):
        sub_linear = parsed["subdivisions"].get(level)
        if sub_linear is None:
            break

        if level % 2 == 0:
            # 2×2
            ix, iy = MATRIX_2X2_IDX_TO_POS[sub_linear + 1]  # convert back to 1-based
            new_w = cell_w / MATRIX_2X2_SIZE
            new_h = cell_h / MATRIX_2X2_SIZE
            origin_x += ix * new_w
            origin_y += iy * new_h
            cell_w, cell_h = new_w, new_h
        else:
            # 5×5
            label = MATRIX_5X5_LINEAR_TO_LABEL[sub_linear]
            ix, iy = MATRIX_5X5_LABEL_TO_POS[label]
            new_w = cell_w / MATRIX_5X5_SIZE
            new_h = cell_h / MATRIX_5X5_SIZE
            origin_x += ix * new_w
            origin_y += iy * new_h
            cell_w, cell_h = new_w, new_h

    return origin_x, origin_y, cell_w, cell_h


def _decoded_result(parsed: Dict) -> Dict:
    """Build the full decoded result dict from parsed components."""
    depth = parsed["depth"]

    origin_x, origin_y, cell_w, cell_h = _compute_cell_bounds(parsed)

    # Centroid in quadrant-relative sinusoidal coords
    cx_qrel = origin_x + cell_w / 2.0
    cy_qrel = origin_y + cell_h / 2.0

    # Apply quadrant sign
    sign_x, sign_y = QUADRANT_SIGNS[parsed["quadrant"]]
    cx_sinu = sign_x * cx_qrel
    cy_sinu = sign_y * cy_qrel

    lon, lat = _sinu_to_latlon(cx_sinu, cy_sinu)

    # Rebuild canonical from parsed
    canonical = _rebuild_canonical(parsed)

    # Compact
    packed = _pack_index(
        QUADRANTS[parsed["quadrant"]],
        parsed["base_ix"],
        parsed["base_iy"],
        parsed["subdivisions"],
        depth,
    )
    compact = _encode_base36(packed, COMPACT_LENGTHS[depth])

    # Cell boundary in lat/lon
    bbox = cell_geometry_latlon(parsed)

    return {
        "lat": lat,
        "lon": lon,
        "canonical": canonical,
        "compact": compact,
        "storage": packed,
        "depth": depth,
        "quadrant": parsed["quadrant"],
        "cell_side": LEVEL_CELL_SIDE.get(depth),
        "cell_area": LEVEL_CELL_AREA.get(depth),
        "bbox": bbox,
    }


def _rebuild_canonical(parsed: Dict) -> str:
    """Rebuild the canonical hash string from parsed components."""
    depth = parsed["depth"]
    if depth == 0:
        return parsed["quadrant"]

    parts = [f"{parsed['quadrant']}({parsed['base_ix']:04d}/{parsed['base_iy']:04d}"]

    for level in range(2, depth + 1):
        sub = parsed["subdivisions"].get(level)
        if sub is None:
            break
        if level % 2 == 0:
            parts.append(f"({sub + 1}")  # convert 0-based back to 1-based
        else:
            label = MATRIX_5X5_LINEAR_TO_LABEL[sub]
            parts.append(f"({label}")

    close_count = 1 + max(0, depth - 1)
    return "".join(parts) + ")" * close_count


# ── Index packing / unpacking ────────────────────────────────────────────

def _pack_index(
    quadrant_idx: int,
    base_ix: int,
    base_iy: int,
    subdivisions: Dict[int, int],
    depth: int,
) -> int:
    """Pack ITACaRT components into a single integer for compact encoding."""
    index = quadrant_idx
    index = index * MAX_BASE_IX + base_ix
    index = index * MAX_BASE_IY + base_iy

    for level in range(2, depth + 1):
        sub = subdivisions.get(level, 0)
        if level % 2 == 0:
            index = index * MATRIX_2X2_CELLS + sub
        else:
            index = index * MATRIX_5X5_CELLS + sub

    return index


def _unpack_index(packed: int, depth: int) -> Dict:
    """Unpack a single integer back into ITACaRT components."""
    index = packed

    # Reverse: extract subdivisions from right to left
    subdivisions: Dict[int, int] = {}
    for level in range(depth, 1, -1):
        if level % 2 == 0:
            subdivisions[level] = index % MATRIX_2X2_CELLS
            index //= MATRIX_2X2_CELLS
        else:
            subdivisions[level] = index % MATRIX_5X5_CELLS
            index //= MATRIX_5X5_CELLS

    base_iy = index % MAX_BASE_IY
    index //= MAX_BASE_IY
    base_ix = index % MAX_BASE_IX
    index //= MAX_BASE_IX
    quadrant_idx = index

    return {
        "quadrant": QUADRANT_NAMES[quadrant_idx],
        "base_ix": base_ix,
        "base_iy": base_iy,
        "depth": depth,
        "subdivisions": subdivisions,
    }


# ── Base36 encoding / decoding ───────────────────────────────────────────

def _encode_base36(num: int, length: int) -> str:
    """Encode an integer as a fixed-length, zero-padded base36 string."""
    if num < 0:
        raise ValueError("Cannot encode negative numbers")
    chars: List[str] = []
    for _ in range(length):
        chars.append(BASE36_CHARS[num % 36])
        num //= 36
    return "".join(reversed(chars))


def _decode_base36(s: str) -> int:
    """Decode a base36 string into an integer."""
    num = 0
    for c in s.upper():
        if c not in BASE36_CHAR_TO_IDX:
            raise ValueError(f"Invalid base36 character: '{c}'")
        num = num * 36 + BASE36_CHAR_TO_IDX[c]
    return num
