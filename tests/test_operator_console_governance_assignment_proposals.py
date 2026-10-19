"""Console contract for CAP-024 proposal-only governance nominations."""

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


def test_nomination_panel_is_exact_grant_gated_and_proposal_only():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'scope.resource === "governance_roles" && scope.action === "create"' in source
    assert "governanceRoleReadLocations.has(locationId)" in source
    assert "governanceRoleCreateLocations.has(locationId)" in source
    assert 'id="governance-role-proposal-create" hidden' in source
    assert "remains proposed until a separate human review" in source
    assert "cannot activate or approve an assignment" in source
    assert "proposal.party_id" not in source
    assert "proposal.mandate" not in source


def test_nomination_submit_uses_csrf_and_proposal_only_gateway_route():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitGovernanceRoleProposal(event)",
        "async function loadGovernanceTacticalItems(append = false)",
    )
    assert "event.preventDefault()" in submit
    assert "globalThis.crypto?.randomUUID?.()" in submit
    assert "governanceRoleCreateLocations.has(locationId)" in submit
    assert '`/operator/api/governance/${encodeURIComponent(locationId)}/roles/${encodeURIComponent(roleId)}/assignments`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "assignment_type: assignmentType" in submit
    assert "It still requires separate human review." in submit
    assert "innerHTML" not in submit


def test_own_nomination_history_uses_bounded_private_readback_and_keyset_cursor():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadGovernanceAssignmentProposalHistory(append = false)",
        "async function submitGovernanceRoleProposal(event)",
    )
    assert 'governanceRoleReadLocations.has(locationId)' in reader
    assert 'limit: "50"' in reader
    assert '`/operator/api/governance/${encodeURIComponent(locationId)}/assignment-proposals?${params}`' in reader
    assert 'params.set("cursor_created_at", governanceRoleProposalNextCursor.created_at)' in reader
    assert 'params.set("cursor_assignment_id", governanceRoleProposalNextCursor.assignment_id)' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "proposal.request_id" in reader
    assert "proposal.status" in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader


def test_nomination_controls_are_present_and_event_handlers_are_registered():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "governance-role-proposal-form",
        "governance-role-proposal-party",
        "governance-role-proposal-type",
        "governance-role-proposal-mandate",
        "governance-role-proposal-refresh",
        "governance-role-proposal-history-rows",
        "governance-role-proposal-more",
    ):
        assert f'id="{element_id}"' in source
    assert 'governanceRoleProposalForm.addEventListener("submit", submitGovernanceRoleProposal)' in source
    assert 'governanceRoleProposalMore.addEventListener(' in source


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
