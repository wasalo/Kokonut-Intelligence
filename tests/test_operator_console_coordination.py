"""Console contract for read-only CAP-034 coordination aggregates."""

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


def test_coordination_summary_panel_requires_exact_scoped_read_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="coordination-summary".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only counts for location-scoped alliances" in panel.group()
    assert 'scope.resource === "coordination" && scope.action === "read"' in source
    assert "coordinationSummaryLocations = new Set(coordinationLocationIds)" in source
    assert 'coordinationSummary.hidden = false' in source


def test_summary_reader_uses_no_store_route_and_discards_stale_responses():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCoordinationSummary()", "async function loadSession()")
    assert '`/operator/api/coordination/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "coordinationSummaryLocations.has(locationId)" in reader
    assert "requestVersion !== coordinationSummaryRequestVersion" in reader
    assert "locationId !== coordinationSummaryLocation.value" in reader
    assert "innerHTML" not in reader


def test_renderer_uses_only_projection_aggregate_counts():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderCoordinationSummary(summary)", "async function loadCoordinationSummary()")
    for field in (
        "alliance_count", "draft_alliance_count", "proposed_alliance_count", "approved_alliance_count",
        "active_alliance_count", "paused_alliance_count", "completed_alliance_count",
        "dissolved_alliance_count", "rejected_alliance_count", "overdue_review_count",
        "open_conflict_declaration_count", "unreviewed_harm_analysis_count", "open_appeal_count",
        "open_remedy_count", "preserved_minority_view_count", "completed_knowledge_exchange_count",
        "open_learning_link_count", "draft_metric_observation_count", "rejected_metric_observation_count",
    ):
        assert f'"{field}"' in renderer
    assert "Object.entries" not in renderer
    assert "textContent" in renderer
    for private_field in ("party_id", "alliance_name", "narrative", "evidence", "metric_value"):
        assert private_field not in renderer


def test_refresh_and_location_controls_are_wired_and_ids_are_unique():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'coordinationSummaryLocation.addEventListener("change", loadCoordinationSummary)' in source
    assert 'document.querySelector("#coordination-summary-refresh").addEventListener("click", loadCoordinationSummary)' in source
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
