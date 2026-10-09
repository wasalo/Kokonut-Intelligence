"""Work item lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

_LOOP = "Assignment and blocking are reversible before completion; bounded by human decisions."


WORK_ITEM = register(WorkflowSpec(
    id="work_item",
    title="Work Item Lifecycle",
    states=frozenset({"draft", "assigned", "in_progress", "blocked", "done", "cancelled"}),
    invariants=(
        "A work item cannot leave draft without an assignee.",
        "An item must be assigned before it can be started.",
        "blocked requires a reason recorded in work_item_event.",
        "done requires an assignee and a recorded completion event.",
        "cancelled is terminal and may be reached from any non-terminal state.",
        "Exactly one accountable responsibility should exist before work starts (RACI).",
    ),
    source_refs=(
        "schemas/postgres/175_management_work_items.sql",
        "services/management/workbench.py",
        "services/management/responsibility.py",
    ),
    steps=(
        Step("draft_entry", "manager", "draft", "Create work item", entry=True, transitions=(
            Transition("assign", "assigned", "has assignee", "assign"),
            Transition("cancel_draft", "cancelled", "rejected before assignment", "cancel"),
        )),
        Step("assign", "manager", "assigned", "Assign owner", transitions=(
            Transition("start", "in_progress", "work begins", "start"),
            Transition("unassign", "draft", "owner removed", "unassign", loop_rationale=_LOOP),
            Transition("cancel_assigned", "cancelled", "cancelled while assigned", "cancel"),
        )),
        Step("unassign", "manager", "draft", "Return to draft without owner", transitions=(
            Transition("assign", "assigned", "reassigned", "assign", loop_rationale=_LOOP),
            Transition("cancel_draft", "cancelled", "cancelled in draft", "cancel"),
        )),
        Step("start", "worker", "in_progress", "Begin work", transitions=(
            Transition("block", "blocked", "impediment found", "block", loop_rationale=_LOOP),
            Transition("complete", "done", "work finished", "complete"),
            Transition("cancel_active", "cancelled", "cancelled in progress", "cancel"),
        )),
        Step("block", "worker", "blocked", "Record impediment", transitions=(
            Transition("unblock", "in_progress", "impediment cleared", "unblock", loop_rationale=_LOOP),
            Transition("cancel_active", "cancelled", "cancelled while blocked", "cancel"),
        )),
        Step("unblock", "worker", "in_progress", "Resume work", transitions=(
            Transition("block", "blocked", "re-impediment", "block", loop_rationale=_LOOP),
            Transition("complete", "done", "work finished", "complete"),
            Transition("cancel_active", "cancelled", "cancelled in progress", "cancel"),
        )),
        Step("complete", "worker", "done", "Terminal completed work item", terminal=True),
        Step("cancel_draft", "manager", "cancelled", "Terminal cancelled item", terminal=True),
        Step("cancel_assigned", "manager", "cancelled", "Terminal cancelled item", terminal=True),
        Step("cancel_active", "manager", "cancelled", "Terminal cancelled item", terminal=True),
    ),
))
