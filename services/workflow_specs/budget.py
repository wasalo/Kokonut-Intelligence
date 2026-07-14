"""Financial plan (budget) lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

BUDGET = register(WorkflowSpec(
    id="budget",
    title="Financial Plan Lifecycle",
    states=frozenset({"draft", "approved", "active", "closed", "cancelled"}),
    invariants=(
        "A plan cannot be activated before it is approved.",
        "Approval is a human decision; agents cannot approve or close a plan.",
        "Actuals are derived from verified expense_event and revenue_event rows.",
        "Closing a plan is terminal.",
    ),
    source_refs=(
        "schemas/postgres/176_financial_planning.sql",
        "services/planning/budget.py",
    ),
    steps=(
        Step("budget_draft", "planner", "draft", "Create financial plan", entry=True, transitions=(
            Transition("budget_approve", "approved", "approved by reviewer", "approve"),
            Transition("budget_cancel_draft", "cancelled", "cancelled before approval", "cancel"),
        )),
        Step("budget_approve", "human reviewer", "approved", "Review and approve plan",
             human_approval=True, transitions=(
            Transition("budget_activate", "active", "activate plan", "activate"),
            Transition("budget_cancel_approved", "cancelled", "cancelled after approval", "cancel"),
        )),
        Step("budget_activate", "planner", "active", "Put plan into effect", transitions=(
            Transition("budget_close", "closed", "period closed", "close"),
            Transition("budget_cancel_active", "cancelled", "cancelled while active", "cancel"),
        )),
        Step("budget_close", "planner", "closed", "Terminal closed plan", terminal=True),
        Step("budget_cancel_draft", "planner", "cancelled", "Terminal cancelled plan", terminal=True),
        Step("budget_cancel_approved", "planner", "cancelled", "Terminal cancelled plan", terminal=True),
        Step("budget_cancel_active", "planner", "cancelled", "Terminal cancelled plan", terminal=True),
    ),
))
