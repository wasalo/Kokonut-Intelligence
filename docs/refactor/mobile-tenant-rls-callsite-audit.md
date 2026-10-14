# Field Collector tenant and RLS call-site audit

Updated: 14 October 2026

## Finding

Migration 391 pins newly issued enrollment codes and registered devices to the
verified current location owner and rejects later binding changes. Migration
392 moves bearer-token resolution and one-time code redemption behind narrow
functions owned by dedicated non-login, non-bypass roles. Migration 393 signs
mobile-device tenant context with a database-private HMAC key. Migration 394
adds signed OIDC operator context after validating the active session,
tenant-qualified grant, membership, and current owner/share. Both proofs bind
to the current PostgreSQL backend and transaction; the RLS accessor verifies
the signature instead of trusting caller-set labels. Network-isolated
PostgreSQL 16 acceptance applied and replayed migrations 391–395, forced RLS
in disposable databases, and passed mobile credential/context plus operator
owner/share, denial, lock, cleanup, and session-role checks. Migrations 392–395
have not been applied to the candidate, and none enables application-table
RLS. Migration 395 removes runtime-role access to `operator_session` and gives
OIDC a separate auth login for bounded session functions. Runtime provisioning
now limits `mobile_device` and `mobile_device_enrollment` to explicit column
grants and denies reads of `device_token_hash`, `push_token`, and `code_hash`.
The shared runtime identity can still issue enrollment rows and clear a device
token during revocation; DML on other public tables remains broad. Those writes
and other application roles/callers remain to be bounded.
Gateway API-key context, legacy transport helpers, the preflight CLI, worker
jobs, and unverified Directus consumers also need explicit database access
designs. Do not enable RLS until those paths and their roles are closed.

## Access-path inventory

