"""Operator-console contracts for authoring and reviewing Delphi notices."""

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


def test_notice_draft_requires_same_location_read_and_consent_draft_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'scope.resource === "delphi" && scope.action === "consent_draft"' in source
    assert 'scope.resource === "delphi" && scope.action === "read"' in source
    assert "delphiReadLocationIds.has(locationId)" in source
    assert "delphiConsentNoticeDraftLocations" in source
    assert "selected?.dataset?.status !== \"draft\"" in source
    assert "1 to 12,000 characters" not in source
    assert 'maxlength="12000"' in source
    assert "immutable after submission" in source
    assert 'id="delphi-consent-notice-scope-questionnaire"' in source
    assert 'id="delphi-consent-notice-scope-minority"' in source
    assert "questionnaire_responses" in source and "minority_reports" in source


def test_notice_draft_is_csrf_protected_no_store_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitDelphiConsentNoticeDraft()",
        "async function loadDelphiConsentNoticeReviewQueue(",
    )
    assert "window.confirm(" in submit
    assert 'method: "POST"' in submit
    assert 'cache: "no-store"' in submit
    assert 'credentials: "same-origin"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "delphiConsentNoticeDraftRequestIds.get(requestKey)" in submit
    assert "delphiConsentNoticeDraftRequestIds.set(requestKey, requestId)" in submit
    assert "delphiConsentNoticeDraftRequestIds.delete(requestKey)" in submit
    assert 'delphiConsentNoticeDraftVersion.value = ""' in submit
    assert 'delphiConsentNoticeDraftText.value = ""' in submit
    assert "collection_scopes: collectionScopes" in submit
    assert 'collectionScopes.includes("questionnaire_responses")' in submit
    assert 'result.status !== "submitted"' in submit
    assert "will not issue invites or open the study" in submit


def test_notice_review_is_bounded_and_renders_text_without_self_review():
    source = CONSOLE.read_text(encoding="utf-8")
    loader = _function(
        source,
        "async function loadDelphiConsentNoticeReviewQueue(append = false)",
        "async function submitDelphiConsentNoticeDecision(",
    )
    assert 'limit: "50"' in loader
    assert "delphiConsentNoticeReviewOffset" in loader
    assert 'cache: "no-store"' in loader
    assert 'credentials: "same-origin"' in loader
    assert "notice.review_ready !== true" in loader
    assert "authors cannot review their own notice" in loader
    assert "textContent" in loader
    assert "innerHTML" not in loader
    assert "notice.collection_scopes" in loader
    assert "Submit a scoped replacement" in loader


def test_notice_decision_requires_independence_allowlists_csrf_and_stable_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    decision = _function(
        source,
        "async function submitDelphiConsentNoticeDecision(",
        "function clearDelphiParticipantInviteLink()",
    )
    assert "notice.review_ready !== true" in decision
    assert '"approve", "reject"' in decision
    assert '"approved_after_independent_review"' in decision
    assert '"privacy_scope_incomplete", "purpose_unclear", "withdrawal_terms_incomplete", "other"' in decision
    assert "window.confirm(" in decision
    assert '"X-CSRF-Token": csrf' in decision
    assert 'cache: "no-store"' in decision
    assert "delphiConsentNoticeDecisionRequestIds.get(requestKey)" in decision
    assert "delphiConsentNoticeDecisionRequestIds.set(requestKey, requestId)" in decision
    assert "delphiConsentNoticeDecisionRequestIds.delete(requestKey)" in decision
    assert "does not open the study or issue an invite" in decision


def test_notice_controls_have_unique_ids_and_inline_javascript_parses(tmp_path):
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-consent-notice-draft",
        "delphi-consent-notice-draft-location",
        "delphi-consent-notice-draft-study",
        "delphi-consent-notice-draft-version",
        "delphi-consent-notice-draft-text",
        "delphi-consent-notice-scope-questionnaire",
        "delphi-consent-notice-scope-minority",
        "delphi-consent-notice-review",
        "delphi-consent-notice-review-location",
        "delphi-consent-notice-review-rows",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiConsentNoticeDraftSubmit.addEventListener("click", submitDelphiConsentNoticeDraft)' in source
    assert 'delphiConsentNoticeReviewRefresh.addEventListener("click", () => loadDelphiConsentNoticeReviewQueue())' in source
    node = shutil.which("node")
    if node is None:
        return
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    script = tmp_path / "operator-console.js"
    script.write_text(scripts[0], encoding="utf-8")
    subprocess.run([node, "--check", str(script)], check=True, capture_output=True, text=True)
