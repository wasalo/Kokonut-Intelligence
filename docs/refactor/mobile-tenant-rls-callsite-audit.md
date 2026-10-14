# Field Collector tenant and RLS call-site audit

Updated: 14 October 2026

## Finding

Migration 391 pins newly issued enrollment codes and registered devices to the
verified current location owner and rejects later binding changes. The local
migration 392 source moves bearer-token resolution and one-time code redemption
behind narrow functions owned by a dedicated non-login, non-bypass role. A
network-isolated PostgreSQL 16 acceptance passed migration replay, least-
privilege lookup, registration, expiry, conflict, and owner-transfer checks.
Migration 392 has not been applied to the candidate. Both migrations leave
row-level security disabled. Credential resolution is now closed in the
first-party source path; legacy transport helpers, the preflight CLI, and
unverified Directus consumers still need explicit database access designs. Do
not enable RLS until those paths and their database roles are closed.

## Access-path inventory

| Path | Current scope enforcement | RLS readiness / required work |
| --- | --- | --- |
| Device-token resolution: [`_device_for_token`](../../services/mobile/api.py#L353) | Hashes the presented token and calls `kokonut_security.resolve_mobile_device_token`; the function returns only device/user/location identity and whether the stored owner binding is current. It does not return the hash or collection data. | Isolated PostgreSQL acceptance passes for current, legacy-unbound, transferred-owner, and unknown tokens. Migration 392 is not yet on the candidate; verify the deployed app-role grant and retain this bounded return contract before RLS. |
| One-time enrollment redemption: [`register_device`](../../services/mobile/api.py#L834) | Calls `kokonut_security.redeem_mobile_enrollment`, which locks the one-time enrollment, share-locks current owner rows, inserts one owner-bound device, and consumes the code atomically. The function rejects invalid arguments, expiry, stale ownership, and device-ID conflicts without consuming the code. | Isolated PostgreSQL acceptance passes replay, conflict, success/reuse, expiry, owner-transfer, and concurrent redemption checks; two competing requests created exactly one device and consumed the code once. Migration 392 is not yet on the candidate. Repeat this race under the final runtime database role/RLS contract. |
| Device-scoped forms, sync, status, and media-policy reads | After token resolution, these handlers call [`set_mobile_device_tenant_context`](../../services/common/tenant_context.py#L90) on the same connection before protected location/data queries. It validates the active device against the current verified owner and uses transaction-local context. | The protected-query pattern is reusable after token-resolution closure. Review every SQL statement and keep context plus data work in the same transaction. Media object storage remains a separate provider boundary. |
| OIDC operator enrollment/revocation: [`_create_enrollment`](../../services/mobile/api.py#L762), `_revoke_enrollment`, `_revoke_device` | The OIDC wrappers pass an operator ID; the service sets operator tenant context before location-owner checks and writes. | Source pattern is tenant-aware. Validate with forced-RLS disposable PostgreSQL tests and ensure request failures roll back and clear context. |
| Capability/API-key enrollment and revocation: [`router.py`](../../services/gateway/router.py#L58) and [`_create_enrollment`](../../services/mobile/api.py#L762) | Gateway middleware authorizes the exact `mobile_device` action/location and records an internal request marker. The same write transaction validates and share-locks the current verified owner, sets `actor_type=gateway`, and performs the enrollment/revocation. Missing marker, stale/missing owner, or failed context is denied before the write. | The application source path is closed and focused route/helper checks pass. Still not ready for RLS: the database custom setting is forgeable by any role with arbitrary SQL. The Gateway API-key/capability grant is not independently verified by PostgreSQL; establish a constrained database role or a database-verified capability before claiming a database isolation boundary. |
| Legacy analytics transport CLI: [`mobile_offline.py`](../../services/analytics/mobile_offline.py) | Direct registration now fails closed. Device listing, collection queue/pending reads, batch sync, conflict resolution, and global sync statistics still use direct SQL without tenant context. | Not ready for RLS. Keep it behind a restricted maintenance role or migrate/disable each command; transport-only status is not a substitute for tenant authorization. |
| Tenant preflight: [`collect_inventory`](../../services/mobile/tenant_preflight.py#L557) | Runs a read-only repeatable-read aggregate and emits opaque references/counts; it deliberately examines ownership and grants across locations. | Give it an explicit owner/preflight database role and document who may invoke it. Do not run the aggregate with the ordinary app role once RLS is enabled. |
| Directus and database views | The archived Directus runtime identity and effective grants have not been verified; OFU-09 tracks the required isolated runtime and fixture. Migration 139 also defines legacy mobile sync/device views. | Not ready. Inspect role grants, view ownership/invoker behavior, hooks, saved queries, and all consumers in a matching isolated Directus runtime before choosing RLS policies or retirement scope. |
| Recovery fixtures and ordered migrations | Recovery fixture SQL inserts devices into isolated scratch databases. Migration 391 adds owner-binding triggers and indexes; migration 392 adds credential functions and hardens the trigger's fixed search path. Neither enables RLS. | Migration 391 is applied on the candidate; 392 passed isolated PostgreSQL 16 acceptance but has not been rolled out. Keep fixtures and migration execution on explicit maintenance credentials. Candidate 391 evidence: [rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json). Migration 392 evidence: [disposable acceptance](builds/2026-10-14-recovery/mobile-credential-functions-disposable.json). |

## Context trust boundary

The device and operator helpers verify the caller against database rows before
setting transaction-local `kokonut.*` values. The Gateway mutation helper
carries a request identity already authorized by middleware and independently
verifies the current location owner; it does not validate the Gateway grant in
PostgreSQL. PostgreSQL accepts custom two-part settings and exposes `set_config`
for setting them; those settings are context values, not proof of identity by
themselves. If the ordinary application database role can issue arbitrary SQL,
it can also choose custom context values. Treat these helpers as application query scoping and defense in depth until the
role boundary is explicit. For an RLS boundary against direct SQL from other
consumers, establish context through a database function/role that verifies the
credential or grant itself, or constrain the role so callers cannot select
arbitrary tenant context. See PostgreSQL’s
[custom options](https://www.postgresql.org/docs/current/runtime-config-custom.html)
and [configuration-setting functions](https://www.postgresql.org/docs/current/config-setting.html).

## Required sequence before RLS

1. Inventory every table, view, trigger, worker, CLI, API-key route, OIDC route,
   Directus role/hook, and maintenance command that reads or writes the tenant
   tables. Record the database role and whether it bypasses RLS.
2. Close the token and enrollment credential lookup paths without weakening
   token hashing, one-time use, owner-transfer serialization, or revocation.
   Migration 392 now implements these bounded paths and passes isolated
   PostgreSQL acceptance; its candidate rollout and final app-role grant still
   need review before policies are prepared.
3. Keep Gateway capability/API-key mutation context in the same transaction,
   and validate it under forced RLS with the final role model. Retain OIDC and
   mobile context cleanup at transaction end.
4. Separate app, migration, backup, Directus, preflight, and recovery-fixture
   database roles. Verify least privilege and view semantics on PostgreSQL 16.
5. In disposable PostgreSQL, test owner and explicitly shared access; wrong or
   stale owner; legacy NULL binding; absent and forged context; expired, used,
   revoked, and concurrently redeemed enrollment codes; owner transfer during
   requests; API-key/OIDC denial; view access; rollback; and transaction reset.
   Migration 392 covers concurrent single-use redemption, expiry, owner
   transfer, and token states; repeat the checks under final RLS and runtime
   roles.
6. Only then prepare a separately approved candidate migration with an
   encrypted checkpoint and a verified restore path. Keep RLS disabled if any
   access path or consumer remains unknown.

This audit combines source review and isolated migration-392 acceptance. It
does not claim Directus parity, worker isolation, a database-verified Gateway
capability, candidate rollout of migration 392, database-role hardening across
consumers, an RLS migration, or live candidate RLS acceptance.
