"""Console contract for CAP-025 location-scoped identity review."""

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


def test_review_panel_is_gated_by_the_exact_location_review_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="stakeholder-identity-review".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "append-only" in panel.group()
    assert "source identifiers and raw feedback" in panel.group()
    assert 'scope.resource === "stakeholder_identity" && scope.action === "review"' in source
    assert "stakeholderIdentityReview.hidden = false" in source
    assert "stakeholderIdentityReviewLocations = new Set(stakeholderIdentityReviewLocationIds)" in source


def test_queue_reader_is_location_scoped_no_store_stale_guarded_and_keyset_paged():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadStakeholderIdentityReviewCases(",
        "async function decideStakeholderIdentityCase(",
    )
    assert '`/operator/api/stakeholder-identity/${encodeURIComponent(locationId)}/cases?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50" })' in reader
    assert 'params.set("cursor_created_at", stakeholderIdentityReviewNextCursor.created_at)' in reader
    assert 'params.set("cursor_case_id", stakeholderIdentityReviewNextCursor.case_id)' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "stakeholderIdentityReviewLocations.has(locationId)" in reader
    assert "requestVersion !== stakeholderIdentityReviewRequestVersion" in reader
    assert "locationId !== stakeholderIdentityReviewLocation.value" in reader


def test_case_renderer_uses_only_consent_filtered_fields_and_disables_withheld_identity():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendStakeholderIdentityReviewCase(",
        "async function loadStakeholderIdentityReviewCases(",
    )
    for field in (
        "source_label", "candidate_name", "match_method", "evidence_code", "confidence", "created_at",
    ):
        assert f"identityCase.{field}" in renderer
    assert "identityCase.candidate_party_id" in renderer  # used only to fail closed on withheld identity
    assert "identityCase.source_farmer_profile_id" not in renderer
    assert "identityCase.reviewer_operator_id" not in renderer
    assert "identityCase.raw_feedback" not in renderer
    assert 'description.textContent' in renderer
    assert "Decision controls are disabled" in renderer
    assert "innerHTML" not in renderer


def test_decisions_use_allowlisted_reason_codes_csrf_confirmation_and_stable_retry_id():
    source = CONSOLE.read_text(encoding="utf-8")
    decision = _function(source, "async function decideStakeholderIdentityCase(", "async function loadSession()")
    assert 'window.confirm(' in decision
    assert 'const csrf = csrfToken()' in decision
    assert '"X-CSRF-Token": csrf' in decision
    assert 'method: "POST"' in decision
    assert '"match_confirmed"' in decision
    assert '"insufficient_evidence", "conflicting_identity", "source_not_eligible"' in decision
    assert 'request_id: pending.request_id' in decision
    assert 'stakeholderIdentityPendingDecisions.set(identityCase.case_id, pending)' in decision
    assert 'stakeholderIdentityPendingDecisions.delete(identityCase.case_id)' in decision
    assert "retry the same choice" in decision.lower()
    assert "innerHTML" not in decision


def test_review_controls_are_wired_and_document_ids_are_unique():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'document.querySelector("#stakeholder-identity-review-refresh").addEventListener("click", () => loadStakeholderIdentityReviewCases())' in source
    assert 'stakeholderIdentityReviewLocation.addEventListener("change", () => loadStakeholderIdentityReviewCases())' in source
    assert 'stakeholderIdentityReviewMore.addEventListener("click", () => loadStakeholderIdentityReviewCases(true))' in source
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
