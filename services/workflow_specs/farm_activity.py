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
        "Verification confirms the activity occurred and data is accurate.",
        "Publication makes the activity available for metric computation.",
        "Rejection is terminal and requires a reason.",
    ),
    source_refs=(
        "schemas/postgres/003_operations.sql",
        "services/ingestion/sensor_ingester.py",
    ),
    steps=(
        Step("fa_draft_entry", "farmer", "draft", "Record farm activity", entry=True, transitions=(
            Transition("fa_submit", "submitted", "submit for verification", "submit"),
            Transition("fa_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("fa_submit", "farmer", "submitted", "Submit activity for verification", transitions=(
            Transition("fa_verify", "verified", "activity confirmed", "verify"),
            Transition("fa_reject_submitted", "rejected", "activity not confirmed", "reject"),
        )),
        Step("fa_verify", "reviewer", "verified", "Verify activity data", human_approval=True, transitions=(
            Transition("fa_publish", "published", "approved for metric computation", "publish"),
            Transition("fa_reject_verified", "rejected", "data inaccurate after verification", "reject"),
        )),
        Step("fa_publish", "system", "published", "Terminal published activity", terminal=True),
        Step("fa_reject_draft", "reviewer", "rejected", "Terminal rejected activity", terminal=True),
        Step("fa_reject_submitted", "reviewer", "rejected", "Terminal rejected activity", terminal=True),
        Step("fa_reject_verified", "reviewer", "rejected", "Terminal rejected activity", terminal=True),
    ),
))
