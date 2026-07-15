"""Impact claim lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


IMPACT_CLAIM = register(WorkflowSpec(
    id="impact_claim",
    title="Impact Claim Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "An impact claim begins in draft and requires evidence.",
        "Public impact claims require evidence maturity >= 4.",
        "Public carbon claims require evidence maturity 6, claim_type='third_party_verified_claim', and published status.",
        "Verification is a human decision; agents cannot verify claims.",
        "Rejection is terminal and requires a reason.",
    ),
    source_refs=(
        "schemas/postgres/031_impact_claims_and_cids.sql",
        "services/agents/tasks.py",
    ),
    steps=(
        Step("ic_draft_entry", "author", "draft", "Create impact claim", entry=True, transitions=(
            Transition("ic_submit", "submitted", "submit for review", "submit"),
            Transition("ic_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("ic_submit", "author", "submitted", "Submit claim for review", transitions=(
            Transition("ic_verify", "verified", "evidence reviewed and verified", "verify"),
            Transition("ic_reject_submitted", "rejected", "insufficient evidence", "reject"),
        )),
        Step("ic_verify", "reviewer", "verified", "Verify claim evidence", human_approval=True, transitions=(
            Transition("ic_publish", "published", "approved for publication", "publish"),
            Transition("ic_reject_verified", "rejected", "evidence insufficient for publication", "reject"),
        )),
        Step("ic_publish", "system", "published", "Terminal published claim", terminal=True),
        Step("ic_reject_draft", "reviewer", "rejected", "Terminal rejected claim", terminal=True),
        Step("ic_reject_submitted", "reviewer", "rejected", "Terminal rejected claim", terminal=True),
        Step("ic_reject_verified", "reviewer", "rejected", "Terminal rejected claim", terminal=True),
    ),
))
