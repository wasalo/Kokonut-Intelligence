#!/usr/bin/env python3
"""
LLM Chat — Natural Language Interface

Processes natural language queries about farm data, classifies intent,
and returns structured responses from existing analytics services.

Usage:
    python -m services.analytics.llm_chat chat --session-id UUID --message "What was the maize yield?"
    python -m services.analytics.llm_chat session --create --location-id UUID --user admin
    python -m services.analytics.llm_chat intents
    python -m services.analytics.llm_chat history --session-id UUID
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.llm_chat")


# ============================================================
# Intent Classification
# ============================================================

# Keyword-based intent classification (lightweight, no LLM dependency)
INTENT_KEYWORDS = {
    "get_yield": {
        "keywords": ["yield", "harvest", "production", "crop output", "how much", "kg/ha", "tons"],
        "priority": 10,
    },
    "get_weather": {
        "keywords": ["weather", "forecast", "rain", "temperature", "wind", "humidity", "sunny", "cloudy"],
        "priority": 10,
    },
    "get_soil": {
        "keywords": ["soil", "moisture", "nitrogen", "phosphorus", "potassium", "organic matter", "ph", "compaction"],
        "priority": 10,
    },
    "get_crisp": {
        "keywords": ["crisp", "risk", "score", "rating", "climate risk", "carbon yield", "financial risk"],
        "priority": 8,
    },
    "get_advisory": {
        "keywords": ["advice", "recommend", "should", "alert", "warning", "action", "what to do", "priority"],
        "priority": 7,
    },
    "compare_seasons": {
        "keywords": ["compare", "trend", "difference", "vs", "versus", "last season", "previous", "historical"],
        "priority": 6,
    },
    "estimate_cost": {
        "keywords": ["cost", "price", "budget", "expense", "spend", "estimate", "how much does"],
        "priority": 6,
    },
    "digital_twin": {
        "keywords": ["simulate", "what if", "scenario", "project", "predict", "model", "forecast yield"],
        "priority": 5,
    },
}


def classify_intent(message: str) -> dict:
    """Classify the intent of a user message using keyword matching."""
    message_lower = message.lower().strip()

    scores = {}
    for intent, config in INTENT_KEYWORDS.items():
        score = 0
        for kw in config["keywords"]:
            if kw in message_lower:
                # Longer keyword matches are more specific
                score += len(kw) * config["priority"]
        if score > 0:
            scores[intent] = score

    if not scores:
        return {"intent": "unknown", "confidence": 0.0, "entities": {}}

    best_intent = max(scores, key=scores.get)
    max_possible = max(config["priority"] * len(max(config["keywords"], key=len))
                       for config in INTENT_KEYWORDS.values())
    confidence = min(scores[best_intent] / max_possible, 1.0)

    # Extract entities from message
    entities = _extract_entities(message_lower)

    return {
        "intent": best_intent,
        "confidence": round(confidence, 2),
        "entities": entities,
    }


def _extract_entities(message: str) -> dict:
    """Extract entities (crop names, dates, metrics) from message."""
    entities = {}

    # Crop names
    crops = ["maize", "beans", "cassava", "sweet potato", "coffee", "avocado", "tomato", "banana"]
    for crop in crops:
        if crop in message:
            entities["crop_name"] = crop

    # Time references
    if any(w in message for w in ["last season", "previous", "last year"]):
        entities["time_ref"] = "last_season"
    elif any(w in message for w in ["this season", "current", "this year"]):
        entities["time_ref"] = "this_season"
    elif any(w in message for w in ["today", "now", "current"]):
        entities["time_ref"] = "today"
    elif any(w in message for w in ["tomorrow", "next"]):
        entities["time_ref"] = "tomorrow"

    # Metrics
    metric_map = {
        "yield": "yield_amount",
        "moisture": "soil_moisture",
        "nitrogen": "soil_nitrogen",
        "temperature": "air_temperature",
        "rainfall": "precipitation",
        "wind": "wind_speed",
    }
    for keyword, metric in metric_map.items():
        if keyword in message:
            entities["metric"] = metric

    # Areas
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(ha|hectare|acre)", message)
    if area_match:
        entities["area"] = float(area_match.group(1))
        entities["area_unit"] = area_match.group(2)

    # Numbers (potential quantities)
    num_match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|tons?|mm|cm)", message)
    if num_match:
        entities["quantity"] = float(num_match.group(1))
        entities["quantity_unit"] = num_match.group(2)

    return entities


# ============================================================
# Session Management
# ============================================================

def create_session(conn, location_id: str = None, user_id: str = None, title: str = None) -> dict:
    """Create a new chat session."""
    cur = conn.cursor()
    session_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO chat_session (id, location_id, user_id, title, status)
        VALUES (%s, %s, %s, %s, 'active')
        RETURNING id
        """,
        (session_id, location_id, user_id, title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"),
    )
    conn.commit()
    cur.close()
    return {"session_id": session_id, "location_id": location_id, "user_id": user_id}


