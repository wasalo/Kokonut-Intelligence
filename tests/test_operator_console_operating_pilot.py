"""Console contract for CAP-037 operating-pilot reads and private draft creation."""

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


def test_operating_pilot_surface_is_gated_by_exact_location_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="operating-pilot".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Location-scoped operating summary" in panel.group()
    assert 'id="operating-pilot-demand-create-form"' in panel.group()
    assert 'id="operating-pilot-capacity-create-form"' in panel.group()
    assert 'id="operating-pilot-resource-create-form"' in panel.group()
    assert 'id="operating-pilot-own-capacity-rows"' in panel.group()
    assert 'id="operating-pilot-own-resources-rows"' in panel.group()
    assert 'id="operating-pilot-capacity-review-rows"' in panel.group()
    assert 'id="operating-pilot-demand-review-rows"' in panel.group()
    assert 'id="operating-pilot-work-opportunities-rows"' in panel.group()
    assert 'id="operating-pilot-work-opportunities"' in panel.group()
    assert 'id="operating-pilot-work-claim-review-rows"' in panel.group()
    assert 'id="operating-pilot-work-claim-review"' in panel.group()
    assert 'id="operating-pilot-work-claim-allocation-rows"' in panel.group()
    assert 'id="operating-pilot-work-claim-allocation"' in panel.group()
    assert 'id="operating-pilot-work-claim-allocation-dialog"' in source
    assert 'id="operating-pilot-work-claim-allocation-acknowledged"' in source
    assert 'id="operating-pilot-work-claim-review-dialog"' in source
    assert 'id="operating-pilot-work-claim-review-acknowledged"' in source
    assert 'id="operating-pilot-capacity-review-dialog"' in source
    assert 'id="operating-pilot-capacity-review-acknowledged"' in source
    assert "including your private notes" in panel.group()
    assert "Work-claim activity" in panel.group()
    assert "Resource-request categories" in panel.group()
    assert 'scope.resource === "operating_pilot" && scope.action === "read"' in source
    assert 'scope.resource === "operating_pilot" && scope.action === "create"' in source
    assert 'scope.resource === "operating_pilot" && scope.action === "read_own"' in source
    assert 'scope.resource === "operating_pilot" && scope.action === "review"' in source
    assert "operatingPilotLocations = new Set(operatingPilotLocationIds)" in source
    assert 'operatingPilot.hidden = false' in source
    assert "operating-pilot" in source


