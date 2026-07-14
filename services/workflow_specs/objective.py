"""Objective review (performance management) lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

_LOOP = "Review status is revisited as conditions change; bounded by human reassessment."


OBJECTIVE = register(WorkflowSpec(
    id="objective",
    title="Objective Review Lifecycle",
    states=frozenset({"on_track", "at_risk", "off_track", "closed"}),
    invariants=(
        "An objective starts with an initial review setting its health status.",
        "off_track reviews should spawn a corrective work item.",
        "closed is terminal; reopening requires a new review.",
    ),
    source_refs=(
        "schemas/postgres/177_objective_enhancements.sql",
        "services/planning/performance.py",
        "services/management/workbench.py",
    ),
    steps=(
        Step("on_track", "reviewer", "on_track", "Initial or steady-state review", entry=True, transitions=(
            Transition("at_risk", "at_risk", "concerns emerging", "flag at_risk", loop_rationale=_LOOP),
            Transition("off_track", "off_track", "materially behind", "flag off_track", loop_rationale=_LOOP),
            Transition("closed", "closed", "objective achieved", "close"),
        )),
        Step("at_risk", "reviewer", "at_risk", "At-risk review", transitions=(
            Transition("on_track", "on_track", "recovered", "recover", loop_rationale=_LOOP),
            Transition("off_track", "off_track", "worsened", "escalate", loop_rationale=_LOOP),
            Transition("closed", "closed", "resolved or withdrawn", "close"),
        )),
        Step("off_track", "reviewer", "off_track", "Off-track review", transitions=(
            Transition("at_risk", "at_risk", "partial recovery", "improve", loop_rationale=_LOOP),
            Transition("on_track", "on_track", "recovered", "recover", loop_rationale=_LOOP),
            Transition("closed", "closed", "withdrawn or superseded", "close"),
        )),
        Step("closed", "system", "closed", "Terminal closed objective", terminal=True),
    ),
))
