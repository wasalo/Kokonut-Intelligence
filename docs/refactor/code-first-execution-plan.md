# Code-first refactor execution plan

**Updated:** 19 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68

**Current local slices — 19 October 2026:** CAP-031 has an internal location budget read at `GET /operator/api/planning/{location_id}/budgets`. Migration 455 rechecks exact `planning_budget:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. It includes only plans owned by the location's current organization with budget lines assigned to that location. Results contain plan status/currency/period, planned amount, verified same-currency expenses and variance, foreign-currency expense count, and scenario count; plan labels, categories, objective identity, assumptions, and transaction details are excluded. The focused Gateway, exact route-policy, and migration-metadata selection passes 49 tests. Disposable PostgreSQL 16 applies/replays migration 455 and passes seven lineage, currency, scope, privacy, and ACL assertions. CAP-032 adds `GET /operator/api/business-architecture/{location_id}/summary`, protected by exact `business_architecture:read` and signed tenant context; focused selection passes 48 tests and migration 456 replay passes seven scope/approval/privacy/privilege assertions. CAP-033 adds `GET /operator/api/business-planning/{location_id}/canvases` under exact `business_planning:read`; migration 457 returns location-only canvases with governed lifecycle, nine content blocks, and source references while excluding raw imports, metadata, actors, and organization canvases; 48 focused tests and seven disposable assertions pass. CAP-034 adds `GET /operator/api/coordination/{location_id}/summary` under exact `coordination:read`; migration 458 returns aggregate governance indicators only for exact location alliances and does not alter approval, consent, activation, or publication; 42 focused tests and six disposable assertions pass. Candidate and legacy databases are untouched; migrations 455–458 are not rolled out. CAP-031 remains partial; CAP-032–034 are prepared. Generated pitch/business-plan parity, populated-data parity, live OIDC/browser, trigger/worker recovery, universal ACL/RLS, and owner acceptance remain open. Checklist: 675 complete / 19 open; matrix: 36 baseline-retained, 7 deployed, 23 prepared. Evidence: [CAP-031 contract](planning-budget-kernel-read-contract.md), [CAP-031 acceptance](builds/2026-10-19-recovery/cap-031-budget-summary-disposable.json), [CAP-032 contract](business-architecture-kernel-read-contract.md), [CAP-032 acceptance](builds/2026-10-19-recovery/cap-032-business-architecture-disposable.json), [CAP-033 contract](business-planning-kernel-read-contract.md), [CAP-033 acceptance](builds/2026-10-19-recovery/cap-033-business-canvas-disposable.json), [CAP-034 contract](coordination-kernel-read-contract.md), and [CAP-034 acceptance](builds/2026-10-19-recovery/cap-034-coordination-summary-disposable.json).

**Previous local slice — 19 October 2026:** CAP-030 now has a location-scoped management summary at `GET /operator/api/management/{location_id}/summary`. Migration 454 rechecks exact `management_workflow:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. The response aggregates work lifecycle/open-priority counts, overdue/SLA totals, claim/escalation totals, and latest event time for exact location matches; task content, personal identities, estimated effort, notes, and escalation reasons are excluded. The focused Gateway, route-policy, and migration-metadata selection passes 42 tests. Disposable PostgreSQL 16 applies/replays migration 454 and passes seven scope, aggregate, privacy, and ACL assertions. Candidate and legacy databases are untouched; migration 454 is not rolled out. CAP-030 remains prepared, not accepted: assignment/transition, claim review, dynamic SLA policy, escalation mutation/audit parity, unscoped work-item review, populated fixtures, live OIDC/browser behavior, universal ACL/RLS, and MAN-CAP-030 owner review remain open. Checklist: 671 complete / 19 open; matrix: 39 baseline-retained, 7 deployed, 20 prepared. Evidence: [CAP-030 contract](management-work-kernel-read-contract.md) and [disposable acceptance](builds/2026-10-19-recovery/cap-030-management-work-summary-disposable.json).