def test_summary_and_pages_use_protected_no_store_routes_and_safe_text_rendering():
    source = CONSOLE.read_text(encoding="utf-8")
    summary = _function(source, "async function loadOperatingPilotSummary()", "async function loadOperatingPilotDemand(")
    demand = _function(source, "async function loadOperatingPilotDemand(append = false)", "async function loadOperatingPilotCapacity(")
    capacity = _function(source, "async function loadOperatingPilotCapacity(append = false)", "async function loadOperatingPilot()")
    claims = _function(source, "async function loadOperatingPilotWorkClaims(append = false)", "async function loadOperatingPilotWorkOpportunities(")
    resources = _function(source, "async function loadOperatingPilotResources(append = false)", "async function loadOperatingPilot()")
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/summary`' in summary
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/demand-signals?${params}`' in demand
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/capacity-periods?${params}`' in capacity
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/work-claims?${params}`' in claims
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/resource-categories?${params}`' in resources
    for reader in (summary, demand, capacity, claims, resources):
        assert 'credentials: "same-origin"' in reader
        assert 'cache: "no-store"' in reader
        assert "operatingPilotLocations.has(locationId)" in reader
        assert "innerHTML" not in reader
    assert "description.textContent = operatingPilotDisplayValue(value)" in source
    assert "cell.textContent = operatingPilotDisplayValue(value)" in source


def test_capacity_cohort_suppression_never_renders_hour_totals():
    source = CONSOLE.read_text(encoding="utf-8")
    capacity = _function(source, "async function loadOperatingPilotCapacity(append = false)", "async function loadOperatingPilot()")
    assert 'const suppression = item.suppressed === true' in capacity
    assert capacity.count('suppression ? "Suppressed (<3 contributors)" : item.') == 3
    assert 'addOperatingPilotMetric("Current-period capacity", "Suppressed (<3 contributors)")' in source


def test_work_claim_cohort_suppression_never_renders_individual_claim_data():
    source = CONSOLE.read_text(encoding="utf-8")
    claims = _function(
        source,
        "async function loadOperatingPilotWorkClaims(append = false)",
        "async function loadOperatingPilotWorkOpportunities(",
    )
    assert 'item.suppressed === true ? "Suppressed (<3 contributors)" : item.claim_count' in claims
    assert "item.work_type" in claims
    for private_field in ("claim_id", "work_item_id", "claimant_party_id", "decision_reason"):
        assert private_field not in claims


def test_resource_request_draft_is_create_grant_gated_private_and_retry_safe():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = _function(source, 'id="operating-pilot-resource-create"', 'id="operating-pilot-own-capacity"')
    submit = _function(source, "async function submitOperatingPilotResourceDraft(event)", "function cancelOperatingPilotCapacityEdit()")
    assert "operatingPilotResourceCreate.hidden = !operatingPilotCreateLocations.has(locationId)" in source
    assert "&& !(operatingPilotOwnDemandLocations.has(locationId)" in source
    assert "operatingPilotEditOwnResourceLocations.has(locationId)" in source
    assert '`/operator/api/operating-pilot/${encodeURIComponent(locationId)}/resource-requests${' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert "crypto.randomUUID()" in submit
    assert "result.status !== \"draft\"" in submit
    assert "Private resource draft saved" in submit
    assert "not visible in the review queue" in submit
    assert "innerHTML" not in submit
    assert "description" in panel
    assert "funding decision" in panel
    assert 'id="operating-pilot-resource-edit-cancel"' in panel
    assert '"PUT" : "POST"' in submit
    assert "saving a revised private resource-request draft" in submit.lower()


def test_resource_revision_is_edit_own_gated_idempotent_and_keeps_submission_separate():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotResourceDraft(event)",
        "function cancelOperatingPilotCapacityEdit()",
    )
    edit = _function(
        source,
        "function startOperatingPilotResourceEdit(item, locationId)",
        "async function loadOperatingPilotCapacityReviewQueue(",
    )
    row = _function(
        source,
        "function appendOperatingPilotOwnResourceRow(item)",
        "async function loadOperatingPilotOwnResourceRequests(",
    )
    assert "operatingPilotEditOwnResourceLocations.has(locationId)" in submit
    assert '`/${encodeURIComponent(draftId)}`' in submit
    assert 'method: isEditing ? "PUT" : "POST"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "operatingPilotPendingResourceCreate.request_id" in submit
    assert "result.replayed" in submit
    assert "status === \"draft\"" in edit
    assert "item.draft_id" in edit
    assert "operatingPilotEditOwnResourceLocations.has(locationId)" in row
    assert 'item.status === "draft"' in row
    assert "textContent = \"Edit your draft\"" in row


def test_resource_submission_requires_submit_own_confirmation_and_stable_retry():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotResourceRequest(item, locationId, button)",
        "function cancelOperatingPilotCapacityEdit()",
    )
    row = _function(
        source,
        "function appendOperatingPilotOwnResourceRow(item)",
        "async function loadOperatingPilotOwnResourceRequests(",
    )
    assert "operatingPilotSubmitOwnResourceLocations.has(locationId)" in submit
    assert 'item.status !== "draft"' in submit
    assert "window.confirm" in submit
    assert 'method: "POST"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert "operatingPilotPendingResourceSubmissions.get(item.draft_id)" in submit
    assert "operatingPilotPendingResourceSubmissions.set(item.draft_id, requestId)" in submit
    assert "result.status !== \"submitted\"" in submit
    assert 'submit.textContent = "Submit for review"' in row
    assert "operatingPilotSubmitOwnResourceLocations.has(locationId)" in row