def get_session(conn, session_id: str) -> dict:
    """Get session details."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, location_id, user_id, title, status, message_count, started_at FROM chat_session WHERE id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return {"error": "Session not found"}
    return {
        "session_id": row[0],
        "location_id": row[1],
        "user_id": row[2],
        "title": row[3],
        "status": row[4],
        "message_count": row[5],
        "started_at": row[6].isoformat() if row[6] else None,
    }


# ============================================================
# Message Processing
# ============================================================

def process_message(conn, session_id: str, message: str) -> dict:
    """Process a user message and generate a response."""
    import time as _time
    start_time = _time.time()

    # Classify intent
    classification = classify_intent(message)
    intent = classification["intent"]

    # Store user message
    user_msg_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_message (id, session_id, role, content, intent, intent_confidence, entities)
        VALUES (%s, %s, 'user', %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (user_msg_id, session_id, message, intent, classification["confidence"], json.dumps(classification["entities"])),
    )

    # Update session message count
    cur.execute(
        """
        UPDATE chat_session
        SET message_count = message_count + 1, last_message_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (session_id,),
    )
    conn.commit()

    # Get session context
    cur.execute("SELECT location_id FROM chat_session WHERE id = %s", (session_id,))
    session_row = cur.fetchone()
    location_id = session_row[0] if session_row else None

    # Generate response based on intent
    response_text, sources, query_results = _handle_intent(conn, intent, classification["entities"], location_id)

    # Store assistant message
    response_time_ms = int((_time.time() - start_time) * 1000)
    assistant_msg_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO chat_message
            (id, session_id, role, content, intent, intent_confidence, entities,
             response_time_ms, sources, query_results)
        VALUES (%s, %s, 'assistant', %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            assistant_msg_id, session_id, response_text, intent,
            classification["confidence"], json.dumps(classification["entities"]),
            response_time_ms, json.dumps(sources), json.dumps(query_results),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "message_id": assistant_msg_id,
        "response": response_text,
        "intent": intent,
        "confidence": classification["confidence"],
        "entities": classification["entities"],
        "sources": sources,
        "response_time_ms": response_time_ms,
    }


def _handle_intent(conn, intent: str, entities: dict, location_id: str = None) -> tuple:
    """Handle a classified intent and return (response_text, sources, query_results)."""
    if intent == "get_yield":
        return _handle_yield(conn, entities, location_id)
    elif intent == "get_weather":
        return _handle_weather(conn, entities, location_id)
    elif intent == "get_soil":
        return _handle_soil(conn, entities, location_id)
    elif intent == "get_crisp":
        return _handle_crisp(conn, entities, location_id)
    elif intent == "get_advisory":
        return _handle_advisory(conn, entities, location_id)
    elif intent == "compare_seasons":
        return _handle_comparison(conn, entities, location_id)
    elif intent == "estimate_cost":
        return _handle_cost(conn, entities, location_id)
    elif intent == "digital_twin":
        return _handle_twin(conn, entities, location_id)
    else:
        return (
            "I'm not sure how to help with that. I can assist with yield data, weather forecasts, soil conditions, CRISP scores, advisory recommendations, season comparisons, cost estimates, and digital twin simulations. Could you rephrase your question?",
            [],
            {},
        )


# ============================================================
# Intent Handlers
# ============================================================

