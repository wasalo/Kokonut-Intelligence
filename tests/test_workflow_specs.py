"""Focused workflow specification tests."""

import pytest

from services.workflow_specs import (
    Step,
    Transition,
    WorkflowSpec,
    WorkflowValidationError,
    render_markdown,
    render_mermaid,
    validate,
)


def spec(*steps, states=frozenset({"draft", "submitted", "published"})):
    return WorkflowSpec("example", "Example", states, tuple(steps))


def terminal(step_id="end", state="submitted"):
    return Step(step_id, "human", state, "finish", terminal=True)


def assert_invalid(workflow, message):
    with pytest.raises(WorkflowValidationError, match=message):
        validate(workflow)


def test_rejects_unreachable_step():
    workflow = spec(
        Step("start", "human", "draft", "submit", (Transition("end", "submitted"),), entry=True),
        terminal(),
        terminal("orphan"),
    )
    assert_invalid(workflow, "unreachable step: orphan")


def test_rejects_dangling_target():
    workflow = spec(
        Step("start", "human", "draft", "submit", (Transition("missing", "submitted"),), entry=True)
    )
    assert_invalid(workflow, "dangling target: missing")


def test_rejects_nonterminal_path():
    workflow = spec(
        Step("start", "human", "draft", "wait", (Transition("stuck", "draft"),), entry=True),
        Step("stuck", "human", "draft", "wait", (Transition("stuck", "draft", bounded_retry=True),)),
    )
    assert_invalid(workflow, "cannot reach a terminal")


def test_rejects_unbounded_cycle():
    workflow = spec(
        Step("start", "human", "draft", "try", (Transition("retry", "draft"),), entry=True),
        Step("retry", "human", "draft", "retry", (Transition("start", "draft"), Transition("end", "submitted"))),
        terminal(),
    )
    assert_invalid(workflow, "cycle transition .* is unbounded")


def test_rejects_high_risk_action_without_prior_approval():
    workflow = spec(
        Step("start", "human", "draft", "submit", (Transition("risk", "submitted"),), entry=True),
        Step("risk", "human", "submitted", "onchain_submit", (Transition("end", "submitted"),)),
        terminal(),
    )
    assert_invalid(workflow, "high-risk step risk lacks prior human approval")


def test_rejects_agent_publish_path():
    workflow = spec(
        Step("start", "agent", "draft", "draft", (Transition("end", "published"),), entry=True),
        terminal("end", "published"),
    )
    assert_invalid(workflow, "agent path transitions to published")


def test_rendering_is_deterministic():
    first = spec(
        Step("start", "human", "draft", "choose", (
            Transition("z_end", "submitted", guard="z", outcome="later"),
            Transition("a_end", "submitted", guard="a", outcome="now"),
        ), entry=True),
        terminal("z_end"),
        terminal("a_end"),
    )
    second = spec(first.steps[2], first.steps[0], first.steps[1])
    assert render_markdown(first) == render_markdown(second)
    assert render_mermaid(first) == render_mermaid(second)
    assert render_markdown(first).index("a_end") < render_markdown(first).index("z_end")
