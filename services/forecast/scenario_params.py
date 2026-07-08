"""Scenario parameters: load, resolve, and manage worst/base/best case parameters."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScenarioParam:
    """A single scenario parameter with worst/base/best values."""
    key: str
    category: str
    name: str
    unit: str | None
    base_value: float
    worst_value: float
    best_value: float
    distribution: str = "triangular"
    std_deviation: float | None = None
    min_bound: float | None = None
    max_bound: float | None = None

    def sample(self) -> float:
        """Sample a random value from this parameter's distribution."""
        if self.distribution == "fixed":
            return self.base_value
        elif self.distribution == "uniform":
            return random.uniform(self.worst_value, self.best_value)
        elif self.distribution == "triangular":
            left = min(self.worst_value, self.best_value)
            right = max(self.worst_value, self.best_value)
            return random.triangular(left, right, self.base_value)
        elif self.distribution == "normal":
            mean = self.base_value
            sigma = self.std_deviation or abs(self.best_value - self.worst_value) / 4
            value = random.gauss(mean, sigma)
            if self.min_bound is not None:
                value = max(value, self.min_bound)
            if self.max_bound is not None:
                value = min(value, self.max_bound)
            return value
        elif self.distribution == "lognormal":
            import math
            mean = self.base_value
            sigma = self.std_deviation or 0.5
            value = random.lognormvariate(math.log(max(mean, 0.01)), sigma)
            if self.min_bound is not None:
                value = max(value, self.min_bound)
            if self.max_bound is not None:
                value = min(value, self.max_bound)
            return value
        return self.base_value

    def worst_case(self) -> float:
        """Return the worst-case value."""
        return self.worst_value

    def best_case(self) -> float:
        """Return the best-case value."""
        return self.best_value

    def range_pct(self) -> float:
        """Return the range as a percentage of base value."""
        if self.base_value == 0:
            return 0
        return abs(self.best_value - self.worst_value) / abs(self.base_value) * 100


def load_scenario_params(conn, scenario_id: str) -> dict[str, ScenarioParam]:
    """Load all active parameters for a scenario from the database.

    Returns a dict keyed by parameter_key.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT parameter_key, parameter_category, parameter_name, unit,
               base_value, worst_value, best_value, distribution,
               std_deviation, min_bound, max_bound
        FROM scenario_parameter
        WHERE scenario_id = %s AND is_active = TRUE
        """,
        (scenario_id,),
    )
    rows = cur.fetchall()
    cur.close()

    params = {}
    for row in rows:
        params[row[0]] = ScenarioParam(
            key=row[0],
            category=row[1],
            name=row[2],
            unit=row[3],
            base_value=float(row[4]),
            worst_value=float(row[5]),
            best_value=float(row[6]),
            distribution=row[7] or "triangular",
            std_deviation=float(row[8]) if row[8] is not None else None,
            min_bound=float(row[9]) if row[9] is not None else None,
            max_bound=float(row[10]) if row[10] is not None else None,
        )

    logger.info("Loaded %d parameters for scenario %s", len(params), scenario_id)
    return params


def get_param_value(params: dict[str, ScenarioParam], key: str, case: str = "base") -> float | None:
    """Get a parameter value by key and case (base/worst/best).

    Returns None if the parameter doesn't exist.
    """
    param = params.get(key)
    if param is None:
        return None
    if case == "worst":
        return param.worst_case()
    elif case == "best":
        return param.best_case()
    return param.base_value


def sample_all_params(params: dict[str, ScenarioParam]) -> dict[str, float]:
    """Sample random values for all parameters.

    Returns a dict keyed by parameter_key with sampled values.
    """
    return {key: param.sample() for key, param in params.items()}


def compute_param_summary(params: dict[str, ScenarioParam]) -> dict[str, Any]:
    """Compute a summary of all parameters.

    Returns category-grouped statistics.
    """
    categories: dict[str, list[ScenarioParam]] = {}
    for param in params.values():
        categories.setdefault(param.category, []).append(param)

    summary = {}
    for category, cat_params in categories.items():
        summary[category] = {
            "count": len(cat_params),
            "parameters": [
                {
                    "key": p.key,
                    "name": p.name,
                    "unit": p.unit,
                    "base": p.base_value,
                    "worst": p.worst_value,
                    "best": p.best_value,
                    "range_pct": round(p.range_pct(), 1),
                }
                for p in cat_params
            ],
        }

    return {
        "total_parameters": len(params),
        "categories": summary,
    }


def apply_params_to_forecast(params: dict[str, ScenarioParam], case: str = "base") -> dict[str, Any]:
    """Convert scenario parameters to forecast engine assumptions format.

    Maps scenario_parameter keys to the JSONB structures used by the forecast engine.
    """
    loss_rate = get_param_value(params, "loss_rate", case)
    drought_impact = get_param_value(params, "drought_yield_impact", case)
    pest_loss = get_param_value(params, "pest_disease_loss", case)
    yield_improvement = get_param_value(params, "yield_improvement", case)

    # Yield adjustments: combine loss, drought, and pest impacts
    total_yield_loss = 1.0
    if loss_rate is not None:
        total_yield_loss *= (1 - loss_rate)
    if drought_impact is not None:
        total_yield_loss *= (1 - drought_impact)
    if pest_loss is not None:
        total_yield_loss *= (1 - pest_loss)

    # Cost inflation by category
    cost_adjustments = {}
    for key in ["fertilizer_cost_inflation", "labor_cost_inflation",
                "transport_cost_inflation", "seed_cost_inflation"]:
        val = get_param_value(params, key, case)
        if val is not None:
            category = key.replace("_cost_inflation", "")
            cost_adjustments[category] = val

    # Governance
    public_goods = get_param_value(params, "public_goods_allocation_pct", case)
    retention = get_param_value(params, "retention_rate_pct", case)

    # Weather
    drought_prob = get_param_value(params, "drought_probability", case)
    flood_prob = get_param_value(params, "flood_probability", case)

    # Ecological
    carbon_rate = get_param_value(params, "carbon_sequestration_rate", case)
    biodiversity_price = get_param_value(params, "biodiversity_credit_price", case)

    return {
        "yield_adjustments": {
            "total_yield_loss_factor": round(total_yield_loss, 4),
            "loss_rate": loss_rate,
            "drought_impact": drought_impact,
            "pest_loss": pest_loss,
            "yield_improvement": yield_improvement,
        },
        "cost_adjustments": cost_adjustments,
        "governance": {
            "public_goods_allocation_pct": public_goods,
            "retention_rate_pct": retention,
        },
        "weather": {
            "drought_probability": drought_prob,
            "flood_probability": flood_prob,
        },
        "ecological": {
            "carbon_sequestration_rate": carbon_rate,
            "biodiversity_credit_price": biodiversity_price,
        },
    }
