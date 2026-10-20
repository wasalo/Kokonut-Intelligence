"""Console contract for the read-only CAP-035 lifecycle summary."""

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


def test_solution_lifecycle_panel_requires_exact_scoped_read_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only aggregate lifecycle counts" in panel.group()
    assert 'scope.resource === "solution_lifecycle" && scope.action === "read"' in source
    assert "solutionLifecycleLocations = new Set(solutionLifecycleReadLocationIds)" in source
    assert 'solutionLifecycle.hidden = false' in source
    assert "No lifecycle state was changed" in source


def test_summary_uses_same_origin_no_store_route_and_discards_stale_location_responses():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleSummary()", "async function loadSession()")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleSummaryRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "innerHTML" not in reader


def test_gate_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleGates(", "function createSolutionLifecycleGateReviewPanel(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleGatesRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_gate_panel_displays_only_fixed_non_mutating_status_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<h3>Location-linked stage gates</h3>(.*?)</section>', source, re.DOTALL)
    assert panel is not None
    assert "does not approve a transition" in panel.group(1)
    renderer = _function(source, "function appendSolutionLifecycleGate(", "async function loadSolutionLifecycleGates(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "from_stage", "to_stage",
        "required_evidence_maturity", "required_experiment_count", "requires_human_approval",
        "gate_status", "gate_created_at", "latest_evaluation_passed", "latest_evaluated_at",
    ):
        assert f"gate.{field}" in renderer
    assert "gate.solution_id" not in renderer
    assert "gate.evidence" not in renderer
    assert "gate.reviewer" not in renderer
    assert "gate.raw" not in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_gate_evaluation_form_requires_create_scope_and_preserves_exact_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendSolutionLifecycleGate(", "async function loadSolutionLifecycleGates(")
    form = _function(source, "function createSolutionLifecycleGateEvaluationForm(", "async function loadSolutionLifecycleGates(")
    assert 'solutionLifecycleCreateLocations.has(solutionLifecycleLocation.value)' in renderer
    assert '["draft", "ready"].includes(gate.gate_status)' in renderer
    assert "createSolutionLifecycleGateEvaluationForm(gate.gate_id)" in renderer
    assert "JSON.parse(observed.value)" in form and "JSON.parse(evidence.value)" in form
    assert "Array.isArray(observedValue)" in form
    assert "Array.isArray(evidenceValue)" in form
    assert "form.pendingEvaluation.fingerprint !== fingerprint" in form
    assert "form.pendingEvaluation.request_id" in form
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates/${encodeURIComponent(gateId)}/evaluations`' in form
    assert 'method: "POST"' in form and 'cache: "no-store"' in form
    assert '"X-CSRF-Token": csrf' in form
    assert "does not approve" in source or "Gate approval remains a separate human review." in form
    assert "innerHTML" not in form


def test_gate_evidence_and_approval_require_review_grant_and_remain_separate():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendSolutionLifecycleGate(", "async function loadSolutionLifecycleGates(")
    review = _function(source, "function createSolutionLifecycleGateReviewPanel(", "function appendSolutionLifecycleExperiment(")
    assert 'solutionLifecycleReviewLocations.has(solutionLifecycleLocation.value)' in renderer
    assert 'gate.requires_human_approval === true' in renderer
    assert "gate.latest_evaluation_passed === true" in renderer
    assert "createSolutionLifecycleGateReviewPanel(" in renderer
    assert "gate.gate_id," in renderer
    assert "solutionLifecycleReviewLocations.has(locationId)" in review
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates/${encodeURIComponent(gateId)}/review`' in review
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates/${encodeURIComponent(gateId)}/approve`' in review
    assert 'credentials: "same-origin"' in review and 'cache: "no-store"' in review
    assert 'method: "POST"' in review and '"X-CSRF-Token": csrf' in review
    assert "approval.pendingRequestId" in review
    assert "acknowledge.checked" in review
    assert "different active person from the evaluator" in review
    assert "This gate does not require a second reviewer" in review
    assert 'const requiresIndependentReview = result.requires_human_approval === true' in review
    assert 'approve.textContent = requiresIndependentReview' in review
    assert "The solution stage remains unchanged" in review
    assert "result.evaluated_by_party_id" not in review
    assert "innerHTML" not in review


def test_gate_transition_requires_approved_passing_gate_and_exact_transition_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendSolutionLifecycleGate(", "async function loadSolutionLifecycleGates(")
    form = _function(source, "function createSolutionLifecycleGateTransitionForm(", "async function loadSolutionLifecycleGates(")
    assert "solutionLifecycleTransitionLocations.has(solutionLifecycleLocation.value)" in renderer
    assert 'gate.gate_status === "approved"' in renderer
    assert "gate.latest_evaluation_passed === true" in renderer
    assert '["validated", "funded", "adoption_ready", "scaled"].includes(gate.to_stage)' in renderer
    assert "createSolutionLifecycleGateTransitionForm(gate.gate_id, gate.to_stage)" in renderer
    assert 'scope.resource === "solution_lifecycle" && scope.action === "transition"' in source
    assert 'solutionLifecycleTransitionLocations = new Set' in source
    assert "Evidence references must be valid JSON." in form
    assert "form.pendingTransition?.fingerprint !== fingerprint" in form
    assert "form.pendingTransition.request_id" in form
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/gates/${encodeURIComponent(gateId)}/transition`' in form
    assert 'method: "POST"' in form and 'cache: "no-store"' in form
    assert 'credentials: "same-origin"' in form
    assert '"X-CSRF-Token": csrf' in form
    assert "loadSolutionLifecycleGates(), loadSolutionLifecycleSummary()" in form
    assert "innerHTML" not in form


def test_experiment_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleExperiments(", "function appendSolutionLifecycleFundingCase(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/experiments?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleExperimentsRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "result.next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_experiment_renderer_limits_result_visibility_to_reviewed_enum_and_metadata():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<h3>Experiments and reviewed outcomes</h3>(.*?)</section>', source, re.DOTALL)
    assert panel is not None
    assert "only an explicitly reviewed outcome" in panel.group(1)
    renderer = _function(source, "function appendSolutionLifecycleExperiment(", "async function loadSolutionLifecycleExperiments(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "protocol_version",
        "experiment_status", "duration_days", "primary_metric_count", "secondary_metric_count",
        "experiment_created_at", "experiment_updated_at", "started_at", "completed_at",
        "latest_result_outcome", "latest_result_reviewed_at",
    ):
        assert f"experiment.{field}" in renderer
    assert "experiment.latest_result_reviewed_at" in renderer
    for private_field in ("solution_id", "hypothesis", "metric_key", "primary_results", "adverse_events", "evidence"):
        assert f"experiment.{private_field}" not in renderer
    assert "heading.textContent = experiment.experiment_id" not in renderer
    assert "No reviewed result" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_experiment_result_review_form_is_exact_grant_and_pending_state_gated():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleExperiment(",
        "function createSolutionLifecycleExperimentReviewPanel(",
    )
    assert "solutionLifecycleReviewLocations.has(solutionLifecycleLocation.value)" in renderer
    assert 'experiment.experiment_status === "completed"' in renderer
    assert "!experiment.latest_result_reviewed_at" in renderer
    assert "createSolutionLifecycleExperimentReviewPanel(experiment.experiment_id)" in renderer


def test_experiment_result_review_uses_private_text_detail_csrf_and_stable_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    review = _function(
        source,
        "function createSolutionLifecycleExperimentReviewPanel(",
        "async function loadSolutionLifecycleExperiments(",
    )
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/experiments/${encodeURIComponent(experimentId)}/review`' in review
    assert 'credentials: "same-origin"' in review and 'cache: "no-store"' in review
    assert "result.protocol || {}" in review and "result.latest_analysis || {}" in review
    assert "result.observations || []" in review
    assert "protocol.textContent = JSON.stringify" in review
    assert "analysis.textContent = JSON.stringify" in review
    assert "observations.textContent = JSON.stringify" in review
    assert "innerHTML" not in review
    assert 'method: "POST"' in review
    assert '"X-CSRF-Token": csrf' in review
    assert "acknowledgement.checked" in review
    assert "form.pendingExperimentReview.fingerprint !== fingerprint" in review
    assert "form.pendingExperimentReview.request_id" in review
    assert "does not advance the solution stage" in review


def test_funding_draft_form_is_create_grant_gated_and_excludes_approval_actions():
    source = CONSOLE.read_text(encoding="utf-8")
    html = source.split('<section id="solution-lifecycle-funding-proposal"', 1)[1].split("</section>", 1)[0]
    assert 'id="solution-lifecycle-funding-proposal" hidden' in source
    assert "This creates a private draft and optional proposed tranches only" in html
    assert "does not submit, approve, release funds, or advance the solution stage" in html
    for field in (
        "solution-lifecycle-funding-amount",
        "solution-lifecycle-funding-rationale",
        "solution-lifecycle-funding-evidence",
        "solution-lifecycle-funding-tranches",
        "solution-lifecycle-funding-acknowledgement",
    ):
        assert f'id="{field}"' in html
    assert "Approve funding" not in html and "Release tranche" not in html


def test_funding_targets_and_draft_submit_use_location_scope_csrf_and_stable_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    targets = _function(
        source,
        "async function loadSolutionLifecycleFundingTargets(",
        "async function submitSolutionLifecycleFundingProposal(",
    )
    submit = _function(
        source,
        "async function submitSolutionLifecycleFundingProposal(",
        "async function submitSolutionLifecycleFundingDraft(",
    )
    assert "/funding/targets?${params}" in targets
    assert 'credentials: "same-origin"' in targets and 'cache: "no-store"' in targets
    assert "solution.solution_id" in targets and "option.textContent" in targets
    assert "locationId !== solutionLifecycleLocation.value" in targets
    assert "solutionLifecycleCreateLocations.has(locationId)" in submit
    assert 'method: "POST"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "solutionLifecyclePendingFundingProposal.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingFundingProposal.request_id" in submit
    assert 'cache: "no-store"' in submit and 'credentials: "same-origin"' in submit
    assert "It has not been submitted or approved." in submit
    assert "innerHTML" not in targets + submit


def test_funding_submission_is_separately_grant_gated_acknowledged_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    html = re.search(
        r'<section id="solution-lifecycle-funding-submission".*?</section>',
        source,
        re.DOTALL,
    )
    assert html is not None
    assert 'id="solution-lifecycle-funding-submission-acknowledgement"' in html.group()
    assert "independent review" in html.group()
    assert "does not approve the request" in html.group()
    submit = _function(
        source,
        "async function submitSolutionLifecycleFundingDraft(",
        "async function loadSolutionLifecycleFunding(",
    )
    assert 'scope.action === "submit"' in source
    assert "solutionLifecycleSubmitLocations.has(pending.locationId)" in submit
    assert "solutionLifecycleFundingSubmissionAcknowledge.checked" in submit
    assert "/funding/${encodeURIComponent(pending.fundingCaseId)}/submit" in submit
    assert "pending.requestId" in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'cache: "no-store"' in submit and 'credentials: "same-origin"' in submit
    assert "No funds were approved or released" in submit
    assert "solutionLifecycleFundingSubmissionForm.addEventListener(\"submit\", submitSolutionLifecycleFundingDraft)" in source
    assert "innerHTML" not in submit


def test_funding_review_inbox_offers_only_independent_case_approval():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="solution-lifecycle-funding-review".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert 'solutionLifecycleFundingReview.hidden = !solutionLifecycleReviewLocations.has(solutionLifecycleLocation.value)' in source
    assert "Submitted request amounts, rationale, evidence, and tranche terms are private" in panel.group()
    assert "independent case decision" in panel.group()
    assert "Proposed tranches remain proposed" in panel.group()
    assert "no funds are released" in panel.group()
    assert 'id="solution-lifecycle-funding-review-approval-acknowledgement"' in panel.group()
    assert 'id="solution-lifecycle-funding-review-approval-submit"' in panel.group()
    assert "Approve tranche" not in panel.group() and "Release funds" not in panel.group()
    assert 'id="solution-lifecycle-funding-review-queue"' in panel.group()
    assert 'id="solution-lifecycle-funding-review-detail"' in panel.group()
    assert 'scope.resource === "solution_lifecycle" && scope.action === "review"' in source


def test_funding_review_reader_and_detail_use_review_scope_no_store_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    queue = _function(
        source,
        "async function loadSolutionLifecycleFundingReviewQueue(",
        "async function loadSolutionLifecycleFundingReviewDetail(",
    )
    detail = _function(
        source,
        "async function loadSolutionLifecycleFundingReviewDetail(",
        "async function approveSolutionLifecycleFundingCase(",
    )
    renderer = _function(
        source,
        "function appendSolutionLifecycleFundingReviewCase(",
        "async function loadSolutionLifecycleFundingReviewQueue(",
    )
    assert "/funding/review?${params}" in queue
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    assert "solutionLifecycleReviewLocations.has(locationId)" in queue
    assert "requestVersion !== solutionLifecycleFundingReviewRequestVersion" in queue
    assert "locationId !== solutionLifecycleLocation.value" in queue
    assert "result.funding_cases" in queue and "result.next_offset" in queue
    assert "/funding/${encodeURIComponent(fundingCaseId)}/review" in detail
    assert 'credentials: "same-origin"' in detail and 'cache: "no-store"' in detail
    assert "solutionLifecycleReviewLocations.has(locationId)" in detail
    assert "requestVersion !== solutionLifecycleFundingReviewDetailVersion" in detail
    assert "locationId !== solutionLifecycleLocation.value" in detail
    for field in ("requested_amount", "rationale", "evidence", "tranches", "submitter_attributed", "is_self_authored"):
        assert f"fundingCase.{field}" in renderer or f"result.{field}" in detail
    assert "textContent" in renderer and "textContent" in detail
    assert "innerHTML" not in queue + detail + renderer
    assert 'method: "POST"' not in queue + detail


def test_funding_case_approval_is_acknowledged_review_granted_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    detail = _function(
        source,
        "async function loadSolutionLifecycleFundingReviewDetail(",
        "async function approveSolutionLifecycleFundingCase(",
    )
    approval = _function(
        source,
        "async function approveSolutionLifecycleFundingCase(",
        "function appendSolutionLifecycleSupplementalRecord(",
    )
    assert 'result.decision_status === "submitted"' in detail
    assert "result.submitter_attributed === true" in detail
    assert "result.is_self_authored === false" in detail
    assert "pending.requestId" in approval
    assert "solutionLifecycleReviewLocations.has(pending.locationId)" in approval
    assert "solutionLifecycleFundingReviewApprovalAcknowledge.checked" in approval
    assert "/funding/${encodeURIComponent(pending.fundingCaseId)}/approve" in approval
    assert '"X-CSRF-Token": csrf' in approval
    assert 'method: "POST"' in approval
    assert 'credentials: "same-origin"' in approval and 'cache: "no-store"' in approval
    assert "no funds were released" in approval
    assert "solutionLifecycleFundingReviewApprovalSubmit.addEventListener(\"click\", approveSolutionLifecycleFundingCase)" in source
    assert "innerHTML" not in detail + approval


def test_funding_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleFunding(", "async function loadSolutionLifecycleFundingTrancheReviewDetail(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/funding?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleFundingRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert 'Array.isArray(result.funding)' in reader
    assert "result.next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_funding_renderer_omits_amounts_terms_evidence_and_party_details():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<h3>Funding and tranche status</h3>(.*?)</section>', source, re.DOTALL)
    assert panel is not None
    assert "amounts, milestone terms, rationale, evidence" in panel.group(1)
    renderer = _function(source, "function appendSolutionLifecycleFundingCase(", "async function loadSolutionLifecycleFundingTargets(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "capital_stage",
        "funding_instrument", "currency", "decision_status", "case_created_at", "case_approved_at",
        "tranche_number", "tranche_status", "tranche_approved_at", "tranche_released_at",
    ):
        assert f"fundingCase.{field}" in renderer
    for private_field in (
        "requested_amount", "authorized_amount", "amount",
        "milestone", "rationale", "evidence", "submitted_by", "approved_by", "party_id",
    ):
        assert f"fundingCase.{private_field}" not in renderer
    assert '["Funding case ID"' not in renderer
    assert '["Tranche ID"' not in renderer
    assert "No tranche recorded" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_supplemental_projection_routes_and_result_keys_are_fixed_allowlists():
    source = CONSOLE.read_text(encoding="utf-8")
    start = source.index("const solutionLifecycleSupplementalViews = Object.freeze({")
    end = source.index("\n      });", start)
    views = source[start:end]
    for route in ("adoption", "scale-gates", "replications", "learning", "retirements"):
        assert f'route: "{route}"' in views
    for response_key in ("programs", "scale_gates", "replications", "learning", "retirements"):
        assert f'responseKey: "{response_key}"' in views
    for option in ("adoption", "scale-gates", "replications", "learning", "retirements"):
        assert f'<option value="{option}">' in source
    for private_field in (
        "adopter_ref", "cohort_id", "evidence", "party_id", "reviewer_id", "target_context",
        "adaptation_required", "learning_text", "recommendation", "trigger_reason", "residual_risk",
    ):
        assert f'"{private_field}"' not in views


def test_supplemental_projection_reader_uses_same_origin_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleProjection(", "function appendScaleGateAssessmentTarget(")
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/${view.route}?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "requestVersion !== solutionLifecycleProjectionRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "viewName !== solutionLifecycleProjection.value" in reader
    assert "result[view.responseKey]" in reader
    assert "result.next_offset" in reader and "result.has_more" in reader
    assert 'method: "POST"' not in reader
    assert "innerHTML" not in reader


def test_supplemental_renderer_uses_fixed_view_fields_and_hides_small_adoption_cohorts():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendSolutionLifecycleSupplementalRecord(", "async function loadSolutionLifecycleProjection(")
    assert "for (const [label, field] of view.fields)" in renderer
    assert "record[field]" in renderer
    assert 'field === "consented_adopter_reference_count"' in renderer
    assert "Withheld below disclosure threshold" in renderer
    assert 'typeof value === "boolean"' in renderer
    assert "record.solution_name" in renderer
    assert "record.party_id" not in renderer
    assert "Object.entries" not in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_adoption_event_detail_uses_only_consent_checked_coarse_suppressed_phase_counts():
    source = CONSOLE.read_text(encoding="utf-8")
    assert "View consented phase summary" in source
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/adoption/${encodeURIComponent(programId)}/events`' in source
    assert 'credentials: "same-origin"' in source
    assert 'cache: "no-store"' in source
    assert "solutionLifecycleLocations.has(locationId)" in source
    assert 'solutionLifecycleProjection.value !== "adoption"' in source
    assert "summary.breakdown_suppressed === true" in source
    assert "Number.isSafeInteger(count)" in source
    for field in (
        "engagement_reference_count", "commitment_reference_count", "use_reference_count",
        "advocacy_reference_count", "paused_or_abandoned_reference_count",
    ):
        assert field in source
    loader = _function(
        source,
        "async function loadSolutionLifecycleAdoptionEventSummary(",
        "async function loadSolutionLifecycleProjection(",
    )
    for private_field in (
        "adopter_ref", "cohort_id", "observed_at", "fidelity_score",
        "support_required", "outcome", "evidence", "recorded_by_party_id",
    ):
        assert f'"{private_field}"' not in loader
    assert "article.isConnected" in loader
    assert "requestVersion !== solutionLifecycleAdoptionEventRequestVersion" in loader
    assert "status.replaceChildren" in loader
    assert "innerHTML" not in loader


def test_learning_proposal_source_loader_requires_both_grants_and_filters_reviewed_completion():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-learning-proposal".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'solutionLifecycleLearningProposal.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)' in source
    assert '|| !solutionLifecycleCreateLocations.has(solutionLifecycleLocation.value)' in source
    reader = _function(source, "async function loadSolutionLifecycleLearningSources(", "function learningReferenceLines(")
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "solutionLifecycleCreateLocations.has(locationId)" in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(offset) })' in reader
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/replications?${params}`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert 'record.replication_status !== "completed"' in reader
    assert "record.has_review !== true" in reader
    assert 'option.value = record.replication_id' in reader
    assert "option.textContent" in reader
    assert "replication_id}" not in reader


def test_learning_proposal_submit_is_create_scoped_draft_only_csrf_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(source, "async function submitSolutionLifecycleLearningProposal(", "function learningReviewConflictFields(")
    assert "solutionLifecycleCreateLocations.has(locationId)" in submit
    assert 'scope.resource === "solution_lifecycle" && scope.action === "create"' in source
    assert '"#solution-lifecycle-learning-confirm"' in submit
    assert "solutionLifecyclePendingLearningProposal.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingLearningProposal.request_id" in submit
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/replications/${encodeURIComponent(replicationId)}/learning`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'body: JSON.stringify({ ...proposal, request_id: requestId })' in submit
    assert "proposed and requires independent human review" in submit
    assert "decision_status" not in submit and "approve" not in submit and "accept" not in submit
    assert "lockSolutionLifecycleLearningProposalForRetry(true)" in submit
    assert "refreshSolutionLifecycleLocationLock();" in source


def test_learning_review_console_is_review_grant_gated_and_shows_role_conflicts():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-learning-review".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "exact location review grant" in panel.group(0)
    assert "does not apply the lesson or change the solution stage" in panel.group(0)
    assert 'solutionLifecycleLearningReview.hidden = !solutionLifecycleReviewLocations.has(solutionLifecycleLocation.value)' in source
    renderer = _function(
        source,
        "function learningReviewConflictFields(",
        "async function loadSolutionLifecycleLearningReviewQueue(",
    )
    for field in (
        "is_self_authored", "is_self_starter", "is_initial_approver",
        "is_completion_reviewer", "is_source_owner", "is_source_approver",
        "is_source_result_reviewer",
    ):
        assert field in renderer
    queue = _function(
        source,
        "async function loadSolutionLifecycleLearningReviewQueue(",
        "async function loadSolutionLifecycleLearningReviewDetail(",
    )
    assert "solutionLifecycleReviewLocations.has(locationId)" in queue
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/learning/review?${params}`' in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    assert "requestVersion !== solutionLifecycleLearningReviewRequestVersion" in queue
    assert "result.next_offset" in queue and "result.has_more" in queue
    assert "innerHTML" not in queue


def test_learning_review_console_uses_current_lineage_csrf_and_stable_retries_without_apply():
    source = CONSOLE.read_text(encoding="utf-8")
    detail = _function(
        source,
        "async function loadSolutionLifecycleLearningReviewDetail(",
        "function lockSolutionLifecycleLearningReviewForRetry(",
    )
    assert 'record.source_is_current === true' in detail
    assert "learningReviewConflictFields(record)" in detail
    assert "solutionLifecycleLearningReviewFinding.textContent" in detail
    assert "solutionLifecycleLearningReviewEvidence.textContent" in detail
    assert "innerHTML" not in detail
    submit = _function(
        source,
        "async function submitSolutionLifecycleLearningReview(",
        "function appendSolutionLifecycleLearningApplicationItem(",
    )
    assert "solutionLifecycleReviewLocations.has(locationId)" in submit
    assert "solutionLifecycleLearningReviewConfirm.checked" in submit
    assert "solutionLifecyclePendingLearningReview.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingLearningReview.request_id" in submit
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/learning/${encodeURIComponent(record.learning_record_id)}/review`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit and 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "applied_to_version" not in submit and "solution stage is unchanged" in submit


def test_learning_application_console_requires_apply_grant_and_records_version_only():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-learning-application".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "exact location apply grant" in panel.group(0)
    assert "distinct from the independent reviewer" in panel.group(0)
    assert "does not change the solution stage" in panel.group(0)
    assert 'scope.resource === "solution_lifecycle" && scope.action === "apply"' in source
    assert 'solutionLifecycleLearningApplication.hidden = !solutionLifecycleApplyLocations.has(solutionLifecycleLocation.value)' in source

    renderer = _function(
        source,
        "function appendSolutionLifecycleLearningApplicationItem(",
        "async function loadSolutionLifecycleLearningApplicationQueue(",
    )
    assert "cell.textContent" in renderer
    assert "item.is_reviewed_by_current_actor" in renderer
    assert "innerHTML" not in renderer

    queue = _function(
        source,
        "async function loadSolutionLifecycleLearningApplicationQueue(",
        "async function submitSolutionLifecycleLearningApplication(",
    )
    assert "solutionLifecycleApplyLocations.has(locationId)" in queue
    assert "/learning/application" in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    assert "requestVersion !== solutionLifecycleLearningApplicationRequestVersion" in queue
    assert "result.next_offset" in queue and "result.has_more" in queue

    submit = _function(
        source,
        "async function submitSolutionLifecycleLearningApplication(",
        "function renderCoordinationSummary(",
    )
    assert "solutionLifecycleApplyLocations.has(locationId)" in submit
    assert "item.is_reviewed_by_current_actor === true" in submit
    assert "solutionLifecyclePendingLearningApplications.get(learningRecordId)" in submit
    assert "solutionLifecyclePendingLearningApplications.set(learningRecordId, pending)" in submit
    assert "X-CSRF-Token" in submit and 'cache: "no-store"' in submit
    assert 'method: "POST"' in submit and 'credentials: "same-origin"' in submit
    assert "decision_status" not in submit and "current_stage" not in submit


def test_replication_proposal_sources_require_both_grants_and_reviewed_validation():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-replication-proposal".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'solutionLifecycleReplicationProposal.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)' in source
    assert '|| !solutionLifecycleCreateLocations.has(solutionLifecycleLocation.value)' in source
    reader = _function(
        source,
        "async function loadSolutionLifecycleReplicationSources(",
        "function lockSolutionLifecycleReplicationProposal(",
    )
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "solutionLifecycleCreateLocations.has(locationId)" in reader
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/experiments?${params}`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert 'record.solution_status !== "active"' in reader
    assert 'record.experiment_status !== "validated"' in reader
    assert 'record.latest_result_outcome !== "validated"' in reader
    assert "record.latest_result_reviewed_at" in reader
    assert 'option.value = record.experiment_id' in reader


def test_replication_proposal_submit_is_draft_only_csrf_bounded_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitSolutionLifecycleReplicationProposal(",
        "function resetSolutionLifecycleReplicationReviewQueue()",
    )
    assert "solutionLifecycleCreateLocations.has(locationId)" in submit
    assert "solutionLifecycleLocations.has(locationId)" in submit
    assert "solutionLifecycleReplicationConfirm.checked" in submit
    assert "JSON.parse(protocolText)" in submit
    assert "protocolText).length > 65536" in submit
    assert "solutionLifecyclePendingReplicationProposal.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingReplicationProposal.request_id" in submit
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/replications`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'body: JSON.stringify({ ...proposal, request_id: requestId })' in submit
    assert "proposed for independent human review" in submit
    assert "lockSolutionLifecycleReplicationProposal(true)" in submit
    assert "approved" not in submit and "activate" not in submit and "completed" not in submit
    assert 'solutionLifecycleReplicationProposalForm.addEventListener("submit", submitSolutionLifecycleReplicationProposal)' in source


def test_retirement_proposal_sources_are_both_grant_gated_exact_origin_and_paged():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-retirement-proposal".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'solutionLifecycleRetirementProposal.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)' in source
    assert "|| !solutionLifecycleCreateLocations.has(solutionLifecycleLocation.value)" in source
    reader = _function(
        source,
        "async function loadSolutionLifecycleRetirementSources(",
        "function updateSolutionLifecycleRetirementReplacementVisibility(",
    )
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "solutionLifecycleCreateLocations.has(locationId)" in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(offset) })' in reader
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/retirement-candidates?${params}`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "record.solution_id" in reader
    assert "option.textContent = label" in reader
    assert "requestVersion !== solutionLifecycleRetirementSourcesRequestVersion" in reader


def test_retirement_proposal_submit_is_bounded_csrf_idempotent_and_draft_only():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitSolutionLifecycleRetirementProposal(",
        "function resetSolutionLifecycleLearningSources(",
    )
    assert "solutionLifecycleCreateLocations.has(locationId)" in submit
    assert "solutionLifecycleLocations.has(locationId)" in submit
    assert '"#solution-lifecycle-retirement-confirm"' in submit
    assert "retirementType === \"superseded\"" in submit
    assert "if (retirementType === \"superseded\") proposal.replacement_solution_id = replacementId" in submit
    assert "replacementId === solutionId" in submit
    assert "retirementEvidenceLines()" in submit
    assert "solutionLifecyclePendingRetirementProposal.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingRetirementProposal.request_id" in submit
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/solutions/${encodeURIComponent(solutionId)}/retirements`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "body: JSON.stringify({ ...proposal, request_id: requestId })" in submit
    assert "requires independent human review" in submit
    assert "solutionLifecyclePendingLearningProposal" in submit
    assert 'solutionLifecycleRetirementProposalForm.addEventListener("submit", submitSolutionLifecycleRetirementProposal)' in source
    assert 'solutionLifecycleRetirementSourcesLoad.addEventListener("click", () => loadSolutionLifecycleRetirementSources())' in source
    assert "innerHTML" not in submit


def test_replication_review_console_is_grant_gated_private_independent_and_retry_safe():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-replication-review".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "exact location review grant" in panel.group(0)
    queue = _function(
        source,
        "async function loadSolutionLifecycleReplicationReviewQueue(",
        "async function loadSolutionLifecycleReplicationReviewDetail(",
    )
    assert 'solutionLifecycleReviewLocations.has(locationId)' in queue
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/replications/review?${params}`' in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    detail = _function(
        source,
        "async function loadSolutionLifecycleReplicationReviewDetail(",
        "function lockSolutionLifecycleReplicationReview(",
    )
    assert "result.is_self_authored === true" in detail
    assert "solutionLifecycleReplicationReviewForm.hidden = selfAuthored" in detail
    assert "description.textContent =" in detail
    assert "innerHTML" not in detail
    review = _function(
        source,
        "async function reviewSolutionLifecycleReplication(",
        "async function loadSolutionLifecycleLearningSources(",
    )
    assert 'decision === "rejected" && reason.length < 10' in review
    assert "solutionLifecyclePendingReplicationReview.fingerprint !== fingerprint" in review
    assert "solutionLifecyclePendingReplicationReview.request_id" in review
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/replications/${encodeURIComponent(detail.replication_id)}/review`' in review
    assert 'method: "POST"' in review and 'cache: "no-store"' in review
    assert '"X-CSRF-Token": csrf' in review
    assert "Approval does not start or complete the replication" in review
    assert "lockSolutionLifecycleReplicationReview(solutionLifecycleReplicationReviewSubmitting)" in review
    assert "innerHTML" not in review


def test_retirement_review_console_uses_review_grants_and_private_text_rendering():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-retirement-review".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "solutionLifecycleReviewLocations = new Set(solutionLifecycleReviewLocationIds)" in source
    assert "...solutionLifecycleReadLocationIds, ...solutionLifecycleReviewLocationIds" in source
    assert source.index('id="solution-lifecycle-location"') < source.index('id="solution-lifecycle-read-surfaces"')
    assert "solutionLifecycleReadSurfaces.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)" in source
    assert "solutionLifecycleRetirementReview.hidden = !solutionLifecycleReviewLocations.has(solutionLifecycleLocation.value)" in source
    queue = _function(
        source,
        "async function loadSolutionLifecycleRetirementReviewQueue(",
        "async function loadSolutionLifecycleRetirementReviewDetail(",
    )
    assert "solutionLifecycleReviewLocations.has(locationId)" in queue
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/retirements/review?${params}`' in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    renderer = _function(
        source,
        "function appendSolutionLifecycleRetirementReviewItems(",
        "async function loadSolutionLifecycleRetirementReviewQueue(",
    )
    assert "heading.textContent" in renderer and "button.textContent" in renderer
    assert "is_self_authored" in renderer and "proposer_attributed" in renderer
    assert "innerHTML" not in renderer
    detail = _function(
        source,
        "async function loadSolutionLifecycleRetirementReviewDetail(",
        "function lockSolutionLifecycleRetirementApproval(",
    )
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/retirements/review/${encodeURIComponent(retirementId)}`' in detail
    assert 'solutionLifecycleRetirementReviewEvidence.textContent = JSON.stringify' in detail
    assert "result.is_self_authored === true" in detail
    assert "result.proposer_attributed !== true" in detail
    assert "innerHTML" not in detail


def test_retirement_review_approval_is_confirmed_csrf_protected_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    approve = _function(
        source,
        "async function approveSolutionLifecycleRetirement(",
        "function resetSolutionLifecycleLearningSources(",
    )
    assert "detail.is_self_authored === true" in approve
    assert "detail.proposer_attributed !== true" in approve
    assert 'solutionLifecycleReviewLocations.has(locationId)' in approve
    assert "solutionLifecycleRetirementReviewConfirm.checked" in approve
    assert "solutionLifecyclePendingRetirementApproval.request_id" in approve
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/retirements/${encodeURIComponent(detail.retirement_id)}/approve`' in approve
    assert 'method: "POST"' in approve
    assert 'credentials: "same-origin"' in approve
    assert 'cache: "no-store"' in approve
    assert '"X-CSRF-Token": csrf' in approve
    assert 'body: JSON.stringify({ request_id: requestId })' in approve
    assert "does not schedule or execute the retirement" in approve
    assert 'solutionLifecycleRetirementReviewApprove.addEventListener("click", approveSolutionLifecycleRetirement)' in source


def test_renderer_uses_only_fixed_aggregate_groups_and_safe_dom_text():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderSolutionLifecycleSummary(summary)", "async function loadSolutionLifecycleSummary()")
    for key in (
        "stage_counts", "solution_status_counts", "stage_gate_status_counts",
        "latest_gate_evaluation_counts", "experiment_status_counts", "experiment_result_counts",
        "replication_status_counts", "funding_decision_counts", "adoption_program_status_counts",
        "configuration_approval_counts", "adopter_readiness_counts", "scale_gate_status_counts",
        "learning_decision_counts", "retirement_status_counts",
    ):
        assert f'"{key}"' in renderer
    assert "Object.entries" not in renderer
    assert "textContent" in renderer
    for private_field in ("solution_id", "solution_name", "evidence", "requested_amount", "party_id"):
        assert private_field not in renderer


def test_console_ids_are_unique_and_refresh_controls_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    assert 'solutionLifecycleLocation.addEventListener("change", () =>' in source
    assert "loadSolutionLifecycleSummary();" in source
    assert 'solutionLifecycleGatesLoad.addEventListener("click", () => loadSolutionLifecycleGates())' in source
    assert 'solutionLifecycleGatesMore.addEventListener("click", () => loadSolutionLifecycleGates(true))' in source
    assert 'solutionLifecycleExperimentsLoad.addEventListener("click", () => loadSolutionLifecycleExperiments())' in source
    assert 'solutionLifecycleExperimentsMore.addEventListener("click", () => loadSolutionLifecycleExperiments(true))' in source
    assert 'solutionLifecycleFundingLoad.addEventListener("click", () => loadSolutionLifecycleFunding())' in source
    assert 'solutionLifecycleFundingMore.addEventListener("click", () => loadSolutionLifecycleFunding(true))' in source
    assert 'solutionLifecycleProjectionLoad.addEventListener("click", () => loadSolutionLifecycleProjection())' in source
    assert 'solutionLifecycleProjectionMore.addEventListener("click", () => loadSolutionLifecycleProjection(true))' in source
    assert 'solutionLifecycleProjection.addEventListener("change", () => loadSolutionLifecycleProjection())' in source
    assert 'solutionLifecycleLearningSourcesLoad.addEventListener("click", () => loadSolutionLifecycleLearningSources())' in source
    assert 'solutionLifecycleLearningSourcesMore.addEventListener("click", () => loadSolutionLifecycleLearningSources(true))' in source
    assert 'solutionLifecycleLearningProposalForm.addEventListener("submit", submitSolutionLifecycleLearningProposal)' in source
    assert 'document.querySelector("#solution-lifecycle-learning-reset").addEventListener("click"' in source
    assert 'document.querySelector("#solution-lifecycle-refresh").addEventListener("click", loadSolutionLifecycleSummary)' in source


def test_funding_tranche_review_is_review_grant_gated_and_private():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleFundingCase(",
        "async function loadSolutionLifecycleFundingTargets(",
    )
    assert 'solutionLifecycleReviewLocations.has(locationId)' in renderer
    assert 'fundingCase.decision_status === "approved"' in renderer
    assert 'fundingCase.tranche_status === "proposed"' in renderer
    assert "fundingCase.funding_case_id" in renderer and "fundingCase.tranche_id" in renderer
    assert 'review.textContent = "Review proposed tranche"' in renderer
    assert "loadSolutionLifecycleFundingTrancheReviewDetail(" in renderer
    assert "innerHTML" not in renderer

    detail = _function(
        source,
        "async function loadSolutionLifecycleFundingTrancheReviewDetail(",
        "async function approveSolutionLifecycleFundingTranche(",
    )
    assert "/tranches/${encodeURIComponent(trancheId)}/review`" in detail
    assert 'credentials: "same-origin"' in detail and 'cache: "no-store"' in detail
    assert "solutionLifecycleReviewLocations.has(locationId)" in detail
    assert "requestVersion !== solutionLifecycleFundingTrancheReviewDetailVersion" in detail
    assert "locationId !== solutionLifecycleLocation.value" in detail
    assert "result.milestone_conditions" in detail and ".textContent = JSON.stringify" in detail
    assert "result.eligible_for_independent_approval === true" in detail
    assert 'result.case_decision_status === "approved"' in detail
    assert 'result.tranche_status === "proposed"' in detail
    assert "globalThis.crypto?.randomUUID?.()" in detail
    assert "innerHTML" not in detail


def test_funding_tranche_approval_is_acknowledged_csrf_protected_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    approve = _function(
        source,
        "async function approveSolutionLifecycleFundingTranche(",
        "function appendSolutionLifecycleFundingReviewCase(",
    )
    assert "solutionLifecycleReviewLocations.has(pending.locationId)" in approve
    assert "solutionLifecycleFundingTrancheApprovalAcknowledge.checked" in approve
    assert "pending.requestId" in approve
    assert "/tranches/${encodeURIComponent(pending.trancheId)}/approve`" in approve
    assert 'method: "POST"' in approve
    assert 'credentials: "same-origin"' in approve
    assert 'cache: "no-store"' in approve
    assert '"X-CSRF-Token": csrf' in approve
    assert "response.status < 500" in approve
    assert "Retrying will reuse the same request ID" in approve
    assert "No money was released" in approve and "solution stage did not change" in approve
    assert 'solutionLifecycleFundingTrancheApprovalSubmit.addEventListener("click", approveSolutionLifecycleFundingTranche)' in source
    assert 'solutionLifecycleFundingTrancheApprovalAcknowledge.addEventListener("change"' in source
    assert "innerHTML" not in approve


def test_replication_activation_is_transition_grant_gated_acknowledged_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleSupplementalRecord(",
        "async function loadSolutionLifecycleAdoptionEventSummary(",
    )
    assert 'view.route === "replications"' in renderer
    assert 'solutionLifecycleTransitionLocations.has(locationId)' in renderer
    assert 'record.replication_status === "approved"' in renderer
    assert 'record.replication_status === "active"' in renderer
    assert "createSolutionLifecycleReplicationActivationForm(record, locationId)" in renderer
    assert "innerHTML" not in renderer

    action = _function(
        source,
        "function createSolutionLifecycleReplicationActivationForm(",
        "async function loadSolutionLifecycleAdoptionEventSummary(",
    )
    assert "solutionLifecycleTransitionLocations.has(locationId)" in action
    assert 'method: "POST"' in action
    assert "/replications/${encodeURIComponent(record.replication_id)}/start`" in action
    assert 'credentials: "same-origin"' in action
    assert 'cache: "no-store"' in action
    assert '"X-CSRF-Token": csrf' in action
    assert "request.requestId" in action
    assert "acknowledged: true" in action
    assert "Retry this same request" in action
    assert "solutionLifecyclePendingReplicationActivation" in action
    assert "solution stage are unchanged" in action
    assert "textContent" in action
    assert "innerHTML" not in action

    location_change = _function(
        source,
        'solutionLifecycleLocation.addEventListener("change", () => {',
        'solutionLifecycleGatesLoad.addEventListener("click", () => loadSolutionLifecycleGates())',
    )
    assert "Resolve the pending replication start request" in location_change


def test_replication_completion_review_is_exact_review_grant_gated_paged_and_private():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="solution-lifecycle-replication-completion-review".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert 'id="solution-lifecycle-replication-completion-review" hidden' in panel.group()
    assert "solution stage remains unchanged" in panel.group()
    assert "leaves the replication active" in panel.group()

    queue = _function(
        source,
        "async function loadSolutionLifecycleReplicationCompletionReviewQueue(",
        "async function loadSolutionLifecycleReplicationCompletionReviewDetail(",
    )
    assert 'solutionLifecycleReviewLocations.has(locationId)' in queue
    assert "solutionLifecycleLocations.has(locationId)" not in queue
    assert "/replications/completion-review?${params}`" in queue
    assert 'new URLSearchParams({ limit: "50", offset: String(offset) })' in queue
    assert 'credentials: "same-origin"' in queue and 'cache: "no-store"' in queue
    assert "requestVersion !== solutionLifecycleReplicationCompletionReviewRequestVersion" in queue
    assert "locationId !== solutionLifecycleLocation.value" in queue
    assert "result.next_offset" in queue and "result.has_more" in queue
    assert "cell.textContent = String(value)" in queue
    assert "innerHTML" not in queue

    detail = _function(
        source,
        "async function loadSolutionLifecycleReplicationCompletionReviewDetail(",
        "function lockSolutionLifecycleReplicationCompletionReview(",
    )
    assert "/completion-proposals/${encodeURIComponent(proposalId)}/review`" in detail
    assert 'credentials: "same-origin"' in detail and 'cache: "no-store"' in detail
    assert "result.outcome_summary" in detail
    assert "JSON.stringify(result.evidence ?? [], null, 2)" in detail
    for reviewer_guard in (
        "result.is_self_authored !== true",
        "result.is_self_started !== true",
        "result.is_initial_approver !== true",
        "result.is_source_owner !== true",
        "result.is_source_approver !== true",
        "result.is_source_result_reviewer !== true",
        "result.source_is_current === true",
    ):
        assert reviewer_guard in detail
    assert "innerHTML" not in detail


def test_replication_completion_decision_is_acknowledged_csrf_protected_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    review = _function(
        source,
        "async function reviewSolutionLifecycleReplicationCompletion(",
        "async function loadSolutionLifecycleLearningSources(",
    )
    assert "solutionLifecycleReviewLocations.has(locationId)" in review
    assert "detail.is_self_authored === true" in review
    assert "detail.is_self_started === true" in review
    assert "detail.is_initial_approver === true" in review
    assert "detail.is_source_result_reviewer === true" in review
    assert "detail.source_is_current !== true" in review
    assert "solutionLifecycleReplicationCompletionReviewConfirm.checked" in review
    assert 'decision === "rejected" && reason.length < 10' in review
    assert "solutionLifecyclePendingReplicationCompletionReview.fingerprint !== fingerprint" in review
    assert "solutionLifecyclePendingReplicationCompletionReview.request_id" in review
    assert "/completion-proposals/${encodeURIComponent(detail.proposal_id)}/review`" in review
    assert 'method: "POST"' in review
    assert 'credentials: "same-origin"' in review and 'cache: "no-store"' in review
    assert '"X-CSRF-Token": csrf' in review
    assert "response.status < 500" in review
    assert "result.replayed === true" in review
    assert "Replication completed with reviewed outcome" in review
    assert "the solution stage is unchanged" in review
    assert "Replication remains active" in review
    assert 'solutionLifecycleReplicationCompletionReviewForm.addEventListener("submit", reviewSolutionLifecycleReplicationCompletion)' in source
    assert 'solutionLifecycleReplicationCompletionReviewDecision.addEventListener("change"' in source
    assert "innerHTML" not in review


def test_replication_completion_submission_is_active_row_submit_grant_gated_and_bounded():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleSupplementalRecord(",
        "function createSolutionLifecycleReplicationActivationForm(",
    )
    assert 'view.route === "replications"' in renderer
    assert 'record.replication_status === "active"' in renderer
    assert "solutionLifecycleSubmitLocations.has(locationId)" in renderer
    assert "record.replication_id" in renderer
    assert "createSolutionLifecycleReplicationCompletionProposalForm(record, locationId)" in renderer

    form = _function(
        source,
        "function createSolutionLifecycleReplicationCompletionProposalForm(",
        "async function loadSolutionLifecycleAdoptionEventSummary(",
    )
    assert '"successful"' in form and '"failed"' in form
    assert 'evidence_maturity: Number(maturity.value)' in form
    assert 'summary.minLength = 10' in form and 'summary.maxLength = 4000' in form
    assert 'evidence.maxLength = 65536' in form
    assert "evidenceValue.length > 100" in form
    assert "TextEncoder().encode(encodedEvidence).length > 65536" in form
    assert "solutionLifecycleSubmitLocations.has(locationId)" in form
    assert "solutionLifecycleLocations.has(locationId)" in form
    assert '"X-CSRF-Token": csrf' in form
    assert "/completion-proposals`" in form
    assert 'method: "POST"' in form
    assert 'credentials: "same-origin"' in form and 'cache: "no-store"' in form
    assert "solutionLifecyclePendingReplicationCompletionProposal.fingerprint !== fingerprint" in form
    assert "solutionLifecyclePendingReplicationCompletionProposal.request_id" in form
    assert "The result may be uncertain" in form
    assert "Replication remains active and the solution stage is unchanged" in form
    assert "does not complete the replication" in form
    assert "innerHTML" not in renderer + form

    location_change = _function(
        source,
        'solutionLifecycleLocation.addEventListener("change", () => {',
        'solutionLifecycleGatesLoad.addEventListener("click", () => loadSolutionLifecycleGates())',
    )
    assert "Resolve the pending completion-report request" in location_change


def test_scale_gate_assessment_and_review_panels_are_hidden_and_explain_separate_human_decisions():
    source = CONSOLE.read_text(encoding="utf-8")
    assessment = re.search(r'<section id="solution-lifecycle-scale-assessment".*?</section>', source, re.DOTALL)
    review = re.search(r'<section id="solution-lifecycle-scale-review".*?</section>', source, re.DOTALL)
    assert assessment is not None and 'id="solution-lifecycle-scale-assessment" hidden' in assessment.group()
    assert review is not None and 'id="solution-lifecycle-scale-review" hidden' in review.group()
    assert "exact location create grant" in assessment.group()
    assert "different active human" in assessment.group()
    assert "exact location review grant" in review.group()
    assert "Neither decision advances the solution stage" in review.group()


def test_scale_gate_assessment_is_typed_evidence_backed_create_only_and_retry_safe():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendScaleGateAssessmentTarget(", "async function loadSolutionLifecycleScaleGateAssessmentTargets(")
    reader = _function(
        source,
        "async function loadSolutionLifecycleScaleGateAssessmentTargets(",
        "async function submitSolutionLifecycleScaleGateAssessment(",
    )
    submit = _function(
        source,
        "async function submitSolutionLifecycleScaleGateAssessment(",
        "function appendSolutionLifecycleScaleGateReview(",
    )
    assert "target.comparison_operator" in renderer and "target.threshold_numeric" in renderer
    assert "Proposed result for independent review" in renderer
    assert "sample.max = \"10000000\"" in renderer
    assert "textContent" in renderer and "innerHTML" not in renderer
    assert "solutionLifecycleCreateLocations.has(locationId)" in reader
    assert "/scale-gates/assessment-targets?${params}" in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== solutionLifecycleScaleAssessmentRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "evidenceRefs.length < 1 || evidenceRefs.length > 100" in submit
    assert "form.pendingAssessment.fingerprint !== fingerprint" in submit
    assert "form.pendingAssessment.request_id" in submit
    assert "/scale-gates/${encodeURIComponent(target.scale_gate_id)}/evaluations`" in submit
    assert 'method: "POST"' in submit and 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "does not advance the solution stage" in renderer
    assert "innerHTML" not in submit


def test_scale_gate_review_queue_detail_and_decision_are_scoped_independent_and_retry_safe():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function appendSolutionLifecycleScaleGateReview(", "async function loadSolutionLifecycleScaleGateReviewQueue(")
    queue = _function(
        source,
        "async function loadSolutionLifecycleScaleGateReviewQueue(",
        "async function loadSolutionLifecycleScaleGateReviewDetail(",
    )
    detail = _function(
        source,
        "async function loadSolutionLifecycleScaleGateReviewDetail(",
        "async function submitSolutionLifecycleScaleGateReview(",
    )
    submit = _function(
        source,
        "async function submitSolutionLifecycleScaleGateReview(",
        "function resetSolutionLifecycleRetirementSources(",
    )
    assert "item.evaluator_conflict === true" in renderer and "button.disabled" in renderer
    assert "textContent" in renderer and "innerHTML" not in renderer
    assert "solutionLifecycleReviewLocations.has(locationId)" in queue
    assert "/scale-gates/review?${params}" in queue
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in queue
    assert 'cache: "no-store"' in queue
    assert "requestVersion !== solutionLifecycleScaleReviewRequestVersion" in queue
    assert "locationId !== solutionLifecycleLocation.value" in queue
    assert "record.evaluator_conflict !== true" in detail
    assert "solutionLifecycleScaleReviewEvidence.textContent = JSON.stringify" in detail
    assert "innerHTML" not in detail
    assert 'decision === "rejected" && (!reviewReason || reviewReason.length < 10' in submit
    assert "solutionLifecyclePendingScaleReview.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingScaleReview.request_id" in submit
    assert "/scale-gates/review/${encodeURIComponent(record.assessment_id)}`" in submit
    assert 'method: "POST"' in submit and 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "Solution stage unchanged" in submit
    assert "innerHTML" not in submit


def test_retirement_migration_sunset_and_post_review_are_scoped_acknowledged_and_retry_safe():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleSupplementalRecord(",
        "function createSolutionLifecycleReplicationActivationForm(",
    )
    form = _function(
        source,
        "function createSolutionLifecycleRetirementTransitionForm(",
        "function createSolutionLifecycleReplicationActivationForm(",
    )
    assert 'view.route === "retirements"' in renderer
    assert 'record.retirement_status === "approved"' in renderer
    assert 'record.retirement_status === "migration"' in renderer
    assert 'record.retirement_status === "sunset"' in renderer
    assert "solutionLifecycleTransitionLocations.has(locationId)" in renderer
    assert "solutionLifecycleReviewLocations.has(locationId)" in renderer
    assert 'effectiveDate.type = "datetime-local"' in form
    assert "parsed.toISOString()" in form
    assert "solutionLifecyclePendingRetirementTransition.fingerprint !== fingerprint" in form
    assert "pendingRequest.requestId" in form
    assert "pendingRequest.payload" in form
    assert "post-retirement-review" in form
    assert 'credentials: "same-origin"' in form and 'cache: "no-store"' in form
    assert '"X-CSRF-Token": csrf' in form
    assert "no data will be deleted or pruned" in form.lower()
    assert "innerHTML" not in renderer + form

    location_change = _function(
        source,
        'solutionLifecycleLocation.addEventListener("change", () => {',
        'solutionLifecycleGatesLoad.addEventListener("click", () => loadSolutionLifecycleGates())',
    )
    assert "Resolve the pending retirement transition before changing locations." in location_change
    assert "|| solutionLifecyclePendingRetirementTransition)" in source


def test_location_solution_creation_is_exact_grant_gated_acknowledged_and_retry_stable():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="solution-lifecycle-create".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "location-originated discovery" in panel.group(0)
    assert "does not create cross-location links or stage gates" in panel.group(0)
    assert 'solutionLifecycleCreate.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)' in source
    assert '|| !solutionLifecycleCreateLocations.has(solutionLifecycleLocation.value)' in source
    submit = _function(
        source,
        "async function submitSolutionLifecycleCreate(",
        "function appendSolutionLifecycleGate(",
    )
    assert "solutionLifecycleCreateLocations.has(locationId)" in submit
    assert 'scope.resource === "solution_lifecycle" && scope.action === "create"' in source
    assert '"#solution-lifecycle-create-confirm"' in submit
    assert "solutionLifecyclePendingCreate.fingerprint !== fingerprint" in submit
    assert "solutionLifecyclePendingCreate.request_id" in submit
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/solutions`' in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit and 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "innerHTML" not in submit


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
