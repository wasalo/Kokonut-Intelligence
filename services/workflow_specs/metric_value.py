"""Metric value lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

METRIC_VALUE = register(WorkflowSpec(
    id="metric_value",
    title="Metric Value Lifecycle",
    states=frozenset({"draft", "verified"}),
    invariants=(
        "Metric computation creates draft, unverified metric_value rows.",
        "A human reviewer must verify individual values before public metric views expose them.",
        "Verification is a human decision; agents cannot auto-verify.",
        "The verified state is terminal.",
    ),
    source_refs=(
        "schemas/postgres/007_modeled_outputs.sql",
        "services/metrics/engine.py",
    ),
    steps=(
        Step("mv_draft_entry", "system", "draft", "Compute metric value", entry=True, transitions=(
            Transition("mv_verify", "verified", "human reviewer verified", "verify"),
        )),
        Step("mv_verify", "reviewer", "verified", "Human verification of metric value", terminal=True,
             human_approval=True),
    ),
))
