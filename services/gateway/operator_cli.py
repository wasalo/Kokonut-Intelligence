"""Local database administration for explicitly provisioned OIDC operators."""

from __future__ import annotations

import argparse
import re
from urllib.parse import urlsplit
from uuid import UUID

from services.common.cli import get_connection, print_json, run
from services.gateway.farm_activity_roles import (
    FARM_ACTIVITY_ROLE_SCOPES,
    get_farm_activity_role_scopes,
)

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
                     updated_at = NOW()
               WHERE operator_identity.enabled = TRUE
               RETURNING id, issuer, subject, display_name, enabled""",
            {
                "issuer": args.issuer,
                "subject": subject,
                "display_name": args.display_name,
            },
        ).first()
        if row is None:
            raise ValueError(
                "operator identity is disabled; provisioning will not re-enable it"
            )
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


def bind_governance_party(args) -> None:
    """Explicitly bind an OIDC operator to an existing human party UUID."""
    operator_id = _uuid(args.operator_id, "operator-id")
    party_id = _uuid(args.party_id, "party-id")
    bound_by = args.bound_by.strip()
    reason = args.reason.strip()
    if not bound_by or not reason:
        raise ValueError("bound-by and reason are required")
    with get_connection() as conn:
        conn.execute("SET LOCAL ROLE kokonut_governance_identity_admin")
        row = conn.execute(
            """SELECT * FROM kokonut_security.bind_operator_governance_party(
                       :operator_id, :party_id, :bound_by, :reason
                   )""",
            {
                "operator_id": operator_id,
                "party_id": party_id,
                "bound_by": bound_by,
                "reason": reason,
            },
        ).first()
    if row is None:
        raise ValueError("governance person binding was not created")
    print_json(row)


def revoke_governance_party_binding(args) -> None:
    binding_id = _uuid(args.binding_id, "binding-id")
    revoked_by = args.revoked_by.strip()
    reason = args.reason.strip()
    if not revoked_by or not reason:
        raise ValueError("revoked-by and reason are required")
    with get_connection() as conn:
        conn.execute("SET LOCAL ROLE kokonut_governance_identity_admin")
        row = conn.execute(
            """SELECT * FROM kokonut_security.revoke_operator_governance_party_binding(
                       :binding_id, :revoked_by, :reason
                   )""",
            {
                "binding_id": binding_id,
                "revoked_by": revoked_by,
                "reason": reason,
            },
        ).first()
    if row is None:
        raise ValueError("active governance person binding was not found")
    print_json(row)


def list_governance_party_bindings(args) -> None:
    operator_id = _uuid(args.operator_id, "operator-id") if args.operator_id else None
    with get_connection() as conn:
        conn.execute("SET LOCAL ROLE kokonut_governance_identity_admin")
        rows = conn.execute(
            """SELECT * FROM kokonut_security.list_operator_governance_party_bindings(
                       :operator_id
                   )""",
            {"operator_id": operator_id},
        ).all()
    print_json(rows)


def grant_scope(args) -> None:
    if not _SLUG.fullmatch(args.resource) or not _SLUG.fullmatch(args.action):
        raise ValueError("resource and action must be lowercase identifiers without wildcards")
    operator_id = _uuid(args.operator_id, "operator-id")
    location_id = _uuid(args.location_id, "location-id")
    if not args.granted_by.strip():
        raise ValueError("granted-by must identify the local operator")
    organization_id = (
        _uuid(args.organization_id, "organization-id") if args.organization_id else None
    )
    with get_connection() as conn:
        identity = conn.execute(
            """SELECT id FROM operator_identity
                WHERE id = :operator_id AND enabled = TRUE""",
            {"operator_id": operator_id},
        ).first()
        if identity is None:
            raise ValueError("enabled operator identity was not found")
        target = conn.execute(
            """SELECT loc.organization_id AS location_organization_id
                 FROM location AS loc
                WHERE loc.id = :location_id
                FOR SHARE""",
            {"location_id": location_id},
        ).first()
        if target is None:
            raise ValueError("location was not found")
        location_organization_id = (
            str(target["location_organization_id"])
            if target["location_organization_id"] is not None
            else None
        )
        owner = conn.execute(
            """SELECT organization_id
                 FROM location_tenant_owner_verification
                WHERE location_id = :location_id AND revoked_at IS NULL
                FOR SHARE""",
            {"location_id": location_id},
        ).first()
        verified_organization_id = str(owner["organization_id"]) if owner is not None else None
        if verified_organization_id is not None and verified_organization_id != location_organization_id:
            raise ValueError("location ownership verification is stale; resolve ownership before granting access")
        if organization_id is None:
            if verified_organization_id is not None:
                raise ValueError("verified tenant locations require --organization-id")
        else:
            if verified_organization_id is None:
                raise ValueError("tenant-qualified grants require a current verified location owner")
            membership = conn.execute(
                """SELECT 1
                     FROM operator_organization_membership AS membership
                     JOIN organization AS tenant ON tenant.id = membership.organization_id
                    WHERE membership.operator_id = :operator_id
                      AND membership.organization_id = :organization_id
                      AND membership.revoked_at IS NULL
                      AND tenant.status = 'active'
                    FOR SHARE OF membership, tenant""",
                {"operator_id": operator_id, "organization_id": organization_id},
            ).first()
            if membership is None:
                raise ValueError("operator must have active membership in the requested organization")
            owns_location = (
                verified_organization_id == organization_id
                and location_organization_id == organization_id
            )
            shared_location = conn.execute(
                """SELECT 1 FROM location_organization_share
                    WHERE location_id = :location_id
                      AND organization_id = :organization_id
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > NOW())
                    FOR SHARE""",
                {"location_id": location_id, "organization_id": organization_id},
            ).first()
            if not owns_location and shared_location is None:
                raise ValueError("organization needs a current verified owner or explicit location share")
        row = conn.execute(
            """INSERT INTO operator_scope_grant
                   (operator_id, resource, action, location_id, organization_id, granted_by)
               VALUES (:operator_id, :resource, :action, :location_id, :organization_id, :granted_by)
               ON CONFLICT (operator_id, resource, action, location_id)
                   WHERE revoked_at IS NULL DO NOTHING
               RETURNING id, operator_id, resource, action, location_id,
                         organization_id, granted_by""",
            {
                "operator_id": operator_id,
                "resource": args.resource,
                "action": args.action,
                "location_id": location_id,
                "organization_id": organization_id,
                "granted_by": args.granted_by.strip(),
            },
        ).first()
        if row is None:
            existing = conn.execute(
                """SELECT id, operator_id, resource, action, location_id,
                          organization_id, granted_by
                     FROM operator_scope_grant
                    WHERE operator_id = :operator_id AND resource = :resource
                      AND action = :action AND location_id = :location_id
                      AND revoked_at IS NULL
                    FOR UPDATE""",
                {
                    "operator_id": operator_id,
                    "resource": args.resource,
                    "action": args.action,
                    "location_id": location_id,
                },
            ).first()
            existing_organization_id = (
                str(existing["organization_id"])
                if existing is not None and existing["organization_id"] is not None
                else None
            )
            if existing is not None and existing_organization_id is None and organization_id is not None:
                row = conn.execute(
                    """UPDATE operator_scope_grant
                          SET organization_id = :organization_id
                        WHERE id = :grant_id AND organization_id IS NULL
                          AND revoked_at IS NULL
                        RETURNING id, operator_id, resource, action, location_id,
                                  organization_id, granted_by""",
                    {"organization_id": organization_id, "grant_id": existing["id"]},
                ).first()
                if row is None:
                    existing = conn.execute(
                        """SELECT id, operator_id, resource, action, location_id,
                                  organization_id, granted_by
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
                    if (
                        existing is None
                        or existing["organization_id"] is None
                        or str(existing["organization_id"]) != organization_id
                    ):
                        raise ValueError("an active scope grant exists under a different tenant")
                    row = existing
            elif existing is None:
                raise ValueError("an active scope grant could not be resolved")
            elif existing_organization_id != organization_id:
                raise ValueError("an active scope grant exists under a different tenant; revoke it first")
            else:
                row = existing
    print_json(row)


