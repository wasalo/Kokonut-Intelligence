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
    reader = _function(source, "async function loadSolutionLifecycleGates(", "function appendSolutionLifecycleExperiment(")
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
    for private_field in ("experiment_id", "solution_id", "hypothesis", "metric_key", "primary_results", "adverse_events", "evidence"):
        assert f"experiment.{private_field}" not in renderer
    assert "No reviewed result" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_funding_reader_uses_location_scope_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadSolutionLifecycleFunding(", "function appendSolutionLifecycleSupplementalRecord(")
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
    renderer = _function(source, "function appendSolutionLifecycleFundingCase(", "async function loadSolutionLifecycleFunding(")
    for field in (
        "solution_name", "solution_type", "current_stage", "solution_status", "capital_stage",
        "funding_instrument", "currency", "decision_status", "case_created_at", "case_approved_at",
        "tranche_number", "tranche_status", "tranche_approved_at", "tranche_released_at",
    ):
        assert f"fundingCase.{field}" in renderer
    for private_field in (
        "funding_case_id", "tranche_id", "requested_amount", "authorized_amount", "amount",
        "milestone", "rationale", "evidence", "submitted_by", "approved_by", "party_id",
    ):
        assert f"fundingCase.{private_field}" not in renderer
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
    reader = _function(source, "async function loadSolutionLifecycleProjection(", "function resetSolutionLifecycleRetirementSources(")
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
    submit = _function(source, "async function submitSolutionLifecycleLearningProposal(", "function renderCoordinationSummary(")
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
    assert "solutionLifecycleLocation.disabled = locked" in source


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
