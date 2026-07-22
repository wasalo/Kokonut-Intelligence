"""Market Order lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

SPEC_NAME = register(WorkflowSpec(
    id="market_order",
    title="Market Order Lifecycle",
    states=frozenset({"pending", "confirmed", "shipped", "delivered", "cancelled"}),
    invariants=(
        "order requires listing_id, buyer_id, quantity",
        "confirmation records payment and fulfillment acceptance",
        "delivery records completed transaction",
    ),
    source_refs=(
        "schemas/postgres/186_process_state_models.sql",
        "schemas/postgres/187_state_model_triggers.sql",
    ),
    steps=(
        Step("mo_pending_entry", "buyer", "pending", "Create market order", entry=True, transitions=(
            Transition("mo_confirm", "confirmed", "payment and fulfillment accepted", "confirm"),
            Transition("mo_cancel", "cancelled", "withdrawn before confirmation", "cancel"),
        )),
        Step("mo_confirm", "seller", "confirmed", "Confirm market order", human_approval=True, transitions=(
            Transition("mo_ship", "shipped", "order handed to carrier", "ship"),
            Transition("mo_cancel", "cancelled", "fulfillment failed", "cancel"),
        )),
        Step("mo_ship", "carrier", "shipped", "Ship market order", transitions=(
            Transition("mo_deliver", "delivered", "order received", "deliver"),
            Transition("mo_cancel", "cancelled", "delivery failed", "cancel"),
        )),
        Step("mo_deliver", "carrier", "delivered", "Terminal delivered market order", terminal=True),
        Step("mo_cancel", "seller", "cancelled", "Terminal cancelled market order", terminal=True),
    ),
))
