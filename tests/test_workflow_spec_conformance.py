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
    assert {spec.id for spec in list_specs()} == {"carbon_retirement", "event_bus_delivery"}
    for spec in list_specs():
        validate(spec)
        assert spec.invariants
        assert spec.source_refs


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
