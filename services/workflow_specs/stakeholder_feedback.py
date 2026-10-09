"""Stakeholder feedback lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

STAKEHOLDER_FEEDBACK = register(WorkflowSpec(
    id="stakeholder_feedback",
    title="Stakeholder Feedback Lifecycle",
    states=frozenset({"draft", "submitted", "verified", "published", "rejected"}),
    invariants=(
        "Stakeholder feedback is private by default.",
        "Public feedback requires consent_given=TRUE, public consent scope, status='published', and a non-empty public_summary.",
        "Verification requires a minimum 7-day review period after submission.",
        "Publication makes feedback publicly visible with redacted PII.",
        "Rejection is terminal and requires a reason.",
    ),
    source_refs=(
        "schemas/postgres/030_stakeholder_feedback.sql",
        "services/agents/feedback_agent.py",
    ),
    steps=(
        Step("sf_draft_entry", "stakeholder", "draft", "Record feedback", entry=True, transitions=(
            Transition("sf_submit", "submitted", "submit for review", "submit"),
            Transition("sf_reject_draft", "rejected", "withdrawn before submission", "reject"),
        )),
        Step("sf_submit", "stakeholder", "submitted", "Submit feedback for review", transitions=(
            Transition("sf_verify", "verified", "7-day review period elapsed, verified", "verify"),
            Transition("sf_reject_submitted", "rejected", "rejected during review", "reject"),
        )),
        Step("sf_verify", "reviewer", "verified", "Verify feedback and consent", human_approval=True, transitions=(
            Transition("sf_publish", "published", "approved for public display", "publish"),
            Transition("sf_reject_verified", "rejected", "rejected after verification", "reject"),
        )),
        Step("sf_publish", "system", "published", "Terminal published feedback", terminal=True),
        Step("sf_reject_draft", "reviewer", "rejected", "Terminal rejected feedback", terminal=True),
        Step("sf_reject_submitted", "reviewer", "rejected", "Terminal rejected feedback", terminal=True),
        Step("sf_reject_verified", "reviewer", "rejected", "Terminal rejected feedback", terminal=True),
    ),
))
