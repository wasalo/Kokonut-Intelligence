# Field Collector tenant and RLS call-site audit

Updated: 14 October 2026

## Finding

Migration 391 pins newly issued enrollment codes and registered devices to the
verified current location owner and rejects later binding changes. It leaves
row-level security disabled. The first-party Gateway sets transaction-local
tenant context for many protected device operations, but credential resolution,
API-key operator mutations, legacy transport helpers, the preflight CLI, and
unverified Directus consumers still need an explicit database access design.
Do not enable RLS until those paths and their database roles are closed.

## Access-path inventory

| Path | Current scope enforcement | RLS readiness / required work |
| --- | --- | --- |
| Device-token resolution: [`_device_for_token`](../../services/mobile/api.py#L353) | Hashes the presented token, reads one active device, and closes that connection. It runs before each endpoint opens the transaction that establishes tenant context. | Not ready for an RLS policy on `mobile_device`. Move this lookup behind a narrowly scoped credential-resolution function/role that returns only the device identity needed to begin the next transaction. Preserve token hashing and revocation checks. |
| One-time enrollment redemption: [`register_device`](../../services/mobile/api.py#L834) | Looks up the enrollment-code hash `FOR UPDATE`, checks the active owner, inserts the device, and marks the code used in one transaction. The code is a bearer credential; no tenant context exists before lookup. | Not ready for ordinary RLS. Preserve atomic single-use semantics with a narrow redemption function/role or equivalent verified access path; do not grant broad no-context table reads. Test concurrent redemption and owner transfer. |
| Device-scoped forms, sync, status, and media-policy reads | After token resolution, these handlers call [`set_mobile_device_tenant_context`](../../services/common/tenant_context.py#L90) on the same connection before protected location/data queries. It validates the active device against the current verified owner and uses transaction-local context. | The protected-query pattern is reusable after token-resolution closure. Review every SQL statement and keep context plus data work in the same transaction. Media object storage remains a separate provider boundary. |
| OIDC operator enrollment/revocation: [`_create_enrollment`](../../services/mobile/api.py#L762), `_revoke_enrollment`, `_revoke_device` | The OIDC wrappers pass an operator ID; the service sets operator tenant context before location-owner checks and writes. | Source pattern is tenant-aware. Validate with forced-RLS disposable PostgreSQL tests and ensure request failures roll back and clear context. |
| Capability/API-key enrollment and revocation: [`router.py`](../../services/gateway/router.py#L58) and [`_create_enrollment`](../../services/mobile/api.py#L762) | Gateway checks a location-scoped `mobile_device` capability, but the non-OIDC service calls use `operator_id=None`; the service therefore skips `set_operator_tenant_context`. | Not ready for RLS. Bind the capability identity to a database-verifiable tenant context or retire these mutation routes before RLS. Test scope, current-owner match, denial, and cleanup. |
| Legacy analytics transport CLI: [`mobile_offline.py`](../../services/analytics/mobile_offline.py) | Direct registration now fails closed. Device listing, collection queue/pending reads, batch sync, conflict resolution, and global sync statistics still use direct SQL without tenant context. | Not ready for RLS. Keep it behind a restricted maintenance role or migrate/disable each command; transport-only status is not a substitute for tenant authorization. |
| Tenant preflight: [`collect_inventory`](../../services/mobile/tenant_preflight.py#L557) | Runs a read-only repeatable-read aggregate and emits opaque references/counts; it deliberately examines ownership and grants across locations. | Give it an explicit owner/preflight database role and document who may invoke it. Do not run the aggregate with the ordinary app role once RLS is enabled. |
| Directus and database views | The archived Directus runtime identity and effective grants have not been verified; OFU-09 tracks the required isolated runtime and fixture. Migration 139 also defines legacy mobile sync/device views. | Not ready. Inspect role grants, view ownership/invoker behavior, hooks, saved queries, and all consumers in a matching isolated Directus runtime before choosing RLS policies or retirement scope. |
| Recovery fixtures and ordered migrations | Recovery fixture SQL inserts devices into isolated scratch databases. Migration 391 adds owner-binding triggers and indexes, but does not enable RLS. | Keep fixtures and migration execution on explicit maintenance credentials. The candidate rollout confirms migration 391 is applied and RLS remains disabled ([evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)). |

## Context trust boundary

The current Python helper verifies the device/operator against database rows,
then sets transaction-local `kokonut.*` values. PostgreSQL accepts custom
two-part settings and exposes `set_config` for setting them; those settings are
therefore context values, not proof of identity by themselves. If the ordinary
application database role can issue arbitrary SQL, it can also choose custom
context values. Treat the current helper as application query scoping and
defense in depth until the role boundary is explicit. For an RLS boundary
against direct SQL from other consumers, establish context through a database
function/role that verifies the credential or grant itself, or constrain the
role so callers cannot select arbitrary tenant context. See PostgreSQL’s
[custom options](https://www.postgresql.org/docs/current/runtime-config-custom.html)
and [configuration-setting functions](https://www.postgresql.org/docs/current/config-setting.html).

## Required sequence before RLS

1. Inventory every table, view, trigger, worker, CLI, API-key route, OIDC route,
   Directus role/hook, and maintenance command that reads or writes the tenant
   tables. Record the database role and whether it bypasses RLS.
2. Close the token and enrollment credential lookup paths without weakening
   token hashing, one-time use, owner-transfer serialization, or revocation.
3. Add tenant context to capability/API-key mutations, or disable them before
   enabling policies. Retain OIDC and mobile context cleanup at transaction end.
4. Separate app, migration, backup, Directus, preflight, and recovery-fixture
   database roles. Verify least privilege and view semantics on PostgreSQL 16.
5. In disposable PostgreSQL, test owner and explicitly shared access; wrong or
   stale owner; legacy NULL binding; absent and forged context; expired, used,
   revoked, and concurrently redeemed enrollment codes; owner transfer during
   requests; API-key/OIDC denial; view access; rollback; and transaction reset.
6. Only then prepare a separately approved candidate migration with an
   encrypted checkpoint and a verified restore path. Keep RLS disabled if any
   access path or consumer remains unknown.

This audit is source-based. It does not claim Directus parity, worker isolation,
database-role hardening, an RLS migration, or a live candidate RLS acceptance.