def test_own_resource_history_is_read_own_gated_private_paged_and_safely_rendered():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = _function(
        source,
        'id="operating-pilot-own-resources"',
        'id="operating-pilot-own-capacity"',
    )
    loader = _function(
        source,
        "async function loadOperatingPilotOwnResourceRequests(append = false)",
        "async function loadOperatingPilotCapacityReviewQueue(",
    )
    row = _function(
        source,
        "function appendOperatingPilotOwnResourceRow(item)",
        "async function loadOperatingPilotOwnResourceRequests(",
    )
    assert "operatingPilotOwnResources.hidden = !operatingPilotOwnDemandLocations.has(locationId)" in source
    assert "/my-resource-requests?${params}" in loader
    assert "operatingPilotOwnDemandLocations.has(locationId)" in loader
    assert 'credentials: "same-origin"' in loader
    assert 'cache: "no-store"' in loader
    assert "nextOffset <= 10000" in loader
    assert "operatingPilotOwnResourcesRequestVersion" in loader
    assert "locationId !== operatingPilotLocation.value" in loader
    assert "innerHTML" not in loader
    assert "cell.textContent = operatingPilotDisplayValue(value)" in row
    for field in ("resource_type", "description", "urgency", "requested_by", "status"):
        assert f"item.{field}" in row
    assert "read_own grant" in panel


def test_work_opportunities_show_claim_action_only_under_claim_own_and_keep_it_proposal_only():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = _function(
        source,
        "async function loadOperatingPilotWorkOpportunities(append = false)",
        "function appendOperatingPilotWorkOpportunityRow(",
    )
    row = _function(
        source,
        "function appendOperatingPilotWorkOpportunityRow(",
        "async function proposeOperatingPilotWorkClaim(",
    )
    claim = _function(
        source,
        "async function proposeOperatingPilotWorkClaim(",
        "async function loadOperatingPilotResources(",
    )
    assert "operatingPilotClaimOwnLocations.has(locationId)" in panel
    assert "work-opportunities?${params}" in panel
    assert 'credentials: "same-origin"' in panel
    assert 'cache: "no-store"' in panel
    assert "innerHTML" not in panel
    assert 'item.has_own_claim !== true' in row
    assert 'button.textContent = "Propose claim"' in row
    assert 'method: "POST"' in claim
    assert '"X-CSRF-Token": csrf' in claim
    assert 'cache: "no-store"' in claim
    assert "request_id: requestId" in claim
    assert "does not assign work" in claim


def test_work_claim_review_is_exact_grant_gated_redacted_and_paged():
    source = CONSOLE.read_text(encoding="utf-8")
    queue = _function(
        source,
        "async function loadOperatingPilotWorkClaimReviewQueue(append = false)",
        "function appendOperatingPilotWorkClaimReviewRow(",
    )
    row = _function(
        source,
        "function appendOperatingPilotWorkClaimReviewRow(",
        "function syncOperatingPilotWorkClaimReviewReason(",
    )
    submit = _function(
        source,
        "async function submitOperatingPilotWorkClaimReview(event)",
        "async function loadOperatingPilot()",
    )
    assert 'operatingPilotCapacityReviewLocations.has(locationId)' in queue
    assert "work-claim-review-queue?${params}" in queue
    assert 'credentials: "same-origin"' in queue
    assert 'cache: "no-store"' in queue
    assert "nextOffset <= 10000" in queue
    assert "claimant_party_id" not in row
    assert "decision_reason" not in row
    assert "display_name" not in row
    assert 'review.textContent = "Review proposal"' in row
    assert "operatingPilotCapacityReviewLocations.has(pending.location_id)" in submit
    assert "/work-claims/${encodeURIComponent(pending.claim_id)}/review" in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'cache: "no-store"' in submit
    assert "operatingPilotPendingWorkClaimReviewDecisions" in submit
    assert "Acceptance permits a later allocation decision" in row
    assert "No work assignment was made." in submit


def test_work_claim_review_form_requires_rejection_reason_and_explicit_acknowledgement():
    source = CONSOLE.read_text(encoding="utf-8")
    reason = _function(
        source,
        "function syncOperatingPilotWorkClaimReviewReason()",
        "async function submitOperatingPilotWorkClaimReview(event)",
    )
    submit = _function(
        source,
        "async function submitOperatingPilotWorkClaimReview(event)",
        "async function loadOperatingPilot()",
    )
    assert 'operatingPilotWorkClaimReviewReason.required = rejecting' in reason
    assert "Enter a reason before rejecting this proposal." in submit
    assert "operatingPilotWorkClaimReviewAcknowledged.checked" in submit
    assert '"decision", "reason"' not in submit
    assert "request_id: pendingRequest.request_id" in submit
    assert 'operatingPilotWorkClaimReviewMore.addEventListener(' in source