def _handle_yield(conn, entities, location_id):
    cur = conn.cursor()
    crop = entities.get("crop_name")
    if location_id:
        where = "location_id = %s AND status IN ('verified', 'published')"
        params = [location_id]
        if crop:
            where += " AND crop_name = %s"
            params.append(crop)
        cur.execute(
            f"SELECT AVG(yield_amount), SUM(total_yield), COUNT(*) FROM harvest_yield_observation WHERE {where}",
            tuple(params),
        )
        row = cur.fetchone()
        cur.close()
        if row and row[0]:
            response = f"The average yield is {float(row[0]):.0f} kg/ha across {int(row[2])} observations. Total production: {float(row[1] or 0):.0f} kg."
            if crop:
                response = f"The average {crop} yield is {float(row[0]):.0f} kg/ha across {int(row[2])} observations. Total production: {float(row[1] or 0):.0f} kg."
            return response, ["harvest_yield_observation"], {"avg_yield": float(row[0]), "total": float(row[1] or 0)}
    cur.close()
    return "I don't have yield data for that query. Could you specify the location or crop?", [], {}


def _handle_weather(conn, entities, location_id):
    cur = conn.cursor()
    if location_id:
        time_ref = entities.get("time_ref", "today")
        if time_ref == "tomorrow":
            cur.execute(
                """SELECT forecast_date, temp_min_c, temp_max_c, precipitation_prob_pct, wind_speed_kmh
                   FROM weather_forecast WHERE location_id = %s AND forecast_date = CURRENT_DATE + 1
                   ORDER BY forecast_hour LIMIT 4""",
                (location_id,),
            )
        else:
            cur.execute(
                """SELECT AVG(temperature_c), AVG(precipitation_mm), AVG(humidity_pct), AVG(wind_speed_kmh)
                   FROM weather_observation WHERE location_id = %s AND observation_date >= CURRENT_DATE - 1""",
                (location_id,),
            )
        row = cur.fetchone()
        cur.close()
        if row:
            if time_ref == "tomorrow" and row[0]:
                response = f"Tomorrow's forecast: {float(row[1]):.0f}–{float(row[2]):.0f}°C, rain probability {float(row[3]):.0f}%, wind {float(row[4]):.0f} km/h."
            elif row[0]:
                response = f"Recent weather: avg temperature {float(row[0]):.1f}°C, rainfall {float(row[1] or 0):.1f}mm, humidity {float(row[2] or 0):.0f}%, wind {float(row[3] or 0):.1f} km/h."
            else:
                response = "Weather data is not available for this location."
            return response, ["weather_observation", "weather_forecast"], {}
    cur.close()
    return "I don't have weather data for that location. Could you provide a location?", [], {}


def _handle_soil(conn, entities, location_id):
    metric = entities.get("metric", "soil_moisture")
    cur = conn.cursor()
    if location_id:
        cur.execute(
            f"""SELECT AVG(value) FROM sensor_reading
                WHERE location_id = %s AND sensor_type = %s
                AND reading_date >= CURRENT_DATE - 7""",
            (location_id, metric),
        )
        row = cur.fetchone()
        cur.close()
        if row and row[0]:
            metric_name = metric.replace("_", " ")
            return f"Average {metric_name} over the past week: {float(row[0]):.1f}.", ["sensor_reading"], {"value": float(row[0])}
    cur.close()
    return "I don't have soil data for that query. Could you specify the metric or location?", [], {}


def _handle_crisp(conn, entities, location_id):
    cur = conn.cursor()
    if location_id:
        cur.execute(
            """SELECT dimension_name, score, risk_band
               FROM crisp_dimension_score
               WHERE location_id = %s
               ORDER BY score DESC""",
            (location_id,),
        )
        rows = cur.fetchall()
        cur.close()
        if rows:
            response_parts = ["CRISP Risk Scores:"]
            for name, score, band in rows:
                response_parts.append(f"  {name}: {float(score):.0f}/100 ({band})")
            return "\n".join(response_parts), ["crisp_dimension_score"], {"scores": {r[0]: float(r[1]) for r in rows}}
    cur.close()
    return "I don't have CRISP scores for that location.", [], {}


