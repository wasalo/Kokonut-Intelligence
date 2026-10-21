"""Console contract for read-only CAP-037 operating-pilot views."""

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


def test_operating_pilot_surface_is_gated_by_exact_location_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="operating-pilot".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only, location-scoped summary" in panel.group()
    assert "Work-claim activity" in panel.group()
    assert 'scope.resource === "operating_pilot" && scope.action === "read"' in source
    assert "operatingPilotLocations = new Set(operatingPilotLocationIds)" in source
    assert 'operatingPilot.hidden = false' in source
    assert "operating-pilot" in source


def test_summary_and_pages_use_protected_no_store_routes_and_safe_text_rendering():
    source = CONSOLE.read_text(encoding="utf-8")
    summary = _function(source, "async function loadOperatingPilotSummary()", "async function loadOperatingPilotDemand(")
    demand = _function(source, "async function loadOperatingPilotDemand(append = false)", "async function loadOperatingPilotCapacity(")
    capacity = _function(source, "async function loadOperatingPilotCapacity(append = false)", "async function loadOperatingPilot()")
    claims = _function(source, "async function loadOperatingPilotWorkClaims(append = false)", "async function loadOperatingPilot()")
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/summary`' in summary
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/demand-signals?${params}`' in demand
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/capacity-periods?${params}`' in capacity
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/work-claims?${params}`' in claims
    for reader in (summary, demand, capacity, claims):
        assert 'credentials: "same-origin"' in reader
        assert 'cache: "no-store"' in reader
        assert "operatingPilotLocations.has(locationId)" in reader
        assert "innerHTML" not in reader
    assert "description.textContent = operatingPilotDisplayValue(value)" in source
    assert "cell.textContent = operatingPilotDisplayValue(value)" in source


def test_capacity_cohort_suppression_never_renders_hour_totals():
    source = CONSOLE.read_text(encoding="utf-8")
    capacity = _function(source, "async function loadOperatingPilotCapacity(append = false)", "async function loadOperatingPilot()")
    assert 'const suppression = item.suppressed === true' in capacity
    assert capacity.count('suppression ? "Suppressed (<3 contributors)" : item.') == 3
    assert 'addOperatingPilotMetric("Current-period capacity", "Suppressed (<3 contributors)")' in source


def test_work_claim_cohort_suppression_never_renders_individual_claim_data():
    source = CONSOLE.read_text(encoding="utf-8")
    claims = _function(
        source,
        "async function loadOperatingPilotWorkClaims(append = false)",
        "async function loadOperatingPilot()",
    )
    assert 'item.suppressed === true ? "Suppressed (<3 contributors)" : item.claim_count' in claims
    assert "item.work_type" in claims
    for private_field in ("claim_id", "work_item_id", "claimant_party_id", "decision_reason"):
        assert private_field not in claims


def test_summary_renders_only_fixed_aggregate_allowlists():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderOperatingPilotSummary(summary)", "function appendOperatingPilotRow(")
    for key in (
        '"work_claims"',
        '"competency_reviews"',
        '"learning_plans"',
        '"resource_requests"',
        '"aggregate_only_coaching_sessions"',
    ):
        assert key in renderer
    assert "Object.entries" not in renderer
    assert "party_id" not in renderer
    assert "participant" not in renderer


def test_location_changes_and_load_more_are_wired_with_bounded_paging():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'operatingPilotLocation.addEventListener("change", loadOperatingPilot)' in source
    assert 'operatingPilotDemandMore.addEventListener("click", () => loadOperatingPilotDemand(true))' in source
    assert 'operatingPilotCapacityMore.addEventListener("click", () => loadOperatingPilotCapacity(true))' in source
    assert 'operatingPilotWorkClaimsMore.addEventListener("click", () => loadOperatingPilotWorkClaims(true))' in source
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in source
    assert source.count("nextOffset <= 10000") >= 3
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
