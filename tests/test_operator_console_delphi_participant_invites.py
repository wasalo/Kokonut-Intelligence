"""Grant, secret-handling, and browser contracts for Delphi invite operations."""

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_invite_console_requires_same_location_read_and_invite_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="delphi-participant-invites".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'scope.resource === "delphi" && scope.action === "read"' in source
    assert 'scope.resource === "delphi" && scope.action === "invite"' in source
    assert 'scope.resource === "delphi" && scope.action === "invite_revoke"' in source
    assert "delphiInviteGrantLocationIds" in source
    assert "delphiReadLocationIds.has(locationId)" in source
    assert "delphiParticipantInviteRevokeLocations" in source
    assert "this panel does not send email" in panel.group()


def test_issue_is_confirmed_csrf_protected_no_store_and_shows_secret_once():
    source = CONSOLE.read_text(encoding="utf-8")
    issue = _function(
        source,
        "async function submitDelphiParticipantInvite()",
        "async function submitDelphiParticipantInviteRevoke(",
    )
    assert 'selectedStudy?.dataset?.status !== "draft"' in issue
    assert "window.confirm(" in issue
    assert 'method: "POST"' in issue
    assert 'cache: "no-store"' in issue
    assert 'credentials: "same-origin"' in issue
    assert '"X-CSRF-Token": csrf' in issue
    assert "globalThis.crypto?.randomUUID?.()" in issue
    assert 'delphiParticipantInviteIssueRequestIds.delete(requestKey)' in issue
    assert "result.replayed" in issue
    assert 'window.location.origin}/api/participation/delphi#${result.invite_token}' in issue
    assert "sessionStorage" not in issue and "localStorage" not in issue
    assert "token cannot be retrieved again" in issue


def test_invite_queue_is_bounded_and_never_renders_private_tokens_as_markup():
    source = CONSOLE.read_text(encoding="utf-8")
    loader = _function(
        source,
        "async function loadDelphiParticipantInviteQueue(append = false)",
        "async function submitDelphiParticipantInvite()",
    )
    assert 'limit: "50"' in loader
    assert "delphiParticipantInviteOffset" in loader
    assert 'cache: "no-store"' in loader
    assert 'credentials: "same-origin"' in loader
    assert "result.location_id !== locationId" in loader
    assert "result.study_id !== studyId" in loader
    assert "textContent" in loader
    assert "innerHTML" not in loader
    assert "invite_token" not in loader and "token_digest" not in loader


def test_revoke_has_independent_grant_confirmation_reason_allowlist_and_retry_id():
    source = CONSOLE.read_text(encoding="utf-8")
    revoke = _function(
        source,
        "async function submitDelphiParticipantInviteRevoke(",
        "function refreshDelphiStudyItemControls()",
    )
    assert "delphiParticipantInviteRevokeLocations.has(locationId)" in revoke
    assert '"sent_to_wrong_recipient"' in revoke
    assert '"token_exposed"' in revoke
    assert "window.confirm(" in revoke
    assert '"X-CSRF-Token": csrf' in revoke
    assert "delphiParticipantInviteRevokeRequestIds.get(requestKey)" in revoke
    assert "delphiParticipantInviteRevokeRequestIds.set(requestKey, requestId)" in revoke
    assert "delphiParticipantInviteRevokeRequestIds.delete(requestKey)" in revoke
    assert 'cache: "no-store"' in revoke


def test_invite_controls_have_unique_ids_and_inline_javascript_parses(tmp_path):
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-participant-invites",
        "delphi-participant-invites-location",
        "delphi-participant-invites-study",
        "delphi-participant-invites-issue",
        "delphi-participant-invites-link-value",
        "delphi-participant-invites-rows",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiParticipantInviteIssue.addEventListener("click", submitDelphiParticipantInvite)' in source
    node = shutil.which("node")
    if node is None:
        return
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    script = tmp_path / "operator-console.js"
    script.write_text(scripts[0], encoding="utf-8")
    subprocess.run([node, "--check", str(script)], check=True, capture_output=True, text=True)
