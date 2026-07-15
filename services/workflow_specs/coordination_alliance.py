"""Alliance governance workflow specification."""

from .model import Step, Transition, WorkflowSpec
from .registry import register


COORDINATION_ALLIANCE = register(WorkflowSpec(
    id="coordination_alliance",
    title="Coordination Alliance Governance Workflow",
    states=frozenset({
        "draft", "consultation", "due_diligence", "approval", "activation",
        "review", "suspension", "renewal", "termination", "rejected",
    }),
    invariants=(
        "Consultation records affected parties, consent boundaries, accessibility, and minority views.",
        "Due diligence records identity, contribution capacity, dependency risk, capture risk, and ecological safeguards.",
        "Approval requires a linked stakeholder decision or cooperative governance record and a human approver.",
        "Activation is a human-approved transition and does not authorize unrecorded legal, financial, or operational commitments.",
        "Review evaluates participation, contribution delivery, benefit distribution, harm, risk, and knowledge exchange.",
        "Suspension pauses activation when material risk, unresolved harm, or governance failure is detected.",
        "Termination is a human-reviewed terminal outcome with disposition and outstanding-obligation evidence.",
        "Renewal starts a new consultation cycle and must not silently extend the prior agreement.",
    ),
    source_refs=(
        "schemas/postgres/235_coordination_strategy.sql",
        "schemas/postgres/236_coordination_workflow_integration.sql",
        "schemas/postgres/179_lifecycle_transition.sql",
        "services/analytics/stakeholder_decisions.py",
        "services/analytics/cooperative_governance.py",
    ),
    steps=(
        Step("ca_draft", "coordination proposer", "draft", "Prepare alliance consultation", entry=True, transitions=(
            Transition("ca_consultation", "consultation", "scope and participants are ready", "consult"),
            Transition("ca_terminate_draft", "termination", "no mandate or unsafe premise", "terminate"),
        )),
        Step("ca_consultation", "stakeholder coordinator", "consultation", "Consult affected and participating parties", transitions=(
            Transition("ca_due_diligence", "due_diligence", "consent, accessibility, and representation are documented", "consulted", bounded_retry=True, loop_rationale="Each alliance term has one explicit consultation-to-diligence cycle before approval or termination."),
            Transition("ca_terminate_consultation", "termination", "consultation identifies unacceptable harm", "terminate"),
        )),
        Step("ca_due_diligence", "due diligence reviewer", "due_diligence", "Assess identity, capacity, dependency, capture, and ecological risk", transitions=(
            Transition("ca_approval", "approval", "evidence and mitigations are complete", "due_diligence_complete", bounded_retry=True, loop_rationale="The due-diligence-to-approval path is bounded by the current alliance term and explicit termination outcome."),
            Transition("ca_consultation", "consultation", "material gaps require renewed consultation", "revise", bounded_retry=True, loop_rationale="A bounded governance cycle permits renewed consultation when diligence changes the affected-party scope."),
            Transition("ca_terminate_diligence", "termination", "risk cannot be acceptably mitigated", "terminate"),
        )),
        Step("ca_approval", "human reviewer", "approval", "Approve alliance through stakeholder decision or cooperative governance", human_approval=True, transaction_boundary=True, transitions=(
            Transition("ca_activation", "activation", "approval and separation of duties are complete", "approve", bounded_retry=True, loop_rationale="Activation occurs at most once per approved alliance term before review or termination."),
            Transition("ca_consultation", "consultation", "approval requires material redesign", "revise", bounded_retry=True, loop_rationale="A rejected approval returns to consultation only for a bounded redesign cycle."),
            Transition("ca_terminate_approval", "termination", "approval is rejected without a viable redesign", "terminate"),
        )),
        Step("ca_activation", "human operator", "activation", "Activate approved alliance controls", human_approval=True, high_risk=True, external_side_effect=True, transaction_boundary=True, transitions=(
            Transition("ca_review", "review", "participants, commitments, and controls are active", "activate", bounded_retry=True, loop_rationale="Activation enters one governed review cycle for the current alliance term."),
            Transition("ca_terminate_activation", "termination", "activation preconditions fail", "terminate"),
        )),
        Step("ca_review", "human reviewer", "review", "Review participation, value, harms, risks, and learning", human_approval=True, transitions=(
            Transition("ca_renewal", "renewal", "review recommends continuation with a new term", "renew", bounded_retry=True, loop_rationale="Review may propose one explicit renewal decision; termination remains available."),
            Transition("ca_suspension", "suspension", "material risk or unresolved harm requires pause", "suspend", bounded_retry=True, loop_rationale="Suspension may return to review only after corrective evidence is recorded."),
            Transition("ca_termination_review", "termination", "review recommends closure", "terminate"),
        )),
        Step("ca_suspension", "human reviewer", "suspension", "Suspend alliance activity and preserve obligations", human_approval=True, transaction_boundary=True, transitions=(
            Transition("ca_review", "review", "corrective evidence is complete", "resume_review", bounded_retry=True, loop_rationale="Suspension and review form a bounded remediation loop governed by corrective evidence."),
            Transition("ca_terminate_suspension", "termination", "suspension cannot be safely resolved", "terminate"),
        )),
        Step("ca_renewal", "human reviewer", "renewal", "Prepare a new alliance term", human_approval=True, transaction_boundary=True, transitions=(
            Transition("ca_consultation", "consultation", "renewal requires fresh consent and scope review", "renew", bounded_retry=True, loop_rationale="Renewal creates a new governed term rather than silently extending an alliance."),
            Transition("ca_terminate_renewal", "termination", "renewal is declined", "terminate"),
        )),
        Step("ca_terminate_draft", "human reviewer", "termination", "Terminate alliance before consultation", terminal=True),
        Step("ca_terminate_consultation", "human reviewer", "termination", "Terminate after consultation", terminal=True),
        Step("ca_terminate_diligence", "human reviewer", "termination", "Terminate after due diligence", terminal=True),
        Step("ca_terminate_approval", "human reviewer", "termination", "Terminate after approval review", terminal=True),
        Step("ca_terminate_activation", "human reviewer", "termination", "Terminate before activation completes", terminal=True),
        Step("ca_termination_review", "human reviewer", "termination", "Terminate after review", terminal=True),
        Step("ca_terminate_suspension", "human reviewer", "termination", "Terminate from suspension", terminal=True),
        Step("ca_terminate_renewal", "human reviewer", "termination", "Terminate after renewal decision", terminal=True),
    ),
))
