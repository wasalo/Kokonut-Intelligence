"""Console contract for location-scoped irrigation status reads."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_irrigation_panel_is_hidden_until_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="irrigation-status".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="irrigation-status" hidden' in panel.group()
    assert 'scope.resource === "precision_irrigation" && scope.action === "read"' in source
    assert "irrigationStatusLocations = new Set(irrigationStatusLocationIds)" in source
    assert "irrigationStatus.hidden = false" in source
    assert "cannot approve schedules or control devices" in source


def test_status_request_is_grant_checked_private_bounded_and_stale_guarded():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadIrrigationStatus(", "function traceabilityDisplayValue(")
    assert "irrigationStatusLocations.has(locationId)" in reader
    assert '`/operator/api/irrigation/${encodeURIComponent(locationId)}/status?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert "irrigationStatusOffset > 10000" in reader
    assert "result.location_id !== locationId || result.offset !== offset" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== irrigationStatusRequestVersion" in reader
    assert "locationId !== irrigationStatusLocation.value" in reader
    assert "Previously loaded zones remain visible" in reader
    assert "irrigationStatusMore.disabled = false" in reader


def test_zone_renderer_uses_fixed_fields_as_text_and_never_exposes_controls():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderIrrigationStatusZone(", "async function loadIrrigationStatus(")
    for field in (
        "zone.name", "zone.soil_type", "zone.area_m2", "zone.current_moisture_pct",
        "zone.moisture_status", "zone.target_min_pct", "zone.target_max_pct",
        "zone.next_irrigation_start", "zone.next_irrigation_status",
        "zone.next_irrigation_volume_l", "zone.last_irrigation_at",
        "zone.last_irrigation_volume_l",
    ):
        assert field in renderer
    assert "cell.textContent" in renderer
    assert "innerHTML" not in renderer
    for forbidden in ("sensor_device_id", "actuator", "coordinates", "geometry", "reason"):
        assert forbidden not in renderer


def test_location_refresh_and_pagination_bind_to_the_granted_surface():
    source = CONSOLE.read_text(encoding="utf-8")
    bootstrap = _function(source, "async function loadSession()", "document.querySelector(\"#coordination-summary-refresh\")")
    assert "for (const locationId of irrigationStatusLocationIds)" in bootstrap
    assert "irrigationStatusLocation.append(option)" in bootstrap
    assert "await loadIrrigationStatus()" in bootstrap
    assert 'document.querySelector("#irrigation-status-refresh").addEventListener("click", () => loadIrrigationStatus())' in source
    assert 'irrigationStatusLocation.addEventListener("change", () => loadIrrigationStatus())' in source
    assert 'irrigationStatusMore.addEventListener("click", () => loadIrrigationStatus(true))' in source


def test_element_ids_are_unique_and_inline_javascript_parses():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^\"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"

    node = shutil.which("node")
    if node is None:
        return
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as script:
        script.write(scripts[0])
        script.flush()
        result = subprocess.run(
            [node, "--check", script.name],
            check=False,
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, result.stderr
