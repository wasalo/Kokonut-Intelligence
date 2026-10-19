"""Operator console schedules sessions only with the exact tactical create grant."""

import re
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def test_tactical_session_form_is_draft_safe_and_explicitly_scoped():
    source = CONSOLE.read_text(encoding="utf-8")
    form = re.search(
        r'<form id="governance-tactical-session-create-form".*?</form>',
        source,
        re.DOTALL,
    )
    assert form is not None
    assert 'name="circle_id"' in form.group()
    assert 'name="session_type"' in form.group()
    assert 'name="title"' in form.group()
    assert 'name="reason"' in form.group()
    assert 'name="notes"' not in form.group()
    assert 'name="outcome_summary"' not in form.group()
    assert 'name="status"' not in form.group()
    assert "A session is created as planned." in source
    assert 'scope.resource === "governance_tactical" && scope.action === "create"' in source
    assert "governanceTacticalCreateLocations.has(locationId)" in source


def test_create_uses_csrf_no_store_and_reuses_request_id_for_unchanged_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    start = source.index("async function createGovernanceTacticalSession(event)")
    end = source.index("async function loadGovernanceTacticalItems", start)
    create_handler = source[start:end]
    assert "csrfToken()" in create_handler
    assert '"X-CSRF-Token": csrf' in create_handler
    assert 'method: "POST"' in create_handler
    assert 'cache: "no-store"' in create_handler
    assert '`/operator/api/governance/${encodeURIComponent(locationId)}/tactical-sessions`' in create_handler
    assert "pendingGovernanceTacticalSessionRequest.requestId" in create_handler
    assert "pendingGovernanceTacticalSessionRequest.content !== normalizedContent" in create_handler
    assert 'pendingGovernanceTacticalSessionRequest = null' in create_handler
    assert "governanceTacticalSessionCreateForm.reset()" in create_handler
    assert "innerHTML" not in create_handler


def test_console_ids_are_unique_and_creation_form_is_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "governance-tactical-session-create-form",
        "governance-tactical-session-circle",
        "governance-tactical-session-type",
        "governance-tactical-session-title",
        "governance-tactical-session-scheduled",
        "governance-tactical-session-agenda",
        "governance-tactical-session-reason",
        "governance-tactical-session-create-status",
    ):
        assert f'id="{element_id}"' in source
    assert 'governanceTacticalSessionCreateForm.addEventListener("submit", createGovernanceTacticalSession)' in source
    assert 'governanceTacticalSessionCreateForm.hidden = !governanceTacticalCreateLocations.has(governanceTacticalLocation.value)' in source
