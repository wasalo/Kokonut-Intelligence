"""Contract checks for the grant-gated waste-management console panel."""

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

SOURCE = Path("apps/operator-console/index.html").read_text()


def test_waste_management_panel_is_hidden_and_omits_sensitive_details():
    start = SOURCE.index('<section id="waste-management"')
    end = SOURCE.index('<section id="landscape-pollinator"', start)
    panel = SOURCE[start:end]
    assert 'id="waste-management" hidden' in panel
    assert "Compost yield and process measurements are descriptive and advisory, not a compost-quality certification." in panel
    assert "Incident narratives, affected areas, destinations, costs, notes, and reporter identities are excluded." in panel
    assert "Counts are not compliance determinations." in panel
    assert "New entries are location-scoped and remain recorded until a separate human verification workflow is available." in panel
    for element_id in (
        "waste-management-streams", "waste-management-compost",
        "waste-management-recycling", "waste-management-incidents",
    ):
            assert f'id="{element_id}"' in panel


def test_waste_reader_uses_exact_grant_scope_and_no_store_location_checked_request():
    assert 'scope.resource === "waste_management" && scope.action === "read"' in SOURCE
    reader = re.search(r"async function loadWasteManagementSummary\(\).*?\n      }", SOURCE, re.DOTALL)
    assert reader
    assert "wasteManagementLocations.has(locationId)" in reader.group()
    assert '`/operator/api/waste/${encodeURIComponent(locationId)}/summary`' in reader.group()
    assert 'cache: "no-store"' in reader.group()
    assert "result.location_id !== locationId" in reader.group()
    assert "requestVersion !== wasteManagementRequestVersion" in reader.group()
    assert "Array.isArray(result.pollution_incidents)" in reader.group()


def test_waste_console_validates_categories_and_renders_only_fixed_text_fields():
    renderer = re.search(r"function renderWasteManagementSummary\(summary\).*?\n      }", SOURCE, re.DOTALL)
    assert renderer
    assert "wasteTypes.has(row?.waste_type)" in renderer.group()
    assert "compostMethods.has(row?.compost_method)" in renderer.group()
    assert '"weighted_yield_pct"' in renderer.group()
    assert '"mean_batch_yield_pct"' in renderer.group()
    assert "row.graded_batches <= row.record_count" in renderer.group()
    assert "incidentStatuses.has(row?.status)" in renderer.group()
    table_renderer = re.search(r"function renderWasteAggregateTable\(.*?\n      }", SOURCE, re.DOTALL)
    assert table_renderer
    assert "cell.textContent = wasteManagementValue(item[field])" in table_renderer.group()
    assert ".innerHTML" not in table_renderer.group()


def test_waste_console_refresh_and_location_change_are_wired_and_ids_unique():
    assert 'document.querySelector("#waste-management-refresh").addEventListener("click", loadWasteManagementSummary)' in SOURCE
    assert 'wasteManagementLocation.addEventListener("change", () =>' in SOURCE
    assert 'scope.resource === "waste_management" && scope.action === "create"' in SOURCE
    assert 'const compostingCaptureForm = document.querySelector("#composting-capture-form")' in SOURCE
    assert 'compostingCapture.hidden = !canCreate' in SOURCE
    assert 'route: "composting"' in SOURCE
    assert 'compost_method: compostingCaptureForm.querySelector("#composting-capture-method").value' in SOURCE
    assert 'id="composting-capture-feedstock" type="text" maxlength="200"' in SOURCE
    assert 'id="composting-capture-method" type="text" maxlength="100"' in SOURCE
    assert 'output_kg: compostingCaptureForm.querySelector("#composting-capture-output").value || null' in SOURCE
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in SOURCE
    assert '"X-CSRF-Token": csrfToken()' in SOURCE
    assert "Retrying reuses the same request ID and entry." in SOURCE
    assert "result.status !== \"recorded\"" in SOURCE
    ids = re.findall(r'\bid="([^\"]+)"', SOURCE)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


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
