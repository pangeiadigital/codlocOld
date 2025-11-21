"""Coordinate reference system utilities."""

from functools import lru_cache
from pathlib import Path
from typing import Tuple

from pyproj import CRS, Transformer

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
WKT_FILENAME = "target_crs.wkt"


@lru_cache(maxsize=1)
def load_target_crs() -> CRS:
    """Loads the target CRS definition from the packaged WKT resource."""
    wkt_path = RESOURCES_DIR / WKT_FILENAME
    with wkt_path.open("r", encoding="utf-8") as wkt_file:
        wkt_content = wkt_file.read()
    return CRS.from_wkt(wkt_content)


@lru_cache(maxsize=1)
def build_transformers() -> Tuple[Transformer, Transformer]:
    """Builds forward and inverse transformers between WGS84 and the target CRS."""
    target_crs = load_target_crs()
    wgs84 = CRS.from_epsg(4326)
    forward = Transformer.from_crs(wgs84, target_crs, always_xy=True)
    inverse = Transformer.from_crs(target_crs, wgs84, always_xy=True)
    return forward, inverse