def grant_organization_membership(args) -> None:
    operator_id = _uuid(args.operator_id, "operator-id")
    organization_id = _uuid(args.organization_id, "organization-id")
    if not args.granted_by.strip():
        raise ValueError("granted-by must identify the local operator")
    with get_connection() as conn:
        identity = conn.execute(
            "SELECT id FROM operator_identity WHERE id = :operator_id AND enabled = TRUE FOR SHARE",
            {"operator_id": operator_id},
        ).first()
        organization = conn.execute(
            "SELECT id FROM organization WHERE id = :organization_id AND status = 'active' FOR SHARE",
            {"organization_id": organization_id},
        ).first()
        if identity is None or organization is None:
            raise ValueError("enabled operator and active organization are required")
        row = conn.execute(
            """INSERT INTO operator_organization_membership
                   (operator_id, organization_id, membership_role, granted_by)
               VALUES (:operator_id, :organization_id, :membership_role, :granted_by)
               ON CONFLICT (operator_id, organization_id)
                   WHERE revoked_at IS NULL DO NOTHING
               RETURNING id, operator_id, organization_id, membership_role,
                         granted_by, created_at, revoked_at""",
            {
                "operator_id": operator_id,
                "organization_id": organization_id,
                "membership_role": args.membership_role,
                "granted_by": args.granted_by.strip(),
            },
        ).first()
        if row is None:
            row = conn.execute(
                """SELECT id, operator_id, organization_id, membership_role,
                          granted_by, created_at, revoked_at
                     FROM operator_organization_membership
                    WHERE operator_id = :operator_id
                      AND organization_id = :organization_id
                      AND revoked_at IS NULL""",
                {"operator_id": operator_id, "organization_id": organization_id},
            ).first()
            if row is not None and row["membership_role"] != args.membership_role:
                raise ValueError(
                    "active membership has a different role; revoke it before changing the role"
                )
    print_json(row)


