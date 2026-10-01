# KI-21 Phase 0 — Gateway and Field Collector API Acceptance Map

- **Status:** Partial, source-backed draft; not runtime sign-off or deployment authorization
- **Evidence date:** 2026-10-01
- **Scope:** HTTP Gateway and Field Collector routes only. This is the next slice of the Phase 0 capability acceptance matrix, not a complete map of Directus, gRPC, CLI, workers, MQTT, files, or chain workflows.
- **Validation boundary:** Repository code and test references were reviewed. No endpoint was exercised against a live service or database for this document. Staging services remain stopped; backup and restore verification remain open.

See the broader [Phase 0 capability baseline](phase0-capability-baseline.md) and [Phase 1 Staging retained-volume inventory](phase1-staging-volume-inventory.md).

## Common Gateway controls

- `services/gateway/app.py` applies rate limiting, authorization policy, and audit handling before dispatching every HTTP request. Route authorization is opt-in for public paths; unmatched method/path pairs are protected by default.
- A route marked `public` bypasses Gateway API-key/capability authorization. It does **not** automatically make downstream access safe: the mobile sync and status handlers perform their own device-token check, while public registration does not.
- The rate limiter is an in-process token bucket (default 100-token burst, refill 10/second); it is not shared across Gateway replicas and resets with process state.
- Audit events are sent to the security audit layer. If durable audit writing fails, the exception is logged and the request continues; durable persistence is therefore a required integration-test gate, not guaranteed by the handler call alone.
- `CORS_ORIGIN` defaults to `*`. Set and verify an explicit origin policy before external browser exposure.
- The Field Collector stores its queued records, forms, settings, and device token in browser `localStorage`; the application does not encrypt these values at rest. Same-origin script execution can read the stored token and offline data.
- FastAPI also registers `/`, `/docs`, and `/openapi.json`, but these paths have no explicit public route policy and therefore use the protected fallback. Decide and test the intended public contract.

## Route acceptance map

### 1. Health and static Field Collector

- **Actor and paths:** Anonymous health probes use `GET /health`; field users open `GET /mobile`, `/mobile/`, or `/api/mobile/app`.
- **Authorization and effects:** These paths are explicitly public. Health returns service/version/Git SHA/timestamp. The app routes serve the repository HTML file; neither path is intended to mutate canonical records.
- **Integration and observability:** FastAPI Gateway and its local static asset; Gateway rate-limit and audit middleware apply. The health response discloses build metadata, which should be included in the external-exposure decision.
- **Evidence:** `tests/test_gateway_auth.py` checks anonymous health; `tests/test_mobile_api.py` checks the static app and its route policy.
- **Recovery / open gate:** Rebuild the app from versioned source. Confirm the desired behavior of `/`, `/docs`, and `/openapi.json`; there is no route-level acceptance test for their protected-fallback behavior in the reviewed test set.

### 2. Public location reads

- **Actor and paths:** Anonymous callers can request `GET /api/locations` and `GET /api/locations/{location_id}`.
- **Source and effects:** Both handlers proxy to Directus; list returns at most 100 records, while the single-location handler validates UUID syntax. The handlers issue GET requests through the shared `HttpClient` without explicit caller or tenant credentials. The effective Directus permission contract must be verified rather than inferred from this proxy.
- **Authorization and approval:** Gateway policy is public; no location-specific authorization is applied at this layer. Approval is required for the intended public fields and tenant/location visibility.
- **Observable behavior and evidence:** Upstream failures become `502` responses. No route-level contract or permission test for these two proxies was found in the reviewed tests.
- **Recovery / open gate:** Source data is Directus/PostgreSQL-backed. Verify anonymous Directus role permissions, tenant isolation, response schema, and upstream error behavior before treating these routes as externally safe.

### 3. Public metric, risk, analytics, identity, and registry reads