def test_work_claim_allocation_is_separately_granted_private_paged_and_confirmed():
    source = CONSOLE.read_text(encoding="utf-8")
    queue = _function(
        source,
        "async function loadOperatingPilotWorkClaimAllocationQueue(append = false)",
        "function appendOperatingPilotWorkClaimAllocationRow(",
    )
    row = _function(
        source,
        "function appendOperatingPilotWorkClaimAllocationRow(",
        "async function submitOperatingPilotWorkClaimAllocation(event)",
    )
    submit = _function(
        source,
        "async function submitOperatingPilotWorkClaimAllocation(event)",
        "async function loadOperatingPilot()",
    )
    assert "operatingPilotAllocateLocations.has(locationId)" in queue
    assert "work-claim-allocation-queue?${params}" in queue
    assert 'credentials: "same-origin"' in queue
    assert 'cache: "no-store"' in queue
    assert "nextOffset <= 10000" in queue
    assert "innerHTML" not in queue
    assert "item.claimant_name" in row
    assert "cell.textContent = operatingPilotDisplayValue(value)" in row
    assert "operatingPilotAllocateLocations.has(locationId)" in row
    assert "operatingPilotWorkClaimAllocationAcknowledged.checked" in submit
    assert "/work-claims/${encodeURIComponent(pending.claim_id)}/allocate" in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'cache: "no-store"' in submit
    assert "operatingPilotPendingWorkClaimAllocations" in submit
    assert "request_id: requestId" in submit
    assert "does not start or complete the work item" in source
    assert 'scope.action === "allocate"' in source


def test_resource_category_suppression_never_renders_requester_or_narrative_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    resources = _function(
        source,
        "async function loadOperatingPilotResources(append = false)",
        "async function loadOperatingPilotOwnCapacityProfiles(",
    )
    assert 'item.suppressed === true ? "Suppressed (<3 requesters)" : item.request_count' in resources
    assert "item.resource_category" in resources
    for private_field in ("requested_by_party_id", "description", "decision_reason", "urgency"):
        assert private_field not in resources


def test_summary_renders_only_fixed_aggregate_allowlists():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(source, "function renderOperatingPilotSummary(summary)", "function appendOperatingPilotRow(")
    for key in (
        '"work_claims"',
        '"competency_reviews"',
        '"learning_plans"',
        '"resource_requests"',
        '"aggregate_only_coaching_sessions"',
    ):
        assert key in renderer
    assert "Object.entries" not in renderer
    assert "party_id" not in renderer
    assert "participant" not in renderer


def test_location_changes_and_load_more_are_wired_with_bounded_paging():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'operatingPilotLocation.addEventListener("change", () =>' in source
    assert "cancelOperatingPilotCapacityEdit();" in source
    assert 'operatingPilotDemandMore.addEventListener("click", () => loadOperatingPilotDemand(true))' in source
    assert 'operatingPilotCapacityMore.addEventListener("click", () => loadOperatingPilotCapacity(true))' in source
    assert 'operatingPilotWorkClaimsMore.addEventListener("click", () => loadOperatingPilotWorkClaims(true))' in source
    assert 'operatingPilotWorkOpportunitiesMore.addEventListener("click", () => loadOperatingPilotWorkOpportunities(true))' in source
    assert 'operatingPilotResourceMore.addEventListener("click", () => loadOperatingPilotResources(true))' in source
    assert 'operatingPilotOwnCapacityMore.addEventListener("click", () => loadOperatingPilotOwnCapacityProfiles(true))' in source
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in source
    assert source.count("nextOffset <= 10000") >= 4
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_own_capacity_records_use_separate_grant_private_no_store_route_and_safe_cells():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadOperatingPilotOwnCapacityProfiles(append = false)",
        "async function loadOperatingPilot()",
    )
    assert "operatingPilotOwnCapacityLocations.has(locationId)" in reader
    assert "my-capacity-profiles?${params}" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "appendOperatingPilotOwnCapacityRow(item, locationId)" in reader
    assert "innerHTML" not in reader
    assert "nextOffset <= 10000" in reader
    own_row = _function(
        source,
        "function appendOperatingPilotOwnCapacityRow(item, locationId)",
        "async function loadOperatingPilotOwnCapacityProfiles(append = false)",
    )
    assert "item.notes" in own_row
    assert "textContent" in own_row

    initialize = _function(source, "async function loadOperatingPilot()", "function addSequentialEvidenceMetric(")
    no_aggregate_read = initialize.index("if (!operatingPilotLocations.has(locationId))")
    own_profile_fetch = initialize.index("await loadOperatingPilotOwnCapacityProfiles();", no_aggregate_read)
    early_return = initialize.index("return;", own_profile_fetch)
    assert no_aggregate_read < own_profile_fetch < early_return
    assert "operatingPilotOwnCapacityLocations.has(locationId)" in source
    assert "...operatingPilotOwnCapacityLocationIds" in source


