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
    assert 'id="operating-pilot-own-capacity-rows"' in panel.group()
    assert 'id="operating-pilot-capacity-review-rows"' in panel.group()
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
    claims = _function(source, "async function loadOperatingPilotWorkClaims(append = false)", "async function loadOperatingPilot()")
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
        "async function loadOperatingPilot()",
    )
    assert 'item.suppressed === true ? "Suppressed (<3 contributors)" : item.claim_count' in claims
    assert "item.work_type" in claims
    for private_field in ("claim_id", "work_item_id", "claimant_party_id", "decision_reason"):
        assert private_field not in claims


def test_resource_category_suppression_never_renders_requester_or_narrative_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    resources = _function(
        source,
        "async function loadOperatingPilotResources(append = false)",
        "async function loadOperatingPilot()",
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


def test_demand_draft_form_is_create_grant_gated_and_never_submits_or_approves():
    source = CONSOLE.read_text(encoding="utf-8")
    submit = _function(
        source,
        "async function submitOperatingPilotDemandDraft(event)",
        "async function submitOperatingPilotDemandSignal()",
    )
    assert "operatingPilotCreateLocations.has(locationId)" in submit
    assert "const csrf = csrfToken()" in submit
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit
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
        "function cancelOperatingPilotCapacityEdit()",
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
        "async function submitOperatingPilotDemandSignal()",
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
    assert "isEditing" not in create
    assert "result.signal_id" in create
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
