"""Keep private geometry data and parser details out of legacy import errors."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

from services.ingestion import kml_import, shapefile_import


def test_kml_parse_and_placemark_failures_omit_source_payload(tmp_path):
    secret = "private-farm-coordinate-payload"
    malformed = tmp_path / "malformed.kml"
    malformed.write_text(f"<broken>{secret}<unfinished")

    parse_result = kml_import.import_kml(str(malformed))

    assert parse_result["status"] == "error"
    assert parse_result["message"].startswith("XML parse error (")
    assert secret not in repr(parse_result)

    invalid_coordinate = tmp_path / "placemark.kml"
    invalid_coordinate.write_text(
        "<kml xmlns='http://www.opengis.net/kml/2.2'><Placemark>"
        "<name>private contributor name</name><Point><coordinates>"
        f"{secret},0 1,1</coordinates></Point></Placemark></kml>"
    )
    result = kml_import.import_kml(str(invalid_coordinate))

    assert result["errors"] == ["Placemark 0: import failed (ValueError)"]
    assert secret not in repr(result)
    assert "private contributor name" not in repr(result)


def test_shapefile_feature_failure_redacts_payload_from_result_and_log(tmp_path, monkeypatch):
    secret = "private geometry database password=secret"
    path = tmp_path / "farm.shp"
    path.touch()
    logger = MagicMock()

    class _Coordinates:
        def __getitem__(self, _index):
            raise RuntimeError(secret)

    class _Source:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter([{
                "geometry": {"type": "Point", "coordinates": _Coordinates()},
                "properties": {"name": "private contributor"},
            }])

    fiona = ModuleType("fiona")
    fiona.open = MagicMock(return_value=_Source())
    monkeypatch.setitem(sys.modules, "fiona", fiona)
    monkeypatch.setattr(shapefile_import, "logger", logger)

    result = shapefile_import.import_shapefile(str(path))

    assert result["errors"] == ["Feature 0: import failed (RuntimeError)"]
    assert secret not in repr(result)
    assert "private contributor" not in repr(result)
    assert secret not in repr(logger.mock_calls)


def test_shapefile_open_failure_is_bounded_in_result_and_log(tmp_path, monkeypatch):
    secret = "fiona failed at https://user:password@example.invalid/private"
    path = tmp_path / "farm.shp"
    path.touch()
    logger = MagicMock()
    fiona = ModuleType("fiona")
    fiona.open = MagicMock(side_effect=RuntimeError(secret))
    monkeypatch.setitem(sys.modules, "fiona", fiona)
    monkeypatch.setattr(shapefile_import, "logger", logger)

    result = shapefile_import.import_shapefile(str(path))

    assert result["status"] == "error"
    assert result["errors"] == ["Shapefile read failed (RuntimeError)"]
    assert secret not in repr(result)
    assert secret not in repr(logger.mock_calls)
