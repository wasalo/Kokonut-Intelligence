# Kokonut Kernel implementation progress

**Updated:** 11 October 2026. **Current implementation focus: Phase 7 — native
application API, with an additive versioned public-location read slice in source.**
Preparatory Phase 8 image work
has also occurred. This is not a sequential completion claim: earlier phases
have implementation evidence but unresolved acceptance criteria.

Implementation work has local commits on `chore/kernel-plan-ignore`, based on
`ad806f504bfef15cba41446d777cb22f6bd8fe6a`. No implementation PR/merge or passing
release CI is recorded. The root implementation plan remains intentionally
ignored; this ledger and the [capability matrix](capability-matrix.md) provide
repository-visible progress alongside it.

## Phase ledger

| Phase | Implementation status | Delivered evidence / likely owners | Remaining completion gates |
| --- | --- | --- | --- |
| 0 — Baseline | Inventory delivered; closure partial | 66 capability owners/checks, frozen source/dependency inventory and local container/volume counts; [baseline](README.md), [storage](local-data-inventory.md) | Collection/consumer refinement, logical Redis/BI/broker/private-media state, selected legacy logical records restored; complete provider/media/role recovery and broader ownership pending |
| 1 — Ports/providers | Implemented in selected paths; acceptance open | Typed provider settings/health; analytics/cache/events/scheduler ports; lazy vendor adapters; static check passes at 17 vendor sites; services/core/, services/common/, services/analytics/ | Contract/import/config and legacy behavior acceptance; storage/remaining domain construction audit; reviewed dependency lock |
| 2 — Minimal runtime | Fresh AMD64 runtime exercised; workflow acceptance open | Dockerfile.kernel, standalone candidate/portability manifests, supervisor and split roles; portability DB/API/worker had run, then returned to stopped/exited state after recovery probes; latest portability app image includes audit CLI; separately, the active candidate app and database are healthy with a current-source image, 370 applied schema migrations through 379 and zero pending; separate recovery fixture has 365 checksummed schema files through 374; sensor anomaly alert/claim/outbox/actuation approval effects now share a transaction and one actual EventBus worker crash/retry completed on attempt two without duplicate effects; [runtime](portability-runtime.md), [sensor entrypoint](sensor-entrypoint-recovery.md), [sensor delivery](sensor-anomaly-delivery.md) | Governed farm write/submit/independent review/publish, metric/report workflow, mobile sync and accepted-work recovery; no seeded pilot fixture yet; external provider acceptance and broader event/runtime recovery remain open |
| 3 — Optional analytics/BI | Partial | PG metric catalog/public roll-up; optional ClickHouse driver/overlay; sensor source/event/outbox paths exercised against raw ClickHouse and v3 daily summary; Directus, Metabase metadata, and analytics-source roles verified on isolated copies; pinned Directus bootstrap/runtime and Metabase populated-metadata startup healthy; sample board classified as generic e-commerce demo; source-aligned scratch applied all 369 migrations through 378, zero pending, and passed actual-view grants and rollback-only reporting probes; transactional replay validated all 369 current schema checksums and rollback of injected DDL plus ledger state (`0|0`); a separate clone accepted the 25 pending archived migrations with zero pending and unchanged original-column fingerprints across 16 populated tables; migration-354 SAFE addresses, owners, thresholds, versions, and nonces matched read-only Gnosis Chain calls; independent NOI recomputation matched the view on six cycles, exposing six stale snapshots and a missing upsert key; migration 379 plus native reconciliation SQL and Directus-hook alignment brought six snapshots into parity on a separate network-disabled clone; [NOI reconciliation](noi-snapshot-reconciliation.md), [evidence](builds/2026-10-11-recovery/noi-snapshot-parity.json), [consumer role policy](optional-database-roles.md), [report contract](metabase-reporting-contract.md), [populated parity](builds/2026-10-11-recovery/populated-report-view-parity.json), [candidate preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json), [compatibility review](pending-migration-compatibility-review.md), [reporting migration](../../schemas/postgres/377_kokonut_reporting_contract.sql), [NOI index migration](../../schemas/postgres/379_noi_snapshot_crop_cycle_key.sql), [reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json), [transaction evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json), [populated clone evidence](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json), [checksum triage](migration-checksum-drift.md), [startup evidence](builds/2026-10-11-recovery/metabase-populated-startup.json) | Archived application clone remains unchanged with 25 pending migrations. The candidate's exact historical checksum was repaired through the audited path; migrations 371–379 applied transactionally and the exact-target plan reports zero pending across 370 schema files. Its checkpoint restored successfully in isolation. The reporting views and NOI unique index exist. The candidate analytics login is provisioned and verified with no unreviewed application relation access; the optional Metabase profile is healthy with its separate H2 demo and Kokonut source/cards; populated saved-card SQL matches independent farm, attestation and synthetic metric references, including publication and date-window filters. Populated farm-summary and Celo-attestation view parity passed; synthetic nonempty metric period/method probe passed while the populated source has zero published policies; ClickHouse dataset/report parity and rebuild lineage; replay/outage acceptance; DuckDB/Parquet path and owned dashboard UI |
| 4 — Owned orchestration | Partial; idle native workers running | 15 JobSpecs, legacy flow delegation, scheduler planning/graph audit/guarded activation and same-window migration 371; the new daily `noi_snapshots` job is prepared but disabled; services/core/jobs.py, services/scheduler/, services/flows/ | Flow-by-flow schedule ownership/cutover, actual execution/retries/cancellation/recovery, historical Prefect state; no task activation or shadow comparison performed |
| 5 — Optional Redis | Partial; local runtime/restart and isolated PostgreSQL shared-consumption, lock-timeout, and direct and ASGI multi-process plus two-container network HTTP checks passed; provider selection remains open | Existing PG computation cache retained; local limiter concurrency/LRU/process reset and candidate app restart verified; in the migration-373 portability DB, two backend instances admitted 121/140 concurrent checks within the refill-aware bound, denied an over-capacity request, returned retry 10, and isolated a distinct caller; a held synthetic row lock raised SQLSTATE 55P03 after 2.124 seconds and its bucket was removed; network-disabled source ASGI checks selected PostgresRateLimiter and returned 503/Retry-After 30 on an unreachable DB; GatewayAudit now has a bounded SQLite queue, idempotent startup replay, a status/checkpoint/restore CLI, and process-exit/checkpoint/restore recovery evidence; four OS processes shared one bucket across 160 direct calls (114 allowed, 46 denied in 1.653 seconds), then four gateway processes handled 160 ASGI requests (121 returned 200, 39 returned 429 with Retry-After) within the refill-aware bound; two private-network API containers then handled 160 HTTP requests through the shared database (119 returned 200, 41 returned 429 with Retry-After); PostgreSQL adapter remains opt-in and candidate stays local; [local runtime](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json), [local contract](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json), [process reset](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json), [app restart](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json), [PG shared check](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json), [lock timeout](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json), [multi-process check](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json), [ASGI multi-process](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json), [two-container HTTP](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json), [audit outage/replay](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json), [checkpoint recovery](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json), [audit write guard](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json) | Volume/host/device loss, external alert delivery and production retention owner; auth/revocation/cache/TTL and identity-abuse acceptance; production/public ingress, multi-host failover, replica restart and scale acceptance; scale remains unavailable |
| 6 — Optional edges | Prepared/built in selected targets; acceptance open | MQTT/gRPC/HTTP sensor/Caddy overlays; CSV/HTTP exercised in-process and over TCP inside the private recovery network; selected handler receipt recovery; bounded Caddy TLS/redirect/header smoke, one-hop forwarded-header audit identity check, loopback-published redirect/follow check at default and alternate HTTPS ports, configured/untrusted CORS preflight, CORS decoration on an auth denial, isolated current-source and deployed local limiter checks with 429/Retry-After, preflight bypass and durable audit, plus promoted-image local concurrency/LRU, process reset, candidate app restart, source-level PostgreSQL-outage 503, real audit outage journaling and startup replay across app-container replacement, checkpoint/restore and process-exit recovery, held-row lock-timeout handling, direct four-process shared-bucket consumption, four-process gateway ASGI 200/429 behavior, and two-container network HTTP sharing; [sensor evidence](sensor-entrypoint-recovery.md), [proxy evidence](kernel-proxy.md), [source limiter](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json), [runtime limiter](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json), [local contract](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json), [process reset](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json), [app restart](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json), [outage boundary](builds/2026-10-11-recovery/postgres-rate-limit-outage.json), [audit outage](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json), [lock timeout](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json), [multi-process check](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json), [ASGI multi-process](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json), [two-container HTTP](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json), [audit journal](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json), [audit checkpoint](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json), [audit write guard](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json) | Volume/host/device loss, external alert delivery and production retention owner; production/public ingress, replica failover/scale; non-loopback/public ingress, multi-hop trusted-proxy policy, mobile/upload parity, CORS on successful authenticated/credentialed responses, HTTP/CSV/MQTT parity, optional service parity, broader handler recovery, delayed sink visibility/reconciliation, RPC streaming/auth and external Traefik acceptance |
| 7 — Native API | **Active, partial read slice deployed; v1 public read aliases, typed SDK sources, local operator overview, and source-level OIDC report review reads added** | Native public locations/metrics, published CRISP and location roll-up, strict response models, bounded read execution and readiness gates; additive `/api/v1` routes with explicit public policies; generated Python/TypeScript models and paths; local read-only Kernel overview; optional OIDC identity/session adapter; location-scoped submitted `report_snapshot` list/detail routes and same-origin read-only queue; services/gateway/router.py, services/gateway/operator_auth.py, services/gateway/operator_review.py, services/gateway/app.py, apps/operator-console/index.html | Live v1 payload/role/grant/auth and Directus parity; JavaScript SDK runtime import and offline Python/JavaScript SDK contract parity passed with fake adapters, while live route parity remains open; shared lifecycle hooks, tenant/RLS scope and governed writes/reviewer flows; OIDC provider configuration, migration 380, login/session/audit and report queue scope/detail acceptance remain open |
| 8 — ARM64/scale/retirement | Build preparation only | AMD64/ARM64 app/PostGIS artifacts; isolated portability deployment path; edge settings; [latest ARM64](arm64-public-reads.md) | ARM64 runtime/bootstrap/restore, actual 4 GB Pi/SSD measurement, 24-hour recovery, CI architecture gates, scale concurrency, release locking, production cutover and dependency retirement |

**No phase is marked fully accepted under the plan's complete criteria.** Builds,
source implementation and idle startup are useful milestones, but do not satisfy
domain or recovery acceptance. Work advanced across phases while preserving old
data/providers; provider retirement and production cutover have not occurred.

## Capability accounting

All 66 original IDs/checks remain in the matrix. Current integration progress:

- **6 deployed partial/adjacent integrations:** CAP-001, 007, 014, 031, 039, 047.
- **4 prepared partial integrations:** CAP-040, 053, 064, 066. CAP-040 now includes one bounded handler-effect and durable-receipt recovery rehearsal; it remains partial.
- **56 baseline-retained domains:** Kernel access paths and parity still unassessed.
- **0 fully accepted Kernel capabilities.** All MAN-CAP gates remain open.

CAP-031's public location roll-up is adjacent API work, not completion of planning
or internal portfolio analyses. CAP-014's published read does not certify the
five-dimension scoring engine. Shared infrastructure/image/schema work supports
many rows without migrating or certifying their full workflows. Source retention
does not guarantee an unchanged capability can run with minimal dependencies.

## Current deployment evidence

The isolated project `kokonut-kernel-portability` previously ran a private AMD64
database, API and native scheduler/event worker. Its recorded API and worker
image is
`sha256:78389fb6cf1f05291e89b35ce4f0271e533bbe5403be97a8d77a29cdfc5825f5`;
the database image is
`sha256:b573e82124b3530c454ea6d5ae8aefce1fb7ee137467f66f75a5079f8569ee6b`.
The portability app image was rebuilt with the audit maintenance CLI at
`sha256:13602e4470f02855320d458c3b229cf6d341a337ea3f7ccb04e4a353f42234f3`.
A one-off network-disabled container returned an empty status for an absent
journal without mounting a database or persistent volume; checkpoint, verify,
restore and overwrite refusal also passed against a private temporary bind
fixture. The candidate app and database remain up and healthy; portability API/worker containers remain
exited on the previous image and the portability database remains cleanly
stopped. No service recreation or provider change occurred. Ports remain private
per the manifest/runtime record; no legacy storage was migrated into this fresh
database. [CLI image evidence](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).

364 ordered schema migrations completed with zero failures, including 371–373.
That applies only to portability; candidate/legacy backlog is independent.
Numbered seeds and pilot data have not been loaded. Last worker workload
inspection was empty. Readiness checks cover bundled checksums, required extension
presence and four public relations/column sets; they do not certify view semantics,
grants, populated API responses, or recovery. See [exact runtime chronology and
rollback identities](portability-runtime.md).

No broad Python/Solidity/extension acceptance suites, multi-domain parity
fixtures, live summary request comparisons or full restore rehearsals are recorded.
The scoped single-reading sensor parity check is documented separately.
Lint/static gates and Docker health/startup are reported separately from tests.
The latest paired batch artifacts include public read models and the structural
relation gate; no ARM64 service has been started. Scale is still rejected by
the planner. Directus hooks/metadata, old dashboards and legacy volumes remain.

## Next work and tracking rule

Prioritize closing baseline/recovery and minimal workflow acceptance alongside
Phase 7, before adding governed writes or retiring a provider. Prepare a scoped
pilot/reference fixture and backup/restore path; establish public response,
authorization/lifecycle, mobile and worker recovery evidence. Continue Phase 7
through explicit domain contracts and reviewer policy, then SDK/console work.
ARM64/Pi/scale certification follows the relevant parity gates.