**Previous local slice — 19 October 2026:** CAP-029 now has a location-scoped Kernel read at `GET /operator/api/competitive-landscape/{location_id}/summaries`. Migration 453 rechecks exact `competitive_landscape:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. The bounded response contains landscape metadata and aggregate actor/threat, Five Forces, signal, verified advantage, and outcome signals; identity, narrative, evidence, source references, statements, and individual outcome values are excluded. The focused Gateway and exact route-policy selection passes 16 tests; the combined Gateway, policy, migration-metadata, and legacy parity selection passes 56 tests with two skips. Disposable PostgreSQL 16 applies/replays migration 453 and passes seven aggregate, scope, grant, pagination, output-contract, and ACL assertions. Candidate and legacy databases are untouched; migration 453 is not rolled out. CAP-029 remains prepared, not accepted: workflow/report/dashboard parity, populated fixture comparison, live OIDC/browser behavior, universal runtime ACL/RLS, and MAN-CAP-029 owner review remain open. Checklist: 670 complete / 19 open; matrix: 40 baseline-retained, 7 deployed, 19 prepared. Evidence: [CAP-029 contract](competitive-landscape-kernel-read-contract.md) and [disposable acceptance](builds/2026-10-19-recovery/cap-029-competitive-landscape-disposable.json).

**Previous local slice — 19 October 2026:** CAP-024's tactical content implementation is ready for owner review. Migration 445 adds Gateway creation of open tactical items and exact-grant edits for open items/planned sessions, with signed tenant context, active person binding, same-location reference validation, lifecycle separation, stable idempotent retries, and private immutable before/after history. Runtime and Directus direct writes are denied; the function owner has only column-scoped writes and the narrow `UPDATE(id)` row-lock privileges. The operator console now has grant-gated CSRF/no-store forms. The focused mutation slice passes 19 tests; the broader CAP-024 Gateway, route-policy, and console suites pass 182 tests with five skips; migration metadata passes 33 tests, and disposable PostgreSQL 16 applies/replays migrations 437–445 and verifies scope, bindings, lifecycle boundaries, retries/collisions, audit, and ACLs. Ruff, compilation, JavaScript syntax, capability validation, SQL inventory, and diff checks pass. Candidate remains at migration 444; no candidate/legacy DB was changed. Checklist: 658 complete / 19 open (677 total); matrix remains 45 baseline-retained, 7 deployed, 14 prepared. CAP-024 remains prepared rather than MAN-CAP accepted; least-privilege rollout, remaining report/populated-fixture parity, tenant RLS, live OIDC/browser, and accountable-owner review remain open. Evidence: [contract](governance-tactical-content-mutation-contract.md); [database acceptance](builds/2026-10-19-recovery/governance-tactical-content-mutations-disposable.json).

**Previous local slice — 18 October 2026:** CAP-024 now includes audited Gateway creation and draft editing for circles and roles. Migration 443 creates location-scoped definitions only as drafts; draft edits are restricted to descriptive fields and protected by signed tenant context, exact create/update grants, active person binding, same-location circle hierarchy checks, idempotent request history, and an immutable private before/after ledger. Runtime and Directus direct writes are revoked and trigger-guarded. The console exposes CSRF-protected create/edit controls and loads circle edit fields from a separate no-store detail route requiring exact location `:read` and `:update` grants; the aggregate summary keeps free text excluded. The focused CAP-024 Gateway, route-policy, and console suite passes 151 tests (5 skipped), and the ordered migration metadata suite passes 33 tests; disposable PostgreSQL 16 applies/replays migrations 437–443 and verifies authorization, scope, retry/collision behavior, draft-only updates, ledger privacy, and direct-write denial. Ruff, compilation, JavaScript syntax, capability validation, and runtime SQL inventory (850 source files / 4,111 execution sites) pass. Candidate remains at migration 437 and uses administrative `PG_USER=kokonut`; migrations 438–443 are not rolled out and the candidate runtime does not yet enforce their ACL boundary. Candidate and legacy databases were not changed. Work is local and uncommitted on `feat/mobile-offline-acceptance`. Checklist: 654 complete / 19 open (673 total); matrix: 45 baseline-retained, 7 deployed, 14 prepared. CAP-024 remains prepared, not accepted: least-privilege candidate rollout, broader parity, populated parity, domain RLS, live OIDC/browser behavior, and named MAN-CAP review remain open ([contract](governance-definition-lifecycle-contract.md); [migration](../../schemas/postgres/443_governance_definition_mutations.sql); [database evidence](builds/2026-10-18-recovery/governance-definition-mutations-disposable.json)).
**Previous local slice — 18 October 2026:** CAP-024 now has an OIDC-protected, aggregate-only governance summary at `/operator/api/governance/{location_id}/summary`. The route requires an exact location `governance_roles:read` grant and establishes signed tenant context before read-only, location-filtered SQL. It reports circle review state and role/assignment/authority/tension/tactical counts without stakeholder identities or private free text. Eight focused service/route/policy tests pass with synthetic connections; Ruff, compilation, capability validation, and diff checks pass. No database, provider, or candidate/legacy service was contacted. This prepares CAP-024 but does not accept MAN-CAP-024; item-level review/mutation parity, populated fixtures, and domain-table RLS remain open. Work is local and unpushed; candidate remains at migration 435. Matrix: 45 baseline-retained, 7 deployed, 14 prepared. Checklist: 640 complete / 19 open.

**Previous local checkpoint — 18 October 2026:** The accumulated local batch includes the CRISP/organic SDK slices, native true-cost/emergency/attestation/ecocredit/credit-custody summaries, private Data Stream no-store handling, and the CAP-023 Baal Gateway read surface. CAP-023 exposes protected global config, bounded proposal, and member reads under `governance:read`; location-bound API keys and capability tokens cannot authorize the global DAO resource, chain ID 100 is required, and raw provider/event fields are omitted. Large share/loot/vote quantities are decimal strings; required config reads fail closed. Non-admin keys require the global scope; the configured Directus admin key keeps its existing bypass. A pre-existing Gateway router indentation defect was corrected. The focused Gateway/auth/capability/governance/indexer suite passed 98 tests; Ruff, compilation, capability validation, and diff checks passed with mocked clients. No candidate/legacy database or RPC provider was contacted. The work is local and unpushed; the candidate remains at migration 435. Capability classification: 46 baseline-retained, 7 deployed, 13 prepared. Checklist: 639 complete / 19 open. Signed Data Stream attachment-byte delivery, live EAS validation, populated parity, actual key provisioning, credit-custody writes, domain-table RLS, production recovery, physical Raspberry Pi, release certification, and reviewed cutover remain open.

**Pushed checkpoint — 18 October 2026:** PR #68 continues on `feat/mobile-offline-acceptance`. Latest pushed source commit: `5eefa4c2`; CI #493 and Security #217 passed on that head ([CI](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/39152583925); [Security](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/39152583914)). The local candidate has 426 applied schema entries through migration 435 and six applied seed entries; its schema-only plan has zero pending entries. Migration 435 followed a fresh encrypted checkpoint and isolated restore rehearsal, with matching 431-row migration-ledger fingerprints, extension versions, and 1,396 public relations ([rollout evidence](builds/2026-10-18-recovery/candidate-migration-435-rollout.json)). Current-source ARM64/QEMU app/PostGIS runtime replay remains through migration 434; a separate image smoke from `9e02eeff` built `linux/arm64` and imported the RPC worker offline. Local RPC follow-ups now use exact decimal half-up conversion in both scheduled and legacy manual paths, hash the same numeric JSON bytes sent to PostgreSQL, and request each isolated run's wallet reads at one block height and timestamp. The isolated worker buffers observations and rechecks the selected block hash before persistence; the legacy CLI uses the same per-chain anchor and rolls back its transaction if the hash changes before commit. Neither path pins reads to the hash or recovers later reorganizations. The combined focused worker/legacy boundary set passes 284 tests, with disposable PostgreSQL confirming exact eight-decimal storage. The latest SDK batch adds read models and typed location-scoped readers for credit-ledger, finance, ecological/MRV, metrics, forecast, market, and value-flow records; the focused SDK slice passes 96 Python tests and 46 JavaScript tests, TypeScript build, Ruff, compilation, schema and capability guards. Six SDK commits were pushed together as `5eefa4c2`; CI #493 and Security #217 passed on that head. The local candidate stays through migration 435. These checks do not establish physical Raspberry Pi, power-loss, sustained performance, provider, or MAN-CAP acceptance. A package-wide Ruff scan still reports 39 findings in untouched generated/example files. The matrix remains 54 baseline-retained, 7 deployed, and 5 prepared. Checklist: 620 complete / 19 open. Tenant/RLS, provider parity, physical Raspberry Pi, production recovery, release certification, and cutover remain open.

**Pushed RPC worker batch — 18 October 2026 (`9e02eeff`):** The native RPC JobSpec now targets a default-off, chain-scoped wallet-balance snapshot worker with an exact worker DSN and provider endpoint map. Migration 436 provides bounded lock, wallet lookup, snapshot/outbox, and completion functions; disposable network-disabled PostgreSQL 16 acceptance passed replay, forced-RLS writes, idempotency, legacy same-block reuse, legacy CLI duplicate handling without a missing unique index, conflict/malformed-identity rejection, and direct-table denial. The focused worker boundary suite passed 272 tests with Ruff, compilation, Compose config, and regenerated source inventories. An additional `linux/arm64` image build and QEMU worker-import/snapshot smoke passed with networking disabled; its temporary image was removed, and candidate containers remained healthy ([ARM64 evidence](builds/2026-10-18-recovery/arm64-rpc-worker-image-smoke.json)). The candidate remains through migration 435; no credential, provider, persisted schedule, or feature activation was used. It does not add transaction-history scanning, confirmation depth/finality, or reorg recovery. Checklist at push: 610 complete / 19 open; capability counts unchanged ([checks](builds/2026-10-18-recovery/rpc-indexer-worker-checks.json)).

**Local RPC consistency follow-up — 18 October 2026:** review found that binary-float wei conversion could lose precision, and fetching a fresh block height per wallet could mix heights inside one snapshot run. The isolated worker now uses `Decimal` half-up rounding, hashes the exact numeric JSON sent to PostgreSQL, and requests every wallet at one block height and timestamp. It buffers observations and rechecks the selected block hash before persistence. The legacy CLI now shares the per-chain block height and timestamp and rolls back all run rows when the hash changes before commit. Neither path pins reads to the hash or recovers later reorganizations. The legacy manual path also keeps balances and parsed transaction values as `Decimal` through PostgreSQL and ClickHouse payload preparation. The combined nine-suite worker/legacy boundary set passes 284 tests. Disposable network-disabled PostgreSQL 16 acceptance stores `0.00000001` exactly through migration 436. Ruff, Python compilation, and regenerated worker/runtime inventories pass. This follow-up is local and not yet pushed; the candidate stays through 435 and no RPC provider or runtime database was used ([checks](builds/2026-10-18-recovery/rpc-indexer-worker-checks.json); [database evidence](builds/2026-10-18-recovery/rpc-indexer-worker-disposable.json)). Checklist: 614 complete / 19 open.

**Prior pushed batch — 18 October 2026 (`641a04b9`):** The local candidate migration rollout is complete: a fresh encrypted checkpoint was restore-rehearsed, the ordered runner applied only migration 435, the schema ledger reports 426 applied schemas with zero non-applied entries and six applied seeds, and candidate health is good ([rollout evidence](builds/2026-10-18-recovery/candidate-migration-435-rollout.json)). Migration 435 closes conflicting stable financial outbox-key reuse; its disposable PostgreSQL 16 replay, forced-RLS, exact-replay, conflict-rollback, and ACL checks also pass. Directus was not running; rebuild its hook before enabling any Directus write profile to prevent duplicate projection. Financial update/delete reconciliation, historical backfill, populated report parity, candidate provider delivery, and named MAN-CAP acceptance remain open. Checklist: 608 complete / 19 open; capability matrix: 54 baseline-retained, 7 deployed, 5 prepared.

**Historical branch checkpoint — 17 October 2026:** PR #68 was at `efdd05b5`; CI #433 was in progress and Security #157 passed. CI #431 failed eight generated worker-inventory freshness/source-contract checks on the preceding head after 5,851 tests passed. Security #156 and CI #432 passed on `ebeddb45`. The pushed correction refreshed five worker inventories and removed line-number coupling from the SQL statement-kind regression; all 30 focused inventory tests passed, with all five generated checks, Ruff, Python compilation, and capability-matrix validation passing locally. The batch also refreshed report source/query/helper inventories that fixed CI #430. Worker-status output containment redacted historical scheduler, EventBus, MQTT delivery, and ClickHouse outbox dead-letter errors. The optional gRPC health adapter reported only a bounded remote exception class and closed the channel. At that historical checkpoint, the checklist was 517 complete / 19 open; these counts are superseded by [batches.md](batches.md).

**Implementation batch pushed — 17 October 2026:** Impact Office status reads, sandbox run history, and agent action audit records now redact persisted diagnostics while retaining failure presence and run/action identity. Gateway audit database and local-journal failure logs retain only exception classes while preserving fallback behavior; Gateway internal errors log only the exception class and return the generic 500. PostgreSQL, ClickHouse, and Directus health probes also log only exception classes and preserve generic status results. The worker-history changes pass 34 focused checks; agent-audit/safety checks report 11 passed and nine database-dependent skips; Gateway audit has nine passing checks, the route/auth slice has 34, and health/driver-registry checks have 33. Ruff and compilation pass. The schedule ownership guide matches all 17 generated JobSpecs, including the `eas_legacy` compatibility fallback. Candidate migrations 417–419 were already present in the 423-migration pre-433 baseline; the isolated notification feature remains disabled pending its encrypted credential. No database, worker, sandbox execution, schedule, provider, or local journal was accessed in that pushed batch. The checklist at that point was 502 complete / 20 open; named transport, tenant, and live worker acceptance remain open.

**Current local credential-preparation batch — 17 October 2026:** A fresh notification-enqueue password and DSN are staged in encrypted `.env.sops`; SOPS round-trip and changed-key-scope checks pass without displaying plaintext. The feature flag remains false, and no login/grant was provisioned or database/provider contacted. The current checklist is 504 complete / 19 open. Candidate role provisioning, external delivery, and activation review remain open.

**Pushed CI correction — 17 October 2026 (`ebeddb45`):** CI #431 failed because five generated worker maps were stale and one inventory regression asserted obsolete source line numbers; eight tests failed while 5,851 passed. All five reports now match current sources, and the SQL classification test asserts statement kinds by source file instead of fixed line offsets. The focused worker inventory suite passes 30 tests; generated report checks, Ruff, compilation, `git diff --check`, and capability-matrix validation pass. No database, worker, or provider was used. The correction has been pushed; hosted CI/Security results for `ebeddb45` are pending ([evidence](builds/2026-10-17-recovery/ci-431-worker-inventory-fix.json)).


**Pushed EAS worker batch — 17 October 2026:** Native scheduled EAS
indexing now routes through a default-off isolated worker and dedicated login.
Migration 433 adds bounded chain lock, recipient, cursor, page/outbox, and status
functions; the login has no direct table privileges and the protocol data is
global, so the worker does not assert a location tenant context. The EAS
GraphQL contract is extracted from the shared-database legacy module so the
isolated child can start with shared PostgreSQL settings stripped. The 277-test
focused EAS/scheduler/runtime-role/source-map suite, Ruff, compilation,
generated worker/runtime inventories, and disposable PostgreSQL 16 forced-RLS
and migration-replay check pass. After an age-encrypted checkpoint and isolated
restore rehearsal, migration 433 is applied to the local candidate; the app
was rebuilt and health/protected-route behavior verified. Both EAS roles remain
NOLOGIN, and no worker credential, persisted task, or live EAS endpoint was
used. Task reconciliation, provider pagination/recovery parity, live runtime
acceptance, and MAN-CAP acceptance remain open ([migration](../../schemas/postgres/433_isolated_eas_indexer.sql);
[worker](../../services/ingestion/eas_worker.py);
[provider contract](../../services/ingestion/eas_provider.py);
[disposable evidence](builds/2026-10-17-recovery/eas-indexer-worker-disposable.json);
[candidate rollout](builds/2026-10-17-recovery/candidate-migration-433-rollout.json)).
The provider adapter now fails closed on GraphQL errors, partial responses,
invalid JSON, and missing data; the worker refuses a response missing its
attestations field before cursor advancement. It now validates newest-first page
ordering and stops pagination after crossing below the saved timestamp cursor,
while retaining the inclusive cursor second. Twenty-two mocked EAS
provider/worker/cursor tests plus Ruff and compilation pass. This does not close
concurrent offset-page stability or earlier-than-cursor recovery; no live
endpoint was queried ([error evidence](builds/2026-10-17-recovery/eas-provider-graphql-error-contract.json);
[cursor-scan evidence](builds/2026-10-17-recovery/eas-cursor-boundary-scan.json)).
The worker now also rejects absent, null, boolean, negative, fractional,
malformed, and out-of-range attestation timestamps before persistence or cursor
advancement; seven focused cases pass within the combined 36-test EAS suite. An optional
`--replay-lookback-seconds` enables operator-selected idempotent replay below a
saved cursor without lowering it; zero remains the default. Six focused
replay/argument/output checks pass, and successful worker output reports the
selected interval. This does not recover arrivals beyond a requested
interval or close concurrent offset-page movement ([timestamp evidence](builds/2026-10-17-recovery/eas-timestamp-contract.json);
[replay evidence](builds/2026-10-17-recovery/eas-explicit-replay-lookback.json)).
**Local code-first follow-up — 17 October 2026:** the isolated worker detects
an identical attestation-ID fingerprint on consecutive full provider pages and
stops before another page write or cursor advancement. It keeps only one page
fingerprint in memory, so the guard stays bounded; already persisted pages
remain safe for idempotent retry. The repeated-page regression, all 36 EAS
provider/worker/cursor tests, 130 scheduled-command contract tests, and 50
worker/runtime inventory tests pass. Ruff, compilation, capability-matrix
validation, and all generated inventory checks pass. CI #408 later failed on
two stale test contracts in the pushed baseline; both local test corrections
pass and await the next batch push ([evidence](builds/2026-10-17-recovery/eas-repeated-page-guard.json)).
**Local EAS offset-stability follow-up — 17 October 2026:** the worker now
compares each in-scope page with the preceding full page and fails before
persistence on any shared attestation ID. It also rejects duplicate IDs within
a page and checks a shorter terminal page. This catches adjacent overlap caused
by repeated offsets or common front-of-result-set shifts while retaining only
one page of IDs. The combined EAS, scheduled-command, and worker/runtime
inventory suites pass 219 tests (39, 130, and 50 respectively), with Ruff,
compilation, capability-matrix validation, and generated inventory checks
passing. No provider or database was contacted. Gaps without adjacent overlap,
non-adjacent cycles, earlier-than-cursor arrivals, and live endpoint behavior
remain open. CI #408 failed on two stale test contracts in pushed commit
`4f5be68d`; their corrections pass the affected local tests and await hosted
confirmation ([evidence](builds/2026-10-17-recovery/eas-offset-overlap-guard.json)).
**Local Gnosis error-containment follow-up — 17 October 2026:** Gnosis RPC
block-height and block-range exceptions no longer expose raw provider details
in scheduler errors or `chain_indexer_status`; ClickHouse outbox errors retain
their type but use a fixed message. The 13-test mocked Gnosis recovery suite,
Ruff, and compilation pass. No provider or database was contacted. CI #408
failed on two stale test contracts in pushed commit `4f5be68d`; both fixes are
in the next local batch. Historical receipt reconciliation, removed-log/deep-reorg
recovery, and live provider acceptance remain open
([evidence](builds/2026-10-17-recovery/gnosis-error-sanitization.json)).
**Pushed remote-sensing error-containment follow-up — 17 October 2026:** signed
and legacy remote-sensing job paths now normalize provider errors before
attempt/job persistence and scheduler output; provider adapter logs retain only
exception classes. Legacy ClickHouse outbox failures keep their type and
rollback behavior with a fixed summary. Seventy-four focused mocked
worker/scheduler/automation
checks pass with Ruff, and no provider or database was contacted. Source parity
and MAN-CAP acceptance remain open
([evidence](builds/2026-10-17-recovery/remote-sensing-error-sanitization.json)).
This slice is in commit `541d3eb0`.
**Pushed EAS error-containment follow-up — 17 October 2026:** legacy and
isolated EAS indexing now remove raw provider details from chain status,
ingestion audit, logs, and scheduler errors. Outbox failure keeps its typed
exception and rollback semantics with a fixed message; isolated persistence
wrappers suppress raw database exception context. The 184-test EAS/provider/
scheduler/operation-map suite and Ruff pass. No provider or database was
contacted; live endpoint recovery and pagination remain open
([evidence](builds/2026-10-17-recovery/eas-error-sanitization.json)).
This slice is in commit `541d3eb0`.
**Pushed provider failure-containment batch — 17 October 2026 (commit f432b933):** the
shared outbox now suppresses database exception causes on enqueue
failure and persists/logs only fixed delivery summaries and exception classes.
The focused outbox/producer suite passes 101 tests with Ruff. No database or
ClickHouse endpoint was contacted; runtime delivery acceptance remains open
([evidence](builds/2026-10-17-recovery/clickhouse-outbox-error-sanitization.json)).
The RPC indexer now also stores and reports only bounded failure summaries
while preserving per-wallet savepoints, outbox rollback, and connection cleanup;
six mocked contract/recovery tests pass with Ruff
([evidence](builds/2026-10-17-recovery/rpc-indexer-error-sanitization.json)).
The Baal indexer also aborts a block batch on provider query failure, preserves
the last committed cursor in its failure status, and sanitizes provider and
database errors. Four mocked recovery tests and Ruff pass; historical receipt
and reorg recovery remain open
([evidence](builds/2026-10-17-recovery/baal-indexer-error-recovery.json)).
**Local weather follow-up — 17 October 2026:** the legacy current-weather and
forecast runners now store bounded failure summaries and omit provider details
from direct ClickHouse fallback logs. Four new mocked regressions pass within a
26-test weather scope/atomicity suite with Ruff; no endpoint or database was
contacted ([evidence](builds/2026-10-17-recovery/weather-legacy-error-redaction.json)).
The GEE climate adapter now also redacts initialization and MODIS/SMAP/
Sentinel-1/ERA5 failures from logs and returned results. Six new mocked tests
pass inside a 44-test climate suite with Ruff; no provider or database was
contacted ([evidence](builds/2026-10-17-recovery/gee-climate-error-redaction.json)).
**Local freshness follow-up — 17 October 2026:** failed measurements now store
bounded evaluation summaries and log only the exception class. Savepoint rollback
and preservation of the previous stale/critical state remain unchanged. The
33-test mocked freshness suite passes with Ruff and no database or destination
was contacted ([evidence](builds/2026-10-17-recovery/freshness-query-error-redaction.json)).
**Local MQTT follow-up — 17 October 2026:** callback and ClickHouse fallback logs
now report exception classes only. QoS 1 failures still remain unacknowledged
for broker retry and propagate a bounded error. Three new mocked checks pass
within the 74-test MQTT/producer suite with Ruff and no live service access
([evidence](builds/2026-10-17-recovery/mqtt-subscriber-error-redaction.json)).
**Local HTTP sensor follow-up — 17 October 2026:** device lookup and reading
processing failures now omit raw details from logs and preserve bounded,
retryable 503 responses; direct ClickHouse fallback logs are bounded too. Three
new TestClient regressions pass within a 50-test HTTP/MQTT suite with Ruff; no
live service was contacted ([evidence](builds/2026-10-17-recovery/http-sensor-error-redaction.json)).
**Local anomaly-notification follow-up — 17 October 2026:** SMTP, Directus, and
actuator failure logs retain only exception classes. Critical severity continues
to force human approval. Three new mocked checks pass within a 72-test
anomaly/IoT suite with Ruff; no delivery service or database was contacted
([evidence](builds/2026-10-17-recovery/anomaly-notification-error-redaction.json)).
**Local MQTT actuator follow-up — 17 October 2026:** direct client-creation and
publish failures now log only exception classes. Two new mocked checks pass in
the 64-test actuator/anomaly suite with Ruff; no broker or database was
contacted ([evidence](builds/2026-10-17-recovery/mqtt-actuator-error-redaction.json)).
**Current local shared-ingestion follow-up — 17 October 2026:** owned-connection
audit and indexer-status write failures now log only exception classes.
Caller-owned errors still propagate; owned connections close. Two mocked checks
pass with Ruff ([evidence](builds/2026-10-17-recovery/ingestion-base-error-redaction.json)).
**Current local price-provider follow-up — 17 October 2026:** Yahoo Finance
fetch/audit failures and Oracle sync failures omit raw exception text from logs
and returned results. Three new mocked redaction regressions pass within the
74-test price, Oracle, shared-ingestion, market-data, and outbox suite with Ruff
and compilation; no provider or database was contacted
([evidence](builds/2026-10-17-recovery/price-provider-error-redaction.json)).
The EAS price-attestation fallback now also logs only the exception class while
preserving the audit commit and best-effort response; one new mocked regression
passes in the updated 76-test combined suite
([evidence](builds/2026-10-17-recovery/price-attestation-error-redaction.json)).
Legacy CSV sensor ingestion now redacts invalid source cells and row-processing
details from logs/audit, while retaining rollback and canonical projection
failure propagation. Four new mocked regressions pass in an 88-test
sensor/driver/outbox suite with Ruff and compilation
([evidence](builds/2026-10-17-recovery/sensor-ingester-error-redaction.json)).
Demo-only EAS, Gnosis, and remote-sensing ClickHouse fallbacks now log only
exception classes, while connection-backed outbox errors still propagate.
Four new mocked regressions pass within 63 outbox/indexer/worker tests with
Ruff and compilation ([evidence](builds/2026-10-17-recovery/clickhouse-fallback-error-redaction.json)).
GIS and remote-sensing CSV ingestion also redacts invalid spatial/source input
and raw row/database exception details while preserving rollback; five new
mocked regressions pass within 67 GIS/remote-sensing/outbox tests with Ruff and
compilation ([evidence](builds/2026-10-17-recovery/geospatial-import-error-redaction.json)).
The EAS signer now persists/returns only bounded exception summaries for failed
requests while preserving failed status and attempt counting; one new mocked
regression passes within 52 attestation/EAS tests with Ruff and compilation
([evidence](builds/2026-10-17-recovery/attestation-signer-error-redaction.json)).
Post-confirmation carbon-retirement chain failures likewise return/log only a
bounded summary while preserving the reviewer gate, committed internal state,
and non-blocking sync; one new mocked regression passes within 53 credit and
chain-sync tests with Ruff and compilation
([evidence](builds/2026-10-17-recovery/carbon-retirement-chain-error-redaction.json)).
Credit batch mint/retirement, RPC initialization, and balance verification
also omit provider details; query failures cannot be reported as a match, and
best-effort batch issuance returns a bounded error summary. Five new mocked
regressions pass within 27 credit-chain/batch tests with Ruff and compilation
([evidence](builds/2026-10-17-recovery/credit-chain-error-redaction.json)).
Data Stream batch anchoring also bounds per-post failures while retaining
successful pending requests and partial-success totals; one new mocked
regression passes within the 47-test Data Stream suite with Ruff and compilation
([evidence](builds/2026-10-17-recovery/data-stream-anchor-error-redaction.json)).
Remote harvest logs now retain a URL source reference without user-info/query/
fragment data, and provider failures are class-only in persisted/returned
messages; safe validation guidance remains. Two mocked regressions pass with
Ruff and compilation ([evidence](builds/2026-10-17-recovery/harvest-manager-error-redaction.json)).
Spatial GeoJSON/KML feature errors, invalid XML, and audit-write failures also
omit raw payload/database details while preserving partial-import behavior;
four new regressions pass within a 22-test spatial-import/security suite with
Ruff and compilation
([evidence](builds/2026-10-17-recovery/spatial-import-error-redaction.json)).
The legacy KML/Shapefile adapters also bound parser, feature, and source-read
errors without returning source coordinates or contributor names; three new
synthetic regressions and two existing compatibility checks pass with Ruff and
compilation ([evidence](builds/2026-10-17-recovery/legacy-geo-import-error-redaction.json)).
Reporting cadence no longer returns report-generator stdout/stderr; failed
commands keep the exit code and safe status summary, and completion remains
success-only. Three mocked regressions pass within 34 cadence/source tests with
Ruff and compilation
([evidence](builds/2026-10-17-recovery/reporting-cadence-output-redaction.json)).
Process simulation now returns only an exception-class summary on calculation
failure while retaining rollback and cancelled lifecycle state; one mocked
regression passes with Ruff and compilation
([evidence](builds/2026-10-17-recovery/process-simulation-error-redaction.json)).
Feedback automation now bounds evaluation and full-cycle errors in both API
responses and persisted logs while preserving rollback and run-state behavior;
two new regressions pass within its 14-test suite with Ruff and compilation
([evidence](builds/2026-10-17-recovery/feedback-automation-error-redaction.json)).
Local harvest no longer stores or returns host file paths; file-read errors are
bounded in API and durable log values. Two mocked regressions pass within seven
harvest tests with Ruff and compilation
([evidence](builds/2026-10-17-recovery/local-harvest-error-redaction.json)).
Spatial block and leave-one-out cross-validation now suppress raw per-fold
prediction failures while retaining aggregate fold behavior; two new mocked
regressions and six existing cross-validator checks pass with Ruff and
compilation
([evidence](builds/2026-10-17-recovery/spatial-cv-error-redaction.json)).
Forecast batch and dashboard-projection failures are now class-only, the
scenario name is omitted from failure output, and the dashboard connection
closes on failed writes; two mocked regressions pass within the forecast suite
with Ruff and compilation
([evidence](builds/2026-10-17-recovery/forecast-error-redaction.json)).
The EventBus child protocol now redacts handler and malformed-request details;
the parent accepts only a validated exception-class field or a fixed fallback
before persisting a delivery error. Its 34-test runner/durability suite passes
with Ruff and compilation
([evidence](builds/2026-10-17-recovery/event-handler-error-redaction.json)).
Composite state, graph, comprehensive-status, and strategic-reserve report
failures now use bounded summaries while retaining per-section continuation;
four mocked report regressions pass with Ruff and compilation
([evidence](builds/2026-10-17-recovery/report-state-error-redaction.json)).
The report-generator CLI now stores bounded failure summaries in automatic
run items and does not print raw single-report exceptions; two new regressions
pass within the 22-test report/read-only/CLI suite with Ruff and compilation
([evidence](builds/2026-10-17-recovery/report-generator-error-redaction.json)).
Saved-dataset refresh CLI failures now omit thrown exception contents and
returned query-error text, preserve all-mode continuation, and close the
single-refresh connection; four mocked regressions pass within the 12-test
read-only/CLI suite with Ruff and compilation
([evidence](builds/2026-10-17-recovery/dataset-refresh-error-redaction.json)).
Nested best-effort business-plan, reference-class, reward-calibration, and
simulation-reserve failures also use exception-class summaries within otherwise
successful report payloads; four mocked regressions pass in the report and
business-plan compatibility suite (41 passed, 2 database-backed tests
skipped) with Ruff and compilation
([evidence](builds/2026-10-17-recovery/nested-report-error-redaction.json)).
The governed file exporter also returns only bounded failure classes, removes
partial files, and keeps audit-write/cleanup warnings free of database error
text; three mocked regressions pass with the export reliability checks
([evidence](builds/2026-10-17-recovery/export-error-redaction.json)).
The four best-effort capital-accounting lenses also return bounded failure
summaries without dropping successful sections; focused failure injection and
the existing accounting suite pass with Ruff and compilation
([evidence](builds/2026-10-17-recovery/capital-accounting-error-redaction.json)).
Monte Carlo draws and clash sweeps now bound simulator errors while preserving
failure counts and continuation; variogram fitting omits raw model-library
diagnostics. Their 11-test suites pass with Ruff and compilation using
synthetic inputs ([simulation evidence](builds/2026-10-17-recovery/simulation-error-redaction.json);
[variogram evidence](builds/2026-10-17-recovery/variogram-error-redaction.json)).
SAFE-proposed attestation failures now persist and return only bounded
exception-class summaries, preserving per-request failure accounting; five
focused attestation tests pass without contacting a chain, SAFE service, or
database ([evidence](builds/2026-10-17-recovery/safe-attestation-error-redaction.json)).
The EAS CLI now follows the same boundary for top-level command failures and
best-effort signer status; seven focused attestation tests preserve the
nonzero-exit behavior without a live key or chain
([evidence](builds/2026-10-17-recovery/attestation-cli-error-redaction.json)).
The legacy subgraph caller also sanitizes provider/status/audit/log errors and
preserves typed outbox rollback; three focused mocked tests pass with Ruff
([evidence](builds/2026-10-17-recovery/subgraph-indexer-error-sanitization.json)).
**Code-first follow-up — 17 October 2026:** the legacy freshness-alert
sender now closes webhook responses on success and failure, retains only an
HTTP status or exception class for webhook/SMTP failures, and preserves the last
known alert state when a database measurement fails. Thirty-three focused tests
pass with Ruff and compilation; no destination or database was contacted. This
follow-up is included in pushed commit `4f5be68d` and awaits hosted CI
([delivery evidence](builds/2026-10-17-recovery/freshness-alert-error-containment.json);
[state evidence](builds/2026-10-17-recovery/freshness-alert-state-recovery.json)).
**Current code-first follow-up — 17 October 2026:** scheduled worker import
paths now remain usable with shared PostgreSQL settings stripped. An internal
worker marker prevents shared dotenv decryption and shared production DB
validation during import, while the canonical shared database factory fails
before connecting from isolated children. EventBus cache/notification handlers
retain the legacy path while their isolated features are disabled. The
focused worker/import/EventBus/scheduler suite passes 130 tests, all eight
scheduled worker `--help` checks pass, and Ruff, compilation, and diff checks
are clean. No candidate migration, database, provider, schedule, or real
credential was used ([evidence](builds/2026-10-17-recovery/isolated-worker-import-boundary.json)).
The current source-inventory refresh covers 31 operation roots and 93 source
files; 73 worker SQL sites still lack a static function path and the worker
boundary preflight remains `review_required`. The whole-service SQL inventory
covers 4,006 execution sites across 826 files. Generated worker/runtime maps
were regenerated after current source edits, their check modes pass, and the
eight focused inventory suites pass 50 tests
([latest worker inventory evidence](builds/2026-10-17-recovery/ci-431-worker-inventory-fix.json);
[runtime inventory evidence](builds/2026-10-17-recovery/worker-inventory-refresh-current.json)).
**Previous pushed functional batch:** Gnosis cursor separation and RPC wallet atomicity are in commits `caa3426` and `6d76eb9`. At the functional push, Security run #104 was in progress and CI run #380 was pending. Earlier pushed batches include Gnosis checkpoint/replay recovery (`4531a03`, `b024ef5`), the EAS cursor rebaseline (`272fcde`), and market-data recovery (`46d3ef3`).
**Previous functional batch:** Migration 424 separates the Gnosis Moloch cursor from wallet RPC while preserving the legacy status row and requiring operator review before advancing an inherited cursor. The RPC wallet indexer commits activity, status, and ClickHouse outbox intent together, with per-wallet savepoints and error status on partial failure. The 184-test Gnosis cursor suite and 133-test RPC recovery/contract/outbox/scheduler suite pass with Ruff and compilation; disposable PostgreSQL 16 receipt checks and network-disabled cursor migration/replay checks pass. Historical receipt backfill, Gnosis deep-reorg recovery, RPC transaction-history coverage, confirmation depth, and provider/runtime parity remain open; no live provider, candidate, legacy database, or schedule was accessed.

**Previous pushed functional batch:** Commit `61088543` routes native NOI snapshot reconciliation through its dedicated default-off worker, exact secret mapping, and migration 425's signed `noi_snapshot/reconcile` function. Its source/scheduler/inventory suite passed 193 tests and seven isolated PostgreSQL checks passed.

**Previous pushed functional batch — 17 October 2026:** Scheduled current-weather ingestion now uses the dedicated default-off `services.ingestion.weather_worker`; migration 427 adds signed location lookup and bounded atomic observation/audit/outbox/receipt storage. Commit `b41f4068` is on the remote feature branch. Its 178 focused tests and nine disposable PostgreSQL 16 checks pass; the candidate remains through migration 403 and the feature/grants are not deployed.

**Previous code-first batch — 17 October 2026:** The native Market Data JobSpec now routes through a default-off isolated World Bank worker, while the manual CLI, seed path, and legacy persisted-task entrypoint remain available. Migration 430 adds a dedicated login boundary and bounded price/audit function; runtime-role provisioning keeps the login disabled until its distinct encrypted password is supplied. The 199 focused worker/market/scheduler tests, Ruff, compilation, generated inventories, and six disposable PostgreSQL 16 forced-RLS checks pass. No live provider, candidate or legacy database, or persisted schedule was accessed. At that point the checklist had 435 checked / 21 open items; the 66-row matrix had 54 baseline-retained, 7 deployed, and 5 prepared, with zero accepted MAN-CAP checks. Provider parity, schedule ownership, and CAP-040/047 acceptance remain open ([migration](../../schemas/postgres/430_isolated_market_data_worker.sql); [evidence](builds/2026-10-17-recovery/market-data-worker-disposable.json)).

**Previous local code-first follow-on — 17 October 2026:** Scheduled sensor pulls compare persisted registry values with an immutable source-controlled name/type/module/class mapping before importing; the built-in `sensor_csv` scheduled reader additionally confines paths beneath a configured root, rejects traversal and symlinks, and uses `O_NOFOLLOW` descriptor opens. Compose mounts that root read-only and lets operators select the host input directory. Manual driver operations remain unchanged. The focused sensor schedule/CLI/command-contract/worker-map suite passes 179 tests; Ruff, compilation, generated inventories, three Compose profile config checks, and the capability-matrix check pass. Tests use synthetic temporary files; no configured input, database, driver instance, provider, or schedule was accessed ([allowlist evidence](builds/2026-10-17-recovery/scheduled-sensor-driver-code-allowlist.json); [contract](sensor-driver-scheduled-contract.md); [path evidence](builds/2026-10-17-recovery/scheduled-sensor-csv-path-confinement.json)).

**Current local code-first follow-on — 17 October 2026:** Scheduled CSV sensor
ingestion now runs through a dedicated default-off `sensor_ingestion` worker
with exact DSN/credential routing and no shared PostgreSQL fallback. Migration
431 adds signed driver/catalog lookup, bounded atomic reading/event/audit/
ClickHouse-outbox writes, duplicate suppression, and location-bound status
auditing. The 200 focused sensor-worker/scheduler/runtime-role checks, Ruff,
compilation, generated worker inventories, capability-matrix validation, and
five disposable PostgreSQL 16 forced-RLS checks pass. The runner now waits for
PostGIS's final TCP listener before applying migrations. The candidate remains
at migration 403; migration 431, the login/grant, and the feature are not
deployed or enabled, and persisted tasks remain on the legacy entrypoint until
schedule owners reconcile them. No real sensor input/provider, credentials,
candidate or legacy database, or schedule was used. The checklist is now 436
complete and 21 open (457 total); MAN-CAP-040/047 remain open ([worker](../../services/ingestion/sensor_worker.py);
[migration](../../schemas/postgres/431_signed_sensor_driver_worker.sql);
[evidence](builds/2026-10-17-recovery/signed-sensor-ingestion-worker-disposable.json)).

**Current local security follow-on — 17 October 2026:** Exact source-mapped
EventBus handlers now receive only their dedicated worker DSN and credential;
shared PostgreSQL settings and global geospatial provider secrets are removed
from those child environments. Unmapped legacy handlers retain their current
environment pending dedicated identities. The Kernel supervisor's scheduler
child allowlist is derived from the same module-to-worker map, including the
climate, market-data, sensor-ingestion, and remote-sensing workers. The expanded
scheduler/EventBus boundary suite passes 224 tests. The separate notification
worker receives the notification-enqueue identity needed by its mapped alert
handlers, and the EventBus process receives only the identities used by its
source-mapped handler children. Ruff, compilation,
dependency-group and provider-boundary checks pass. No database, provider,
candidate, legacy stack, or real credential was accessed. This does not close
live worker credential provisioning or broader runtime recovery ([evidence](builds/2026-10-17-recovery/event-handler-dedicated-environment.json)).

**Previous code-first batch — 17 October 2026:** Scheduled climate refresh uses the default-off signed `services.ingestion.climate_worker`; the manual CLI remains intact. Migration 429 provides signed location/bbox lookup and source-specific bounded writes for WorldClim, ERA5-Land, MODIS, SMAP, and Sentinel-1 summaries, with same-transaction ingestion audits and no direct climate-table grants. The 156-test climate/worker/scheduler suite, Ruff, compilation, generated worker inventories, and nine disposable PostgreSQL 16 forced-RLS checks pass. No real provider/key, candidate or legacy database, or schedule was accessed. Migrations 428–429 are not deployed. Worker credentials/location grants, live provider parity, provider ownership, and rollout remain open ([migration](../../schemas/postgres/429_signed_climate_worker.sql); [evidence](builds/2026-10-17-recovery/climate-worker-disposable.json)).

This plan orders the remaining work so repository changes and reproducible
software checks happen before decisions that require production owners, live
provider accounts, populated reference data, or external infrastructure. It is
an execution map for the existing open items in [batches.md](batches.md), not a
second capability acceptance ledger. Keep the capability matrix's named
MAN-CAP checks open until each has its own retained evidence.

## Current accounting

The latest security-hardening batch was pushed to the PR branch as `efdd05b5`.
Across these slices, raw exception messages, model paths, identifiers, and
child output are replaced with bounded summaries while rollback, retry, and
fallback behavior remain intact. Each slice has focused regression evidence in
`docs/refactor/batches.md`; the newest ML/model-security/retraining/import suite
passes 57 tests and regenerated worker-import closure checks pass. CI #433 is in progress and
Security #157 passed on `efdd05b5`; the preceding `ebeddb45` head
passed CI #432 and Security #156.

The live candidate ledger now confirms 424 applied schema migration IDs through
migration 433, six applied seed-ledger entries, and zero pending or failed
rows. A read-only Docker inventory confirms the candidate app, PostgreSQL, and
Metabase are healthy and the proxy is running; the database is published only
on `127.0.0.1:5433`, and the legacy `kokonut-intelligence` containers are
stopped. This supersedes earlier snapshots that described migration 403 as
current. The recorded rollout left application-table RLS disabled and EAS roles
NOLOGIN; worker credentials, grants, providers, and schedules remain gated. No
containers or database state were changed during this verification.

A recent local outbox batch gives canonical ingestion failures a typed
`OutboxEnqueueError` and rolls back or propagates it through weather, RPC,
remote-sensing provider dispatch, subgraph/EAS, and Gnosis transaction owners.
Nine producer helpers now have paired failure and connection-free fallback
regressions; 158 focused tests pass across outbox, weather, remote-sensing, and
attestation contracts. This does not close live provider/PostgreSQL recovery
acceptance ([evidence](builds/2026-10-16-recovery/ingestion-outbox-failure-atomicity.json)).

The climate scheduled path now has a default-off signed worker and migration
429's bounded source-specific location lookup and summary/audit functions. Its
156 focused checks, Ruff, compilation, worker inventory refresh, and nine
forced-RLS disposable PostgreSQL checks pass. Migration 429 is present in the
last recorded candidate schema through migration 433; no climate worker
credential, location grant, provider, or schedule was activated. See the
current batch summary and retained evidence above.

- The Gnosis indexer now commits each block range with its event projections,
  outbox intents, and status checkpoint. Migration 423 adds new-event receipts:
  identical log identities are skipped and changed canonical block data fails
  closed. Migration 424 isolates the `gnosis_moloch` status cursor and preserves
  the shared legacy boundary in a paused row with provenance. The code requires
  an explicit operator `--from-block` before accepting that inherited boundary.
  The 184-test
  Gnosis/outbox/command/migration set, Ruff, compilation, and disposable
  PostgreSQL 16 migration/replay/duplicate/mismatch/rollback checks pass. No
  provider was contacted. Legacy receipt backfill and removed-log/deep reorg
  cleanup remain open
  ([checkpoint](builds/2026-10-16-recovery/gnosis-indexer-checkpoint-atomicity.json);
  [receipt evidence](builds/2026-10-16-recovery/gnosis-event-receipts-disposable.json);
  [cursor evidence](builds/2026-10-16-recovery/gnosis-indexer-cursor-disposable.json)).
- The market-data importer now propagates World Bank failures instead of
  treating bundled samples as provider success. Live and explicit-seed source
  keys are separate; provider payload validation happens before the database
  opens; and prices plus accurate `ingestion_log` counts commit atomically.
  Sixteen focused mocked tests, Ruff, and compilation pass. No provider or
  database was accessed; historical correction behavior and live parity remain
  open ([evidence](builds/2026-10-16-recovery/market-data-provider-atomicity.json)).

- ClickHouse outbox failures now use capped exponential retry delays (60 seconds
  through one hour), including client-setup failures; the retry schedule is
  derived from the persisted attempt count and retains the existing eight-try
  dead-letter bound and stable insertion token. Fifty-seven focused outbox,
  failure-injection, and producer tests pass with mocked boundaries. Live
  PostgreSQL/ClickHouse outage acceptance remains open
  ([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json)).

- The manual remote-sensing CSV path now requires a canonical location UUID or
  explicit `--all-locations`. Single-location SQL reads plots only within the
  selected location; every row must match plot/farm lineage, and accepted-row
  idempotency hashes use canonical IDs. Multi-location imports remain available
  behind the explicit aggregate selector. Fifty-five focused scope, outbox,
  smoke, and remote-sensing checks pass. This remains CLI/query-level scope,
  not operator authorization or RLS ([evidence](builds/2026-10-16-recovery/remote-sensing-csv-location-scope.json)).
- The weather-forecast producer now protects each location's complete forecast
  insert batch with a savepoint, propagates row errors for rollback, records
  success/failure audit entries on the same PostgreSQL transaction, and queues
  only successful batches for ClickHouse projection. Outbox enqueue failure
  propagates and closes without commit. Six new mocked regressions plus the
  forecast, scope, and shared producer suites pass 36 tests; Ruff, compilation,
  and diff checks pass. No provider or database was contacted, so live delivery
  and PostgreSQL transaction acceptance remain
  open ([evidence](builds/2026-10-16-recovery/weather-forecast-atomic-projection.json)).
- The execution checklist now has **517 checked and 19 open items (536 total)**,
  counting nested implementation subtasks. The open items cover live provider
  setup, digests, browser/runtime acceptance, tenant and Directus boundaries,
  populated report parity, policy activation, external delivery,
  long-duration recovery, and release/cutover gates.
- An earlier batch at `4d46800` made the owner-selected
  Gateway-only farm-activity boundary explicit in the optional Directus role
  seed. Twenty-four focused tests and fresh Directus 12.1.1 runtime apply,
  replay, health, and login checks pass; zero of the nine managed policies
  retain farm-activity grants, while 14 unrelated curated permissions remain.
  Unknown custom policy rows are preserved. The candidate and legacy databases
  were not touched. This adds no accepted capability: the matrix remains 66
  rows (54 baseline-retained, 7 deployed, 5 prepared), with zero accepted
  MAN-CAP checks.
- Since the previous `8c7a053` accounting, commit `a1f45da` added the native
  Gateway farm-activity API and migration 404, with 13 focused service/HTTP/
  policy tests and 11 disposable PostgreSQL 16 checks passing. Commit `359e1d5`
  then added and pushed the separate operator-console panel; six focused console
  contract checks pass, including inline JavaScript syntax validation. Migration
  404 has not been applied to the candidate, and no MAN-CAP check was accepted.
  Security #66 passed and CI #342 failed on a seed UPDATE that migration 404
  correctly rejects. The local fix embeds immutable lineage in pilot INSERTs
  and removes the later alignment UPDATE; 16 focused source checks passed, then
  the fix was included in a subsequent push. The later pushes also add anomaly
  transaction boundaries and the signed worker-context adapter described in
  the current status above.
- When this local batch began, the remote PR head was
  [`6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f`](https://github.com/wasalo/Kokonut-Intelligence/commit/6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f)
  on `feat/mobile-offline-acceptance`, PR #68. CI #336 was pending and
  Security #60 passed. The pushed batch includes ARM64 optional-profile checks
  and KGP worker restart/lease recovery with guild/domain/task projection and
  simulated reorg rebuild. The current local extension replays all 394 ordered
  schema sources, adds source-linked governance target/selector/guild-scope
  policy projections, and verifies seven-event canonical replay and rebuild on
  a simulated chain-tip change. The same disposable check verifies PostgreSQL
  restart reconnect and lease reclaim against the real cursor table. A fresh
  encrypted candidate checkpoint was restore-rehearsed before migration 403
  was applied; at that historical checkpoint the candidate had 394 applied
  schemas and zero pending, health 200, and protected-route 401. A later rollout
  advanced the candidate through migration 433. The application policy table
  was empty at the earlier checkpoint and RLS remains off. These synthetic rows and stubbed chain
  behavior use no seed, live RPC, or provider calls. Other event types, real
  chain reorgs, ARM64 hardware behavior, and live KGP RPC/event processing remain
  unverified. This batch is now pushed as `8c7a053`; CI #337 and Security #61
  are running. Earlier owner, tenant,
  report, retention, Directus, and worker-boundary work remains in the PR.
- The report generator now rejects read-only escapes through transaction
  settings, autocommit, and `cursor.connection`. Nine focused tests and an
  isolated PostgreSQL check pass; the latter proved rejected calculations
  leave no rows and the approved writer can still create the draft afterward.
  The database role remains capable of writes outside this guarded path, and
  populated report output parity remains open. An AST-only inventory now maps
  all 94 registered generators to source locations and declared inputs. A
  second inventory maps 177 direct query sites: 126 show a bound location-scope
  signal, including attestation queries bound by `subject_type='location'` and
  `subject_id`. Conditional, mixed, no-signal, and helper-only report paths
  still need scope-contract review. Neither inventory proves tenant isolation
  or semantic parity. Direct queue/detail service tests
  also verify the OIDC report-review tenant-context and cleanup contract.
- The scheduler now obtains a fresh bounded-timeout connection for each tick
  while preserving one worker ID. Ten focused scheduler tests pass. An earlier
  disposable PostgreSQL stop/start check used a stub engine; the current check
  replays scheduler/event migrations and uses the real SchedulerEngine to claim,
  launch, and complete bounded `services.events --process --batch-size 10`
  tasks before and after restart. A separate probe kills the real engine after
  it commits a due task lease but before subprocess dispatch; forced expiry in
  the disposable database lets a replacement worker mark the first run failed
  and finish the task as attempt two. It uses an empty synthetic EventBus queue
  and no provider. This covers claim-to-dispatch recovery only; a crash after
  task effects, full-ledger parity, and long-duration recovery remain open
  ([evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json)).
- A local EventBus worker slice now creates and closes its bus per iteration,
  recreates bounded-timeout notification connections, and retries logged
  failures. Twenty focused event-worker/EventBus tests pass with Ruff and
  compilation. A disposable PostgreSQL stop/start check replays migrations
  116, 165, and 375 and confirms the actual worker completes synthetic
  events before and after restart under one worker identity while invoking the
  real allowlisted alert-notification child handler. A fake webhook bound to
  `127.0.0.1` returned one synthetic `503`; the outbox recorded retryable/failed
  and then recovered to succeeded/succeeded after retry with the same
  idempotency key. The post-restart notification also succeeded with a distinct
  ID. A third request was received while its worker awaited the response; after
  the worker was killed and the fixture expired its lease, a replacement
  reclaimed the notification with attempt history `lease_lost,succeeded` and
  reused the idempotency key. No remote provider was contacted. Full
  migration-ledger parity, real provider delivery, production-duration lease
  recovery, and long-duration recovery remain open
  ([evidence](builds/2026-10-16-recovery/event-worker-postgres-reconnect.json)).
- A local KGP indexer change reconnects with a five-second timeout for each
  scan cycle, preserving lease ownership/reclaim semantics while containing
  rollback and failure-recording errors on a broken database connection.
  Sixteen focused KGP/guild tests pass. The current disposable check replays
  all 393 ordered PostgreSQL schema sources in separate transactions and
  records checksums. The real indexer processes synthetic `GuildCreated`,
  `DomainCreated`, and `TaskCreated` logs, confirms each projection links to its
  source event, and verifies canonical replay is idempotent. A stubbed tip
  change exercises reorg reset: all three events become noncanonical, dependent
  domain/task projections are removed, and retaining the configured guild key
  lets the replacement branch rebuild all three projections. The same check
  verifies PostgreSQL restart reconnect and expired-lease reclaim against the
  real cursor table. Deployment/cursor/contract/guild rows are synthetic; no
  seed, live RPC, or provider call is made. Other event types, real chain
  reorgs, production-duration lease reclaim, and live event recovery remain
  open
  ([evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json)).
- Directus source permissions now align with organization/location grants: the
  seed removes its obsolete user-level location filter while preserving other
  predicates, the grant hook covers `revenue_event`, and the isolated API
  fixture prepares a synthetic mapped operator. Five focused Python checks,
  61 extension tests, the TypeScript build, and a disposable PostgreSQL 16 SQL
  replay/fail-closed check pass. Pinned-image Field Note own/cross reads pass
  through the loaded tenant hook. Field Worker `farm_activity` permissions are
  hidden by the unlicensed Directus custom-permission boundary, so that API
  slice remains denied. The owner selected Gateway operations while keeping
  Directus optional; Gateway farm-activity operations are now the selected
  direction. Directus role/field/relationship and hook-dispatch parity
  remain open. This slice is included in the latest pushed head ([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json)).
- The capability matrix contains 66 capabilities: 54 baseline-retained, 7
  deployed, and 5 prepared. None of the 66 named MAN-CAP checks is accepted.
- The live local candidate ledger has 424 applied schemas through migration
  433, six applied seed-ledger entries, zero pending rows, and zero failed
  rows. The candidate app, PostgreSQL, and Metabase report healthy, with the
  proxy running; the database host binding is loopback-only on port 5433.
  Earlier rollout evidence records health 200 and anonymous protected-route
  access 401. Application-table RLS is
  disabled. The five owner-approved reference catalogs and migrations 401–402
  are applied; 115 other seed files remain held. It still uses the `kokonut` superuser because a separate
  runtime credential is not provisioned. The seed approval does not authorize
  RLS or production import.
- The owner selected self-hosted ZITADEL, organization/location authorization,
  Kokonut Network operation of Genesis, Seeds, Adelphi, Terra Viva, and V1,
  reference catalogs only with pilot rows held, USA and Dominican Republic as
  retention jurisdictions, and a 24-hour recovery target. Retention windows and
  legal-hold rules must be runtime-configurable; no durations are hardcoded or
  selected now. Policy configuration, approval roles, and hold operations are
  deployment gates. ZITADEL host/client settings, remaining operator/location
  mapping, R2 credentials, and external alert routing remain open.
- ARM64 Buildx/QEMU acceptance now exercises all 393 current schema files
  through migration 402, with matching logical-restore fingerprints, zero
  pending migrations, PostGIS geometry, health, protected-route denial,
  database-restart health recovery, and explicit Compose recovery after an app
  SIGKILL. The current refresh had no explicit CPU/memory caps and started the
  app before migrations, so workers logged missing-schema errors during
  bootstrap. This does not certify physical Raspberry Pi performance,
  power/storage/network failure, or production failover ([evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-402.json)).
  The default, OIDC, gRPC, and MQTT application targets also build for ARM64;
  network-disabled QEMU checks import their runtime/stubs, the pinned Mosquitto
  binary reports `aarch64`, and merged planner configs select ARM64 for every
  enabled service. No gRPC/PostgreSQL server or MQTT traffic/mTLS was tested
  ([transport evidence](builds/2026-10-16-recovery/kernel-arm64-transport-smokes.json)).
- Encrypted checkpoints now authenticate their manifests and have an optional
  S3/R2-compatible transfer CLI. Fake-store checks cover staged byte verification,
  create-only completion, idempotency, tamper rejection, and private no-overwrite
  restore. No live credentials or remote objects were used; R2 acceptance remains
  open ([contract](backup-object-storage.md); [offline evidence](builds/2026-10-15-recovery/backup-object-transport-offline.json)).

## Selected open gates: code batches before owner inputs

The owner selected the remaining open items in `batches.md` on 14 October.
On 15 October the owner supplied additional product/deployment decisions; see
the record below. Work through code batches first, then close only the live
provider, populated-data, and operational gates that cannot be established from
the repository.

## Owner decisions recorded 15 October 2026

- **Tenant ownership:** Kokonut Genesis, Kokonut Seeds, Kokonut Adelphi,
  Kokonut Terra Viva, and Kokonut V1 are operated by Kokonut Network. Adelphi
  and Genesis remain confirmed exclusive. No sharing was specified for the
  other three, so do not create shared grants without a later explicit mapping.
  The four existing farms have owner-held data for post-build ingestion;
  Terra Viva is still in design. This is an operating-tenant mapping, not a
  claim about legal land title. Other locations remain unassigned until mapped.
- **Tenant model:** Directus-compatible access follows organization/location
  grants. The Gateway remains the authorization authority; Directus parity
  must consume the same grant model.
- **Reports/providers:** port all repository-verified Kokonut report, dashboard,
  provider, and scheduled-job capabilities first. The owner will decide what to
  retain, remove, or improve after review. Validate semantic report output
  after the four farms' data is ingested. The archive's generic e-commerce
  sample-H2 Metabase cards are not to be mislabeled as Kokonut product assets.
- **R2:** production account `7219a605e3c2144a30987e20fd4cf397`, endpoint
  `https://7219a605e3c2144a30987e20fd4cf397.r2.cloudflarestorage.com`, buckets
  `kokonut-production` and `kokonut-backups`. No credentials were supplied;
  provision them through SOPS or at production deployment. Test-prefix,
  least-privilege, and lifecycle acceptance remain open.
