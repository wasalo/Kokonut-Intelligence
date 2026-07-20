"""Canonical prediction and calibration operations."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2.extras


CALCULATION_VERSION = "v1"


def _domain_for_metric(metric: str) -> str:
    if any(key in metric for key in ("revenue", "noi", "cash_flow", "value_usd", "margin")):
        return "financial"
    if "yield" in metric or "production" in metric:
        return "yield"
    if "carbon" in metric:
        return "carbon"
    if "biodiversity" in metric or "ecological" in metric:
        return "ecological"
    return "operations"


def _horizon_bucket(seconds: int) -> str:
    days = seconds / 86400
    if days <= 7:
        return "0-7d"
    if days <= 30:
        return "8-30d"
    if days <= 90:
        return "31-90d"
    if days <= 365:
        return "91-365d"
    return "366d+"


class PredictionService:
    def __init__(self, conn):
        self.conn = conn

    def record_forecast_output(self, output_id: str) -> dict[str, Any]:
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT fo.*, fs.version AS scenario_version
            FROM forecast_output fo JOIN forecast_scenario fs ON fs.id = fo.scenario_id
            WHERE fo.id = %s
            """,
            (output_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError("Forecast output not found")
        issued = row["calculated_at"] or datetime.now(timezone.utc)
        target_start = datetime.combine(row["period_start"], datetime.min.time(), timezone.utc)
        target_end = datetime.combine(row["period_end"], datetime.max.time(), timezone.utc)
        horizon = max(0, int((target_end - issued).total_seconds()))
        inputs = row.get("inputs") or {}
        input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()
        cur.execute(
            """
            INSERT INTO prediction_ledger (
                source_table, source_id, domain, metric_key, unit, location_id,
                crop_cycle_id, model_name, model_version, issued_at, target_start,
                target_end, horizon_seconds, predicted_value, interval_low,
                interval_high, confidence_level, inputs, input_hash, status
            ) VALUES ('forecast_output', %s, %s, %s, %s, %s, %s,
                      'kokonut_forecast_engine', %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, 'submitted')
            ON CONFLICT (source_table, source_id, source_point_key) DO UPDATE SET
                predicted_value = EXCLUDED.predicted_value,
                interval_low = EXCLUDED.interval_low,
                interval_high = EXCLUDED.interval_high,
                inputs = EXCLUDED.inputs,
                input_hash = EXCLUDED.input_hash
            RETURNING *
            """,
            (output_id, _domain_for_metric(row["metric_name"]), row["metric_name"], row["unit"],
             row["location_id"], row.get("crop_cycle_id"), row["calculation_version"] or f"scenario-{row['scenario_version']}",
             issued, target_start, target_end, horizon, row["value"],
             min(row.get("confidence_low"), row.get("confidence_high")) if row.get("confidence_low") is not None and row.get("confidence_high") is not None else row.get("confidence_low"),
             max(row.get("confidence_low"), row.get("confidence_high")) if row.get("confidence_low") is not None and row.get("confidence_high") is not None else row.get("confidence_high"),
             row.get("confidence_level"), psycopg2.extras.Json(inputs), input_hash),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result

    def record_outcome(
        self, prediction_id: str, source_table: str, source_id: str,
        actual_timestamp: datetime, actual_value: float, unit: str,
        verified_by: Optional[str] = None, source_status: Optional[str] = None,
    ) -> dict[str, Any]:
        status = "verified" if verified_by else "draft"
        if verified_by:
            uuid.UUID(verified_by)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO prediction_outcome (
                prediction_id, actual_source_table, actual_source_id, actual_timestamp,
                actual_value, unit, source_status, status, verified_by, verified_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      CASE WHEN %s IS NOT NULL THEN NOW() ELSE NULL END)
            RETURNING *
            """,
            (prediction_id, source_table, source_id, actual_timestamp, actual_value,
             unit, source_status, status, verified_by, verified_by),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result

    def resolve_forecast_outcome(self, prediction_id: str) -> dict[str, Any]:
        """Match allowlisted forecast metrics to governed actual records as a draft."""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM prediction_ledger WHERE id=%s", (prediction_id,))
        prediction = cur.fetchone()
        if not prediction:
            cur.close()
            raise ValueError("Prediction not found")
        resolvers = {
            "projected_revenue_usd": ("revenue_event", "amount_usd", "usd"),
            "total_yield_tonnes": ("harvest_event", "quantity", "tonnes"),
            "loss_adjusted_yield_tonnes": ("harvest_event", "quantity", "tonnes"),
        }
        metric = prediction["metric_key"]
        if metric in resolvers:
            table, value_column, unit = resolvers[metric]
            unit_filter = "AND unit = %s" if table == "harvest_event" else ""
            params = [prediction["location_id"], prediction["target_start"], prediction["target_end"]]
            if unit_filter != "":
                params.append(unit)
            cur.execute(
                f"""SELECT COALESCE(SUM({value_column}),0) AS actual_value,
                            ARRAY_AGG(id) AS source_ids, MAX(event_date) AS actual_at
                     FROM {table}
                     WHERE location_id=%s AND event_date BETWEEN %s AND %s
                       AND status IN ('verified','published') {unit_filter}""",
                tuple(params),
            )
            actual = dict(cur.fetchone())
        elif metric in {"projected_noi_usd", "risk_adjusted_noi_usd"}:
            cur.execute(
                """
                SELECT
                  COALESCE((SELECT SUM(amount_usd) FROM revenue_event
                    WHERE location_id=%s AND event_date BETWEEN %s AND %s
                      AND status IN ('verified','published')),0)
                  - COALESCE((SELECT SUM(amount) FROM expense_event
                    WHERE location_id=%s AND expense_date BETWEEN %s AND %s
                      AND status IN ('verified','published')),0) AS actual_value,
                  GREATEST(
                    (SELECT MAX(event_date) FROM revenue_event WHERE location_id=%s),
                    (SELECT MAX(expense_date) FROM expense_event WHERE location_id=%s)
                  ) AS actual_at
                """,
                (prediction["location_id"], prediction["target_start"], prediction["target_end"],
                 prediction["location_id"], prediction["target_start"], prediction["target_end"],
                 prediction["location_id"], prediction["location_id"]),
            )
            actual = dict(cur.fetchone())
            actual["source_ids"] = []
            table, unit = "revenue_event+expense_event", "usd"
        else:
            cur.close()
            raise ValueError(f"No governed outcome resolver for metric {metric}")
        if not actual.get("actual_at"):
            cur.close()
            raise ValueError("No governed actual records exist for the prediction period")
        synthetic_source_id = prediction["id"]
        cur.execute(
            """
            INSERT INTO prediction_outcome (
                prediction_id,actual_source_table,actual_source_id,actual_timestamp,
                actual_value,unit,source_status,evidence,status
            ) VALUES (%s,%s,%s,%s,%s,%s,'verified_sources',%s,'draft')
            RETURNING *
            """,
            (prediction_id, f"aggregate:{table}", synthetic_source_id, actual["actual_at"],
             actual["actual_value"], unit,
             psycopg2.extras.Json({"source_ids": actual.get("source_ids") or [], "aggregation": "sum"})),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result

    def verify_outcome(self, outcome_id: str, verified_by: str) -> dict[str, Any]:
        uuid.UUID(verified_by)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """UPDATE prediction_outcome SET status='verified',verified_by=%s,verified_at=NOW()
               WHERE id=%s AND status IN ('draft','submitted') RETURNING *""",
            (verified_by, outcome_id),
        )
        row = cur.fetchone()
        if not row:
            self.conn.rollback()
            cur.close()
            raise ValueError("Outcome is not available for verification")
        self.conn.commit()
        cur.close()
        return dict(row)

    def evaluate(self, prediction_id: str) -> dict[str, Any]:
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT pl.*, po.id AS outcome_id, po.actual_value, po.unit AS actual_unit
            FROM prediction_ledger pl
            JOIN prediction_outcome po ON po.prediction_id = pl.id
             AND po.status IN ('verified','published')
            WHERE pl.id = %s ORDER BY po.verified_at DESC LIMIT 1
            """,
            (prediction_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError("Prediction has no verified outcome")
        if row["unit"] != row["actual_unit"]:
            cur.close()
            raise ValueError("Prediction and outcome units do not match")
        predicted, actual = float(row["predicted_value"]), float(row["actual_value"])
        signed = predicted - actual
        ape = abs(signed / actual) * 100 if actual != 0 else None
        within = None
        if row["interval_low"] is not None and row["interval_high"] is not None:
            within = float(row["interval_low"]) <= actual <= float(row["interval_high"])
        brier = (float(row["probability"]) - actual) ** 2 if row["probability"] is not None and actual in (0, 1) else None
        cur.execute(
            """
            INSERT INTO prediction_evaluation (
                prediction_id, outcome_id, signed_error, absolute_error, squared_error,
                absolute_percentage_error, within_interval, brier_score, evaluation_version
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (prediction_id, outcome_id, evaluation_version) DO UPDATE SET
                signed_error=EXCLUDED.signed_error, absolute_error=EXCLUDED.absolute_error,
                squared_error=EXCLUDED.squared_error,
                absolute_percentage_error=EXCLUDED.absolute_percentage_error,
                within_interval=EXCLUDED.within_interval, brier_score=EXCLUDED.brier_score,
                evaluated_at=NOW()
            RETURNING *
            """,
            (prediction_id, row["outcome_id"], signed, abs(signed), signed ** 2, ape, within, brier, CALCULATION_VERSION),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result

    def assess_calibration(self, model_name: str, model_version: str, metric_key: str) -> dict[str, Any]:
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT pl.domain, pl.location_id, pl.crop_id, pl.horizon_seconds,
                   pe.signed_error, pe.absolute_error, pe.squared_error,
                   pe.absolute_percentage_error, pe.within_interval, pe.brier_score,
                   po.actual_value
            FROM prediction_evaluation pe
            JOIN prediction_ledger pl ON pl.id = pe.prediction_id
            JOIN prediction_outcome po ON po.id = pe.outcome_id
            WHERE pl.model_name=%s AND pl.model_version=%s AND pl.metric_key=%s
              AND po.status IN ('verified','published')
            """,
            (model_name, model_version, metric_key),
        )
        rows = [dict(row) for row in cur.fetchall()]
        domain = rows[0]["domain"] if rows else _domain_for_metric(metric_key)
        cur.execute(
            """
            SELECT * FROM prediction_calibration_policy
            WHERE active=TRUE AND domain=%s
              AND (metric_key IS NULL OR metric_key=%s)
              AND (model_name IS NULL OR model_name=%s)
              AND (model_version IS NULL OR model_version=%s)
            ORDER BY (metric_key IS NOT NULL)::int + (model_name IS NOT NULL)::int + (model_version IS NOT NULL)::int DESC
            LIMIT 1
            """,
            (domain, metric_key, model_name, model_version),
        )
        policy = dict(cur.fetchone() or {"minimum_sample_size": 20})
        n = len(rows)
        mae = sum(float(r["absolute_error"]) for r in rows) / n if n else None
        rmse = math.sqrt(sum(float(r["squared_error"]) for r in rows) / n) if n else None
        signed_bias = sum(float(r["signed_error"]) for r in rows) / n if n else None
        actual_mean = sum(abs(float(r["actual_value"])) for r in rows) / n if n else 0
        bias_pct = abs(signed_bias / actual_mean) * 100 if n and actual_mean else None
        apes = [float(r["absolute_percentage_error"]) for r in rows if r["absolute_percentage_error"] is not None]
        mape = sum(apes) / len(apes) if apes else None
        intervals = [r["within_interval"] for r in rows if r["within_interval"] is not None]
        coverage = sum(bool(v) for v in intervals) / len(intervals) if intervals else None
        briers = [float(r["brier_score"]) for r in rows if r["brier_score"] is not None]
        mean_brier = sum(briers) / len(briers) if briers else None
        failures = []
        if n < int(policy.get("minimum_sample_size", 20)):
            gate = "insufficient_data"
        else:
            checks = (("mape", mape, policy.get("maximum_mape")),
                      ("absolute_bias_pct", bias_pct, policy.get("maximum_abs_bias_pct")),
                      ("brier_score", mean_brier, policy.get("maximum_brier_score")))
            for name, value, maximum in checks:
                if maximum is not None and value is not None and value > float(maximum):
                    failures.append(name)
            minimum_coverage = policy.get("minimum_interval_coverage")
            if minimum_coverage is not None and coverage is not None and coverage < float(minimum_coverage):
                failures.append("interval_coverage")
            gate = "fail" if failures else "pass"
        bucket = _horizon_bucket(int(rows[0]["horizon_seconds"])) if rows else "unknown"
        cur.execute(
            """
            INSERT INTO prediction_calibration_assessment (
                domain,metric_key,model_name,model_version,location_id,crop_id,horizon_bucket,
                policy_id,sample_size,mae,rmse,mape,signed_bias,bias_pct,interval_coverage,
                mean_brier_score,gate_result,failure_reasons,evaluation_cutoff,calculation_version
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s)
            RETURNING *
            """,
            (domain, metric_key, model_name, model_version,
             rows[0]["location_id"] if rows else None, rows[0]["crop_id"] if rows else None,
             bucket, policy.get("id"), n, mae, rmse, mape, signed_bias, bias_pct,
             coverage, mean_brier, gate, psycopg2.extras.Json(failures), CALCULATION_VERSION),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result

    def compare_outside_view(self, prediction_id: str, reference_class_id: str,
                             selection_rationale: str, deviation_rationale: Optional[str] = None,
                             disconfirming_evidence: Optional[str] = None) -> dict[str, Any]:
        if not selection_rationale.strip():
            raise ValueError("Reference-class selection rationale is required")
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT pl.predicted_value, pl.metric_key, pl.unit,
                   rc.median, rc.p10, rc.metric_key AS reference_metric, rc.unit AS reference_unit
            FROM prediction_ledger pl CROSS JOIN reference_class rc
            WHERE pl.id=%s AND rc.id=%s AND rc.status IN ('verified','published')
            """,
            (prediction_id, reference_class_id),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError("Prediction or governed reference class not found")
        if row["metric_key"] != row["reference_metric"] or row["unit"] != row["reference_unit"]:
            cur.close()
            raise ValueError("Reference class metric and unit must match the prediction")
        inside, median = float(row["predicted_value"]), float(row["median"])
        deviation = ((inside - median) / abs(median) * 100) if median else None
        if deviation is not None and abs(deviation) > 10 and not (deviation_rationale or "").strip():
            cur.close()
            raise ValueError("Material inside/outside-view deviations require rationale")
        cur.execute(
            """
            INSERT INTO outside_view_comparison (
                prediction_id,reference_class_id,inside_estimate,reference_median,
                reference_adverse,deviation_pct,selection_rationale,deviation_rationale,
                disconfirming_evidence,fit_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'good')
            ON CONFLICT (prediction_id,reference_class_id) DO UPDATE SET
                selection_rationale=EXCLUDED.selection_rationale,
                deviation_rationale=EXCLUDED.deviation_rationale,
                disconfirming_evidence=EXCLUDED.disconfirming_evidence,
                deviation_pct=EXCLUDED.deviation_pct
            RETURNING *
            """,
            (prediction_id, reference_class_id, inside, median, row["p10"], deviation,
             selection_rationale, deviation_rationale, disconfirming_evidence),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result