Every subsequent Kernel slice updates this ledger, the ignored root plan's phase
notes, directly affected matrix rows and the linked execution record. Record
source/image/profile identity, what changed, what was exercised, remaining gates,
and rollback. Mark an acceptance gate closed only with its retained evidence;
never infer parity from unchanged source, a build or a healthcheck. Avoid a single
completion percentage until work items and acceptance weights are agreed.

## Phase 7 v1 public location contract — 11 October 2026

Added strict response envelopes and additive `GET /api/v1/locations` and
`GET /api/v1/locations/{location_id}` routes. They use the native governed
`v_public_farm_summary` read path, document schemas through FastAPI OpenAPI, and
leave the existing unversioned Directus/native response wrappers unchanged.
Malformed UUIDs return 400; missing and ineligible locations share a 404.
Added typed location methods to separate Python and JavaScript public API
clients; the existing Directus clients remain unchanged. Updated the contract
and capability checklist. This is source implementation only: no runtime
payload comparison, grant review or Directus parity check was performed; the
SDK source has not been generated from OpenAPI or released; the TypeScript package build could not run because `tsc` is unavailable in the local checkout. No test suite was
added or run. Roll back by reverting the additive routes/models/SDK clients or
deploying the preceding gateway image; existing clients continue using
`/api/locations`.

The scoped native v1 OpenAPI snapshot is now retained at
[`native-public-api-v1.openapi.json`](native-public-api-v1.openapi.json); see
the additive-read entry below.

## Phase 7 additive public read aliases — 11 October 2026

Added `/api/v1/metrics/{location_id}`, `/api/v1/crisp/{location_id}`, and
`/api/v1/analytics/{location_id}/summary` as additive wrappers over the existing
strict-model read handlers. Successful v1 responses use `{ "data": ... }`, while
the legacy unversioned paths retain their raw response shape. Added explicit
public `read` route policies, envelope response models, and unique OpenAPI
operation IDs. Extended Python and JavaScript public clients with typed metric
summary, published CRISP, and governed location-summary results. Updated the
contract docs, capability rows, and Batch 5 checklist. This is source-level
implementation only. Exported the scoped native OpenAPI from the existing
Gateway dependency image with the current source mounted read-only and network
disabled; the generated document includes `x-kokonut-policy` derived from the
route-policy function. No service was started. The local host cannot import
FastAPI. The JavaScript build remains unavailable because `tsc` is not installed.
Python syntax compilation, JSON parsing and diff whitespace checks passed; no
test suite or HTTP route request was executed. SDK release packaging, HTTP
authorization/payload/Directus parity, and the operations-console slice remain
open. Rollback reverts the additive decorators and policy entries plus SDK
methods; the original routes remain.

## Phase 7 OpenAPI-derived SDK types and paths — 11 October 2026

Added a standard-library generator that reads the retained native v1 OpenAPI
snapshot and emits public response payload types for Python and TypeScript plus
operation-to-path tables. Both SDK clients now import those generated types and
use the generated path templates, while convenience method wrappers remain
handwritten. Regenerated artifacts from the snapshot; Python syntax compilation
and `python3 -m scripts.generate_public_api_sdk --check` passed. The local `tsc`
executable is still unavailable, so the TypeScript build was not run; no test
suite or HTTP route request ran. Refresh the OpenAPI snapshot before rerunning
the generator. SDK build/publication, runtime
parity, and the operations-console slice remain open.

## Phase 7 JavaScript SDK compiler compatibility — 11 October 2026

Installed the SDK's declared TypeScript 5.8.3 development dependency locally and
ran `npm run build` successfully. This exposed stale Directus SDK usage in
`sdk/javascript/src/client.ts`: item commands are now imported from
`@directus/sdk` and passed to `request()`, login reads the SDK's documented
`access_token` field, and requests await the asynchronous token setup/update.
The build compiles package sources and declarations; no
test suite or API request ran. This establishes compile-time compatibility, not
live Directus behavior, public-route parity, or SDK release readiness. Local
`node_modules/` and generated `dist/` remain ignored. Rollback by reverting the
client adapter change; the prior source failed this same compile. See the
[Batch 5 checklist](batches.md).

## Phase 7 JavaScript SDK package preflight — 11 October 2026

The npm package is configured as ESM to match `@directus/sdk` 17, its repository
metadata points to this checkout's `sdk/javascript` directory, the Apache
license is included at the package root, and `src/__tests__` is excluded from
published output. The lockfile pins TypeScript 5.8.3, `@directus/sdk` 17.0.2,
and Vitest 5.0.3. After cleaning only the generated, ignored `dist/`, the
TypeScript build passed and `npm pack --dry-run --json` listed 27 files with no
test output. The initial five development-tool audit findings were addressed by
upgrading Vitest; npm now reports zero vulnerabilities. No tarball was created
or published. No test suite or package runtime import was run; runtime parity
and versioned release remain open. See the [Batch 5 checklist](batches.md).

## Phase 7 Python SDK package preflight — 11 October 2026

Added the repository README, Apache license, and `py.typed` marker to the
`kokonut-intelligence` 0.1.0 distribution metadata. The repository URL now
matches this checkout's GitHub origin. Built a wheel and source distribution
with the installed setuptools backend, then inspected their archive contents and
metadata without installing or importing them. The wheel contains the typed
HTTP/Directus and native public API client modules, license, and package
metadata; the source distribution also contains the README and project source.
Artifacts were retained outside the repository in
`/private/tmp/kokonut-python-sdk-artifacts/`:

- `kokonut_intelligence-0.1.0-py3-none-any.whl` — 16,976 bytes;
  SHA-256 `3b99e5e9358794a804ef32283508839f460ccfcc1b13565e9342fff7b8e3a2fd`.
- `kokonut_intelligence-0.1.0.tar.gz` — 16,787 bytes;
  SHA-256 `208380cba97d05cc418b8d68b77bc805e44909f2a4b875158c51d4ebe9762ab5`.

The initial distribution contained only the `kokonut` HTTP SDK package;
generated protobuf/gRPC modules were excluded. That boundary is resolved in the
following entry. No SDK import, API request, test suite, or publish ran. Runtime
import/API parity and explicit release authorization remain open. See the
[Batch 5 checklist](batches.md).

## Phase 7 Python SDK optional gRPC distribution — 11 October 2026

Resolved the generated-protobuf packaging boundary without adding gRPC to the
base SDK. Added a pinned `grpc-codegen` extra and a `grpc` runtime extra, plus a
reproducible generator that puts source-generated modules under `kokonut.grpc`
and rewrites Python imports and generated class module metadata; protobuf
package/service names and descriptors remain derived from the unchanged
`proto/` files. The generated
code requires `grpcio>=1.68.1` and `protobuf>=5.28.1`; the SDK extra declares
compatible runtime bounds. Ruff passes, and regeneration reports all 10
generated Python modules up to date. The 0.1.0 wheel and sdist build and each
contain the 16 package `.py` files (10 generated modules plus six package
initializers); artifacts are under
`/private/tmp/kokonut-sdk-proto-artifacts/`. The standard isolated build first
could not reach PyPI, so the archive build used the already-installed setuptools
in the isolated code-generator environment. No SDK install/import, gRPC call,
test suite, publish, or release occurred. Runtime import/API parity remains
open. Roll back the generator, generated package and SDK extras together; the
legacy repository-level generated stubs and gRPC server are unchanged. See the
[Batch 5 checklist](batches.md).

## Phase 7 Python SDK isolated wheel import check — 11 October 2026

Installed the built `kokonut-intelligence` 0.1.0 wheel and the declared `grpc`
runtime dependencies into a clean temporary environment at
`/private/tmp/kokonut-sdk-import-env/`. The base REST clients and all 10
generated gRPC/Protobuf modules imported successfully with grpcio 1.84.0 and
protobuf 5.29.6. The check confirmed namespaced `PageRequest` class metadata and
the unchanged `data.v1.DataService` and `ecocredit.v1.EcocreditService` names
from their original descriptor paths. No API/RPC request, test suite, or
publish ran. Python SDK import acceptance is closed for this wheel/runtime
combination; JavaScript runtime import, live route/API parity, gRPC transport
authorization and release approval remain open. The wheel used is retained
under `/private/tmp/kokonut-sdk-proto-artifacts/`. See the [Batch 5
checklist](batches.md).

## Phase 7 TypeScript gRPC package proto boundary — 11 October 2026

Source inspection found that the TypeScript gRPC clients searched for proto
files relative to a repository checkout, while the npm package published only
`dist/`; an installed package therefore could not load either service
definition. The package now copies the Data/Ecocredit proto files and their
pagination/type imports into `dist/proto` during build, and both clients resolve
definitions relative to that package-owned directory. `prepack` performs a
clean build so npm archives include those assets. Removed the unused
`@bufbuild/protobuf` runtime dependency and Buf generation step; this client
uses `@grpc/proto-loader` directly. The first npm archive listing included
Vitest output under `dist/__tests__`, so the TypeScript build now excludes test
sources. `npm pack --dry-run --json` then completed its clean build and listed
23 files, including all five proto files and no test output. The default npm
cache is root-owned on this machine, so the archive preflight used a temporary
cache under `/private/tmp/kokonut-typescript-npm-cache/`. No test suite,
installed-package import, API/RPC call, or publish ran. Runtime acceptance and
Python/TypeScript API parity remain open. Roll back the package copy script,
client paths, build exclusions, lifecycle/dependency edits, and this
documentation together. See the [Batch 5 checklist](batches.md).

## Phase 7 TypeScript gRPC isolated npm package import check — 11 October 2026

Created the 1.0.0 npm tarball with its clean `prepack` build, extracted it into
`/private/tmp/kokonut-typescript-sdk-import-check-20261011/`, and resolved
`@grpc/grpc-js` and `@grpc/proto-loader` from the existing local dependency
installation. Constructing both `DataServiceClient` and
`EcocreditServiceClient` loaded their package-bundled proto definitions and
exposed the expected `generateIRI` and `classes` methods; both clients closed
successfully. No RPC/API call or test suite ran. This validates package import
and proto loading for this local artifact/dependency combination, not
server/client API parity or a published registry install. The tarball and
extracted package remain under the temporary path above. See the [Batch 5
checklist](batches.md).

## Phase 7 Python/JavaScript SDK pagination parity — 11 October 2026

Static comparison of the generated native v1 path maps found the same five
OpenAPI operation IDs and route templates in both REST SDKs. The legacy Directus
SDKs differed in pagination: JavaScript treated `0` as absent, defaulted an
offset without a limit to 100 rows, and let `page` override offset; Python
preserves explicit zero values, converts offset only when a limit is supplied,
and gives offset precedence. JavaScript now follows those rules and rejects a
zero limit paired with offset before it can emit an infinite page value. The
TypeScript build passed. No suite, runtime import, HTTP request, or live API
parity check ran; these remain separate acceptance gates. See the [Batch 5
checklist](batches.md).

## Phase 7 JavaScript REST SDK isolated package import check — 11 October 2026

Packed the `@kokonut-intelligence/sdk` 0.1.0 artifact (27 files) and extracted
it to `/private/tmp/kokonut-javascript-sdk-import-check-20261011/consumer/`.
The isolated consumer resolved `@directus/sdk` from the existing local
dependency install, imported the package's ESM entry point, and instantiated
both `KokonutClient` and `KokonutPublicApiClient`. Expected method groups and
the exported `PublicApiError` were present. A guarded fetch implementation
recorded zero HTTP calls. No test suite, live request, or API response parity
check ran. This closes local package import acceptance for this artifact and
dependency combination; full Python/JavaScript API behavior parity and release
approval remain open. See the [Batch 5 checklist](batches.md).


## Phase 7 Python/JavaScript offline API parity — 11 October 2026

Ran both SDKs against injected fake HTTP adapters, with no network or live API
calls. The probe covered all five generated v1 reads (location list/detail,
metrics, published CRISP, and location summary), including special-character
path IDs, `Accept` and API-key headers, response field values, and error cases
for malformed envelopes, error payloads, and invalid JSON. Python returns date
and datetime objects while JavaScript preserves the equivalent ISO wire strings.
The probe also captured Directus list queries for missing limits, offset/page
precedence, and zero-limit offset handling.

The comparison exposed and fixed inconsistent URL-component escaping, permissive
JavaScript handling of `data: null`, different malformed/error fallback
messages, Python's uncaught successful-response JSON error, and Python's divide
by zero for offset pagination with a zero limit. JavaScript now matches Python's
strict path escaping and response-envelope rules; both SDKs now report consistent
public API errors and reject zero-limit offset pagination before a request.
`npm run build` passed, and the rebuilt 27-file JavaScript npm artifact passed
the same consumer-side probes. The 6 D / 4 P / 56 B / 0 accepted capability
counts do not change: live Gateway route/auth behavior, tenant scope, and wider
SDK parity remain open. See the [Batch 5 checklist](batches.md).

## Phase 7 operations-console identity boundary — 11 October 2026

Initial repository inspection found no first-party operator web app. The Cloudflare
edge preview is synthetic-only and disconnected from KI APIs; the mobile
Field Collector is not an operator surface. The Gateway currently authenticates
protected routes with API keys or capability tokens, and treats the configured
Directus admin token as full access. It has no human browser session or
federated identity adapter. Those credentials must not be embedded in a browser
bundle. Documented a replaceable operator identity/session port, tenant and
location scope rules, stable audit actor requirements, same-origin/CSRF
boundary, a read-only first console slice, likely files, acceptance, and
rollback in [the console contract](kernel-operations-console.md). Split the
Batch 5 checklist into completed boundary documentation and pending provider
selection/implementation. No code, credentials, CORS settings, or runtime state
changed; no tests or runtime probes ran. The identity source is a product choice
before implementation; the contract recommends provider-neutral OIDC so
Directus remains optional.

