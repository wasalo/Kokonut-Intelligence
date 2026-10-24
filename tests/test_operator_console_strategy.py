"""Console contract for read-only CAP-028 strategy summaries."""

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


def test_strategy_panel_requires_exact_location_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="strategy-plan-summary".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "Structural gate status describes database checks only" in panel.group()
    assert 'scope.resource === "strategy" && scope.action === "read"' in source
    assert "strategyPlanLocations = new Set(strategyPlanLocationIds)" in source
    assert "strategyPlanSummary.hidden = false" in source


def test_strategy_reader_uses_protected_no_store_route_stale_guards_and_paging():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadStrategyPlanSummaries(", "async function loadSession()")
    assert '`/operator/api/strategy/${encodeURIComponent(locationId)}/plans?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "strategyPlanLocations.has(locationId)" in reader
    assert "requestVersion !== strategyPlanRequestVersion" in reader
    assert "locationId !== strategyPlanLocation.value" in reader
    assert "nextOffset <= 10000" in reader
    assert "innerHTML" not in reader


def test_card_renderer_uses_fixed_fields_and_labels_gate_as_nonapproval():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderStrategyPlanCard(plan)", "async function loadStrategyPlanSummaries(")
    for field in (
        "plan_name", "version", "plan_status", "visibility", "planning_horizon_start",
        "planning_horizon_end", "updated_at", "cascade_mode", "cascade_status",
        "has_parent_strategy", "objective_count", "initiative_count",
        "completed_initiative_count", "investment_case_count", "recommended_investment_count",
        "open_coherence_finding_count", "blocking_finding_count", "structural_gate_status",
        "open_review_task_count", "submitted_allocation_count", "approved_allocation_count",
    ):
        assert f'["{field}"' in renderer or f"plan.{field}" in renderer
    assert '"Structural gate status (not approval)"' in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    for private_field in (
        "strategy_plan_id", "parent_strategy_plan_id", "diagnosis", "guiding_policy",
        "cascade_rationale", "allocation_rationale", "cost", "evidence", "party_id",
    ):
        assert f"plan.{private_field}" not in renderer


def test_refresh_location_and_pagination_controls_are_wired_with_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'strategyPlanLocation.addEventListener("change", () => loadStrategyPlanSummaries())' in source
    assert 'document.querySelector("#strategy-plan-refresh").addEventListener("click", () => loadStrategyPlanSummaries())' in source
    assert 'strategyPlanMore.addEventListener("click", () => loadStrategyPlanSummaries(true))' in source
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
