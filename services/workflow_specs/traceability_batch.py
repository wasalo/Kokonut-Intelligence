"""Traceability Batch lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

SPEC_NAME = register(WorkflowSpec(
    id="traceability_batch",
    title="Traceability Batch Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "batch requires location_id, crop, quantity, harvest_date",
        "verification confirms custody chain integrity",
        "publication enables provenance tracking",
    ),
    source_refs=(
        "schemas/postgres/003_operations.sql",
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("tb_draft_entry", "farmer", "draft", "Create traceability batch", entry=True, transitions=(
            Transition("tb_submit", "submitted", "submit for verification", "submit"),
            Transition("tb_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("tb_submit", "farmer", "submitted", "Submit traceability batch for review", transitions=(
            Transition("tb_verify", "verified", "custody chain verified", "verify"),
            Transition("tb_reject_submitted", "rejected", "custody chain invalid", "reject"),
        )),
        Step("tb_verify", "reviewer", "verified", "Verify traceability batch integrity", human_approval=True, transitions=(
            Transition("tb_publish", "published", "approved for provenance tracking", "publish"),
            Transition("tb_reject_verified", "rejected", "integrity check failed", "reject"),
        )),
        Step("tb_publish", "system", "published", "Terminal published traceability batch", terminal=True),
        Step("tb_reject_draft", "reviewer", "rejected", "Terminal rejected traceability batch", terminal=True),
        Step("tb_reject_submitted", "reviewer", "rejected", "Terminal rejected traceability batch", terminal=True),
        Step("tb_reject_verified", "reviewer", "rejected", "Terminal rejected traceability batch", terminal=True),
    ),
))
