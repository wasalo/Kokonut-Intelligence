"""Raster metadata: read GeoTIFF headers and store metadata."""

from __future__ import annotations

import os

from services.common.errors import safe_exception_class
from services.common.logging import get_logger

logger = get_logger("ingestion.raster_metadata")

_RASTER_FORMATS = {
    ".geotiff": "geotiff",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".jp2": "jp2",
    ".png": "png",
}


def _schema_file_format(filepath: str) -> str:
    return _RASTER_FORMATS.get(os.path.splitext(filepath)[1].lower(), "other")


def import_raster_metadata(filepath: str, location_id: str = None,
                           source_system: str = None) -> dict:
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    try:
        import rasterio
    except ImportError:
        return {"status": "error", "message": "rasterio not installed. Run: pip install rasterio"}

    try:
        with rasterio.open(filepath) as src:
            bounds = src.bounds
            transform = src.transform

            pixel_width = abs(transform.a)
            pixel_height = abs(transform.e)

            data = {
                "file_url": filepath,
                "file_name": os.path.basename(filepath),
                "file_format": _schema_file_format(filepath),
                "crs": str(src.crs) if src.crs else None,
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
                "bbox_west": bounds.left,
                "bbox_south": bounds.bottom,
                "bbox_east": bounds.right,
                "bbox_north": bounds.top,
                "num_bands": src.count,
                "band_names": [src.descriptions[i] or f"band_{i+1}" for i in range(src.count)],
                "file_size_bytes": os.path.getsize(filepath),
                "data_type": str(src.dtypes[0]) if src.dtypes else None,
                "nodata_value": float(src.nodata) if src.nodata is not None else None,
                "location_id": location_id,
                "source_system": source_system,
            }
            return {"status": "success", "metadata": data}
    except Exception as exc:
        logger.error("Failed to import raster metadata (%s)", safe_exception_class(exc))
        return {"status": "error", "message": "Failed to read raster metadata"}


def get_raster_info(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    try:
        import rasterio
    except ImportError:
        return {"status": "error", "message": "rasterio not installed"}

    try:
        with rasterio.open(filepath) as src:
            bounds = src.bounds
            return {
                "crs": str(src.crs) if src.crs else None,
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "bounds": {
                    "west": bounds.left, "south": bounds.bottom,
                    "east": bounds.right, "north": bounds.top,
                },
                "pixel_size": {"x": abs(src.transform.a), "y": abs(src.transform.e)},
                "data_type": str(src.dtypes[0]) if src.dtypes else None,
                "file_size": os.path.getsize(filepath),
            }
    except Exception as exc:
        logger.error("Failed to read raster info (%s)", safe_exception_class(exc))
        return {"status": "error", "message": "Failed to read raster info"}