def revoke_organization_membership(args) -> None:
    membership_id = _uuid(args.membership_id, "membership-id")
    if not args.revoked_by.strip() or not args.reason.strip():
        raise ValueError("revoked-by and reason are required")
    with get_connection() as conn:
        row = conn.execute(
            """UPDATE operator_organization_membership
                  SET revoked_at = NOW(), revoked_by = :revoked_by,
                      revocation_reason = :reason
                WHERE id = :membership_id AND revoked_at IS NULL
                RETURNING id, operator_id, organization_id, revoked_at,
                          revoked_by, revocation_reason""",
            {
                "membership_id": membership_id,
                "revoked_by": args.revoked_by.strip(),
                "reason": args.reason.strip(),
            },
        ).first()
        if row is not None:
            conn.execute(
                """UPDATE operator_scope_grant
                      SET revoked_at = NOW(), revoked_by = :revoked_by,
                          revocation_reason = :reason
                    WHERE operator_id = :operator_id
                      AND organization_id = :organization_id
                      AND revoked_at IS NULL""",
                {
                    "operator_id": row["operator_id"],
                    "organization_id": row["organization_id"],
                    "revoked_by": args.revoked_by.strip(),
                    "reason": args.reason.strip(),
                },
            )
    if row is None:
        raise ValueError("active organization membership was not found")
    print_json(row)


