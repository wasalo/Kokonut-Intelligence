"""Market Order lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


SPEC_NAME = register(WorkflowSpec(
    id="market_order",
    title="Market Order Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "order requires listing_id, buyer_id, quantity",
        "verification confirms payment and shipping",
        "publication records completed transaction",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("mo_draft_entry", "buyer", "draft", "Create market order", entry=True, transitions=(
            Transition("mo_submit", "submitted", "submit for verification", "submit"),
            Transition("mo_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("mo_submit", "buyer", "submitted", "Submit market order for review", transitions=(
            Transition("mo_verify", "verified", "payment and shipping confirmed", "verify"),
            Transition("mo_reject_submitted", "rejected", "payment failed", "reject"),
        )),
        Step("mo_verify", "seller", "verified", "Verify market order payment and shipping", human_approval=True, transitions=(
            Transition("mo_publish", "published", "approved for transaction recording", "publish"),
            Transition("mo_reject_verified", "rejected", "order fulfillment failed", "reject"),
        )),
        Step("mo_publish", "system", "published", "Terminal published market order", terminal=True),
        Step("mo_reject_draft", "seller", "rejected", "Terminal rejected market order", terminal=True),
        Step("mo_reject_submitted", "seller", "rejected", "Terminal rejected market order", terminal=True),
        Step("mo_reject_verified", "seller", "rejected", "Terminal rejected market order", terminal=True),
    ),
))
