"""Typed normalized strategy representation used by all projections."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class StrategyStatement:
    id: str
    statement_type: str
    text: str


@dataclass(frozen=True)
class StrategyObjective:
    id: str
    statement: str
    perspective: Optional[str] = None
    theme: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = None
    status: Optional[str] = None


@dataclass(frozen=True)
class StrategyGoal:
    id: str
    name: str
    objectives: tuple[StrategyObjective, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PerformanceIndicator:
    id: str
    name: str
    objective_id: Optional[str] = None
    description: Optional[str] = None
    metric_key: Optional[str] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    actual_value: Optional[float] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    direction: str = "gte"
    unit: Optional[str] = None
    calculation_method: Optional[str] = None
    data_source_type: Optional[str] = None
    data_source_ref: Optional[str] = None
    evidence_maturity: Optional[int] = None
    stakeholder_impact: Optional[str] = None
    variance_value: Optional[float] = None
    variance_pct: Optional[float] = None
    variance_explanation: Optional[str] = None
    review_status: str = "draft"


@dataclass(frozen=True)
class ValueChainLink:
    id: str
    value_chain_type: str
    name: str
    performance_indicator_id: Optional[str] = None
    record_type: Optional[str] = None
    record_id: Optional[str] = None
    description: Optional[str] = None
    sequence_order: int = 1
    status: str = "draft"


@dataclass(frozen=True)
class StrategyDocument:
    id: str
    name: str
    status: str
    version: int
    horizon_start: date
    horizon_end: date
    diagnosis_summary: str = ""
    guiding_policy: str = ""
    theory_of_change: Optional[str] = None
    uncertainty_summary: Optional[str] = None
    statements: tuple[StrategyStatement, ...] = field(default_factory=tuple)
    goals: tuple[StrategyGoal, ...] = field(default_factory=tuple)
    indicators: tuple[PerformanceIndicator, ...] = field(default_factory=tuple)
    value_chain: tuple[ValueChainLink, ...] = field(default_factory=tuple)
