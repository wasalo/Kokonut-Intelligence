"""Project (portfolio) lifecycle workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register

_LOOP = "Projects move between active and on_hold as conditions change; bounded by human decision."


PROJECT = register(WorkflowSpec(
    id="project",
    title="Project Lifecycle",
    states=frozenset({"draft", "active", "on_hold", "done", "cancelled"}),
    invariants=(
        "A project cannot start without being created in draft.",
        "on_hold requires a reason note.",
        "done and cancelled are terminal.",
    ),
    source_refs=(
        "schemas/postgres/178_program_portfolio.sql",
        "services/planning/portfolio.py",
    ),
    steps=(
        Step("project_draft", "manager", "draft", "Create project", entry=True, transitions=(
            Transition("project_active", "active", "work begins", "start"),
            Transition("project_cancel_draft", "cancelled", "cancelled before start", "cancel"),
        )),
        Step("project_active", "manager", "active", "Active project", transitions=(
            Transition("project_hold", "on_hold", "work paused", "hold", loop_rationale=_LOOP),
            Transition("project_done", "done", "work finished", "complete"),
            Transition("project_cancel_active", "cancelled", "cancelled while active", "cancel"),
        )),
        Step("project_hold", "manager", "on_hold", "On-hold project", transitions=(
            Transition("project_active", "active", "work resumed", "resume", loop_rationale=_LOOP),
            Transition("project_cancel_hold", "cancelled", "cancelled while on hold", "cancel"),
        )),
        Step("project_done", "manager", "done", "Terminal completed project", terminal=True),
        Step("project_cancel_draft", "manager", "cancelled", "Terminal cancelled project", terminal=True),
        Step("project_cancel_active", "manager", "cancelled", "Terminal cancelled project", terminal=True),
        Step("project_cancel_hold", "manager", "cancelled", "Terminal cancelled project", terminal=True),
    ),
))
