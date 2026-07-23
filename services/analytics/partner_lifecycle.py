"""Partner Lifecycle service.

Manages partner lifecycle stages, evaluations, and scorecards
for formal partnership management beyond the flat partner table.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.database import get_db


# ──────────────────────────────────────────────
# Partner Lifecycle
# ──────────────────────────────────────────────

def create_lifecycle(
    conn, partner_id: str, stage: str = "prospect",
    location_id: Optional[str] = None, partnership_type: Optional[str] = None,
    strategic_importance: str = "medium", stage_notes: Optional[str] = None,
    contract_start_date: Optional[str] = None, contract_end_date: Optional[str] = None,
    next_review_date: Optional[str] = None, assigned_to: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO partner_lifecycle (
                partner_id, location_id, stage, partnership_type,
                strategic_importance, stage_notes, contract_start_date,
                contract_end_date, next_review_date, assigned_to, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, partner_id, stage, strategic_importance
            """,
            (
                partner_id, location_id, stage, partnership_type,
                strategic_importance, stage_notes, contract_start_date,
                contract_end_date, next_review_date, assigned_to, created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def advance_stage(
    conn, lifecycle_id: str, new_stage: str,
    notes: Optional[str] = None, updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE partner_lifecycle
            SET stage = %s, stage_entered_at = NOW(), stage_notes = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, partner_id, stage, stage_entered_at
            """,
            (new_stage, notes, lifecycle_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"lifecycle {lifecycle_id} not found")
        conn.commit()
        return dict(row)


def list_lifecycles(
    conn, location_id: Optional[str] = None, stage: Optional[str] = None,
    partner_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        conditions = ["pl.status = 'active'"]
        params: list = []
        if location_id:
            conditions.append("pl.location_id = %s")
            params.append(location_id)
        if stage:
            conditions.append("pl.stage = %s")
            params.append(stage)
        if partner_id:
            conditions.append("pl.partner_id = %s")
            params.append(partner_id)
        where = " AND ".join(conditions)
        cur.execute(
            f"""
            SELECT pl.id, pl.partner_id, p.name AS partner_name, pl.stage,
                   pl.strategic_importance, pl.partnership_type,
                   pl.stage_entered_at, pl.next_review_date, pl.contract_end_date
            FROM partner_lifecycle pl
            JOIN partner p ON p.id = pl.partner_id
            WHERE {where}
            ORDER BY pl.stage_entered_at DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get_lifecycle(conn, lifecycle_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT pl.*, p.name AS partner_name
            FROM partner_lifecycle pl
            JOIN partner p ON p.id = pl.partner_id
            WHERE pl.id = %s
            """,
            (lifecycle_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        # Attach evaluations
        cur.execute(
            """
            SELECT id, evaluation_type, overall_score, evaluation_date, evaluated_by
            FROM partner_evaluation WHERE lifecycle_id = %s
            ORDER BY evaluation_date DESC
            """,
            (lifecycle_id,),
        )
        result["evaluations"] = [dict(r) for r in cur.fetchall()]
        # Attach scorecards
        cur.execute(
            """
            SELECT id, period_start, period_end, overall_score, graded_by
            FROM partner_scorecard WHERE lifecycle_id = %s
            ORDER BY period_end DESC
            """,
            (lifecycle_id,),
        )
        result["scorecards"] = [dict(r) for r in cur.fetchall()]
        return result


# ──────────────────────────────────────────────
# Partner Evaluation
# ──────────────────────────────────────────────

def create_evaluation(
    conn, lifecycle_id: str, partner_id: str, evaluation_type: str,
    technical_score: float = 0, financial_score: float = 0,
    reliability_score: float = 0, compliance_score: float = 0,
    strengths: Optional[List[str]] = None,
    weaknesses: Optional[List[str]] = None,
    recommendations: Optional[str] = None,
    evaluated_by: Optional[str] = None,
) -> Dict[str, Any]:
    # Auto-compute overall as weighted average
    overall = (technical_score * 0.3 + financial_score * 0.25 +
               reliability_score * 0.25 + compliance_score * 0.2)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO partner_evaluation (
                lifecycle_id, partner_id, evaluation_type,
                technical_score, financial_score, reliability_score,
                compliance_score, overall_score, strengths, weaknesses,
                recommendations, evaluated_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, evaluation_type, overall_score, evaluation_date
            """,
            (
                lifecycle_id, partner_id, evaluation_type,
                technical_score, financial_score, reliability_score,
                compliance_score, round(overall, 2),
                strengths or [], weaknesses or [], recommendations, evaluated_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_evaluations(
    conn, lifecycle_id: str,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, evaluation_type, technical_score, financial_score,
                   reliability_score, compliance_score, overall_score,
                   strengths, weaknesses, evaluation_date
            FROM partner_evaluation WHERE lifecycle_id = %s
            ORDER BY evaluation_date DESC
            """,
            (lifecycle_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# Partner Scorecard
# ──────────────────────────────────────────────

def create_scorecard(
    conn, lifecycle_id: str, partner_id: str,
    period_start: str, period_end: str,
    deliveries_on_time_pct: float = 0, quality_score: float = 0,
    responsiveness_score: float = 0, cost_competitiveness: float = 0,
    innovation_score: float = 0, incidents: int = 0,
    notes: Optional[str] = None, graded_by: Optional[str] = None,
) -> Dict[str, Any]:
    overall = (deliveries_on_time_pct * 0.25 + quality_score * 0.30 +
               responsiveness_score * 0.20 + cost_competitiveness * 0.15 +
               innovation_score * 0.10)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO partner_scorecard (
                lifecycle_id, partner_id, period_start, period_end,
                deliveries_on_time_pct, quality_score, responsiveness_score,
                cost_competitiveness, innovation_score, overall_score,
                incidents, notes, graded_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lifecycle_id, period_start, period_end)
            DO UPDATE SET
                deliveries_on_time_pct = EXCLUDED.deliveries_on_time_pct,
                quality_score = EXCLUDED.quality_score,
                responsiveness_score = EXCLUDED.responsiveness_score,
                cost_competitiveness = EXCLUDED.cost_competitiveness,
                innovation_score = EXCLUDED.innovation_score,
                overall_score = EXCLUDED.overall_score,
                incidents = EXCLUDED.incidents,
                notes = EXCLUDED.notes,
                graded_by = EXCLUDED.graded_by
            RETURNING id, overall_score, period_start, period_end
            """,
            (
                lifecycle_id, partner_id, period_start, period_end,
                deliveries_on_time_pct, quality_score, responsiveness_score,
                cost_competitiveness, innovation_score, round(overall, 2),
                incidents, notes, graded_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_scorecards(
    conn, lifecycle_id: str,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, period_start, period_end, deliveries_on_time_pct,
                   quality_score, responsiveness_score, cost_competitiveness,
                   innovation_score, overall_score, incidents
            FROM partner_scorecard WHERE lifecycle_id = %s
            ORDER BY period_end DESC
            """,
            (lifecycle_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "create":
            out = create_lifecycle(
                conn, args.partner_id, stage=args.stage,
                location_id=args.location_id,
                partnership_type=args.partnership_type,
                strategic_importance=args.importance,
                stage_notes=args.notes,
                created_by=args.created_by,
            )
        elif args.command == "advance":
            out = advance_stage(conn, args.lifecycle_id, args.stage, notes=args.notes)
        elif args.command == "list":
            out = list_lifecycles(
                conn, location_id=args.location_id, stage=args.stage,
                partner_id=args.partner_id,
            )
        elif args.command == "get":
            out = get_lifecycle(conn, args.lifecycle_id)
        elif args.command == "evaluate":
            out = create_evaluation(
                conn, args.lifecycle_id, args.partner_id, args.evaluation_type,
                technical_score=args.technical, financial_score=args.financial,
                reliability_score=args.reliability, compliance_score=args.compliance,
                recommendations=args.recommendations, evaluated_by=args.evaluated_by,
            )
        elif args.command == "list-evaluations":
            out = list_evaluations(conn, args.lifecycle_id)
        elif args.command == "scorecard":
            out = create_scorecard(
                conn, args.lifecycle_id, args.partner_id,
                args.period_start, args.period_end,
                deliveries_on_time_pct=args.on_time, quality_score=args.quality,
                responsiveness_score=args.responsiveness,
                cost_competitiveness=args.cost, innovation_score=args.innovation,
                incidents=args.incidents, notes=args.notes,
                graded_by=args.graded_by,
            )
        elif args.command == "list-scorecards":
            out = list_scorecards(conn, args.lifecycle_id)
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Partner Lifecycle Management")
    p.add_argument("--location-id", default=None)
    p.add_argument("--partner-id", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create")
    c.add_argument("--partner-id", required=True)
    c.add_argument("--stage", default="prospect",
                   choices=["prospect", "negotiation", "pilot", "active",
                            "review", "renewal", "suspended", "exited"])
    c.add_argument("--partnership-type", default=None)
    c.add_argument("--importance", default="medium",
                   choices=["low", "medium", "high", "critical"])
    c.add_argument("--notes", default=None)
    c.add_argument("--created-by", default=None)

    a = sub.add_parser("advance")
    a.add_argument("--lifecycle-id", required=True)
    a.add_argument("--stage", required=True,
                   choices=["prospect", "negotiation", "pilot", "active",
                            "review", "renewal", "suspended", "exited"])
    a.add_argument("--notes", default=None)

    ls = sub.add_parser("list")
    ls.add_argument("--stage", default=None)
    ls.add_argument("--partner-id", default=None)

    g = sub.add_parser("get")
    g.add_argument("--lifecycle-id", required=True)

    e = sub.add_parser("evaluate")
    e.add_argument("--lifecycle-id", required=True)
    e.add_argument("--partner-id", required=True)
    e.add_argument("--evaluation-type", required=True,
                   choices=["initial", "quarterly", "annual", "ad_hoc", "exit"])
    e.add_argument("--technical", type=float, default=0)
    e.add_argument("--financial", type=float, default=0)
    e.add_argument("--reliability", type=float, default=0)
    e.add_argument("--compliance", type=float, default=0)
    e.add_argument("--recommendations", default=None)
    e.add_argument("--evaluated-by", default=None)

    le = sub.add_parser("list-evaluations")
    le.add_argument("--lifecycle-id", required=True)

    sc = sub.add_parser("scorecard")
    sc.add_argument("--lifecycle-id", required=True)
    sc.add_argument("--partner-id", required=True)
    sc.add_argument("--period-start", required=True)
    sc.add_argument("--period-end", required=True)
    sc.add_argument("--on-time", type=float, default=0)
    sc.add_argument("--quality", type=float, default=0)
    sc.add_argument("--responsiveness", type=float, default=0)
    sc.add_argument("--cost", type=float, default=0)
    sc.add_argument("--innovation", type=float, default=0)
    sc.add_argument("--incidents", type=int, default=0)
    sc.add_argument("--notes", default=None)
    sc.add_argument("--graded-by", default=None)

    lsc = sub.add_parser("list-scorecards")
    lsc.add_argument("--lifecycle-id", required=True)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
