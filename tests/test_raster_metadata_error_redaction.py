"""Raster inspection failures must not log private file paths or diagnostics."""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.ingestion.raster_metadata import get_raster_info, import_raster_metadata


@pytest.mark.parametrize(
    ("reader", "message"),
    [
        (import_raster_metadata, "Failed to read raster metadata"),
        (get_raster_info, "Failed to read raster info"),
    ],
)
def test_raster_open_failure_logs_only_exception_class(reader, message, tmp_path, monkeypatch, caplog):
    private_path = tmp_path / "private-customer-source.tif"
    private_path.write_bytes(b"not a real raster")
    rasterio = SimpleNamespace(open=Mock(side_effect=RuntimeError("private path plus credential=secret")))
    monkeypatch.setitem(sys.modules, "rasterio", rasterio)

    with caplog.at_level(logging.ERROR, logger="kokonut.ingestion.raster_metadata"):
        if reader is import_raster_metadata:
            result = reader(str(private_path), location_id="private-location")
        else:
            result = reader(str(private_path))

    assert result == {"status": "error", "message": message}
    assert str(private_path) not in caplog.text
    assert "credential=secret" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert "Traceback" not in caplog.text


def test_tif_metadata_matches_schema_format_and_does_not_infer_missing_crs(
    tmp_path, monkeypatch
):
    source = tmp_path / "sample.TIF"
    source.write_bytes(b"raster-fixture")

    class FakeRaster:
        bounds = SimpleNamespace(left=1, bottom=2, right=3, top=4)
        transform = SimpleNamespace(a=0.25, e=-0.25)
        crs = None
        count = 1
        descriptions = (None,)
        dtypes = ("uint16",)
        nodata = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setitem(sys.modules, "rasterio", SimpleNamespace(open=Mock(return_value=FakeRaster())))

    result = import_raster_metadata(str(source), location_id="location-1")

    assert result["status"] == "success"
    assert result["metadata"]["file_format"] == "tiff"
    assert result["metadata"]["crs"] is None