- **Actor and paths:** Anonymous callers can access `GET /api/metrics/{location_id}`, `GET /api/crisp/{location_id}`, `GET /api/analytics/{location_id}/summary`, `GET /api/iri/resolve`, `GET /api/federation/nodes`, `GET /api/drivers`, and `GET /api/health/services`.
- **Source and effects:** Metrics query `v_public_metric_summary` and do not compute or create values. CRISP and portfolio summaries call service/library methods. IRI, federation, driver, and service-health routes query their corresponding registries/services. These are read paths in the inspected handlers.
- **Authorization and approval:** All are explicitly public at the Gateway. Product/data owners still need to approve which fields and node/driver/health details are public; route policy alone is not a data-classification decision.
- **Observable behavior and evidence:** `tests/test_gateway_public_metrics.py` verifies the metrics handler reads the view and does not call `compute_all`. `tests/test_gateway_auth.py` checks anonymous IRI access is not rejected with `401`. Service-level tests exist for CRISP and portfolio behavior, but the reviewed source baseline identifies limited endpoint-level schema/security coverage for those handlers. No endpoint-level tests were found for federation nodes, drivers, or service health in this focused review.
- **Recovery / open gate:** These reads depend on their underlying PostgreSQL-backed services and registries. Confirm response schemas, public eligibility, failure behavior, and query bounds through route-level tests; backup/recovery remains subject to the separate Staging recovery gate.

### 4. Governed data-stream post creation

- **Actor and path:** Authenticated API-key or capability-token caller: `POST /api/data-stream/post`.
- **Authorization and scope:** Gateway policy requires resource `data_stream_post`, action `create`, and resolves `location_id` from the JSON body before authorization. API-key scopes and capability checks are handled by `services/gateway/auth.py`. The handler uses `request.state.caller` as `created_by`; it does not trust a caller-supplied `created_by` field.
- **State and approval:** The handler passes location, post type, title, content, and verified caller to `create_post`. The service inserts a `data_stream_post` with status `draft` and default `internal` visibility. This route does not itself verify or publish the post; subsequent governed transitions require their own authorization and human-approval evidence. **Response-contract gap:** `create_post` returns a mapping containing `id` and `created_at`, but the Gateway wraps that whole mapping under `post_id`; the current route test mocks a scalar string and therefore does not exercise the real service return shape. Define the response contract and test the actual mapping before sign-off.
- **Evidence:** `tests/test_gateway_auth.py` covers anonymous denial, verified actor attribution, required scopes, location-scoped strict mode, and capability verification. These tests do not by themselves prove durable PostgreSQL insert behavior or the full human-verification lifecycle.
- **Recovery / open gate:** The record is in canonical PostgreSQL. The current Staging backup checkpoint is stale and no restore has been rehearsed; see the [retained-volume inventory](phase1-staging-volume-inventory.md). Add/retain database integration coverage for the draft insert, failure rollback, audit persistence, and downstream approval path before migration sign-off.

### 5. Mobile form discovery

- **Actor and path:** Anonymous Field Collector clients request `GET /api/mobile/forms`, optionally with `location_id`.
- **Source and effects:** The handler returns active `mobile_form` definitions. It includes global forms (`location_id IS NULL`) and forms matching the supplied location. This is a read-only database path; the route is marked public and does not authenticate a user or device.
- **Authorization and approval:** Confirm that form schemas and location-specific form metadata are intentionally public, and that the caller-supplied location filter is an acceptable visibility boundary. The current handler does not set explicit cache-control headers despite describing the definitions as cacheable.
- **Evidence:** `tests/test_mobile_api.py` checks that the route policy is public. No query-result privacy or cache-header test was found in the reviewed test set.
- **Recovery / open gate:** Forms are PostgreSQL-backed. Add endpoint tests for global/location-specific filtering, inactive forms, schema compatibility, and permitted public fields.

### 6. Device registration — open enrollment gate

