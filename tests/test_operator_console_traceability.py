"""Console contract for location-scoped traceability reads."""

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


def test_traceability_panel_requires_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="traceability".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="traceability" hidden' in panel.group()
    assert 'scope.resource === "traceability" && scope.action === "read"' in source
    assert "traceabilityLocations = new Set(traceabilityLocationIds)" in source
    assert "traceability.hidden = false" in source
    assert "does not verify, publish, or attest a batch" in panel.group()


def test_batch_list_uses_no_store_location_grant_paging_and_status_allowlist():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadTraceabilityBatches(", "function renderTraceabilityRecords(")
    assert '`/operator/api/traceability/${encodeURIComponent(locationId)}/batches?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert "traceabilityLocations.has(locationId)" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== traceabilityListRequestVersion" in reader
    assert "locationId !== traceabilityLocation.value" in reader
    assert "result.offset !== offset" in reader
    assert "traceabilityOffset > 10000" in reader
    assert "traceabilityDetailRequestVersion += 1" in reader
    for status in ("active", "in_transit", "delivered", "consumed", "rejected", "expired"):
        assert f'value="{status}"' in source


def test_batch_and_related_records_render_fixed_fields_as_text_only():
    source = CONSOLE.read_text(encoding="utf-8")
    related_renderer = _function(source, "function renderTraceabilityRecords(", "function renderTraceabilityBatch(result)")
    assert "records?.items" in related_renderer
    assert "records?.truncated === true" in related_renderer
    assert "Showing the first 100 records" in related_renderer
    assert "innerHTML" not in related_renderer

    row_renderer = _function(source, "function renderTraceabilityBatchRows(", "async function loadTraceabilityBatches(")
    for field in ("batch_number", "crop_name", "quantity", "harvest_date", "organic", "status"):
        assert f'["{field}"' in row_renderer
    assert "batch.id" in row_renderer
    assert "textContent" in row_renderer
    assert "innerHTML" not in row_renderer

    detail_renderer = _function(source, "function renderTraceabilityBatch(result)", "async function loadTraceabilityBatch(")
    for key in ("custody_transfers", "quality_inspections", "certifications", "food_safety_records", "provenance_events"):
        assert f'["{key}"' in detail_renderer
    for forbidden in ("actor_id", "actor_name", "inspector_id", "recorded_by", "evidence_url", "metadata", "gps"):
        assert forbidden not in detail_renderer
    assert "textContent" in detail_renderer
    assert "innerHTML" not in detail_renderer


def test_detail_reads_are_location_bound_no_store_and_stale_guarded():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadTraceabilityBatch(batchId)", "function renderBusinessPlanningCanvas(")
    assert '`/operator/api/traceability/${encodeURIComponent(locationId)}/batches/${encodeURIComponent(batchId)}`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "traceabilityLocations.has(locationId)" in reader
    assert "requestVersion !== traceabilityDetailRequestVersion" in reader
    assert "locationId !== traceabilityLocation.value" in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader


def test_refresh_location_paging_and_inline_javascript_contracts():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'traceabilityLocation.addEventListener("change", () => loadTraceabilityBatches())' in source
    assert 'traceabilityMore.addEventListener("click", () => loadTraceabilityBatches(true))' in source
    assert 'document.querySelector("#traceability-refresh").addEventListener("click"' in source
    assert 'document.querySelector("#traceability-status-filter").addEventListener("change"' in source
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
