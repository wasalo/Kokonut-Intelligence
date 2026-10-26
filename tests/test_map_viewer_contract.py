"""Source-level safety contract for the legacy Leaflet farm viewer."""

from pathlib import Path

VIEWER = Path(__file__).parents[1] / "services/maps/viewer.html"


def test_farm_popup_uses_text_nodes_for_database_metadata():
    source = VIEWER.read_text(encoding="utf-8")

    assert "title.textContent" in source
    assert "description.textContent" in source
    assert ".bindPopup(createFarmPopup(loc))" in source
    assert "bindPopup(`<b>${loc.name}</b>" not in source


def test_map_accepts_zero_coordinates_and_rejects_out_of_range_values():
    source = VIEWER.read_text(encoding="utf-8")

    assert "function parseCoordinate(value, minimum, maximum)" in source
    assert "Number.isFinite(coordinate)" in source
    assert "parseCoordinate(loc.latitude, -90, 90)" in source
    assert "parseCoordinate(loc.longitude, -180, 180)" in source
    assert "latitude !== null && longitude !== null" in source
    assert "if (loc.latitude && loc.longitude)" not in source