def grant_location_share(args) -> None:
    location_id = _uuid(args.location_id, "location-id")
    organization_id = _uuid(args.organization_id, "organization-id")
    granted_by_operator_id = _uuid(args.granted_by_operator_id, "granted-by-operator-id")
    if not args.reason.strip():
        raise ValueError("reason is required")
    with get_connection() as conn:
        location = conn.execute(
            """SELECT loc.organization_id AS location_organization_id,
                      owner.organization_id AS verified_organization_id
                 FROM location AS loc
                 JOIN location_tenant_owner_verification AS owner
                   ON owner.location_id = loc.id AND owner.revoked_at IS NULL
                  AND owner.organization_id = loc.organization_id
                WHERE loc.id = :location_id
                FOR SHARE OF loc, owner""",
            {"location_id": location_id},
        ).first()
        if location is None:
            raise ValueError("location needs a current verified owner before it can be shared")
        owner_organization_id = str(location["verified_organization_id"])
        if owner_organization_id == organization_id:
            raise ValueError("the owner organization does not need a share grant")
        target_org = conn.execute(
            "SELECT id FROM organization WHERE id = :organization_id AND status = 'active' FOR SHARE",
            {"organization_id": organization_id},
        ).first()
        owner_admin = conn.execute(
            """SELECT 1
                 FROM operator_identity AS identity
                 JOIN operator_organization_membership AS membership
                   ON membership.operator_id = identity.id
                WHERE identity.id = :operator_id AND identity.enabled = TRUE
                  AND membership.organization_id = :organization_id
                  AND membership.membership_role = 'tenant_admin'
                  AND membership.revoked_at IS NULL
                FOR SHARE OF identity, membership""",
            {
                "operator_id": granted_by_operator_id,
                "organization_id": owner_organization_id,
            },
        ).first()
        if target_org is None or owner_admin is None:
            raise ValueError("active recipient organization and owner tenant administrator are required")
        row = conn.execute(
            """INSERT INTO location_organization_share
                   (location_id, organization_id, granted_by_operator_id, reason)
               VALUES (:location_id, :organization_id, :granted_by_operator_id, :reason)
               ON CONFLICT (location_id, organization_id)
                   WHERE revoked_at IS NULL DO NOTHING
               RETURNING id, location_id, organization_id, granted_by_operator_id,
                         reason, created_at, expires_at, revoked_at""",
            {
                "location_id": location_id,
                "organization_id": organization_id,
                "granted_by_operator_id": granted_by_operator_id,
                "reason": args.reason.strip(),
            },
        ).first()
        if row is None:
            row = conn.execute(
                """SELECT id, location_id, organization_id, granted_by_operator_id,
                          reason, created_at, expires_at, revoked_at
                     FROM location_organization_share
                    WHERE location_id = :location_id AND organization_id = :organization_id
                      AND revoked_at IS NULL""",
                {"location_id": location_id, "organization_id": organization_id},
            ).first()
    print_json(row)


def revoke_location_share(args) -> None:
    share_id = _uuid(args.share_id, "share-id")
    revoked_by_operator_id = _uuid(args.revoked_by_operator_id, "revoked-by-operator-id")
    if not args.reason.strip():
        raise ValueError("reason is required")
    with get_connection() as conn:
        share = conn.execute(
            """SELECT share.id AS share_id, share.location_id AS location_id,
                      share.organization_id AS organization_id,
                      owner.organization_id AS owner_organization_id
                 FROM location_organization_share AS share
                 JOIN location AS loc ON loc.id = share.location_id
                 JOIN location_tenant_owner_verification AS owner
                   ON owner.location_id = loc.id AND owner.revoked_at IS NULL
                  AND owner.organization_id = loc.organization_id
                WHERE share.id = :share_id AND share.revoked_at IS NULL
                FOR UPDATE OF share, loc, owner""",
            {"share_id": share_id},
        ).first()
        if share is None:
            raise ValueError("active verified location share was not found")
        owner_admin = conn.execute(
            """SELECT 1
                 FROM operator_identity AS identity
                 JOIN operator_organization_membership AS membership
                   ON membership.operator_id = identity.id
                WHERE identity.id = :operator_id AND identity.enabled = TRUE
                  AND membership.organization_id = :organization_id
                  AND membership.membership_role = 'tenant_admin'
                  AND membership.revoked_at IS NULL
                FOR SHARE OF identity, membership""",
            {
                "operator_id": revoked_by_operator_id,
                "organization_id": str(share["owner_organization_id"]),
            },
        ).first()
        if owner_admin is None:
            raise ValueError("an active owner tenant administrator is required")
        row = conn.execute(
            """UPDATE location_organization_share
                  SET revoked_at = NOW(), revoked_by_operator_id = :revoked_by_operator_id,
                      revocation_reason = :reason
                WHERE id = :share_id AND revoked_at IS NULL
                RETURNING id, location_id, organization_id, revoked_at,
                          revoked_by_operator_id, revocation_reason""",
            {
                "share_id": share_id,
                "revoked_by_operator_id": revoked_by_operator_id,
                "reason": args.reason.strip(),
            },
        ).first()
        conn.execute(
            """UPDATE operator_scope_grant
                  SET revoked_at = NOW(), revoked_by = :revoked_by,
                      revocation_reason = :reason
                WHERE location_id = :location_id
                  AND organization_id = :organization_id
                  AND revoked_at IS NULL""",
            {
                "location_id": share["location_id"],
                "organization_id": share["organization_id"],
                "revoked_by": revoked_by_operator_id,
                "reason": args.reason.strip(),
            },
        )
    print_json(row)


