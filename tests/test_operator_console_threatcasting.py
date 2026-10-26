"""Console contract for read-only CAP-026 advisory backcasting views."""

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


def test_backcasting_panel_requires_exact_location_read_grants_and_is_advisory():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="threatcasting-backcasts".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "cannot approve a plan, change milestone state, publish a recommendation" in panel.group()
    assert 'scope.resource === "threatcasting" && scope.action === "read"' in source
    assert "threatcastingLocations = new Set(threatcastingLocationIds)" in source
    assert "threatcastingBackcasts.hidden = false" in source


def test_list_reader_uses_signed_scope_route_no_store_and_keyset_cursor():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadThreatcastingPlans(", "async function loadSession()")
    assert '`/operator/api/threatcasting/${encodeURIComponent(locationId)}/backcast-plans?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50" })' in reader
    assert 'params.set("cursor_created_at", threatcastingNextCursor.created_at)' in reader
    assert 'params.set("cursor_plan_id", threatcastingNextCursor.plan_id)' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "threatcastingLocations.has(locationId)" in reader
    assert "requestVersion !== threatcastingListRequestVersion" in reader
    assert "locationId !== threatcastingLocation.value" in reader
    assert 'result.advisory_only !== true' in reader
    assert "innerHTML" not in reader


def test_plan_detail_reader_is_no_store_stale_guarded_and_handles_response_cap():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadThreatcastingPlanDetail(", "async function loadThreatcastingPlans(")
    assert '`/operator/api/threatcasting/${encodeURIComponent(locationId)}/backcast-plans/${encodeURIComponent(planId)}`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== threatcastingDetailRequestVersion" in reader
    assert "locationId !== threatcastingLocation.value" in reader
    assert "planId !== threatcastingSelectedPlanId" in reader
    assert "response.status === 413" in reader
    assert 'result.advisory_only !== true' in reader
    assert "innerHTML" not in reader


def test_cards_render_only_fixed_advisory_fields_as_text():
    source = CONSOLE.read_text(encoding="utf-8")
    card = _function(source, "function appendThreatcastingPlanCard(plan)", "function renderThreatcastingPlanDetail(")
    for field in (
        "plan_name", "narrative_title", "narrative_type", "threat_name",
        "future_state_description", "current_gap_analysis", "created_at", "updated_at",
        "milestone_count", "completed_milestone_count", "blocked_milestone_count",
    ):
        assert f"plan.{field}" in card
    assert "advisory" in card.lower()
    assert "textContent" in card
    assert "innerHTML" not in card
    assert "textContent = plan.id" not in card


def test_detail_renderer_uses_fixed_milestone_fields_and_hides_dependency_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderThreatcastingPlanDetail(plan)", "async function loadThreatcastingPlanDetail(")
    for field in (
        "plan_name", "narrative_title", "narrative_type", "threat_name",
        "future_state_description", "current_gap_analysis", "created_at", "updated_at",
        "milestones", "milestone_order", "milestone_description", "milestone_target_date",
        "milestone_status", "dependencies", "responsible_party", "resource_requirements",
        "completion_evidence",
    ):
        assert f"plan.{field}" in renderer or f"milestone.{field}" in renderer
    assert "dependencies.length" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    assert "milestone.dependencies.join" not in renderer


def test_refresh_location_more_controls_and_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'threatcastingLocation.addEventListener("change", () => loadThreatcastingPlans())' in source
    assert 'document.querySelector("#threatcasting-refresh").addEventListener("click", () => loadThreatcastingPlans())' in source
    assert 'threatcastingMore.addEventListener("click", () => loadThreatcastingPlans(true))' in source
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
