"""Remote sensing feature engineering: spectral indices and tasseled cap from Sentinel-2 bands."""

from __future__ import annotations

import math
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_satvi(swir1: float, red: float, swir2: float) -> Optional[float]:
    """Compute Soil Adjusted Total Vegetation Index (Marsett et al. 2006).

    SATVI = 1.5 * (SWIR1 - Red) / (SWIR1 + Red + 0.5) - SWIR2 / 2

    Positively associated with green and dry vegetation.
    """
    denominator = swir1 + red + 0.5
    if denominator == 0:
        return None
    return round(1.5 * (swir1 - red) / denominator - swir2 / 2, 4)


def compute_bsi(red: float, swir1: float, nir: float, blue: float) -> Optional[float]:
    """Compute Bare Soil Index.

    BSI = (Red + SWIR1) - (NIR + Blue) / (Red + SWIR1) + (NIR + Blue)

    Negatively associated with vegetation cover.
    """
    numerator = (red + swir1) - (nir + blue)
    denominator = (red + swir1) + (nir + blue)
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def compute_nbr2(nir: float, swir2: float) -> Optional[float]:
    """Compute Normalized Burn Ratio 2 (Dvorakova et al. 2021).

    NBR2 = (NIR - SWIR2) / (NIR + SWIR2)

    Larger values typically associated with moist soils or crop residues.
    """
    denominator = nir + swir2
    if denominator == 0:
        return None
    return round((nir - swir2) / denominator, 4)


def compute_ndti(swir1: float, swir2: float) -> Optional[float]:
    """Compute Normalized Difference Tillage Index.

    NDTI = (SWIR1 - SWIR2) / (SWIR1 + SWIR2)

    Larger values more likely associated with conventional tillage.
    """
    denominator = swir1 + swir2
    if denominator == 0:
        return None
    return round((swir1 - swir2) / denominator, 4)


def compute_lswi(nir: float, swir1: float) -> Optional[float]:
    """Compute Land Surface Water Index.

    LSWI = (NIR - SWIR1) / (NIR + SWIR1)

    Positively correlated with total liquid water content in vegetation and soil.
    """
    denominator = nir + swir1
    if denominator == 0:
        return None
    return round((nir - swir1) / denominator, 4)


def compute_brightness_index(red: float, green: float) -> Optional[float]:
    """Compute Brightness Index.

    BI = sqrt((Red^2 + Green^2) / 2)

    Under bare soil conditions, brighter soils have less organic matter.
    """
    return round(math.sqrt((red**2 + green**2) / 2), 4)


def compute_tasseled_cap(
    blue: float, green: float, red: float, nir: float, swir1: float, swir2: float
) -> dict[str, Optional[float]]:
    """Compute Tasseled Cap transformation for Sentinel-2 (Shi & Xu 2019).

    Returns brightness, greenness, and wetness components.
    """
    brightness = (
        0.3510 * blue + 0.3813 * green + 0.3437 * red
        + 0.7196 * nir + 0.2396 * swir1 + 0.1949 * swir2
    )
    greenness = (
        -0.3599 * blue - 0.3813 * green - 0.3437 * red
        + 0.7196 * nir + 0.2396 * swir1 + 0.2856 * swir2
    )
    wetness = (
        0.2578 * blue + 0.2305 * green + 0.0883 * red
        + 0.1071 * nir - 0.7611 * swir1 - 0.5308 * swir2
    )
    return {
        "tc_brightness": round(brightness, 4),
        "tc_greenness": round(greenness, 4),
        "tc_wetness": round(wetness, 4),
    }


def compute_all_indices(bands: dict[str, float]) -> dict[str, Optional[float]]:
    """Compute all spectral indices from Sentinel-2 band values.

    Args:
        bands: dict with keys 'blue', 'green', 'red', 'nir', 'swir1', 'swir2'

    Returns:
        dict with all computed indices
    """
    blue = bands.get("blue", 0)
    green = bands.get("green", 0)
    red = bands.get("red", 0)
    nir = bands.get("nir", 0)
    swir1 = bands.get("swir1", 0)
    swir2 = bands.get("swir2", 0)

    ndvi = None
    if (nir + red) != 0:
        ndvi = round((nir - red) / (nir + red), 4)

    savi = None
    if (nir + red + 0.5) != 0:
        savi = round(1.5 * (nir - red) / (nir + red + 0.5), 4)

    tc = compute_tasseled_cap(blue, green, red, nir, swir1, swir2)

    return {
        "ndvi": ndvi,
        "savi": savi,
        "satvi": compute_satvi(swir1, red, swir2),
        "bsi": compute_bsi(red, swir1, nir, blue),
        "nbr2": compute_nbr2(nir, swir2),
        "ndti": compute_ndti(swir1, swir2),
        "lswi": compute_lswi(nir, swir1),
        "brightness_index": compute_brightness_index(red, green),
        **tc,
    }


def derive_indices_from_row(row: dict) -> dict[str, Any]:
    """Derive spectral indices from existing remote_sensing_observation columns.

    Uses stored band values or pre-computed indices where available.
    Returns dict of index values to update.
    """
    bands = {}
    for band in ["blue", "green", "red", "nir", "swir1", "swir2"]:
        key = f"band_{band}"
        if key in row and row[key] is not None:
            bands[band] = float(row[key])

    if len(bands) < 3:
        return {}

    return compute_all_indices(bands)
