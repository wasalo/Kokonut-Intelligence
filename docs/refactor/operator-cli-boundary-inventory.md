# Operator CLI boundary inventory

Status: source-classified; database-principal and owner acceptance remain open.

This inventory describes `services/gateway/operator_cli.py`, also mounted as
`python3 -m services.cli operator`. It is a local database-administration CLI.
It does not authenticate an OIDC browser session or derive the supplied actor
arguments from one. A value such as `--granted-by`, `--revoked-by`, or
`--requested-by-operator-id` is authoritative only where the command or its
database function independently verifies the referenced identity and scope.

## Connection and principal

The CLI uses `services.common.cli.get_connection()`, which delegates to
`services.common.database.get_connection()` and then `get_db()`. The connection
uses the shared `PG_USER`/`PG_PASSWORD` configuration; `PG_USER` defaults to
`kokonut`. There is no operator-specific CLI login or per-command session check.
The `kokonut_operator_auth` login is a separate Gateway authentication
credential for bounded operator-session functions, not the principal used by
this CLI. The current candidate still uses the `kokonut` superuser, and the
runtime-role policy grants broad DML on existing application tables. Therefore
the CLI must be treated as a trusted local DBA/break-glass surface; its
application-level checks do not constrain a database principal with broader
rights.

## Command behavior

| Command | Checks performed by source or database | Actor/audit behavior | Remaining boundary |
| --- | --- | --- | --- |
| `identity provision` | Requires HTTPS issuer and a non-empty, bounded subject. Inserts a new enabled identity. An existing enabled identity may have its display name refreshed. A matching disabled identity now fails closed. | No actor or reason is stored. Provisioning does not auto-create grants. | Database-login trust is the only caller boundary. There is no explicit reactivation command. |
| `identity disable` | Sets `operator_identity.enabled = false` and revokes active sessions in one transaction. | No disabling actor or reason is stored. | Local database-login trust; review the missing durable actor/reason record before using as an operational workflow. |
| `identity party bind/revoke/list` | Uses `SET LOCAL ROLE kokonut_governance_identity_admin` and bounded `kokonut_security` functions. Listing can be narrowed to one operator. | Bind/revoke require actor and reason, persisted by the function. | The database role/function boundary is verified separately; the actor text itself is attribution, not an OIDC session. |
| `grant` | Validates resource/action identifiers, enabled target identity, location, current owner verification, target membership in the selected organization, and owner-or-active-share scope before upsert. | `--granted-by` is free text and is not checked against an identity or tenant-admin membership. | Trusted local DBA caller; do not treat the grantor string as proof of approval. |
| `farm-activity-role grant` | Validates enabled target, current verified location owner, target membership, and owner-or-active-share scope; expands the fixed role catalogue in one transaction. | `--granted-by` is free text and is not verified. | Same local DBA boundary; no authenticated grantor check. |
| `organization-membership grant` | Requires an enabled target identity and active organization; prevents a conflicting active role from being silently changed. | `--granted-by` is free text and is not verified. | Only the local database principal authorizes the membership grant. |
| `organization-membership revoke` | Revokes the membership and every active scope grant for the same operator and organization in one transaction. | Requires non-blank actor/reason and records both on membership and cascaded grants. The actor text is not authenticated. | Local database-login trust; reason lengths are not bounded in the CLI. |
| `location-share grant/revoke` | Requires a current verified owner and an enabled `tenant_admin` identity from that owner organization. Grant also requires an active recipient organization. Revocation cascades to that recipient's location grants. | Uses the verified operator UUID and records a reason; cascading scope grants receive the same actor/reason. | Source verifies the referenced identity, but CLI invocation still relies on trusted database access; live workflow acceptance remains separate. |
| `tenant-transfer request/accept/cancel` | Calls migration 390 functions. Request requires a current verified source owner and enabled source tenant admin. Acceptance requires a pending request, a different operator, unchanged owner/relationships, still-active source approval, and enabled target tenant admin; the ownership/share/grant transition is atomic. Cancellation requires an enabled source tenant admin. | Operator UUIDs, references, and reasons are persisted by the functions. | These are explicit local DBA invocations of database-enforced rules, not browser/session authentication. Disposable migration acceptance does not establish production operator access. |
| `list` | Reads all identities, grants, memberships, shares, and transfers without filters or pagination. It does not read operator sessions. | Read-only; no actor recorded. | Output includes issuer/subject/email and access history across organizations; restrict it to the trusted local DBA surface. |
| `farm-activity-role templates` | Renders the source-controlled static role/scope registry without connecting to PostgreSQL. | No actor or mutation. | No database authorization question for this offline catalogue path. |

## Evidence and limits

The CAP-039 offline selection compares standalone and unified CLI output for
operator identity provisioning, operator list, and scope-grant revocation using
fake connections. Focused mocked checks cover disabled-identity reactivation
and revocation audit fields. These tests verify parsing, SQL construction,
synthetic output, and connection cleanup; they do not prove PostgreSQL
authorization, an authenticated grantor, or production principal separation.
Migration 390's request, acceptance, and cancellation functions have separate
disposable PostgreSQL checks.

Before calling the operator boundary accepted, the repository owner must select
the intended administration model and confirm which database principal may run
these commands. The code evidence cannot decide whether identity provisioning,
identity disablement, direct grant creation, and membership administration
remain break-glass DBA actions or move behind authenticated Gateway workflows.
It also cannot decide whether the global list should remain available to that
operator or receive pagination/redaction. Keep MAN-CAP-039 open until those
decisions and the selected principal's database boundary are verified.

## Source references

- [Operator CLI](../../services/gateway/operator_cli.py)
- [Unified CLI registration](../../services/cli.py)
- [Database connection configuration](../../services/common/database.py)
- [Operator identity and session schema](../../schemas/postgres/380_operator_identity_sessions.sql)
- [Tenant-aware grants](../../schemas/postgres/388_tenant_aware_operator_grants.sql)
- [Audited owner transfers](../../schemas/postgres/390_audited_location_tenant_transfers.sql)
- [Runtime-role policy](runtime-role-policy.md)
- [Offline CLI contract and evidence](unified-cli-kernel-contract.md)
