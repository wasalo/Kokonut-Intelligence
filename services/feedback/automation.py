"""Feedback Loop Automation — closes the feedback loop that's structurally complete but dormant.

Periodically evaluates outcomes, generates feedback signals, and
applies adjustments. Supports dry-run mode for review before auto-apply.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class FeedbackAutomation:
    """Automates feedback loop evaluation and adjustment."""

    def __init__(self, conn=None, dry_run: bool = True):
        self._conn = conn
        self._dry_run = dry_run

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def run_evaluation(
        self, location_id: Optional[str] = None, since_hours: int = 168
    ) -> Dict[str, Any]:
        """Evaluate recent outcomes and generate feedback signals."""
        if since_hours < 0:
            raise ValueError("since_hours must be non-negative")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        start_time = time.time()

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Insert running log
        cur.execute("""
            INSERT INTO feedback_automation_log (
                id, run_type, location_id, status, started_at, created_at
            ) VALUES (%s, 'evaluate', %s, 'running', %s, %s)
        """, (log_id, location_id, now, now))
        conn.commit()

        try:
            # Find unprocessed outcomes
            conditions = [
                "ao.feedback_applied = FALSE",
                "NOT EXISTS (SELECT 1 FROM feedback_loop fl "
                "WHERE fl.source_outcome_id = ao.id)",
            ]
            params: list = []

            if location_id:
                conditions.append("ao.location_id = %s")
                params.append(location_id)

            where_clause = " AND ".join(conditions)

            cur.execute(f"""
                SELECT ao.*, dl.policy_id
                FROM action_outcome ao
                LEFT JOIN decision_log dl ON dl.id = ao.decision_id
                WHERE {where_clause}
                  AND ao.measured_at > NOW() - (%s * INTERVAL '1 hour')
                  ORDER BY ao.measured_at DESC
            """, params + [since_hours])
            outcomes = [dict(r) for r in cur.fetchall()]

            signals = []
            for outcome in outcomes:
                signal = self._analyze_outcome(outcome)
                if signal:
                    signals.append(signal)

            # Update log
            duration_ms = (time.time() - start_time) * 1000
            cur.execute("""
                UPDATE feedback_automation_log
                SET status = 'completed',
                    outcomes_evaluated = %s,
                    feedback_signals_generated = %s,
                    run_duration_ms = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (len(outcomes), len(signals), duration_ms, log_id))
            conn.commit()

            return {
                "log_id": log_id,
                "status": "completed",
                "outcomes_evaluated": len(outcomes),
                "signals_generated": len(signals),
                "signals": signals,
                "duration_ms": round(duration_ms, 2),
            }

        except Exception as e:
            conn.rollback()
            cur.execute("""
                UPDATE feedback_automation_log
                SET status = 'failed', errors = %s, completed_at = NOW()
                WHERE id = %s
            """, (psycopg2.extras.Json([str(e)]), log_id))
            conn.commit()
            return {
                "log_id": log_id,
                "status": "failed",
                "error": str(e),
            }
        finally:
            cur.close()

    def run_full_cycle(
        self, location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evaluate outcomes + apply feedback + update thresholds."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        start_time = time.time()

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Insert running log
        cur.execute("""
            INSERT INTO feedback_automation_log (
                id, run_type, location_id, status, started_at, created_at
            ) VALUES (%s, 'full_cycle', %s, 'running', %s, %s)
        """, (log_id, location_id, now, now))
        conn.commit()

        try:
            # Evaluate outcomes
            eval_result = self.run_evaluation(location_id)

            # Apply feedback from generated signals
            applied_count = 0
            proposed_count = 0
            adjusted_count = 0

            if eval_result["signals"]:
                for signal in eval_result["signals"]:
                    if self._dry_run:
                        continue

                    # Apply the feedback
                    apply_result = self._apply_signal(cur, signal)
                    if apply_result.get("proposed"):
                        proposed_count += 1
                    if apply_result.get("adjusted"):
                        adjusted_count += 1

            if not self._dry_run:
                conn.commit()

            duration_ms = (time.time() - start_time) * 1000
            cur.execute("""
                UPDATE feedback_automation_log
                SET status = 'completed',
                    outcomes_evaluated = %s,
                    feedback_signals_generated = %s,
                    feedback_loops_applied = %s,
                    thresholds_adjusted = %s,
                    run_duration_ms = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (
                eval_result["outcomes_evaluated"],
                eval_result["signals_generated"],
                applied_count,
                adjusted_count,
                duration_ms,
                log_id,
            ))
            conn.commit()

            return {
                "log_id": log_id,
                "status": "completed",
                "outcomes_evaluated": eval_result["outcomes_evaluated"],
                "signals_generated": eval_result["signals_generated"],
                "feedback_loops_applied": applied_count,
                "feedback_loops_proposed": proposed_count,
                "thresholds_adjusted": adjusted_count,
                "dry_run": self._dry_run,
                "duration_ms": round(duration_ms, 2),
            }

        except Exception as e:
            conn.rollback()
            cur.execute("""
                UPDATE feedback_automation_log
                SET status = 'failed', errors = %s, completed_at = NOW()
                WHERE id = %s
            """, (psycopg2.extras.Json([str(e)]), log_id))
            conn.commit()
            return {"log_id": log_id, "status": "failed", "error": str(e)}
        finally:
            cur.close()

    def get_automation_log(
        self, location_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get history of automation runs."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if location_id:
            cur.execute("""
                SELECT * FROM feedback_automation_log
                WHERE location_id = %s
                ORDER BY started_at DESC
                LIMIT %s
            """, (location_id, limit))
        else:
            cur.execute("""
                SELECT * FROM feedback_automation_log
                ORDER BY started_at DESC
                LIMIT %s
            """, (limit,))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def configure(
        self,
        location_id: Optional[str],
        eval_interval_hours: int = 24,
        dry_run: bool = True,
        max_adjustments: int = 5,
        auto_apply: bool = False,
    ) -> Dict[str, Any]:
        """Configure automation parameters for a location."""
        if auto_apply:
            raise ValueError(
                "Automatic feedback application is disabled; human approval is required"
            )
        if eval_interval_hours <= 0 or max_adjustments < 0:
            raise ValueError("Invalid feedback automation limits")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            INSERT INTO feedback_automation_config (
                location_id, eval_interval_hours, max_adjustments_per_run,
                auto_apply, dry_run, enabled, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
            ON CONFLICT (location_id) DO UPDATE SET
                eval_interval_hours = EXCLUDED.eval_interval_hours,
                max_adjustments_per_run = EXCLUDED.max_adjustments_per_run,
                auto_apply = EXCLUDED.auto_apply,
                dry_run = EXCLUDED.dry_run,
                updated_at = NOW()
            RETURNING *
        """, (location_id, eval_interval_hours, max_adjustments, auto_apply, dry_run))

        row = dict(cur.fetchone())
        conn.commit()
        cur.close()

        self._dry_run = dry_run
        return row

    def get_pending_adjustments(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List adjustments that would be applied (for review)."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["fl.status = 'proposed'"]
        params: list = []

        if location_id:
            conditions.append("ao.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT fl.*, ao.action_type, ao.outcome_type
            FROM feedback_loop fl
            JOIN action_outcome ao ON ao.id = fl.source_outcome_id
            WHERE {where_clause}
            ORDER BY fl.created_at DESC
            LIMIT 50
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # --- Private helpers ---

    def _analyze_outcome(
        self, outcome: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single outcome and generate a feedback signal."""
        outcome_type = outcome.get("outcome_type", "unknown")
        action_type = outcome.get("action_type", "")
        location_id = outcome.get("location_id")

        signal = {
            "outcome_id": str(outcome["id"]),
            "outcome_type": outcome_type,
            "action_type": action_type,
            "location_id": location_id,
        }

        if outcome_type in ("ineffective", "counterproductive"):
            signal["recommendation"] = "increase_threshold"
            signal["priority"] = "high"
            signal["reason"] = (
                f"Action '{action_type}' was {outcome_type}. "
                "Consider adjusting thresholds or switching approach."
            )
            return signal

        if outcome_type == "no_effect":
            signal["recommendation"] = "review_threshold"
            signal["priority"] = "medium"
            signal["reason"] = (
                f"Action '{action_type}' had no effect. "
                "Threshold may be too sensitive or action not targeted."
            )
            return signal

        if outcome_type == "partially_effective":
            signal["recommendation"] = "fine_tune"
            signal["priority"] = "low"
            signal["reason"] = (
                f"Action '{action_type}' was partially effective. "
                "Minor threshold adjustment may improve results."
            )
            return signal

        return None

    def _apply_signal(
        self, cur, signal: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Apply a feedback signal by creating a feedback_loop record."""
        outcome_id = signal["outcome_id"]
        action_type = signal["action_type"]
        location_id = signal["location_id"]
        recommendation = signal.get("recommendation", "")

        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if recommendation == "increase_threshold":
            adjustment_magnitude = 0.1
        elif recommendation == "fine_tune":
            adjustment_magnitude = 0.05
        else:
            adjustment_magnitude = 0.0

        cur.execute("""
            INSERT INTO feedback_loop (
                id, loop_type, source_outcome_id,
                target_entity, target_field,
                new_value, adjustment_reason, adjustment_magnitude,
                status, created_at, updated_at
            ) VALUES (%s, 'threshold_adjustment', %s, 'adaptive_threshold',
                      'current_value', %s, %s, %s, 'proposed', %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            feedback_id, outcome_id,
            psycopg2.extras.Json({
                "recommendation": recommendation,
                "action_type": action_type,
                "location_id": location_id,
            }),
            signal.get("reason", "automated feedback"),
            adjustment_magnitude,
            now, now,
        ))

        return {
            "proposed": cur.rowcount == 1,
            "applied": False,
            "adjusted": False,
        }

    # --- Process-specific feedback signals ---

    def evaluate_process_health(
        self, location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate feedback signals based on process health metrics.

        Checks:
        - Process health conformance drops below threshold
        - Process cost exceeds target
        - Process maturity assessment changes
        - Handoff SLA compliance drops
        """
        conn = self._get_conn()
        signals = []

        # 1. Check conformance
        try:
            from services.analytics import process_mining as pm, value_stream
            for etype in value_stream.INSTRUMENTED_TYPES:
                traces = pm.get_traces(conn, entity_type=etype)
                if len(traces) < 5:
                    continue
                model = pm.load_model(conn, etype)
                conforming = 0
                total = 0
                for (_e, _id), trace in traces.items():
                    seq = [t["to_status"] for t in trace]
                    if seq:
                        total += 1
                        is_conf, _ = pm.classify_conformance(seq, model)
                        if is_conf:
                            conforming += 1
                if total > 0:
                    ratio = conforming / total
                    if ratio < 0.8:
                        signals.append({
                            "signal_type": "process_conformance_low",
                            "entity_type": etype,
                            "conformance_ratio": round(ratio, 4),
                            "priority": "high",
                            "reason": f"Conformance for {etype} is {ratio:.0%}, below 80% threshold.",
                            "recommendation": "review_process_violations",
                        })
        except Exception:
            pass

        # 2. Check process cost
        try:
            from services.analytics.process_costing import process_cost_per_instance
            process_keys = [
                "farm_operations", "harvest_management", "data_publication",
                "impact_verification", "metric_governance",
            ]
            for pk in process_keys:
                cost = process_cost_per_instance(conn, pk)
                if cost["total_cost"] > 100:
                    signals.append({
                        "signal_type": "process_cost_high",
                        "process_key": pk,
                        "total_cost": cost["total_cost"],
                        "priority": "medium",
                        "reason": f"Total cost for {pk} is ${cost['total_cost']:.2f}, exceeding $100 threshold.",
                        "recommendation": "review_cost_structure",
                    })
        except Exception:
            pass

        # 3. Check handoff SLA compliance
        try:
            from services.analytics.process_interfaces import handoff_sla_compliance
            compliance = handoff_sla_compliance(conn)
            overall = compliance.get("overall", {})
            if overall.get("compliance_pct") is not None and overall["compliance_pct"] < 90:
                signals.append({
                    "signal_type": "handoff_sla_low",
                    "compliance_pct": overall["compliance_pct"],
                    "breached_count": overall.get("breached", 0),
                    "priority": "high",
                    "reason": f"Handoff SLA compliance is {overall['compliance_pct']:.0f}%, below 90% threshold.",
                    "recommendation": "review_handoff_bottlenecks",
                })
        except Exception:
            pass

        # 4. Check maturity level
        try:
            from services.analytics.process_gap import assess_maturity
            maturity_signals = []
            process_keys = [
                "farm_operations", "harvest_management", "data_publication",
                "impact_verification", "metric_governance",
            ]
            for pk in process_keys:
                mat = assess_maturity(conn, pk)
                if mat["level"] <= 1:
                    maturity_signals.append({
                        "process_key": pk,
                        "level": mat["level"],
                        "level_name": mat["level_name"],
                    })
            if maturity_signals:
                signals.append({
                    "signal_type": "process_maturity_low",
                    "processes": maturity_signals,
                    "priority": "medium",
                    "reason": f"{len(maturity_signals)} processes at maturity level 1 (Initial).",
                    "recommendation": "define_workflow_specs_and_targets",
                })
        except Exception:
            pass

        return {
            "signals_generated": len(signals),
            "signals": signals,
        }
