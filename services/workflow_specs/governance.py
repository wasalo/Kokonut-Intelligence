"""Workflow specifications for Kokonut role-and-circle governance records."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


def _linear(spec_id, title, states, transitions, terminals, source, invariants):
    steps = []
    for index, state in enumerate(states):
        steps.append(Step(
            f"{state}_step",
            "human reviewer" if state in {"approved", "active", "implemented", "completed"} else "circle participant",
            state,
            f"Process {state}",
            transitions=tuple(Transition(f"{target}_step", next_state, guard, outcome) for target, next_state, guard, outcome in transitions.get(state, ())),
            entry=index == 0,
            terminal=state in terminals,
            human_approval=state in {"approved", "active", "implemented"},
            transaction_boundary=state in {"approved", "active", "implemented"},
        ))
    return register(WorkflowSpec(
        id=spec_id, title=title, states=frozenset(states), steps=tuple(steps),
        invariants=invariants, source_refs=(source,),
    ))


GOVERNANCE_CIRCLE = _linear("governance_circle", "Governance Circle Lifecycle",
    ("draft", "submitted", "active", "suspended", "retired", "rejected"), {
        "draft": (("submitted", "submitted", "purpose and scope documented", "submit"), ("rejected", "rejected", "invalid proposal", "reject")),
        "submitted": (("active", "active", "human approves circle", "activate"), ("rejected", "rejected", "human rejects circle", "reject")),
        "active": (("suspended", "suspended", "governance risk requires pause", "suspend"), ("retired", "retired", "circle is no longer needed", "retire")),
        "suspended": (("retired", "retired", "circle is retired", "retire"),),
    }, ("retired", "rejected"), "schemas/postgres/242_governance_circles_roles.sql",
    ("An active circle requires a purpose, scope, and human governance.",))

GOVERNANCE_ROLE = _linear("governance_role", "Governance Role Lifecycle",
    ("draft", "submitted", "approved", "active", "suspended", "retired", "rejected"), {
        "draft": (("submitted", "submitted", "purpose and accountabilities documented", "submit"), ("rejected", "rejected", "invalid role", "reject")),
        "submitted": (("approved", "approved", "human approves role definition", "approve"), ("rejected", "rejected", "human rejects role definition", "reject")),
        "approved": (("active", "active", "role is activated in an active circle", "activate"),),
        "active": (("suspended", "suspended", "role authority is paused", "suspend"), ("retired", "retired", "role is superseded", "retire")),
        "suspended": (("retired", "retired", "role is retired", "retire"),),
    }, ("retired", "rejected"), "schemas/postgres/242_governance_circles_roles.sql",
    ("A role is independent of the party filling it.", "An active role requires an active circle."))

GOVERNANCE_ROLE_ASSIGNMENT = _linear("governance_role_assignment", "Governance Role Assignment Lifecycle",
    ("proposed", "active", "suspended", "ended", "rejected"), {
        "proposed": (("active", "active", "human approves assignment", "activate"), ("rejected", "rejected", "assignment is rejected", "reject")),
        "active": (("suspended", "suspended", "recusal or authority pause", "suspend"), ("ended", "ended", "term ends", "end")),
        "suspended": (("ended", "ended", "assignment ends", "end"),),
    }, ("ended", "rejected"), "schemas/postgres/243_governance_role_authority.sql",
    ("An active assignment requires human approval and a non-recused party.",))

GOVERNANCE_TENSION = _linear("governance_tension", "Governance Tension Lifecycle",
    ("draft", "submitted", "triaged", "in_progress", "resolved", "deferred", "rejected", "closed"), {
        "draft": (("submitted", "submitted", "report is ready for triage", "submit"), ("rejected", "rejected", "invalid report", "reject")),
        "submitted": (("triaged", "triaged", "owner is assigned", "triage"), ("rejected", "rejected", "not actionable", "reject")),
        "triaged": (("in_progress", "in_progress", "owned action begins", "start"), ("deferred", "deferred", "action is intentionally deferred", "defer")),
        "in_progress": (("resolved", "resolved", "resolution is evidenced", "resolve"), ("rejected", "rejected", "tension is invalidated", "reject")),
        "resolved": (("closed", "closed", "review confirms closure", "close"),),
        "deferred": (("closed", "closed", "deferred item is closed with rationale", "close"),),
    }, ("closed", "rejected"), "schemas/postgres/244_governance_tensions.sql",
    ("A triaged or active tension has an owner role or party.", "A resolved tension has a resolution summary."))

GOVERNANCE_PROPOSAL = _linear("governance_proposal", "Governance Proposal Lifecycle",
    ("draft", "submitted", "in_review", "approved", "implemented", "rejected", "superseded", "cancelled"), {
        "draft": (("submitted", "submitted", "proposal has a proposer and evidence", "submit"), ("rejected", "rejected", "invalid proposal", "reject"), ("cancelled", "cancelled", "proposal withdrawn", "cancel")),
        "submitted": (("in_review", "in_review", "objections and reviews begin", "review"), ("rejected", "rejected", "human rejects proposal", "reject")),
        "in_review": (("approved", "approved", "human approval and review gates clear", "approve"), ("rejected", "rejected", "review rejects proposal", "reject"), ("superseded", "superseded", "new proposal replaces this one", "supersede")),
        "approved": (("implemented", "implemented", "implementation work is complete", "implement"),),
    }, ("implemented", "rejected", "superseded", "cancelled"), "schemas/postgres/246_governance_proposals.sql",
    ("Approved proposals require a human approver.", "Material harm and consent objections must be resolved before approval.", "Implementation requires a linked work item."))

GOVERNANCE_TACTICAL_SESSION = _linear("governance_tactical_session", "Tactical Governance Session Lifecycle",
    ("planned", "active", "completed", "cancelled"), {
        "planned": (("active", "active", "session begins", "start"), ("cancelled", "cancelled", "session cancelled", "cancel")),
        "active": (("completed", "completed", "outcomes recorded", "complete"), ("cancelled", "cancelled", "session cancelled", "cancel")),
    }, ("completed", "cancelled"), "schemas/postgres/247_governance_tactical_coordination.sql",
    ("A completed session has an outcome summary.",))

GOVERNANCE_TACTICAL_ITEM = _linear("governance_tactical_item", "Tactical Governance Item Lifecycle",
    ("open", "in_progress", "disposed", "cancelled"), {
        "open": (("in_progress", "in_progress", "an owner starts the action", "start"), ("cancelled", "cancelled", "item cancelled", "cancel")),
        "in_progress": (("disposed", "disposed", "explicit disposition recorded", "dispose"), ("cancelled", "cancelled", "item cancelled", "cancel")),
    }, ("disposed", "cancelled"), "schemas/postgres/247_governance_tactical_coordination.sql",
    ("A disposed item has a disposition type, summary, and actor.",))

GOVERNANCE_CIRCLE_LINK = _linear("governance_circle_link", "Cross-Circle Link Lifecycle",
    ("proposed", "active", "suspended", "ended", "rejected"), {
        "proposed": (("active", "active", "human approves link", "activate"), ("rejected", "rejected", "link rejected", "reject")),
        "active": (("suspended", "suspended", "recusal or mandate pause", "suspend"), ("ended", "ended", "term ends", "end")),
        "suspended": (("ended", "ended", "link ends", "end"),),
    }, ("ended", "rejected"), "schemas/postgres/248_governance_circle_links.sql",
    ("An active link requires active circles, an active role assignment, a mandate, and human approval."))