## Batch 5 mobile access boundary review — 11 October 2026

Read `services/mobile/api.py`, migrations 139/215/320/322/357/358, and the
Field Collector vault. The current mobile path derives device/user/location from
the consumed enrollment and active hashed device token; it binds media uploads
and references to device, location, client ID, status, and expiry. Anonymous
forms are active public global forms; enrolled devices can read active global
and their assigned-location forms. `offline_collection` has no `party_id`,
consent event, or tenant ID, and mobile `user_id` has no enforced mapping to the
canonical party-based consent ledger. Sync also does not validate provided
form ID/version/type against an active form. Documented the boundary and these
gaps in [mobile access contract](mobile-access-contract.md), and corrected the
mobile README's migration status: schemas 357/358 are in the local candidate's
applied migration set, without enabling local media or changing legacy,
staging, or production. No runtime probe or test suite ran. No consent/form
policy or schema behavior changed. Rollback only the candidate mobile profile or
revert any future implementation; preserve encrypted media and key custody.

## Batch 5 HTTP sensor deployment contract — 11 October 2026

Reconciled `http-sensor-overlay.md` against the Compose service,
`http_sensor_receiver.py`, and `http_sensor_limits.py`. Documented private-only
port exposure, HMAC/device checks, 10 KiB single and 256 KiB batch limits,
ten-second body deadline, per-reading transaction/duplicate semantics, and
single versus batch retry behavior. Linked the earlier isolated receiver
listener/CSV/outbox evidence and clarified it did not enable the optional Compose
overlay. The overlay itself has not been built or started; runtime identity,
health, grant, timestamp, shutdown, and public-ingress gates remain open. No
source/runtime behavior changed and no test suite ran. Rollback remains removing
only the `http-sensors` overlay service; preserve database/outbox/device state.

## Batch execution — 10 October 2026

[Six-batch checklist](batches.md). **Batch 1 complete:** matching AMD64/ARM64
minimal artifacts now bundle source inventories and the public relation readiness
gate. [Build evidence](builds/2026-10-10-batch1/README.md). Running images are unchanged.
No new capability acceptance gates closed; counts remain 6 D / 4 P / 56 B / 0 accepted.
**Current batch: 2 — scoped PostgreSQL restore complete; legacy storage preservation
and populated/provider recovery gates remain in progress.**

### Batch 2 preparation update — 10 October 2026

Read-only aggregates recorded for five legacy stores; anonymous Redis and broker
log volumes now have explicit owners. Added a scoped age-encrypted PostgreSQL
checkpoint script, standalone recovery Compose destination, retention/restore
procedure and Adelphi fixture outline. [Evidence and gaps](recovery-preparation.md).
Shell syntax and Compose parsing passed; no checkpoint/restore or test suites ran.
Batch 2 remains in progress; full provider ownership and recovery acceptance open.
Running deployments unchanged; capability acceptance counts unchanged.

### Batch 2 scoped recovery performed — 10 October 2026

Portability PostgreSQL encrypted checkpoint restored successfully into a fresh,
isolated database. All 364 migration fingerprints, extension versions and eight
selected aggregate counts match. Selected workload/media tables are empty; active
work and media recovery remain unproven. Stopped legacy Redis/broker files archived
with age encryption; logical session/message inventory and archive restore pending.
Recovery container stopped with volume retained; source deployments unchanged.
[Retained evidence](builds/2026-10-10-recovery/README.md). No acceptance suites run. Batch 2 stays open
for complete provider ownership, independent backup copy and populated recovery.

### Batch 2 legacy preservation — 10 October 2026

All ten locally attached legacy volumes and selected configuration captured in
a finalized age-encrypted archive; source containers remained stopped. Sizes and
image/volume mappings retained. External-setting presence inspected without values;
no configured Prefect/mobile storage settings found in the inspected local scope.
[Preservation scope and restore procedure](legacy-storage-preservation.md). Logical provider
state and populated job/media recovery remain open; no capability acceptance closed.
User deferred independent R2 production backups and authorized a local development
mirror under backups/development-mirror/. Same-disk copies are not independent
production protection. Running Kernel services unchanged; no test suites ran.

Local development mirror completed with matching ciphertext/metadata SHA256;
independent production backup remains deferred to the release batch.

### Batch 2 provider clone inventory — 10 October 2026

Isolated copied Redis/PostgreSQL engines loaded successfully: Redis has four string
keys without expiry; Metabase contains 39 cards and one dashboard. Four PostgreSQL
databases and globals captured into age-encrypted logical archives, with matching
development mirror checksums. Broker clone counters are ambiguous/anomalous and
do not certify application backlog. [Evidence and limits](provider-clone-inventory.md).
All clones stopped; original legacy services/storage unchanged. No test suites ran.
Batch 2 remains open for populated recovery, provider semantics and logical archive
restore. No capability acceptance counts changed.

### Batch 2 populated legacy database restore — 10 October 2026

All four legacy logical archives restored into fresh isolated databases on the
compatible recorded image. Counts and whole-row comparison fingerprints match for
13 selected tables, including populated events, sensors, weather, wallets,
attestations and Metabase cards/dashboard. [Restore evidence](legacy-logical-restore.md).
Both recovery engines stopped and volumes retained. Original legacy and running
Kernel deployments unchanged. Globals/grants were not applied; no active workload
or uploaded media exists in the selected source. Batch 2 remains open for those
recovery gates, broker/ClickHouse and external ownership. No acceptance suites ran
and no complete capability acceptance counts changed.

### Batch 2 analytics and broker inventory — 10 October 2026

Compatible isolated ClickHouse copy loaded: 34 analytics objects in default, zero
active non-system rows/parts, expected kokonut_analytics empty. Schema definitions
encrypted and mirrored; complete object metadata retained. Original broker file
scanned offline: version 6, one configuration chunk, zero message/client/subscription
chunks. [Evidence and limits](analytics-broker-recovery.md). Original services remain stopped;
ClickHouse clone stopped with volume retained. No acceptance suites ran. Full
analytics output/restore and transport recovery remain open; capability counts
unchanged. Redis semantics, active work/private media and permissions still pending.

### Batch 2 work/media recovery preparation — 10 October 2026

Added quiesced local-media checkpoint and exclusive staged restore commands, with
ciphertext/object hashes, database checkpoint binding and secret custody labels.
Defined exact isolated lease/window/event/delivery/dead-letter/device/media fixture.
[Commands, fixture and gates](work-media-recovery.md). Both scripts passed Ruff; no media
commands, fixture records or acceptance suites executed. AES/key/DB-reference
authentication and active-work recovery remain open. Running deployments unchanged.

### Batch 2 guarded fixture preparation — 10 October 2026

Added standalone private fixture deployment and guarded transactional disabled
durable-work seed loader. Checks dedicated project/image/volume/network/roles and
all bundled migration checksums before insertion. [Setup and limits](recovery-fixture-setup.md).
Ruff and Compose parsing passed. Deployment not started, SQL not applied, no
acceptance suites run. Device/media loader and exercised recovery gates remain
open; no phase/capability acceptance counts changed.

### Batch 2 device/media loader preparation — 10 October 2026

Added authenticated two-object synthetic media loader and transactional device/
collection/reference seed. Shared full target/schema guard extracted for both
loaders. AES-GCM associated-data, JPEG size/hash and exact scope validated before
insertion; no device/enrollment authority minted. [Inputs and limits](recovery-media-fixture.md).
Ruff passed. No fixture provisioned or SQL applied; acceptance suites not run.
Paired recovery, stale ownership, replay/disposal and enrollment/consent remain open.

### Batch 2 exercised synthetic recovery — 10 October 2026

With explicit user authorization, provisioned the private fixture and restored
364 checksummed schema records. Applied disabled work and two authenticated
synthetic media records. Captured a quiesced paired encrypted DB/media checkpoint;
restored DB into fresh `recovery_roundtrip` and media into an unused private directory.
All 12 selected whole-row count/fingerprints match. Both restored objects authenticate
with the separately age-encrypted development AES key. Wrong key, changed associated
data, duplicate work/media seeds, reused restore destination and capture without
quiescence were rejected. Actual scheduler code recovered the expired lease,
retained its original window, advanced retry to 2 and rejected stale completion;
no job dispatched. Fixture stopped after checks; volumes and checkpoints retained.

[Sanitized results](builds/2026-10-10-recovery/fixture-roundtrip.json).
Backups/key custody: ignored `backups/recovery-fixture-20261010/`; the key itself
is only persisted as `media-key.age`. This is a local development recovery exercise.
Live enrollment/consent, handler effects/replay/disposal, role/grant policy,
external provider ownership, production/Pi certification and full recovery acceptance
remain open. Batch 2 stays active; no capability is fully accepted.

### Batch 2 event recovery exercised — 10 October 2026

After the host restart, started only the retained private recovery fixture for
this slice. Host project/image/volume/network/schema guard passed. Eight synthetic
event checks passed against real PostgreSQL: expired lease reclaim/stale owner
rejection; successful delivery skipped on retry; bounded retries to dead letter;
audited replay with duplicate rejection and successful-delivery preservation;
orphan replay rejection; operator identity/reason requirements; audited disposal
with duplicate rejection. Handler invocation used controlled outcomes; no domain
handler or external effect ran. Synthetic handlers disabled again on exit.

[Evidence](builds/2026-10-10-recovery/fixture-events.json).
Reproducible guarded launcher: `bash scripts/kernel-recovery-event-checks.sh`
after loading encrypted secrets and starting the fixture. This mutates the exact
seeded event fixture and is intentionally not repeatable against completed state:
restore the retained pre-exercise checkpoint into a separately reviewed fresh
fixture before another run. Never rerun its seed into existing work tables.
The first attempt stopped before claiming work because a check assumed no standard
handler registrations; corrected to inspect the synthetic event type only.

Fixture stopped afterward; volumes/backups retained. Legacy stack remains stopped.
Candidate services restarted automatically; portability services remain stopped
following the host restart. No deployment promotion occurred.
Actual handler side effects/idempotency, child-process timeouts, concurrent workers,
roles/grants and provider ownership still require evidence. Batch 2 remains active;
no capability becomes fully accepted.

### Batch 2 legacy authorization recovery — 10 October 2026

Read-only metadata from all four isolated source databases excludes password hashes.
One custom role (`kokonut`) is superuser with create-role/create-database,
replication and bypass-RLS privileges. No custom memberships, default ACLs or
row-security tables were found. Ownership and explicit object ACLs matched all
four logical restores. Main database schema ACLs initially differed because
no-privileges dumps omit grants. Rehearsed two explicit schema grants only on
the isolated logical restore; all selected main-database catalog fields then matched.
Both recovery clones stopped; original databases and encrypted globals unchanged.

[Inventory](builds/2026-10-10-recovery/legacy-authorization.json),
[before comparison](builds/2026-10-10-recovery/legacy-authorization-comparison.json),
[grant rehearsal](builds/2026-10-10-recovery/legacy-authorization-grants-rehearsal.json).
Recovery compatibility policy: create the recorded database owner under private
operator custody, restore no-owner/no-privileges archives, review source catalog
metadata, then apply only explicitly reviewed grants. Never replay encrypted
globals blindly or print their credentials. The isolated SQL fixture is not a
production migration and must not be added to ordered schema files.

Production policy remains open: separate migration/operator and runtime roles,
restrict privileges to actual service needs, and verify runtime denial of DDL,
role creation and unrelated databases alongside required domain workflows.
Legacy superuser parity does not satisfy that gate. Batch 2 remains active.

### Batch 2 Redis ownership assessment — 10 October 2026

Inspected the retained no-network Redis clone without printing key identities or
values. Four db0 string keys have no Redis expiry. Three are source-mapped against
the exact retained Directus image: two API request telemetry counters and one
collaboration instance registry. These are not evidence of governed domain state
or queued jobs. One opaque key remains unclassified; retain the encrypted RDB and
original volume, and leave Redis retirement blocked pending its ownership review.

[Sanitized evidence](builds/2026-10-10-recovery/redis-ownership.json).
Pinned source paths: `middleware/request-counter.js`,
`telemetry/counter/use-counters.js`, `websocket/collab/messenger.js`,
`websocket/collab/store.js`, `utils/store.js` in the retained Directus image.
Telemetry counters stay archived; they must not become native rate-limit state.
Collaboration presence is runtime state: archive it, reconnect clients and recreate
instance identity when restoring the optional adapter. Do not import stale
presence into Kernel domain tables. No Redis keys deleted or rewritten; clone stopped.

Kernel computation cache remains PostgreSQL-backed (`services/cache/cache.py`),
and native gateway rate-limit state has its own provider boundary and PostgreSQL
schema. Directus Redis settings remain optional-adapter concerns; clustered Directus
cache/collaboration/limit behavior still needs adapter acceptance before changing
its deployment. Source mapping is not live Redis-free Directus certification.
Batch 2 remains active; no capability promoted to fully accepted.

### Batch 2 final Redis key mapped — 10 October 2026

All four retained db0 keys now have source-backed owners. The remaining `rlflx`
namespace is the pinned rate-limiter-flexible default. Directus authentication
constructs a limiter with `duration: 0` and consumes by `user.id`; privately matched
the retained UUID to `directus_users` in the isolated legacy PostgreSQL clone.
Only a boolean match is retained, with hashed key identity; no UUID or counter
value is published. This is a persistent failed-login counter, not disposable
cache or native gateway rate-limit state. No source keys/grants/data modified.
Both recovery clones stopped after inspection.