def test_own_demand_history_uses_read_own_grant_private_no_store_route_and_safe_cells():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="operating-pilot-own-demand".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "only your receipt-backed demand records and private planning notes" in panel.group()
    assert 'id="operating-pilot-own-demand-rows"' in panel.group()
    assert "operatingPilotOwnDemandLocations = new Set(operatingPilotOwnCapacityLocationIds)" in source
    reader = _function(
        source,
        "async function loadOperatingPilotOwnDemandSignals(append = false)",
        "async function loadOperatingPilotCapacityReviewQueue(",
    )
    row = _function(
        source,
        "function appendOperatingPilotOwnDemandRow(item, locationId)",
        "async function loadOperatingPilotOwnDemandSignals(",
    )
    assert "operatingPilotOwnDemandLocations.has(locationId)" in reader
    assert "my-demand-signals?${params}" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "locationId !== operatingPilotLocation.value" in reader
    assert "item.description" in row
    assert "cell.textContent = operatingPilotDisplayValue(value)" in row
    assert 'id="operating-pilot-demand-edit-cancel"' in source
    assert "Action</th></tr></thead>" in panel.group()
    assert "operatingPilotEditOwnDemandLocations.has(locationId)" in row
    assert '["draft", "rejected"].includes(item.status)' in row
    assert "startOperatingPilotDemandEdit(item, locationId)" in row
    assert "innerHTML" not in row
    assert 'method: "POST"' not in reader
    assert "loadOperatingPilotOwnDemandSignals();" in source
    assert 'operatingPilotOwnDemandMore.addEventListener("click", () => loadOperatingPilotOwnDemandSignals(true))' in source


def test_demand_draft_revision_is_owner_only_idempotent_and_draft_preserving():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotDemandDraft(event)",
        "function cancelOperatingPilotDemandEdit()",
    )
    start = _function(
        source,
        "function startOperatingPilotDemandEdit(item, locationId)",
        "async function submitOperatingPilotDemandSignal()",
    )
    initialize = _function(source, "async function loadOperatingPilot()", "function addSequentialEvidenceMetric(")
    assert "operatingPilotEditOwnDemandLocations.has(locationId)" in submit
    assert "operatingPilotOwnDemandLocations.has(locationId)" in start
    assert '["draft", "rejected"].includes(item.status)' in start
    assert "operatingPilotPendingDemandEdit = { signal_id: item.signal_id, location_id: locationId }" in start
    assert "item.description || \"\"" in start
    assert "method: isEditing ? \"PUT\" : \"POST\"" in submit
    assert "encodeURIComponent(signalId)" in submit
    assert "signalId, ...payload" in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert 'cache: "no-store"' in submit
    assert "operatingPilotPendingDemandCreate.request_id" in submit
    assert "prior version is retained as superseded" in submit
    assert "replacement remains private and unsubmitted" in submit
    assert "operatingPilotDemandCreate.hidden = !operatingPilotCreateLocations.has(locationId)" in initialize
    assert "operatingPilotOwnDemandLocations.has(locationId)" in initialize
    assert "operatingPilotEditOwnDemandLocations.has(locationId)" in initialize
    assert "loadOperatingPilotOwnDemandSignals();" in submit


