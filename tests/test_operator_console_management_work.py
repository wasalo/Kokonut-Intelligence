"""Console contract for the read-only CAP-030 management summary."""

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


def test_management_panel_requires_exact_scoped_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="management-work-summary".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only counts for work items, urgency, due dates, claims, escalations" in panel.group()
    assert 'scope.resource === "management_workflow" && scope.action === "read"' in source
    assert "managementWorkLocations = new Set(managementWorkLocationIds)" in source
    assert "managementWorkSummary.hidden = false" in source


def test_summary_reader_uses_protected_no_store_route_and_discards_stale_responses():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadManagementWorkSummary()", "async function loadSession()")
    assert '`/operator/api/management/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "managementWorkLocations.has(locationId)" in reader
    assert "requestVersion !== managementWorkRequestVersion" in reader
    assert "locationId !== managementWorkLocation.value" in reader
    assert "innerHTML" not in reader


def test_renderer_uses_fixed_aggregate_allowlist_only():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderManagementWorkSummary(summary)", "async function loadManagementWorkSummary()")
    for field in (
        "work_item_count", "open_work_item_count", "draft_count", "assigned_count",
        "in_progress_count", "blocked_count", "done_count", "cancelled_count",
        "high_priority_open_count", "critical_priority_open_count", "overdue_count",
        "sla_breached_count", "pending_claim_count", "accepted_claim_count",
        "open_escalation_count", "resolved_escalation_count", "latest_work_event_at",
    ):
        assert f'["{field}"' in renderer
    assert "Object.entries" not in renderer
    assert "textContent" in renderer
    for private_field in (
        "task_title", "description", "assignee", "claimant", "estimated_effort",
        "skill_requirements", "notes", "escalation_reason", "work_item_id",
    ):
        assert private_field not in renderer


def test_refresh_and_location_controls_are_wired_with_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'managementWorkLocation.addEventListener("change", loadManagementWorkSummary)' in source
    assert 'document.querySelector("#management-work-refresh").addEventListener("click", loadManagementWorkSummary)' in source
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