def revoke_scope(args) -> None:
    grant_id = _uuid(args.grant_id, "grant-id")
    revoked_by = args.revoked_by.strip()
    reason = args.reason.strip()
    if not revoked_by or not reason:
        raise ValueError("revoked-by and reason are required")
    if len(revoked_by) > 200 or len(reason) > 2000:
        raise ValueError("revoked-by or reason exceeds the supported length")
    with get_connection() as conn:
        row = conn.execute(
            """UPDATE operator_scope_grant
                  SET revoked_at = NOW(), revoked_by = :revoked_by,
                      revocation_reason = :reason
                 WHERE id = :grant_id AND revoked_at IS NULL
               RETURNING id, operator_id, resource, action, location_id,
                         revoked_at, revoked_by, revocation_reason""",
            {"grant_id": grant_id, "revoked_by": revoked_by, "reason": reason},
        ).first()
    if row is None:
        raise ValueError("active scope grant was not found")
    print_json(row)


def grant_farm_activity_role(args) -> None:
    """Expand a named legacy role to ordinary, tenant-qualified scope grants."""
    operator_id = _uuid(args.operator_id, "operator-id")
    location_id = _uuid(args.location_id, "location-id")
    organization_id = _uuid(args.organization_id, "organization-id")
    scopes = get_farm_activity_role_scopes(args.role)
    if not args.granted_by.strip():
        raise ValueError("granted-by must identify the local operator")

    with get_connection() as conn:
        identity = conn.execute(
            "SELECT id FROM operator_identity WHERE id = :operator_id AND enabled = TRUE FOR SHARE",
            {"operator_id": operator_id},
        ).first()
        if identity is None:
            raise ValueError("enabled operator identity was not found")

        target = conn.execute(
            """SELECT organization_id AS location_organization_id
                 FROM location WHERE id = :location_id FOR SHARE""",
            {"location_id": location_id},
        ).first()
        if target is None:
            raise ValueError("location was not found")
        location_organization_id = (
            str(target["location_organization_id"])
            if target["location_organization_id"] is not None
            else None
        )
        owner = conn.execute(
            """SELECT organization_id
                 FROM location_tenant_owner_verification
                WHERE location_id = :location_id AND revoked_at IS NULL
                FOR SHARE""",
            {"location_id": location_id},
        ).first()
        verified_organization_id = str(owner["organization_id"]) if owner else None
        if verified_organization_id is None or verified_organization_id != location_organization_id:
            raise ValueError("location must have a current verified tenant owner")

        membership = conn.execute(
            """SELECT 1
                 FROM operator_organization_membership AS membership
                 JOIN organization AS tenant ON tenant.id = membership.organization_id
                WHERE membership.operator_id = :operator_id
                  AND membership.organization_id = :organization_id
                  AND membership.revoked_at IS NULL
                  AND tenant.status = 'active'
                FOR SHARE OF membership, tenant""",
            {"operator_id": operator_id, "organization_id": organization_id},
        ).first()
        if membership is None:
            raise ValueError("operator must have active membership in the requested organization")

        owns_location = verified_organization_id == organization_id
        shared_location = conn.execute(
            """SELECT 1 FROM location_organization_share
                WHERE location_id = :location_id
                  AND organization_id = :organization_id
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                FOR SHARE""",
            {"location_id": location_id, "organization_id": organization_id},
        ).first()
        if not owns_location and shared_location is None:
            raise ValueError("organization needs the verified owner or an active location share")

        granted = []
        for resource, action in scopes:
            parameters = {
                "operator_id": operator_id,
                "resource": resource,
                "action": action,
                "location_id": location_id,
                "organization_id": organization_id,
                "granted_by": args.granted_by.strip(),
            }
            row = conn.execute(
                """INSERT INTO operator_scope_grant
                       (operator_id, resource, action, location_id, organization_id, granted_by)
                   VALUES (:operator_id, :resource, :action, :location_id,
                           :organization_id, :granted_by)
                   ON CONFLICT (operator_id, resource, action, location_id)
                       WHERE revoked_at IS NULL DO NOTHING
                   RETURNING id, operator_id, resource, action, location_id,
                             organization_id, granted_by""",
                parameters,
            ).first()
            if row is None:
                existing = conn.execute(
                    """SELECT id, operator_id, resource, action, location_id,
                              organization_id, granted_by
                         FROM operator_scope_grant
                        WHERE operator_id = :operator_id AND resource = :resource
                          AND action = :action AND location_id = :location_id
                          AND revoked_at IS NULL
                        FOR UPDATE""",
                    parameters,
                ).first()
                if existing is None:
                    raise ValueError("an active role grant could not be resolved")
                existing_organization_id = (
                    str(existing["organization_id"])
                    if existing["organization_id"] is not None
                    else None
                )
                if existing_organization_id is None:
                    row = conn.execute(
                        """UPDATE operator_scope_grant
                              SET organization_id = :organization_id
                            WHERE id = :grant_id AND organization_id IS NULL
                              AND revoked_at IS NULL
                            RETURNING id, operator_id, resource, action, location_id,
                                      organization_id, granted_by""",
                        {"organization_id": organization_id, "grant_id": existing["id"]},
                    ).first()
                    if row is None:
                        raise ValueError("an existing role grant changed during provisioning")
                elif existing_organization_id != organization_id:
                    raise ValueError("an active scope grant exists under a different tenant; revoke it first")
                else:
                    row = existing
            granted.append(row)

    print_json({"role": args.role, "grants": granted})


