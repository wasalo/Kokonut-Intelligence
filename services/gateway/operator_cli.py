"""Local database administration for explicitly provisioned OIDC operators."""

from __future__ import annotations

import argparse
import re
from urllib.parse import urlsplit
from uuid import UUID

from services.common.cli import get_connection, print_json, run

_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ValueError(f"{label} must be a UUID") from exc


def provision_identity(args) -> None:
    issuer = urlsplit(args.issuer)
    subject = args.subject
    if (
        issuer.scheme != "https"
        or not issuer.netloc
        or issuer.username
        or issuer.password
        or issuer.query
        or issuer.fragment
        or not subject
        or len(subject) > 255
        or subject != subject.strip()
    ):
        raise ValueError("issuer must be HTTPS and subject must be non-empty")
    with get_connection() as conn:
        row = conn.execute(
            """INSERT INTO operator_identity (issuer, subject, display_name, enabled)
               VALUES (:issuer, :subject, :display_name, TRUE)
               ON CONFLICT (issuer, subject) DO UPDATE
                 SET display_name = COALESCE(EXCLUDED.display_name, operator_identity.display_name),
                     enabled = TRUE, updated_at = NOW()
               RETURNING id, issuer, subject, display_name, enabled""",
            {
                "issuer": args.issuer,
                "subject": subject,
                "display_name": args.display_name,
            },
        ).first()
    print_json(row)


def disable_identity(args) -> None:
    operator_id = _uuid(args.operator_id, "operator-id")
    with get_connection() as conn:
        row = conn.execute(
            """UPDATE operator_identity SET enabled = FALSE, updated_at = NOW()
                 WHERE id = :operator_id
               RETURNING id, issuer, subject, enabled""",
            {"operator_id": operator_id},
        ).first()
        if row is not None:
            conn.execute(
                """UPDATE operator_session SET revoked_at = NOW()
                    WHERE operator_id = :operator_id AND revoked_at IS NULL""",
                {"operator_id": operator_id},
            )
    if row is None:
        raise ValueError("operator identity was not found")
    print_json(row)


def grant_scope(args) -> None:
    if not _SLUG.fullmatch(args.resource) or not _SLUG.fullmatch(args.action):
        raise ValueError("resource and action must be lowercase identifiers without wildcards")
    operator_id = _uuid(args.operator_id, "operator-id")
    location_id = _uuid(args.location_id, "location-id")
    if not args.granted_by.strip():
        raise ValueError("granted-by must identify the local operator")
    with get_connection() as conn:
        identity = conn.execute(
            """SELECT id FROM operator_identity
                WHERE id = :operator_id AND enabled = TRUE""",
            {"operator_id": operator_id},
        ).first()
        if identity is None:
            raise ValueError("enabled operator identity was not found")
        row = conn.execute(
            """INSERT INTO operator_scope_grant
                   (operator_id, resource, action, location_id, granted_by)
               VALUES (:operator_id, :resource, :action, :location_id, :granted_by)
               ON CONFLICT (operator_id, resource, action, location_id)
                   WHERE revoked_at IS NULL DO NOTHING
               RETURNING id, operator_id, resource, action, location_id, granted_by""",
            {
                "operator_id": operator_id,
                "resource": args.resource,
                "action": args.action,
                "location_id": location_id,
                "granted_by": args.granted_by.strip(),
            },
        ).first()
        if row is None:
            existing = conn.execute(
                """SELECT id, operator_id, resource, action, location_id, granted_by
                     FROM operator_scope_grant
                    WHERE operator_id = :operator_id AND resource = :resource
                      AND action = :action AND location_id = :location_id
                      AND revoked_at IS NULL""",
                {
                    "operator_id": operator_id,
                    "resource": args.resource,
                    "action": args.action,
                    "location_id": location_id,
                },
            ).first()
            if existing is None:
                raise ValueError("enabled operator identity was not found")
            row = existing
    print_json(row)


def revoke_scope(args) -> None:
    grant_id = _uuid(args.grant_id, "grant-id")
    with get_connection() as conn:
        row = conn.execute(
            """UPDATE operator_scope_grant SET revoked_at = NOW()
                 WHERE id = :grant_id AND revoked_at IS NULL
               RETURNING id, operator_id, resource, action, location_id, revoked_at""",
            {"grant_id": grant_id},
        ).first()
    if row is None:
        raise ValueError("active scope grant was not found")
    print_json(row)


def list_operators(args) -> None:
    with get_connection() as conn:
        identities = conn.execute(
            """SELECT id, issuer, subject, display_name, email, enabled, created_at
                 FROM operator_identity ORDER BY created_at, id"""
        ).all()
        grants = conn.execute(
            """SELECT id, operator_id, resource, action, location_id, granted_by,
                      created_at, revoked_at
                 FROM operator_scope_grant ORDER BY created_at, id"""
        ).all()
    print_json({"identities": identities, "grants": grants})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    identity = commands.add_parser("identity", help="Provision or disable an OIDC subject")
    identity_commands = identity.add_subparsers(dest="identity_command", required=True)
    provision = identity_commands.add_parser("provision")
    provision.add_argument("--issuer", required=True)
    provision.add_argument("--subject", required=True)
    provision.add_argument("--display-name")
    provision.set_defaults(func=provision_identity)
    disable = identity_commands.add_parser("disable")
    disable.add_argument("--operator-id", required=True)
    disable.set_defaults(func=disable_identity)

    grant = commands.add_parser("grant", help="Grant one resource/action for one location")
    grant.add_argument("--operator-id", required=True)
    grant.add_argument("--resource", required=True)
    grant.add_argument("--action", required=True)
    grant.add_argument("--location-id", required=True)
    grant.add_argument("--granted-by", required=True)
    grant.set_defaults(func=grant_scope)

    revoke = commands.add_parser("revoke-grant", help="Revoke one operator scope grant")
    revoke.add_argument("--grant-id", required=True)
    revoke.set_defaults(func=revoke_scope)

    listing = commands.add_parser("list", help="List operator identities and grants")
    listing.set_defaults(func=list_operators)
    args = parser.parse_args()
    run(args.func, args)


if __name__ == "__main__":
    main()
