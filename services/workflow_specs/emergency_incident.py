"""Emergency Incident lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


SPEC_NAME = register(WorkflowSpec(
    id="emergency_incident",
    title="Emergency Incident Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "incident requires type, severity, description, affected_area",
        "verification confirms response actions",
        "publication enables compliance reporting",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("ei_draft_entry", "farmer", "draft", "Create emergency incident report", entry=True, transitions=(
            Transition("ei_submit", "submitted", "submit for verification", "submit"),
            Transition("ei_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("ei_submit", "farmer", "submitted", "Submit emergency incident for review", transitions=(
            Transition("ei_verify", "verified", "response actions confirmed", "verify"),
            Transition("ei_reject_submitted", "rejected", "incident details invalid", "reject"),
        )),
        Step("ei_verify", "reviewer", "verified", "Verify emergency incident response", human_approval=True, transitions=(
            Transition("ei_publish", "published", "approved for compliance reporting", "publish"),
            Transition("ei_reject_verified", "rejected", "incident response inadequate", "reject"),
        )),
        Step("ei_publish", "system", "published", "Terminal published emergency incident", terminal=True),
        Step("ei_reject_draft", "reviewer", "rejected", "Terminal rejected emergency incident", terminal=True),
        Step("ei_reject_submitted", "reviewer", "rejected", "Terminal rejected emergency incident", terminal=True),
        Step("ei_reject_verified", "reviewer", "rejected", "Terminal rejected emergency incident", terminal=True),
    ),
))