[Updated evidence](builds/2026-10-10-recovery/redis-ownership.json).
Redis ownership inventory is complete for the retained local snapshot. Retirement
remains open: optional Directus must preserve this security counter in compatible
Redis state, or use an explicitly reviewed transfer/reset policy with login lockout
acceptance checks. Native gateway token buckets do not replace failed-login policy.
Do not clear Redis wholesale or promote a Redis-free Directus deployment based
on the telemetry/presence classifications. Original volume and encrypted archives
remain the rollback source. Live lockout behavior and provider parity remain open.
Batch 2 stays active; no capability fully accepted.

### Batch 2 ClickHouse database reconciliation — 10 October 2026

Found the bootstrap selecting no database while repository SQL uses unqualified
object names. Legacy objects therefore reside in `default`, whereas service
clients/analytics profiles select `kokonut_analytics`. Corrected `scripts/seed.sh`
to validate a simple `CH_DB` identifier and explicitly select it for readiness
and schema application; no historical SQL files edited. Shell syntax passed.
In the isolated retained clone, the configured database was empty. Applied all
six repository schema files twice successfully, creating 34 objects; default
name/engine/row inventory unchanged. This is a rehearsal, not deployment promotion.

[Bootstrap evidence](builds/2026-10-10-recovery/clickhouse-target-bootstrap.json).
A synthetic sensor projection inserted values 10,20 and then 30 in separate blocks.
Raw and summary counts equal 3, but sum of per-block summary averages is 45 versus
raw average 20. `mv_daily_sensor_summary` uses SummingMergeTree with ordinary
average/min/max/uniq outputs; those statistics cannot safely be summed across
blocks. This is a failed analytics parity gate, not an accepted projection.
[Projection evidence](builds/2026-10-10-recovery/clickhouse-sensor-projection.json).

Batch 4 must introduce versioned corrected rollups using aggregate states or
sum/count plus proper min/max/distinct aggregates, audit all analogous views,
rebuild from retained raw data with explicit backfill, update consumers, and
exercise multi-block/merged output against PostgreSQL queries. Preserve old
views/data until parity passes; never silently replace their definitions.
Legacy physical application tables had zero rows, so no populated historical
transfer was inferred. New synthetic rows exist only in the recovery clone;
clone stopped afterward. Original legacy storage and running deployments unchanged.
Batch 2 remains active for external ownership and remaining recovery gates.

### Versioned sensor rollups exercised — 10 October 2026

Added schema 007 with aggregate-state materialized views and finalized v2 daily/
rate read interfaces; historical schemas/views unchanged. Isolated quiesced
backfill, subsequent separate blocks and FINAL merge outputs match raw aggregates
for all fields, including exact distinct sensors/locations and suspect readings.
No deployment promotion or consumer switch. [Migration, rollback and evidence](sensor-rollups-v2.md).
Batch 2 stays active; PostgreSQL/outbox/dashboard parity and other rollups remain open.

### Remaining analytics rollups corrected — 10 October 2026

Audited all 11 materialized definitions in schemas 002/003/006. Added versioned
raw read interfaces in schema 008 for monthly distinct wallets, both Digital Lego
rollups with missing merge-key dimensions, and remote-sensing non-additive
statistics. Historical definitions retained. Reapplication, separate-block fixtures,
nullable statistics, dimension preservation and before/after FINAL merge checks
passed in the isolated clone; clone stopped. [Interfaces, audit and evidence](analytics-read-views-v2.md).
No saved dashboard switch, running deployment promotion or full analytics acceptance.
PostgreSQL/outbox parity and raw-view resource measurements remain open.

### Durable outbox recovery exercised — 10 October 2026

Hardened enqueue: a reused event key requires identical hash, source/target,
columns and rows; conflicting projection raises for caller rollback. Completion
now requires an unexpired lease as well as owner/token. No SQL migration changed.
Seven PostgreSQL-backed isolated checks passed: caller rollback, matching-key
idempotency/conflict rejection, paused-provider retry preservation, expired lease
reclaim/stale completion rejection, eight-attempt dead letter, replay/duplicate
rejection and successful delivery not reclaimed. Ruff passed.
[Evidence](builds/2026-10-10-recovery/fixture-outbox.json).

Execution used pinned fixture operator plus a read-only mount of changed outbox
source; this does not certify the unchanged deployed image. Fixture retains one
synthetic succeeded outbox record; check intentionally refuses nonempty outbox
on rerun. Recovery checkpoint and volumes retained; fixture stopped afterward.
Transport results were controlled: no live ClickHouse driver delivery or
PostgreSQL-v2 output parity claimed. Cross-store crash after insert/before ack can
still duplicate analytics rows; requires explicit delivery identity and proven
sink deduplication/reconciliation. Outbox replay currently lacks actor/reason audit
and needs alignment with event dead-letter governance before acceptance.
Batch 2 stays active; these are preparatory Batch 4 durability checks.

### Outbox operator auditing exercised — 10 October 2026

Added ordered schema 374 and atomic audited replay/disposal with required actor/
reason, retained attempts/hash and duplicate rejection. Explicit host migration
runner applied one migration to fixture only (365 schemas); four isolated checks
passed, including forced audit insert failure rolling back state. Ruff passed.
[Interfaces, deployment and rollback](outbox-operator-audit.md).
Initial attempt to invoke the Compose-based migration CLI inside the operator
failed because Docker is absent there; no migration applied in that attempt.
Host invocation with explicit fixture selection succeeded. Running images unchanged.
Recovery fixture stopped and records retained; full operator role/identity policy,
concurrent actions and live sink crash deduplication remain open. Batch 2 active.

### Live outbox recovery exercised — 10 October 2026

Fixed ingestion CH_DB selection and JSON-persisted payload transport; added stable
insertion tokens/bounded raw-table block windows and NULL sensor plot handling.
Real driver crash-before-ack replay passed against new raw sensor v3 read views;
three outbox payloads yield three raw rows, average 20. V2 materialized summaries
failed replay parity even with dependent-view setting; failure slices retained.
[Exact limits, failure evidence and deployment](live-outbox-recovery.md).
Fixture roles stopped afterward; production/legacy unchanged. Canonical domain
source ingestion, restarts/concurrency/window eviction and full parity remain open.
Batch 2 stays active. Earlier sensor-v2 arithmetic checks did not cover this crash
case; v3 now supersedes v2 as the recommended sensor read interface.

### Canonical sensor ingestion recovery — 10 October 2026

Transactional producer now projects stored PostgreSQL precision/unit and actual
reading UUID through the shared outbox helper; enqueue failures propagate. Same
sensor/timestamp conflicting value/quality is rejected. Five real PostgreSQL/live
ClickHouse checks passed, including source rollback, retry identity and v3 parity.
Ruff passed. [Evidence, migration/rollback and limits](canonical-sensor-recovery.md).
Fixture roles stopped; running deployment unchanged. Legacy hash-keyed projections
require reconciliation before producer promotion; full CSV/HTTP, concurrent source
writes and field device authority remain open. Batch 2 still active.

### Batch 2 single-reading sensor path — 10 October 2026

Ran the normal `run_single` producer in the isolated recovery fixture. Two source
rows, platform events, distinct succeeded outbox records, raw ClickHouse rows and
the v3 daily summary match. The first post-delivery read did not see the rows in a
five-second window; a later read-only verification confirmed parity. No latency
guarantee is inferred. [Scope and evidence](sensor-entrypoint-recovery.md).
Ruff passed; no Python acceptance suite ran. Both fixture services stopped with
volumes retained. Legacy lineage, CSV/HTTP, handler effects, concurrency/restart,
operator authorization and dashboard parity remain open; Batch 2 stays active.

### ClickHouse first-read visibility trace — 10 October 2026

Sanitized query-log evidence confirms both inserts and 44 immediate reads used
`kokonut_analytics`; inserts and reads reported no exceptions. The reads found no
rows within five seconds, while a later query found both sensor-date rows. Effective
settings had async inserts and query cache disabled, so those factors do not explain
the delay. Root cause and delivery-visibility contract remain open; no latency
guarantee or capability acceptance is inferred. [Evidence](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json).
The isolated analytics service is stopped with volumes retained; no application
deployment changed.

### Batch 2 CSV and authenticated HTTP sensor entrypoints — 10 October 2026

Fixed FastAPI route annotation resolution and added HTTP `sensor_reading` event
publication through the shared event-store adapter in the source/outbox
transaction. Isolated rehearsal accepted two CSV rows and three authenticated
HTTP rows; rejected one malformed timestamp and an invalid HMAC with 401. Five
source rows produced five pending platform events and five succeeded outbox rows.
Raw ClickHouse rows and the v3 location/day/type summary match. The first read was
immediate; the earlier delay remains unexplained. [Evidence and limits](sensor-entrypoint-recovery.md).
Ruff and diff checks passed; no Python test suite ran. At that point, event handlers
remained unprocessed, and HTTP used in-process ASGI rather than a network listener.
Batch 2 remains active; CAP-040 stays P.

### Batch 2 selected sensor handler and receipt recovery — 10 October 2026

Processed only the synthetic low-moisture `sensor_reading` event in the isolated
fixture. Runtime execution exposed and fixed three handler defects in
`services/ingestion/anomaly_detector.py`: UUID/text comparison in the device lookup,
a missing current-value argument for rate-of-change evaluation, and a UUID-valued
alert-event JSON field. The bounded retry completed with one warning alert at
reading 10; three earlier failed attempts remain in the durable delivery/log history.
After a controlled return to processing with a new lease owner, the successful
handler receipt skipped re-execution: attempt/log/alert counts did not change. Four
sibling sensor events remain pending and the generated `sensor_alert` event remains
pending. SMTP, Directus and actuator outputs were disabled. [Sanitized evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json).

This is a controlled receipt-recovery simulation, not a process-kill, concurrent
worker, or queue-wide run. No schema migration or pytest suite ran. After evidence
capture, only the fixture database was stopped; analytics stayed stopped and the
volumes/checkpoint were retained. The HTTP listener/proxy, broader handler behavior,
legacy lineage, runtime-role policy, restart/concurrency, dashboards and full
provider recovery remain open. Batch 2 continues; CAP-040 stays P.

### Batch 2 HTTP listener over the isolated network — 10 October 2026

Before writes, created encrypted PostgreSQL checkpoint
`backups/recovery-fixture-pre-http-listener-20261011T024804Z` (restore not
rehearsed). Ran the actual receiver in a temporary operator container and sent
requests from a second container on the fixture's internal Docker network; no host
port was published. Health returned 200, invalid HMAC returned 401, authenticated
single and two-item batch requests succeeded, a repeated reading returned duplicate,
and a signed URL/payload device mismatch returned 400. PostgreSQL shows three
distinct source readings, three pending `sensor_reading` platform events and three
pending ClickHouse outbox rows. No ClickHouse worker or event handler ran. The
temporary credential was removed and the synthetic device restored to inactive.
[Sanitized evidence](builds/2026-10-10-recovery/sensor-http-listener.json).

The request assertions completed; the probe's final report-file write failed because
its host temp path was not mounted into the client container. Uvicorn access logs
and a separate read-only SQL query confirmed the HTTP status codes and persisted
counts. Pydantic v2 emitted deprecation warnings for `.dict()` calls, without
affecting the requests. TLS, proxy, host-published ingress, concurrent requests,
ClickHouse delivery and handler execution remain open. The encrypted checkpoint
and fixture volumes are retained; the fixture database and legacy stack are stopped.
Batch 2 remains active; CAP-040 stays P.

### Batch 2 retained local sensor lineage reconciliation — 10 October 2026

Read-only inspection of the isolated, no-network legacy PostgreSQL recovery clone
found 15 sensor source rows with 15 distinct reading IDs and zero ClickHouse
outbox rows. The retained ClickHouse inventory has zero physical rows in
`default.sensor_readings`. No historical local projection needs re-keying or
replay beside the canonical UUID-keyed producer. This does not establish remote
or unarchived sink state; any populated external target still requires independent
source/sink reconciliation before promotion. The clone was stopped after
inspection; no sensor values or original source/archive data were changed.
[Sanitized evidence](builds/2026-10-10-recovery/legacy-sensor-lineage.json).

This closes only the retained local snapshot lineage item. Batch 2 remains active;
CAP-040 remains partial while TLS/proxy, concurrency/restart, broader handlers,
external target ownership, dashboard parity and full transport acceptance remain
open.

### Batch 2 HTTP listener ClickHouse follow-up — 10 October 2026

Created an encrypted PostgreSQL checkpoint before changing fixture delivery state
and verified it by decrypting to `/dev/null`; restore remains unrehearsed. A
read-only query confirmed the three target sources were created after the exact
pre-listener checkpoint timestamp. In the isolated recovery deployment, the
existing outbox function claimed only the three canonical HTTP listener projections; all
three succeeded on attempt one. ClickHouse has one exact-value row at each source
timestamp. Three unrelated ready outbox rows were held only for batch scoping and
their original availability times were restored.

A broad per-device pending-event count initially included older fixture events. A
read-only follow-up keyed by the three source UUIDs confirmed all three listener
events remain pending with no handler deliveries or logs. No event processor ran.
The database and analytics containers were stopped with volumes retained. [Sanitized
evidence](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json).

This completes only the synthetic listener-to-ClickHouse projection slice. Batch 2
remains active; CAP-040 remains partial while TLS/proxy, restart/concurrency,
broader handler behavior, external target ownership, dashboard parity and full
transport acceptance remain open.

### Optional Kernel Caddy localhost TLS check — 10 October 2026

Validated the pinned Caddy configuration and exercised HTTPS against the existing
healthy candidate app from a private Docker network. The explicit local CA and
`localhost` hostname validated; `/health` returned 200, HTTP redirected with
308, the three configured security headers were present, and an unauthenticated
unknown route remained 401. The local certificate remained usable after
container recreation with its dedicated volume retained. The final proxy had no
host port bindings; the existing candidate app retained its prior loopback
8098 binding and was not rebuilt or restarted. The legacy stack remained
stopped. Normal gateway access auditing ran for the HTTPS requests; no domain
records or migrations were written. [Scope and evidence](kernel-proxy.md),
[sanitized result](builds/2026-10-10-recovery/kernel-proxy-runtime.json).