def test_demand_draft_form_is_create_grant_gated_and_never_submits_or_approves():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotDemandDraft(event)",
        "function cancelOperatingPilotDemandEdit()",
    )
    assert "operatingPilotCreateLocations.has(locationId)" in submit
    assert "const csrf = csrfToken()" in submit
    assert 'method: isEditing ? "PUT" : "POST", credentials: "same-origin", cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "crypto.randomUUID()" in submit
    assert "operatingPilotPendingDemandCreate.request_id" in submit
    assert 'result.replayed' in submit
    assert "It remains private and unsubmitted." in submit
    assert "/approve" not in submit.lower()
    assert "/submit" not in submit.lower()


def test_capacity_draft_form_is_create_grant_gated_and_never_submits_or_approves():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotCapacityDraft(event)",
        "async function submitOperatingPilotResourceDraft(event)",
    )
    assert "operatingPilotCreateLocations.has(locationId)" in submit
    assert "const csrf = csrfToken()" in submit
    assert 'method: isEditing ? "PUT" : "POST", credentials: "same-origin", cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "crypto.randomUUID()" in submit
    assert "operatingPilotPendingCapacityCreate.request_id" in submit
    assert "/capacity-profiles" in submit
    assert "private and unsubmitted" in submit
    assert "/approve" not in submit.lower()
    assert "/submit" not in submit.lower()
    assert "operatingPilotCapacityCreate.hidden = !operatingPilotCreateLocations.has(locationId)\n          && !(operatingPilotOwnCapacityLocations.has(locationId)" in source
    assert 'scope.action === "edit_own"' in source


def test_capacity_revision_replaces_only_own_draft_under_separate_edit_own_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotCapacityDraft(event)",
        "function cancelOperatingPilotCapacityEdit()",
    )
    edit_row = _function(
        source,
        "function appendOperatingPilotOwnCapacityRow(item, locationId)",
        "async function loadOperatingPilotOwnCapacityProfiles(append = false)",
    )
    assert "operatingPilotEditOwnCapacityLocations.has(locationId)" in submit
    assert "method: isEditing ? \"PUT\" : \"POST\"" in submit
    assert "encodeURIComponent(profileId)" in submit
    assert "profileId, ...payload" in submit
    assert "operatingPilotPendingCapacityCreate.request_id" in submit
    assert "prior version is retained as superseded" in submit
    assert '["draft", "rejected"].includes(item.status) && item.source === "self_reported"' in edit_row
    assert "startOperatingPilotCapacityEdit(item, locationId)" in edit_row
    assert "innerHTML" not in edit_row
    assert "operatingPilotOwnCapacityLocations.has(locationId)" in source
    assert "operatingPilotEditOwnCapacityLocations.has(locationId)" in source
    assert 'id="operating-pilot-capacity-edit-cancel"' in source


def test_capacity_submission_is_explicit_idempotent_and_separately_granted():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotCapacityProfile(item, locationId, button)",
        "async function loadOperatingPilotSummary()",
    )
    own_row = _function(
        source,
        "function appendOperatingPilotOwnCapacityRow(item, locationId)",
        "async function loadOperatingPilotOwnCapacityProfiles(append = false)",
    )
    assert "operatingPilotSubmitOwnCapacityLocations.has(locationId)" in submit
    assert "window.confirm(" in submit
    assert "cannot be edited after submission" in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "operatingPilotPendingCapacitySubmissions.set(item.profile_id, requestId)" in submit
    assert "operatingPilotPendingCapacitySubmissions.delete(item.profile_id)" in submit
    assert "Retry keeps the same request ID." in submit
    assert "hasPendingSubmission" in own_row
    assert "Submit for independent review" in own_row
    assert "Retry capacity submission" in own_row
    assert 'scope.action === "submit_own"' in source
    assert "/approve" not in submit.lower()


