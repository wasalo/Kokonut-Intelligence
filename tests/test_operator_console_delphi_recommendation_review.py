"""Console contract for location-scoped Delphi recommendation review."""

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


def test_review_panel_is_gated_by_exact_location_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel_match = re.search(
        r'<section id="delphi-recommendation-review".*?</section>',
        source,
        re.DOTALL,
    )
    assert panel_match is not None
    panel = panel_match.group()
    assert 'scope.resource === "delphi" && scope.action === "review"' in source
    assert "delphiRecommendationReviewLocations.has(locationId)" in source
    assert "Approval requires a separate reviewer" in panel
    assert "does not publish the recommendation" in panel
    assert "innerHTML" not in panel


def test_queue_uses_scoped_private_no_store_reads_and_exposes_blockers():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadDelphiRecommendationReviewQueue(append = false)",
        "async function submitDelphiRecommendationDecision(",
    )
    assert "delphiRecommendationReviewLocations.has(locationId)" in reader
    assert '`/operator/api/delphi/${encodeURIComponent(locationId)}/recommendations?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(delphiRecommendationReviewOffset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert 'const readyForApproval = recommendation.review_ready === true && blockers.length === 0;' in reader
    assert 'readiness.textContent = readyForApproval ? "Ready for approval" : "Approval blocked";' in reader
    assert 'blockers.includes("self_review")' in reader
    assert "draftText.textContent" in reader
    assert "innerHTML" not in reader


def test_decisions_keep_csrf_reason_code_and_retry_boundaries():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiRecommendationDecision(",
        "async function loadGovernanceTensionQueue(",
    )
    assert 'recommendation.review_ready !== true' in submitter
    assert "recommendation.blocked_reasons.length > 0" in submitter
    assert 'recommendation.blocked_reasons.includes("self_review")' in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'method: "POST"' in submitter
    assert 'JSON.stringify({ decision, request_id: requestId, reason_code: reasonCode })' in submitter
    assert "delphiRecommendationRequestIds.get(requestKey)" in submitter
    assert "delphiRecommendationRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiRecommendationRequestIds.delete(requestKey)" in submitter
    for reason_code in (
        "approved_after_review",
        "insufficient_evidence",
        "privacy_concern",
        "minority_report_open",
        "other",
    ):
        assert f'"{reason_code}"' in source


def test_review_controls_have_unique_ids_and_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-recommendation-review",
        "delphi-recommendation-review-location",
        "delphi-recommendation-review-refresh",
        "delphi-recommendation-review-status",
        "delphi-recommendation-review-rows",
        "delphi-recommendation-review-more",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiRecommendationReviewLocation.addEventListener("change", () => loadDelphiRecommendationReviewQueue())' in source
    assert 'delphiRecommendationReviewMore.addEventListener("click", () => loadDelphiRecommendationReviewQueue(true))' in source


def test_minority_report_review_is_scoped_private_and_consent_aware():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadDelphiMinorityReviewQueue(append = false)",
        "async function submitDelphiMinorityDecision(",
    )
    submitter = _function(
        source,
        "async function submitDelphiMinorityDecision(",
        "async function submitDelphiStudyDraft()",
    )
    assert "delphiMinorityReviewLocations.has(locationId)" in reader
    assert '`/operator/api/delphi/${encodeURIComponent(locationId)}/minority-reports?${params}`' in reader
    assert 'credentials: "same-origin"' in reader and 'cache: "no-store"' in reader
    assert "position.textContent" in reader and "rationale.textContent" in reader
    assert "delphiMinorityReviewLocations.has(locationId)" in submitter
    assert "window.confirm" in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter and 'method: "POST"' in submitter
    assert "delphiMinorityReviewRequestIds.get(requestKey)" in submitter
    assert "delphiMinorityReviewRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiMinorityReviewRequestIds.delete(requestKey)" in submitter
    assert "await loadDelphiRecommendationReviewQueue()" in submitter
    assert "innerHTML" not in reader + submitter
    for reason_code in ("evidence_considered", "out_of_scope", "privacy_concern", "insufficient_evidence", "other"):
        assert f'"{reason_code}"' in source


def test_minority_review_controls_and_privacy_copy_are_present():
    source = CONSOLE.read_text(encoding="utf-8")
    for element_id in (
        "delphi-minority-review",
        "delphi-minority-review-location",
        "delphi-minority-review-refresh",
        "delphi-minority-review-status",
        "delphi-minority-review-rows",
        "delphi-minority-review-more",
    ):
        assert f'id="{element_id}"' in source
    assert "Withdrawn or unlinked reports remain private pending human disposition" in source
    assert 'delphiMinorityReviewLocation.addEventListener("change", () => loadDelphiMinorityReviewQueue())' in source
    assert 'delphiMinorityReviewMore.addEventListener("click", () => loadDelphiMinorityReviewQueue(true))' in source


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
