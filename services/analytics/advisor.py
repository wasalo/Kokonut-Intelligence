#!/usr/bin/env python3
"""
Advisory / Recommendation Engine

Evaluates rules against current farm data and generates actionable recommendations.
Integrates with weather forecasts, sensor data, crop phenology, and CRISP scores.

Usage:
    python -m services.analytics.advisor --evaluate --location-id UUID
    python -m services.analytics.advisor --list --location-id UUID
    python -m services.analytics.advisor --accept --recommendation-id UUID --user-id admin
    python -m services.analytics.advisor --dismiss --recommendation-id UUID --reason "not needed"
    python -m services.analytics.advisor --run-cycle --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.advisor")


# ============================================================
# Rule Evaluation
# ============================================================

def evaluate_rules(conn, location_id: str) -> list[dict]:
    """Evaluate all active advisory rules for a location.
    
    Returns list of triggered rules with context data.
    """
    cur = conn.cursor()

    # Get active rules
    cur.execute(
        """
        SELECT id, name, rule_type, domain, priority, conditions,
               recommendation_template, severity, cooldown_hours, max_per_day
        FROM advisory_rule
        WHERE status = 'active'
        ORDER BY priority DESC
        """,
    )
    rules = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    triggered = []
    for rule in rules:
        # Check cooldown
        if _is_in_cooldown(conn, rule["id"], location_id, rule.get("cooldown_hours", 24)):
            continue

        # Check daily limit
        if _exceeds_daily_limit(conn, rule["id"], location_id, rule.get("max_per_day", 5)):
            continue

        # Evaluate conditions
        context = _evaluate_conditions(conn, location_id, rule["conditions"], rule["rule_type"])
        if context:
            triggered.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "rule_type": rule["rule_type"],
                "domain": rule["domain"],
                "severity": rule["severity"],
                "priority": rule["priority"],
                "template": rule["recommendation_template"],
                "context": context,
            })

    cur.close()
    return triggered


def _is_in_cooldown(conn, rule_id: str, location_id: str, cooldown_hours: int) -> bool:
    """Check if a rule is in cooldown period for this location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM advisory_recommendation
            WHERE rule_id = %s AND location_id = %s
              AND created_at > NOW() - INTERVAL '%s hours'
        )
        """,
        (rule_id, location_id, cooldown_hours),
    )
    result = cur.fetchone()[0]
    cur.close()
    return result


def _exceeds_daily_limit(conn, rule_id: str, location_id: str, max_per_day: int) -> bool:
    """Check if rule has exceeded daily generation limit."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM advisory_recommendation
        WHERE rule_id = %s AND location_id = %s
          AND created_at >= CURRENT_DATE
        """,
        (rule_id, location_id),
    )
    count = cur.fetchone()[0]
    cur.close()
    return count >= max_per_day


def _evaluate_conditions(conn, location_id: str, conditions: dict, rule_type: str) -> Optional[dict]:
    """Evaluate rule conditions against current data. Returns context if triggered."""
    if not conditions:
        return None

    if rule_type == "threshold":
        return _eval_threshold(conn, location_id, conditions)
    elif rule_type == "composite":
        return _eval_composite(conn, location_id, conditions)
    elif rule_type == "schedule":
        return _eval_schedule(conn, location_id, conditions)
    elif rule_type == "forecast_based":
        return _eval_forecast(conn, location_id, conditions)
    elif rule_type == "anomaly_response":
        return _eval_anomaly(conn, location_id, conditions)
    return None


def _eval_threshold(conn, location_id: str, conditions: dict) -> Optional[dict]:
    """Evaluate a single threshold condition."""
    metric = conditions.get("metric")
    operator = conditions.get("operator", "lt")
    threshold = conditions.get("threshold")
    source = conditions.get("source", "sensor")

    if metric is None or threshold is None:
        return None

    cur = conn.cursor()
    value = None

    if source == "sensor":
        cur.execute(
            """
            SELECT AVG(value) FROM sensor_reading
            WHERE location_id = %s AND sensor_type = %s
              AND reading_date >= CURRENT_DATE - 3
            """,
            (location_id, metric),
        )
        row = cur.fetchone()
        value = float(row[0]) if row and row[0] is not None else None

    elif source == "weather":
        cur.execute(
            """
            SELECT AVG(temperature_c), AVG(precipitation_mm), AVG(humidity_pct)
            FROM weather_observation
            WHERE location_id = %s AND observation_date >= CURRENT_DATE - 1
            """,
            (location_id,),
        )
        row = cur.fetchone()
        if row:
            if metric == "temperature":
                value = float(row[0]) if row[0] else None
            elif metric == "precipitation":
                value = float(row[1]) if row[1] else None
            elif metric == "humidity":
                value = float(row[2]) if row[2] else None

    elif source == "forecast":
        cur.execute(
            """
            SELECT AVG(precipitation_prob_pct), AVG(wind_speed_kmh),
                   MIN(temp_min_c), MAX(temp_max_c)
            FROM weather_forecast
            WHERE location_id = %s
              AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
            """,
            (location_id,),
        )
        row = cur.fetchone()
        if row:
            if metric == "precipitation_prob":
                value = float(row[0]) if row[0] else None
            elif metric == "wind_speed":
                value = float(row[1]) if row[1] else None
            elif metric == "temp_min":
                value = float(row[2]) if row[2] else None
            elif metric == "temp_max":
                value = float(row[3]) if row[3] else None

    cur.close()

    if value is None:
        return None

    triggered = False
    if operator == "lt" and value < threshold:
        triggered = True
    elif operator == "gt" and value > threshold:
        triggered = True
    elif operator == "lte" and value <= threshold:
        triggered = True
    elif operator == "gte" and value >= threshold:
        triggered = True
    elif operator == "eq" and abs(value - threshold) < 0.01:
        triggered = True

    if triggered:
        return {
            "metric": metric,
            "value": round(value, 2),
            "threshold": threshold,
            "operator": operator,
            "source": source,
        }
    return None


def _eval_composite(conn, location_id: str, conditions: dict) -> Optional[dict]:
    """Evaluate composite conditions (all must be true)."""
    results = {}
    all_triggered = True

    for key, cond in conditions.items():
        result = _eval_threshold(conn, location_id, cond)
        if result:
            results[key] = result
        else:
            all_triggered = False

    return results if all_triggered and results else None


def _eval_schedule(conn, location_id: str, conditions: dict) -> Optional[dict]:
    """Evaluate schedule-based conditions."""
    interval_days = conditions.get("interval_days", 7)
    last_check_field = conditions.get("last_check_field", "last_soil_check")

    cur = conn.cursor()
    cur.execute(
        f"SELECT metadata->>%s FROM location WHERE id = %s",
        (last_check_field, location_id),
    )
    row = cur.fetchone()
    cur.close()

    if not row or not row[0]:
        return {"interval_days": interval_days, "last_check": None, "overdue": True}

    try:
        last_check = datetime.fromisoformat(row[0]).date()
        days_since = (datetime.now().date() - last_check).days
        if days_since >= interval_days:
            return {
                "interval_days": interval_days,
                "last_check": row[0],
                "days_since": days_since,
                "overdue": True,
            }
    except (ValueError, TypeError):
        pass

    return None


def _eval_forecast(conn, location_id: str, conditions: dict) -> Optional[dict]:
    """Evaluate forecast-based conditions."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT forecast_date, precipitation_prob_pct, wind_speed_kmh,
               temp_min_c, temp_max_c
        FROM weather_forecast
        WHERE location_id = %s
          AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 5
        ORDER BY forecast_date, forecast_hour
        """,
        (location_id,),
    )
    forecasts = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    cur.close()

    if not forecasts:
        return None

    # Check spray window: low wind + low precip probability
    if conditions.get("type") == "spray_window":
        suitable_days = []
        for f in forecasts:
            wind = float(f.get("wind_speed_kmh") or 0)
            precip_prob = float(f.get("precipitation_prob_pct") or 0)
            if wind < 15 and precip_prob < 30:
                suitable_days.append(f["forecast_date"])
        if suitable_days:
            return {"suitable_days": suitable_days, "type": "spray_window"}

    # Check frost risk
    if conditions.get("type") == "frost_risk":
        min_temp = conditions.get("min_temp", 5)
        frost_days = [f for f in forecasts if f.get("temp_min_c") and float(f["temp_min_c"]) < min_temp]
        if frost_days:
            return {"frost_days": [f["forecast_date"] for f in frost_days], "type": "frost_risk"}

    return None


def _eval_anomaly(conn, location_id: str, conditions: dict) -> Optional[dict]:
    """Evaluate anomaly-based conditions."""
    cur = conn.cursor()
    severity = conditions.get("min_severity", "warning")

    cur.execute(
        """
        SELECT COUNT(*) FROM sensor_alert
        WHERE location_id = %s
          AND created_at >= NOW() - INTERVAL '24 hours'
          AND severity >= %s
        """,
        (location_id, severity),
    )
    count = cur.fetchone()[0]
    cur.close()

    if count > 0:
        return {"alert_count_24h": count, "min_severity": severity}
    return None


# ============================================================
# Recommendation Generation
# ============================================================

def generate_recommendation(conn, rule: dict, context: dict) -> dict:
    """Generate a recommendation from a triggered rule and context."""
    # Fill template with context values
    template = rule["template"]
    try:
        title = template.split("\n")[0][:255] if template else rule["rule_name"]
    except Exception:
        title = rule["rule_name"]

    # Build summary from template + context
    summary = template
    for key, val in context.items():
        if isinstance(val, (str, int, float)):
            summary = summary.replace(f"{{{key}}}", str(val))
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                summary = summary.replace(f"{{{key}.{k2}}}", str(v2))

    # Determine urgency from severity and context
    urgency = "this_week"
    if rule["severity"] == "critical":
        urgency = "within_24h"
    elif rule["severity"] == "warning":
        urgency = "within_48h"
    if context.get("type") == "frost_risk":
        urgency = "immediate"

    # Determine action type
    action_type = rule["domain"]
    action_config = {"rule_id": rule["rule_id"], **context}

    # Create recommendation record
    rec_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO advisory_recommendation
            (id, location_id, rule_id, domain, title, summary, details,
             urgency, severity, action_type, action_config, status)
        VALUES (%s, (SELECT location_id FROM advisory_rule WHERE id = %s LIMIT 1),
                %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, 'pending')
        RETURNING id
        """,
        (
            rec_id, rule["rule_id"], rule["rule_id"], rule["domain"],
            title, summary[:2000], json.dumps(context),
            urgency, rule["severity"], action_type, json.dumps(action_config),
        ),
    )
    result_id = cur.fetchone()[0]

    # Log the action
    cur.execute(
        """
        INSERT INTO advisory_log (recommendation_id, action, new_status, notes)
        VALUES (%s, 'created', 'pending', %s)
        """,
        (result_id, f"Generated from rule: {rule['rule_name']}"),
    )

    conn.commit()
    cur.close()

    return {
        "recommendation_id": result_id,
        "rule_name": rule["rule_name"],
        "domain": rule["domain"],
        "title": title,
        "urgency": urgency,
        "severity": rule["severity"],
        "status": "pending",
    }