- **Production/recovery:** target hostname `hub.kokonut.network`; 24-hour
  recovery target; replica/failover work is deferred to production. Cutover is
  approved once all readiness gates pass. Public ingress, TLS, trusted proxy
  hops, and production RPO details remain to be established.
- **Retention:** the owner requested industry-standard periods and legal holds,
  and identified the United States and Dominican Republic. There is no single
  duration to apply across these record types: Dominican Republic Law 172-13
  governs personal-data protection, and FTC guidance recommends keeping
  personal information only as long as needed; record-specific duties still
  need a reviewed schedule. Keep no-prune behavior until purpose-specific
  periods, archive access, legal-hold ownership, and erasure approval are
  defined ([Dominican Republic Law 172-13](https://www.consultoria.gov.do/Consulta/Home/FileManagement?documentId=3371232&managementType=1),
  [FTC data-retention guidance](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business),
  [NIST SP 800-92 log-management guide](https://csrc.nist.gov/pubs/sp/800/92/final)).

### Self-hosted OIDC options

Kokonut's own Gateway session, tenant-scope, and authorization layer remains
self-hosted. OIDC is the protocol used to verify an operator's initial identity;
the OIDC provider can also be self-hosted. Choosing an IdP does not make
Directus mandatory or move Kokonut's org/location authorization into that IdP.

| Option | Fit | Trade-off |
|---|---|---|
| **ZITADEL (selected)** | Self-hosted OIDC, PostgreSQL-backed, supports Caddy as a reverse proxy, and Redis is optional. Treat its identity database and credentials as a separately backed-up security boundary; shared PostgreSQL is only acceptable with a dedicated database/role and verified privileges. | Adds a separately operated identity service and its own data/backup lifecycle. The current Compose guide lists 2 GB RAM as a prerequisite; the process alone is described at about 512 MB, so do not use the process figure as whole-stack or Raspberry Pi sizing. ([Compose guide](https://zitadel.com/docs/self-hosting/deploy/compose), [production guide](https://zitadel.com/docs/self-hosting/manage/production)) |
| **Authentik** | Self-hosted OIDC provider with authorization-code and PKCE support and an administrator-facing workflow UI. ([OIDC provider docs](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)) | Good option when its identity workflows and admin interface are desired; deployment/service footprint should be checked against the lightweight profile before adoption. |
| **Keycloak** | Mature self-hosted identity and access-management server; official container and production docs cover PostgreSQL and production operation. ([container docs](https://www.keycloak.org/server/containers), [supported configurations](https://www.keycloak.org/server/supported-configurations)) | Broad capabilities and ecosystem, with a larger operational surface than the Kernel itself needs for its current OIDC client contract. |
| **Kokonut-managed credentials** | Keep account credentials and login entirely in Kokonut's own service. | Maximum control, but Kokonut would own password storage, MFA/passkeys, recovery, abuse defense, security patching, and identity lifecycle. Implementing an OIDC server from scratch is not recommended. |

The owner selected **self-hosted ZITADEL** on 15 October. Keep it as an
optional, replaceable identity profile behind Caddy, while retaining Kokonut's
current session/scope/tenant layer. The identity hostname, issuer/client
details, test accounts, and secret provisioning remain open; no IdP has been
installed or configured. See the [ZITADEL provider plan](zitadel-provider.md).

### What the originally proposed 30 candidate seeds would write

The originally proposed action was a **data write to the local migration-400 candidate
database**, not a schema migration and not a production action. It would add
metric definitions and governance frameworks, dashboard/report datasets,
business capability and roadmap catalogs, plus Adelphi pilot stakeholder,
governance, coordination, funding, and reserve records. Some are explicitly
examples or pilot claims (including stakeholder proxy parties and 2021–2024
funding/participation rows), so these would appear as candidate data for owner
review. They are not measurements imported from Genesis, Seeds, Adelphi, or V1.

The earlier proposal was limited to the exact 30 curated seed files through
the ordered runner, with checksum/ledger tracking. It skipped already-applied
`seed:140_mobile_forms.sql`, excludes `seed:064-068_impact_network.sql` because
it contains pilot upserts and a location-owner update, and leaves the other 90
pending sources alone. A source review found that several “pilot/example” seeds
write records that can be mistaken for real evidence: `105` creates a consent
row described as `operator-approved` with `legal_basis='consent'` via
`system_migration`; `109` and `110` create Adelphi governance circles/roles with
`active` status; `114` marks 2021–2024 funding rounds closed and participations
executed, including a “Genesis farm launch capital” round attached to Adelphi;
and `115` creates active reserves, including a 20,000-tonne carbon buffer and
balances derived from those funding rows. These are not established by the
owner's message and must not be treated as real consent, governance, funding,
or farm data. The owner selected reference catalogs only and held pilot rows. The new
`scripts/seed.sh --catalog-only` path selects five files: expense categories,
metric definitions and governance metadata, flow metrics, and carbon reference
factors/benchmarks/protocols. Dashboard records marked published/verified,
business assumptions, mixed framework/organization seeds, and pilot records
remain outside this selection; see the exact [scope and held-file
rationale](reference-seed-scope.md). The earlier preflight restore checkpoint
predated migrations 392–400. On 15 October, a fresh checkpoint of the current
migration-400 candidate was restore-rehearsed in an isolated `template0`
database, then used as the rollback reference for the separately approved five-file write. Archive and parity details are in [the preflight](builds/2026-10-15-recovery/candidate-reference-seed-checkpoint-preflight.json); applied checksums and resulting counts are in [the rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json). Other curated and pilot seeds remain held.

| Batch | Selected checklist items | Code work to complete first | Owner or external gate held open |
|---|---|---|---|
| API and transport parity | 1, 3, 12, 14 | Finish REST/gRPC method and error parity, authenticated CORS, SDK contract coverage, and synthetic auth/scope checks. The enabled gRPC loopback slice now registers both generated services and exercises key/scope decisions; the Directus fixture preflight now blocks without writes when its required identity field is absent. | Real OIDC, trusted HTTPS certificate, Directus runtime identity/schema and effective permissions, tenant-specific parity, and release authorization. |
| Tenant and database boundaries | 9, 12 | Extend transaction-bound tenant context across remaining Gateway routes and worker jobs; audit direct SQL and direct-database role access; add synthetic owner/share and denial checks. Migrations 405–414 integrate the sensor-anomaly handler with its dedicated DSN/credential, signed tenant context, bounded operations, and one caller-owned transaction. Forty-five focused anomaly/EventBus tests and eight end-to-end disposable PostgreSQL checks pass, including child crash after commit and attempt-two retry without duplicate effects ([delivery evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json]). Existing context, role-isolation, owner-transfer/revocation/expiry, signature/replay-denial, and transaction-lock checks also pass ([acceptance](builds/2026-10-16-recovery/worker-tenant-context-disposable.json)). Remaining code work covers control-plane separation and other worker/Gateway scopes; a real worker login, credential, and active location grant still need deployment provisioning before activation or RLS. |
| Recovery and delivery | 1, 4, 6 | Continue provider-off/failure, lease reclaim, retry/idempotency, duplicate prevention, process outage, and rollback checks with fake endpoints or disposable databases. | Production provider state, external delivery destination, schedule/operator inventory, alert/on-call owner, and a 24-hour run window. |
| Reports and dashboards | 1, 5, 6, 10 | Port all repository-verified Kokonut surfaces, finish query safety and synthetic parity, and document migration boundaries. Do not infer saved-query ownership from the archived Metabase database or represent generic sample-H2 e-commerce cards as Kokonut product reports. | The owner supplied the common cross-lifecycle review audience: liquidity providers, DAO members, guild members, and the wider community. This does not grant blanket report access. Per-report visibility/scope, populated semantic fixtures, external/operator-edited consumers, and DB roles follow farm-data ingestion. |
| Field Collector | 11, 13 | Expand isolated browser/API checks for retired forms, consent, queue behavior, and cleanup; no-network OIDC checks now cover login/session/logout, invalid claims before DB access, discovery metadata URL, requested scopes, and configured S256 PKCE. | Configure selected ZITADEL after the owner supplies the identity hostname and the secrets are provisioned; trusted HTTPS browser origin and human disposition/retention decisions remain open. |
| Deployment and cutover | 1, 7, 15, 16 | Keep ARM64 code assessment and local profile/route checks current; complete non-disruptive restart/recovery checks. | 24-hour recovery target and conditional cutover approval are supplied. Schedule/resource budget, public ingress/TLS/trusted proxies, physical power/device behavior, production replicas/failover, and production schedule owners remain open or deferred. |
| Curated seed write | 8 | **Complete:** the five owner-approved catalog migrations applied successfully through the explicit candidate Compose target; ledger checksums and resulting counts are recorded ([rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json)). | The owner approved and completed this local reference write. Remaining pilot/curated seed files stay held; production import is not authorized by this operation. |
| Retention policy | 2 | Keep no-prune as the default; runtime policy, audited holds, optional jurisdiction/purpose codes, synthetic PostgreSQL acceptance, and candidate migrations 401–402 are complete. Unresolved scoped policies fail closed. | USA and Dominican Republic were supplied. Periods are deliberately runtime-configured, not hardcoded; deployment still needs approved policy data, accountable approval/hold roles, archive access, a scope resolver, and erasure procedures. |

## Work order

### Batch A — Close the current CI result

**Purpose:** establish the exact baseline for further local work.

**Repository surface:** `.github/workflows/ci.yml`, `scripts/run-github-ci.sh`,
and the focused test named in any failure log.

**Action:** At batch start, CI #336 was pending and Security #60 passed on
  pushed SHA `6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f`. The local disposable
  KGP check replays all 394 ordered PostgreSQL schema sources, processes seven
  guild/domain/task/governance events through the real indexer, verifies source
  links and idempotent replay, simulates a reorg and replacement-branch
  projection rebuild, then checks restart and lease reclaim against the real
  cursor table. Forty-eight focused migration/KGP/guild tests, Ruff,
  compilation, capability-matrix, and JSON evidence checks pass. A fresh
  encrypted checkpoint and isolated restore preceded candidate migration 403;
  the candidate is healthy with zero pending schemas, but its app image was not
  rebuilt and RLS remains disabled. No live RPC, seed, or provider is used.

**Acceptance:** require passing CI and Security on the current PR head before
merging. The scheduler runtime acceptance is source/disposable evidence only;
the report guard disposable database does not establish populated output
parity or least-privilege role behavior outside that integration.

### Batch B — Finish software tenant boundaries before considering RLS

**Purpose:** make every supported caller establish verified tenant context
before protected reads and writes, and make direct database access fail closed.

**Likely code surface:**

- `services/gateway/` authentication, route dependencies, and tenant context;
- `services/scheduler/`, event workers, and job handlers that access tenant
  data directly;
- `services/analytics/mobile_offline.py` and other legacy CLI entry points;
- `services/mobile/` and Gateway API-key/mobile credential paths;
- `services/migration/`, `scripts/check-*disposable.py`, and the runtime-role
  bootstrap for privilege boundaries;
- `tests/test_gateway_auth.py`, `tests/test_mobile_api.py`, tenant-context,
  worker, CLI, and migration tests.

**Code tasks:**

1. **Complete for tenant-bound mobile-device writes and the Data Stream
   create route:** migration 396 verifies
   API-key and capability-token activity, expiry/revocation, exact
   resource/action/location scope, and current location ownership before
   signing context for that transaction. Scope denial clears prior context;
   credential and owner rows stay locked until transaction end. API keys with
   wildcard or location-free scopes fail closed. The runtime role can read only
   reviewed authentication columns and cannot manage API keys. Focused Gateway,
   mobile, tenant-context, and role tests plus isolated forced-RLS acceptance
   pass. The Data Stream route now uses the same DB-verified transaction
   context before its draft INSERT, and uses the database-derived actor UUID.
   Its isolated forced-RLS probe verifies matching owner/location/actor writes
   and cross-location denial. This source-only slice does not cover other
   Gateway routes, shared organization affiliation for API keys, candidate
   credential provisioning, or application RLS.
2. Trace each worker and legacy CLI query to its service identity and tenant
   context. **Partial:** `services.analytics.mobile_offline` helpers and CLI
   commands now fail before database access because there is no authenticated
   tenant identity, and no repository runtime caller depends on them. Equivalent
   capture/sync uses the consent-aware Gateway. Continue the same trace across
   workers and other CLIs; give workers only required database functions and
   columns, and reject unscoped paths before mutation. Allowlisted cache event
   handlers now require a valid location UUID before invalidating entries,
   preventing malformed events from triggering a global cache flush. The
   [worker operation map](worker-operation-map.md) inventories all 22 scheduled
   modules and seven event-handler pairs, with a test guarding allowlist parity.
   It records source-visible effects and known replay boundaries; transitive
   service/provider calls and existing persisted schedule reconciliation remain
    open. The source-only effect index now records 36 unique direct effect sites
   (40 operation/site memberships) across 26 worker roots. The scheduled carbon
  adjustment check has its own read-only entrypoint; the interactive
  credit-management CLI is excluded from scheduler allowlisting. The function
  graph now follows the shared `services.common.cli.run(main)` callback. A separate comparison
  covers the current 17 shared JobSpecs: the inventory has five no-input defaults
  and twelve validated-input jobs, while EAS/RPC require explicit supported
  chains. The earlier eight-no-input comparison recorded that anomaly,
  climate, weather, weather forecast, metrics, credit adjustment, and remote sensing require a
  schema-validated location per scheduled task; scheduled sensor ingestion now requires one location-bound registered driver
  instance; no active source instance or schedule has been configured.
  The manual sensor CLI now requires a canonical `--location-id` for reads and
  writes and binds sensor lookup, inventory, and calibration SQL to that
  location. One hundred ten focused sensor/scheduler checks pass. This is a
  query filter only; it does not authenticate the caller or establish signed
  context/RLS ([evidence](builds/2026-10-16-recovery/sensor-ingestion-cli-location-scope.json)).
  The adjacent device-manager CLI now also scopes listing, health lookup,
  registration, and health updates; its registration upsert cannot move an
  existing slug across locations. Sixty-one focused device/IoT tests pass;
  these UUID filters also do not grant caller identity or database isolation
  ([evidence](builds/2026-10-16-recovery/device-manager-location-scope.json)).
  The optional Prefect adapters preserve multi-location behavior by dispatching
  one task per active Kokonut Network location. Remote sensing is available only as a
  bounded sequential batch (1–10 jobs, default one) and now requires the
  location for manual and scheduled calls, and ClickHouse projection
  is limited to a bounded run-once contract. No task or provider was activated.
  Neither report inspects persisted tasks or
   provider state, and neither proves runtime identity or tenant context. New
   module-specific operation schemas validate values and option
   combinations at activation, run-now, generated job plans, and subprocess
   dispatch; they reject human-review actions, unsafe cleanup, unbounded event
   loops and recurring sensor ingestion without a source. Scheduler and event
  operations still inherit the shared runtime identity. The exact NOI worker
  module now receives its named worker key only, with shared PostgreSQL login
  settings stripped from that child; this does not establish RLS for other
  jobs. The broader code trace is recorded in
   [the tenant call-site audit](mobile-tenant-rls-callsite-audit.md). A new
   location-scoped OIDC operations overview supplies device inventory and
   aggregate queue counts only when both `mobile_device:read` and
   `mobile_collection_review:read` apply. Its query sets signed tenant context
   and repeats both grant checks; focused service, route, and console checks
   pass. The console ignores responses from older inventory requests after a
   location switch; live OIDC/database and browser race acceptance remain open.
   The report-review queue/detail services now also have five direct source
   regressions for same-connection context-before-query, repeated location
   grants, legacy-context denial, rollback/close, and the detail-size bound.
   Synthetic connections do not verify the PostgreSQL signing functions or
   final database role ([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)).
3. Complete runtime-role restrictions for remaining public tables and verify
   existing handlers still work through their narrow grants/functions.
   **Partial:** the opt-in bootstrap still grants broad DML on existing public
  tables outside reviewed exceptions, but it now revokes both global and
   `public`-schema default privileges for future tables and sequences. The
  disposable PostgreSQL 16 role acceptance still passed current-handler SQL
  and proved a table/sequence created after provisioning is inaccessible to
  the runtime login. A new whole-services SQL inventory covers all 818 Python
   source files and identifies direct execution sites and candidate relation
  names without becoming an ACL. The current generated inventory covers 3,916
  SQL execution sites across 818 source files, including 307 worker-linked
   sites; literal query wrappers are unwrapped while parameter values remain
   unobserved. The report is static
   evidence, not an ACL. The next review classifies API, worker, CLI, and
   indirect-query surfaces before deriving explicit grants; worker, Directus,
   and RLS boundaries remain open ([role evidence](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json); [SQL inventory](runtime-sql-inventory.json); [latest inventory check](builds/2026-10-15-recovery/runtime-sql-inventory-refresh.json)).
4. Add a machine-readable preflight that detects unbounded callers, unsafe
   grants, missing migration prerequisites, and pending tenant mappings without
  printing personal or secret values. **Partial:** the static-only worker
  preflight confirms all 25 allowlisted roots and imports, reports the shared
  runtime identity and 72 SQL sites without static function matches,
  and keeps RLS blocked. The complementary aggregate tenant preflight now
  reports pending/current-source checksum drift counts, connected-role
  superuser/BYPASSRLS and public DML/RLS indicators, and enabled scheduler
  contract and known-unbounded-scope counts without returning identifiers, task
  names, or arguments. Four focused source tests plus six existing tenant
  preflight tests pass (10 total). A separate disposable PostgreSQL 16 run
  exercised the actual catalog queries with synthetic rows on a no-egress,
  internal-only Docker network: 388 schema sources, two matched ledger rows,
  one checksum drift, one removed source, a pending migration count, an
  RLS-disabled DML table, an owned table without FORCE RLS, and valid/rejected
  scheduled commands. Output-leak assertions passed and the database/network
  were removed. Neither candidate nor legacy data was touched and no migration
  was applied. The output also encodes that a dedicated read-only preflight role
  is required before the CLI runs after RLS. These reports do not prove worker
  isolation. The CLI now requires the dedicated `kokonut_tenant_preflight`
  login through `KOKONUT_TENANT_PREFLIGHT_DSN`, checks it is direct/read-only
  with no public DML/ownership or object creation, and inspects the configured
  application role separately. The CLI also requires `BYPASSRLS` to be enabled
  exactly when an inventory relation has RLS, preventing filtered global
  counts. The connection path has source tests only; no credentials or database
  role were provisioned. Owner mapping, remaining
  runtime role restriction, active-schedule reconciliation, and complete worker context remain open
  ([static report](worker-boundary-preflight.json); [source evidence](builds/2026-10-14-recovery/tenant-database-readiness-check.json); [PostgreSQL evidence](builds/2026-10-14-recovery/tenant-database-readiness-postgres.json); [test evidence](builds/2026-10-14-recovery/worker-boundary-preflight-check.json)).
5. Keep application RLS disabled until all code paths and data ownership inputs
   pass. Isolated forced-RLS fixtures can prove policy behavior; they do not
   authorize turning it on in the candidate or a populated deployment.

**Acceptance:** disposable PostgreSQL tests cover owner/shared scope, denial,
revocation, stale context, cleanup, least-privilege grants, worker/CLI behavior,
and migration replay. The candidate rollout of migrations 392–400 and the
populated pre-400 restore/runtime-role replay are complete; worker, remaining
runtime-role, Directus/view, ownership, and RLS gates remain open.
Non-demo location owners and legacy OIDC affiliations are human inputs under
OFU-01/02; use only the already-confirmed Kokonut Network demo mapping in
synthetic tests.

### Batch C — Close the API and client contract gaps

**Purpose:** demonstrate that native Gateway, optional transports, and SDKs
enforce the same authorization and payload contract.

**Likely code surface:** `services/gateway/router.py`, `services/gateway/app.py`,
`services/grpc/`, `proto/`, `sdk/python/`, `sdk/javascript/`, generated OpenAPI
artifacts, and their tests under `tests/` and each SDK package.

**Code tasks:** exercise public and protected route parity, method/action
policies, tenant scopes, response models, error envelopes, pagination, payload
limits, and bounded shutdown across REST and gRPC. Expand the existing fake
adapter parity checks to remaining supported methods, including streaming
authorization where applicable. Preserve gRPC as an optional transport and
make a disabled-provider response explicit.

**Acceptance:** offline SDK tests plus ASGI/disposable-database checks show the
same allow/deny decisions, schema, and error behavior across each supported
transport. Live identity-provider login and delivery of enrollment codes stay
under OFU-07 and OFU-10.

**Progress:** the five generated native v1 reads now have durable Python and
TypeScript fake-transport regression tests for method/path parity, encoded path
segments, API-key/accept headers, typed payloads, and normalized failure cases.
Those checks passed offline. A response-shape follow-up now requires array data
for list reads and object data for detail reads in both clients; malformed
shapes produce the same normalized envelope error. Two new focused regressions
per language pass, as does the complete 11-test JavaScript SDK suite and its
TypeScript build. Gateway route/auth and tenant-scope parity remain open; see
the [acceptance record](builds/2026-10-14-recovery/sdk-public-api-parity.json).
The gRPC adapter now also has focused tests for the disabled-provider boundary:
both server startup and health checks return the explicit disabled error before
loading optional gRPC dependencies. This does not establish enabled transport
parity or runtime acceptance ([evidence](builds/2026-10-14-recovery/grpc-disabled-provider-import-boundary.json)).
The two gRPC service protos now have a source inventory pinning 55 RPC methods
to their handlers and exact resource/action scopes. Every protected handler
checks scope before acquiring a DB connection; the one public content-hash
helper is confirmed DB-free. This source check does not establish API-key,
tenant, streaming, TLS, or native Gateway parity
([evidence](builds/2026-10-14-recovery/grpc-rpc-policy-inventory.json)).
The interceptor also had a streaming context leak: `ContextVar` identity stayed
set in the caller after a response yielded. The wrapper now scopes identity to
generator creation/advancement and cleanup, resets before returning control to
gRPC, and closes canceled iterators under the authenticated context. The five
new lifecycle regressions and existing gRPC tests pass (33 total)
([evidence](builds/2026-10-14-recovery/grpc-auth-context-lifecycle.json)).
The native and Field Collector routers now also have a pinned full method/path
policy inventory. A 27-test focused Gateway run confirms exact resource/action/
public policy coverage, 401 for every registered private route when anonymous,
and 401 for unknown routes, wrong methods, and near-miss paths ([route inventory evidence](builds/2026-10-14-recovery/gateway-route-policy-inventory.json)).
The OIDC operator router now has a separate exact inventory for all 48 concrete registered
method/path entries, including scoped grants, secondary grants, public login
endpoints, and six governed farm-activity actions. Unknown operator paths and
method mismatches return 401 in the source test ([current route inventory](builds/2026-10-18-recovery/gateway-credit-custody-summary.json); [original inventory](builds/2026-10-14-recovery/operator-route-policy-inventory.json)). The new location-scoped Field Collector overview requires both device-read and collection-review grants and returns no tokens or payloads; focused route, query, and console checks pass.
The operator console's cookie-authenticated draft edit now passes both its
credentialed CORS preflight and successful-response checks; PATCH was added to
the explicit CORS method allowlist. Browser/runtime ingress acceptance remains
open ([CORS evidence](builds/2026-10-14-recovery/gateway-cors-patch-preflight.json)).
The Directus parity fixture also checks its historical identity-scope column
before creating synthetic users or activity rows. A missing
`directus_users.location_id` returns a blocked precondition with no fixture
writes (three source checks and one fake-schema execution pass, with Ruff and
Python compilation). The owner has since selected organization/location
grants; the next code step must bind Directus identities to Kokonut operator
identities and enforce those grants. Runtime read/write, field, hook, and
schedule parity remain open ([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)). The create-time tenant-reference hook now rejects explicitly malformed `location_id` values instead of silently skipping its reference checks; the extension TypeScript build passes. This is input validation only and does not authorize a caller's tenant scope ([source](../../extensions/kokonut-hooks/src/tenant-validation.ts); [parity inventory](directus-parity-inventory.md)).
The enabled gRPC loopback acceptance also found and corrected service methods
that constructed service request/response messages from `types_pb2` instead of
`service_pb2`. All handler protobuf references now resolve against their
generated modules; a real ephemeral loopback call verifies API-key rejection,
scope denial before service DB acquisition, a correctly scoped response, and
the unauthenticated health exemption. This does not close TLS, real database,
tenant, or cross-transport parity ([evidence](builds/2026-10-14-recovery/grpc-enabled-loopback-transport.json)).

### Batch D — Complete code-verifiable capability slices and reporting

**Purpose:** move the 56 baseline rows through small, evidence-backed slices
without treating retained source code as migrated capability.

**Likely code surface:** domain modules named in
[capability-matrix.md](capability-matrix.md), `services/analytics/`,
`services/export/`, `services/data_stream/`, `services/credit_class/`,
`services/governance/`, `services/ingestion/`, `services/core/`, the native
Gateway, and scoped fixtures in `tests/`/`scripts/fixtures/`.

Work by domain family and keep each change narrow:

1. Core farm, agriculture, ecology, and process workflows (CAP-002–017).
2. Governance, finance, strategy, organization, and agent safety
   (CAP-018–038).
3. Ingestion, dMRV, Web3, reserves, markets, geospatial and interoperability
   (CAP-040–063).
4. Reporting, business model, State of Kokonut, and gRPC integration
   (CAP-064–066, plus CAP-001/007/031/039 where shared reporting is involved).

For each slice, identify the canonical data contract, optional provider
boundary, lifecycle/human-review boundary, minimum-dependency execution path,
and source tests before changing code. Add synthetic fixtures for behavior
that can be decided from the repository. Use the owner-supplied stakeholder
review audience (liquidity providers, DAO members, guild members, and wider
community), but do not infer per-report visibility, owner scopes, measures,
or production semantics; those require report-owner review and reference data
in OFU-04/14. Directus source and permission
contracts can be improved locally, but supported-version runtime-role parity
needs the disposable identity/schema fixture in OFU-09.

**Progress (15 October 2026):** the report snapshot CLI now requires explicit
location scope for bulk generation, rejects conflicting selectors before
opening PostgreSQL, and accepts standalone hash verification. All 94 report
generator keys remain available. Eleven focused checks and Ruff pass without
database or provider access ([evidence](builds/2026-10-15-recovery/report-generator-cli-scope.json)). All single and bulk calculations use a session-level PostgreSQL read-only default, and draft persistence starts after calculation. A disposable PostgreSQL probe found that switching to autocommit after changing the default could permit a write. The connection facade now denies autocommit changes directly and through `cursor.connection`; direct DML still receives SQLSTATE `25006`, and the draft write succeeds after calculation. Nine focused tests, Ruff, compilation, and the disposable check pass. The application connection remains a writer, so this is a guard rather than a database-role boundary. Populated output parity remains open ([calculation evidence](builds/2026-10-15-recovery/report-generator-read-only-calculation.json); [disposable evidence](builds/2026-10-15-recovery/report-generator-readonly-disposable.json)).

The AST-only helper-scope inventory now follows statically imported and
same-module local functions for all 94 registered reports. It finds helper
query sites in 34 report types, with 167 report-to-helper query-site
memberships and 63 visible location-scope signals. The trace corrected several
invalid relative analytics imports in the report modules; its source coverage
does not prove runtime behavior, tenant isolation, authorization, or output
parity ([inventory](report-generator-helper-scope-inventory.json)).

**Acceptance:** the slice's source tests pass and its contract/evidence path is
documented. The matrix remains `B`, `D`, or `P` until its named MAN-CAP
acceptance is completed with representative scoped data and retained output.

### Batch E — Native scheduler, providers, and recovery code

**Purpose:** finish the code-level replaceability and resilience checks before
production configuration is supplied.

**Likely code surface:** `services/core/jobs.py`, `services/scheduler/`,
`services/flows/`, `services/events/`, `services/analytics/backend.py`,
provider adapters under `services/core/`, `services/storage/`, Compose
profiles, and `scripts/fixtures/`.

**Code tasks:** complete synthetic parity for scheduler planning/dispatch,
leases, idempotency, retries and dead-letter operations; prove one-dispatcher
and duplicate prevention; exercise provider absent/disabled/failure paths;
cover backup/media restore and outbox behavior with fake endpoints and
disposable databases. Improve the report/query safety boundary for
repository-owned surfaces. The legacy saved-query runner remains disabled by
default; when explicitly enabled, a dedicated identity may read only the three
curated reporting views in a read-only transaction, while the application
identity updates refresh metadata. External/operator-edited queries, retained
dashboard selection, and tenant-scoped report parity remain open.

**Progress (14 October 2026):** the saved-query runner is isolated from the
application database connection, checks its live role attributes and ACLs,
uses statement/lock timeouts, counts results without fetching them, and refuses
to write stale refresh metadata if the saved SQL changed during execution. The
disposable PostgreSQL proof and focused checks are retained in
[`saved-reporting-reader-disposable.json`](builds/2026-10-14-recovery/saved-reporting-reader-disposable.json).

**Supervisor tests (14 October 2026):** four focused tests cover graceful
shutdown, signal escalation, unexpected clean child exit, and cleanup after a
partial launch. One POSIX integration case verifies SIGTERM reaches a child
and grandchild; database outage and lease recovery remain open
([evidence](builds/2026-10-14-recovery/kernel-supervisor-unit-contract.json)).

**Projection failure injection (14 October 2026):** ten unit tests cover the
ClickHouse outbox's disabled-provider, client-setup, partial-batch, completion,
fencing, and cleanup behavior. They mock both database and provider boundaries;
real lease recovery and process-level outage behavior remain open
([evidence](builds/2026-10-14-recovery/clickhouse-outbox-failure-injection.json)).

**Outbox retry backoff (16 October 2026):** failed delivery outcomes now use a
60-second exponential base, doubling by persisted attempt number and capping at
one hour. ClickHouse setup failures use the same schedule; the existing
eight-attempt dead-letter bound, lease fence, and idempotent insert token are
unchanged. Fifty-seven focused outbox, failure-injection, and producer tests
pass. The checks use mocks and source contracts only; no database or ClickHouse
service was contacted ([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json)).

**Private-media key confinement (17 October 2026):** the S3-compatible
Field Collector adapter now validates the private object prefix for upload,
head, and delete operations, including rejecting traversal and empty path
segments before provider access. The storage/reconcile/cleanup suite passes 49
tests with Ruff and compilation clean. No R2 credentials, objects, or live
provider calls were used. This hardens the code path but does not close live
R2 inventory/deletion or retention acceptance.

**Scheduler crash-after-effect recovery (16 October 2026):** the disposable
PostgreSQL acceptance now kills the real SchedulerEngine after an allowlisted
event-processing child commits a notification outbox effect but before task
completion is recorded. Attempt two observes the completed durable event and
keeps a single outbox row and one successful handler delivery. This also found
and fixed the handler-runner stdout protocol bug caused by INFO logs emitted
after a committed effect. Five focused tests, Ruff, compilation, and the
disposable PostgreSQL run pass; no provider delivery or candidate/legacy access
occurred ([runner](../../scripts/check-scheduler-engine-reconnect-disposable.py);
[evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json);
[protocol regression](../../tests/test_event_handler_runner.py)). Broader
provider, worker-process, and long-duration recovery remain open.

**Provider-aware recovery (14 October 2026):** encrypted Compose checkpoints now
declare their PostgreSQL and ClickHouse contents. PostgreSQL-only backup and
restore no longer require ClickHouse credentials or a running ClickHouse
service. When ClickHouse is selected, backup preflights it before creating
artifacts, and restore validates the manifest and required services before
restoring PostgreSQL; rollback runs the same read-only restore preflight before
stopping app services. Fake-Compose acceptance covers provider-off backup,
restore/preflight, enabled backup/restore, and missing-service fail-fast
([evidence](builds/2026-10-14-recovery/provider-aware-backup-restore.json)).

**Migration replay (14 October 2026):** ordered migrations 392–397 and the
runner's no-op replay passed on a restored, age-encrypted candidate checkpoint
using PostgreSQL 16.4. The same 388 current schema sources also passed from an
empty PostgreSQL database in a separate internal-only Compose project. The
candidate then received migrations 392–397 through the ordered schema-only
runner after a fresh encrypted checkpoint and restore rehearsal. The app alone
was recreated; candidate health and anonymous route protection passed, and the
temporary restore project was removed. RLS stayed disabled and no seed SQL ran
([restore replay](builds/2026-10-14-recovery/candidate-migration-392-397-restored-replay.json); [clean bootstrap](builds/2026-10-14-recovery/clean-bootstrap-388-migrations.json); [candidate rollout](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json)).

**Dynamic retention source implementation (15 October 2026):** migration 401
adds nullable runtime policy windows, draft/approval state, and an audited,
append-only record-level legal-hold ledger. Event cleanup no longer accepts a
caller-selected `--days`; it requires exactly one approved active global
`event_bus` / `platform_event` policy, checks pending dead letters, unsuccessful
handler deliveries, and active holds, and remains default-off behind its feature
gate. Generic data-governance cleanup also requires its independent feature gate,
approved policy metadata, and no active hold. No periods or schedules have been
configured, and no fixed duration is proposed. The candidate has now applied migrations 401 and 402 after a fresh checkpoint
and restore rehearsal of its post-seed state. Disposable migration/hold
acceptance also passed on an isolated synthetic PostgreSQL fixture through the
ordered migration runner. It verifies the legacy-policy transition,
policy history, holds and event cleanup protections. The focused source/unit set also
passes 94 tests plus four subtests. Acceptance caught an undersized history
action column and the migration was corrected. No policy was configured and
cleanup remains disabled; deployment still needs approved policy data and
accountable operating roles ([database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json); [source evidence](builds/2026-10-15-recovery/retention-policy-source-checks.json); [migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql); [operations](retention-policy-operations.md)).

**Dynamic retention scope metadata (15 October 2026):** migration 402 adds
nullable owner-defined jurisdiction and purpose codes without defaults or
hardcoded legal meaning. The CLI and audited policy snapshots preserve these
codes. Auto-enforcement is rejected for unresolved codes, the generic sweeper
skips scoped policies, and EventBus cleanup rejects ambiguous active policy
state. Sixty-two focused source tests and four subtests pass; migrations 401
and 402 pass against an isolated synthetic PostgreSQL fixture. The candidate now includes these schema changes; no retention values or
policies were configured ([migration](../../schemas/postgres/402_retention_policy_scope_codes.sql);
[scope evidence](builds/2026-10-15-recovery/retention-policy-scope-source-checks.json);
[database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json)).

**Location-scoped scheduled forecast — 16 October 2026:** the shared job
catalog now exposes the repository's five-day weather-forecast ingestion as a
separate optional JobSpec. Its command contract requires exactly one location
UUID and rejects aggregate mode; generated plans remain disabled and
non-overlapping. Forecast inserts use the existing natural-key upsert, audit
record, and same-transaction ClickHouse outbox boundary. The current worker map
and source/function/SQL/effect inventories now include this root. The focused
scheduler and worker-inventory suites pass 154 checks; forecast rollback,
explicit-scope, and outbox regressions pass 43 checks, with Ruff clean. All
provider/database boundaries are mocked; no schedule, API key, database, or
provider was activated. The location selector is not tenant authorization;
signed worker context, per-location grant, credentials, cadence, and live
provider parity remain open ([evidence](builds/2026-10-16-recovery/weather-forecast-scheduled-job-contract.json);
[source contract](worker-job-contract-inventory.json); [schedule inventory](schedule-ownership-inventory.md)).

**Signed weather-forecast worker — 16 October 2026:** the native scheduled
module now routes through `services.ingestion.weather_forecast_worker` with an
exact `weather_forecast` secret mapping and a default-off feature flag. The
scheduler child receives only that DSN/credential pair; shared PostgreSQL
settings are stripped. Migration 426 adds signed location lookup and bounded
atomic forecast/audit/ClickHouse-outbox persistence. It uses only required
column grants and a no-login function owner, and the disposable PostgreSQL 16
fixture proves the path with forced RLS on location, forecast, audit, and
outbox. The 127-test focused source/scheduler/map suite, Ruff, generated
inventories, and nine disposable migration checks pass. The feature remains
off and migration 426 is not candidate-deployed; real credentials/grants,
provider parity, active schedule state, and legacy task reconciliation remain
open. The legacy module stays allowlisted for persisted tasks and still uses
the shared runtime identity until owners reconcile them. No candidate or
legacy database, provider, schedule, or MAN-CAP acceptance was touched.
Evidence: [migration check](builds/2026-10-16-recovery/weather-forecast-worker-disposable.json),
[worker operation map](worker-operation-map.json), and
[updated static inventories](worker-boundary-preflight.json).

**Signed current-weather worker — 17 October 2026:** native scheduled current-weather ingestion now routes through `services.ingestion.weather_worker` with an exact `weather` worker identity, default-off feature flag, and environment filtering for its named DSN, credential, and OpenWeatherMap key. The legacy `services.ingestion.weather` module remains allowlisted only for existing persisted tasks pending schedule-owner reconciliation. Migration 427 provides signed `weather_observation/ingest` coordinate lookup and atomic bounded storage for the observation, sanitized ingestion audit, ClickHouse outbox intent, and provider-payload receipt. It rejects cross-location rows, conflicting outbox reuse, and missing context; forced-RLS disposable PostgreSQL verifies the no-direct-table-access boundary. The focused suite passes 178 tests and nine disposable PostgreSQL 16 checks; Ruff, compilation, and generated inventories pass. No candidate or legacy database, provider, real credential, or schedule was accessed. Migration 427 is not candidate-deployed, worker grants are not provisioned, and the feature stays off. Existing task rows, provider parity, and live recovery remain open ([worker](../../services/ingestion/weather_worker.py); [migration](../../schemas/postgres/427_signed_weather_observation_worker.sql); [runner](../../scripts/check-weather-observation-worker-disposable.py); [evidence](builds/2026-10-17-recovery/weather-observation-worker-disposable.json)).

**Acceptance:** deterministic isolated checks pass without external provider
credentials and preserve rollback evidence. Actual schedule inventory and
operators (OFU-16), alert destination/on-call owner (OFU-05), report retention
policy (OFU-03), R2 account/live objects (OFU-08), and production topology
(OFU-06) remain owner gates.

### Batch F — Code-only ARM64 and constrained-runtime assessment

**Purpose:** assess Raspberry Pi suitability from reproducible software
checks while clearly recording the physical limitation.

**Likely code surface:** `Dockerfile.kernel`, `docker-compose.yml`,
`docker-compose.*.yml`, `.github/workflows/ci.yml`,
`scripts/kernel-inventory.py`, `scripts/run-github-ci.sh`, migration/restore
scripts, and image/profile tests.

**Checks:** build the minimal and selected optional targets for ARM64 under
Buildx/QEMU; run container startup, migrations, health/readiness, backup and
restore in emulation; apply a 4 GB memory limit and representative CPU quotas
to software fixtures where practical; capture image/package inventories and
startup/resource measurements; test orderly restart and simulated process or
container loss. Keep PostgreSQL and optional stores private. Treat emulation
and cgroup limits as compatibility checks, not a hardware benchmark.

**Result (14 October 2026):** the minimal app and PostGIS images built and ran
as `linux/arm64`; all 386 schema migrations applied with zero failures; PostGIS
topology/raster functions were available; `/health` returned 200; a 4.9 MB
logical backup restored to a second database with matching SHA-256 migration
fingerprint and successful Kernel schema readiness; database restart and
simulated app-container loss recovered. Container limits were 1.5 GiB for
PostgreSQL and 1 GiB for the app, two CPUs each, with no host ports. The focused
Compose architecture contract passed. See the retained
[acceptance record](builds/2026-10-14-recovery/arm64-qemu-runtime-acceptance.json).

**Acceptance:** passed for the minimal app/PostGIS runtime under QEMU, with
emulator conditions, resource limits, migration and restore evidence recorded.
Actual Pi storage wear, thermals, power-loss behavior, physical network
reliability, and sustained device performance stay unverified until hardware is
available; no human input is needed for this code-only assessment.

**Prior schema-400 refresh (15 October 2026):** the isolated profile planner
built the app and PostGIS images as linux/arm64, applied all 391 schemas through
migration 400 with zero failures, restored a logical backup with matching
migration fingerprints and zero pending migrations, and passed HTTP health,
anonymous protected-write denial, database restart, and app SIGKILL recovery.
Spatial and manually enabled raster functions also passed. The database
restart caused the scheduler child to exit on a closed connection; the Kernel
supervisor restarted the app processes and health recovered. The scheduler
source now opens a fresh connection per tick; a separate loopback-only
disposable PostgreSQL stop/start check confirmed its worker process reconnects
after database recovery, with the task engine stubbed. Repeated/long provider
outage behavior, lease recovery, and physical Pi limits remain open. The earlier
restricted command shell could not access the Docker Desktop socket; host-
authorized access reached the healthy daemon and completed this check
([prior evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-400.json)).

**Schema-402 refresh (15 October 2026):** a fresh, uniquely named ARM64 project
applied all 393 schema files through migration 402, with zero failures or
pending migrations. A 5,220,702-byte custom-format dump restored into a second
template0 database with a matching 393-row SHA-256 migration fingerprint and
zero pending migrations. PostGIS geometry, `/health` 200, anonymous protected
write 401, health after database restart, and health after app SIGKILL followed
by Compose `up` passed. The app started before migration, so workers logged
missing-schema errors during bootstrap; this refresh did not apply explicit
resource limits or seeds. Raspberry Pi hardware, 24-hour recovery, and real
provider/lease outages remain open
([evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-402.json)).

**Schema-gated startup follow-up (15 October 2026):** the image default and
standard-role commands now pass `--require-schema`. In a new ARM64 QEMU project,
the app remained child-free while the ledger was empty; after 393 ordered
schemas applied and a zero-pending plan, API/scheduler/event children started,
health returned 200, a protected write returned 401, and Docker reported the
app healthy. The app was limited to 1 GiB/two CPUs and PostgreSQL to 1.5
GiB/two CPUs. The disposable project and volumes were removed. This closes the
worker-before-migration source/runtime path under emulation, not physical Pi,
24-hour, or provider-outage acceptance
([evidence](builds/2026-10-15-recovery/kernel-schema-startup-guard.json)).

### Batch G — Reconcile ledgers, then request only owner decisions

Update `batches.md`, `progress.md`, `capability-matrix.md`, the relevant
evidence records, and this plan after each batch. Keep raw checklist counts
separate from capability acceptance. Before production/candidate rollout,
present the owner only with unresolved inputs or separately gated writes.

## Owner-input gates after code work

These do not block the code-first batches above, but they block the associated
deployment or semantic acceptance:

- **Ownership and access:** the owner mapped Kokonut Genesis, Kokonut Seeds,
  Kokonut Adelphi, Kokonut Terra Viva, and Kokonut V1 to the Kokonut Network
  operating tenant (OFU-01). Adelphi and Genesis are confirmed exclusive;
  do not infer legal land title. Other locations stay unassigned. Operator-to-
  organization grants and legacy account reconciliation remain open (OFU-02).
- **Governance and reporting:** USA and Dominican Republic are the selected
  retention jurisdictions. Runtime-configurable policy support is implemented
  in source; no periods are hardcoded. Approved policy data, accountable
  approval/hold roles, and deployment verification remain open (OFU-03). The owner selected all repository-backed
  reports and provider jobs for code-first porting; populated reference
  outputs follow the planned farm-data ingestion (OFU-04/14). Directus should
  consume organization/location grants; supported consumers and runtime
  identity still need isolated parity evidence (OFU-09/15).
- **Production operations:** alert destination/on-call (OFU-05), public
  ingress, trusted proxy hops, TLS, and production recovery topology (OFU-06),
  active scheduler inventory/operators (OFU-16), and scheduling the
  owner-selected 24-hour recovery window (OFU-13). Replica/failover checks are
  deferred to production.
- **Provider setup:** identity hostname, issuer/client settings and test
  identities for the selected self-hosted ZITADEL provider (OFU-07); R2
  credentials and lifecycle policy (OFU-08); browser vault and trusted local
  HTTPS certificate when browser acceptance is scheduled (OFU-10/11).
- **Candidate-only writes:** the five selected reference catalogs (OFU-17) were
  applied to the local candidate after separate approval. The earlier 30-file
  proposal is superseded; pilot rows remain held. Migrations 392–434 are rolled
  out to the local candidate; 425 schema entries are applied through migration
  434, with zero pending or failed entries. No migration 435 or later is
  applied. Runtime credential provisioning remains tracked under OFU-19. The
  candidate has six recorded seed entries; 115 unselected seed sources remain
  pending.

There is no active Raspberry Pi request: OFU-12 records the completed code-only
scope and lack of hardware. If the owner later supplies a Pi, add a separate
physical acceptance record rather than revising emulation evidence.

## Push and release cadence

Keep related changes in local commits and push reviewable batches, as
requested. The latest pushed head is `6c53e0fe` on PR #68. Security #209 passed; CI
#485 is in progress. The Directus source fixture correction is included in this
head. Review hosted checks for the current head before release decisions.
Never push directly to `main`. Keep each candidate database rollout separately
gated even when its migration and disposable acceptance are complete.


**Current local security logging slice — 17 October 2026:** access-audit and capability-token database failure logs now retain only the exception class. Rollback, return fallbacks, and issue exception propagation are unchanged. The focused security audit/capability/interceptor/Gateway audit suites pass 38 tests with Ruff, compilation, and diff checks; failures use mocked connections only. Checklist: 504 complete / 19 open. The capability matrix remains unchanged ([evidence](builds/2026-10-17-recovery/security-audit-error-redaction.json)).

**Current local federation logging slice — 17 October 2026:** federation node, share/query, and sync database failures now log only the bounded exception class; sync also omits caller-provided error strings. Rollback, fallback values, and exception propagation remain unchanged. Thirteen new mocked regression cases pass alongside the existing federation tests (40 total) with Ruff, compilation, and diff checks; no database or provider was contacted. Checklist: 505 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/federation-error-redaction.json)).

**Current local EventBus logging slice — 17 October 2026:** EventBus batch failures, worker iteration failures, and bus-close failures now log only bounded exception classes. Rollback and re-raise behavior, fresh-bus reconnect, and durable retry semantics remain intact. Forty focused tests and three subtests pass with Ruff, compilation, and diff checks using mocks only. Checklist: 506 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/event-worker-error-redaction.json)).

**Current local scheduler logging slice — 17 October 2026:** scheduler tick and connection-close failures now log only bounded exception classes. Failed ticks still return `None`, close their connection without rollback, and reconnect on the next tick; close failures stay contained. Thirteen focused scheduler checks pass, and the combined security/federation/EventBus/scheduler suite passes 131 tests plus three subtests with Ruff, compilation, and diff checks. No database or provider was used. Checklist: 507 complete / 19 open; the 66-row matrix is unchanged ([evidence](builds/2026-10-17-recovery/scheduler-worker-error-redaction.json)).

**Current local stream logging slice — 17 October 2026:** stream ingestion, buffer, window, and alert paths now log only bounded exception classes. Per-row failures remain counted, transaction rollback and public fallback behavior are preserved, and alert publication remains best-effort. Fifteen focused mocked failure cases pass within a 42-test stream suite with Ruff, compilation, and diff checks. Checklist: 508 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/stream-error-redaction.json)).

**Current local cache logging slice — 17 October 2026:** computation-cache failures no longer log database messages, tracebacks, cache keys, or location identifiers. Cache write rollback/propagation and read, cleanup, invalidation, and statistics fallbacks remain unchanged. Five focused mocked failures pass within a 48-test cache suite with Ruff, compilation, and diff checks. Checklist: 509 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/cache-error-redaction.json)).

