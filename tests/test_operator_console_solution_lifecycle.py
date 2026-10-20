"""Console contract for the read-only CAP-035 lifecycle summary."""

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


def test_solution_lifecycle_panel_requires_exact_scoped_read_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only aggregate lifecycle counts" in panel.group()
    assert 'scope.resource === "solution_lifecycle" && scope.action === "read"' in source
    assert "solutionLifecycleLocations = new Set(solutionLifecycleLocationIds)" in source
    assert 'solutionLifecycle.hidden = false' in source
    assert "No lifecycle state was changed" in source


def test_summary_uses_same_origin_no_store_route_and_discards_stale_location_responses():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleSummary()", "async function loadSession()")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleSummaryRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "innerHTML" not in reader


def test_renderer_uses_only_fixed_aggregate_groups_and_safe_dom_text():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderSolutionLifecycleSummary(summary)", "async function loadSolutionLifecycleSummary()")
    for key in (
        "stage_counts", "solution_status_counts", "stage_gate_status_counts",
        "latest_gate_evaluation_counts", "experiment_status_counts", "experiment_result_counts",
        "replication_status_counts", "funding_decision_counts", "adoption_program_status_counts",
        "configuration_approval_counts", "adopter_readiness_counts", "scale_gate_status_counts",
        "learning_decision_counts", "retirement_status_counts",
    ):
        assert f'"{key}"' in renderer
    assert "Object.entries" not in renderer
    assert "textContent" in renderer
    for private_field in ("solution_id", "solution_name", "evidence", "requested_amount", "party_id"):
        assert private_field not in renderer


def test_console_ids_are_unique_and_refresh_controls_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    assert 'solutionLifecycleLocation.addEventListener("change", loadSolutionLifecycleSummary)' in source
    assert 'document.querySelector("#solution-lifecycle-refresh").addEventListener("click", loadSolutionLifecycleSummary)' in source


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