def list_farm_activity_role_templates(_args) -> None:
    print_json(
        {
            "roles": {
                role: [
                    {"resource": resource, "action": action}
                    for resource, action in get_farm_activity_role_scopes(role)
                ]
                for role in FARM_ACTIVITY_ROLE_SCOPES
            }
        }
    )


def request_location_tenant_transfer(args) -> None:
    location_id = _uuid(args.location_id, "location-id")
    target_organization_id = _uuid(args.target_organization_id, "target-organization-id")
    requested_by_operator_id = _uuid(args.requested_by_operator_id, "requested-by-operator-id")
    request_reference = args.request_reference.strip()
    reason = args.reason.strip()
    if not request_reference or not reason:
        raise ValueError("request-reference and reason are required")
    with get_connection() as conn:
        transfer_id = conn.execute(
            """SELECT request_location_tenant_transfer(
                          :location_id, :target_organization_id,
                          :requested_by_operator_id, :request_reference, :reason
                      ) AS id""",
            {
                "location_id": location_id,
                "target_organization_id": target_organization_id,
                "requested_by_operator_id": requested_by_operator_id,
                "request_reference": request_reference,
                "reason": reason,
            },
        ).first()["id"]
        row = conn.execute(
            """SELECT id, location_id, source_owner_verification_id,
                      source_organization_id, target_organization_id,
                      requested_by_operator_id, request_reference, request_reason,
                      requested_at, status
                 FROM location_tenant_transfer WHERE id = :transfer_id""",
            {"transfer_id": transfer_id},
        ).first()
    print_json(row)


def accept_location_tenant_transfer(args) -> None:
    transfer_id = _uuid(args.transfer_id, "transfer-id")
    accepting_operator_id = _uuid(args.accepting_operator_id, "accepting-operator-id")
    acceptance_reference = args.acceptance_reference.strip()
    if not acceptance_reference:
        raise ValueError("acceptance-reference is required")
    with get_connection() as conn:
        conn.execute(
            """SELECT accept_location_tenant_transfer(
                          :transfer_id, :accepting_operator_id, :acceptance_reference
                      )""",
            {
                "transfer_id": transfer_id,
                "accepting_operator_id": accepting_operator_id,
                "acceptance_reference": acceptance_reference,
            },
        )
        row = conn.execute(
            """SELECT id, location_id, source_organization_id, target_organization_id,
                      requested_by_operator_id, request_reference, requested_at,
                      accepted_by_operator_id, acceptance_reference, accepted_at,
                      resulting_owner_verification_id, revoked_share_ids,
                      revoked_scope_grant_ids, status
                 FROM location_tenant_transfer WHERE id = :transfer_id""",
            {"transfer_id": transfer_id},
        ).first()
    print_json(row)


