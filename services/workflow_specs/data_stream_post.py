"""Data stream post lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

DATA_STREAM_POST = register(WorkflowSpec(
    id="data_stream_post",
    title="Data Stream Post Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "A data stream post begins in draft and requires a verified farm_registry_record for public visibility.",
        "Submission moves the post into the review pipeline.",
        "Verification is a human decision; agents cannot verify.",
        "Publication makes the post publicly visible and immutable.",
        "Rejection is terminal and requires a reason recorded in the lifecycle ledger.",
        "Blockchain anchoring uses the kokonut-data-post EAS schema on Celo.",
    ),
    source_refs=(
        "schemas/postgres/100_data_stream.sql",
        "services/data_stream/cli.py",
    ),
    steps=(
        Step("dsp_draft_entry", "author", "draft", "Create data stream post", entry=True, transitions=(
            Transition("dsp_submit", "submitted", "submit for review", "submit"),
            Transition("dsp_reject_draft", "rejected", "rejected before submission", "reject"),
        )),
        Step("dsp_submit", "author", "submitted", "Submit post for review", transitions=(
            Transition("dsp_verify", "verified", "reviewed and verified", "verify"),
            Transition("dsp_reject_submitted", "rejected", "rejected during review", "reject"),
        )),
        Step("dsp_verify", "reviewer", "verified", "Verify post accuracy", human_approval=True, transitions=(
            Transition("dsp_publish", "published", "approved for publication", "publish"),
            Transition("dsp_reject_verified", "rejected", "rejected after verification", "reject"),
        )),
        Step("dsp_publish", "system", "published", "Terminal published post", terminal=True),
        Step("dsp_reject_draft", "reviewer", "rejected", "Terminal rejected post", terminal=True),
        Step("dsp_reject_submitted", "reviewer", "rejected", "Terminal rejected post", terminal=True),
        Step("dsp_reject_verified", "reviewer", "rejected", "Terminal rejected post", terminal=True),
    ),
))