def test_demand_submission_is_separate_confirmed_and_retries_with_same_request_id():
    source = CONSOLE.read_text(encoding="utf-8")
    create = _function(
        source,
        "async function submitOperatingPilotDemandDraft(event)",
        "function cancelOperatingPilotDemandEdit()",
    )
    submit = _function(
        source,
        "async function submitOperatingPilotDemandSignal()",
        "async function submitOperatingPilotCapacityDraft(event)",
    )
    initialize = _function(
        source,
        "async function loadOperatingPilot()",
        "function addSequentialEvidenceMetric(",
    )
    assert "result.signal_id" in create
    assert 'method: isEditing ? "PUT" : "POST"' in create
    assert 'id="operating-pilot-demand-submit"' in source
    assert "operatingPilotPendingDemandSubmission" in create
    assert "operatingPilotSubmitOwnDemandLocations.has(locationId)" in submit
    assert "window.confirm(" in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "pending.request_id" in submit
    assert "Retry unchanged to reuse the same request ID." in submit
    assert "/demand-signals/${encodeURIComponent(pending.signal_id)}/submit" in submit
    assert "Demand draft submitted for independent review. It has not been approved or fulfilled." in submit
    assert '"verified", "published", "rejected"' in submit
    assert "The prior submission was accepted. Current lifecycle status:" in submit
    assert 'scope.action === "submit_own"' in source
    assert "operatingPilotSubmitOwnDemandLocations = new Set(operatingPilotSubmitOwnDemandLocationIds)" in source
    assert "syncOperatingPilotDemandSubmissionAction();" in initialize
    assert "...operatingPilotSubmitOwnDemandLocationIds" in source
    assert "/approve" not in submit.lower()
    assert "/fulfill" not in submit.lower()


def test_capacity_review_queue_has_separate_grant_and_omits_identity_and_notes():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadOperatingPilotCapacityReviewQueue(append = false)",
        "async function loadOperatingPilot()",
    )
    initialize = _function(source, "async function loadOperatingPilot()", "function addSequentialEvidenceMetric(")
    assert "operatingPilotCapacityReviewLocations.has(locationId)" in reader
    assert "capacity-review-queue?${params}" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "appendOperatingPilotCapacityReviewRow(item, locationId)" in reader
    assert "innerHTML" not in reader
    assert "party_id" not in reader
    assert "item.notes" not in reader
    assert "requestVersion !== operatingPilotCapacityReviewRequestVersion" in reader
    assert "locationId !== operatingPilotLocation.value" in reader
    assert "No review decision was recorded." in reader
    assert "operatingPilotCapacityReview.hidden = !operatingPilotCapacityReviewLocations.has(locationId)" in initialize
    assert "reads.push(loadOperatingPilotCapacityReviewQueue())" in initialize
    assert "await loadOperatingPilotCapacityReviewQueue()" in initialize
    assert "...operatingPilotCapacityReviewLocationIds" in source
    assert 'click", () => loadOperatingPilotCapacityReviewQueue(true)' in source


def test_demand_review_queue_is_bounded_redacted_and_review_grant_gated():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadOperatingPilotDemandReviewQueue(append = false)",
        "function appendOperatingPilotDemandReviewRow(item, locationId)",
    )
    row = _function(
        source,
        "function appendOperatingPilotDemandReviewRow(item, locationId)",
        "function syncOperatingPilotDemandReviewReason()",
    )
    initialize = _function(source, "async function loadOperatingPilot()", "function addSequentialEvidenceMetric(")
    assert "operatingPilotCapacityReviewLocations.has(locationId)" in reader
    assert "demand-review-queue?${params}" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "appendOperatingPilotDemandReviewRow(item, locationId)" in reader
    assert "requestVersion !== operatingPilotDemandReviewRequestVersion" in reader
    assert "locationId !== operatingPilotLocation.value" in reader
    assert "innerHTML" not in reader + row
    assert "description" not in row
    assert "party_id" not in row
    assert "cell.textContent = operatingPilotDisplayValue(value)" in row
    assert "Review submission" in row
    assert "operatingPilotCapacityReviewLocations.has(locationId)" in row
    assert "operatingPilotDemandReview.hidden = !operatingPilotCapacityReviewLocations.has(locationId)" in initialize
    assert "reads.push(loadOperatingPilotDemandReviewQueue())" in initialize
    assert "await loadOperatingPilotDemandReviewQueue()" in initialize
    assert 'click", () => loadOperatingPilotDemandReviewQueue(true)' in source