- **Actor and path:** Anonymous caller: `POST /api/mobile/register`.
- **Source and state effects:** The request supplies `device_id`, optional `user_id`, and optional `location_id`; the Field Collector sends the user/location values from manually editable local settings, not from an authenticated identity. The handler creates an opaque token and stores only its SHA-256 hash. On `device_id` conflict, the upsert replaces the user, location, and token hash and sets the device back to `active`.
- **Authorization and approval:** The Gateway marks registration public, so API-key/capability authorization is skipped. The inspected handler does not prove that the caller controls the device ID or is authorized to assign the supplied user/location. This is an **open acceptance blocker** for external exposure: product/security owners must choose and implement a trusted enrollment and reassignment policy before this route is approved. The default IP-based rate limiter is not a substitute for ownership or authorization.
- **Observable behavior and evidence:** The response returns the newly issued device token once. The reviewed API tests verify the public policy but do not exercise the HTTP registration/upsert, unauthorized reassignment, abuse controls, or token rotation.
- **Recovery / open gate:** Device records and token hashes are PostgreSQL state; recover them only through an approved, tested backup path. Add route-level tests for enrollment authorization, conflict behavior, reassignment, revocation, and token disclosure before release.

### 7. Offline sync and per-device status

- **Actor and paths:** A registered device uses `POST /api/mobile/sync` and `GET /api/mobile/sync/status` with `x-device-token`.
- **Authorization and scope:** These routes are public to Gateway middleware but the handlers require an active token hash, verify the request `device_id` matches the token-bound device, and derive `user_id` and `location_id` from the registered device record. A request cannot select a different location in the collection payload.
- **State and effects:** Sync inserts `offline_collection` rows with `pending` status, deduplicates on non-null `client_id`, updates device `last_seen_at`, and writes a `sync_log` record in one transaction. The model permits up to 50 collections; each payload is checked against an 8 MB serialized-size limit after request parsing. The browser converts selected photos into JPEG data URLs in `payload.photos`, stores that queue in `localStorage`, and also sends filenames in `photo_refs`; the API persists the payload as JSONB in `offline_collection`. This is not a separate media-upload/authorization path, so image bytes and field data remain together in the database payload. The route allows up to 50 items; no route-level aggregate request-body limit is apparent before JSON parsing, while any upstream proxy limit remains unverified. Status returns per-device pending/error/conflict counts and `last_sync_at`. The sync handler updates `last_seen_at` but does not update `last_sync_at`; the source does not establish which component, if any, refreshes that field.
- **Approval and observability:** The route queues evidence; it does not verify or publish it. Persistent collection/sync rows and the Gateway audit trail are the observable state. Confirm operational handling for stuck pending/error/conflict records and audit-write failures.
- **Evidence:** `tests/test_mobile_api.py` checks public route policy and request coordinate validation. `tests/test_mobile_offline.py` exercises service-level registration, duplicate client IDs, queue/sync/conflict/status logic with mocked database objects. No HTTP-level coverage was found in the reviewed test set for missing/invalid/revoked token, device mismatch, location binding, API batch boundaries, or retry behavior.
- **Recovery / open gate:** Canonical sync state resides in PostgreSQL. Verify database restore and client retry/idempotency behavior before relying on these records; no fresh Staging checkpoint or restore verification has been performed.

## Acceptance gates to close this slice

1. **Enrollment and identity:** Decide the trusted device-enrollment/reassignment model, then test it at the HTTP boundary. The current public upsert can change an existing device's user/location/token when its `device_id` is presented.
2. **Public data exposure:** Approve the public fields for location, forms, metrics, federation, driver, and service-health endpoints. Verify Directus permissions and location isolation; do not assume a public route policy is equivalent to a safe public dataset.
3. **Scope and governance:** Test the API-key/capability scope on the post endpoint through durable DB behavior, and verify draft-to-submitted-to-verified/published transitions remain separately authorized and human governed.
4. **Offline privacy, abuse, and scale:** Treat locally stored device tokens, user/location settings, GPS observations, queued records, and photo data as sensitive. Choose and document a browser/device storage threat model; moving to IndexedDB alone is not encryption. Remove Base64 image bytes from JSONB payloads in favor of an authenticated private-media flow with opaque references and location/device authorization. Set production CORS origins and an aggregate request-size/rate-limit policy before external exposure.
5. **Audit and observability:** Add an integration test for durable audit persistence and a documented operator signal/response when audit writes fail. Confirm health metadata is appropriate to disclose.
6. **Recovery:** Establish coverage for PostgreSQL plus associated media/device state, verify a fresh encrypted checkpoint and its contents, and conduct an isolated restore rehearsal under separate authorization. The requested Staging service start and restore have **not** been authorized or performed; the existing backup/recovery gate remains open.
7. **Runtime evidence:** After the above decisions and test setup, add isolated route-level tests for Directus proxy permissions, mobile enrollment/token checks, sync replay/location binding, error schemas, and public-read data eligibility. Do not use Staging as a substitute for an isolated test fixture.

