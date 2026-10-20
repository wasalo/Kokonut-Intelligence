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


def test_gate_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleGates(", "function renderCoordinationSummary(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleGatesRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_gate_panel_displays_only_fixed_non_mutating_status_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<h3>Location-linked stage gates</h3>(.*?)</section>', source, re.DOTALL)
    assert panel is not None
    assert "does not approve a transition" in panel.group(1)
    renderer = _function(source, "function appendSolutionLifecycleGate(", "async function loadSolutionLifecycleGates(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "from_stage", "to_stage",
        "required_evidence_maturity", "required_experiment_count", "requires_human_approval",
        "gate_status", "gate_created_at", "latest_evaluation_passed", "latest_evaluated_at",
    ):
        assert f"gate.{field}" in renderer
    for private_field in ("gate_id", "solution_id", "evidence", "reviewer", "raw"):
        assert f"gate.{private_field}" not in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_experiment_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleExperiments(", "function renderCoordinationSummary(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/experiments?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleExperimentsRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "result.next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_experiment_renderer_limits_result_visibility_to_reviewed_enum_and_metadata():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<h3>Experiments and reviewed outcomes</h3>(.*?)</section>', source, re.DOTALL)
    assert panel is not None
    assert "only an explicitly reviewed outcome" in panel.group(1)
    renderer = _function(source, "function appendSolutionLifecycleExperiment(", "async function loadSolutionLifecycleExperiments(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "protocol_version",
        "experiment_status", "duration_days", "primary_metric_count", "secondary_metric_count",
        "experiment_created_at", "experiment_updated_at", "started_at", "completed_at",
        "latest_result_outcome", "latest_result_reviewed_at",
    ):
        assert f"experiment.{field}" in renderer
    assert "experiment.latest_result_reviewed_at" in renderer
    for private_field in ("experiment_id", "solution_id", "hypothesis", "metric_key", "primary_results", "adverse_events", "evidence"):
        assert f"experiment.{private_field}" not in renderer
    assert "No reviewed result" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


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
    assert 'solutionLifecycleLocation.addEventListener("change", () =>' in source
    assert "loadSolutionLifecycleSummary();" in source
    assert 'solutionLifecycleGatesLoad.addEventListener("click", () => loadSolutionLifecycleGates())' in source
    assert 'solutionLifecycleGatesMore.addEventListener("click", () => loadSolutionLifecycleGates(true))' in source
    assert 'solutionLifecycleExperimentsLoad.addEventListener("click", () => loadSolutionLifecycleExperiments())' in source
    assert 'solutionLifecycleExperimentsMore.addEventListener("click", () => loadSolutionLifecycleExperiments(true))' in source
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
