"""Extension Enrollment lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

SPEC_NAME = register(WorkflowSpec(
    id="extension_enrollment",
    title="Extension Enrollment Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "enrollment requires farmer_id, module_id",
        "verification confirms completion and assessment score",
        "publication records learning progress",
    ),
    source_refs=(
        "schemas/postgres/194_process_taxonomy_expansion.sql",
    ),
    steps=(
        Step("ee_draft_entry", "farmer", "draft", "Create extension enrollment", entry=True, transitions=(
            Transition("ee_submit", "submitted", "submit for verification", "submit"),
            Transition("ee_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("ee_submit", "farmer", "submitted", "Submit extension enrollment for review", transitions=(
            Transition("ee_verify", "verified", "completion and score confirmed", "verify"),
            Transition("ee_reject_submitted", "rejected", "incomplete enrollment", "reject"),
        )),
        Step("ee_verify", "trainer", "verified", "Verify extension enrollment completion", human_approval=True, transitions=(
            Transition("ee_publish", "published", "approved for learning progress recording", "publish"),
            Transition("ee_reject_verified", "rejected", "assessment score below threshold", "reject"),
        )),
        Step("ee_publish", "system", "published", "Terminal published extension enrollment", terminal=True),
        Step("ee_reject_draft", "trainer", "rejected", "Terminal rejected extension enrollment", terminal=True),
        Step("ee_reject_submitted", "trainer", "rejected", "Terminal rejected extension enrollment", terminal=True),
        Step("ee_reject_verified", "trainer", "rejected", "Terminal rejected extension enrollment", terminal=True),
    ),
))
