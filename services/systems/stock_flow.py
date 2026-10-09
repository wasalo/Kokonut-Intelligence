"""Stock-and-Flow Simulator — dynamic system modeling with PySD.

Provides predefined system dynamics models for farm systems and
runs simulations to project outcomes over time.
"""

from __future__ import annotations

import ast
import operator
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


# Try importing PySD
try:
    import pysd
    PYSD_AVAILABLE = True
except ImportError:
    PYSD_AVAILABLE = False


# Predefined model equations (simplified Euler integration)
PREDEFINED_MODELS = {
    "soil_carbon": {
        "description": "Soil carbon dynamics with organic matter inputs and decomposition",
        "time_unit": "day",
        "stocks": {
            "soil_carbon": {"initial": 50.0, "unit": "tonnes/ha"},
        },
        "flows": {
            "carbon_input": {"from": None, "to": "soil_carbon", "rate": "0.5"},
            "carbon_decomposition": {"from": "soil_carbon", "to": None, "rate": "soil_carbon * 0.02"},
        },
        "equations": {
            "soil_carbon": "INTEG(carbon_input - carbon_decomposition, 50)",
            "carbon_input": "IF THEN ELSE(practice_type = 'cover_crop', 0.8, 0.3)",
            "carbon_decomposition": "soil_carbon * 0.02",
        },
    },
    "water_balance": {
        "description": "Water balance with rainfall, evaporation, and runoff",
        "time_unit": "day",
        "stocks": {
            "soil_water": {"initial": 100.0, "unit": "mm"},
        },
        "flows": {
            "rainfall": {"from": None, "to": "soil_water", "rate": "5.0"},
            "evaporation": {"from": "soil_water", "to": None, "rate": "soil_water * 0.01"},
            "runoff": {"from": "soil_water", "to": None, "rate": "MAX(0, soil_water - 150) * 0.05"},
        },
        "equations": {
            "soil_water": "INTEG(rainfall - evaporation - runoff, 100)",
            "rainfall": "5.0",
            "evaporation": "soil_water * 0.01",
            "runoff": "MAX(0, soil_water - 150) * 0.05",
        },
    },
    "financial_sustainability": {
        "description": "Financial sustainability with revenue, costs, and reserves",
        "time_unit": "month",
        "stocks": {
            "cash_reserve": {"initial": 10000.0, "unit": "USD"},
        },
        "flows": {
            "revenue": {"from": None, "to": "cash_reserve", "rate": "2000"},
            "operating_cost": {"from": "cash_reserve", "to": None, "rate": "1500"},
            "investment": {"from": "cash_reserve", "to": None, "rate": "300"},
        },
        "equations": {
            "cash_reserve": "INTEG(revenue - operating_cost - investment, 10000)",
            "revenue": "2000",
            "operating_cost": "1500",
            "investment": "300",
        },
    },
    "crop_yield": {
        "description": "Crop yield dynamics with soil health and weather effects",
        "time_unit": "month",
        "stocks": {
            "soil_fertility": {"initial": 70.0, "unit": "index"},
        },
        "flows": {
            "fertility_gain": {"from": None, "to": "soil_fertility", "rate": "IF THEN ELSE(use_cover_crop, 2.0, 0.5)"},
            "fertility_loss": {"from": "soil_fertility", "to": None, "rate": "IF THEN ELSE(use_tillage, 3.0, 1.0)"},
        },
        "equations": {
            "soil_fertility": "INTEG(fertility_gain - fertility_loss, 70)",
            "crop_yield_index": "soil_fertility * 0.8 + weather_factor * 0.2",
            "weather_factor": "1.0",
        },
    },
}


