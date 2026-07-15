"""Channel Orchestration + Customer Health service.

Manages multi-channel delivery configurations, per-segment channel
preferences, fallback rules, interaction tracking, and automated
customer health scoring.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db


# ──────────────────────────────────────────────
# Channel Configuration
# ──────────────────────────────────────────────

def create_channel_config(
    conn, location_id: str, channel_name: str, channel_type: str,
    config: Optional[Dict] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO channel_config (location_id, channel_name, channel_type, config)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (location_id, channel_name) DO UPDATE
            SET channel_type = EXCLUDED.channel_type, config = EXCLUDED.config, updated_at = NOW()
            RETURNING id, channel_name, channel_type, is_active
            """,
            (location_id, channel_name, channel_type, json.dumps(config or {})),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_channel_configs(conn, location_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, channel_name, channel_type, is_active, config, created_at
            FROM channel_config WHERE location_id = %s
            ORDER BY channel_name
            """,
            (location_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# Channel Preferences
# ──────────────────────────────────────────────

def set_channel_preference(
    conn, location_id: str, segment_type: str, channel_type: str,
    priority: int = 0, is_primary: bool = False,
    segment_id: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO channel_preference (
                location_id, segment_type, segment_id, channel_type, priority, is_primary
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, segment_type, channel_type, priority, is_primary
            """,
            (location_id, segment_type, segment_id, channel_type, priority, is_primary),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def get_delivery_plan(
    conn, location_id: str, segment_type: str = "all",
    segment_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get ordered channel list for a segment, with fallback rules."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Get preferences for this segment (or 'all' segment)
        cur.execute(
            """
            SELECT cp.channel_type, cp.priority, cp.is_primary
            FROM channel_preference cp
            WHERE cp.location_id = %s
              AND cp.segment_type IN (%s, 'all')
            ORDER BY cp.priority DESC, cp.is_primary DESC
            """,
            (location_id, segment_type),
        )
        prefs = [dict(r) for r in cur.fetchall()]

        # Get active fallback rules
        cur.execute(
            """
            SELECT primary_channel, fallback_channels, trigger_condition, timeout_hours
            FROM channel_fallback_rule
            WHERE location_id = %s AND is_active = TRUE
            """,
            (location_id,),
        )
        fallbacks = {r["primary_channel"]: dict(r) for r in cur.fetchall()}

        # Get active channel configs
        cur.execute(
            """
            SELECT channel_name, channel_type, config
            FROM channel_config
            WHERE location_id = %s AND is_active = TRUE
            """,
            (location_id,),
        )
        configs = {r["channel_type"]: dict(r) for r in cur.fetchall()}

    # Build delivery plan
    plan = []
    for pref in prefs:
        ch = pref["channel_type"]
        entry = {
            "channel": ch,
            "priority": pref["priority"],
            "is_primary": pref["is_primary"],
            "config": configs.get(ch, {}).get("config", {}),
            "fallback": fallbacks.get(ch),
        }
        plan.append(entry)

    # If no preferences set, return all active channels as defaults
    if not plan:
        for ch_type, cfg in configs.items():
            plan.append({
                "channel": ch_type,
                "priority": 0,
                "is_primary": False,
                "config": cfg.get("config", {}),
                "fallback": fallbacks.get(ch_type),
            })

    return plan


# ──────────────────────────────────────────────
# Fallback Rules
# ──────────────────────────────────────────────

def create_fallback_rule(
    conn, location_id: str, rule_name: str, primary_channel: str,
    fallback_channels: List[str], trigger_condition: str = "no_response",
    timeout_hours: int = 24,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO channel_fallback_rule (
                location_id, rule_name, primary_channel, fallback_channels,
                trigger_condition, timeout_hours
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, rule_name, primary_channel, fallback_channels
            """,
            (
                location_id, rule_name, primary_channel,
                json.dumps(fallback_channels), trigger_condition, timeout_hours,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Customer Interactions
# ──────────────────────────────────────────────

def log_interaction(
    conn, location_id: str, customer_type: str, customer_id: str,
    interaction_type: str, channel_type: Optional[str] = None,
    subject: Optional[str] = None, content: Optional[str] = None,
    sentiment: Optional[str] = None, response_required: bool = False,
    response_by: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO customer_interaction (
                location_id, customer_type, customer_id, interaction_type,
                channel_type, subject, content, sentiment,
                response_required, response_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, interaction_type, sentiment, created_at
            """,
            (
                location_id, customer_type, customer_id, interaction_type,
                channel_type, subject, content, sentiment,
                response_required, response_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_interactions(
    conn, location_id: str, customer_type: Optional[str] = None,
    customer_id: Optional[str] = None, limit: int = 50,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        conditions = ["location_id = %s"]
        params: list = [location_id]
        if customer_type:
            conditions.append("customer_type = %s")
            params.append(customer_type)
        if customer_id:
            conditions.append("customer_id = %s")
            params.append(customer_id)
        where = " AND ".join(conditions)
        cur.execute(
            f"""
            SELECT id, customer_type, customer_id, interaction_type,
                   channel_type, subject, sentiment, created_at
            FROM customer_interaction
            WHERE {where}
            ORDER BY created_at DESC LIMIT %s
            """,
            params + [limit],
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# Customer Health Score
# ──────────────────────────────────────────────

def compute_health_score(
    conn, location_id: str, customer_type: str, customer_id: str,
) -> Dict[str, Any]:
    """Compute automated health score (0-100) from interactions, feedback, orders.

    Components:
    - Engagement (30%): total interactions in last 90 days
    - Satisfaction (30%): sentiment ratio (positive / total)
    - Recency (20%): days since last interaction (lower = better)
    - Frequency (20%): average interactions per week
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Get interactions for this customer in last 90 days
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_interactions,
                COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive_count,
                COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative_count,
                MAX(created_at) AS last_interaction,
                MIN(created_at) AS first_interaction
            FROM customer_interaction
            WHERE location_id = %s
              AND customer_type = %s
              AND customer_id = %s
              AND created_at >= NOW() - INTERVAL '90 days'
            """,
            (location_id, customer_type, customer_id),
        )
        stats = dict(cur.fetchone())

        # Get feedback sentiment
        cur.execute(
            """
            SELECT
                COUNT(*) AS feedback_count,
                AVG(CASE
                    WHEN sentiment = 'positive' THEN 1.0
                    WHEN sentiment = 'neutral' THEN 0.5
                    WHEN sentiment = 'negative' THEN 0.0
                    ELSE 0.5
                END) AS avg_sentiment
            FROM stakeholder_feedback
            WHERE location_id = %s
              AND created_at >= NOW() - INTERVAL '90 days'
            """,
            (location_id,),
        )
        fb = dict(cur.fetchone())

    total = stats["total_interactions"] or 0
    positive = stats["positive_count"] or 0
    last = stats["last_interaction"]
    first = stats["first_interaction"]

    # Engagement score (0-100): scale by 20 interactions = 100
    engagement = min(100.0, (total / 20.0) * 100) if total > 0 else 0.0

    # Satisfaction score (0-100): positive ratio * 100, blended with feedback
    if total > 0:
        interaction_sentiment = positive / total if total > 0 else 0.5
    else:
        interaction_sentiment = 0.5
    feedback_sentiment = float(fb["avg_sentiment"] or 0.5)
    satisfaction = ((interaction_sentiment * 0.6 + feedback_sentiment * 0.4) * 100)

    # Recency score (0-100): 0 days = 100, 90+ days = 0
    if last:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since = (now - last).days
        recency = max(0.0, 100.0 - (days_since / 90.0) * 100)
    else:
        recency = 0.0

    # Frequency score (0-100): interactions per week, 2+/week = 100
    if first and last and total > 0:
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        span_weeks = max((last - first).days / 7.0, 1.0)
        freq_per_week = total / span_weeks
        frequency = min(100.0, (freq_per_week / 2.0) * 100)
    else:
        frequency = 0.0

    # Composite score
    health = (
        engagement * 0.30
        + satisfaction * 0.30
        + recency * 0.20
        + frequency * 0.20
    )
    health = round(min(100.0, max(0.0, health)), 1)

    breakdown = {
        "engagement": round(engagement, 1),
        "satisfaction": round(satisfaction, 1),
        "recency": round(recency, 1),
        "frequency": round(frequency, 1),
        "total_interactions_90d": total,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO customer_health_score (
                location_id, customer_type, customer_id,
                health_score, engagement_score, satisfaction_score,
                recency_score, frequency_score, breakdown, computed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (location_id, customer_type, customer_id)
            DO UPDATE SET
                health_score = EXCLUDED.health_score,
                engagement_score = EXCLUDED.engagement_score,
                satisfaction_score = EXCLUDED.satisfaction_score,
                recency_score = EXCLUDED.recency_score,
                frequency_score = EXCLUDED.frequency_score,
                breakdown = EXCLUDED.breakdown,
                computed_at = NOW(),
                updated_at = NOW()
            """,
            (
                location_id, customer_type, customer_id,
                health, engagement, satisfaction, recency, frequency,
                json.dumps(breakdown),
            ),
        )
        conn.commit()

    return {
        "health_score": health,
        "engagement_score": round(engagement, 1),
        "satisfaction_score": round(satisfaction, 1),
        "recency_score": round(recency, 1),
        "frequency_score": round(frequency, 1),
        "breakdown": breakdown,
    }


def list_health_scores(
    conn, location_id: str, customer_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if customer_type:
            cur.execute(
                """
                SELECT id, customer_type, customer_id, health_score,
                       engagement_score, satisfaction_score, recency_score,
                       frequency_score, computed_at
                FROM customer_health_score
                WHERE location_id = %s AND customer_type = %s
                ORDER BY health_score DESC
                """,
                (location_id, customer_type),
            )
        else:
            cur.execute(
                """
                SELECT id, customer_type, customer_id, health_score,
                       engagement_score, satisfaction_score, recency_score,
                       frequency_score, computed_at
                FROM customer_health_score
                WHERE location_id = %s
                ORDER BY health_score DESC
                """,
                (location_id,),
            )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "create-channel":
            out = create_channel_config(
                conn, args.location_id, args.channel_name, args.channel_type,
            )
        elif args.command == "list-channels":
            out = list_channel_configs(conn, args.location_id)
        elif args.command == "set-preference":
            out = set_channel_preference(
                conn, args.location_id, args.segment_type, args.channel_type,
                priority=args.priority, is_primary=args.is_primary,
            )
        elif args.command == "delivery-plan":
            out = get_delivery_plan(conn, args.location_id, args.segment_type)
        elif args.command == "create-fallback":
            out = create_fallback_rule(
                conn, args.location_id, args.rule_name, args.primary_channel,
                args.fallback_channels, trigger_condition=args.trigger,
                timeout_hours=args.timeout,
            )
        elif args.command == "log-interaction":
            out = log_interaction(
                conn, args.location_id, args.customer_type, args.customer_id,
                args.interaction_type, channel_type=args.channel,
                subject=args.subject, sentiment=args.sentiment,
            )
        elif args.command == "list-interactions":
            out = list_interactions(
                conn, args.location_id, customer_type=args.customer_type,
            )
        elif args.command == "compute-health":
            out = compute_health_score(
                conn, args.location_id, args.customer_type, args.customer_id,
            )
        elif args.command == "list-health":
            out = list_health_scores(
                conn, args.location_id, customer_type=args.customer_type,
            )
        else:
            out = {}
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Channel Orchestration + Customer Health")
    p.add_argument("--location-id", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    cc = sub.add_parser("create-channel")
    cc.add_argument("--channel-name", required=True)
    cc.add_argument("--channel-type", required=True,
                    choices=["sms", "whatsapp", "mobile_app", "email", "voice_call",
                             "ussd", "radio", "community_screen", "print", "in_person",
                             "web_portal", "api"])

    sub.add_parser("list-channels")

    sp = sub.add_parser("set-preference")
    sp.add_argument("--segment-type", required=True,
                    choices=["farmer", "buyer", "cooperative", "community", "all"])
    sp.add_argument("--channel-type", required=True)
    sp.add_argument("--priority", type=int, default=0)
    sp.add_argument("--is-primary", action="store_true")

    dp = sub.add_parser("delivery-plan")
    dp.add_argument("--segment-type", default="all")

    cf = sub.add_parser("create-fallback")
    cf.add_argument("--rule-name", required=True)
    cf.add_argument("--primary-channel", required=True)
    cf.add_argument("--fallback-channels", nargs="+", required=True)
    cf.add_argument("--trigger", default="no_response",
                    choices=["no_response", "delivery_failed", "timeout", "manual"])
    cf.add_argument("--timeout", type=int, default=24)

    li = sub.add_parser("log-interaction")
    li.add_argument("--customer-type", required=True,
                    choices=["farmer", "buyer", "cooperative", "community", "partner"])
    li.add_argument("--customer-id", required=True)
    li.add_argument("--interaction-type", required=True)
    li.add_argument("--channel", default=None)
    li.add_argument("--subject", default=None)
    li.add_argument("--sentiment", default=None,
                    choices=["positive", "neutral", "negative"])

    lis = sub.add_parser("list-interactions")
    lis.add_argument("--customer-type", default=None)

    ch = sub.add_parser("compute-health")
    ch.add_argument("--customer-type", required=True,
                    choices=["farmer", "buyer", "cooperative", "community", "partner"])
    ch.add_argument("--customer-id", required=True)

    lh = sub.add_parser("list-health")
    lh.add_argument("--customer-type", default=None)

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
