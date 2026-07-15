"""Insurance Claim lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


SPEC_NAME = register(WorkflowSpec(
    id="insurance_claim",
    title="Insurance Claim Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "claim requires policy_id, type, amount, evidence",
        "verification confirms claim validity",
        "publication enables payout processing",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("ic_draft_entry", "farmer", "draft", "Create insurance claim", entry=True, transitions=(
            Transition("ic_submit", "submitted", "submit for verification", "submit"),
            Transition("ic_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("ic_submit", "farmer", "submitted", "Submit insurance claim for review", transitions=(
            Transition("ic_verify", "verified", "claim evidence confirmed", "verify"),
            Transition("ic_reject_submitted", "rejected", "insufficient evidence", "reject"),
        )),
        Step("ic_verify", "reviewer", "verified", "Verify insurance claim validity", human_approval=True, transitions=(
            Transition("ic_publish", "published", "approved for payout processing", "publish"),
            Transition("ic_reject_verified", "rejected", "claim invalid", "reject"),
        )),
        Step("ic_publish", "system", "published", "Terminal published insurance claim", terminal=True),
        Step("ic_reject_draft", "reviewer", "rejected", "Terminal rejected insurance claim", terminal=True),
        Step("ic_reject_submitted", "reviewer", "rejected", "Terminal rejected insurance claim", terminal=True),
        Step("ic_reject_verified", "reviewer", "rejected", "Terminal rejected insurance claim", terminal=True),
    ),
))