**Current local graph/RDF logging slice — 17 October 2026:** typed graph projection and RDF generation failures now log bounded exception classes without exception details, tracebacks, or RDF location IDs. Both flows still roll back and re-raise before generation activation. The graph projection/RDF/linked-data suite passes 157 checks with Ruff, compilation, and diff checks using mocks. Checklist: 510 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/graph-rdf-error-redaction.json)).

**Current local metric-event logging slice — 17 October 2026:** best-effort `metric_computed` publication now logs only a bounded exception class, without the location identifier or traceback. Event failure still does not interrupt the metric result path. The focused mocked test, Ruff, compilation, and diff checks pass. Checklist: 511 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/metric-event-error-redaction.json)).

**Current local raster-metadata logging slice — 17 October 2026:** raster metadata reads now log only bounded exception classes, with no private paths or tracebacks. Generic metadata read errors and file/dependency behavior remain unchanged. Two mocked failure regressions pass inside a 21-test raster suite with Ruff, compilation, and diff checks. Checklist: 512 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/raster-metadata-error-redaction.json)).

**Current local sandbox logging slice — 17 October 2026:** environment, run-history, resource-monitor, and isolation database failures now log bounded exception classes only. Creation rollback/re-raise, write fallbacks, and empty/None read results remain unchanged; persisted run diagnostics remain redacted. Eight mocked database-failure regressions pass within a 36-test sandbox suite with Ruff, compilation, and diff checks. Checklist: 513 complete / 19 open; the 66-row capability matrix is unchanged ([evidence](builds/2026-10-17-recovery/sandbox-database-error-redaction.json)).