| Path | Current scope enforcement | RLS readiness / required work |
| --- | --- | --- |
| Device-token resolution: [`_device_for_token`](../../services/mobile/api.py#L353) | Hashes the presented token and calls `kokonut_security.resolve_mobile_device_token`; the function returns only device/user/location identity and whether the stored owner binding is current. It does not return the hash or collection data. | Isolated PostgreSQL acceptance passes for current, legacy-unbound, transferred-owner, and unknown tokens. Through the provisioned runtime login, the bounded resolver succeeds while direct SELECT of `device_token_hash` and `push_token`, hash predicates, and `SELECT *` are denied. A separate bounded device-revocation function and HTTP-under-runtime acceptance remain open. |
| One-time enrollment redemption: [`register_device`](../../services/mobile/api.py#L834) | Calls `kokonut_security.redeem_mobile_enrollment`, which locks the one-time enrollment, share-locks current owner rows, inserts one owner-bound device, and consumes the code atomically. The function rejects invalid arguments, expiry, stale ownership, and device-ID conflicts without consuming the code. | Isolated PostgreSQL acceptance passes replay, conflict, success/reuse, expiry, owner-transfer, and concurrent redemption checks; two competing requests created exactly one device and consumed the code once. Through the provisioned runtime login, redemption succeeds while direct SELECT of `code_hash` and `SELECT *` are denied. Enrollment issue/revoke SQL remains column-scoped. Migrations 392–395 are not yet on the candidate. Repeat this race under the final runtime database role/RLS contract. |
| Device-scoped forms, sync, status, and media-policy reads | After token resolution, these handlers call [`set_mobile_device_tenant_context`](../../services/common/tenant_context.py#L90) on the same connection before protected location/data queries. PostgreSQL validates the token hash and current owner, then signs backend/transaction-bound context; policies must use `kokonut_security.current_tenant_context()`, not the diagnostic GUC labels. | Forced-RLS disposable acceptance passes valid mobile scope, cross-tenant filtering, forged/tampered context denial, invalid-token clearing, and transaction reset. Migrations 392–393 are not yet on the candidate. Review every SQL statement and keep context plus data work in the same transaction. Media object storage remains a separate provider boundary. |
| OIDC operator enrollment/revocation: [`_create_enrollment`](../../services/mobile/api.py#L762), `_revoke_enrollment`, `_revoke_device` | Middleware binds the authenticated opaque session hash in request-local context. The service passes it to migration 394's definer function, which validates current session/identity, tenant-qualified grants, membership, owner/share, and all additional scopes, locks the rows, and signs tenant context. Migration 395 moves session creation, lookup, and revocation to the dedicated operator-auth connection; the application role cannot read session hashes. | Migrations 394–395 passed forced-RLS disposable acceptance for owner/shared grants, stale/legacy/cross-tenant denial, cleanup, share revocation, scope-revocation locking, direct runtime-role denial, and bounded session lifecycle. Other runtime data access and non-OIDC paths still need the final role and context contract before RLS. |
| Capability/API-key enrollment and revocation: [`router.py`](../../services/gateway/router.py#L58) and [`_create_enrollment`](../../services/mobile/api.py#L762) | Gateway middleware authorizes the exact `mobile_device` action/location and records an internal request marker. The same write transaction validates and share-locks the current verified owner, sets `actor_type=gateway`, and performs the enrollment/revocation. Missing marker, stale/missing owner, or failed context is denied before the write. | The application source path is closed and focused route/helper checks pass. Still not ready for RLS: the database custom setting is forgeable by any role with arbitrary SQL. The Gateway API-key/capability grant is not independently verified by PostgreSQL; establish a constrained database role or a database-verified capability before claiming a database isolation boundary. |
| Legacy analytics transport CLI: [`mobile_offline.py`](../../services/analytics/mobile_offline.py) | Direct registration now fails closed. Device listing, collection queue/pending reads, batch sync, conflict resolution, and global sync statistics still use direct SQL without tenant context. | Not ready for RLS. Keep it behind a restricted maintenance role or migrate/disable each command; transport-only status is not a substitute for tenant authorization. |
| Tenant preflight: [`collect_inventory`](../../services/mobile/tenant_preflight.py#L557) | Runs a read-only repeatable-read aggregate and emits opaque references/counts; it deliberately examines ownership and grants across locations. It no longer reads mobile credential columns and uses active/revoked state for device counts. | Give it an explicit owner/preflight database role and document who may invoke it. Do not run the aggregate with the ordinary app role once RLS is enabled. |
| Directus and database views | The archived Directus runtime identity and effective grants have not been verified; OFU-09 tracks the required isolated runtime and fixture. Migration 139 also defines legacy mobile sync/device views. | Not ready. Inspect role grants, view ownership/invoker behavior, hooks, saved queries, and all consumers in a matching isolated Directus runtime before choosing RLS policies or retirement scope. |
| Recovery fixtures and ordered migrations | Recovery fixture SQL inserts devices into isolated scratch databases. Migration 391 adds owner-binding triggers and indexes; 392 adds credential functions; 393 signs mobile context; 394 signs OIDC operator context and adds dormant definer-role RLS policies; 395 isolates operator sessions behind bounded functions and a dedicated auth login. None enables application-table RLS. | Migration 391 is applied on the candidate; 392–395 passed isolated PostgreSQL 16 acceptance but have not been rolled out. Keep fixtures and migration execution on explicit maintenance credentials. Candidate 391 evidence: [rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json). Migrations 392–393 evidence: [mobile acceptance](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json); migration 394 evidence: [operator acceptance](builds/2026-10-14-recovery/operator-tenant-context-disposable.json); migration 395 evidence: [session-role acceptance](builds/2026-10-14-recovery/operator-session-role-disposable.json). |

## Context trust boundary

The mobile-device setter verifies the presented token hash and current owner;
the OIDC operator setter verifies the session hash, tenant-qualified grants,
membership, and owner/share state. Both sign with the private database key,
and the accessor accepts only a signature bound to the current backend and
transaction. The key is unreadable by the ordinary role; caller-set
tenant/location/actor labels do not create a valid proof. Migration 395 removes
direct runtime access to session hashes and limits session operations to a
separate auth login with three bounded functions. Runtime provisioning removes
table-wide grants from mobile device/enrollment rows and prevents reading
device-token, push, and enrollment-code hashes. The shared runtime identity can
still issue enrollments and revoke devices, and its DML on other public tables
is broad. Gateway API-key context remains unsigned:
the helper carries a request identity already authorized by
middleware and independently verifies the current location owner, but
PostgreSQL does not verify the Gateway grant. Resolve these database role and
credential boundaries before enabling RLS. See PostgreSQL’s
[custom options](https://www.postgresql.org/docs/current/runtime-config-custom.html)
and [configuration-setting functions](https://www.postgresql.org/docs/current/config-setting.html).

## Required sequence before RLS

1. Inventory every table, view, trigger, worker, CLI, API-key route, OIDC route,
   Directus role/hook, and maintenance command that reads or writes the tenant
   tables. Record the database role and whether it bypasses RLS.
2. Close the token and enrollment credential lookup paths without weakening
   token hashing, one-time use, owner-transfer serialization, or revocation.
   Migrations 392–393 implement bounded credential paths and signed mobile
   context, passing isolated PostgreSQL forced-RLS acceptance. Runtime-role
   provisioning now denies direct reads of token, push, and enrollment hashes
   and applies declared mobile-table column grants. Candidate rollout, real
   HTTP-under-runtime checks, and a bounded device-revocation function remain
   open.
3. Keep Gateway capability/API-key mutation context in the same transaction
   and validate it under forced RLS with the final role model. Migration 394
   adds database-verified OIDC context. Migration 395 moves session creation,
   lookup, and revocation to a separate auth role while removing runtime access
   to session hashes. Mobile and operator context cleanup is verified at
   transaction end.
4. Separate app, migration, backup, Directus, preflight, and recovery-fixture
   database roles. Verify least privilege and view semantics on PostgreSQL 16.
5. In disposable PostgreSQL, test owner and explicitly shared access; wrong or
   stale owner; legacy NULL binding; absent and forged context; expired, used,
   revoked, and concurrently redeemed enrollment codes; owner transfer during
   requests; API-key/OIDC denial; view access; rollback; and transaction reset.
   Migrations 392–395 cover concurrent single-use redemption, expiry, owner
   transfer, mobile and OIDC signed contexts, and the isolated operator-session
   API under disposable forced RLS. Repeat all checks under the final runtime
   role and add Gateway, view, worker, and legacy CLI cases.
6. Only then prepare a separately approved candidate migration with an
   encrypted checkpoint and a verified restore path. Keep RLS disabled if any
   access path or consumer remains unknown.

This audit combines source review, isolated migration-392/393/394/395
acceptance, and a PostgreSQL 16 runtime-role credential-grant check. It does
not claim Directus parity, worker isolation, a database-verified Gateway
capability, a final app-table role allowlist, candidate rollout of migrations
392–395, database-role hardening across consumers, an RLS migration, or live
candidate RLS acceptance. See [runtime mobile role evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json).
