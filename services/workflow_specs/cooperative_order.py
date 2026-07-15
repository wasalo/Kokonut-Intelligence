"""Cooperative Order lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


SPEC_NAME = register(WorkflowSpec(
    id="cooperative_order",
    title="Cooperative Order Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "order requires cooperative_id, order_name, target quantity and price",
        "verification confirms participant commitments",
        "publication enables collective procurement",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("co_draft_entry", "member", "draft", "Create cooperative order", entry=True, transitions=(
            Transition("co_submit", "submitted", "submit for verification", "submit"),
            Transition("co_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("co_submit", "member", "submitted", "Submit cooperative order for review", transitions=(
            Transition("co_verify", "verified", "participant commitments confirmed", "verify"),
            Transition("co_reject_submitted", "rejected", "insufficient commitments", "reject"),
        )),
        Step("co_verify", "coordinator", "verified", "Verify cooperative order commitments", human_approval=True, transitions=(
            Transition("co_publish", "published", "approved for collective procurement", "publish"),
            Transition("co_reject_verified", "rejected", "order requirements not met", "reject"),
        )),
        Step("co_publish", "system", "published", "Terminal published cooperative order", terminal=True),
        Step("co_reject_draft", "coordinator", "rejected", "Terminal rejected cooperative order", terminal=True),
        Step("co_reject_submitted", "coordinator", "rejected", "Terminal rejected cooperative order", terminal=True),
        Step("co_reject_verified", "coordinator", "rejected", "Terminal rejected cooperative order", terminal=True),
    ),
))