**Current local ML logging slice — 17 October 2026:** Prophet fit/save/load and scheduled retraining failures now log bounded exception classes only, with no raw error text, model names, sensor identifiers, or local artifact paths. Existing fallback results, independent save attempts, artifact skipping, and descriptor cleanup remain intact. The 57-test ML/model-security/retraining/import suite passes with Ruff, compilation, diff checks, and regenerated worker-import closure validation. No provider or database was accessed. Checklist: 514 complete / 19 open; capability classifications are unchanged ([evidence](builds/2026-10-17-recovery/ml-anomaly-model-error-redaction.json)).

**Current local gRPC logging slice — 17 October 2026:** API-key database failures, request-interceptor exceptions, and optional service-import warnings now log bounded classes while retaining the generic authentication error, original gRPC exception propagation, and optional adapter behavior. The 32-test gRPC/auth/policy suite passes with Ruff and compilation on mocked boundaries. No database or RPC provider was contacted. Checklist: 515 complete / 19 open ([evidence](builds/2026-10-17-recovery/grpc-auth-request-error-redaction.json)).

**Current local metadata/trend logging slice — 17 October 2026:** batch anchoring omits private IRIs and exception details from warnings, while trend analysis omits metric names and raw errors. Anchor failures remain per-item failures and trend failures still return no score. Two mocked regressions pass with Ruff, compilation, and diff checks; no database/provider was accessed. Checklist: 516 complete / 19 open ([evidence](builds/2026-10-17-recovery/metadata-trend-error-redaction.json)).


