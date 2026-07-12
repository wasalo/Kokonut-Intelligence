"""Causal Loop Diagram Engine — defines reinforcing/balancing feedback structures.

Provides static causal loop definitions for common farm systems, evaluates
loop state from current data, and detects which loops are active.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import FARM_CAUSAL_LOOPS


class CausalLoopEngine:
    """Manages and evaluates causal loop diagrams for farm systems."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def load_loop(self, loop_name: str) -> Optional[Dict[str, Any]]:
        """Load a causal loop definition by name."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM causal_loop WHERE loop_name = %s AND is_enabled = TRUE
        """, (loop_name,))
        loop_row = cur.fetchone()

        if loop_row is None:
            cur.close()
            return None

        loop = dict(loop_row)

        cur.execute("""
            SELECT * FROM causal_link WHERE loop_id = %s ORDER BY source_variable
        """, (loop["id"],))
        loop["links"] = [dict(r) for r in cur.fetchall()]
        cur.close()

        return loop

    def list_loops(
        self,
        domain: Optional[str] = None,
        loop_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all causal loops with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["cl.is_enabled = TRUE"]
        params = []

        if domain:
            conditions.append("cl.domain = %s")
            params.append(domain)
        if loop_type:
            conditions.append("cl.loop_type = %s")
            params.append(loop_type)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT cl.*, COUNT(cl.id) as link_count
            FROM causal_loop cl
            LEFT JOIN causal_link cll ON cll.loop_id = cl.id
            WHERE {where_clause}
            GROUP BY cl.id
            ORDER BY cl.loop_name
        """, params)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def evaluate_loop(
        self, loop_name: str, location_id: str
    ) -> Dict[str, Any]:
        """Evaluate the current state of a causal loop for a location.

        Returns the loop definition with current variable values and
        loop strength assessment.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        loop = self.load_loop(loop_name)
        if loop is None:
            cur.close()
            return {"error": f"Loop '{loop_name}' not found"}

        # Gather current variable values
        variable_values = {}
        for link in loop["links"]:
            for var_name in [link["source_variable"], link["target_variable"]]:
                if var_name not in variable_values:
                    value = self._get_variable_value(
                        cur, var_name, location_id
                    )
                    variable_values[var_name] = value

        # Compute loop strength
        loop_strength = self._compute_loop_strength(loop, variable_values)

        cur.close()

        return {
            "loop_name": loop_name,
            "loop_type": loop["loop_type"],
            "domain": loop["domain"],
            "description": loop["description"],
            "variable_values": variable_values,
            "loop_strength": loop_strength,
            "link_count": len(loop["links"]),
            "archetype": loop.get("archetype"),
        }

    def list_active_loops(
        self, location_id: str, threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """List causal loops that are currently active for a location.

        A loop is considered active if its strength exceeds the threshold.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT loop_name FROM causal_loop WHERE is_enabled = TRUE
        """, ())

        loop_names = [r["loop_name"] for r in cur.fetchall()]
        cur.close()

        active_loops = []
        for loop_name in loop_names:
            result = self.evaluate_loop(loop_name, location_id)
            if "error" not in result and result["loop_strength"] > threshold:
                active_loops.append(result)

        active_loops.sort(key=lambda x: x["loop_strength"], reverse=True)
        return active_loops

    def get_loop_variables(self, loop_name: str) -> List[str]:
        """Get all unique variable names in a loop."""
        loop = self.load_loop(loop_name)
        if loop is None:
            return []

        variables = set()
        for link in loop["links"]:
            variables.add(link["source_variable"])
            variables.add(link["target_variable"])

        return sorted(variables)

    def _get_variable_value(
        self, cur, variable_name: str, location_id: str
    ) -> Optional[float]:
        """Get the current value of a system variable."""
        # Try system_variable table first
        cur.execute("""
            SELECT current_value FROM system_variable
            WHERE variable_name = %s AND location_id = %s
        """, (variable_name, location_id))
        row = cur.fetchone()
        if row is not None:
            return float(row["current_value"])

        # Fall back to metric lookup
        metric_mapping = {
            "soil_carbon": "soil_carbon_delta",
            "water_retention": "water_resilience",
            "crop_yield": "crop_revenue",
            "revenue": "value_flowed",
            "training_events": "attestation_coverage",
            "biodiversity": "biodiversity_delta",
            "soil_structure": "soil_carbon_delta",
            "organic_matter": "soil_carbon_delta",
        }

        metric_key = metric_mapping.get(variable_name)
        if metric_key:
            cur.execute("""
                SELECT mv.value FROM metric_value mv
                JOIN metric_definition md ON md.id = mv.metric_definition_id
                WHERE mv.location_id = %s AND md.metric_key = %s
                AND mv.verified = TRUE
                ORDER BY mv.computed_at DESC LIMIT 1
            """, (location_id, metric_key))
            row = cur.fetchone()
            if row is not None:
                return float(row["value"])

        return None

    def _compute_loop_strength(
        self,
        loop: Dict[str, Any],
        variable_values: Dict[str, Optional[float]],
    ) -> float:
        """Compute the overall strength of a causal loop.

        Strength is based on:
        1. How many variables have known values (data completeness)
        2. The polarity consistency (all links reinforcing or all balancing)
        3. The number of links
        """
        links = loop["links"]
        if not links:
            return 0.0

        # Data completeness factor
        known_count = sum(
            1 for v in variable_values.values() if v is not None
        )
        total_vars = len(variable_values)
        completeness = known_count / total_vars if total_vars > 0 else 0.0

        # Link density factor (normalized to 0-1)
        link_density = min(len(links) / 6.0, 1.0)

        # Polarity consistency (all + or all - is stronger than mixed)
        polarities = [link["polarity"] for link in links]
        pos_count = polarities.count("+")
        neg_count = polarities.count("-")
        consistency = max(pos_count, neg_count) / len(polarities)

        # Weighted combination
        strength = (
            0.4 * completeness
            + 0.3 * link_density
            + 0.3 * consistency
        )

        return round(strength, 3)