An initial disposable Compose attempt retained the default loopback mappings
because `ports: []` merged instead of resetting; it was stopped before probe
traffic. The corrected resolved model used `!reset []` and was verified to have
no host bindings. This check does not cover public ingress, mobile/upload parity,
header spoofing/audit identity, CORS, rate limits, or production certificate
recovery. CAP-040 and Phase 6 remain partial.

### Optional Caddy forwarded-header audit identity check — 10 October 2026

Through the private Caddy proxy, sent one request to a unique unknown route with
forged `X-Forwarded-For`, `X-Real-IP`, and `Forwarded` values. The gateway
returned 401. A read-only query restricted to that exact request path found one
denied audit row whose IP matched the Caddy container's upstream peer address
and none of the supplied addresses. This confirms the selected single-hop
Caddy path honors the gateway's `proxy_headers=False` behavior. The synthetic
denied access-audit record intentionally remains in the candidate database; no
farm/sensor domain data or schema changed. [Evidence](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json).

This does not define trusted client IP handling for other ingress layers or
multiple proxy hops, and does not validate rate limiting or public exposure.
Phase 6 and CAP-040 remain partial.

### Optional Kernel Caddy loopback-published ingress check — 10 October 2026

The first host-level HTTP probe found that Caddy's default HTTPS redirect
omitted the nonstandard published TLS port. Updated the Kernel Caddy config to
redirect through `KOKONUT_KERNEL_HTTPS_PORT` (default `8448`) and passed that
setting into the proxy container. After recreating the proxy, the host-published
HTTP endpoint at `127.0.0.1:8088` returned 308 to
`https://localhost:8448/health`; following it with the local CA explicitly
trusted and hostname verification enabled returned 200. The container bound
both ports only to `127.0.0.1`. [Evidence](builds/2026-10-10-recovery/proxy-loopback-ingress.json).

The existing candidate app and database were not rebuilt or restarted; the
legacy stack remained stopped. The health request traversed gateway middleware,
but audit persistence was not queried. No domain writes or migrations were
issued. The temporary proxy project and volumes were removed. Non-loopback or
public ingress, mobile/upload parity, CORS, rate limits, multi-hop trusted
proxies, and production origin/cookie behavior remain open. Phase 6 and CAP-040
remain partial; no pytest suite ran.

### Optional Kernel Caddy configurable HTTPS port check — 10 October 2026

Used a separate temporary Compose project with HTTP `18088` and HTTPS `18448`.
Compose published both ports only on loopback and passed `18448` into Caddy.
HTTP redirected to `https://localhost:18448/health`; the CA-verified,
hostname-verified follow-up returned 200 after one redirect. This checks that
the environment override stays aligned between Docker port publication and
the redirect. The candidate app/database were reused without restart; the
temporary proxy and its volumes were removed, and the legacy stack remained
stopped. [Evidence](builds/2026-10-10-recovery/proxy-custom-port.json). No
domain writes, migrations or pytest suites ran. Public ingress and the remaining
Phase 6/CAP-040 acceptance work remain open.

### Kernel gateway CORS preflight check — 10 October 2026

Read the active gateway's explicit localhost origin list and sent two direct
loopback `OPTIONS` preflights to `/health`. `http://localhost:3000` was allowed
for `GET` with `x-api-key`; `https://untrusted.invalid` received 400 without an
allow-origin header. The preflight path does not enter gateway audit/rate-limit
middleware. A separate reachability `GET /health` traversed normal middleware;
audit persistence was not queried. No farm/sensor domain writes or migrations
were issued. [Evidence](builds/2026-10-10-recovery/proxy-cors-preflight.json).
Authenticated response CORS, credentials, mobile/media paths, public origins
and rate limits remain open; Phase 6 and CAP-040 remain partial.

The follow-up CORS response probe sent two unauthenticated GETs to a unique
unknown path. Both returned 401; the configured origin received the matching
allow-origin header and the untrusted origin did not. A read-only exact-path
query found the two expected denied `credentials_required` audit rows, retained
in the candidate database. No domain data or schema changed. [Evidence](builds/2026-10-10-recovery/proxy-cors-auth-response.json).
At the time of the CORS probe, the running candidate image predates the new
rate-limit provider module, so no runtime result was claimed from that container.

### Kernel gateway rate-limit source-path check — 10 October 2026

At the time of this source-path check, the deployed candidate image predates
`services/gateway/rate_limit_backend.py`.
A disposable network-isolated container used the current workspace `services/`
as a read-only mount and injected a one-token in-memory limiter. A health GET
returned 200; configured-origin preflight still returned 200 after that token
was spent; the next GET returned 429 with `Retry-After: 100` and the configured
CORS allow-origin header. The audit method was monkeypatched to capture one
allowed 200 and one denied `rate_limited` 429 in memory. No candidate service,
database, persistent audit, domain data or schema was touched. [Evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json).

This proves only the current-source ASGI middleware path with injected test
settings. It does not certify deployed defaults, persistent audit, the
PostgreSQL shared adapter, concurrency, eviction/restart or multi-replica
behavior. Rebuild before runtime acceptance; Phase 6 and CAP-040 remain partial.
No pytest suite ran.


### Kernel gateway local limiter runtime and promotion — 10 October 2026

Rebuilt the candidate app image and ran an API-only canary on loopback port
18098 against the existing private candidate database. The configured provider
was `local`; current source defaults are 100 tokens with a 10-token/second
refill. A 2.766-second sequential burst allowed 127 `GET /health` responses,
then returned 429 with `Retry-After: 1` and the configured CORS origin. OPTIONS
preflight from that origin returned 200 after exhaustion; the next GET returned
429. A read-only query confirmed 127 allowed and two denied `rate_limited` audit
rows for the accepted probe, intentionally retained.

The rebuilt image was promoted to the active candidate app. It is healthy and
serves `/health` with the configured CORS header; the PostgreSQL container and
volume were not recreated. A credential-free filesystem rollback image was saved
before replacement. Exploratory probe rows are separately listed in the
[evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json).

This accepts only the single-process local limiter runtime. PostgreSQL shared
limits, concurrency, restart/eviction policy, multiple replicas, public ingress,
and broader authenticated/mutation CORS remain open. No migrations, domain
writes or pytest suites ran. Phase 5/6 and CAP-040 remain partial.

### Batch 2 GatewayAudit outage and recovery boundary — 11 October 2026

The initial isolated stop/restart probe characterized the pre-journal behavior:
the event attempted during downtime was absent after PostgreSQL returned, while
a new control event persisted. This is retained as historical baseline evidence
and is superseded by the implementation and recovery check below.
[Historical evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).

### Batch 2 bounded GatewayAudit journal and replay — 11 October 2026

Added a standard-library SQLite journal for failed audit writes, stable event
UUIDs and occurrence timestamps, idempotent PostgreSQL inserts, a 10,000-event
default queue cap, a 16 KiB event cap, private file checks, Compose named-volume
mounts, and a FastAPI startup/15-second replay worker. The real ASGI outage
request returned 503 with `Retry-After: 30` and queued one row. After replacing
the app container while retaining its volume, the startup worker replayed the
event once without another request, preserved `created_at`, and drained the
journal. The duplicate event ID remained one database row; a one-event
configured cap rejected a second enqueue; file mode was 0600.
[Implementation details](gateway-audit-spool.md), [sanitized recovery evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).

No migration or domain write occurred. The exact synthetic audit row, temporary
app containers and temporary spool volume were removed; the portability
database returned to its previous stopped state, and the active candidate was
not touched. No pytest suite ran. CAP-040 remains partial: saturation,
volume/host loss, encrypted retention and live-volume restore, candidate
activation, replica failover/scale and production ingress need separate
acceptance. The PostgreSQL rate-limit
provider remains opt-in; the active candidate continues to use local limits.

### Batch 2 audit journal checkpoint and crash recovery — 11 October 2026

Added `services.gateway.audit_spool_cli`, mounted as `services.cli audit-spool`,
for status, integrity verification, SQLite online checkpoint and restore to a
new path. The status command leaves an absent journal absent. In a private
synthetic fixture, a committed enqueue
survived abrupt writer-process exit; an uncommitted insert rolled back. A
checkpoint remained a consistent one-event snapshot after a second event was
added to the live source. Restore preserved the event ID, wrote mode 0600, and
refused to overwrite an existing destination. The source held two events after
the checkpoint; all temporary fixture data was removed.
[Runbook and limitations](gateway-audit-spool.md), [sanitized evidence](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).

This accepts only the CLI and local SQLite process-exit/checkpoint recovery
boundary. Encrypted retention/transfer, actual installation into a stopped
Compose volume, physical-device/power failure, external alert routing and
production retention ownership remain open. A separate temporary container from
the rebuilt portability image ran unified-CLI status with no database or spool
volume mounted. Checkpoint/verify/restore also ran in the temporary image
container with a private bind fixture; candidate containers stayed healthy and untouched.
[Image check](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).
No migration, domain write or pytest suite ran.

### Batch 2 concurrent audit journal writers and online checkpoint — 11 October 2026

The first cold-start contention probe exposed a reproducible SQLite lock race:
3 of 8 processes failed during simultaneous WAL/schema initialization. Added
bounded retry with capped exponential backoff for transient `busy`/`locked`
initialization errors in `services/gateway/audit_spool.py`. After the change,
three cold-start runs each committed all 144 events from 12 writer processes
with clean integrity checks. Ten warm writers committed 201 events including a
seed event. A separate online checkpoint ran during active writes: all 8 writers
were still active when it returned, the checkpoint contained a valid 166-event
snapshot, and the source completed with 481 events. No writer errors occurred.
[Sanitized evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json).

Temporary fixtures were removed. No Compose stack, migration, domain write or
pytest suite was touched. This closes local SQLite process-contention coverage;
device/power loss, volume/host loss, external alert delivery, approved retention
and live-volume restore remain open. CAP-040 stays partial.

### Batch 2 audit journal saturation alert and write guard — 11 October 2026

Added an absolute queue alert threshold, defaulting to 80% of the configured
cap, and passed its override through the candidate and portability Compose
profiles. `services.cli audit-spool status` now reports count, cap, threshold,
alert and write-restriction state without printing records. `/health` reports
`audit_capture` as `ok`, `degraded` or `unavailable`. Before a non-read handler,
the middleware replays pending records, checks capacity and commits/removes a
small SQLite write probe. At/above threshold or on detected storage failure it
returns 503 with `Retry-After: 30` before handler execution. The guard logs a
state transition once per process; reads remain available.

In the private ASGI fixture, four of five queued records crossed a configured
threshold of four and the synthetic mutating handler was not called. Removing
one event allowed the handler to run. Removing a journal file after the process
had observed it, or pointing at a path whose parent was a regular file, blocked
the handler and reported unavailable. An injected `ENOSPC` probe error also
returned 503 before handler execution; no real disk was filled. The CLI kept an absent journal absent,
reported a 4/5 queue as alerting/restricted, and exposed no event payload. The
transactional capacity probe left no retained probe record. All fixtures were
removed; no Compose service, migration or domain row was changed. No pytest
suite ran. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json).

CAP-040 remains partial: physical-device/power failure, lost-volume detection
after process restart, external alert delivery, approved retention ownership,
cross-process/multi-worker admission races, live-volume restore and multi-replica
recovery remain open.

### Batch 2 audit mutation admission reservations — 11 October 2026

Added an in-process reservation around mutating gateway requests. Admission now
counts outstanding mutations against the journal threshold and holds each slot
through handler completion and audit capture; `finally` releases the slot after
both successful and exceptional handler paths. This prevents concurrent
requests in one gateway process from each claiming the same remaining headroom.

A private synthetic spool at 3/4 threshold admitted one of 32 concurrent thread
callers, released the reservation, and admitted a later call without changing
the three queued records. An ASGI fixture confirmed reservation → handler →
audit → release order on success and error. Ruff, compileall and diff checks
passed. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).

This is single-process admission evidence only. Cross-process/multi-worker
coordination was still open at that checkpoint. Queue pressure from concurrent
read/denial audits, power/device failure, external alert delivery and approved
retention remain open. No Docker service, database, migration or domain row was
changed; no pytest suite ran. CAP-040 remains partial.

### Batch 2 cross-worker audit reservations and stale-owner recovery — 11 October 2026

Moved admission reservations into SQLite transactions and tied them to private
POSIX advisory owner locks. Sixteen local worker processes sharing one journal
at 3/4 threshold admitted exactly one mutation. After a worker was terminated
with `os._exit` while holding a reservation, the next write preflight detected
the released OS lock, removed the stale reservation and admitted a new request.
ASGI fixtures confirmed successful and error audit events are queued before the
reservation is released; a synthetic outage also confirmed a later write is
blocked before its handler. A forked worker retained the parent's active
reservation under a distinct owner lock. An injected release-storage failure
was logged and its orphan slot was reclaimed on the next preflight. A health
read's own queued audit event demonstrated that read traffic can consume
remaining spool capacity.

Ruff, compileall and whitespace checks passed. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).
This covers local processes on one POSIX filesystem only. Multi-host filesystems,
independent replicas/failover, power/device failure, external alert delivery and
approved retention remain open. No Compose service, database, migration or
domain row was changed; no pytest suite ran. CAP-040 remains partial.

### Batch 2 concurrent event-handler effect — 11 October 2026

