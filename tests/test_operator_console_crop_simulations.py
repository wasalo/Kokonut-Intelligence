"""Console contract for persisted crop-simulation reads."""

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


def test_simulation_panel_is_hidden_until_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="crop-simulations".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="crop-simulations" hidden' in panel.group()
    assert 'scope.resource === "digital_twin" && scope.action === "read"' in source
    assert "cropSimulationLocations = new Set(cropSimulationLocationIds)" in source
    assert "cropSimulations.hidden = false" in source
    assert "does not run a model, change a run" in panel.group()


def test_run_list_is_private_bounded_and_location_page_checked():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCropSimulationRuns(", "async function loadCropSimulationDetail(")
    assert "cropSimulationLocations.has(locationId)" in reader
    assert '`/operator/api/crop-simulations/${encodeURIComponent(locationId)}/runs?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert "cropSimulationRunOffset > 10000" in reader
    assert "result.location_id !== locationId || result.offset !== offset" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== cropSimulationListRequestVersion" in reader
    assert "locationId !== cropSimulationsLocation.value" in reader
    assert "cropSimulationDetailRequestVersion += 1" in reader
    assert "cropSimulationsMore.disabled = false" in reader


def test_detail_and_daily_state_pages_remain_bound_to_location_and_run():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCropSimulationDetail(", "function traceabilityDisplayValue(")
    assert '`/operator/api/crop-simulations/${encodeURIComponent(locationId)}/runs/${encodeURIComponent(runId)}?${params}`' in reader
    assert "cropSimulationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "result.run?.run_id !== runId" in reader
    assert "result.offset !== offset" in reader
    assert "requestVersion !== cropSimulationDetailRequestVersion" in reader
    assert "locationId !== cropSimulationsLocation.value" in reader
    assert "runId !== cropSimulationSelectedRunId" in reader
    assert 'cache: "no-store"' in reader
    assert "cropSimulationStateOffset > 10000" in reader
    assert "cropSimulationsStatesMore.disabled = false" in reader


def test_renderers_expose_only_fixed_run_and_state_fields_as_text():
    source = CONSOLE.read_text(encoding="utf-8")
    run_renderer = _function(source, "function renderCropSimulationRun(", "function renderCropSimulationRunSummary(")
    for field in ("twin_name", "completed_at", "final_yield", "final_yield_unit", "total_water_mm", "total_nitrogen_kg", "avg_soil_carbon_pct", "run.run_id"):
        assert field in run_renderer
    assert "cell.textContent" in run_renderer
    assert "button.textContent" in run_renderer
    assert "innerHTML" not in run_renderer

    state_renderer = _function(source, "function renderCropSimulationState(", "async function loadCropSimulationRuns(")
    for field in (
        "crop_stage", "soil_moisture_pct", "soil_nitrogen_ppm", "soil_carbon_pct",
        "soil_temperature_c", "gdd_accumulated", "crop_biomass_kg_ha", "leaf_area_index",
        "root_depth_cm", "rainfall_mm", "irrigation_mm", "et_actual_mm", "drainage_mm",
        "temp_avg_c", "temp_min_c", "temp_max_c", "solar_radiation_mj", "humidity_pct",
        "wind_speed_kmh", "carbon_sequestered_kg_ha", "carbon_emitted_kg_ha",
    ):
        assert field in state_renderer
    assert "description.textContent" in state_renderer
    assert "innerHTML" not in state_renderer
    for forbidden in ("parameters", "metadata", "error", "revenue", "cost", "state_id"):
        assert forbidden not in run_renderer + state_renderer


def test_refresh_location_and_paging_handlers_and_inline_script_contracts():
    source = CONSOLE.read_text(encoding="utf-8")
    bootstrap = _function(source, "async function loadSession()", "document.querySelector(\"#coordination-summary-refresh\")")
    assert "for (const locationId of cropSimulationLocationIds)" in bootstrap
    assert "cropSimulationsLocation.append(option)" in bootstrap
    assert "await loadCropSimulationRuns()" in bootstrap
    assert 'cropSimulationsLocation.addEventListener("change", () => loadCropSimulationRuns())' in source
    assert 'cropSimulationsMore.addEventListener("click", () => loadCropSimulationRuns(true))' in source
    assert "loadCropSimulationDetail(cropSimulationSelectedRunId, true)" in source
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