class StockFlowSimulator:
    """Runs stock-and-flow simulations for farm systems."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def list_models(self) -> List[Dict[str, Any]]:
        """List all available stock-and-flow models."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT id, model_name, description, time_unit, is_enabled
            FROM stock_flow_model WHERE is_enabled = TRUE
            ORDER BY model_name
        """)
        db_models = [dict(r) for r in cur.fetchall()]
        cur.close()

        # Add predefined models
        all_models = []
        for name, config in PREDEFINED_MODELS.items():
            all_models.append({
                "model_name": name,
                "description": config["description"],
                "time_unit": config["time_unit"],
                "source": "predefined",
            })

        for model in db_models:
            model["source"] = "database"
            all_models.append(model)

        return all_models

    def run_simulation(
        self,
        model_name: str,
        location_id: str,
        scenario_name: str = "baseline",
        duration: int = 365,
        time_step: int = 1,
        parameters: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Run a stock-and-flow simulation.

        Args:
            model_name: Name of the model to simulate.
            location_id: Location for context-specific parameters.
            scenario_name: Name of this scenario run.
            duration: Simulation duration in model time units.
            time_step: Time step size.
            parameters: Override model parameters.

        Returns:
            Simulation results with trajectory and summary.
        """
        config = PREDEFINED_MODELS.get(model_name)
        if config is None:
            return {"error": f"Model '{model_name}' not found"}

        # Get initial conditions from DB if available
        initial = self._get_initial_conditions(model_name, location_id)
        if parameters:
            initial.update(parameters)

        # Run Euler integration simulation
        trajectory = self._run_euler(
            config, initial, duration, time_step
        )

        # Compute summary statistics
        summary = self._compute_summary(trajectory, config)

        # Persist run
        run_id = self._persist_run(
            model_name, location_id, scenario_name,
            parameters or {}, trajectory, summary, duration, time_step
        )

        return {
            "run_id": run_id,
            "model_name": model_name,
            "scenario_name": scenario_name,
            "duration": duration,
            "time_step": time_step,
            "trajectory": trajectory,
            "summary": summary,
        }

    def compare_scenarios(
        self,
        model_name: str,
        location_id: str,
        scenario_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compare multiple scenarios for a model.

        Args:
            model_name: Name of the model.
            location_id: Location for context.
            scenario_list: List of {name, parameters} dicts.

        Returns:
            Comparison of scenario outcomes.
        """
        results = []
        for scenario in scenario_list:
            result = self.run_simulation(
                model_name, location_id,
                scenario_name=scenario.get("name", "unnamed"),
                parameters=scenario.get("parameters"),
            )
            results.append({
                "scenario": scenario.get("name", "unnamed"),
                "parameters": scenario.get("parameters", {}),
                "final_values": result["summary"],
                "trajectory_length": len(result["trajectory"]),
            })

        return {
            "model_name": model_name,
            "scenario_count": len(results),
            "scenarios": results,
        }

    def monte_carlo_stock(
        self,
        model_name: str,
        location_id: str,
        stock_name: str,
        *,
        parameter_sampler: Dict[str, Any],
        n: int = 500,
        seed: Optional[int] = None,
        max_workers: int = 8,
        duration: int = 365,
        time_step: int = 1,
    ) -> Dict[str, Any]:
        """Run a Monte Carlo ensemble over a stock-and-flow model.

        ADVISORY-ONLY: returns a distribution of a chosen stock's final value
        under perturbed model parameters. ``run_simulation`` persists a run row
        per draw (legitimate history, not governed state). No publish/act effects.

        Args:
            model_name: Model to simulate (e.g. "soil_carbon").
            location_id: Location for context.
            stock_name: Which stock's final value to aggregate.
            parameter_sampler: Mapping of model parameter -> distribution spec.
            n: Number of draws.
            seed: RNG seed for reproducibility.
            max_workers: Bound on concurrent draws (each opens its own connection).
            duration / time_step: Forwarded to ``run_simulation``.

        Returns:
            Distribution dict from ``services.simulation.resolution.monte_carlo``.
        """
        from ..simulation.resolution import monte_carlo
        from .base import get_db

        metric = f"summary.{stock_name}.final"

        def _sim(conn, **params):
            return self.run_simulation(
                model_name, location_id,
                scenario_name="monte_carlo",
                duration=duration, time_step=time_step,
                parameters=params,
            )

        return monte_carlo(
            _sim,
            {},
            sampler=parameter_sampler,
            metric=metric,
            conn_factory=get_db,
            n=n,
            seed=seed,
            max_workers=max_workers,
        )

    def get_trajectory(
        self, model_name: str, location_id: str, scenario: str = "baseline"
    ) -> List[Dict[str, Any]]:
        """Get the trajectory for a recent simulation run."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT trajectory FROM stock_flow_run
            WHERE location_id = %s AND scenario_name = %s
            ORDER BY run_at DESC LIMIT 1
        """, (location_id, scenario))

        row = cur.fetchone()
        cur.close()
        if row is None:
            return []
        return row["trajectory"]

    # --- Private helpers ---

    def _get_initial_conditions(
        self, model_name: str, location_id: str
    ) -> Dict[str, float]:
        """Get initial conditions from database or defaults."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        initial = {}

        # Try to get from system_variable table
        cur.execute("""
            SELECT variable_name, current_value
            FROM system_variable
            WHERE location_id = %s AND variable_type = 'stock'
        """, (location_id,))
        for row in cur.fetchall():
            initial[row["variable_name"]] = float(row["current_value"])

        cur.close()

        # Fill in defaults from model config
        config = PREDEFINED_MODELS.get(model_name, {})
        for stock_name, stock_config in config.get("stocks", {}).items():
            if stock_name not in initial:
                initial[stock_name] = stock_config["initial"]

        return initial

    def _run_euler(
        self,
        config: Dict,
        initial: Dict[str, float],
        duration: int,
        time_step: int,
    ) -> List[Dict[str, Any]]:
        """Run Euler integration simulation."""
        trajectory = []

        stocks = {}
        for name, stock_config in config.get("stocks", {}).items():
            stocks[name] = initial.get(name, stock_config["initial"])

        for t in range(0, duration + 1, time_step):
            # Record current state
            record = {"time": t}
            record.update(stocks)

            # Compute flows
            flows = {}
            for flow_name, flow_config in config.get("flows", {}).items():
                rate_expr = flow_config.get("rate", "0")
                # Simple expression evaluation (replace variable names with values)
                rate_val = self._eval_rate(rate_expr, stocks, initial)
                flows[flow_name] = rate_val

            # Update stocks
            for flow_name, flow_config in config.get("flows", {}).items():
                rate = flows[flow_name]
                source = flow_config.get("from")
                target = flow_config.get("to")

                if source and source in stocks:
                    stocks[source] -= rate * time_step
                    stocks[source] = max(stocks[source], 0)
                if target and target in stocks:
                    stocks[target] += rate * time_step
                    stocks[target] = max(stocks[target], 0)

            trajectory.append(record)

        return trajectory

    def _eval_rate(
        self, expr: str, stocks: Dict, initial: Dict
    ) -> float:
        """Simple expression evaluator for flow rates."""
        # Replace variable names with values (longest names first to avoid partial matches)
        for name in sorted(stocks.keys(), key=len, reverse=True):
            expr = expr.replace(name, str(stocks[name]))

        # Handle IF THEN ELSE (simplified)
        if "IF THEN ELSE" in expr:
            # Simplified: just use the first value
            parts = expr.split(",")
            if len(parts) >= 2:
                try:
                    return float(parts[1].strip().rstrip(")"))
                except ValueError:
                    return 0.0

        # Handle MAX
        if "MAX" in expr:
            import re
            match = re.search(r"MAX\(0,\s*([^)]+)\)\s*\*?\s*([0-9.]+)?", expr)
            if match:
                inner = match.group(1)
                multiplier = float(match.group(2)) if match.group(2) else 1.0
                for name, value in stocks.items():
                    inner = inner.replace(name, str(value))
                try:
                    val = self._safe_numeric_eval(inner)
                    return max(0, float(val)) * multiplier
                except Exception:
                    return 0.0

        # Evaluate only a small arithmetic grammar; model expressions are data.
        try:
            return float(self._safe_numeric_eval(expr))
        except Exception:
            return 0.0

    @staticmethod
    def _safe_numeric_eval(expr: str) -> float:
        """Evaluate arithmetic without executing Python code."""
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                value = float(node.value)
                if not math.isfinite(value):
                    raise ValueError("non-finite numeric literal")
                return value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and type(node.op) in operators:
                left = visit(node.left)
                right = visit(node.right)
                value = operators[type(node.op)](left, right)
                if not math.isfinite(value):
                    raise ValueError("non-finite arithmetic result")
                return value
            raise ValueError("unsupported expression")

        return visit(ast.parse(expr, mode="eval"))

    def _compute_summary(
        self, trajectory: List[Dict], config: Dict
    ) -> Dict[str, Any]:
        """Compute summary statistics from trajectory."""
        if not trajectory:
            return {}

        summary = {}
        stocks = config.get("stocks", {})

        for stock_name in stocks:
            values = [r.get(stock_name, 0) for r in trajectory]
            summary[stock_name] = {
                "initial": values[0],
                "final": values[-1],
                "min": min(values),
                "max": max(values),
                "change": values[-1] - values[0],
                "change_pct": round(
                    (values[-1] - values[0]) / values[0] * 100, 1
                ) if values[0] != 0 else None,
            }

        return summary

    def _persist_run(
        self,
        model_name: str,
        location_id: str,
        scenario_name: str,
        parameters: Dict,
        trajectory: List[Dict],
        summary: Dict,
        duration: int,
        time_step: int,
    ) -> str:
        """Persist simulation run to database."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        start_date = now.date()
        end_date = (now + timedelta(days=duration)).date()

        # Get model_id if exists
        cur.execute("""
            SELECT id FROM stock_flow_model WHERE model_name = %s
        """, (model_name,))
        model_row = cur.fetchone()
        model_id = model_row["id"] if model_row else None

        cur.execute("""
            INSERT INTO stock_flow_run (
                id, model_id, location_id, scenario_name,
                parameters, start_date, end_date,
                time_step_days, results, trajectory,
                status, run_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', %s)
        """, (
            run_id, model_id, location_id, scenario_name,
            psycopg2.extras.Json(parameters), start_date, end_date,
            time_step, psycopg2.extras.Json(summary),
            psycopg2.extras.Json(trajectory), now,
        ))

        conn.commit()
        cur.close()
        return run_id
