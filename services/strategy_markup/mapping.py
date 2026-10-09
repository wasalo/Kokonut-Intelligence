"""Map canonical PostgreSQL rows into the normalized strategy model."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from .ids import stable_id
from .model import (
    PerformanceIndicator,
    StrategyDocument,
    StrategyGoal,
    StrategyObjective,
    StrategyStatement,
    ValueChainLink,
)


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _number(value: Any):
    return float(value) if value is not None else None


def normalize_strategy(
    plan: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]],
    statements: Iterable[Mapping[str, Any]] = (),
    indicators: Iterable[Mapping[str, Any]] = (),
    value_chain: Iterable[Mapping[str, Any]] = (),
) -> StrategyDocument:
    """Create a deterministic, typed strategy document from database rows."""
    groups: "OrderedDict[str, list[StrategyObjective]]" = OrderedDict()
    sorted_entries = sorted(
        entries,
        key=lambda row: (
            str(row.get("strategic_theme") or row.get("perspective") or "General"),
            str(row.get("perspective") or ""),
            str(row.get("statement") or ""),
            str(row.get("id") or ""),
        ),
    )
    for entry in sorted_entries:
        theme = str(entry.get("strategic_theme") or entry.get("perspective") or "General")
        objective = StrategyObjective(
            id=str(entry["id"]),
            statement=str(entry.get("statement") or ""),
            perspective=entry.get("perspective"),
            theme=theme,
            target_value=_number(entry.get("target_value")),
            current_value=_number(entry.get("current_value")),
            unit=entry.get("unit"),
            status=entry.get("status"),
        )
        groups.setdefault(theme, []).append(objective)
    goals = tuple(
        StrategyGoal(
            id=stable_id("goal", f"{plan['id']}:{name}"),
            name=name,
            objectives=tuple(objectives),
        )
        for name, objectives in groups.items()
    )
    normalized_indicators = tuple(
        PerformanceIndicator(
            id=str(row["id"]),
            name=str(row.get("name") or row.get("metric_key") or row["id"]),
            objective_id=str(row["objective_id"]) if row.get("objective_id") else None,
            description=row.get("description"),
            metric_key=row.get("metric_key"),
            baseline_value=_number(row.get("baseline_value")),
            target_value=_number(row.get("target_value")),
            actual_value=_number(row.get("actual_value")),
            period_start=_as_date(row["period_start"]) if row.get("period_start") else None,
            period_end=_as_date(row["period_end"]) if row.get("period_end") else None,
            direction=row.get("direction") or "gte",
            unit=row.get("unit"),
            calculation_method=row.get("calculation_method"),
            data_source_type=row.get("data_source_type"),
            data_source_ref=row.get("data_source_ref"),
            evidence_maturity=row.get("evidence_maturity"),
            stakeholder_impact=row.get("stakeholder_impact"),
            variance_value=_number(row.get("variance_value")),
            variance_pct=_number(row.get("variance_pct")),
            variance_explanation=row.get("variance_explanation"),
            review_status=row.get("review_status") or "draft",
        )
        for row in sorted(indicators, key=lambda row: (str(row.get("name") or ""), str(row.get("id"))))
    )
    normalized_chain = tuple(
        ValueChainLink(
            id=str(row["id"]),
            value_chain_type=str(row["value_chain_type"]),
            name=str(row["name"]),
            performance_indicator_id=str(row["performance_indicator_id"]) if row.get("performance_indicator_id") else None,
            record_type=row.get("record_type"),
            record_id=str(row["record_id"]) if row.get("record_id") else None,
            description=row.get("description"),
            sequence_order=int(row.get("sequence_order") or 1),
            status=row.get("status") or "draft",
        )
        for row in sorted(value_chain, key=lambda row: (str(row.get("value_chain_type")), int(row.get("sequence_order") or 1), str(row.get("id"))))
    )
    return StrategyDocument(
        id=str(plan["id"]),
        name=str(plan["name"]),
        status=str(plan["status"]),
        version=int(plan.get("version") or 1),
        horizon_start=_as_date(plan["planning_horizon_start"]),
        horizon_end=_as_date(plan["planning_horizon_end"]),
        diagnosis_summary=str(plan.get("diagnosis_summary") or ""),
        guiding_policy=str(plan.get("guiding_policy") or ""),
        theory_of_change=plan.get("theory_of_change"),
        uncertainty_summary=plan.get("uncertainty_summary"),
        statements=tuple(
            StrategyStatement(str(row["id"]), str(row["statement_type"]), str(row["statement_text"]))
            for row in sorted(statements, key=lambda row: (str(row.get("statement_type")), str(row.get("id"))))
        ),
        goals=goals,
        indicators=normalized_indicators,
        value_chain=normalized_chain,
    )
