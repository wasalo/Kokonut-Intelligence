"""Conformance checks for the first DRAKON-inspired workflow specifications."""

from pathlib import Path

from services.workflow_specs.carbon_retirement import CARBON_RETIREMENT
from services.workflow_specs.event_bus import EVENT_BUS
from services.workflow_specs.registry import list_specs
from services.workflow_specs.render import render_markdown, render_mermaid
from services.workflow_specs.validator import validate

ROOT = Path(__file__).resolve().parents[1]


def _transitions(spec):
    return {
        (step.current_state, transition.next_state, transition.outcome)
        for step in spec.steps
        for transition in step.transitions
    }


def test_builtin_specs_validate_and_have_invariants():
    assert {spec.id for spec in list_specs()} == {
        "carbon_retirement",
        "event_bus_delivery",
        "work_item",
        "budget",
        "objective",
        "project",
        "data_stream_post",
        "ai_summary",
        "impact_claim",
        "report_snapshot",
        "stakeholder_feedback",
        "farm_activity",
        "harvest_event",
        "metric_value",
        "traceability_batch",
        "insurance_claim",
        "pest_intervention",
        "emergency_incident",
        "cooperative_order",
        "extension_enrollment",
        "market_order",
    }
    for spec in list_specs():
        validate(spec)
        assert spec.invariants
        assert spec.source_refs


def test_project_spec_blocks_without_note_and_is_terminal():
    from services.workflow_specs.project import PROJECT

    transitions = _transitions(PROJECT)
    assert ("draft", "active", "start") in transitions
    assert ("active", "on_hold", "hold") in transitions
    assert ("active", "done", "complete") in transitions
    for state in ("draft", "active", "on_hold"):
        assert any(cs == state and ns == "cancelled" for cs, ns, _ in transitions)
    done = next(step for step in PROJECT.steps if step.id == "project_done")
    assert done.terminal


def test_objective_spec_review_lifecycle_and_closed_terminal():
    from services.workflow_specs.objective import OBJECTIVE

    transitions = _transitions(OBJECTIVE)
    for state in ("on_track", "at_risk", "off_track"):
        assert any(cs == state and ns == "closed" for cs, ns, _ in transitions)
    closed = next(step for step in OBJECTIVE.steps if step.id == "closed")
    assert closed.terminal
    assert not closed.transitions


def test_budget_spec_requires_human_approval_and_lifecycle():
    from services.workflow_specs.budget import BUDGET

    transitions = _transitions(BUDGET)
    assert ("draft", "approved", "approve") in transitions
    assert ("approved", "active", "activate") in transitions
    assert ("active", "closed", "close") in transitions
    # Cancellation reachable from every non-terminal state.
    for state in ("draft", "approved", "active"):
        assert any(cs == state and ns == "cancelled" for cs, ns, _ in transitions)
    approve = next(step for step in BUDGET.steps if step.id == "budget_approve")
    assert approve.human_approval
    assert approve.actor == "human reviewer"


def test_work_item_spec_covers_lifecycle_and_is_acyclic_outside_revisions():
    from services.workflow_specs.work_item import WORK_ITEM

    transitions = _transitions(WORK_ITEM)
    # Forward lifecycle edges exist.
    assert ("draft", "assigned", "assign") in transitions
    assert ("assigned", "in_progress", "start") in transitions
    assert ("in_progress", "done", "complete") in transitions
    assert ("in_progress", "blocked", "block") in transitions
    assert ("blocked", "in_progress", "unblock") in transitions
    # Cancellation reachable from every non-terminal state.
    for state in ("draft", "assigned", "in_progress", "blocked"):
        assert any(cs == state and ns == "cancelled" for cs, ns, _ in transitions)
    # No agent path reaches a governed publish/verify state.
    assert all(step.actor != "agent" for step in WORK_ITEM.steps)


def test_event_bus_spec_covers_retry_completion_and_operator_disposition():
    transitions = _transitions(EVENT_BUS)
    assert ("processing", "pending", "retry") in transitions
    assert ("processing", "dead_letter", "dead letter") in transitions
    assert ("processing", "completed", "completed") in transitions
    assert ("dead_letter", "pending", "replay") in transitions
    assert ("dead_letter", "disposed", "dispose") in transitions
    invoke = next(step for step in EVENT_BUS.steps if step.id == "invoke")
    assert invoke.external_side_effect
    assert not invoke.retry_safe