# ============================================================
# Recommendation Management
# ============================================================

def list_recommendations(conn, location_id: str, status: str = None,
                          domain: str = None) -> list[dict]:
    """List recommendations for a location."""
    cur = conn.cursor()
    query = """
        SELECT ar.id, ar.domain, ar.title, ar.summary, ar.urgency,
               ar.severity, ar.action_type, ar.estimated_cost_usd,
               ar.status, ar.created_at, ar.expires_at,
               ar2.name AS rule_name
        FROM advisory_recommendation ar
        LEFT JOIN advisory_rule ar2 ON ar2.id = ar.rule_id
        WHERE ar.location_id = %s
    """
    params = [location_id]
    if status:
        query += " AND ar.status = %s"
        params.append(status)
    if domain:
        query += " AND ar.domain = %s"
        params.append(domain)
    query += " ORDER BY ar.created_at DESC LIMIT 50"
    cur.execute(query, params)
    cols = [desc[0] for desc in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


def accept_recommendation(conn, recommendation_id: str, user_id: str) -> dict:
    """Accept a recommendation (pending → accepted)."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE advisory_recommendation
        SET status = 'accepted', executed_by = %s, executed_at = NOW()
        WHERE id = %s AND status = 'pending'
        RETURNING id, domain, title, urgency, severity
        """,
        (user_id, recommendation_id),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Recommendation not found or not pending"}

    cur.execute(
        """
        INSERT INTO advisory_log (recommendation_id, action, old_status, new_status, performed_by)
        VALUES (%s, 'accepted', 'pending', 'accepted', %s)
        """,
        (recommendation_id, user_id),
    )
    conn.commit()
    cur.close()

    return {
        "recommendation_id": str(row[0]),
        "domain": row[1],
        "title": row[2],
        "urgency": row[3],
        "severity": row[4],
        "status": "accepted",
    }


def dismiss_recommendation(conn, recommendation_id: str, reason: str = "") -> dict:
    """Dismiss a recommendation (pending → dismissed)."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE advisory_recommendation
        SET status = 'dismissed', dismissed_reason = %s
        WHERE id = %s AND status = 'pending'
        RETURNING id, domain, title
        """,
        (reason, recommendation_id),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Recommendation not found or not pending"}

    cur.execute(
        """
        INSERT INTO advisory_log (recommendation_id, action, old_status, new_status, notes)
        VALUES (%s, 'dismissed', 'pending', 'dismissed', %s)
        """,
        (recommendation_id, reason),
    )
    conn.commit()
    cur.close()

    return {"recommendation_id": str(row[0]), "status": "dismissed"}


# ============================================================
# Advisory Cycle
# ============================================================

def run_advisory_cycle(conn, location_id: str) -> dict:
    """Run a full advisory cycle: evaluate → generate → expire → summary."""
    # Evaluate rules
    triggered = evaluate_rules(conn, location_id)

    # Generate recommendations
    generated = []
    for rule in triggered:
        rec = generate_recommendation(conn, rule, rule["context"])
        generated.append(rec)

    # Expire old pending recommendations
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE advisory_recommendation
        SET status = 'expired'
        WHERE location_id = %s AND status = 'pending'
          AND expires_at IS NOT NULL AND expires_at < NOW()
        RETURNING id
        """,
        (location_id,),
    )
    expired_count = len(cur.fetchall())
    conn.commit()
    cur.close()

    return {
        "location_id": location_id,
        "rules_evaluated": len(triggered),
        "recommendations_generated": len(generated),
        "expired": expired_count,
        "recommendations": generated,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Advisory / Recommendation Engine")
    sub = parser.add_subparsers(dest="command")

    # Evaluate
    ev = sub.add_parser("evaluate", help="Evaluate rules for a location")
    ev.add_argument("--location-id", required=True)
    ev.add_argument("--json", action="store_true")

    # List
    ls = sub.add_parser("list", help="List recommendations")
    ls.add_argument("--location-id", required=True)
    ls.add_argument("--status")
    ls.add_argument("--domain")
    ls.add_argument("--json", action="store_true")

    # Accept
    ac = sub.add_parser("accept", help="Accept a recommendation")
    ac.add_argument("--recommendation-id", required=True)
    ac.add_argument("--user-id", required=True)
    ac.add_argument("--json", action="store_true")

    # Dismiss
    di = sub.add_parser("dismiss", help="Dismiss a recommendation")
    di.add_argument("--recommendation-id", required=True)
    di.add_argument("--reason", default="")
    di.add_argument("--json", action="store_true")

    # Run cycle
    rc = sub.add_parser("run-cycle", help="Run full advisory cycle")
    rc.add_argument("--location-id", required=True)
    rc.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command in ("evaluate", "list", "accept", "dismiss", "run-cycle"):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "evaluate":
            triggered = evaluate_rules(db, args.location_id)
            output = json.dumps(triggered, indent=2, default=str) if args.json else _format_triggered(triggered)
            print(output)

        elif args.command == "list":
            results = list_recommendations(db, args.location_id, args.status, args.domain)
            output = json.dumps(results, indent=2, default=str) if args.json else _format_list(results)
            print(output)

        elif args.command == "accept":
            result = accept_recommendation(db, args.recommendation_id, args.user_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_action(result)
            print(output)

        elif args.command == "dismiss":
            result = dismiss_recommendation(db, args.recommendation_id, args.reason)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_action(result)
            print(output)

        elif args.command == "run-cycle":
            result = run_advisory_cycle(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_cycle(result)
            print(output)

    finally:
        db.close()


def _format_triggered(triggered: list) -> str:
    if not triggered:
        return "No rules triggered."
    lines = [f"  [{r['severity'].upper()}] {r['rule_name']} ({r['domain']})" for r in triggered]
    return f"Triggered rules ({len(triggered)}):\n" + "\n".join(lines)


def _format_list(results: list) -> str:
    if not results:
        return "No recommendations."
    lines = [f"  [{r['urgency']:12s}] {r['title'][:60]:60s} ({r['status']})" for r in results]
    return f"Recommendations ({len(results)}):\n" + "\n".join(lines)


def _format_action(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return f"Recommendation {r['recommendation_id'][:8]}... → {r['status']}"


def _format_cycle(r: dict) -> str:
    lines = [
        f"Advisory Cycle — {r['location_id'][:8]}...",
        f"  Rules evaluated: {r['rules_evaluated']}",
        f"  Generated: {r['recommendations_generated']}",
        f"  Expired: {r['expired']}",
    ]
    for rec in r.get("recommendations", []):
        lines.append(f"  → [{rec['severity'].upper()}] {rec['title'][:60]}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
