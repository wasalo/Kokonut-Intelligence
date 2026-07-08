"""Monte Carlo simulation and sensitivity analysis for scenario parameters."""

from __future__ import annotations

import json
import random
import statistics
import time
from typing import Any

from services.common.logging import get_logger
from services.forecast.scenario_params import (
    ScenarioParam,
    apply_params_to_forecast,
    load_scenario_params,
    sample_all_params,
)

logger = get_logger(__name__)


def run_monte_carlo(
    conn,
    scenario_id: str,
    base_noi_usd: float,
    base_yield_tonnes: float,
    base_revenue_usd: float,
    simulations: int = 1000,
) -> dict[str, Any]:
    """Run Monte Carlo simulation across all scenario parameters.

    Samples random values for each parameter and computes the distribution
    of NOI, yield, and revenue outcomes.
    """
    start = time.time()
    params = load_scenario_params(conn, scenario_id)

    if not params:
        return {"error": "No parameters found for scenario", "scenario_id": scenario_id}

    noi_samples = []
    yield_samples = []
    revenue_samples = []

    for _ in range(simulations):
        sampled = sample_all_params(params)
        adjustments = apply_params_to_forecast(
            {k: ScenarioParam(
                key=k, category="", name="", unit=None,
                base_value=sampled[k], worst_value=sampled[k], best_value=sampled[k],
            ) for k, v in params.items()},
            case="base",
        )

        # Apply yield adjustments
        yield_factor = adjustments["yield_adjustments"]["total_yield_loss_factor"]
        yield_improvement = adjustments["yield_adjustments"].get("yield_improvement") or 0
        adj_yield = base_yield_tonnes * yield_factor * (1 + yield_improvement)

        # Apply cost adjustments (simplified: adjust total costs by avg inflation)
        cost_adj = adjustments["cost_adjustments"]
        avg_cost_inflation = (
            sum(cost_adj.values()) / len(cost_adj) if cost_adj else 0
        )

        # Apply governance adjustments
        public_goods_pct = adjustments["governance"].get("public_goods_allocation_pct") or 0.10
        retention_pct = adjustments["governance"].get("retention_rate_pct") or 0.20

        # Compute adjusted revenue (yield-driven)
        revenue_factor = adj_yield / base_yield_tonnes if base_yield_tonnes > 0 else 1
        adj_revenue = base_revenue_usd * revenue_factor

        # Compute adjusted NOI (revenue - costs inflated)
        adj_noi = adj_revenue * (1 - avg_cost_inflation) - (base_noi_usd * public_goods_pct)

        noi_samples.append(round(adj_noi, 2))
        yield_samples.append(round(adj_yield, 4))
        revenue_samples.append(round(adj_revenue, 2))

    # Compute statistics
    noi_sorted = sorted(noi_samples)
    yield_sorted = sorted(yield_samples)
    revenue_sorted = sorted(revenue_samples)

    n = len(noi_sorted)
    elapsed_ms = int((time.time() - start) * 1000)

    result = {
        "scenario_id": scenario_id,
        "simulation_type": "monte_carlo",
        "simulations_count": simulations,
        # NOI statistics
        "mean_noi_usd": round(statistics.mean(noi_samples), 2),
        "median_noi_usd": round(statistics.median(noi_samples), 2),
        "std_dev_noi_usd": round(statistics.stdev(noi_samples), 2) if n > 1 else 0,
        "p10_noi_usd": noi_sorted[int(n * 0.10)],
        "p25_noi_usd": noi_sorted[int(n * 0.25)],
        "p75_noi_usd": noi_sorted[int(n * 0.75)],
        "p90_noi_usd": noi_sorted[int(n * 0.90)],
        "prob_negative_noi": round(sum(1 for x in noi_samples if x < 0) / n, 4),
        "value_at_risk_95": noi_sorted[int(n * 0.05)],
        # Yield statistics
        "mean_yield_tonnes": round(statistics.mean(yield_samples), 4),
        "p10_yield_tonnes": yield_sorted[int(n * 0.10)],
        "p90_yield_tonnes": yield_sorted[int(n * 0.90)],
        # Revenue statistics
        "mean_revenue_usd": round(statistics.mean(revenue_samples), 2),
        "p10_revenue_usd": revenue_sorted[int(n * 0.10)],
        "p90_revenue_usd": revenue_sorted[int(n * 0.90)],
        # Distributions (sampled for storage efficiency)
        "noi_distribution": noi_sorted[::max(1, n // 100)],  # ~100 sample points
        "yield_distribution": yield_sorted[::max(1, n // 100)],
        "revenue_distribution": revenue_sorted[::max(1, n // 100)],
        "execution_time_ms": elapsed_ms,
    }

    logger.info("Monte Carlo: %d sims, mean NOI $%.2f, P(noise)=%.2f%%, %dms",
                simulations, result["mean_noi_usd"],
                result["prob_negative_noi"] * 100, elapsed_ms)
    return result


def run_sensitivity_analysis(
    conn,
    scenario_id: str,
    parameter_key: str,
    base_noi_usd: float,
    base_yield_tonnes: float,
    base_revenue_usd: float,
    steps: int = 10,
) -> dict[str, Any]:
    """Run sensitivity analysis on a single parameter.

    Varies the parameter from worst to best across N steps,
    computing NOI for each step.
    """
    params = load_scenario_params(conn, scenario_id)
    param = params.get(parameter_key)

    if param is None:
        return {"error": f"Parameter '{parameter_key}' not found", "scenario_id": scenario_id}

    # Generate steps from worst to best
    left = min(param.worst_value, param.best_value)
    right = max(param.worst_value, param.best_value)
    step_values = [left + (right - left) * i / (steps - 1) for i in range(steps)]

    curve = []
    for value in step_values:
        # Create a modified param set with this value
        test_params = dict(params)
        test_params[parameter_key] = ScenarioParam(
            key=param.key, category=param.category, name=param.name,
            unit=param.unit, base_value=value, worst_value=param.worst_value,
            best_value=param.best_value, distribution="fixed",
        )
        adjustments = apply_params_to_forecast(test_params, case="base")

        # Compute NOI for this parameter value
        yield_factor = adjustments["yield_adjustments"]["total_yield_loss_factor"]
        yield_improvement = adjustments["yield_adjustments"].get("yield_improvement") or 0
        adj_yield = base_yield_tonnes * yield_factor * (1 + yield_improvement)

        cost_adj = adjustments["cost_adjustments"]
        avg_cost_inflation = sum(cost_adj.values()) / len(cost_adj) if cost_adj else 0

        public_goods_pct = adjustments["governance"].get("public_goods_allocation_pct") or 0.10

        revenue_factor = adj_yield / base_yield_tonnes if base_yield_tonnes > 0 else 1
        adj_revenue = base_revenue_usd * revenue_factor
        adj_noi = adj_revenue * (1 - avg_cost_inflation) - (base_noi_usd * public_goods_pct)

        curve.append({
            "parameter_value": round(value, 6),
            "noi_usd": round(adj_noi, 2),
            "yield_tonnes": round(adj_yield, 4),
            "revenue_usd": round(adj_revenue, 2),
        })

    # Compute sensitivity metric: range of NOI / range of parameter
    noi_values = [c["noi_usd"] for c in curve]
    noi_range = max(noi_values) - min(noi_values)
    param_range = right - left if right != left else 1
    elasticity = noi_range / abs(base_noi_usd) / (param_range / abs(param.base_value)) if param.base_value != 0 and base_noi_usd != 0 else 0

    result = {
        "scenario_id": scenario_id,
        "simulation_type": "sensitivity",
        "parameter_key": parameter_key,
        "parameter_name": param.name,
        "parameter_unit": param.unit,
        "base_value": param.base_value,
        "worst_value": param.worst_value,
        "best_value": param.best_value,
        "steps": steps,
        "sensitivity_curve": curve,
        "noi_range_usd": round(noi_range, 2),
        "elasticity": round(elasticity, 4),
        "impact_rank": None,  # Filled by caller when comparing across parameters
    }

    logger.info("Sensitivity: %s, NOI range $%.2f, elasticity %.4f",
                parameter_key, noi_range, elasticity)
    return result


def run_sensitivity_tornado(
    conn,
    scenario_id: str,
    base_noi_usd: float,
    base_yield_tonnes: float,
    base_revenue_usd: float,
    steps: int = 10,
) -> dict[str, Any]:
    """Run sensitivity analysis across all parameters and rank by impact.

    Returns a tornado chart data structure with parameters ranked by NOI impact.
    """
    params = load_scenario_params(conn, scenario_id)
    results = []

    for key in params:
        analysis = run_sensitivity_analysis(
            conn, scenario_id, key,
            base_noi_usd, base_yield_tonnes, base_revenue_usd, steps,
        )
        if "error" not in analysis:
            results.append(analysis)

    # Rank by NOI range (absolute impact)
    results.sort(key=lambda x: x["noi_range_usd"], reverse=True)
    for i, r in enumerate(results):
        r["impact_rank"] = i + 1

    tornado = {
        "scenario_id": scenario_id,
        "simulation_type": "sensitivity",
        "total_parameters": len(results),
        "parameters": [
            {
                "rank": r["impact_rank"],
                "key": r["parameter_key"],
                "name": r["parameter_name"],
                "unit": r["parameter_unit"],
                "base_value": r["base_value"],
                "worst_value": r["worst_value"],
                "best_value": r["best_value"],
                "noi_range_usd": r["noi_range_usd"],
                "elasticity": r["elasticity"],
                "curve": r["sensitivity_curve"],
            }
            for r in results
        ],
    }

    logger.info("Tornado: %d parameters ranked by impact", len(results))
    return tornado
