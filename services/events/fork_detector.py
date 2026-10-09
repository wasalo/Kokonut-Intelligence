"""Fork detector — the chess "fork" tactic applied to cross-domain insight flow.

A *fork* in chess is a single move that attacks two or more enemy pieces at once,
forcing the opponent to concede material because they can answer only one threat.
On the platform, a single observed event that would resolve TWO OR MORE pending
cross-domain transfers (or open decisions) is an analogous fork: one signal closes
multiple governance loops, saving human touches and cycle time.

This module is READ-ONLY by default. ``detect_fork_opportunities`` never writes.
``propose_fork_opportunities`` writes DRAFT rows to ``tactical_opportunity``
(status is forced to 'draft' in code; a human must promote/act on them). No
autonomous action, no publish, no on-chain effect.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def detect_fork_opportunities(
    conn, location_id: Optional[str] = None
) -> Dict[str, Any]:
    """Find single events resolving >=2 pending transfers/decisions (read-only).

    A fork is identified when one ``source_event_id`` has >=2 distinct
    ``target_domain`` values among pending ``insight_transfer`` rows, OR when a
    ``correlation_id``/``trigger_event_id`` is shared by >=2 pending
    ``decision_log`` rows. Both are "one move, many targets".
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Cross-domain transfer forks: group pending transfers by source event.
        cur.execute(
            """
            SELECT source_event_id,
                   COUNT(DISTINCT target_domain) AS target_count,
                   COUNT(*) AS transfer_count,
                   ARRAY_AGG(DISTINCT target_domain) AS target_domains,
                   ARRAY_AGG(id) AS transfer_ids
            FROM insight_transfer
            WHERE transfer_status IN ('detected', 'pending_review')
              AND source_event_id IS NOT NULL
            GROUP BY source_event_id
            HAVING COUNT(DISTINCT target_domain) >= 2
            ORDER BY target_count DESC
            """
        )
        transfer_forks = [dict(r) for r in cur.fetchall()]

        # Decision forks: group pending decisions by correlation/trigger event.
        decision_filter = ""
        params: List[Any] = []
        if location_id:
            decision_filter = " AND location_id = %s"
            params.append(location_id)
        cur.execute(
            f"""
            SELECT COALESCE(correlation_id::text, trigger_event_id::text) AS group_key,
                   COUNT(*) AS decision_count,
                   ARRAY_AGG(id) AS decision_ids,
                   ARRAY_AGG(action_type) AS action_types
            FROM decision_log
            WHERE approval_status = 'pending'
              AND COALESCE(correlation_id::text, trigger_event_id::text) IS NOT NULL
              {decision_filter}
            GROUP BY COALESCE(correlation_id::text, trigger_event_id::text)
            HAVING COUNT(*) >= 2
            ORDER BY decision_count DESC
            """,
            params,
        )
        decision_forks = [dict(r) for r in cur.fetchall()]

    forks = []
    for f in transfer_forks:
        forks.append({
            "fork_type": "insight_transfer",
            "group_key": str(f["source_event_id"]),
            "target_count": int(f["target_count"]),
            "transfer_count": int(f["transfer_count"]),
            "target_domains": f["target_domains"],
            "transfer_ids": [str(t) for t in f["transfer_ids"]],
            "decision_ids": [],
            "severity": "high" if f["target_count"] >= 3 else "medium",
        })
    for f in decision_forks:
        forks.append({
            "fork_type": "decision_log",
            "group_key": f["group_key"],
            "target_count": int(f["decision_count"]),
            "transfer_count": 0,
            "target_domains": [],
            "transfer_ids": [],
            "decision_ids": [str(d) for d in f["decision_ids"]],
            "action_types": f["action_types"],
            "severity": "high" if f["decision_count"] >= 3 else "medium",
        })

    return {
        "location_id": location_id,
        "fork_count": len(forks),
        "forks": forks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Forks are read-only detections. Use propose_fork_opportunities to "
            "surface DRAFT tactical items for human review."
        ),
    }


def propose_fork_opportunities(
    conn, location_id: Optional[str] = None, actor: Optional[str] = None
) -> Dict[str, Any]:
    """Write DRAFT tactical_opportunity rows for each detected fork.

    Status is forced to 'draft' in code; no autonomous action or publish.
    Returns the created opportunity rows (empty if none detected).
    """
    detection = detect_fork_opportunities(conn, location_id=location_id)
    created = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for fork in detection["forks"]:
            detail = fork["target_domains"] or fork.get("action_types") or []
            summary = (
                f"Fork ({fork['fork_type']}): one event resolves "
                f"{fork['target_count']} targets {detail}. Resolve together to "
                f"save human touches and shorten the governance cycle."
            )
            opp_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO tactical_opportunity
                    (id, opportunity_type, location_id, severity,
                     opportunity_summary, source_refs, status, proposed_by)
                VALUES (%s, 'fork', %s, %s, %s, %s, 'draft', %s)
                RETURNING *
                """,
                (
                    opp_id,
                    location_id,
                    fork["severity"],
                    summary,
                    _refs_json(fork),
                    actor,
                ),
            )
            created.append(dict(cur.fetchone()))
    conn.commit()

    return {
        "location_id": location_id,
        "proposed_count": len(created),
        "opportunities": created,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "DRAFT opportunities created; human review required to act.",
    }


def _refs_json(fork: Dict[str, Any]) -> Any:
    refs = {
        "fork_type": fork["fork_type"],
        "group_key": fork["group_key"],
        "transfer_ids": fork.get("transfer_ids", []),
        "decision_ids": fork.get("decision_ids", []),
    }
    return _jsonb(refs)


def _jsonb(obj: Any) -> Any:
    import json as _json

    return _json.dumps(obj)