Restored the retained encrypted recovery checkpoint into a new private Compose
project on its recorded PostgreSQL image. Four separate operator containers
concurrently processed 16 synthetic `metric_computed` events in batches of four.
An in-flight query observed six completed and ten processing events across four
worker IDs. All workers finished four events each with zero failures. The real
allowlisted cache handler invalidated 16 marked analytics entries for one
synthetic location while preserving three sentinel entries for another. All 16
delivery receipts and logs succeeded on attempt one, and every event lease was
released. [Details](event-handler-concurrency.md), [machine evidence](builds/2026-10-11-recovery/event-handler-concurrency.json).

The Compose network was internal and published no host ports; the recovery
database is stopped with its volume retained. Candidate API/database containers
remain healthy and unchanged; legacy services remain stopped. One unrelated
expired synthetic event from the checkpoint was briefly deferred from the global
worker and its original lease timestamp restored exactly afterward. No migration,
domain record or external integration changed. The scoped probe helper passes
Python syntax and whitespace checks; no pytest suite ran. This adds one
concurrent cache-handler effect, not same-event retry/crash or exactly-once
external-effect evidence. Additional handlers, runtime-role policy, provider
ownership/recovery and CAP-040 parity remain open; Batch 2 stays active.

### Batch 2 CRISP cache-handler effect — 11 October 2026

Reused the isolated restored checkpoint and guarded probe to insert 16 synthetic
`crisp_scored` events, 16 target CRISP cache rows, and three sentinel rows. Four
operator containers were launched concurrently; final PostgreSQL ownership
shows four events completed by each of four worker IDs. The allowlisted
`handle_crisp_scored` handler invalidated the 16 target entries with the expected
reason and preserved all three sentinels. Receipts and logs all succeeded on
attempt one, and all event leases were released. The generalized helper also
reverified the earlier metric run. [Report](event-handler-concurrency.md),
[evidence](builds/2026-10-11-recovery/crisp-handler-concurrency.json).

The CRISP in-flight observer query failed on an ambiguous `status` column; the
helper now qualifies it, but this run retains only the final worker distribution,
not an in-flight snapshot. The earlier metric probe retains its in-flight
observation. No migration, domain row or external integration changed. The
recovery DB is stopped with its volume retained, and the unrelated checkpoint
event lease is restored exactly. Same-event retry/crash, remaining handler types,
production runtime-role policy, provider recovery and broader CAP-040 parity stay
open. No pytest suite ran; CAP-040 and Batch 2 remain partial.

### Batch 2 same-event active lease exclusion — 11 October 2026

Held a synthetic CRISP handler at its cache write while worker A owned the
event. Worker B attempted the real event CLI claim; it processed no event, and
PostgreSQL still showed worker A as lease owner with one processing delivery
attempt. After releasing the temporary table lock, worker A completed once,
recorded one successful receipt/log, invalidated its target cache row and
preserved the sentinel. [Details](event-handler-concurrency.md),
[evidence](builds/2026-10-11-recovery/same-event-claim-exclusion.json).

The isolated recovery DB is stopped with its volume retained, and the unrelated
checkpoint event lease was restored to its exact original timestamp. This closes
only exclusion while an event's lease is active; stale-lease takeover during a
still-running handler, crash after side effect, remaining handler types,
production runtime-role policy and provider recovery remain open. No service
behavior, migration or domain record changed, and no pytest suite ran. CAP-040
and Batch 2 remain partial.

### Batch 2 same-event handler timeout and retry — 11 October 2026

A synthetic CRISP handler was held at its cache write until its 30-second
deadline. The first delivery timed out and returned the event to pending with
one retry recorded. A later operator process completed that same event on
attempt two: PostgreSQL retained one timeout and one success log, the event
completed with its lease released, the target cache row was invalidated and the
sentinel row remained valid. The forced lock exceeded the handler deadline, so
the planned concurrent claimant did not run and this does not establish
expired-lease takeover. The unrelated checkpoint fixture lease was restored to
its exact original timestamp. The recovery database is stopped with its volume
retained. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json).

No migration, service behavior or domain record changed; no pytest suite ran.
Crash-after-side-effect recovery, other handler types, production runtime-role
policy, provider recovery and broader CAP-040 parity remain open. CAP-040 and
Batch 2 remain partial; acceptance counts do not change.

### Batch 2 same-event expired-lease takeover — 11 October 2026

Worker A claimed one synthetic CRISP event and blocked in its cache update under
a temporary PostgreSQL table lock. A guarded helper expired only that event's
lease. Worker B reclaimed it while A's handler was still blocked: the database
snapshot showed B as owner on delivery attempt two and two blocked cache-update
sessions. After releasing the lock, both handlers succeeded. A invalidated zero
rows and lost the event completion race; B invalidated the target row and
completed the event. The final delivery is successful, with two success logs,
one target invalidation and the sentinel preserved. A's CLI reported one failed
event because its lease was no longer current.

The default 30-second handler timeout was too short for the first attempt to
capture a second claim; that isolated probe dead-lettered with cache rows
unchanged. For the successful rehearsal, the isolated handler timeout was
temporarily set to 120 seconds and restored to 30. The unrelated checkpoint
fixture lease was restored exactly. The recovery database is stopped with its
volume retained. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json).

No source service behavior, ordered migration, domain record or external effect
changed; no pytest suite ran. Crash-after-side-effect recovery, other handlers,
runtime-role policy, stale-worker lease-loss reporting semantics, provider
recovery and broader CAP-040 parity remain open. The stale worker's CLI counted
one failure even though worker B completed the event; review whether this should
be exposed separately from handler failure. CAP-040 and Batch 2 remain partial;
acceptance counts do not change.

### Batch 2 stale-worker reporting correction — 11 October 2026

`EventBus.process_pending()` now reports `lease_lost` independently from
`failed`, and does not retry an event when the current worker no longer owns its
lease. One-shot event processing exits successfully when lease loss is the only
outcome, while the persistent worker sleeps for its poll interval if it has no
processed or failed work. Handler errors and timeouts remain failures. A focused
regression function passed by direct invocation, along with Python compilation
and `git diff --check`; the standard pytest command could not start because
`pytest` is not installed in the host Python environment. No migration or
database state changed. The concurrent takeover evidence above predates this
reporting correction; rerunning it with the updated CLI remains optional
confirmation. Batch 2 and CAP-040 remain partial.

### Batch 2 crash-after-effect recovery — 11 October 2026

In the private recovery fixture, a guarded worker ran the real CRISP cache
handler, confirmed the target row was invalidated and the sentinel remained
valid, then exited with status 86 immediately before the delivery receipt could
be updated. PostgreSQL retained a processing event and processing delivery at
attempt one, with no handler log. After a guarded expiry of only that synthetic
event's lease, the real event CLI reclaimed it and reported one processed, zero
failed, zero skipped and zero lease losses. The handler ran again, invalidated
zero additional cache rows, and completed attempt two. Final state: completed
event, released lease, one successful handler log, target invalidated once and
sentinel preserved. [Evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json).

The known seeded fixture event was temporarily deferred so a global worker
could not claim it, then its exact original lease timestamp and other fields
were restored. Only the dedicated recovery database was started; it is now
stopped with both fixture volumes retained and no ports published. This covers
one idempotent local cache effect. It does not prove safe retries for non-idempotent
handlers or external effects; remaining handlers, runtime-role policy, provider
recovery and broader CAP-040 acceptance remain open. No migration changed.

### Batch 2 registered event-handler inventory — 11 October 2026

Source-audited the five effective event registrations and execution allowlist.
The metric/CRISP cache invalidators have isolated concurrency and crash/retry
evidence. The anomaly handler can create alert and optional draft-claim records,
publish a downstream event, and use email/Directus/actuator integrations; its
cooldown is not a per-event idempotency receipt. The stale-data and threshold
handlers call best-effort webhook/Directus transports without durable delivery
receipts, leaving duplicate-send and lost-send windows around event completion.
No external endpoint or actuator was contacted. Updated the batch checklist,
capability matrix and handler report to require notification idempotency before
replay probes. No code, migration or database state changed, no Compose project
was started, and no test suite ran. Batch 2 and CAP-040 remain partial.

### Batch 2 event notification outbox implementation — 11 October 2026

Added checksummed migration source `375_notification_outbox.sql` for durable
webhook/Directus notification queue rows, per-attempt receipts and operator
audit. Event handlers now enqueue with stable event/channel/destination identity
before their event receipt can succeed. The event worker dispatches enabled
channels using leases, bounded exponential retry, a stable `Idempotency-Key`,
dead-letter handling and audited replay/disposal. Provider-disabled channels
remain unclaimed; destination URLs and credentials are read from worker env and
are not stored in PostgreSQL. Exposed status/process/dead-letter CLI commands
and configured the standard/portability workers for optional notification
providers. Source compilation and whitespace checks passed. Migration was not
applied to either application database. A fresh, internal-only scratch database
accepted the migration twice. A fake transport verified enqueue idempotency,
changed-payload rejection, disabled-provider pause, retry/backoff, crash after a
fake send followed by lease reclaim using the same idempotency key, CLI help and
operator replay/disposal audit, including replay after a full retry budget with
monotonic attempt history. The allowlisted handler also received the stable source
event id and duplicate handler execution enqueued only one row. All nine checks
passed, with six fake sends and no external network. The scratch database is stopped
and its volume retained.
`py_compile`, CLI help in the operator image, and whitespace checks passed; no
pytest suite ran. Real provider acceptance and sensor anomaly idempotency remain
open. Notification table retention/capacity policy remains open; no automatic
pruning was added. Batch 2 and CAP-040 remain partial. [Evidence](builds/2026-10-11-recovery/notification-outbox-check.json).

### Batch 2 notification outbox capacity visibility — 11 October 2026

`--notification-stats` now reports queue status counts, oldest open age, and
combined storage for the outbox, attempts, and operator audit. Compose profiles
expose configurable 256 MiB warning / 512 MiB critical advisory thresholds.
No writes are blocked and no rows are deleted at either threshold. The
operations note sets a no-prune interim rule to protect identity and audit
evidence; the product/jurisdiction retention and archive period still requires
an owner decision. Ten isolated checks passed against a fresh internal-only
scratch database, including the deterministic critical threshold path; application
databases remain unchanged. [Evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json).
Batch 2 and CAP-047 remain partial.

### Batch 2 sensor anomaly crash/replay — 11 October 2026

Added additive migration `376_sensor_anomaly_delivery.sql` for a durable
per-reading/rule effect receipt, email outbox channel and the existing critical
actuation approval status. The event handler now resolves the exact source
reading and keeps its alert, optional draft claim, ingestion log, notification
intents, approval record and follow-up event in one PostgreSQL transaction.
Auto-created claims use the reading date. The actual EventBus worker subprocess
exited with code 86 after handler commit and before receipt acknowledgement. A
replacement worker reclaimed the expired source event lease and completed
delivery on attempt two; the event receipt moved from `processing` to `success`
with one success log. Alert, claim, effect receipt, ingestion log, downstream
event, actuation record and three notification intents each remained
single-copy. Critical work remained unapproved with
`human_approval_required=true`. A fake SMTP object verified stable `Message-ID`
and idempotency header; internal-only networking prevented egress and no real
provider or actuator was contacted. The focused fixture used only the relevant
schema set, not all repository migrations. Migration 376 re-applied twice;
Python compilation, migration-source validation, Compose parsing and
`git diff --check` passed. The scratch database is stopped with its volume
retained; candidate stayed healthy and legacy services stayed stopped. No
application database migration or pytest suite ran. [Design](sensor-anomaly-delivery.md);
[machine evidence](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json).
This closes one scoped sensor anomaly event-worker crash/retry check. Real
provider acceptance, notification retention, production operator policy,
additional handler/runtime recovery and broader CAP-040/Batch 2 acceptance
remain open.

## Phase 7 local operator overview CLI — 11 October 2026

Added `python3 -m services.cli kernel overview`, a local read-only view of build
metadata and environment-selected provider flags. It performs no database or
network checks and prints no credential values; its output labels health and DB
checks as false. The existing `kernel schema-readiness` remains the separate
read-only database gate. Documented why public `/api/health/services` is not an
operator-console dependency: it probes configured services and is not an
authenticated console. No service was started and no database was queried. A
browser console remains gated on operator identity/scope, audit, CORS, and write
approval policy. Python syntax compilation, generated SDK drift check, and diff
whitespace checks passed. The new CLI command was not invoked and no test suite
was run.

### Batch 2 PostgreSQL runtime-role boundary — 11 October 2026

Added `services/migration/runtime_role.py` and an opt-in Compose overlay that
provisions a distinct application role while leaving migration/operator
credentials separate. The app reads `PG_PASSWORD` first and preserves the
`POSTGRES_PASSWORD` fallback for existing deployments. A synthetic isolated
PostgreSQL fixture provisioned the role twice, checked table DML and default
grants for a table created afterward, and confirmed denial of persistent DDL,
role/database creation, admin-role switching, and access to `postgres`,
`template1`, and a second database. The role has no elevated attributes,
memberships, public-schema CREATE privilege, or owned probe relations. The
fixture had no published ports or network egress.

Candidate and legacy application databases were not migrated or reconfigured.
The candidate remains healthy with its current owner-backed credential; legacy
services remain stopped. The scratch role-check database is stopped and its
named volume retained. Python compilation, Compose parsing and whitespace checks
passed; no pytest suite ran. This completes the opt-in role primitive and its
isolated denial check. A fresh, internal-only populated restore then accepted
repeat provisioning; the native `public_locations()` read returned two rows, a
PostGIS function returned SRID 4326, and a synthetic admin-owned table supported
DML/sequence use. Persistent DDL, role/database creation, admin-role switching
and connections to the other two databases were denied. The test changed no
restored domain rows. [Populated restore evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json).

