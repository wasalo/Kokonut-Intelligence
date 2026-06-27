"""JSON export helpers for EBF scorecards."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extras

from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def export_public_scorecard(conn, scorecard_id: str) -> dict[str, Any]:
    """Export one public-safe EBF scorecard from public views."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_ebf_scorecard_summary
        WHERE scorecard_id = %s
        """,
        (scorecard_id,),
    )
    summary = cur.fetchone()
    if not summary:
        cur.close()
        raise ValueError(f"Public EBF scorecard not found or not publication-ready: {scorecard_id}")

    cur.execute(
        """
        SELECT pillar_key, pillar_name, normalized_score, confidence_level,
               trend_direction, score_evidence_maturity_level,
               score_evidence_maturity_label, evidence_summary, uncertainty_notes
        FROM v_public_ebf_scorecard
        WHERE scorecard_id = %s
        ORDER BY pillar_key
        """,
        (scorecard_id,),
    )
    pillars = [_serialize(dict(row)) for row in cur.fetchall()]
    cur.close()

    exported = _serialize(dict(summary))
    return {
        "export_type": "ebf_scorecard_public",
        "scorecard": exported,
        "pillars": pillars,
        "limitations": [
            "Public EBF scorecards include only published scorecards with evidence maturity Level 4 or higher.",
            "Public carbon pillar scores require evidence maturity Level 6.",
            "Compare pillar context and evidence maturity; do not rank farms as interchangeable units.",
        ],
        "cids_mapping": "EBF score outputs should be represented as cids:IndicatorReport through governed metric_value rows.",
    }


def export_internal_scorecard(conn, scorecard_id: str) -> dict[str, Any]:
    """Export one internal EBF scorecard including calibration and evidence links."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM ebf_scorecard WHERE id = %s", (scorecard_id,))
    scorecard = cur.fetchone()
    if not scorecard:
        cur.close()
        raise ValueError(f"EBF scorecard not found: {scorecard_id}")

    cur.execute(
        """
        SELECT es.*, ep.pillar_name
        FROM ebf_score es
        JOIN ebf_pillar ep ON ep.id = es.pillar_id
        WHERE es.scorecard_id = %s
        ORDER BY ep.sort_order
        """,
        (scorecard_id,),
    )
    scores = [dict(row) for row in cur.fetchall()]
    score_ids = [row["id"] for row in scores]

    evidence: list[dict[str, Any]] = []
    if score_ids:
        cur.execute(
            """
            SELECT *
            FROM ebf_score_evidence
            WHERE score_id = ANY(%s::uuid[])
            ORDER BY created_at, id
            """,
            (score_ids,),
        )
        evidence = [dict(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT *
        FROM ebf_calibration_decision
        WHERE scorecard_id = %s
        ORDER BY decided_at, id
        """,
        (scorecard_id,),
    )
    decisions = [dict(row) for row in cur.fetchall()]
    cur.close()

    return {
        "export_type": "ebf_scorecard_internal",
        "scorecard": _serialize(dict(scorecard)),
        "scores": [_serialize(row) for row in scores],
        "evidence": [_serialize(row) for row in evidence],
        "calibration_decisions": [_serialize(row) for row in decisions],
    }


def dumps_export(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, default=str)
