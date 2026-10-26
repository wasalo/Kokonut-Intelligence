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


def test_tactical_items_can_be_created_and_edited_under_separate_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="governance-tactical-item-create-form"' in source
    assert 'scope.resource === "governance_tactical" && scope.action === "update"' in source
    assert "governanceTacticalCreateLocations.has(locationId)" in source
    assert "governanceTacticalUpdateLocations.has(locationId)" in source
    assert '`/operator/api/governance/${encodeURIComponent(governanceTacticalLocation.value)}/tactical-items`' in source
    assert "/tactical-sessions/${encodeURIComponent(session.id)}" in source
    assert "/tactical-items/${encodeURIComponent(item.id)}" in source
    assert 'method: "PATCH"' in source
    assert 'session.status === "planned"' in source
    assert 'item.status === "open"' in source
    assert "attachTacticalMutationForm" in source
    assert 'cache: "no-store"' in source
    assert '"X-CSRF-Token": csrf' in source
    assert "retry unchanged to reuse request" in source
    assert 'id="governance-tactical-item-create-status"' in source
    for field in ("tension", "work", "decision"):
        assert f'id="governance-tactical-item-{field}"' in source
    assert 'if (value) content[field] = value;' in source
    assert 'else if (editor.clear.checked) content[field] = null;' in source
    assert 'session.status !== "cancelled"' in source
    assert '"facilitator_role_id"' in source
    assert '"recorder_role_id"' in source
    assert 'session_type: typeField.value' in source
    assert 'agenda_scope = agendaField.value.trim()' in source
    assert 'Clear current agenda scope' in source
