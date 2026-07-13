"""Resolvable threat probability forecasts and Brier calibration."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2.extras


SCORING_VERSION = "v1"


def brier_score(probability: float, outcome: float) -> float:
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("probability must be finite and between 0 and 1")
    if outcome not in (0, 1):
        raise ValueError("binary outcome must be 0 or 1")
    return round((probability - outcome) ** 2, 10)


class ProbabilityResolver:
    def __init__(self, conn):
        self.conn = conn

    def create_question(self, location_id: str, domain_key: str, question_text: str,
                        event_definition: str, resolution_criteria: str,
                        resolution_source: str, opens_at: datetime, closes_at: datetime,
                        resolves_by: datetime, created_by: str,
                        threat_id: Optional[str] = None,
                        narrative_id: Optional[str] = None) -> dict[str, Any]:
        uuid.UUID(created_by)
        if not threat_id and not narrative_id:
            raise ValueError("A threat or narrative is required")
        if not opens_at < closes_at <= resolves_by:
            raise ValueError("Question dates must satisfy opens < closes <= resolves")
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO threat_forecast_question (
                location_id,threat_id,narrative_id,domain_key,question_text,event_definition,
                resolution_criteria,resolution_source,opens_at,closes_at,resolves_by,created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """,
            (location_id, threat_id, narrative_id, domain_key, question_text,
             event_definition, resolution_criteria, resolution_source, opens_at,
             closes_at, resolves_by, created_by),
        )
        row = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return row

    def issue_forecast(self, question_id: str, probability: float, source_type: str,
                       methodology_version: str, source_id: Optional[str] = None) -> dict[str, Any]:
        brier_score(probability, 0)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM threat_forecast_question WHERE id=%s", (question_id,))
        question = cur.fetchone()
        now = datetime.now(timezone.utc)
        if not question or question["status"] != "open" or not question["opens_at"] <= now <= question["closes_at"]:
            cur.close()
            raise ValueError("Forecast question is not open")
        cur.execute(
            """INSERT INTO threat_probability_forecast
               (forecast_question_id,source_type,source_id,probability,methodology_version)
               VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (question_id, source_type, source_id, probability, methodology_version),
        )
        row = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return row

    def set_question_status(self, question_id: str, status: str) -> dict[str, Any]:
        if status not in {"open", "closed"}:
            raise ValueError("Question status must be open or closed")
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "UPDATE threat_forecast_question SET status=%s WHERE id=%s AND status IN ('draft','open') RETURNING *",
            (status, question_id),
        )
        row = cur.fetchone()
        if not row:
            self.conn.rollback()
            cur.close()
            raise ValueError("Invalid question transition")
        self.conn.commit()
        cur.close()
        return dict(row)

    def resolve(self, question_id: str, outcome: Optional[float], status: str,
                evidence_refs: list[dict], notes: str, resolved_by: str) -> dict[str, Any]:
        uuid.UUID(resolved_by)
        if status == "resolved" and outcome not in (0, 1):
            raise ValueError("Resolved binary questions require outcome 0 or 1")
        if status in {"cancelled", "invalid"}:
            outcome = None
        if status not in {"resolved", "cancelled", "invalid"} or not notes.strip():
            raise ValueError("Valid resolution status and notes are required")
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT closes_at FROM threat_forecast_question WHERE id=%s", (question_id,))
        question = cur.fetchone()
        if not question or datetime.now(timezone.utc) < question["closes_at"]:
            cur.close()
            raise ValueError("Question cannot be resolved before forecast close")
        cur.execute(
            """INSERT INTO threat_forecast_resolution
               (forecast_question_id,outcome,resolution_status,evidence_refs,resolution_notes,resolved_by)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
            (question_id, outcome, status, psycopg2.extras.Json(evidence_refs), notes, resolved_by),
        )
        resolution = dict(cur.fetchone())
        cur.execute("UPDATE threat_forecast_question SET status=%s WHERE id=%s", (status, question_id))
        if status == "resolved":
            cur.execute("SELECT id, probability FROM threat_probability_forecast WHERE forecast_question_id=%s", (question_id,))
            for forecast in cur.fetchall():
                cur.execute(
                    """INSERT INTO threat_forecast_score
                       (forecast_id,resolution_id,brier_score,scoring_version)
                       VALUES (%s,%s,%s,%s) ON CONFLICT (forecast_id) DO NOTHING""",
                    (forecast["id"], resolution["id"], brier_score(float(forecast["probability"]), float(outcome)), SCORING_VERSION),
                )
        self.conn.commit()
        cur.close()
        return resolution

    def calibrate_expert(self, panel_member_id: str, domain_key: str) -> dict[str, Any]:
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT tfs.brier_score, tfr.outcome
            FROM threat_forecast_score tfs
            JOIN threat_probability_forecast tpf ON tpf.id=tfs.forecast_id
            JOIN threat_forecast_question tfq ON tfq.id=tpf.forecast_question_id
            JOIN threat_forecast_resolution tfr ON tfr.id=tfs.resolution_id
            WHERE tpf.source_type='delphi_member' AND tpf.source_id=%s AND tfq.domain_key=%s
            """,
            (panel_member_id, domain_key),
        )
        rows = [dict(row) for row in cur.fetchall()]
        n = len(rows)
        mean_brier = sum(float(r["brier_score"]) for r in rows) / n if n else None
        base_rate = sum(float(r["outcome"]) for r in rows) / n if n else 0.5
        baseline = sum((base_rate - float(r["outcome"])) ** 2 for r in rows) / n if n else None
        skill = 1 - mean_brier / baseline if n and baseline else 0.0
        reliability = n / (n + 20)
        weight = 1.0 if n < 20 else max(0.5, min(1.5, 1 + reliability * max(-0.5, min(0.5, skill))))
        cur.execute(
            """INSERT INTO delphi_expert_calibration
               (panel_member_id,domain_key,resolved_forecast_count,mean_brier_score,
                baseline_brier_score,brier_skill_score,calibrated_weight,calibration_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (panel_member_id,domain_key,calibration_version) DO UPDATE SET
                 resolved_forecast_count=EXCLUDED.resolved_forecast_count,
                 mean_brier_score=EXCLUDED.mean_brier_score,
                 baseline_brier_score=EXCLUDED.baseline_brier_score,
                 brier_skill_score=EXCLUDED.brier_skill_score,
                 calibrated_weight=EXCLUDED.calibrated_weight,computed_at=NOW()
               RETURNING *""",
            (panel_member_id, domain_key, n, mean_brier, baseline, skill, weight, SCORING_VERSION),
        )
        result = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return result
