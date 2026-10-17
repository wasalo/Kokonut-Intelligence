"""Farm activity lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

FARM_ACTIVITY = register(WorkflowSpec(
    id="farm_activity",
    title="Farm Activity Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "A farm activity begins in draft, created by a farmer or field worker.",
        "Farm activities require source_system, source_id, and source_raw for data lineage.",
        "Verification confirms the activity occurred and data is accurate; the verifier must differ from the submitter.",
        "Publication is a separate, explicit human-approved action and makes the activity available for governed metric computation.",
        "Rejection requires a reason and an explicit human disposition: request correction or close as an exception.",
        "Agents may draft or submit but may not verify or publish farm activities.",
    ),
    source_refs=(
        "schemas/postgres/003_operations.sql",
        "schemas/postgres/179_lifecycle_transition.sql",
        "schemas/postgres/381_mobile_consent_form_revisions.sql",
        "schemas/seeds/140_mobile_forms.sql",
        "services/mobile/api.py",
        "services/gateway/operator_mobile_review.py",
    ),
    steps=(
        Step("fa_draft_entry", "farmer", "draft", "Record farm activity", entry=True, transitions=(
            Transition("fa_review_submitted", "submitted", "submit for verification", "submit"),
        )),
        Step("fa_review_submitted", "human reviewer", "submitted", "Independently review submitted activity", human_approval=True, transitions=(
            Transition("fa_verify", "verified", "activity occurred and data is accurate", "verify", loop_rationale="A human-reviewed correction cycle may return this record to submission."),
            Transition("fa_reject_submitted", "rejected", "activity needs correction or exception disposition", "reject", loop_rationale="A human-reviewed correction cycle may return this record to submission."),
        )),
        Step("fa_verify", "human publisher", "verified", "Decide whether to publish verified activity", human_approval=True, transitions=(
            Transition("fa_publish", "published", "verified activity is explicitly approved for governed use", "publish"),
            Transition("fa_reject_verified", "rejected", "data inaccurate or requires correction", "reject", loop_rationale="A human-reviewed correction cycle may return this record to submission."),
        )),
        Step("fa_publish", "human publisher", "published", "Explicitly publish verified activity", terminal=True, human_approval=True),
        Step("fa_reject_submitted", "human reviewer", "rejected", "Record reasoned disposition for submitted activity", human_approval=True, transitions=(
            Transition("fa_rework", "draft", "correctable issue; return to submitter", "request correction", bounded_retry=True, loop_rationale="Each correction cycle is a human-authorized and audited rework decision."),
            Transition("fa_reject_terminal", "rejected", "exception or withdrawal; close without publication", "close exception"),
        )),
        Step("fa_reject_verified", "human reviewer", "rejected", "Record reasoned disposition for verified activity", human_approval=True, transitions=(
            Transition("fa_rework", "draft", "correctable issue; return to submitter", "request correction", bounded_retry=True, loop_rationale="Each correction cycle is a human-authorized and audited rework decision."),
            Transition("fa_reject_terminal", "rejected", "exception; close without publication", "close exception"),
        )),
        Step("fa_rework", "farmer", "draft", "Correct rejected activity and resubmit", transitions=(
            Transition("fa_review_submitted", "submitted", "correction is ready for review", "resubmit", loop_rationale="A human-reviewed correction cycle may return this record to submission."),
        )),
        Step("fa_reject_terminal", "human reviewer", "rejected", "Terminal exception or withdrawal with retained reason", terminal=True),
    ),
))