**Current local mock-sensor logging slice — 17 October 2026:** demo sensor-reading insert failures now log a bounded exception class without sensor names, timestamps, or raw database details. Per-reading continuation and final database cleanup remain intact. The focused mocked regression passes; test lint, source import/syntax checks, compilation, and diff checks pass. Full-file Ruff still reports pre-existing unused imports/locals in this legacy demo module. No database/provider was used. Checklist: 517 complete / 19 open ([evidence](builds/2026-10-17-recovery/mock-sensor-error-redaction.json)).

### Current local continuation — 17 October 2026

Since the pushed-history checkpoint, local work has added bounded dynamic
retention-policy inventories, refreshed generated worker/runtime SQL counts,
and closed two offline SDK parity gaps: export request fields now match across
Python and JavaScript, and specialized list filters preserve required query
scope plus pagination/metadata options. The sandbox runner now rejects
non-string, malformed, and unregistered module names without echoing caller
input, while registered modules remain blocked until a restricted executor is
configured. Malformed migration-ledger output also produces a fixed
summary rather than echoing database-returned data. Gateway in-memory
rate-limit warnings also omit client IP-based limiter keys while retaining the
same denial, retry, and audit behavior; Gateway catch-all warnings omit
arbitrary caller paths while unknown routes still fail closed. The JavaScript
SDK now implements Python's existing raw export `createMany` operation, and
both SDKs preserve exact non-page-aligned offsets. Python and JavaScript
`CropCycle` types now reflect the canonical PostgreSQL schema, and the NOI
example uses its current yield fields. `HarvestEvent` types now include the
canonical evidence, verification, source-lineage, schema, and audit fields in
both clients. Focused tests, Ruff, TypeScript build, capability-matrix
validation, and diff checks pass; no provider/database was contacted and no
sandbox module executed in the latest slices. Sales and expense event SDK
types also now expose their canonical payment/evidence/allocation/approval
and lineage fields. Location, farm, and plot SDK types now also expose their
canonical spatial, metadata, and audit columns. The TypeScript
`SensorReading` now requires location scope and accepts canonical database
quality values. Python now also has matching sensor registry/device/alert
dataclasses. A reusable offline guard checks 473 base and additive column
names across 20 tables against both SDK model sets and runs in fast-fail CI. First-class
loss, labor, and field-note SDK records and location-scoped helpers now match
the operational tables. WalletProfile, AttestationRecord, and ReportSnapshot
now have current schema column coverage, including selected additive
migrations; `ExportLog` now includes its canonical table fields in both SDKs,
`NoiSnapshot` nullability matches the finance table, and the guard now rejects
Python/TypeScript fields that omit nullable SQL annotations. `AlertRule`'s
nullable maximum threshold is corrected. The guard now also checks 442
primitive SQL types across those 20 models; JSONB and PostGIS shapes remain
unvalidated. The guard passes across 20 models and 473 columns. The checklist
is now 545
complete / 19 open;
capability classifications remain unchanged. These commits remain local for
the next batch push.


