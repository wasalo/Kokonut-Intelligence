"""Explicit operator review, replay, and disposal of private MQTT deliveries."""

import argparse
from uuid import UUID

from services.common.cli import get_connection, print_json, run


def command(args):
    if args.list:
        if not 1 <= args.limit <= 1000:
            raise ValueError("Limit must be between 1 and 1000")
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, status, attempt_count, last_error, created_at, updated_at
                   FROM mqtt_delivery WHERE status IN ('failed', 'dead_letter', 'rejected')
                   ORDER BY updated_at DESC LIMIT :limit""", {"limit": args.limit},
            ).all()
        for row in rows:
            if row.get("last_error"):
                row["last_error"] = "[details redacted]"
        print_json(rows)
        return
    if not (args.actor or "").strip() or not (args.reason or "").strip():
        raise ValueError("Replay and disposal require an actor and reason")
    if args.replay:
        from .field_validation import get_transport_timestamp_mode

        # Fail before reading or resetting the retained receipt/retry budget.
        get_transport_timestamp_mode()
    delivery_id = str(UUID(args.replay or args.dispose))
    with get_connection() as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        row = conn.execute(
            "SELECT * FROM mqtt_delivery WHERE id = :id FOR UPDATE", {"id": delivery_id},
        ).first()
        if row is None:
            raise ValueError("Delivery not found")
        if row["status"] not in {"failed", "dead_letter", "rejected"}:
            raise ValueError("Only failed, dead-letter, or rejected deliveries support operator recovery")
        if args.dispose:
            conn.execute(
                """INSERT INTO mqtt_delivery_action (delivery_id, action, actor, reason)
                   VALUES (:id, 'dispose', :actor, :reason)""",
                {"id": delivery_id, "actor": args.actor, "reason": args.reason},
            )
            conn.execute(
                "UPDATE mqtt_delivery SET status = 'disposed', updated_at = NOW() WHERE id = :id",
                {"id": delivery_id},
            )
    if args.dispose:
        print_json({"id": delivery_id, "status": "disposed"})
        return
    from .mqtt_delivery import process_delivery
    from .mqtt_subscriber import MQTTSensorSubscriber

    subscriber = MQTTSensorSubscriber()
    subscriber._delivery_mode = "qos1"
    topic = row["topic"]
    payload = bytes(row["payload"])

    def process():
        parts = topic.split("/")
        if len(parts) != 4 or parts[0] != "sensors" or parts[3] != "readings":
            return "rejected"
        return subscriber._handle_reading(payload, parts[1], parts[2])

    try:
        outcome = process_delivery(topic, payload, process, replay_actor=args.actor, replay_reason=args.reason)
    finally:
        subscriber.stop()
    print_json(outcome)
    if outcome["status"] != "accepted":
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="MQTT delivery recovery")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--replay", metavar="DELIVERY_UUID")
    group.add_argument("--dispose", metavar="DELIVERY_UUID")
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    parser.add_argument("--limit", type=int, default=50)
    run(command, parser.parse_args())


if __name__ == "__main__":
    main()