def _handle_advisory(conn, entities, location_id):
    cur = conn.cursor()
    if location_id:
        cur.execute(
            """SELECT title, severity, urgency, summary
               FROM advisory_recommendation
               WHERE location_id = %s AND status = 'pending'
               ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END
               LIMIT 5""",
            (location_id,),
        )
        rows = cur.fetchall()
        cur.close()
        if rows:
            response_parts = [f"You have {len(rows)} pending recommendation(s):"]
            for title, severity, urgency, summary in rows:
                response_parts.append(f"  [{severity.upper()}] {title} ({urgency})")
            return "\n".join(response_parts), ["advisory_recommendation"], {"count": len(rows)}
    cur.close()
    return "No pending advisories. All clear!", [], {}


def _handle_comparison(conn, entities, location_id):
    return "Season comparison is available through the yield trend analysis. Use: python -m services.analytics.yield_monitoring trend --location-id UUID", [], {}


def _handle_cost(conn, entities, location_id):
    area = entities.get("area", 1.0)
    crop = entities.get("crop_name", "maize")
    # Simple cost estimate
    fert_cost = 120 * 2.5 * area  # 120 kg/ha × $2.5/kg
    irr_cost = 10 * 0.05 * area * 7 * 12  # 10mm × $0.05/m² × 7 events × 12 months
    total = fert_cost + irr_cost
    return (
        f"Estimated annual costs for {area} ha of {crop}:\n"
        f"  Fertilizer: ${fert_cost:.0f}\n"
        f"  Irrigation: ${irr_cost:.0f}\n"
        f"  Total: ${total:.0f}",
        [],
        {"fertilizer": fert_cost, "irrigation": irr_cost, "total": total},
    )


def _handle_twin(conn, entities, location_id):
    return (
        "Digital twin simulations are available through the CLI. Use:\n"
        "  python -m services.analytics.digital_twin simulate --twin-id UUID\n"
        "  python -m services.analytics.digital_twin scenario --twin-id UUID --name 'Scenario' --params '{...}'",
        [],
        {},
    )


# ============================================================
# History / Query
# ============================================================

def get_chat_history(conn, session_id: str, limit: int = 50) -> list:
    """Get chat history for a session."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, content, intent, intent_confidence, created_at
        FROM chat_message
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (session_id, limit),
    )
    cols = [d[0] for d in cur.description]
    messages = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return messages


def list_intents(conn) -> list:
    """List all registered intents."""
    cur = conn.cursor()
    cur.execute(
        "SELECT name, description, examples, risk_level, status FROM chat_intent WHERE status = 'active' ORDER BY name"
    )
    cols = [d[0] for d in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


# ============================================================
# CLI
# ============================================================

cli = CommandLine("llm_chat", "LLM Chat interface")


def _render_chat(result, args):
    print(json.dumps(result, indent=2, default=str) if args.json else result["response"])


def _render_session(result, args):
    if result is None:
        return
    print(json.dumps(result, indent=2) if args.json else f"Session: {result['session_id'][:8]}...")


def _render_intents(result, args):
    print(json.dumps(result, indent=2, default=str) if args.json else _format_intents(result))


def _render_history(result, args):
    print(json.dumps(result, indent=2, default=str) if args.json else _format_history(result))


cli.subcommand("chat", "Send a message") \
    .add("--session-id", required=True) \
    .add("--message", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: process_message(db, a.session_id, a.message)) \
    .render_with(_render_chat)

cli.subcommand("session", "Create session") \
    .add("--create", action="store_true") \
    .add("--location-id") \
    .add("--user") \
    .add("--json", action="store_true") \
    .run(lambda db, a: create_session(db, a.location_id, a.user) if a.create else None) \
    .render_with(_render_session)

cli.subcommand("intents", "List intents") \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_intents(db)) \
    .render_with(_render_intents)

cli.subcommand("history", "Chat history") \
    .add("--session-id", required=True) \
    .add("--limit", type=int, default=50) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_chat_history(db, a.session_id, a.limit)) \
    .render_with(_render_history)


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()


def _format_intents(results: list) -> str:
    if not results:
        return "No intents registered."
    lines = [f"Intents ({len(results)}):"]
    for r in results:
        lines.append(f"  {r['name']:25s} [{r['risk_level']:8s}] {r['description'][:60]}")
    return "\n".join(lines)


def _format_history(results: list) -> str:
    if not results:
        return "No messages."
    lines = []
    for m in results:
        icon = "You" if m["role"] == "user" else "AI"
        lines.append(f"[{icon}] {m['content'][:100]}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
