"""Console contract for read-only CAP-032 business architecture."""

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


def test_business_architecture_panel_uses_exact_scoped_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="business-architecture-summary".*?</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert "Read-only approved mission statements and location-roadmap mappings" in panel.group()
    assert 'scope.resource === "business_architecture" && scope.action === "read"' in source
    assert "businessArchitectureLocations = new Set(businessArchitectureLocationIds)" in source
    assert "businessArchitectureSummary.hidden = false" in source


def test_reader_uses_protected_no_store_route_stale_guards_and_bounded_pages():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadBusinessArchitectureSummary(", "async function loadSession()")
    assert '`/operator/api/business-architecture/${encodeURIComponent(locationId)}/summary?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "businessArchitectureLocations.has(locationId)" in reader
    assert "requestVersion !== businessArchitectureRequestVersion" in reader
    assert "locationId !== businessArchitectureLocation.value" in reader
    assert "nextOffset <= 10000" in reader
    assert "innerHTML" not in reader


def test_missions_and_mapping_rows_use_allowlisted_fields_and_text_nodes():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadBusinessArchitectureSummary(", "async function loadSession()")
    for field in (
        "statement_type", "statement_text", "effective_date", "review_date",
        "roadmap_name", "roadmap_status", "planning_horizon_start",
        "planning_horizon_end", "requirement_title", "need_type", "priority",
        "requirement_status", "capability_name", "value_stream_name",
        "strategy_perspective",
    ):
        assert f"mission.{field}" in reader or f"mapping.{field}" in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader
    for private_field in (
        "description", "evidence", "party_id", "owner_id", "rationale", "metadata",
        "roadmap_id", "requirement_id",
    ):
        assert f"mapping.{private_field}" not in reader
        assert f"mission.{private_field}" not in reader


def test_refresh_location_and_pagination_controls_are_wired_with_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'businessArchitectureLocation.addEventListener("change", () => loadBusinessArchitectureSummary())' in source
    assert 'document.querySelector("#business-architecture-refresh").addEventListener("click", () => loadBusinessArchitectureSummary())' in source
    assert 'businessArchitectureMore.addEventListener("click", () => loadBusinessArchitectureSummary(true))' in source
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
