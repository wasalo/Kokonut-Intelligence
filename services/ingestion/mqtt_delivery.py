"""Private delivery evidence and serialized, bounded MQTT processing."""

import hashlib

from services.common.cli import get_connection

MAX_ATTEMPTS = 5
TERMINAL = {"accepted", "rejected", "dead_letter", "disposed"}


def delivery_key(topic: str, payload: bytes) -> str:
    return hashlib.sha256(topic.encode() + b"\0" + payload).hexdigest()


def process_delivery(topic: str, payload: bytes, handler, *, replay_actor=None, replay_reason=None) -> dict:
    """Serialize identical deliveries while their source transaction completes.

    Source/outbox commit precedes the receipt commit; a crash between them is
    handled by the existing reading duplicate key on redelivery.
    """
    if len(payload) > 10240:
        raise ValueError("MQTT payload exceeds the broker's evidence limit")
    if replay_actor is not None or replay_reason is not None:
        if (
            not isinstance(replay_actor, str)
            or not replay_actor.strip()
            or not isinstance(replay_reason, str)
            or not replay_reason.strip()
        ):
            raise ValueError("Replay requires an actor and reason")
    with get_connection() as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute(
            """INSERT INTO mqtt_delivery (delivery_key, topic, payload)
               VALUES (:key, :topic, :payload) ON CONFLICT (delivery_key) DO NOTHING""",
            {"key": delivery_key(topic, payload), "topic": topic, "payload": payload},
        )
        row = conn.execute(
            "SELECT * FROM mqtt_delivery WHERE delivery_key = :key FOR UPDATE",
            {"key": delivery_key(topic, payload)},
        ).first()
        if replay_actor is not None:
            if row["status"] not in {"failed", "dead_letter", "rejected"}:
                raise ValueError("Only failed, dead-letter, or rejected deliveries can be replayed")
            conn.execute(
                """INSERT INTO mqtt_delivery_action (delivery_id, action, actor, reason)
                   VALUES (:id, 'replay', :actor, :reason)""",
                {"id": row["id"], "actor": replay_actor, "reason": replay_reason},
            )
            row["attempt_count"] = 0
        elif row["status"] in TERMINAL:
            return {"id": str(row["id"]), "status": row["status"], "attempt_count": row["attempt_count"]}
        attempt = row["attempt_count"] + 1
        error = None
        try:
            outcome = handler()
            if outcome not in {"accepted", "duplicate", "rejected"}:
                raise RuntimeError("Unknown sensor processing outcome")
            status = "accepted" if outcome in {"accepted", "duplicate"} else "rejected"
        except Exception as exc:
            # Store exception type only; SQL errors can contain private payloads.
            error = type(exc).__name__
            status = "dead_letter" if attempt >= MAX_ATTEMPTS else "failed"
        conn.execute(
            """UPDATE mqtt_delivery SET status = :status, attempt_count = :attempt,
                      last_error = :error, updated_at = NOW() WHERE id = :id""",
            {"id": row["id"], "status": status, "attempt": attempt, "error": error},
        )
    return {"id": str(row["id"]), "status": status, "attempt_count": attempt}
