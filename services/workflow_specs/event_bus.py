"""Durable event delivery and dead-letter workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

_LOOP = "Bounded by enabled handlers, max_retries, lease expiry, and operator disposition."

EVENT_BUS = register(WorkflowSpec(
    id="event_bus_delivery",
    title="Durable Event Bus Delivery",
    states=frozenset({"pending", "processing", "delivery_processing", "completed", "dead_letter", "disposed", "deferred", "lease_lost"}),
    invariants=(
        "The event claim commits before any handler executes.",
        "Only the current lease owner may complete, retry, or dead-letter an event.",
        "A successful handler delivery is not intentionally invoked again during normal retry or replay.",
        "Handler effects are at-least-once; handlers must make external effects idempotent.",
        "An event completes only after every enabled handler has a successful delivery or no handlers are enabled.",
        "Retries are bounded by max_retries and final failure creates one pending dead-letter disposition.",
        "Replay and disposal are explicit operator actions; disposal is terminal.",
    ),
    source_refs=("services/events/bus.py", "schemas/postgres/116_event_bus.sql", "schemas/postgres/165_event_bus_durability.sql"),
    steps=(
        Step("claim", "worker", "pending", "Atomically claim event and create lease", entry=True, transaction_boundary=True, retry_safe=True, transitions=(
            Transition("load_handlers", "processing", "claim acquired", "process", loop_rationale=_LOOP),
            Transition("deferred", "deferred", "not due or locked", "leave pending"),
        )),
        Step("deferred", "worker", "deferred", "Stop this polling attempt", terminal=True, retry_safe=True),
        Step("load_handlers", "worker", "processing", "Load enabled handlers", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("complete", "processing", "no enabled handlers or every delivery succeeded", "complete", loop_rationale=_LOOP),
            Transition("lease_check", "processing", "handler remains", "deliver", loop_rationale=_LOOP),
        )),
        Step("lease_check", "worker", "processing", "Extend and verify event lease", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("mark_delivery", "processing", "lease owned", "prepare", loop_rationale=_LOOP),
            Transition("lease_lost", "lease_lost", "lease not owned", "stop"),
        )),
        Step("lease_lost", "worker", "lease_lost", "Stop without changing another worker's event", terminal=True, retry_safe=True),
        Step("mark_delivery", "worker", "processing", "Persist handler delivery as processing", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("invoke", "delivery_processing", "delivery not already successful", "invoke", loop_rationale=_LOOP),
            Transition("load_handlers", "processing", "delivery already successful", "skip", loop_rationale=_LOOP),
        )),
        Step("invoke", "handler process", "delivery_processing", "Invoke handler with bounded timeout", external_side_effect=True, transitions=(
            Transition("record_success", "processing", "handler returns success", "success", loop_rationale=_LOOP),
            Transition("record_failure", "processing", "error, timeout, or missing result", "failure", loop_rationale=_LOOP),
        )),
        Step("record_success", "worker", "processing", "Persist successful delivery and attempt log", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("load_handlers", "processing", "more handlers may remain", "continue", loop_rationale=_LOOP),
        )),
        Step("record_failure", "worker", "processing", "Persist failed delivery and attempt log", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("retry_decision", "processing", "all handlers visited", "evaluate retry", loop_rationale=_LOOP),
        )),
        Step("retry_decision", "worker", "processing", "Conditionally retry or dead-letter under lease ownership", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("claim", "pending", "attempts remain", "retry", bounded_retry=True, loop_rationale=_LOOP),
            Transition("dead_letter", "dead_letter", "retry limit reached", "dead letter", loop_rationale=_LOOP),
            Transition("lease_lost", "lease_lost", "lease ownership changed", "stop"),
        )),
        Step("complete", "worker", "processing", "Conditionally mark event completed and clear lease", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("completed", "completed", "lease owner update succeeds", "completed"),
            Transition("lease_lost", "lease_lost", "lease owner update changes no row", "stop"),
        )),
        Step("completed", "system", "completed", "Terminal completed event", terminal=True, retry_safe=True),
        Step("dead_letter", "worker", "dead_letter", "Persist event and pending dead-letter atomically", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("operator_review", "dead_letter", "operator investigates", "review", loop_rationale=_LOOP),
        )),
        Step("operator_review", "human operator", "dead_letter", "Choose replay, resolve, or discard", human_approval=True, transitions=(
            Transition("claim", "pending", "replay with original event present", "replay", bounded_retry=True, loop_rationale=_LOOP),
            Transition("disposed", "disposed", "resolve or discard with reason", "dispose"),
            Transition("disposed", "disposed", "original event missing", "reject replay"),
        )),
        Step("disposed", "system", "disposed", "Terminal operator disposition", terminal=True, retry_safe=True),
    ),
))
