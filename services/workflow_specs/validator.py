"""Workflow structural and governance validation."""

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

from .model import Step, WorkflowSpec

HIGH_RISK_ACTIONS = frozenset(
    {
        "attest",
        "bulk_update",
        "delete",
        "financial_write",
        "onchain_submit",
        "publish",
        "status_change_to_published",
    }
)


class WorkflowValidationError(ValueError):
    """Raised when a workflow specification is invalid."""

    def __init__(self, errors: List[str]):
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


def validate(spec: WorkflowSpec) -> None:
    """Validate structure, termination, retry bounds, and approval policy."""
    errors: List[str] = []
    by_id: Dict[str, Step] = {}
    metadata = spec.metadata
    for field_name in ("governance_controls", "data_sources", "audit_controls", "test_refs"):
        values = getattr(metadata, field_name)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            errors.append(f"metadata field {field_name} contains an empty or non-string value")
    for step in spec.steps:
        if step.id in by_id:
            errors.append(f"duplicate step id: {step.id}")
        by_id[step.id] = step

    entries = [step for step in spec.steps if step.entry]
    if len(entries) != 1:
        errors.append(f"expected exactly one entry step, found {len(entries)}")

    for step in spec.steps:
        if step.current_state not in spec.states:
            errors.append(f"step {step.id} uses undeclared state: {step.current_state}")
        if step.terminal and step.transitions:
            errors.append(f"terminal step {step.id} has transitions")
        if not step.terminal and not step.transitions:
            errors.append(f"nonterminal step {step.id} has no transitions")
        for transition in step.transitions:
            if transition.target not in by_id:
                errors.append(f"step {step.id} has dangling target: {transition.target}")
            elif transition.next_state != by_id[transition.target].current_state:
                errors.append(
                    f"step {step.id} next state {transition.next_state} does not match "
                    f"target {transition.target} state {by_id[transition.target].current_state}"
                )
            if transition.next_state not in spec.states:
                errors.append(
                    f"step {step.id} transitions to undeclared state: {transition.next_state}"
                )

    if len(entries) == 1:
        reachable = _reachable(entries[0].id, by_id)
        for step_id in sorted(set(by_id) - reachable):
            errors.append(f"unreachable step: {step_id}")
        terminals = {step.id for step in spec.steps if step.terminal}
        can_terminate = _reverse_reachable(terminals, by_id)
        for step_id in sorted(reachable - can_terminate):
            errors.append(f"reachable step cannot reach a terminal: {step_id}")
        _validate_cycles(reachable, by_id, errors)
        _validate_governance(entries[0].id, by_id, errors)

    if errors:
        raise WorkflowValidationError(errors)


def _reachable(start: str, by_id: Dict[str, Step]) -> Set[str]:
    seen: Set[str] = set()
    pending = [start]
    while pending:
        step_id = pending.pop()
        if step_id in seen or step_id not in by_id:
            continue
        seen.add(step_id)
        pending.extend(t.target for t in by_id[step_id].transitions)
    return seen


def _reverse_reachable(starts: Set[str], by_id: Dict[str, Step]) -> Set[str]:
    reverse = defaultdict(list)
    for step in by_id.values():
        for transition in step.transitions:
            reverse[transition.target].append(step.id)
    seen: Set[str] = set()
    pending = list(starts)
    while pending:
        step_id = pending.pop()
        if step_id in seen:
            continue
        seen.add(step_id)
        pending.extend(reverse[step_id])
    return seen


def _validate_cycles(reachable: Set[str], by_id: Dict[str, Step], errors: List[str]) -> None:
    for source in sorted(reachable):
        for transition in by_id[source].transitions:
            if transition.target not in reachable:
                continue
            if source in _reachable(transition.target, by_id):
                if not transition.bounded_retry and not transition.loop_rationale.strip():
                    errors.append(
                        f"cycle transition {source}->{transition.target} is unbounded"
                    )


def _validate_governance(entry: str, by_id: Dict[str, Step], errors: List[str]) -> None:
    pending = deque([(entry, False, False)])
    seen: Set[Tuple[str, bool, bool]] = set()
    while pending:
        step_id, approved_before, agent_path = pending.popleft()
        marker = (step_id, approved_before, agent_path)
        if marker in seen or step_id not in by_id:
            continue
        seen.add(marker)
        step = by_id[step_id]
        is_agent_path = agent_path or step.actor.lower() == "agent"
        if (step.high_risk or step.action.lower() in HIGH_RISK_ACTIONS) and not approved_before:
            errors.append(f"high-risk step {step.id} lacks prior human approval")
        if is_agent_path and (
            step.current_state in {"verified", "published"}
            or step.action.lower() in {"verify", "publish"}
        ):
            errors.append(f"agent path reaches governed action/state at step {step.id}")
        approved_after = approved_before or step.human_approval
        for transition in step.transitions:
            if is_agent_path and transition.next_state in {"verified", "published"}:
                errors.append(
                    f"agent path transitions to {transition.next_state} at step {step.id}"
                )
            pending.append((transition.target, approved_after, is_agent_path))
