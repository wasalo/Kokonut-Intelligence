"""Declarative workflow model."""

from dataclasses import dataclass, field
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class Transition:
    """A guarded outcome connecting two workflow steps."""

    target: str
    next_state: str
    guard: str = "always"
    outcome: str = "continue"
    bounded_retry: bool = False
    loop_rationale: str = ""


Branch = Transition


@dataclass(frozen=True)
class Step:
    """One actor-owned workflow action."""

    id: str
    actor: str
    current_state: str
    action: str
    transitions: Tuple[Transition, ...] = field(default_factory=tuple)
    entry: bool = False
    terminal: bool = False
    transaction_boundary: bool = False
    external_side_effect: bool = False
    human_approval: bool = False
    retry_safe: bool = False
    high_risk: bool = False


@dataclass(frozen=True)
class WorkflowSpec:
    """A complete state and control-flow declaration."""

    id: str
    title: str
    states: FrozenSet[str]
    steps: Tuple[Step, ...]
    invariants: Tuple[str, ...] = field(default_factory=tuple)
    source_refs: Tuple[str, ...] = field(default_factory=tuple)