### SDK list-query and CRUD parity continuation — 18 October 2026

The SDK parity batch is pushed to PR #68 through `6a598d84`. It preserves
generic Directus list-query options in TypeScript, tests Python/TypeScript
detail reads, single and bulk creates, updates, deletes, and response-envelope
handling, and exercises the pinned SDK's list-query transport with stubbed
fetch. Python aggregate requests match its collection route and top-level
array encoding. The Python SDK now maps common HTTP errors to stable exception
classes and safely handles malformed error envelopes. Focused validation passes
94 Python SDK/schema/method tests, 45 JavaScript tests, TypeScript build,
compilation, targeted Ruff, matrix validation, and diff checks. This is offline
API-shape evidence, not live Directus or authorization acceptance. The checklist
is 601 complete / 19 open; see
[list-query evidence](builds/2026-10-18-recovery/sdk-list-query-parameter-parity.json)
and [CRUD evidence](builds/2026-10-18-recovery/sdk-generic-crud-contract.json),
plus [aggregate-wire evidence](builds/2026-10-18-recovery/sdk-aggregate-query-wire-parity.json).

The Python SDK now handles malformed Directus error envelopes without
uncaught shape errors, preserves valid server messages, and maps 400/401/403/404
to documented exception classes. Ten focused regressions pass alongside the
94-test SDK/schema/method suite, Ruff, and compilation. This remains synthetic
error-response coverage, not live API or authorization acceptance
([evidence](builds/2026-10-18-recovery/sdk-python-error-envelope-parity.json)).

