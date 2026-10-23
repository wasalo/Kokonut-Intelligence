"""Console contract for location-scoped human review of AI summaries."""

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


def test_panel_is_hidden_until_exact_review_scope_and_states_lifecycle_boundary():
    source = CONSOLE.read_text(encoding="utf-8")
    panel_match = re.search(r'<section id="ai-summary-review".*?</section>', source, re.DOTALL)
    assert panel_match is not None
    panel = panel_match.group()
    assert 'scope.resource === "ai_summary" && scope.action === "review"' in source
    assert "aiSummaryReviewLocations.has(locationId)" in source
    assert "Approval moves a summary to verified" in panel
    assert "publication remains separate" in panel
    assert "New Gateway drafts record the requesting operator" in panel
    assert "Legacy drafts without reliable requester attribution cannot be approved" in panel
    assert "counts are exact" in panel
    assert "capped at 50 displayed IDs" in panel
    assert "innerHTML" not in panel


def test_queue_uses_bounded_same_origin_no_store_reads_and_safe_text_rendering():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadAiSummaryReviewQueue(append = false)",
        "async function submitAiSummaryReviewDecision(",
    )
    assert "aiSummaryReviewLocations.has(locationId)" in reader
    assert '`/operator/api/ai-summaries/${encodeURIComponent(locationId)}/reviews?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(aiSummaryReviewOffset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "content.textContent = String(summary.content || \"\")" in reader
    assert "item.textContent = blocker" in reader
    assert "summary.source_references" in reader
    assert 'summary.creator_task_key === "unregistered_worker"' in reader
    assert "Agent task: ${summary.creator_task_key}" in reader
    assert 'typeof summary.creator_run_id === "string"' in reader
    assert "Agent run: ${summary.creator_run_id}" in reader
    assert "recordIds.length" in reader
    assert "item.textContent = recordId" in reader
    assert "summary.review_ready === true && blockers.length === 0" in reader
    assert "summary.content_truncated !== true" in reader
    assert "innerHTML" not in reader


def test_decision_requires_csrf_and_preserves_stable_retry_id():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitAiSummaryReviewDecision(",
        "async function loadGovernanceTensionQueue(",
    )
    assert 'summary.review_ready !== true' in submitter
    assert 'summary.content_truncated === true' in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'method: "POST"' in submitter
    assert "aiSummaryReviewRequestIds.get(requestKey)" in submitter
    assert "aiSummaryReviewRequestIds.set(requestKey, requestId)" in submitter
    assert "aiSummaryReviewRequestIds.delete(requestKey)" in submitter
    assert "result.resulting_status === \"verified\"" in submitter
    assert '"insufficient_evidence"' in source
    assert '"privacy_concern"' in source
    assert '"unsupported_claim"' in source
    assert '"other"' in source


def test_controls_have_unique_ids_and_queue_events_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "ai-summary-review",
        "ai-summary-review-location",
        "ai-summary-review-refresh",
        "ai-summary-review-status",
        "ai-summary-review-rows",
        "ai-summary-review-more",
    ):
        assert f'id="{element_id}"' in source
    assert 'aiSummaryReviewLocation.addEventListener("change", () => loadAiSummaryReviewQueue())' in source
    assert 'aiSummaryReviewMore.addEventListener("click", () => loadAiSummaryReviewQueue(true))' in source


def test_draft_panel_requires_exact_draft_scope_and_explains_independent_review():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'scope.resource === "ai_summary" && scope.action === "draft"' in source
    assert 'aiSummaryDraftLocations.has(locationId)' in source
    assert 'id="ai-summary-draft-create" hidden' in source
    assert "records you as the requester" in source
    assert "another operator must review it" in source
    assert "never publishes" in source


def test_draft_submission_uses_csrf_no_store_stable_retry_id_and_safe_rendering():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitAiSummaryDraft()",
        "async function loadGovernanceTensionQueue(",
    )
    assert 'aiSummaryDraftLocations.has(locationId)' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert 'cache: "no-store"' in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert "aiSummaryDraftRequestIds.get(requestKey)" in submitter
    assert "aiSummaryDraftRequestIds.set(requestKey, requestId)" in submitter
    assert "aiSummaryDraftRequestIds.delete(requestKey)" in submitter
    assert "aiSummaryDraftContent.textContent" in submitter
    assert "aiSummaryDraftSources.textContent" in submitter
    assert "innerHTML" not in submitter
    assert 'aiSummaryDraftSubmit.addEventListener("click", submitAiSummaryDraft)' in source


def test_self_review_disables_both_decision_controls_and_legacy_can_only_be_rejected():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadAiSummaryReviewQueue(append = false)",
        "async function submitAiSummaryReviewDecision(",
    )
    assert 'approve.disabled = !ready' in reader
    assert 'reject.disabled = blockers.includes("self_review")' in reader


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
