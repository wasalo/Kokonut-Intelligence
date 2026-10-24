"""Console contract for location-scoped harvest-yield summaries."""

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


def test_yield_panel_is_hidden_until_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="yield-monitoring".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="yield-monitoring" hidden' in panel.group()
    assert 'scope.resource === "yield_monitoring" && scope.action === "read"' in source
    assert "yieldMonitoringLocations = new Set(yieldMonitoringLocationIds)" in source
    assert "yieldMonitoring.hidden = false" in source
    assert "Yields stay grouped by their recorded units" in source


def test_summary_request_is_grant_checked_private_and_stale_guarded():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadYieldMonitoringSummary(", "function traceabilityDisplayValue(")
    assert "yieldMonitoringLocations.has(locationId)" in reader
    assert '`/operator/api/yield-monitoring/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== yieldMonitoringRequestVersion" in reader
    assert "locationId !== yieldMonitoringLocation.value" in reader
    assert "result.location_id !== locationId" in reader
    assert "401" in reader and "403" in reader
    assert "yieldMonitoringLocationIds" in source


def test_renderers_use_fixed_aggregate_fields_and_text_nodes():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderYieldMonitoringSummary(", "async function loadYieldMonitoringSummary(")
    for field in (
        "total_observations", "first_harvest", "last_harvest", "totals_by_yield_unit",
        "crops", "recent_harvests", "yield_unit", "avg_yield", "total_production",
        "harvest_date", "area_ha", "grade",
    ):
        assert field in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    formatter = _function(source, "function yieldMonitoringValue(", "function renderYieldMonitoringTable(")
    assert 'typeof value === "string" || typeof value === "boolean"' in formatter
    assert 'return "—"' in formatter
    table_renderer = _function(source, "function renderYieldMonitoringTable(", "function renderYieldMonitoringSummary(")
    assert "Array.isArray(rows)" in table_renderer
    assert "row?.[field]" in table_renderer
    assert "textContent" in table_renderer
    assert "innerHTML" not in table_renderer
    for forbidden in ("actor_id", "metadata", "evidence_url", "source_id"):
        assert forbidden not in renderer


def test_location_switch_and_refresh_reload_only_the_selected_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'document.querySelector("#yield-monitoring-refresh").addEventListener("click", loadYieldMonitoringSummary)' in source
    assert 'yieldMonitoringLocation.addEventListener("change", loadYieldMonitoringSummary)' in source
    bootstrap = _function(source, "async function loadSession()", "document.querySelector(\"#coordination-summary-refresh\")")
    assert "for (const locationId of yieldMonitoringLocationIds)" in bootstrap
    assert "yieldMonitoringLocation.append(option)" in bootstrap
    assert "await loadYieldMonitoringSummary()" in bootstrap


def test_element_ids_are_unique_and_inline_javascript_parses():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
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