The TypeScript SDK now normalizes the pinned client's HTTP error envelope into
the same named classes as Python, including response status/context. A real
SDK 403 response through stubbed fetch and five mapped status cases pass; the
cross-language contract is documented in the JavaScript README. This remains
offline behavior and does not establish live authorization or tenant scope
([evidence](builds/2026-10-18-recovery/sdk-error-normalization-parity.json)).

The current-source ARM64/QEMU refresh applied all 425 ordered schema
migrations through 434, started the app only after schema readiness, and
verified healthy status, HTTP 200 on `/health`, and HTTP 401 on an anonymous
protected operator route under 1 GiB/1.5 GiB and two-CPU limits. The isolated
project was removed; this is emulation evidence, not physical Raspberry Pi,
power-loss, or 24-hour recovery acceptance
([evidence](builds/2026-10-18-recovery/arm64-qemu-current-schema-434.json)).


### Directus API fixture contract correction — 18 October 2026

The optional Directus API fixture now reflects the owner-selected Gateway-only
farm-activity boundary. Synthetic operators retain valid tenant grants, but
Directus must deny farm-activity reads and writes without changing rows; Field
Note reads still allow the granted location and hide the other location. Seven
focused source/fixture tests pass with Ruff and Python compilation. This does
not establish a fresh pinned-image run or broader collection/field/hook/schedule
parity ([evidence](builds/2026-10-18-recovery/directus-gateway-only-source-contract.json)).

### Financial projection idempotency follow-up — 18 October 2026

Source review found that migration 434 used `ON CONFLICT DO NOTHING` for a
stable financial outbox key. That prevented duplicate rows but silently
accepted a pre-existing key with different contents. Migration 435 adds an
after-insert verification trigger, using the bounded projection-owner role to
compare source identity, target table, columns, rows, and payload hash. Exact
replays remain idempotent; mismatched duplicates raise `23505` so the source
transaction rolls back. Network-disabled disposable PostgreSQL 16 acceptance
applies and replays migrations 434 and 435 under forced RLS and checks both
cases along with source transaction rollback and existing role boundaries.
The candidate remains at migration 434; migration 435 has not been rolled out
and needs its own fresh checkpoint and restore rehearsal. Financial edit/delete
semantics, historical backfill, and populated report parity remain open
([migration](../../schemas/postgres/435_financial_projection_conflict_guard.sql); [evidence](builds/2026-10-18-recovery/financial-events-outbox-disposable.json)).

### Field Collector successful-upload CORS contract — 18 October 2026

An in-process TestClient regression now drives the actual Field Collector media
upload handler through Gateway middleware and verifies a successful 201 keeps
the configured origin, credentialed CORS, and `Vary: Origin`. The device-token
resolver, PostgreSQL connections, and media store are synthetic/mocked. The
focused success and preflight checks pass with Ruff. This is source/runtime
contract evidence, not live device authentication, browser-through-proxy, or
public-ingress acceptance ([evidence](builds/2026-10-18-recovery/mobile-upload-success-cors.json)).

### Location-scoped finance SDK reads — 18 October 2026

The Python and TypeScript SDKs now share a generic read-only location accessor
for `financial_transaction` and `cash_flow_snapshot`, following the same
contract used for carbon-credit ledger collections. Explicit location scope
overrides a conflicting query filter; no create/update/delete, calculation, or
reconciliation operation is exposed. Ninety-six focused Python SDK/schema/
method tests, 46 JavaScript tests, TypeScript build, Ruff, compilation, schema
guard, and capability validation pass offline. CAP-031 remains at `D`; this
does not establish budgeting or portfolio workflow parity
([evidence](builds/2026-10-18-recovery/sdk-finance-read-methods.json)).

### Geostatistics stored-output SDK continuation — 18 October 2026

Expose persisted kriging, realization, spatial-autocorrelation,
cross-validation, and sensor-network-design outputs through typed read-only
Python and TypeScript SDK groups. Location-bearing run records use the shared
location-filter method. Point rows have no location column, so their convenience
reads require `prediction_id` or `realization_id`; caller filters cannot
override those parent selectors. Extend the canonical SQL parity guard to the
seven geostatistics tables, including PostGIS point output, JSON object arrays,
nullable values, and exact CHECK literals. Keep MAN-CAP-008 open: this slice
does not implement or validate geostatistical calculations.

Status: completed locally; offline evidence is recorded in [the batch result](builds/2026-10-18-recovery/sdk-geostat-stored-output-read-methods.json).


### Systems-thinking stored-record SDK continuation — 18 October 2026

Expose the 129 systems-thinking schema as typed read-only Python and TypeScript
SDK groups: shared causal-loop, stock-flow model, and time-delay catalogs;
loop-scoped causal links; and location-scoped variable and saved-result
records. Keep stakeholder `mental_model` out of the generic read surface because
its table has no location column. SQL parity includes CHECK values and JSONB
shapes. This establishes access to stored configuration and results only; the
original simulation, causal evaluation, archetype detection, and intervention
parity gates remain open.

Status: completed locally; offline evidence is recorded in [the batch result](builds/2026-10-18-recovery/sdk-systems-thinking-read-methods.json).


### OODA persisted advisory-record SDK continuation — 18 October 2026

Expose stored situation assessments and OODA cycle logs through location-
scoped typed read-only methods, and their signal/dimension evidence through
parent-assessment-scoped methods. Keep decision-policy review, approval,
decision generation, and action execution out of this SDK read slice. Extend
the canonical SQL parity guard across migrations 124 and 127, including all
nullable columns, JSON shapes, and CHECK-constrained values. MAN-CAP-010 stays
open until decision and action outputs match the named acceptance fixtures.

Status: completed locally; offline evidence is recorded in [the batch result](builds/2026-10-18-recovery/sdk-ooda-advisory-read-methods.json).


### CRISP stored-assessment SDK continuation — 18 October 2026

Expose persisted CRISP assessment summaries and their five dimension detail
records as typed read-only Python and TypeScript SDK groups. The master is
location-scoped; each dimension record carries both `location_id` and
`assessment_id`, so it can be listed by either selector. Preserve the schema's
numeric/nullability, JSONB, lifecycle/rating/confidence, and climate-scenario
contracts. Keep shared weight configuration, score calculation, review, and
publication outside this read-only slice. The named MAN-CAP-014 calculation
and output-parity gates remain open.

Status: completed locally; offline evidence is recorded in [the batch result](builds/2026-10-18-recovery/sdk-crisp-stored-assessment-reads.json).


### CAP-025 location-scoped identity review — 19 October 2026

Start with a bounded identity workflow under the owner-selected network-identity/location-review model. Support only farmer profiles currently assigned to the requested location and only while the latest explicit personal/internal-use consent is granted and unexpired. Keep raw feedback and arbitrary free text outside proposal, review, and response payloads. Require a distinct OIDC operator for approval, make request-key retries exact, and store approved mappings only in the location-scoped ledger. Exclude legacy global trust views. The scoped trust projection is implemented for approved identity evidence only, and an exact `stakeholder_identity:resolve` route returns approved mappings within their source location while current consent and canonical-party privacy checks hold. Neither path emits a global score or reads raw feedback. General trust evidence for other domains, additional source types, live OIDC/browser acceptance, RLS, populated parity, post-review consent disposition, and MAN-CAP-025 owner review remain later gates. Contract: `stakeholder-identity-kernel-contract.md`.

Status: identity-review, scoped identity-trust, and farmer-profile consumer-resolution slices completed locally; CAP-025 remains prepared (`P`), not accepted. See [migration 447 evidence](builds/2026-10-19-recovery/cap-025-stakeholder-trust-disposable.json) and [migration 448 evidence](builds/2026-10-19-recovery/cap-025-identity-resolution-disposable.json).

### CAP-027 facilitator recommendation review — 19 October 2026

Implemented the first location-scoped Kernel review queue and human
approve/reject decision path with exact `delphi:review`, signed context,
independent review, diversity/minority gates, exact retries, and append-only
reason-code audit. The corrected migration 450 disposable PostgreSQL 16
acceptance applies/replays and passes seven assertions; the function owner has
only the `UPDATE(id)` privilege needed to lock the study row. The operator
console now supports grant-gated queue reads and CSRF-protected decisions, with
approval withheld when blockers are present. Five focused console contract and
inline JavaScript syntax checks pass. No candidate or legacy database was
changed. CAP-027 remains prepared; live OIDC/browser behavior, populated
parity, universal ACL/RLS, and owner acceptance remain open.
