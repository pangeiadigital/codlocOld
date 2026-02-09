"""Coordinate reference system utilities."""

from pathlib import Path
from typing import Dict, Tuple

from pyproj import CRS, Transformer

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
WKT_FILENAME = "target_crs.wkt"


def load_target_crs() -> CRS:
    """Loads the target CRS definition from the packaged WKT resource."""
    wkt_path = RESOURCES_DIR / WKT_FILENAME
    with wkt_path.open("r", encoding="utf-8") as wkt_file:
        wkt_content = wkt_file.read()
    return CRS.from_wkt(wkt_content)


def build_transformers() -> Dict[str, Tuple[Transformer, Transformer]]:
    """
    Builds forward and inverse transformers for supported CRS.
    Returns a dictionary keyed by CRS name ('WGS 84', 'SIRGAS 2000') 
    containing (forward, inverse) tuples.
    """
    target_crs = load_target_crs()
    
    # Define supported source CRSs
    # EPSG:4326 = WGS 84
    # EPSG:4674 = SIRGAS 2000
    sources = {
        "WGS 84": CRS.from_epsg(4326),
        "SIRGAS 2000": CRS.from_epsg(4674)
    }

    transformers = {}

    for name, source_crs in sources.items():
        forward = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        inverse = Transformer.from_crs(target_crs, source_crs, always_xy=True)
        transformers[name] = (forward, inverse)
    
    return transformers