def cancel_location_tenant_transfer(args) -> None:
    transfer_id = _uuid(args.transfer_id, "transfer-id")
    cancelling_operator_id = _uuid(args.cancelling_operator_id, "cancelling-operator-id")
    reason = args.reason.strip()
    if not reason:
        raise ValueError("reason is required")
    with get_connection() as conn:
        conn.execute(
            """SELECT cancel_location_tenant_transfer(
                          :transfer_id, :cancelling_operator_id, :reason
                      )""",
            {
                "transfer_id": transfer_id,
                "cancelling_operator_id": cancelling_operator_id,
                "reason": reason,
            },
        )
        row = conn.execute(
            """SELECT id, location_id, source_organization_id, target_organization_id,
                      requested_by_operator_id, request_reference, requested_at,
                      cancelled_by_operator_id, cancellation_reason, cancelled_at, status
                 FROM location_tenant_transfer WHERE id = :transfer_id""",
            {"transfer_id": transfer_id},
        ).first()
    print_json(row)


def list_operators(args) -> None:
    with get_connection() as conn:
        identities = conn.execute(
            """SELECT id, issuer, subject, display_name, email, enabled, created_at
                 FROM operator_identity ORDER BY created_at, id"""
        ).all()
        grants = conn.execute(
            """SELECT id, operator_id, resource, action, location_id, organization_id, granted_by,
                      created_at, revoked_at
                 FROM operator_scope_grant ORDER BY created_at, id"""
        ).all()
        memberships = conn.execute(
            """SELECT id, operator_id, organization_id, membership_role, granted_by,
                      created_at, revoked_at, revoked_by, revocation_reason
                 FROM operator_organization_membership
                ORDER BY created_at, id"""
        ).all()
        shares = conn.execute(
            """SELECT id, location_id, organization_id, granted_by_operator_id, reason,
                      created_at, expires_at, revoked_at, revoked_by_operator_id,
                      revocation_reason
                 FROM location_organization_share ORDER BY created_at, id"""
        ).all()
        transfers = conn.execute(
            """SELECT id, location_id, source_organization_id, target_organization_id,
                      requested_by_operator_id, request_reference, request_reason,
                      requested_at, status, accepted_by_operator_id, acceptance_reference,
                      accepted_at, resulting_owner_verification_id, revoked_share_ids,
                      revoked_scope_grant_ids, cancelled_by_operator_id,
                      cancellation_reason, cancelled_at
                 FROM location_tenant_transfer ORDER BY requested_at, id"""
        ).all()
    print_json({
        "identities": identities,
        "grants": grants,
        "memberships": memberships,
        "shares": shares,
        "tenant_transfers": transfers,
    })


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

    party = identity_commands.add_parser(
        "party", help="Manage an explicit OIDC-operator to human-party binding"
    )
    party_commands = party.add_subparsers(dest="party_command", required=True)
    party_bind = party_commands.add_parser("bind")
    party_bind.add_argument("--operator-id", required=True)
    party_bind.add_argument("--party-id", required=True)
    party_bind.add_argument("--bound-by", required=True)
    party_bind.add_argument("--reason", required=True)
    party_bind.set_defaults(func=bind_governance_party)
    party_revoke = party_commands.add_parser("revoke")
    party_revoke.add_argument("--binding-id", required=True)
    party_revoke.add_argument("--revoked-by", required=True)
    party_revoke.add_argument("--reason", required=True)
    party_revoke.set_defaults(func=revoke_governance_party_binding)
    party_list = party_commands.add_parser("list")
    party_list.add_argument("--operator-id")
    party_list.set_defaults(func=list_governance_party_bindings)

    grant = commands.add_parser("grant", help="Grant one resource/action for one location")
    grant.add_argument("--operator-id", required=True)
    grant.add_argument("--resource", required=True)
    grant.add_argument("--action", required=True)
    grant.add_argument("--location-id", required=True)
    grant.add_argument(
        "--organization-id",
        help="Tenant organization; required for locations with verified ownership or sharing",
    )
    grant.add_argument("--granted-by", required=True)
    grant.set_defaults(func=grant_scope)

    revoke = commands.add_parser("revoke-grant", help="Revoke one operator scope grant")
    revoke.add_argument("--grant-id", required=True)
    revoke.add_argument("--revoked-by", required=True, help="Local operator performing the revocation")
    revoke.add_argument("--reason", required=True, help="Reason for revoking the grant")
    revoke.set_defaults(func=revoke_scope)

    role = commands.add_parser("farm-activity-role", help="Provision a legacy farm-activity role as scoped grants")
    role_commands = role.add_subparsers(dest="role_command", required=True)
    role_templates = role_commands.add_parser("templates", help="List role-to-scope mappings")
    role_templates.set_defaults(func=list_farm_activity_role_templates)
    role_grant = role_commands.add_parser("grant", help="Grant one role template at one tenant location")
    role_grant.add_argument("--role", choices=tuple(FARM_ACTIVITY_ROLE_SCOPES), required=True)
    role_grant.add_argument("--operator-id", required=True)
    role_grant.add_argument("--organization-id", required=True)
    role_grant.add_argument("--location-id", required=True)
    role_grant.add_argument("--granted-by", required=True)
    role_grant.set_defaults(func=grant_farm_activity_role)

    membership = commands.add_parser("organization-membership", help="Manage an operator's tenant affiliation")
    membership_commands = membership.add_subparsers(dest="membership_command", required=True)
    membership_grant = membership_commands.add_parser("grant")
    membership_grant.add_argument("--operator-id", required=True)
    membership_grant.add_argument("--organization-id", required=True)
    membership_grant.add_argument("--membership-role", choices=("operator", "tenant_admin"), default="operator")
    membership_grant.add_argument("--granted-by", required=True)
    membership_grant.set_defaults(func=grant_organization_membership)
    membership_revoke = membership_commands.add_parser("revoke")
    membership_revoke.add_argument("--membership-id", required=True)
    membership_revoke.add_argument("--revoked-by", required=True)
    membership_revoke.add_argument("--reason", required=True)
    membership_revoke.set_defaults(func=revoke_organization_membership)

    share = commands.add_parser("location-share", help="Manage explicit organization access to a location")
    share_commands = share.add_subparsers(dest="share_command", required=True)
    share_grant = share_commands.add_parser("grant")
    share_grant.add_argument("--location-id", required=True)
    share_grant.add_argument("--organization-id", required=True)
    share_grant.add_argument("--granted-by-operator-id", required=True)
    share_grant.add_argument("--reason", required=True)
    share_grant.set_defaults(func=grant_location_share)
    share_revoke = share_commands.add_parser("revoke")
    share_revoke.add_argument("--share-id", required=True)
    share_revoke.add_argument("--revoked-by-operator-id", required=True)
    share_revoke.add_argument("--reason", required=True)
    share_revoke.set_defaults(func=revoke_location_share)

    transfer = commands.add_parser(
        "tenant-transfer", help="Request, accept, or cancel an audited location tenant-owner transfer"
    )
    transfer_commands = transfer.add_subparsers(dest="transfer_command", required=True)
    transfer_request = transfer_commands.add_parser("request")
    transfer_request.add_argument("--location-id", required=True)
    transfer_request.add_argument("--target-organization-id", required=True)
    transfer_request.add_argument("--requested-by-operator-id", required=True)
    transfer_request.add_argument("--request-reference", required=True)
    transfer_request.add_argument("--reason", required=True)
    transfer_request.set_defaults(func=request_location_tenant_transfer)
    transfer_accept = transfer_commands.add_parser("accept")
    transfer_accept.add_argument("--transfer-id", required=True)
    transfer_accept.add_argument("--accepting-operator-id", required=True)
    transfer_accept.add_argument("--acceptance-reference", required=True)
    transfer_accept.set_defaults(func=accept_location_tenant_transfer)
    transfer_cancel = transfer_commands.add_parser("cancel")
    transfer_cancel.add_argument("--transfer-id", required=True)
    transfer_cancel.add_argument("--cancelling-operator-id", required=True)
    transfer_cancel.add_argument("--reason", required=True)
    transfer_cancel.set_defaults(func=cancel_location_tenant_transfer)

    listing = commands.add_parser("list", help="List operator identities and grants")
    listing.set_defaults(func=list_operators)
    args = parser.parse_args()
    run(args.func, args)


if __name__ == "__main__":
    main()