The candidate remains on its owner-backed credential. Source Compose shows
legacy Directus and Metabase still using the `kokonut` superuser; they are not
included in the Kernel runtime-role overlay and need distinct role/grant plans
before optional adoption. Full domain workflow acceptance, provider recovery
and broader platform-integrity acceptance remain open. Batch 2 remains partial.
[Policy](runtime-role-policy.md); [isolated evidence](builds/2026-10-11-recovery/runtime-role-isolation.json).

### Metabase source inventory — 11 October 2026

A fresh internal-only restore of both encrypted database archives found one
registered Metabase source: the sample H2 source, with no host or database name
and no nonempty password value configured. All 39 saved cards and all 22 dashboard card
placements reference H2. The restored metadata has one dashboard and one user;
there is no PostgreSQL or ClickHouse source configured. The inventory did not
read saved-query definitions/SQL, print connection values, start the populated
Metabase runtime, or execute cards. Therefore the legacy dashboard is not
evidence of Kokonut analytics parity. The temporary containers/network were
removed, the isolated named volume was retained, and the candidate remains
healthy while legacy services remain stopped. [Report](metabase-source-inventory.md) ·
[machine evidence](builds/2026-10-11-recovery/metabase-source-inventory.json).

The populated metadata startup is complete: pinned Metabase is healthy on the
non-superuser metadata role and retained the saved-content aggregate counts.
The initial curated-view source contract and migration are now documented and
authored. The next open work is applying migration 377 and running the expanded
role fixture in a fresh isolated populated restore, then validating
Kokonut-specific measures and output parity before optional-profile promotion.

### Populated Metabase startup — 11 October 2026

Restored the encrypted application and Metabase archives into a new
internal-only project. The optional consumer-role fixture passed again: the
Metabase login owned the `metabase` database and 290 application relations;
the analytics login read only its synthetic curated view, and cross-database
denials held. The pinned Metabase 0.62.4 image started against the populated
metadata DB and reached healthy; the health endpoint returned 200. Post-startup
counts matched the earlier inventory of the same encrypted metadata archive:
39 cards, one dashboard, 22 dashboard placements, and one user. The sole source
remains sample H2. No card definitions or SQL
were read or executed. The recovery containers and network were removed; the
volume was retained. Candidate services stayed healthy; legacy services stayed
stopped. [Evidence](builds/2026-10-11-recovery/metabase-populated-startup.json).

This closes the populated metadata startup checklist item only. Source
connectivity, card rendering, semantic/output parity, Kokonut-specific cards,
and optional-profile promotion remain open.

### Metabase saved-content review — 11 October 2026

A fresh internal-only Metabase metadata restore revealed one **E-commerce
Insights** dashboard with 22 placements from 39 cards. The card titles and
source categories cover orders, products, subscriptions, checkout, revenue,
and survey examples; every card points to the sample H2 source. The cards span
19 visualization types. The read-only structural inventory emitted no SQL,
filter values, connection values, user records, or domain rows and did not
execute saved cards. This is generic demo content, not Kokonut analytics
capability or output-parity evidence.

Disposition: preserve the archive and use the sample board only as an
explicitly labeled demo/compatibility fixture. Build Kokonut-specific reports
against reviewed published views and compare agreed reference outputs before
enabling Metabase in an analytics profile. [Report](metabase-source-inventory.md) ·
[evidence](builds/2026-10-11-recovery/metabase-content-inventory.json).

This content-only fixture restored only the Metabase archive. An exploratory
application-database restore in the same temporary project hit a PostGIS
duplicate-extension catalog error; the unused app database was reset empty.
The Metabase restore and inventory succeeded, the isolated volume is retained,
and candidate/legacy services remain unchanged. CAP-007 and Batch 2 remain
partial; no source query or test suite ran.

### Metabase reporting contract — 11 October 2026

Documented the initial PostgreSQL-only reporting boundary and proposed stable
`kokonut_reporting` views. The contract uses the existing public views as
behavioral evidence, not as an approved source to grant unchanged: the farm
summary's `SUM(DISTINCT area)` can undercount equal-area farms, while the metric
summary omits period/method, may tie on computed time, and has no explicit
public metric allowlist. The attestation summary remains explicitly Celo-only.
The document defines role scope, an additive implementation sequence,
acceptance and rollback gates. No schema, grant, Metabase connection, or card
changed in this documentation batch. [Contract](metabase-reporting-contract.md)
· [Checklist](batches.md) · [CAP-007](capability-matrix.md).

### Metabase reporting views verified — 11 October 2026

Applied all 368 current schema migrations, including migration 377, to a clean
`kokonut_reporting_scratch` database in a copied isolated recovery volume. The
checksum-tracked plan then reported zero pending schema migrations. The expanded
consumer-role fixture passed exact access to the three reviewed views and denied
base-table/policy-table reads, DDL, writes, and cross-database connections. Its
rolled-back synthetic probes confirmed equal-area farm/plot totals, farm-specific
registry scope, unsupported-unit fail-closed behavior, an empty-by-default metric
allowlist with published-value visibility, and Celo-only verified/published
attestation counts. Metabase metadata remained populated in the clone; its
ownership setup was confined there. The archived application DB restore still
reports historical checksum drift at `schema:000_extensions.sql`; this was not
repaired or bypassed, and no candidate/legacy database was changed. No Metabase
source or Kokonut cards were configured. [Evidence](builds/2026-10-11-recovery/kokonut-reporting-contract.json) ·
[checklist](batches.md) · [contract](metabase-reporting-contract.md).

### Archived migration checksum drift triage — 11 October 2026

Read the migration ledger and extension catalog from the retained isolated
application restore. Of 344 applied schema rows, only
`schema:000_extensions.sql` mismatches the current source checksum; 24 newer
current schema files are absent from that archive ledger. The six extensions
listed in the current source are installed, but that does not prove the
historical SQL matched. The local Git parent has no prior copy of this migration,
and the ledger's 24-byte `sql_up` value does not hash to the recorded checksum.
No exact repair is approved by the migration runner. I left the ledger and
database unchanged and stopped the inspection container with its volume kept.
[Triage](migration-checksum-drift.md) ·
[sanitized evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json).


### Historical migration source recovered — 11 October 2026

Extracted `schemas/postgres/000_extensions.sql` from the stopped local legacy
worker image. Its SHA256 exactly matches the archived ledger's stored checksum
`cf493b…a245`. The current source adds a synchronization note and three
idempotent extension declarations; all six current extensions are already
installed in the archived clone. Preserved the old SQL under recovery provenance
evidence. No database ledger repair or migration was performed: the runner has
no allowlist entry for this migration, and its policy directs new drift to a new
migration. The archived clone remains gated until the migration/recovery
disposition is documented. The temporary inspection container was removed; the
legacy stack remains stopped and the candidate remains healthy.

