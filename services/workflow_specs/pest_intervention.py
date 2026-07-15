"""Pest Intervention lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


SPEC_NAME = register(WorkflowSpec(
    id="pest_intervention",
    title="Pest Intervention Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "intervention requires scouting_id, type, method",
        "verification confirms IPM compliance",
        "publication records intervention for resistance tracking",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("pi_draft_entry", "farmer", "draft", "Create pest intervention", entry=True, transitions=(
            Transition("pi_submit", "submitted", "submit for verification", "submit"),
            Transition("pi_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("pi_submit", "farmer", "submitted", "Submit pest intervention for review", transitions=(
            Transition("pi_verify", "verified", "IPM compliance confirmed", "verify"),
            Transition("pi_reject_submitted", "rejected", "IPM non-compliance", "reject"),
        )),
        Step("pi_verify", "reviewer", "verified", "Verify pest intervention compliance", human_approval=True, transitions=(
            Transition("pi_publish", "published", "approved for resistance tracking", "publish"),
            Transition("pi_reject_verified", "rejected", "intervention rejected", "reject"),
        )),
        Step("pi_publish", "system", "published", "Terminal published pest intervention", terminal=True),
        Step("pi_reject_draft", "reviewer", "rejected", "Terminal rejected pest intervention", terminal=True),
        Step("pi_reject_submitted", "reviewer", "rejected", "Terminal rejected pest intervention", terminal=True),
        Step("pi_reject_verified", "reviewer", "rejected", "Terminal rejected pest intervention", terminal=True),
    ),
))
