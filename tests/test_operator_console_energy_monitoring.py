"""Contract checks for the grant-gated farm-energy console panel."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("apps/operator-console/index.html").read_text()


def test_energy_panel_is_hidden_and_describes_excluded_reading_fields():
    panel = re.search(r'<section id="energy-monitoring".*?</section>', SOURCE, re.DOTALL)
    assert panel
    assert 'id="energy-monitoring" hidden' in panel.group()
    assert "verified and approved meter readings" in panel.group()
    assert "Costs, source names, device IDs, notes" in panel.group()
    assert "legacy fixed-factor estimate" in panel.group()
    assert "registered renewable-offset values are historical/advisory" in panel.group()
    assert "Reviewed daily efficiency history" in panel.group()
    assert 'id="energy-monitoring-renewable-rows"' in panel.group()
    assert 'id="energy-monitoring-trend-rows"' in panel.group()
    assert 'id="energy-monitoring-efficiency-rows"' in panel.group()
    assert 'id="energy-monitoring-source-rows"' in panel.group()
    assert "Active energy sources" in panel.group()
    assert 'id="energy-monitoring-rows"' in panel.group()


def test_energy_reader_is_exact_grant_gated_no_store_and_checks_response_scope():
    assert 'scope.resource === "energy_monitoring" && scope.action === "read"' in SOURCE
    reader = re.search(
        r"async function loadEnergyMonitoringSummary\(\).*?\n      }", SOURCE, re.DOTALL
    )
    assert reader
    assert "energyMonitoringLocations.has(locationId)" in reader.group()
    assert "`/operator/api/energy/${encodeURIComponent(locationId)}/summary`" in reader.group()
    assert 'cache: "no-store"' in reader.group()
    assert "result.location_id !== locationId" in reader.group()
    assert "requestVersion !== energyMonitoringRequestVersion" in reader.group()
    assert "result.unit !== \"kWh\"" in reader.group()
    assert "result.dashboard_calculations" in reader.group()


def test_energy_reader_renders_fixed_allowlisted_fields_with_text_content():
    renderer = re.search(
        r"function renderEnergyMonitoringSummary\(summary\).*?\n      }", SOURCE, re.DOTALL
    )
    assert renderer
    assert "sourceTypes.has(row?.source_type)" in renderer.group()
    assert "activities.has(row?.activity_type)" in renderer.group()
    assert "calculations.legacy_carbon_estimate" in renderer.group()
    assert "calculations.trend_7d" in renderer.group()
    assert "legacy_source_type_factors_v1" in renderer.group()
    assert "calculations.registered_renewables" in renderer.group()
    assert "registered_carbon_offset_kg" in renderer.group()
    assert "legacy_generation_coverage_pct" in renderer.group()
    assert "calculations.reviewed_efficiency_history" in renderer.group()
    assert "calculations.active_sources_by_type" in renderer.group()
    assert "activeSourceRows.length > sourceTypes.size" in renderer.group()
    assert "energyMonitoringSourceRows.append(row)" in renderer.group()
    assert "efficiencyHistory.length > 12" in renderer.group()
    assert "energyMonitoringEfficiencyRows.append(row)" in renderer.group()
    assert "new Set(sourceEmissions.map" in renderer.group()
    assert "cell.textContent = energyMonitoringValue(value)" in renderer.group()
    assert ".innerHTML" not in renderer.group()
    assert "cost_per_kwh" not in renderer.group()


def test_energy_panel_refresh_and_location_change_are_wired():
    assert 'document.querySelector("#energy-monitoring-refresh").addEventListener("click", loadEnergyMonitoringSummary)' in SOURCE
    assert "energyMonitoringLocation.addEventListener(\"change\", loadEnergyMonitoringSummary)" in SOURCE


def test_inline_console_javascript_passes_node_syntax_check():
    node = shutil.which("node")
    assert node, "Node.js is required for the operator-console JavaScript syntax check"
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", SOURCE, re.IGNORECASE | re.DOTALL)
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