[Drift record](migration-checksum-drift.md) ·
[Historical source](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql) ·
[Sanitized evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Historical migration checksum reconciled in source — 11 October 2026

Git history shows the expanded `000_extensions.sql` was reintroduced on 9
October, after checksum enforcement landed on 15 July. I restored the active
migration file to the exact deployed bytes recovered from the stopped worker
image (`cf493b…a245`) and moved the later `postgis_topology`, `pg_trgm`, and
`pg_stat_statements` declarations into new migration 378. The archived clone
and ledger were not changed. Source validation covered 369 migrations and the
focused migration suite passed (15 tests). A read-only plan on the retained
clone and a fresh 369-migration reporting scratch run are still required; the
previous 368-source reporting scratch used the interim checksum and is not a
current-source target.

[Source correction](migration-checksum-drift.md) ·
[Migration 378](../../schemas/postgres/378_optional_extensions.sql) ·
[Historical source](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql) ·
[Evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Source-aligned reporting replay and archived clone plan — 11 October 2026

The post-alignment read-only plan on the retained archived clone passed checksum
validation and reported 25 pending migrations (353–378); none were applied. I
copied the stopped reporting clone into a second-generation volume, created a
fresh scratch database, applied all 369 current schema migrations through 378,
and confirmed zero pending. The expanded actual-view role fixture passed its
aggregation, publication/lifecycle, Celo attestation, scope, and denial probes.
Synthetic fixture rows rolled back. The first fixture connection used a rotated
credential and failed before changes; I set a synthetic password only in the
second-generation clone and reran successfully. Temporary containers and
networks were removed; the copied volume remains retained, while the source
clone, original recovery volume, candidate, and legacy stack were unchanged.

[Source-aligned evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json) ·
[Archived plan](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Drift/source record](migration-checksum-drift.md) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Transactional migration replay and rollback — 11 October 2026

The migration runner now wraps each SQL body and its `schema_migration` ledger
write in one transaction under the existing advisory lock. Existing balanced
top-level transaction markers are folded into the runner transaction; nested or
unmatched markers are rejected. The focused migration suite passed with 17 tests,
and the wrapper preflight accepted all 488 schema and seed files.

On a third-generation disposable copy, all 369 current schema migrations were
applied and checksum-validated with zero pending. An injected migration created
a table and row, then failed on a duplicate table creation. The runner returned
the expected SQL error; independent post-failure queries confirmed zero probe
tables and zero ledger rows (`0|0`). The reporting-view role fixture remains
covered by its separate source-aligned replay. The archived application clone,
original recovery volume, candidate, and stopped legacy stack were unchanged.
The temporary container and network were removed; the disposable clone volume
was retained.

In a separate compatibility replay, all 25 migrations pending on the archived
clone were applied through the same runner to a copied populated database. The
plan returned zero pending, and pre-migration column fingerprints matched for
all 16 selected populated tables. The retained archived clone still has all 25
pending and was not changed. Two SAFE rows and six migration-version markers
were the expected additions; all other new optional workflow/reporting tables
remained empty. SAFE seed values and the NOI view formula were subsequently
verified onchain and against a populated clone; migration 379 and the native
snapshot reconciler were exercised on a separate network-disabled copy. Active-
target application still requires duplicate-key preflight, exact-target checksum
review, and a verified backup. The daily job remains disabled. Populated
report-output parity and Metabase source/cards remain open.

[Runner documentation](../../services/migration/README.md) ·
[Transactional evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json) ·
[Populated-clone review](pending-migration-compatibility-review.md) ·
[Drift record](migration-checksum-drift.md) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Populated reporting-view parity — 11 October 2026

On a network-disabled disposable copy of the populated recovery database, bidirectional EXCEPT comparisons matched the independent farm-summary query (2 rows) and Celo-attestation query (1 row), with zero differences. The verified-metrics view also matched its independent query, both returning zero because no metric publication policy was published in this dataset. The analytics role received only named SELECT grants on the three reporting views in the disposable copy; as that role it could read those views and was denied on metric values, the migration ledger, the private policy table, and DDL. Five pre-existing public extension metadata relations remained readable through their own grants. The copied source, candidate, and legacy deployment were unchanged; the temporary database and volume were removed. No Metabase source or cards were configured.

Evidence: [sanitized parity and role results](builds/2026-10-11-recovery/populated-report-view-parity.json), [report contract](metabase-reporting-contract.md), and [Batch 4b](batches.md). The copied PostgreSQL cluster emitted a collation-version warning, but all read-only queries completed successfully.


### Candidate migration preflight and fresh schema replay — 11 October 2026

The active candidate has 361 applied schema rows through migration 370 and nine current migrations pending (371–379). The exact-target read-only plan found a single checksum mismatch at schema:000_extensions.sql: the stored checksum is 6e5850e5…5723ff, matching the source used by the candidate, while the current source checksum is cf493b73…1a245. The candidate has zero NOI snapshots, duplicate keys, or null crop-cycle keys. No migration or checksum repair was applied.

A fresh encrypted checkpoint was created for this exact candidate and its archive authenticated and restored successfully into an internal-only database. The ledger, relation count, and selected table counts matched. The checkpoint is mirrored under the same disk. Separately, all 370 current schema sources applied with zero failures to a network-disabled fresh database; its final plan had zero pending. Both scratch projects were removed. The checksum mismatch still blocks applying migrations to the existing candidate under the repository migration-integrity rules.

Evidence: [candidate preflight, backup and fresh replay](builds/2026-10-11-recovery/candidate-migration-preflight.json), [checksum history](migration-checksum-drift.md), [Batch 4a](batches.md), and the ignored root plan.


### Candidate reporting-source ACL review — 11 October 2026

Before the candidate migration update below, read the active candidate's roles and database/schema ACLs inside a
`BEGIN READ ONLY` transaction. `kokonut` is the only login/superuser role; the
runtime, analytics-source, and Metabase metadata roles and migration-377
reporting objects are absent. `PUBLIC` retains `CONNECT` and `TEMPORARY` on
the application database (and `CONNECT` on `postgres` and `template1`). No
grant, schema, role, application row, or Metabase source was changed. This
closes the exact-target ACL inventory item. The source was not ready at review
time. The checksum policy and schema migrations are now resolved on the
candidate; dedicated role/ACL setup remains open.

Evidence: [candidate reporting ACL inventory](builds/2026-10-11-recovery/candidate-reporting-acl-review.json), [active candidate migration result](builds/2026-10-11-recovery/candidate-migration-apply.json), [reporting contract](metabase-reporting-contract.md), [optional database roles](optional-database-roles.md), and [Batch 4b](batches.md). No test suites were run for the ACL inventory; capability counts and deployment selection are unchanged.


### Candidate migration compatibility review — 11 October 2026

The candidate's stored `schema:000_extensions.sql` checksum matches the exact
repository-base bytes. The source change only relocates three idempotent
extension declarations to migration 378; a read-only candidate query confirms
all six expected extensions are installed. The runner now recognizes the exact
historical/current source pair through its audited repair allowlist and refuses
repair unless all six extension effects are present. The focused migration suite
passes 22 tests, including exact-checksum approval, audit insertion,
current-source pinning, and missing-extension rejection. The candidate ledger
had not yet been repaired at this checkpoint, and no pending migration had been applied.

The exact repair and planner then passed on an internal-only fixture seeded from
the candidate's read-only schema ledger. Its post-repair plan reported zero
checksum mismatches and the expected nine pending migrations; the audit row
recorded the exact old/current checksum pair. No candidate application schema
was restored or changed by this check.

Evidence: [preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json), [ACL and extension inventory](builds/2026-10-11-recovery/candidate-reporting-acl-review.json), [isolated repair policy evidence](builds/2026-10-11-recovery/candidate-checksum-repair-policy.json), [migration drift record](migration-checksum-drift.md), [runner policy](../../services/migration/README.md). This is an implementation preparation step; capability counts remain unchanged.


### Active candidate migrations 371–379 — 11 October 2026

The exact candidate repair was recorded through the audited runner path after
the full six-extension precondition passed. The post-repair plan returned the
nine expected migrations; the transactional runner applied all nine with zero
failures. A final source/target plan reports zero pending from 370 applied
schema files. The reporting schema and its three views now exist, with no PUBLIC
table grants. The NOI table remains empty; the unique crop-cycle index exists,
and null/duplicate keys remain zero. Candidate app and database are healthy.
The app supervisor runs scheduler and event-worker processes; scheduler status
reports zero enabled, disabled, or running tasks, so the NOI daily job is not
registered. A separate analytics login is now provisioned and verified; no Kokonut Metabase source/cards are configured, and the built-in H2 demo is recorded in the optional-profile section below.
Legacy remains stopped.

Evidence: [active candidate migration record](builds/2026-10-11-recovery/candidate-migration-apply.json), [preflight backup and restore](builds/2026-10-11-recovery/candidate-migration-preflight.json), and [checksum policy](migration-checksum-drift.md). The recorded checkpoint restores the pre-repair schema; reapplication requires the audited repair. No capability acceptance count changes.

### Active candidate app rebuild — 11 October 2026

Rebuilt the AMD64 Kernel image after adding the optional Metabase-role bootstrap
module. The final image matches every embedded checkout hash: 1,294 of 1,294;
the 11 omitted paths are optional transport/orchestration or development inputs.
The previous app image is preserved as
`kokonut-kernel-candidate-app:pre-metabase-role-20261011`; earlier rollback tags
remain available. Only the app container was recreated. The database container
and PostgreSQL volume remained unchanged and healthy, and Metabase remained
healthy. The app liveness endpoint returned 200,
the explicit candidate migration plan reports zero pending schema migrations,
and the scheduler reports zero enabled/disabled/running tasks. Compose created
the previously absent empty gateway-audit spool volume. No migration, grant,
role or Metabase change occurred. This does not establish API or domain parity,
ARM64/Raspberry Pi readiness, or phase acceptance.

Evidence: [candidate app rebuild](builds/2026-10-11-recovery/candidate-app-rebuild.json),
[migration state](builds/2026-10-11-recovery/candidate-migration-apply.json), and
[batch checklist](batches.md). Capability counts remain unchanged.

### Candidate analytics-source login — 11 October 2026

Added the opt-in `analytics-admin` Compose profile and repeatable
`services.migration.analytics_role` bootstrap. It is guarded for a dedicated
PostgreSQL instance, revokes inherited PUBLIC database CONNECT on all four
existing candidate databases, removes PUBLIC TEMPORARY on the application DB,
and grants the non-admin `kokonut_analytics_ro` login access only to that DB and
the three reviewed reporting views. Its random credential is stored encrypted
in `.env.sops`; the running application keeps its existing identity.

The real analytics login read all three candidate views (each currently has
zero rows) and was denied on the migration ledger, private publication policy,
DDL, temporary tables, and all other candidate databases. No unreviewed
application relation is readable. Existing extension privileges remain
inherited: eight extension metadata relations are accessible and 1,165
extension functions are executable; none of the public-executable extension
functions is SECURITY DEFINER. The one-shot bootstrap container was removed;
the app and database remained healthy, and the migration plan still reports
zero pending. No Kokonut Metabase source/cards were created; the built-in H2
demo was inventoried separately below.

Evidence: [candidate analytics-role record](builds/2026-10-11-recovery/candidate-analytics-role.json),
[role policy](optional-database-roles.md), [migration/bootstrap instructions](../../services/migration/README.md),
and [Batch 4b](batches.md). MAN-CAP counts do not change.

### Candidate Metabase analytics profile — 11 October 2026

Added an opt-in candidate-only `analytics` overlay with pinned Metabase 0.62.4,
a loopback-only UI port, private PostgreSQL networking, sharing disabled, a
bounded JVM heap, and a distinct SOPS-managed encryption key. The one-shot
`metabase_role` bootstrap created `kokonut_metabase` and its
`kokonut_metabase_app` owner. Database ACLs give that role CONNECT and CREATE
only on the metadata database; a real login created a temporary table that was
rolled back and was denied on `kokonut_intelligence`.

Metabase startup exposed the database-level CREATE requirement for installing
`citext`; the bootstrap was tightened to grant CREATE only on its metadata DB,
then re-run successfully. Metabase is healthy; its loopback endpoint returned
HTTP 200 and Docker reports healthy. The default candidate manifest contains
only `database` and `app`, and PostgreSQL has no host port. A sanitized
inventory found one built-in H2 sample source, 39 generic demo cards, one
dashboard with 22 placements, and one user record; no Kokonut PostgreSQL source
or Kokonut cards exist. The startup log confirms credential encryption is
enabled. The legacy stack remains stopped.

The secrets loader also now resolves its own path when sourced from zsh, the
repository's interactive shell. It loaded the needed keys without displaying
values, and the combined opt-in Compose configuration validated.

Evidence: [profile contract](metabase-kernel-profile.md), [profile runtime record](builds/2026-10-11-recovery/candidate-metabase-profile.json), [source inventory](metabase-source-inventory.md), [role policy](optional-database-roles.md), [Batch 4d/4e checklist](batches.md), and [Metabase credential-encryption docs](https://www.metabase.com/docs/latest/databases/encrypting-details-at-rest).
Capability counts remain unchanged.

### Kokonut Metabase source, cards, and local metadata backup — 11 October 2026

Completed local first-run setup with the generated administrator credential
stored encrypted in `.env.sops`. Registered `Kokonut Reporting Views` through
`kokonut_analytics_ro`, using a string inclusion pattern for `kokonut_reporting`.
The first attempt encoded the pattern as a list; that prevented schema
discovery. After correcting it to the comma-separated string expected by
Metabase, schema sync completed and listed only the three approved reporting
views. The source connection validates, and saved credential encryption was
enabled before registration.

Created the `Kokonut Reporting` collection, three SQL cards (farm summary,
verified metric values, and Celo attestation summary), and the
`Kokonut Intelligence | Reporting Overview` dashboard. All card queries
completed and exposed the expected columns. Each returned zero rows, matching
direct PostgreSQL counts; the active candidate has no pilot rows. The generic
H2 sample remains separately labeled demo content. A credential-free card
export and sanitized source/card inventory are retained.

Streamed a fresh custom-format dump of `kokonut_metabase` directly through age
encryption to the ignored local `backups/kernel-metabase-20261011/` directory;
no plaintext dump was written. Decryption with the supplied age identity and
`pg_restore --list` both succeeded with 2,177 archive entries. The
`KOKONUT_METABASE_ENCRYPTION_KEY`, source password, and admin password remain in
SOPS. The archive restored successfully with `--exit-on-error` into a
network-disabled, disposable container using the matching PostGIS 16 image.
Counts matched the live metadata exactly: two sources, 42 saved cards, two
dashboards, 25 saved-card placements, 14 virtual tiles, and two users. The
E-commerce board's virtual tiles are populated heading/text/link/iframe content,
not empty cards. The disposable target was removed and the live metadata was
unchanged. Populated card-output parity was then completed separately on a
copied fixture; the database-view parity evidence from Batch 4b alone does not
certify the Metabase card layer.

Evidence: [candidate runtime and card results](builds/2026-10-11-recovery/candidate-metabase-profile.json),
[sanitized source inventory](metabase-source-inventory.md),
[credential-free card export](metabase/kokonut-reporting-cards.json),
[encrypted backup manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json),
[profile contract](metabase-kernel-profile.md), and [Batch 4e checklist](batches.md).
Capability counts remain unchanged.

### Kokonut card SQL output parity — 11 October 2026

Copied the retained populated reporting volume read-only into a fresh scratch
volume. A temporary source used `kokonut_analytics_ro` and the
`kokonut_reporting` schema filter on a private internal Docker network; there
were no host ports. Metabase executed the exact SQL from the three
credential-free card definitions. Farm summary returned two rows and Celo
attestation summary returned one; both matched independently written
base-table queries with zero differences.

For the metric card, a synthetic verified value and reviewed policy were added
only to the disposable copy. The value stayed hidden while the policy was
`verified`; after publishing the policy, one verified value appeared and an
unverified value remained excluded. In-window and outside-window queries
returned one and zero rows respectively. Both outputs matched independent SQL.
The temporary source, network, container, and scratch volume were removed. The
retained source volume, candidate metadata, candidate application database, and
legacy stack were unchanged. No query rows or credential values were printed.

The active candidate still has no pilot rows, so its saved cards return zero
rows. The populated comparison used the same exported card SQL through the
Metabase dataset API and did not modify saved card objects. See
[sanitized parity evidence](builds/2026-10-11-recovery/metabase-card-output-parity.json),
[card export](metabase/kokonut-reporting-cards.json), and
[Batch 4e checklist](batches.md). Capability counts remain unchanged.


## Batch 5 MQTT deployment contract — 11 October 2026

Reviewed the optional Mosquitto/subscriber Compose overlay and the related QoS,
transaction, recovery, and readiness records. Confirmed the broker/subscriber
are on the private Kernel network with no host ports, separate read-only broker
and subscriber credential mounts, a dedicated persistent broker volume, stable
QoS 1 client identity, manual ACK after durable source/outbox commit, and local
connection/subscription health state. Corrected stale statements: migrations
371/372 are applied to the active local candidate through 379, while the
MQTT-specific image is a historical build and neither MQTT service has been
started. No secrets, broker state, or services were changed; no test suite or
Compose deployment was run for this review. ARM64, mTLS/ACL, ingestion, retry,
reconnect, readiness, and storage recovery acceptance remain open. See
[mqtt profile contract](mqtt-overlay.md), [delivery](mqtt-delivery.md),
[recovery](mqtt-recovery.md), [readiness](mqtt-readiness.md), and [checklist](batches.md).


## Batch 5 gRPC deployment contract — 11 October 2026

Reconciled the private gRPC overlay with the server, auth interceptor, pooled
database adapter, and shutdown code. The contract now states that the service
has no host port, the Caddy profile does not proxy it, Compose omits TLS settings
so the transport is insecure within the private `kernel` network, and API keys
with exact method scopes authorize business RPCs. It also records the `kokonut`
DB-user fallback, unmeasured 4-worker/1–5 pool sizing, 30-second server grace,
40-second container grace, and liveness-only health. Historical image digests
need a rebuild from current checkout. The service was not started and no RPC was
issued; no schema, secrets, or runtime state changed. ARM64, TLS, role, auth/scope,
streaming, data parity, concurrency and shutdown acceptance remain open. No test
suite ran. See [gRPC contract](grpc-overlay.md), [auth](grpc-authentication.md),
[database](grpc-database.md), [shutdown](grpc-shutdown.md), and [checklist](batches.md).

## Batch 5 Caddy proxy deployment contract — 11 October 2026

Reconciled the pinned Caddy Compose overlay, Caddyfile, and retained runtime
checks. Documented loopback defaults (8088/8448), alternate HTTPS port behavior,
all-path forwarding only to the Gateway, local-CA trust, three response headers,
no Caddy healthcheck, no gRPC/sensor routes, ignored forwarded headers, and the
public-ingress gates. Existing private internal TLS, host loopback, alternate
port, and one-hop forwarded-header probes are retained; they do not certify
public bind/DNS/ACME, client trust installation, multi-hop proxies, or
authenticated CORS. No service or config was changed and no suite ran. Rollback
removes only the proxy profile and keeps certificate volumes. See
[proxy contract](kernel-proxy.md), [proxy evidence](builds/2026-10-10-recovery/kernel-proxy-runtime.json),
and [Batch 5 checklist](batches.md).


## Phase 7 OIDC operator identity and report review slice — 11 October 2026

Added an opt-in OIDC adapter using the separate `oidc` image target and
`docker-compose.kernel-oidc.yml` overlay, with secure HTTPS-only cookies,
state/nonce handling, S256 PKCE, database-backed opaque sessions, CSRF checks,
and locally provisioned identity/location grants. Added additive migration
380, a CLI for identity/grant lifecycle, and a same-origin page that displays
the authenticated principal without persisting credentials in browser storage.
The minimal `kernel` target remains free of OIDC dependencies. OIDC is still
disabled because no provider credentials/settings are configured. Migration
380 was not applied and no live login/session request or acceptance suite was
run. Selected `report_snapshot` because the schema and workflow define the
submitted review state. Added exact OIDC route policies, active scope listing
for the signed-in principal, per-location `report_snapshot_review:read`
authorization, read-only list/detail SQL limited to submitted rows, and a
same-origin browser queue that renders report data with `textContent`; SQL
rechecks the active grant, and report details are capped at 512 KiB. Network
snapshots without a location remain outside this scope; the console has no
verification/rejection/publication controls. Python AST parsing, provider-boundary
and requirement-group checks, inline JavaScript syntax, and `git diff --check`
passed. Ruff is not installed, and no tests ran. Runtime authorization, audit,
login, queue and detail acceptance remain open.
Capability counts do not change. See
[`kernel-operations-console.md`](kernel-operations-console.md)
and [Batch 5](batches.md).
