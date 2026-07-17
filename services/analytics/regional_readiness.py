"""Regional Readiness service — full analytical assessment with scoring, benchmarking, and comparison."""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db
from services.common.logging import get_logger

logger = get_logger(__name__)

DIMENSIONS = {
    "infrastructure": {"name": "Infrastructure", "default_weight": 0.20},
    "institutions": {"name": "Institutions", "default_weight": 0.20},
    "market_access": {"name": "Market Access", "default_weight": 0.20},
    "natural_capital": {"name": "Natural Capital", "default_weight": 0.20},
    "policy_environment": {"name": "Policy Environment", "default_weight": 0.10},
    "human_capital": {"name": "Human Capital", "default_weight": 0.10},
}

RATING_BANDS = {
    "A+": (85, 101),
    "A": (70, 85),
    "B": (55, 70),
    "C": (40, 55),
    "D": (0, 40),
}

CONFIDENCE_THRESHOLDS = {
    6: "high", 5: "high", 4: "moderate", 3: "moderate",
    2: "low", 1: "insufficient_evidence",
}


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def weighted_average(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    total_weight = 0.0
    weighted_sum = 0.0
    for key, score in scores.items():
        w = weights.get(key, 0.0)
        if w > 0 and score is not None:
            weighted_sum += score * w
            total_weight += w
    if total_weight == 0:
        return 0.0
    return clamp_score(weighted_sum / total_weight)


def assign_rating(composite_score: float) -> str:
    for rating, (low, high) in RATING_BANDS.items():
        if low <= composite_score < high:
            return rating
    return "D"


def _query_location_weights(conn, location_id: str) -> Dict[str, float]:
    weights = {k: v["default_weight"] for k, v in DIMENSIONS.items()}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT rd.dimension_key, rlw.weight
                   FROM readiness_location_weight rlw
                   JOIN readiness_dimension rd ON rd.id = rlw.dimension_id
                   WHERE rlw.location_id = %s AND rlw.status = 'active'""",
                (location_id,),
            )
            for r in cur.fetchall():
                weights[r["dimension_key"]] = float(r["weight"])
    except psycopg2.Error:
        conn.rollback()

    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    return weights


def gather_evidence(conn, location_id: str) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}

    evidence["location"] = _query_location(conn, location_id)
    evidence["infrastructure"] = _query_infrastructure(conn, location_id)
    evidence["institutions"] = _query_institutions(conn, location_id)
    evidence["market_access"] = _query_market_access(conn, location_id)
    evidence["natural_capital"] = _query_natural_capital(conn, location_id)
    evidence["policy_environment"] = _query_policy(conn, location_id)
    evidence["human_capital"] = _query_human_capital(conn, location_id)
    return evidence


def _query_location(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, latitude, longitude, country FROM location WHERE id = %s",
                (location_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}
    except psycopg2.Error:
        conn.rollback()
        return {}


def _query_infrastructure(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"assets": 0, "sensors": 0, "active_devices": 0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM equipment_asset WHERE location_id = %s",
                (location_id,),
            )
            result["assets"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM sensor_registry WHERE location_id = %s",
                (location_id,),
            )
            result["sensors"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(DISTINCT id) AS cnt FROM device_health
                   WHERE location_id = %s AND status = 'healthy'""",
                (location_id,),
            )
            result["active_devices"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    return result


def _query_institutions(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"cooperatives": 0, "partners": 0, "partner_engagement": 0.0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM cooperative WHERE location_id = %s",
                (location_id,),
            )
            result["cooperatives"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(DISTINCT p.id) AS cnt,
                          AVG(CASE WHEN pl.stage = 'active' THEN 1.0 ELSE 0.5 END) AS engagement
                   FROM partner p
                   LEFT JOIN partner_lifecycle pl ON pl.partner_id = p.id
                   WHERE p.location_id = %s""",
                (location_id,),
            )
            row = cur.fetchone() or {}
            result["partners"] = row.get("cnt", 0) or 0
            result["partner_engagement"] = float(row.get("engagement", 0) or 0)
    except psycopg2.Error:
        conn.rollback()
    return result


def _query_market_access(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"listings": 0, "demand_signals": 0, "commodities": 0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM market_listing WHERE location_id = %s AND status = 'active'",
                (location_id,),
            )
            result["listings"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM buyer_demand_signal WHERE location_id = %s",
                (location_id,),
            )
            result["demand_signals"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(DISTINCT commodity) AS cnt
                   FROM market_price_observation WHERE location_id = %s""",
                (location_id,),
            )
            result["commodities"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    return result


def _query_natural_capital(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"trees": 0, "soil_carbon": 0.0, "recent_rainfall": 0.0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM tree_inventory WHERE location_id = %s",
                (location_id,),
            )
            result["trees"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT AVG(soil_organic_carbon_pct) AS avg_soc
                   FROM soil_carbon_measurement WHERE location_id = %s""",
                (location_id,),
            )
            result["soil_carbon"] = float((cur.fetchone() or {}).get("avg_soc", 0) or 0)
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT SUM(rainfall_mm) AS total
                   FROM weather_observation
                   WHERE location_id = %s
                     AND observation_date >= CURRENT_DATE - INTERVAL '90 days'""",
                (location_id,),
            )
            result["recent_rainfall"] = float((cur.fetchone() or {}).get("total", 0) or 0)
    except psycopg2.Error:
        conn.rollback()
    return result


def _query_policy(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"policy_threats": 0, "certifications": 0, "active_certs": 0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(*) AS cnt FROM threat
                   WHERE location_id = %s AND type = 'policy' AND status IN ('active', 'monitored')""",
                (location_id,),
            )
            result["policy_threats"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT COUNT(*) AS total,
                          COUNT(CASE WHEN status = 'active' THEN 1 END) AS active
                   FROM organic_certification_record WHERE location_id = %s""",
                (location_id,),
            )
            row = cur.fetchone() or {}
            result["certifications"] = row.get("total", 0) or 0
            result["active_certs"] = row.get("active", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    return result


def _query_human_capital(conn, location_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"training_events": 0, "workers": 0, "feedback_count": 0}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM training_event WHERE location_id = %s",
                (location_id,),
            )
            result["training_events"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM farm_worker WHERE location_id = %s",
                (location_id,),
            )
            result["workers"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT id) AS cnt FROM stakeholder_feedback WHERE location_id = %s",
                (location_id,),
            )
            result["feedback_count"] = (cur.fetchone() or {}).get("cnt", 0) or 0
    except psycopg2.Error:
        conn.rollback()
    return result


def _score_infrastructure(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("infrastructure", {})
    assets = data.get("assets", 0)
    sensors = data.get("sensors", 0)
    devices = data.get("active_devices", 0)
    factors = {"asset_count": assets, "sensor_count": sensors, "active_device_count": devices}

    score = min(100.0, (assets * 10) + (sensors * 8) + (devices * 5))
    maturity = 1
    if assets > 0: maturity = 2
    if sensors > 0: maturity = 3
    if devices > 0: maturity = 4
    return clamp_score(score), maturity, factors


def _score_institutions(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("institutions", {})
    coops = data.get("cooperatives", 0)
    partners = data.get("partners", 0)
    engagement = data.get("partner_engagement", 0)
    factors = {"cooperative_count": coops, "partner_count": partners, "partner_engagement": engagement}

    score = min(100.0, (coops * 20) + (partners * 10) + (engagement * 30))
    maturity = 1
    if coops > 0: maturity = 2
    if partners > 0: maturity = 3
    if engagement > 0.7: maturity = 4
    return clamp_score(score), maturity, factors


def _score_market_access(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("market_access", {})
    listings = data.get("listings", 0)
    signals = data.get("demand_signals", 0)
    commodities = data.get("commodities", 0)
    factors = {"listing_count": listings, "demand_signal_count": signals, "commodity_count": commodities}

    score = min(100.0, (listings * 15) + (signals * 5) + (commodities * 10))
    maturity = 1
    if listings > 0: maturity = 2
    if signals > 0: maturity = 3
    if commodities > 2: maturity = 4
    return clamp_score(score), maturity, factors


def _score_natural_capital(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("natural_capital", {})
    trees = data.get("trees", 0)
    soc = data.get("soil_carbon", 0)
    rainfall = data.get("recent_rainfall", 0)
    factors = {"tree_count": trees, "soil_organic_carbon_pct": soc, "recent_rainfall_mm": rainfall}

    tree_score = min(40.0, trees * 2)
    soc_score = min(30.0, soc * 5) if soc > 0 else 0
    rain_score = min(30.0, rainfall / 10) if rainfall > 0 else 0
    score = tree_score + soc_score + rain_score
    maturity = 1
    if trees > 0: maturity = 2
    if soc > 0: maturity = 3
    if rainfall > 0: maturity = 4
    return clamp_score(score), maturity, factors


def _score_policy_environment(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("policy_environment", {})
    threats = data.get("policy_threats", 0)
    certs = data.get("certifications", 0)
    active = data.get("active_certs", 0)
    factors = {"policy_threat_count": threats, "certification_count": certs, "active_cert_count": active}

    threat_penalty = min(40.0, threats * 15)
    cert_bonus = min(60.0, active * 30 + (certs - active) * 10)
    score = max(0.0, 50 + cert_bonus - threat_penalty)
    maturity = 1
    if certs > 0: maturity = 2
    if active > 0: maturity = 3
    if threats == 0 and active > 0: maturity = 4
    return clamp_score(score), maturity, factors


def _score_human_capital(evidence: Dict[str, Any]) -> tuple[float, int, Dict]:
    data = evidence.get("human_capital", {})
    events = data.get("training_events", 0)
    workers = data.get("workers", 0)
    feedback = data.get("feedback_count", 0)
    factors = {"training_event_count": events, "worker_count": workers, "feedback_count": feedback}

    training_score = min(50.0, events * 10)
    worker_score = min(30.0, workers * 5)
    feedback_score = min(20.0, feedback * 2)
    score = training_score + worker_score + feedback_score
    maturity = 1
    if workers > 0: maturity = 2
    if events > 0: maturity = 3
    if feedback > 0: maturity = 4
    return clamp_score(score), maturity, factors


SCORERS = {
    "infrastructure": _score_infrastructure,
    "institutions": _score_institutions,
    "market_access": _score_market_access,
    "natural_capital": _score_natural_capital,
    "policy_environment": _score_policy_environment,
    "human_capital": _score_human_capital,
}


def create_assessment(
    conn,
    location_id: str,
    title: str,
    period_start: str,
    period_end: str,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO regional_assessment
               (location_id, title, period_start, period_end, created_by)
               VALUES (%s, %s, %s, %s, %s)
                RETURNING id, location_id, title, period_start::text, period_end::text,
                      methodology_version, status, created_at""",
            (location_id, title, period_start, period_end, created_by),
        )
        row = dict(cur.fetchone())
        conn.commit()
        logger.info("Created regional assessment %s for %s", row["id"], location_id)
        return row


def compute_composite(conn, assessment_id: str) -> Dict[str, Any]:
    assessment = _get_assessment_raw(conn, assessment_id)
    if not assessment:
        raise ValueError(f"Assessment {assessment_id} not found")
    location_id = str(assessment["location_id"])

    weights = _query_location_weights(conn, location_id)
    evidence = gather_evidence(conn, location_id)

    dimension_scores = {}
    for dim_key, scorer in SCORERS.items():
        raw_score, maturity, factors = scorer(evidence)
        dim_weights = weights
        normalized = clamp_score(raw_score)
        dimension_scores[dim_key] = {
            "raw_score": raw_score,
            "normalized_score": normalized,
            "weight": dim_weights.get(dim_key, 0),
            "evidence_maturity_level": maturity,
            "factors": factors,
        }

    composite = weighted_average(
        {k: v["normalized_score"] for k, v in dimension_scores.items()},
        weights,
    )
    rating = assign_rating(composite)

    min_maturity = min(v["evidence_maturity_level"] for v in dimension_scores.values())
    confidence = CONFIDENCE_THRESHOLDS.get(min_maturity, "insufficient_evidence")

    with conn.cursor() as cur:
        cur.execute(
            """UPDATE regional_assessment
               SET composite_score = %s, rating = %s, confidence_level = %s,
                   infrastructure_score = %s, institutions_score = %s,
                   market_access_score = %s, natural_capital_score = %s,
                   policy_environment_score = %s, human_capital_score = %s
               WHERE id = %s""",
            (
                composite, rating, confidence,
                dimension_scores["infrastructure"]["normalized_score"],
                dimension_scores["institutions"]["normalized_score"],
                dimension_scores["market_access"]["normalized_score"],
                dimension_scores["natural_capital"]["normalized_score"],
                dimension_scores["policy_environment"]["normalized_score"],
                dimension_scores["human_capital"]["normalized_score"],
                assessment_id,
            ),
        )
        for dim_key, ds in dimension_scores.items():
            dim_config = DIMENSIONS[dim_key]
            cur.execute(
                """INSERT INTO regional_dimension_score
                   (assessment_id, location_id, dimension_key, dimension_name, weight,
                    raw_score, normalized_score, evidence_maturity_level, factors)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (assessment_id, dimension_key) DO UPDATE SET
                     raw_score = EXCLUDED.raw_score,
                     normalized_score = EXCLUDED.normalized_score,
                     evidence_maturity_level = EXCLUDED.evidence_maturity_level,
                     factors = EXCLUDED.factors""",
                (
                    assessment_id, location_id, dim_key, dim_config["name"],
                    ds["weight"], ds["raw_score"], ds["normalized_score"],
                    ds["evidence_maturity_level"], json.dumps(ds["factors"]),
                ),
            )
        conn.commit()

    logger.info("Computed composite %s for assessment %s: %s (%s)", composite, assessment_id, rating, confidence)
    return {
        "assessment_id": assessment_id,
        "composite_score": composite,
        "rating": rating,
        "confidence_level": confidence,
        "dimensions": dimension_scores,
    }


def _get_assessment_raw(conn, assessment_id: str) -> Optional[Dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM regional_assessment WHERE id = %s", (assessment_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_assessments(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                """SELECT ra.*, l.name AS location_name
                   FROM regional_assessment ra
                   LEFT JOIN location l ON l.id = ra.location_id
                   WHERE ra.location_id = %s
                   ORDER BY ra.created_at DESC""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT ra.*, l.name AS location_name
                   FROM regional_assessment ra
                   LEFT JOIN location l ON l.id = ra.location_id
                   ORDER BY ra.created_at DESC"""
            )
        return [dict(r) for r in cur.fetchall()]


def get_assessment(conn, assessment_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT ra.*, l.name AS location_name
               FROM regional_assessment ra
               LEFT JOIN location l ON l.id = ra.location_id
               WHERE ra.id = %s""",
            (assessment_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)

        cur.execute(
            """SELECT * FROM regional_dimension_score
               WHERE assessment_id = %s
               ORDER BY dimension_key""",
            (assessment_id,),
        )
        result["dimensions"] = [dict(r) for r in cur.fetchall()]
        return result


def compare_locations(conn, location_ids: List[str]) -> Dict[str, Any]:
    comparisons = []
    for lid in location_ids:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT ra.*, l.name AS location_name
                   FROM regional_assessment ra
                   LEFT JOIN location l ON l.id = ra.location_id
                   WHERE ra.location_id = %s AND ra.status IN ('verified', 'published')
                   ORDER BY ra.created_at DESC LIMIT 1""",
                (lid,),
            )
            row = cur.fetchone()
            if row:
                comparisons.append(dict(row))

    if not comparisons:
        return {"comparisons": [], "ranking": []}

    ranking = sorted(comparisons, key=lambda x: float(x.get("composite_score") or 0), reverse=True)
    return {"comparisons": comparisons, "ranking": [r["location_id"] for r in ranking]}


def create_benchmark(
    conn,
    dimension_key: str,
    benchmark_name: str,
    benchmark_score: float,
    benchmark_type: str = "regional_average",
    source: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO regional_benchmark
               (dimension_key, benchmark_name, benchmark_score, benchmark_type, source, location_id)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id, dimension_key, benchmark_name, benchmark_score, benchmark_type, created_at""",
            (dimension_key, benchmark_name, benchmark_score, benchmark_type, source, location_id),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def compare_to_benchmark(conn, assessment_id: str, benchmark_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM regional_benchmark WHERE id = %s", (benchmark_id,))
        bench = cur.fetchone()
        if not bench:
            raise ValueError(f"Benchmark {benchmark_id} not found")
        bench = dict(bench)

        cur.execute(
            """SELECT * FROM regional_dimension_score
               WHERE assessment_id = %s AND dimension_key = %s""",
            (assessment_id, bench["dimension_key"]),
        )
        ds = cur.fetchone()
        if not ds:
            raise ValueError(f"No dimension score for {bench['dimension_key']}")

        deviation = float(ds["normalized_score"]) - float(bench["benchmark_score"])
        return {
            "dimension_key": bench["dimension_key"],
            "assessment_score": float(ds["normalized_score"]),
            "benchmark_score": float(bench["benchmark_score"]),
            "benchmark_name": bench["benchmark_name"],
            "benchmark_type": bench["benchmark_type"],
            "deviation": round(deviation, 2),
            "relative_position": "above" if deviation >= 0 else "below",
        }


def render_markdown(assessment: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Regional Readiness Assessment: {assessment.get('title', 'Untitled')}\n")
    lines.append(f"**Location:** {assessment.get('location_name', 'N/A')}")
    lines.append(f"**Period:** {assessment.get('period_start', 'N/A')} to {assessment.get('period_end', 'N/A')}")
    lines.append(f"**Rating:** {assessment.get('rating', 'N/A')}")
    lines.append(f"**Composite Score:** {assessment.get('composite_score', 0)}/100")
    lines.append(f"**Confidence:** {assessment.get('confidence_level', 'N/A')}\n")

    dim_labels = {
        "infrastructure": "Infrastructure",
        "institutions": "Institutions",
        "market_access": "Market Access",
        "natural_capital": "Natural Capital",
        "policy_environment": "Policy Environment",
        "human_capital": "Human Capital",
    }
    for dim_key, dim_name in dim_labels.items():
        score = assessment.get(f"{dim_key}_score", 0)
        lines.append(f"## {dim_name} — {score}/100\n")
        dims = [d for d in assessment.get("dimensions", []) if d.get("dimension_key") == dim_key]
        if dims:
            d = dims[0]
            lines.append(f"- Weight: {d.get('weight', 0):.2%}")
            lines.append(f"- Evidence maturity: {d.get('evidence_maturity_level', 1)}/6")
            factors = d.get("factors", {})
            if factors:
                lines.append("- Factors:")
                for k, v in factors.items():
                    lines.append(f"  - {k}: {v}")
        lines.append("")

    return "\n".join(lines)


def render_cli(assessment: Dict[str, Any]) -> str:
    w = 78
    lines = []
    lines.append("=" * w)
    lines.append(f"  REGIONAL READINESS: {assessment.get('title', 'Untitled').upper()}")
    lines.append("=" * w)
    lines.append(f"  Location:  {assessment.get('location_name', 'N/A')}")
    lines.append(f"  Period:    {assessment.get('period_start', 'N/A')} to {assessment.get('period_end', 'N/A')}")
    lines.append(f"  Rating:    {assessment.get('rating', 'N/A')}")
    lines.append(f"  Composite: {assessment.get('composite_score', 0)}/100")
    lines.append(f"  Confidence:{assessment.get('confidence_level', 'N/A')}")
    lines.append("-" * w)

    dim_labels = {
        "infrastructure": "INFRASTRUCTURE", "institutions": "INSTITUTIONS",
        "market_access": "MARKET ACCESS", "natural_capital": "NATURAL CAPITAL",
        "policy_environment": "POLICY ENV", "human_capital": "HUMAN CAPITAL",
    }
    for dim_key, label in dim_labels.items():
        score = assessment.get(f"{dim_key}_score", 0)
        bar_len = int(float(score) / 100 * 30)
        bar = "#" * bar_len + "-" * (30 - bar_len)
        lines.append(f"  {label:<20} [{bar}] {score:>6.1f}")

    lines.append("\n" + "=" * w)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Regional Readiness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="Create assessment")
    p.add_argument("--location-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--period-start", required=True)
    p.add_argument("--period-end", required=True)

    p = sub.add_parser("compute", help="Compute composite score")
    p.add_argument("--assessment-id", required=True)

    p = sub.add_parser("list", help="List assessments")
    p.add_argument("--location-id")

    p = sub.add_parser("get", help="Get assessment")
    p.add_argument("--assessment-id", required=True)

    p = sub.add_parser("compare", help="Compare locations")
    p.add_argument("--location-ids", nargs="+", required=True)

    p = sub.add_parser("create-benchmark", help="Create benchmark")
    p.add_argument("--dimension-key", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--score", type=float, required=True)
    p.add_argument("--type", default="regional_average")
    p.add_argument("--source")

    p = sub.add_parser("benchmark", help="Compare to benchmark")
    p.add_argument("--assessment-id", required=True)
    p.add_argument("--benchmark-id", required=True)

    p = sub.add_parser("dimensions", help="List dimension configs")

    p = sub.add_parser("export", help="Export assessment")
    p.add_argument("--assessment-id", required=True)

    args = parser.parse_args()
    conn = get_db()
    try:
        if args.command == "create":
            result = create_assessment(conn, args.location_id, args.title, args.period_start, args.period_end)
        elif args.command == "compute":
            result = compute_composite(conn, args.assessment_id)
        elif args.command == "list":
            result = list_assessments(conn, args.location_id)
        elif args.command == "get":
            result = get_assessment(conn, args.assessment_id)
        elif args.command == "compare":
            result = compare_locations(conn, args.location_ids)
        elif args.command == "create-benchmark":
            result = create_benchmark(conn, args.dimension_key, args.name, args.score, args.type, args.source)
        elif args.command == "benchmark":
            result = compare_to_benchmark(conn, args.assessment_id, args.benchmark_id)
        elif args.command == "dimensions":
            result = [{"key": k, **v} for k, v in DIMENSIONS.items()]
        elif args.command == "export":
            assessment = get_assessment(conn, args.assessment_id)
            if assessment:
                print(render_markdown(assessment))
                return
            result = {"error": "assessment not found"}
        else:
            result = {"error": "unknown command"}
        print(json.dumps(result, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