def test_demand_review_decision_is_independent_acknowledged_and_idempotent():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotDemandReview(event)",
        "async function loadOperatingPilot()",
    )
    assert "operatingPilotPendingDemandReview" in submit
    assert "operatingPilotCapacityReviewLocations.has(pending.location_id)" in submit
    assert "operatingPilotDemandReviewAcknowledged.checked" in submit
    assert 'decision === "rejected" && !reason' in submit
    assert "operatingPilotPendingDemandReviewDecisions.get(pending.signal_id)" in submit
    assert "crypto.randomUUID()" in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "/demand-signals/${encodeURIComponent(pending.signal_id)}/review" in submit
    assert "Fulfillment remains separate." in submit
    assert "operatingPilotDemandReviewDialog.close()" in submit
    assert "loadOperatingPilotDemandReviewQueue()" in submit
    assert "/fulfill" not in submit.lower()


def test_capacity_review_decision_requires_acknowledgement_csrf_and_exact_retry_id():
    source = CONSOLE.read_text(encoding="utf-8")
    row = _function(
        source,
        "function appendOperatingPilotCapacityReviewRow(item, locationId)",
        "function syncOperatingPilotCapacityReviewReason()",
    )
    submit = _function(
        source,
        "async function submitOperatingPilotCapacityReview(event)",
        "async function loadOperatingPilot()",
    )
    assert "operatingPilotCapacityReviewLocations.has(locationId)" in row
    assert 'review.textContent = "Review submission"' in row
    assert 'operatingPilotCapacityReviewReason.required = rejecting' in source
    assert "if (decision === \"rejected\" && !reason)" in submit
    assert "operatingPilotCapacityReviewAcknowledged.checked" in submit
    assert "operatingPilotPendingCapacityReviewDecisions.get(pending.profile_id)" in submit
    assert "pendingRequest.signature !== signature" in submit
    assert "crypto.randomUUID()" in submit
    assert "csrfToken()" in submit
    assert 'method: "POST"' in submit
    assert 'credentials: "same-origin"' in submit
    assert 'cache: "no-store"' in submit
    assert '"X-CSRF-Token": csrf' in submit
    assert "/capacity-profiles/${encodeURIComponent(pending.profile_id)}/review" in submit
    assert "operatingPilotPendingCapacityReviewDecisions.delete(pending.profile_id)" in submit
    assert "Retry with the same decision and reason to reuse the request ID." in submit


def test_rejected_own_capacity_records_can_be_revised_but_not_resubmitted_as_is():
    source = CONSOLE.read_text(encoding="utf-8")
    edit = _function(
        source,
        "function startOperatingPilotCapacityEdit(item, locationId)",
        "function appendOperatingPilotOwnCapacityRow(item, locationId)",
    )
    row = _function(
        source,
        "function appendOperatingPilotOwnCapacityRow(item, locationId)",
        "async function submitOperatingPilotCapacityProfile(item, locationId, button)",
    )
    assert '["draft", "rejected"].includes(item.status)' in edit
    assert '["draft", "rejected"].includes(item.status)' in row
    assert 'item.status === "rejected" ? "Revise rejected submission"' in row
    assert 'item.status === "draft" || hasPendingSubmission' in row


def test_create_only_location_can_open_draft_form_without_reading_queues():
    source = CONSOLE.read_text(encoding="utf-8")
    initialize = _function(source, "async function loadOperatingPilot()", "function addSequentialEvidenceMetric(")
    assert '...operatingPilotCreateLocationIds' in source
    assert "operatingPilotCapacityCreate.hidden = !operatingPilotCreateLocations.has(locationId)" in initialize
    read_denial = initialize.index('if (!operatingPilotLocations.has(locationId))')
    early_return = initialize.index("return;", read_denial)
    queue_reads = initialize.index("const reads = [", read_denial)
    assert early_return < queue_reads


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
