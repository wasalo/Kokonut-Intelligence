# Gateway tenant context contract

Migration 396 binds API-key and capability-token authorization to signed
PostgreSQL tenant context. It is source-only until separately approved for a
candidate rollout. It does not enable application RLS.

## Credential rules

- Gateway middleware hashes a credential only after its current authorization
  path accepts it. The raw credential is not copied into request state or audit
  records.
- `kokonut_security.set_gateway_tenant_context` rechecks the matching database
  credential in the protected transaction. API keys must be active and
  unexpired; capability tokens must be unrevoked and unexpired. A positive
  maximum usage count is rechecked after Gateway authentication consumes the
  current use, so the final authorized request passes at `usage_count ==
  max_usage` while over-limit tokens fail; zero retains the existing
  unlimited-use behavior.
- A tenant-bound call needs the exact `resource:action:<location UUID>` scope.
  Wildcard, location-free, expired, revoked, duplicate API-key hashes, and
  wrong-location scopes fail closed.
- Migration 396 adds a unique index for API-key hashes. If historic duplicate
  hashes exist, the transactional migration fails without committing partial
  changes; an operator must resolve those rows before rollout.
- The database derives tenant ownership from the active location and current
  verified owner row, locks the credential and owner records, and signs the
  context for the current backend and transaction. `current_tenant_context()`
  accepts the resulting `gateway_api_key` or `gateway_capability` actor only
  after HMAC, backend, and transaction validation.
- The setter and protected query/write must use the same non-autocommit
  connection. Commit or rollback clears the transaction-local context. The
  `POST /api/data-stream/post` handler now establishes this context before its
  draft insert, passes the database-derived actor UUID as `created_by`, and maps
  database scope denial to HTTP 403. The client's `created_by` field is ignored.
  The route keeps its existing response shape (`post_id`) and does not publish
  or verify the draft.

## Runtime role

The ordinary runtime role can read only the API-key columns needed by existing
gRPC authentication. It cannot insert, update, or delete API keys. The role
bootstrap reapplies and verifies this allowlist on every provisioning run;
unknown future columns remain unavailable until reviewed. API-key creation and
rotation remain administrative operations.

Existing environment-configured Gateway keys used for tenant-bound mobile
device operations or Data Stream creation also need a matching
`api_key.key_hash` record with the exact location scope before those operations
can establish tenant context. Database context independently revalidates
capability tokens already stored in `capability_token`. No credential value or
hash should be copied into this document or acceptance output.

The one-shot `python3 -m services.gateway.api_key_provisioning` command bridges
the environment key list to PostgreSQL through
`KOKONUT_API_KEY_PROVISIONER_DSN`, which must be supplied only to the operator
command and kept in encrypted secrets. The default mode is a dry run. `--apply`
inserts only missing SHA-256 hashes with exact UUID-scoped grants; broad,
wildcard, location-free, and malformed scopes are excluded. It never prints or
stores raw key values, updates existing rows, reactivates inactive credentials,
or removes rows for keys absent from the environment. Conflicting existing
records stop the transaction and require an explicit credential rotation or
reconciliation. The command does not take row-update locks; its concurrent
insert path uses the migration-396 unique hash index and can reconcile an
identical concurrent insert. A dedicated maintenance login needs only reviewed
SELECT and INSERT column privileges on `api_key`; the Gateway runtime remains
read-only.

## Acceptance evidence

- [`gateway-tenant-context-disposable.json`](builds/2026-10-14-recovery/gateway-tenant-context-disposable.json)
  records migration replay, forced-RLS API-key/capability behavior, denial and
  cleanup checks in isolated PostgreSQL 16 with Docker networking disabled,
  including a synthetic Data Stream create insert constrained by tenant,
  location, and database-derived actor.
- `tests/test_gateway_data_stream.py` and the focused Gateway route suite cover
  same-connection context-before-insert, actor attribution, input/scope
  rejection, transaction rollback on denial, and HTTP 403 behavior.
- [`runtime-mobile-credential-role-disposable.json`](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json)
  records the repeatable runtime-role bootstrap and API-key write denial.

The fixtures are synthetic and use a minimal compatible schema. They do not
prove candidate data state, execution of the provisioning command, production
key provisioning, shared-organization
API-key access, all Gateway route parity, worker/CLI boundaries, or
application-wide RLS readiness.
