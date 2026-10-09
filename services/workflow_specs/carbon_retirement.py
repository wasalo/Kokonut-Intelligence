"""Carbon retirement reservation and independent confirmation specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

CARBON_RETIREMENT = register(WorkflowSpec(
    id="carbon_retirement",
    title="Carbon Credit Retirement",
    states=frozenset({"requested", "draft", "submitted", "reviewed_draft", "reviewed_submitted", "verified", "rejected", "cancelled", "error"}),
    invariants=(
        "issuable_tonnes, retired_tonnes, and reserved_tonnes remain nonnegative.",
        "retired_tonnes + reserved_tonnes never exceeds issuable_tonnes.",
        "Creating a draft changes reserved_tonnes by +Q and retired_tonnes by 0.",
        "Confirmation changes reserved_tonnes by -Q and retired_tonnes by +Q atomically.",
        "Rejection or cancellation changes reserved_tonnes by -Q and retired_tonnes by 0 atomically.",
        "Permanent retirement requires an independent human reviewer distinct from the requester.",
        "Terminal reviews never mutate balances a second time.",
        "Certificates are ineligible until retirement is independently confirmed.",
    ),
    source_refs=("services/analytics/carbon_credits.py", "schemas/postgres/078_carbon_credits.sql", "schemas/postgres/163_carbon_retirement_integrity.sql"),
    steps=(
        Step("validate_request", "requester", "requested", "Validate quantity, requester, credit eligibility, availability, and idempotency", entry=True, transitions=(
            Transition("reserve", "requested", "new valid request", "reserve"),
            Transition("terminal_existing", "verified", "matching terminal idempotency key", "return existing"),
            Transition("draft_existing", "draft", "matching draft idempotency key", "return existing"),
            Transition("request_error", "error", "invalid, unavailable, or conflicting request", "reject"),
        )),
        Step("reserve", "system", "requested", "Lock credit, reserve Q, and create draft retirement atomically", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("draft", "draft", "conditional balance update succeeds", "draft created"),
            Transition("request_error", "error", "conditional update or insert fails", "rollback"),
        )),
        Step("draft_existing", "system", "draft", "Return existing draft without another reservation", terminal=True, retry_safe=True),
        Step("terminal_existing", "system", "verified", "Return existing terminal result without balance mutation", terminal=True, retry_safe=True),
        Step("request_error", "system", "error", "Rollback and return failure", terminal=True, retry_safe=True),
        Step("draft", "requester", "draft", "Await submission or independent review", transitions=(
            Transition("review_draft", "draft", "review requested", "review"),
            Transition("submitted", "submitted", "submit for review", "submitted"),
        )),
        Step("submitted", "system", "submitted", "Await independent review", transitions=(
            Transition("review_submitted", "submitted", "review requested", "review"),
        )),
        Step("review_draft", "human reviewer", "draft", "Verify reviewer independence and choose disposition", human_approval=True, transitions=(
            Transition("confirm_draft", "reviewed_draft", "confirm", "approve"),
            Transition("release_draft", "reviewed_draft", "reject or cancel", "release"),
        )),
        Step("review_submitted", "human reviewer", "submitted", "Verify reviewer independence and choose disposition", human_approval=True, transitions=(
            Transition("confirm_submitted", "reviewed_submitted", "confirm", "approve"),
            Transition("release_submitted", "reviewed_submitted", "reject or cancel", "release"),
        )),
        Step("confirm_draft", "system", "reviewed_draft", "Move Q from reserved to retired and record confirmation atomically", transaction_boundary=True, high_risk=True, retry_safe=True, transitions=(
            Transition("verified", "verified", "reservation exists and credit remains eligible", "confirmed"),
            Transition("request_error", "error", "guard or transaction fails", "rollback"),
        )),
        Step("confirm_submitted", "system", "reviewed_submitted", "Move Q from reserved to retired and record confirmation atomically", transaction_boundary=True, high_risk=True, retry_safe=True, transitions=(
            Transition("verified", "verified", "reservation exists and credit remains eligible", "confirmed"),
            Transition("request_error", "error", "guard or transaction fails", "rollback"),
        )),
        Step("release_draft", "system", "reviewed_draft", "Release Q from reserved and record reject or cancel atomically", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("rejected", "rejected", "decision is reject", "rejected"),
            Transition("cancelled", "cancelled", "decision is cancel", "cancelled"),
            Transition("request_error", "error", "guard or transaction fails", "rollback"),
        )),
        Step("release_submitted", "system", "reviewed_submitted", "Release Q from reserved and record reject or cancel atomically", transaction_boundary=True, retry_safe=True, transitions=(
            Transition("rejected", "rejected", "decision is reject", "rejected"),
            Transition("cancelled", "cancelled", "decision is cancel", "cancelled"),
            Transition("request_error", "error", "guard or transaction fails", "rollback"),
        )),
        Step("verified", "system", "verified", "Terminal confirmed retirement; repeated review is a no-op", terminal=True, retry_safe=True),
        Step("rejected", "system", "rejected", "Terminal rejected retirement; repeated review is a no-op", terminal=True, retry_safe=True),
        Step("cancelled", "system", "cancelled", "Terminal cancelled retirement; repeated review is a no-op", terminal=True, retry_safe=True),
    ),
))
