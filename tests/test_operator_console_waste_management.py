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
    assert "Aggregate summaries exclude incident narratives, affected areas, destinations, costs, notes, and reporter identities; the incident review queue is separately gated." in panel
    assert "Counts are not compliance determinations." in panel
    assert "New entries are location-scoped and remain recorded until a separate human verification workflow is available." in panel
    for element_id in (
        "waste-management-streams", "waste-management-compost",
        "waste-management-recycling", "waste-management-incidents",
        "waste-management-period-days", "waste-management-period-total",
        "waste-management-by-type", "waste-management-by-disposal",
        "waste-management-compost-efficiency-total", "waste-management-compost-methods",
        "waste-management-compost-quality",
    ):
            assert f'id="{element_id}"' in panel


def test_waste_reader_uses_exact_grant_scope_and_no_store_location_checked_request():
    assert 'scope.resource === "waste_management" && scope.action === "read"' in SOURCE
    reader = re.search(r"async function loadWasteManagementSummary\(\).*?\n      }", SOURCE, re.DOTALL)
    assert reader
    assert "wasteManagementLocations.has(locationId)" in reader.group()
    assert '`/operator/api/waste/${encodeURIComponent(locationId)}/summary?days=${encodeURIComponent(days)}`' in reader.group()
    assert 'cache: "no-store"' in reader.group()
    assert "result.location_id !== locationId" in reader.group()
    assert "result.waste_summary?.period_days !== days" in reader.group()
    assert "result.composting_efficiency?.location_id !== locationId" in reader.group()
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
    assert "period.by_type" in renderer.group()
    assert "efficiency.by_method" in renderer.group()
    assert "efficiency.recent_quality" in renderer.group()
    assert "cell.textContent = wasteManagementValue(item[field])" in SOURCE
    table_renderer = re.search(r"function renderWasteAggregateTable\(.*?\n      }", SOURCE, re.DOTALL)
    assert table_renderer
    assert "cell.textContent = wasteManagementValue(item[field])" in table_renderer.group()
    assert ".innerHTML" not in table_renderer.group()


def test_waste_console_refresh_and_location_change_are_wired_and_ids_unique():
    assert 'document.querySelector("#waste-management-refresh").addEventListener("click", loadWasteManagementSummary)' in SOURCE
    assert 'wasteManagementLocation.addEventListener("change", () =>' in SOURCE
    assert 'wasteManagementDays.addEventListener("change", loadWasteManagementSummary)' in SOURCE
    assert 'scope.resource === "waste_management" && scope.action === "create"' in SOURCE
    assert 'const compostingCaptureForm = document.querySelector("#composting-capture-form")' in SOURCE
    assert 'compostingCapture.hidden = !canCreate' in SOURCE
    assert 'const recyclingCaptureForm = document.querySelector("#recycling-capture-form")' in SOURCE
    assert 'recyclingCapture.hidden = !canCreate' in SOURCE
    assert 'route: "composting"' in SOURCE
    assert 'route: "recycling"' in SOURCE
    assert 'compost_method: compostingCaptureForm.querySelector("#composting-capture-method").value' in SOURCE
    assert 'id="composting-capture-feedstock" type="text" maxlength="200"' in SOURCE
    assert 'id="composting-capture-method" type="text" maxlength="100"' in SOURCE
    assert 'output_kg: compostingCaptureForm.querySelector("#composting-capture-output").value || null' in SOURCE
    assert 'material_type: recyclingCaptureForm.querySelector("#recycling-capture-material").value' in SOURCE
    assert 'revenue: recyclingCaptureForm.querySelector("#recycling-capture-revenue").value || null' in SOURCE
    assert 'id="recycling-capture-material" type="text" maxlength="100"' in SOURCE
    assert 'currency-classified' in SOURCE
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in SOURCE
    assert '"X-CSRF-Token": csrfToken()' in SOURCE
    assert "Retrying reuses the same request ID and entry." in SOURCE
    assert "result.status !== responseStatus" in SOURCE
    assert 'responseStatus = "recorded"' in SOURCE
    ids = re.findall(r'\bid="([^\"]+)"', SOURCE)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_incident_capture_and_resolution_use_separate_grants_and_stable_retries():
    assert 'scope.resource === "waste_management" && scope.action === "create"' in SOURCE
    assert 'scope.resource === "waste_management" && scope.action === "review"' in SOURCE
    assert "incidentCapture.hidden = !canCreate" in SOURCE
    assert "incidentReview.hidden = !canReviewIncidents" in SOURCE
    assert '`/operator/api/waste/${encodeURIComponent(pending.locationId)}/${route}`' in SOURCE
    assert 'route: "incidents"' in SOURCE
    assert 'responseStatus: "open"' in SOURCE
    assert 'responseIdField: "incident_id"' in SOURCE
    assert '"X-CSRF-Token": csrfToken()' in SOURCE
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in SOURCE
    assert '`/operator/api/waste/${encodeURIComponent(pending.locationId)}/incidents/${encodeURIComponent(pending.incidentId)}/resolve`' in SOURCE
    assert 'request_id: requestId' in SOURCE
    assert 'result.status !== "resolved"' in SOURCE
    assert 'Retrying reuses the same request ID and resolution.' in SOURCE
    assert '`/operator/api/waste/${encodeURIComponent(locationId)}/incidents?offset=${offset}`' in SOURCE
    assert 'result.offset !== offset' in SOURCE
    assert 'incidentReviewOffset += 100' in SOURCE
    assert "heading.textContent = `${incident.severity.toUpperCase()} — ${incident.incident_type} — ${incident.incident_date}`" in SOURCE
    assert "description.textContent = incident.description" in SOURCE
    assert ".innerHTML" not in SOURCE[SOURCE.index("function renderPollutionIncidentReviewQueue"):SOURCE.index("async function loadPollutionIncidentReviewQueue")]


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
