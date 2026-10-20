"""Console contract for read-only CAP-033 business canvases."""

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


def test_canvas_panel_requires_exact_location_business_planning_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="business-planning-canvases".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert "Read-only canvases for locations with an active business-planning read grant" in panel.group()
    assert 'scope.resource === "business_planning" && scope.action === "read"' in source
    assert "businessPlanningLocations = new Set(businessPlanningLocationIds)" in source
    assert "businessPlanningCanvases.hidden = false" in source


def test_canvas_reader_uses_protected_no_store_route_and_bounded_paging():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadBusinessPlanningCanvases(", "async function loadSession()")
    assert '`/operator/api/business-planning/${encodeURIComponent(locationId)}/canvases?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "businessPlanningLocations.has(locationId)" in reader
    assert "requestVersion !== businessPlanningRequestVersion" in reader
    assert "locationId !== businessPlanningLocation.value" in reader
    assert "nextOffset <= 10000" in reader
    assert "innerHTML" not in reader


def test_canvas_renderer_uses_fixed_fields_and_text_nodes_for_content():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderBusinessPlanningCanvas(canvas)", "async function loadBusinessPlanningCanvases(")
    for field in (
        "canvas_name", "canvas_description", "lifecycle_status", "fiscal_year",
        "schema_version", "version", "health_score", "tags", "updated_at",
        "key_partners", "key_activities", "key_resources", "value_propositions",
        "customer_relationships", "channels", "customer_segments", "revenue_streams",
        "cost_structure",
    ):
        assert f'["{field}"' in renderer
    assert "textContent" in renderer
    assert "JSON.stringify" in renderer
    assert "innerHTML" not in renderer
    for private_field in ("source_reference", "source_system", "raw_import", "created_by", "updated_by"):
        assert private_field not in renderer


def test_canvas_location_refresh_paging_and_ids_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'businessPlanningLocation.addEventListener("change", () => loadBusinessPlanningCanvases())' in source
    assert 'document.querySelector("#business-planning-refresh").addEventListener("click", () => loadBusinessPlanningCanvases())' in source
    assert 'businessPlanningMore.addEventListener("click", () => loadBusinessPlanningCanvases(true))' in source
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_inline_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        return
    source = CONSOLE.read_text(encoding="utf-8")
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
