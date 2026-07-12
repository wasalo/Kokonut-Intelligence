"""CLI for capability-based security.

Usage:
    python3 -m services.security --issue --holder NAME --capabilities '[{"resource":"harvest_event","action":"write"}]'
    python3 -m services.security --verify --token TOKEN --resource harvest_event --action write
    python3 -m services.security --revoke --token-id UUID
    python3 -m services.security --list-tokens [--holder NAME]
    python3 -m services.security --audit [--caller NAME] [--status denied] [--limit N]
    python3 -m services.security --audit-stats
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_issue(args):
    from services.security.capabilities import CapabilityManager

    manager = CapabilityManager()
    caps = json.loads(args.capabilities) if args.capabilities else []
    result = manager.issue(
        holder=args.holder,
        capabilities=caps,
        ttl_seconds=args.ttl,
        max_usage=args.max_usage,
        created_by=args.created_by,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_verify(args):
    from services.security.capabilities import CapabilityManager

    manager = CapabilityManager()
    result = manager.verify(args.token, args.resource, args.action, args.location_id)
    if result:
        print(json.dumps(result, indent=2))
        return 0
    else:
        print("Token verification failed")
        return 1


def cmd_revoke(args):
    from services.security.capabilities import CapabilityManager

    manager = CapabilityManager()
    if args.token_id:
        ok = manager.revoke(args.token_id)
    elif args.holder:
        count = manager.revoke_by_holder(args.holder)
        print(f"Revoked {count} tokens for {args.holder}")
        return 0
    else:
        print("--revoke requires --token-id or --holder")
        return 1

    if ok:
        print(f"Revoked token: {args.token_id}")
        return 0
    else:
        print(f"Failed to revoke token: {args.token_id}")
        return 1


def cmd_list_tokens(args):
    from services.security.capabilities import CapabilityManager

    manager = CapabilityManager()
    tokens = manager.list_tokens(holder=args.holder, active_only=args.active_only)
    if not tokens:
        print("No tokens found.")
        return 0

    print(f"{'Token ID':<38} {'Holder':<20} {'Expires':<22} {'Usage':<10} {'Revoked'}")
    print("-" * 95)
    for t in tokens:
        revoked = "yes" if t["revoked"] else "no"
        usage = f"{t['usage_count']}/{t['max_usage']}" if t["max_usage"] else str(t["usage_count"])
        print(f"{t['token_id']:<38} {t['holder']:<20} {t['expires_at'] or 'n/a':<22} {usage:<10} {revoked}")
    return 0


def cmd_audit(args):
    from services.security.audit import AuditLogger

    audit = AuditLogger()
    logs = audit.query_logs(
        caller=args.caller,
        resource_type=args.resource_type,
        action=args.action,
        status=args.audit_status,
        limit=args.limit,
    )
    if not logs:
        print("No audit logs found.")
        return 0

    for log in logs:
        print(f"  [{log['status'].upper()}] {log['caller']} {log['action']} on {log['resource_type']}")
        print(f"    ID: {log['log_id']}")
        print(f"    Time: {log['created_at']}")
        print()
    return 0


def cmd_audit_stats(args):
    from services.security.audit import AuditLogger

    audit = AuditLogger()
    stats = audit.stats()
    print(json.dumps(stats, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Security CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", action="store_true", help="Issue a capability token")
    group.add_argument("--verify", action="store_true", help="Verify a capability token")
    group.add_argument("--revoke", action="store_true", help="Revoke a capability token")
    group.add_argument("--list-tokens", action="store_true", help="List capability tokens")
    group.add_argument("--audit", action="store_true", help="Query access audit logs")
    group.add_argument("--audit-stats", action="store_true", help="Show audit statistics")

    parser.add_argument("--holder", help="Token holder name")
    parser.add_argument("--capabilities", help="JSON array of capabilities")
    parser.add_argument("--ttl", type=int, default=43200, help="Token TTL in seconds")
    parser.add_argument("--max-usage", type=int, default=None, help="Max usage count")
    parser.add_argument("--created-by", help="Creator name")
    parser.add_argument("--token", help="Capability token string")
    parser.add_argument("--token-id", help="Token UUID to revoke")
    parser.add_argument("--resource", help="Resource type")
    parser.add_argument("--action", help="Action type")
    parser.add_argument("--location-id", help="Location UUID constraint")
    parser.add_argument("--caller", help="Filter by caller")
    parser.add_argument("--resource-type", help="Filter by resource type")
    parser.add_argument("--audit-status", dest="audit_status", help="Filter by status")
    parser.add_argument("--active-only", action="store_true", default=True, help="Only active tokens")
    parser.add_argument("--limit", type=int, default=50, help="Max results")

    args = parser.parse_args()

    if args.issue:
        if not args.holder:
            parser.error("--issue requires --holder")
        rc = cmd_issue(args)
    elif args.verify:
        if not args.token or not args.resource or not args.action:
            parser.error("--verify requires --token, --resource, and --action")
        rc = cmd_verify(args)
    elif args.revoke:
        if not args.token_id and not args.holder:
            parser.error("--revoke requires --token-id or --holder")
        rc = cmd_revoke(args)
    elif args.list_tokens:
        rc = cmd_list_tokens(args)
    elif args.audit:
        rc = cmd_audit(args)
    elif args.audit_stats:
        rc = cmd_audit_stats(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
