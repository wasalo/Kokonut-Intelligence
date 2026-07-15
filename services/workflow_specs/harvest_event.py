"""Harvest event lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


HARVEST_EVENT = register(WorkflowSpec(
    id="harvest_event",
    title="Harvest Event Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "A harvest event begins in draft, recorded by a farmer or field worker.",
        "Harvest events require plot_id, crop_id, and harvest_date.",
        "Verification confirms the harvest occurred and yield data is accurate.",
        "Publication makes the harvest available for yield analytics and carbon accounting.",
        "Rejection is terminal and requires a reason.",
    ),
    source_refs=(
        "schemas/postgres/003_operations.sql",
        "schemas/postgres/137_yield_monitoring.sql",
    ),
    steps=(
        Step("he_draft_entry", "farmer", "draft", "Record harvest event", entry=True, transitions=(
            Transition("he_submit", "submitted", "submit for verification", "submit"),
            Transition("he_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("he_submit", "farmer", "submitted", "Submit harvest for verification", transitions=(
            Transition("he_verify", "verified", "harvest confirmed", "verify"),
            Transition("he_reject_submitted", "rejected", "harvest not confirmed", "reject"),
        )),
        Step("he_verify", "reviewer", "verified", "Verify harvest data", human_approval=True, transitions=(
            Transition("he_publish", "published", "approved for analytics", "publish"),
            Transition("he_reject_verified", "rejected", "yield data inaccurate", "reject"),
        )),
        Step("he_publish", "system", "published", "Terminal published harvest", terminal=True),
        Step("he_reject_draft", "reviewer", "rejected", "Terminal rejected harvest", terminal=True),
        Step("he_reject_submitted", "reviewer", "rejected", "Terminal rejected harvest", terminal=True),
        Step("he_reject_verified", "reviewer", "rejected", "Terminal rejected harvest", terminal=True),
    ),
))