## Proposed Field Collector remediation sequence (not implemented)

1. **Gate enrollment before external exposure.** The inspected registration route is currently public. Before exposing it externally, replace caller-selected identity binding with a server-issued, short-lived, single-use enrollment challenge bound to an approved user and location. Make conflicting `device_id` registration fail closed; move token rotation, reassignment, reactivation, and revocation to an explicitly authenticated/audited operation.
2. **Scope form and read access.** Permit anonymous access only to explicitly approved global form definitions. Require an active device credential for location-specific forms and derive location from its registration, not the query string. Review the public Directus location proxy and other public read routes against an allowlisted field/tenant contract; remove public policy where no safe public dataset is approved.
3. **Protect offline credentials and records.** Define the threat model for shared/lost devices and same-origin script compromise. Stop persisting the raw device token in `localStorage`; use an appropriate secure credential mechanism, explicit lock/clear/revoke behavior, and minimal retention. Move the offline queue to a storage design that supports large records and, where the supported platform permits it, encryption with a device/user-unlocked key. Do not describe IndexedDB or a key stored beside ciphertext as protection from active same-origin script access. Add a strict CSP and safe rendering/schema validation as defense in depth.
4. **Separate photo media from collection JSON.** Replace `payload.photos` data URLs with an authenticated, resumable upload flow to an approved private media store. Persist opaque file IDs in `photo_refs`; enforce device/location authorization, MIME/size/count limits, private retrieval, retention/deletion, and retry cleanup. Keep the upload and collection acceptance states idempotent and auditable.
5. **Bound and test the HTTP contract.** Enforce a total request-body limit before JSON parsing in addition to per-item limits; test the 50-item and photo boundaries. Add ASGI tests for enrollment authorization/conflicts/revocation, form scoping, missing/invalid/revoked tokens, device mismatch, server-derived location, retry/idempotency, upload permissions, CORS, and absence of sensitive values in logs. Fix the separately identified data-stream response-shape mismatch and define how successful sync updates `last_sync_at`.
6. **Stage only after approvals and recovery evidence.** Review existing device/token/queued-record state without copying private rows into Git or issue comments; define any required token rotation or client transition. Keep Staging stopped until the enrollment, media, privacy, route, test, and backup/restore gates are approved and passed.

## Test inventory and execution status

- Reviewed and executed: `tests/test_gateway_auth.py`, `tests/test_gateway_public_metrics.py`, `tests/test_mobile_api.py`, `tests/test_mobile_offline.py`, `tests/test_gateway_audit.py`, `tests/test_crisp_scoring.py`, and `tests/test_portfolio.py` — **118 passed** on 2026-10-01.
- The declared `requirements.txt` plus Starlette's recommended `httpx2` test client were installed only into `/home/ubuntu/.hermes/cache/scratch/ki21-testenv` (Python 3.11); repository manifests and environments were not changed. The test run used a clean tracked-source export at `fe87954`, excluding `.env.sops`, with `PG_HOST=127.0.0.1` and `PG_PORT=1` so any accidental database connection could only fail against the closed local loopback port. No Staging/live service was started or contacted. This is focused unit/ASGI evidence, not DB integration, external-client, or restore validation.
- No Staging service was started, no retained volume was modified, and no backup or restore was run for this acceptance-map slice.