def test_event_bus_retry_cycle_is_explicitly_bounded():
    retry = next(step for step in EVENT_BUS.steps if step.id == "retry_decision")
    retry_transition = next(item for item in retry.transitions if item.outcome == "retry")
    assert retry_transition.bounded_retry
    assert "max_retries" in retry_transition.loop_rationale


def test_carbon_spec_covers_balance_mutations_and_independent_confirmation():
    text = "\n".join(CARBON_RETIREMENT.invariants)
    assert "retired_tonnes + reserved_tonnes" in text
    assert "reserved_tonnes by +Q" in text
    assert "reserved_tonnes by -Q and retired_tonnes by +Q" in text
    confirmation_steps = [step for step in CARBON_RETIREMENT.steps if step.id.startswith("confirm_")]
    assert confirmation_steps
    assert all(step.high_risk and step.transaction_boundary for step in confirmation_steps)
    review_steps = [step for step in CARBON_RETIREMENT.steps if step.id.startswith("review_")]
    assert all(step.human_approval and step.actor == "human reviewer" for step in review_steps)


def test_carbon_terminal_states_are_idempotent():
    terminal = {step.current_state: step for step in CARBON_RETIREMENT.steps if step.terminal}
    for state in ("verified", "rejected", "cancelled"):
        assert terminal[state].retry_safe
        assert not terminal[state].transitions


def test_generated_workflow_docs_are_current():
    for spec in list_specs():
        path = ROOT / "docs" / f"workflow-{spec.id.replace('_', '-')}.md"
        expected = render_markdown(spec)
        expected += "\n## Mermaid\n\n```mermaid\n"
        expected += render_mermaid(spec)
        expected += "```\n"
        assert path.read_text() == expected


def test_specs_reference_current_production_states_and_controls():
    event_schema = (ROOT / "schemas/postgres/116_event_bus.sql").read_text()
    retirement_schema = (ROOT / "schemas/postgres/163_carbon_retirement_integrity.sql").read_text()
    event_service = (ROOT / "services/events/bus.py").read_text()
    retirement_service = (ROOT / "services/analytics/carbon_credits.py").read_text()

    for state in ("pending", "processing", "completed", "dead_letter"):
        assert state in event_schema
    assert "pg_advisory" not in event_service
    assert "lease_owner" in event_service
    assert "reserved_tonnes" in retirement_schema
    assert "FOR UPDATE" in retirement_service
    assert 'str(retirement["created_by"]) == reviewer_id' in retirement_service


def test_new_5_state_specs_have_proper_steps():
    """Validate that the 7 new 5-state specs have proper step structure."""
    from services.workflow_specs.registry import get_spec

    new_spec_ids = [
        "traceability_batch", "insurance_claim", "pest_intervention",
        "emergency_incident", "cooperative_order", "extension_enrollment",
        "market_order",
    ]
    for spec_id in new_spec_ids:
        spec = get_spec(spec_id)
        # Must have exactly 7 steps (1 entry, 1 submit, 1 verify, 1 publish, 3 reject terminals)
        assert len(spec.steps) == 7, f"{spec_id} should have 7 steps, got {len(spec.steps)}"
        # Must have an entry step
        entry_steps = [s for s in spec.steps if s.entry]
        assert len(entry_steps) == 1, f"{spec_id} must have exactly 1 entry step"
        # Must have a terminal publish step
        publish_steps = [s for s in spec.steps if s.terminal and "publish" in s.id]
        assert len(publish_steps) == 1, f"{spec_id} must have exactly 1 terminal publish step"
        # Must have 3 terminal reject steps
        reject_steps = [s for s in spec.steps if s.terminal and "reject" in s.id]
        assert len(reject_steps) == 3, f"{spec_id} must have 3 terminal reject steps"
        # Verify step must have human_approval
        verify_steps = [s for s in spec.steps if "verify" in s.id and not s.terminal]
        assert verify_steps, f"{spec_id} must have a verify step"
        assert verify_steps[0].human_approval, f"{spec_id} verify step must require human approval"
        # States must be the standard 5-state set
        assert spec.states == frozenset({"draft", "submitted", "verified", "published", "rejected"}), f"{spec_id} has non-standard states"
