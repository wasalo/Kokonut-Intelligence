"""CLI for cooperative governance and explainable stakeholder trust."""

from __future__ import annotations

import argparse
import json
import sys

from services.analytics import cooperative_governance as governance
from services.analytics import stakeholder_trust as trust
from services.common.database import get_db


def out(value):
    print(json.dumps(value, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Stakeholder trust and cooperative governance")
    sub = parser.add_subparsers(dest="command")
    evidence = sub.add_parser("record-evidence")
    evidence.add_argument("party_id"); evidence.add_argument("dimension"); evidence.add_argument("direction"); evidence.add_argument("source_type"); evidence.add_argument("summary")
    evidence.add_argument("--relationship-party-id"); evidence.add_argument("--source-id"); evidence.add_argument("--source-label"); evidence.add_argument("--confidence", type=float); evidence.add_argument("--uncertainty", type=float); evidence.add_argument("--evidence-hash"); evidence.add_argument("--evidence-cid"); evidence.add_argument("--audience", default="internal"); evidence.add_argument("--created-by-party-id")
    evidence.set_defaults(func=lambda c, a: trust.record_evidence(c, a.party_id, a.dimension, a.direction, a.source_type, a.summary, relationship_party_id=a.relationship_party_id, source_id=a.source_id, source_label=a.source_label, confidence=a.confidence, uncertainty=a.uncertainty, evidence_hash=a.evidence_hash, evidence_cid=a.evidence_cid, audience=a.audience, created_by_party_id=a.created_by_party_id))
    buyer = sub.add_parser("verify-buyer")
    buyer.add_argument("buyer_id"); buyer.add_argument("verification_type"); buyer.add_argument("method"); buyer.add_argument("--verified-by-party-id"); buyer.add_argument("--evidence-hash"); buyer.add_argument("--evidence-cid"); buyer.add_argument("--expires-at")
    buyer.set_defaults(func=lambda c, a: trust.verify_buyer(c, a.buyer_id, a.verification_type, a.method, verified_by_party_id=a.verified_by_party_id, evidence_hash=a.evidence_hash, evidence_cid=a.evidence_cid, expires_at=a.expires_at))
    profile = sub.add_parser("profile"); profile.add_argument("party_id"); profile.set_defaults(func=lambda c, a: trust.profile(c, a.party_id))
    timeline = sub.add_parser("timeline"); timeline.add_argument("party_id"); timeline.set_defaults(func=lambda c, a: trust.evidence_timeline(c, a.party_id))
    risks = sub.add_parser("risks"); risks.add_argument("--party-id"); risks.set_defaults(func=lambda c, a: trust.risk_indicators(c, a.party_id))
    health = sub.add_parser("governance-health"); health.add_argument("--cooperative-id"); health.set_defaults(func=lambda c, a: governance.governance_health(c, a.cooperative_id))
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help(); sys.exit(1)
    conn = get_db()
    try:
        out(args.func(conn, args))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
