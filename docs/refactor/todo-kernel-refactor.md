# Kokonut Kernel refactor TODO

Updated: 29 October 2026. This is the active cross-phase work queue for the
owner-provided [architecture implementation plan](implementation-plan-alignment.md).
The detailed, historically preserved acceptance records remain in
[batches.md](batches.md); this file groups their remaining gates into work that
can proceed now and gates that need an owner, provider, populated source data,
or production environment. Check an item only when its evidence is recorded in
the batch log and the affected capability/progress records are updated.

## Completed in the current continuation

- [x] Replay all 675 ordered schema migrations through migration 684 on ARM64
  PostgreSQL/PostGIS under QEMU with verified resource limits, zero failures,
  zero seeds, and disposable cleanup ([evidence](builds/2026-10-29-recovery/arm64-resource-limited-schema-684.json)).
- [x] Convert farm/plot PostGIS boundaries and centers into explicit GeoJSON
  JSONB projections rather than serializing raw geometry
  ([evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).
- [x] Add strict Polygon/Point contracts for valid, null, and empty geometry;
  reject invalid coordinate structures and unexpected fields
  ([same evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).
- [x] Bind farm-summary location, farm, plot, and crop-cycle rows to the
  requested location and their parent records
  ([same evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).
- [x] Verify source projections and malformed/scope failures in focused
  mocked report and Gateway checks ([same evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).

- [x] Replace Comprehensive Status capital accounting's `JsonValue` with
  strict models for all four independently failure-tolerant projections
  ([evidence](builds/2026-10-29-recovery/comprehensive-status-capital-accounting-contract.json)).
- [x] Bind sections and draft credits to the composed location; validate
  advisory-only behavior, period/derived-field parity, draft-only ledger rows,
  and safe partial failures ([same evidence](builds/2026-10-29-recovery/comprehensive-status-capital-accounting-contract.json)).
- [x] Verify OpenAPI, malformed nested rows, and a valid partial-failure
  response with focused mocked route checks ([same evidence](builds/2026-10-29-recovery/comprehensive-status-capital-accounting-contract.json)).

- [x] Replace the Comprehensive Status training-impact `JsonValue` with strict
  public-view-backed section and session models ([evidence](builds/2026-10-29-recovery/comprehensive-status-training-impact-contract.json)).
- [x] Bind the section and sessions to the composed location, preserve nullable
  score fields, and validate lifecycle/type enums and exact count/hour/improvement
  aggregates ([same evidence](builds/2026-10-29-recovery/comprehensive-status-training-impact-contract.json)).
- [x] Verify the exact OpenAPI projection, malformed-output rejection, Decimal
  rounding parity, and the established section-error response
  ([same evidence](builds/2026-10-29-recovery/comprehensive-status-training-impact-contract.json)).

- [x] Replace the Comprehensive Status stakeholder-outcomes `JsonValue` with
  a strict schema-aligned section and exact outcome-row model; preserve the
  source query's verified/published filter ([evidence](builds/2026-10-29-recovery/comprehensive-status-stakeholder-outcomes-contract.json)).
- [x] Bind the section and every outcome row to the composed location, validate
  the lifecycle/importance enums and count parity, and keep its currently empty
  link projection explicitly empty ([same evidence](builds/2026-10-29-recovery/comprehensive-status-stakeholder-outcomes-contract.json)).
- [x] Verify OpenAPI, nullable fields, malformed rows, and the existing
  sanitized section-error response with mock-only route checks
  ([same evidence](builds/2026-10-29-recovery/comprehensive-status-stakeholder-outcomes-contract.json)).

- [x] Replace the Comprehensive Status holistic-wellbeing `JsonValue` section
  with strict public-view-backed cultural, metric, and participatory-action
  response models ([evidence](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json)).
- [x] Bind the nested holistic-wellbeing report to the composed location and
  reject undeclared fields, invalid maturity/value types, and malformed output
  with the existing sanitized error ([same evidence](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json)).
- [x] Preserve the section's established error shape and verify OpenAPI/runtime
  parity using synthetic response payloads ([same evidence](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json)).

- [x] Add a strict OpenAPI/runtime detail model for submitted report snapshots,
  preserving the dynamic report JSON object under the existing 512 KiB cap
  ([evidence](builds/2026-10-29-recovery/submitted-report-detail-gateway-contract.json)).
- [x] Bind the returned report ID to the requested path and reject undeclared
  fields, invalid status/data shape, and oversized payloads
  ([same evidence](builds/2026-10-29-recovery/submitted-report-detail-gateway-contract.json)).
- [x] Make success and error responses consistently private/no-store, including
  400/403/404/413/500/503 paths ([same evidence](builds/2026-10-29-recovery/submitted-report-detail-gateway-contract.json)).

- [x] Enforce the database review queue's stable ascending `created_at, id`
  order and unique summary IDs at the Gateway boundary
  ([evidence](builds/2026-10-29-recovery/ai-summary-review-page-integrity.json)).
- [x] Bind the content-truncated marker to the database's 20,000-character
  projection limit; malformed pages fail with sanitized no-store errors
  ([same evidence](builds/2026-10-29-recovery/ai-summary-review-page-integrity.json)).
- [x] Add mocked regressions for duplicate IDs, incorrect order, and short
  content marked truncated ([same evidence](builds/2026-10-29-recovery/ai-summary-review-page-integrity.json)).

- [x] Publish the strict human review decision request and response schemas
  for approved/rejected AI summaries, including reason-code/lifecycle mapping
  ([evidence](builds/2026-10-29-recovery/ai-summary-human-review-decision-contract.json)).
- [x] Bind response summary, decision, and resulting status to the request and
  reject invalid paths/reason pairings before service access
  ([same evidence](builds/2026-10-29-recovery/ai-summary-human-review-decision-contract.json)).
- [x] Preserve the existing 200 decision response and sanitize malformed
  service results with no-store errors; publish the response contract in
  OpenAPI ([same evidence](builds/2026-10-29-recovery/ai-summary-human-review-decision-contract.json)).

- [x] Add the strict authenticated AI-summary draft request/response contract,
  bind service output to the requested location/type, and validate lifecycle,
  source lineage, and no-store failures
  ([evidence](builds/2026-10-29-recovery/ai-summary-draft-response-contract.json)).
- [x] Reuse one strict source-reference model across draft and review routes,
  including bounded UUID samples, count/truncation consistency, and scope labels
  ([same evidence](builds/2026-10-29-recovery/ai-summary-draft-response-contract.json)).
- [x] Verify OpenAPI, malformed requests/responses, retries, and reviewed-state
  replay with focused route tests; no live database or provider was used
  ([same evidence](builds/2026-10-29-recovery/ai-summary-draft-response-contract.json)).

- [x] Replace both callsites for the internal stakeholder cockpit and the
  coordination-cockpit wildcard with the exact migration-238 summary fields
  ([evidence](builds/2026-10-29-recovery/kernel-strategy-internal-cockpit-projections.json)).
- [x] Verify the 20- and 22-column lists and unchanged internal report
  payloads across all three consuming report paths using fake cursors only
  ([same evidence](builds/2026-10-29-recovery/kernel-strategy-internal-cockpit-projections.json)).

- [x] Replace technology-roadmap and stakeholder-engagement report wildcards
  with the migration-defined 17-, 16-, and 14-column projections, preserving
  ordering, location filters, overdue filtering, and output payloads
  ([evidence](builds/2026-10-29-recovery/kernel-strategy-roadmap-engagement-projections.json)).
- [x] Verify all three ordered projections and report payloads with a focused
  fake-cursor regression; no database or provider was used
  ([same evidence](builds/2026-10-29-recovery/kernel-strategy-roadmap-engagement-projections.json)).

- [x] Replace six commons report wildcards with migration-backed, ordered
  projections; retain location/network scope and serialized rows
  ([evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).
- [x] Replace additional stakeholder, grievance, trust, value-stream, and
  governance report wildcards with exact schema projections and preserve
  report payloads
  ([same evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).
- [x] Align public summary count invariants and driver pagination checks in
  Gateway, Python, and JavaScript; metric counts match timestamp presence and
  published attestations remain a subset of all attestations
  ([same evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).
- [x] Normalize the TypeScript gRPC DataService responses to declared SDK
  shapes, correct `IRIInfo.hash_algorithm`, and bound/cancel the stream adapter
  ([same evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).
- [x] Validate the Data Stream attachment response against its exact 17-field
  projection, bind rows to the requested post, and redact malformed/private
  fields in no-store failures
  ([evidence](builds/2026-10-29-recovery/kernel-c2-file-and-crisp-contracts.json)).
- [x] Align Gateway and both public REST SDKs to CRISP's canonical evidence
  maturity range 0–6; regenerate and verify the public OpenAPI/SDK artifacts
  ([same evidence](builds/2026-10-29-recovery/kernel-c2-file-and-crisp-contracts.json)).

- [x] Replace the public stakeholder-cockpit and coordination-alliance
  wildcards with their exact 13-column migration-238 projections, preserving
  network-wide behavior and internal/public response separation
  ([evidence](builds/2026-10-29-recovery/kernel-strategy-cockpit-report-projections.json)).
- [x] Verify exact column order and unchanged public/internal payloads with a
  focused fake-cursor test; the report-source scan now finds no
  `SELECT * FROM v_public_*` in `services/export/reports`
  ([same evidence](builds/2026-10-29-recovery/kernel-strategy-cockpit-report-projections.json)).

- [x] Replace the organic readiness, transition, certification, prohibited-
  substance, input-audit, and harvest-segregation wildcards with exact ordered
  migration-055 public projections; retain their current location filters and
  report behavior ([evidence](builds/2026-10-29-recovery/kernel-organic-report-projections.json)).
- [x] Verify all six projections, location bindings, output rows, and existing
  readiness, transition, and input aggregates with a focused synthetic test
  ([same evidence](builds/2026-10-29-recovery/kernel-organic-report-projections.json)).

- [x] Replace the training-impact and reward-calibration report wildcards
  with the exact 15-column migration-backed public projections, preserving
  location scope, ordering, output rows, and report aggregates
  ([evidence](builds/2026-10-29-recovery/kernel-operations-training-reward-report-projections.json)).
- [x] Verify the two operations projections plus the approved report and
  assignment-proposal response contracts with focused synthetic checks; no
  database, provider, or live service was used
  ([same evidence](builds/2026-10-29-recovery/kernel-operations-training-reward-report-projections.json)).

- [x] Add a strict Comprehensive Status climate-impact success/error contract,
  binding nested calculations and stored summaries to the selected location
  and year while preserving shared protocols and existing content
  ([evidence](builds/2026-10-28-recovery/kernel-parallel-climate-sow-contracts.json)).
- [x] Replace `SELECT *` across all four Statement of Work parent/child reads
  with the complete current schema projections, preserving scope, ordering,
  and serialized fields ([same evidence](builds/2026-10-28-recovery/kernel-parallel-climate-sow-contracts.json)).

- [x] Add a strict location-bound Comprehensive Status regenerative-outcomes
  contract with period and aggregate validation, preserving current content.
- [x] Validate federation `shared_capabilities` as JSON at runtime without
  narrowing the existing JSONB payload or changing route/SDK behavior.
- [x] Replace stakeholder-outcome `SELECT *` with the explicit 22-column
  migration-aligned projection.
- [x] Replace Green Paper publication-status `SELECT *` with the explicit
  14-column view projection. These preserve current data and do not establish
  content-level privacy or populated-data parity
  ([evidence](builds/2026-10-28-recovery/kernel-parallel-regenerative-federation-report-projections.json)).

- [x] Add a strict Comprehensive Status capital-efficiency contract for both
  public-view row families, including exact location scope.
- [x] Replace GNH-alignment `SELECT *` with the full 14-column public-view
  projection and verify report payload parity.
- [x] Replace cultural-preservation `SELECT *` with the full 16-column
  public-view projection and verify report payload parity.
- [x] Replace renewable-energy `SELECT *` with the full 18-column public-view
  projection and verify report payload parity.
- [x] Validate public CRISP assessment payloads in Python and TypeScript,
  including match to the requested location and date/status/value constraints
  ([evidence](builds/2026-10-28-recovery/kernel-parallel-capital-wellbeing-crisp-contracts.json)).

- [x] Add a strict Comprehensive Status community-governance contract that
  preserves shared null-location and selected-location mechanism rows.
- [x] Add a strict location-bound foundational-wellbeing contract that allows
  qualitative-only observations with null score and count.
- [x] Replace vulnerable-access `SELECT *` with its exact 16-column projection
  and verify serialized payload parity.
- [x] Replace foundational-wellbeing `SELECT *` with its exact 12-column
  projection and verify serialized payload parity.
- [x] Replace community-governance `SELECT *` with its exact 17-column
  projection and verify serialized payload parity, including shared rows.
- [x] Validate public metrics responses in Python and TypeScript, including
  requested-location identity and result-count parity.
- [x] Validate nested public location summaries and both location identities
  in Python and TypeScript, including source-backed metric count/timestamp and
  published-attestation subset invariants
  ([evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).

- [x] Add strict Comprehensive Status contracts for farm summary and published
  financial sustainability, including location binding and existing bounded
  error shapes; preserve current fields and report behavior
  ([evidence](builds/2026-10-28-recovery/kernel-parallel-comprehensive-report-contracts.json)).
- [x] Replace the climate-impact stored-summary `SELECT *` with all 24 current
  schema columns while preserving query bindings and the returned payload
  ([same evidence](builds/2026-10-28-recovery/kernel-parallel-comprehensive-report-contracts.json)).

- [x] Complete the parallel C1/C2/C5 code batch: resolve module-level SQL
  constants only under conservative single-binding rules and refresh the
  ledger/inventories; add strict private Baal Gateway contracts without
  adding those routes to the public SDK; and replace farm-summary `SELECT *`
  projections with explicit current-schema fields. No runtime ACL or report
  lifecycle policy changed ([evidence](builds/2026-10-28-recovery/kernel-parallel-c1-c2-c5-code-batch.json)).

- [x] Add strict OpenAPI/runtime response contracts for farm-activity list and
  published-list reads, including exact location, source-system, and published
  lifecycle checks.
- [x] Validate pollution-incident resolution results against the requested
  incident and location, with a fixed resolved status and no undeclared fields.
- [x] Add a strict private governance-tension detail contract for its
  location/tension identity, bounded event history, and safe reviewer
  projection.
- [x] Validate driver-catalog responses against the generated page and entry
  contracts in both native REST SDKs, rejecting malformed types, bounds, and
  undeclared fields while retaining the HTTP response on SDK errors.
- [x] Add a strict OpenAPI/runtime success contract for Delphi study-open
  readiness. Bind study/location IDs, validate the fixed SQL-derived blocker
  order and eligibility facts, and return a sanitized no-store error for
  malformed projections.
- [x] Align Python and JavaScript native REST SDK error objects by preserving
  the received HTTP response for status, JSON, and envelope failures; transport
  errors without an HTTP response remain unchanged.
- [x] Add a strict OpenAPI/runtime contract to the private stakeholder identity
  resolution read. It returns only the requested location, canonical party ID,
  and aware resolution timestamp; malformed service projections fail with a
  sanitized no-store error.
- [x] Add a strict OpenAPI/runtime success contract to the location-scoped
  governance-tension review queue. Validate its enums, severity bounds,
  timestamps, exact projection, descending order, location, and cursor binding;
  invalid projections return the existing sanitized no-store error.
- [x] Correct the weekly Prefect flow description and add a regression proving
  the currently deployed flow runs climate refresh only. The legacy ML
  retraining path remains outside the Kernel job catalog until it receives a
  signed, bounded identity and retry/idempotency contract.
- [x] Add a strict, location/study/page-bound contract for the Delphi
  participant-invite inventory. Private invite tokens and participant identity
  remain outside the projection; continuation stops at the existing offset
  ceiling.
- [x] Validate `mrv_claim.sensor_device_id` and `sensor_alert_id` through the
  referenced device's location in the optional Directus tenant hook. The
  polymorphic source-record array remains unresolved because it has no table
  discriminator; no broader Directus parity is claimed.
- [x] Convert all four State-of-Kokonut funding/actor queries from conditional
  SQL fragments to static named-bind predicates. Explicit selected-location
  calls remain location-bound; `None` preserves the deliberate network rollup.
  The helper inventory now resolves 169/169 query sites with zero unresolved
  SQL sources.
- [x] Add strict location, ordering, cursor, count, and projection contracts
  for threatcasting backcast-plan list/detail reads while retaining their
  advisory-only semantics.
- [x] Repair the Kernel release-input lock after the OIDC Dockerfile added its
  shared HTTP client requirement. The hash gate now covers the updated
  `Dockerfile.kernel` plus `requirements/oidc.txt` and
  `requirements/http-client.txt`. The local release-input check and 36 focused
  Kernel profile/release-gate tests pass. Hosted CI #71 failed on the stale
  Dockerfile hash; Security passed. A new hosted CI run is still required to
  confirm the repair. See
  [evidence](builds/2026-10-28-recovery/ci-kernel-release-lock-repair.json).
- [x] Keep the migration-seeded `market_reference_data` catalog readable but
  immutable to `kokonut_runtime`. Schema 142 defines commodity categories and
  unit labels, and no service or extension writes the table. Migration 678 and
  runtime-role provisioning deny table and residual column writes while
  preserving the separate Directus administration grant. Focused native and
  ARM64/QEMU PostgreSQL checks pass migration replay, compatibility-grant
  reapplication, read access, write denial, and Directus-role preservation.
  The full native replay and two-tenant probe pass through all 669 schemas;
  candidate and legacy databases remain untouched. See
  [evidence](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-disposable.json).
- [x] Keep the schema-seeded `quantity_unit` vocabulary readable but immutable
  to `kokonut_runtime`. Migration 112 defines and seeds the shared unit labels;
  source and runtime SQL inventories found no application writer or relation
  reader. Migration 679 and runtime-role provisioning deny table and residual
  column writes while preserving Directus administration. Focused native and
  ARM64/QEMU PostgreSQL checks pass migration replay, read access, write
  denial, provisioner reapplication, and Directus grant preservation. The full
  native replay and 34-check two-tenant probe pass through all 670 schemas;
  candidate and legacy databases remain untouched. See
  [native evidence](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-disposable.json).
- [x] Remove stale Directus workflow-role authorization caching. The hook now
  resolves the current role name on each non-admin authorization check, so a
  role rename takes effect immediately; server accountability remains required
  and payload-supplied accountability is ignored. The role/error-safety/workflow
  selection passes 46 tests, and the extension build/typecheck passes. No live
  Directus or database was used ([evidence](builds/2026-10-28-recovery/directus-role-resolution-freshness.json)).
- [x] Bind Delphi worker output to the normalized requested study as well as
  the requested location. An unexpected row returned by the source view now
  fails closed, rolls back the transaction, and closes the connection. The
  focused Delphi worker selection passes 3 tests with targeted Ruff and
  compilation ([evidence](builds/2026-10-28-recovery/delphi-source-study-scope-match.json)).
- [x] Require explicit location scope for the adoption-barrier report before
  database access and remove its unscoped SQL branch. Its location-bound public
  projection still includes reviewed global rows. The focused report selection
  passes 456 tests with Ruff, query-scope inventory, Python compilation, and
  diff checks ([evidence](builds/2026-10-28-recovery/adoption-barriers-location-scope.json)).
- [x] Re-run all schema migrations through 679 on ARM64/QEMU with a 1.5 GiB,
  two-CPU database limit. All 670 schemas applied on `aarch64`, with zero
  pending or failed migrations, no seeds, no OOM, and successful cleanup. This
  remains software portability evidence only; physical Pi, populated-data, and
  production recovery gates remain open ([evidence](builds/2026-10-28-recovery/arm64-resource-limited-schema-679.json)).
- [x] Reconcile C4 provider-job sources. The 23-entry native job catalog matches
  its generated contract and five Prefect deployments; the legacy health-check
  flow is not deployed, and the forecast worker remains default-off. Do not
  invent an active schedule; C4 still needs owner/runtime-state reconciliation
  ([inventory](worker-job-contract-inventory.json)).
- [x] Align Python and TypeScript `get_item` projection serialization. Python
  now omits `fields` for `None`, emits JSON `[]` for an explicit empty list,
  and sends populated field lists as CSV, matching the pinned TypeScript SDK.
  Three mocked wire-contract cases, targeted Ruff, compilation, and diff checks
  pass ([evidence](builds/2026-10-28-recovery/sdk-empty-fields-projection-parity.json)).
- [x] Require explicit location scope in the four location-lineaged stakeholder
  report generators before database access. Their direct-call and CLI behavior
  now agrees with the report registry; `--all` is rejected for these reports.
  The combined nine-module report suite passes 507 tests with four database-
  dependent skips, plus generated query-scope inventory, Ruff, compilation, and diff
  checks ([evidence](builds/2026-10-28-recovery/stakeholder-report-explicit-location.json)).
- [x] Align the TypeScript `ReportSnapshot` model with the canonical SQL and
  Python model; removed three unsupported TypeScript fields. Focused schema
  tests pass (13), and the full parity check covers 109 models/2,150 columns
  ([evidence](builds/2026-10-28-recovery/report-snapshot-types-canonical-schema-parity.json)).
- [x] Require explicit location scope for direct `bio_recipe_library` calls
  before opening a cursor and remove the unscoped SQL branch. Reviewed global
  public catalog rows remain visible under the selected-location query; the
  focused check passes 349 tests with inventory, Ruff, compilation, and diff
  checks ([evidence](builds/2026-10-28-recovery/bio-recipe-library-location-scope.json)).
- [x] Reject booleans for notification-outbox batch-size and lease-duration
  bounds before database access. Python's `bool` subclassing of `int` had
  admitted `True` as a one-second lease; 40 mocked outbox/delivery tests pass
  ([evidence](builds/2026-10-28-recovery/notification-outbox-rejects-boolean-bounds.json)).
- [x] Require explicit location scope for direct `community_governance`
  report calls before cursor creation; the selected-location query preserves
  reviewed public global rows. The focused suite passes 341 tests, and the
  combined nine-module report selection passes 507 with four database-
  dependent skips ([evidence](builds/2026-10-28-recovery/community-governance-location-scope.json)).
- [x] Require explicit locations for `governance_inclusion` and
  `governance_throughput` before cursor creation; their selected-location
  queries retain reviewed public global rows. Dedicated tests pass 290 and 11
  cases respectively. The integrated nine-module report suite passes 507 with
  four database-dependent skips; the generated inventory has 171 direct query
  sites, 170 positional bind sites, and zero unresolved sites. See
  [inclusion evidence](builds/2026-10-28-recovery/governance-inclusion-location-scope.json)
  and [throughput evidence](builds/2026-10-28-recovery/governance-throughput-location-scope.json).
- [x] Publish existing `1..100` pagination limits in the Gateway OpenAPI
  contract for operator ecocredit-batch and attestation list routes. Invalid
  values fail before service invocation; the focused plus existing route suite
  passes 21 tests ([evidence](builds/2026-10-28-recovery/gateway-pagination-openapi-bounds.json)).
- [x] Extend Gateway pagination bounds to Field Activity, nutrient-balance,
  irrigation, crop-simulation, traceability, geostatistics, trend-analysis,
  extension-learning, pollinator health, Delphi consultation, competitive
  landscape, business-architecture, business-planning, Delphi recommendation
  draft, recommendation review, stakeholder identity, stakeholder-trust, and
  Delphi minority-review lists, including AI-summary review, strategy,
  sequential decisions, governance roles, planning budgets, business-planning
  history, threatcasting, Delphi participant invites, consent notices,
  operating-pilot, solution-lifecycle, and pollution-incident queues. The
  endpoints publish validated limit/offset constraints in OpenAPI and reject
  invalid values before service access. Focused suites pass 6, 19, 13, 24, 15,
  73, 34, 12, 74, 21, 50, 18, 32, 15, 18, 13, 20, 21, 28, 14, 20, 8, 20, 23, 14, 29, 35, 243, 448, and 25 tests respectively; bounds match each service's existing maximum
  ([Field Activity](builds/2026-10-28-recovery/farm-activity-pagination-openapi-bounds.json),
  [nutrients](builds/2026-10-28-recovery/nutrient-pagination-openapi-bounds.json),
  [irrigation](builds/2026-10-28-recovery/irrigation-pagination-openapi-bounds.json),
  [crop simulations](builds/2026-10-28-recovery/crop-simulation-pagination-openapi-bounds.json),
  [traceability](builds/2026-10-28-recovery/traceability-pagination-openapi-bounds.json),
  [geostatistics](builds/2026-10-28-recovery/geostatistics-pagination-openapi-bounds.json),
  [trend analysis](builds/2026-10-28-recovery/trend-analysis-pagination-openapi-bounds.json),
  [extension learning](builds/2026-10-28-recovery/extension-learning-pagination-openapi-bounds.json),
  [pollinator health](builds/2026-10-28-recovery/pollinator-pagination-openapi-bounds.json),
  [Delphi consultation](builds/2026-10-28-recovery/delphi-consultation-pagination-openapi-bounds.json),
  [competitive landscape](builds/2026-10-28-recovery/competitive-landscape-pagination-openapi-bounds.json),
  [business architecture](builds/2026-10-28-recovery/business-architecture-pagination-openapi-bounds.json),
  [Delphi recommendation drafts](builds/2026-10-28-recovery/delphi-draft-study-pagination-openapi-bounds.json),
  [stakeholder identity](builds/2026-10-28-recovery/stakeholder-identity-pagination-openapi-bounds.json),
  [business planning](builds/2026-10-28-recovery/business-planning-pagination-openapi-bounds.json),
  [stakeholder trust](builds/2026-10-28-recovery/stakeholder-identity-trust-pagination-openapi-bounds.json),
  [Delphi minority review](builds/2026-10-28-recovery/delphi-minority-review-pagination-openapi-bounds.json),
  [AI-summary review](builds/2026-10-28-recovery/ai-summary-review-pagination-openapi-bounds.json),
  [strategy](builds/2026-10-28-recovery/strategy-pagination-openapi-bounds.json),
  [sequential decisions](builds/2026-10-28-recovery/sequential-decision-pagination-openapi-bounds.json),
  [governance roles](builds/2026-10-28-recovery/governance-role-pagination-openapi-bounds.json),
  [planning budgets](builds/2026-10-28-recovery/planning-budget-pagination-openapi-bounds.json),
  [business-planning history](builds/2026-10-28-recovery/business-planning-edit-history-pagination-openapi.json),
  [threatcasting](builds/2026-10-28-recovery/threatcasting-pagination-openapi-bounds.json),
  [Delphi participant invites](builds/2026-10-28-recovery/delphi-participant-invite-pagination-openapi.json),
  [Delphi consent notices](builds/2026-10-28-recovery/delphi-consent-notice-pagination-openapi-bounds.json),
  [operating pilot](builds/2026-10-28-recovery/operating-pilot-pagination-openapi-bounds.json),
  [solution lifecycle](builds/2026-10-28-recovery/solution-lifecycle-pagination-openapi-bounds.json),
  [waste incident offset](builds/2026-10-28-recovery/waste-incident-offset-bounds.json)).
- [x] Close two more report input-scope mismatches: `replication_readiness`
  and `scaling_roadmap` were location-required by the registry/CLI but their
  direct generators accepted missing locations and queried all public-view
  rows. Both now fail before opening a cursor while keeping reviewed global
  rows inside a selected-location query. The integrated report selection
  passes 516 tests with four database-dependent skips; the fresh inventory
  has 169 direct query sites, 168 positional bind sites, and zero unresolved
  ([replication readiness](builds/2026-10-28-recovery/replication-readiness-location-scope.json),
  [scaling roadmap](builds/2026-10-28-recovery/scaling-roadmap-location-scope.json)).
- [x] Restore typed-list extension query parity across the Python and
  JavaScript SDKs. Python `ListOptions.extra_params` now matches TypeScript
  `ListOptions.extraParams`; representative scoped Field Note reads preserve
  extension parameters while standard options and the required location filter
  remain authoritative. The focused Python SDK/method-parity suite passes 107
  tests, JavaScript passes 56, the TypeScript build and targeted Ruff pass, and
  mocked checks use no database, provider, or network ([evidence](builds/2026-10-28-recovery/sdk-typed-extension-query-parity.json)).
- [x] Keep calculated NOI snapshots read-only in both SDKs. Source review found
  no SDK mutation callsites; generic writes could supply final financial values
  without calculation provenance. Preserve list/detail/crop-cycle reads and
  leave generation in the existing worker/service integrations. Python SDK,
  parity, and report-governance tests pass 111; JavaScript passes 55; the
  TypeScript build, Ruff, and compilation pass. Existing service and Directus
  extension writers were not changed or runtime-validated. See
  [evidence](builds/2026-10-27-recovery/sdk-noi-snapshot-read-only-contract.json).
- [x] Remove generic attestation-record writes from both SDKs and correct the
  workflow examples. `attestation_record` represents governed workflow state
  and chain-indexer projections; direct collection CRUD can create a database
  row without EAS publication or independent review. Preserve list/detail,
  pending-state, and subject-filtered reads. Real chain submission/revocation
  remains in the dedicated EAS service and governed signing workflow. Python SDK,
  parity, and report-governance tests pass 109; JavaScript passes 54; the
  TypeScript build, Ruff, and compilation pass. No database/provider was used.
  See [evidence](builds/2026-10-27-recovery/sdk-attestation-read-only-contract.json).
- [x] Cross-reference the original plan's Phases 0–8 against the repository
  ledger and sprint scope.
- [x] Replay the current 642 ordered schema files on an isolated database and
  run the two-tenant signed-context probe. The probe exposed 1,101 public
  tables with runtime DML and RLS disabled; it does not prove isolation for
  those tables.
- [x] Start a fresh isolated ZITADEL API/Login stack and confirm internal OIDC
  discovery. Fix and record safe permissions for its Login UI token volume.
- [x] Keep these findings and acceptance limits in the sprint, phase and
  capability records. Local commits: `020a5279`, `be1c2c2e`, `968a49fc`,
  `e6bee5ae`, `2f7e0c0a`, `97317dfc`, `263a6d19`, `03d215b2`, `cd7a02bc`.
- [x] Add relation-level runtime ACL/default-ACL capture to the isolated probe
  and a source-callsite/revoke join at
  [`scripts/runtime-privilege-callsite-report.py`](../../scripts/runtime-privilege-callsite-report.py).
  The 26 October full-schema report covered all 1,511 public relations and
  matched 92 source-declared runtime boundaries. The current 27 October replay
  through migration 652 covers the same 1,511 relations and matches 93
  boundaries with zero gaps. It records 1,026 ordinary/partitioned relations
  with effective table-level DML while RLS is off; one now has insert-only
  append-log access, so the count is not a count of UPDATE/DELETE exposure.
  The SQL callsite join remains heuristic. Candidate and legacy privileges
  were untouched.
- [x] Source-audit migration-seeded `waste_type` and `disposal_method`: current
  services use their values on `waste_stream` and have no application write
  target against either lookup catalog. Migration 660, runtime provisioning,
  and the disposable acceptance harness now keep them readable while denying
  runtime mutation. The source/migration/ARM64-contract selection passes 121
  tests; Ruff, compilation, SQL/worker inventories, dependency/provider
  boundaries, matrix validation, and diff checks pass. Database acceptance
  remains open because a read-only Docker query timed out after eight seconds.
  Candidate and legacy databases were not contacted.
- [x] Implement the source-declared C1 runtime ACL repair in role provisioning:
  after the compatibility grant, deny direct runtime access to the 79 private
  tables, deny writes on 12 migration-defined mutation-only tables, and keep
  the append-only farm-activity ledger SELECT-only. The provisioner verifies
  the resulting table and column ACLs. Static comparison covers 91 private or
  mutation-denied relations plus the separate API-key read-only column
  allowlist, with no policy gap. The focused runtime-role suite passes 48
  tests, and a disposable PostgreSQL fixture confirms the scoped ACL outcomes
  plus column-grant detection; full migration-installed acceptance is recorded
  immediately below.
- [x] Complete the 26 October full-schema runtime-role acceptance against all 642 ordered
  migrations through 651: the provisioner installs and verifies all 79 private
  and 12 mutation-denied relation boundaries, with zero residual table or
  column privileges; the general runtime retains the farm-activity audit read.
  Two real restricted operator sessions establish correct synthetic tenant
  context through the bounded function, reject cross-location access, and clear
  context on denial and transaction end. No seeds or farm data were loaded;
  cleanup succeeded; candidate and legacy databases were untouched. The
  probe also verifies API-key reads are limited to seven reviewed columns and
  all writes are denied. The separate ARM64 full-schema replay also passes,
  while this role probe ran natively with matching AMD64 images. The refreshed
  26 October report covered 92 declared boundaries; the current 27 October
  report covers 93 (92 table policies plus the API-key column allowlist) with
  zero gaps across 1,511 relations. See
  [full-schema role evidence](builds/2026-10-26-recovery/runtime-role-full-schema-disposable.json).
- [x] Create a reproducible, read-only source-line inventory for C1's remaining
  analytics write candidates. It links 275 currently unprotected relations to
  425 unique candidate SQL sites across 89 source files (437 relation/site
  references) and reports any unmatched source relation; none are missing.
  Every entry stays marked for caller/source review, and the report explicitly
  forbids inferring authorization or revoking privileges from static matches.
  No database, candidate, or legacy service was accessed. See the
  [inventory](builds/2026-10-27-recovery/analytics-runtime-write-candidate-inventory.json)
  and [generator](../../scripts/runtime-analytics-write-candidate-inventory.py).
- [x] Correct third-party data-portability audit writes to use the existing
  `data_access_log` contract from migration 144. The previous insert targeted
  `access_audit_log` with columns and a status value that table does not have;
  it now records an export/success event in the correct transaction. The
  focused data-governance and analytics-inventory suites pass. No schema change
  or database rollout was needed.
- [x] Enforce the append-only runtime boundary for `data_access_log`. Migration
  652 clears table and residual column grants, restoring only `SELECT` and
  `INSERT`; the provisioner reapplies and verifies that policy after its
  compatibility grant. Disposable PostgreSQL 16 confirms migration replay,
  successful read/append, denial of update/delete/truncate, and removal of stale
  column grants. The refreshed native full-schema probe passes all 643
  migrations through 652 and two-tenant signed-context acceptance with zero
  seeds; no candidate/legacy state was used. The policy report covers 93
  declared boundaries with zero gaps across 1,511 relations. Its 1,026
  table-level DML/RLS-disabled count includes the intentionally insert-only
  audit ledger; it does not mean all those relations allow UPDATE/DELETE. See
  [migration](../schemas/postgres/652_runtime_append_only_data_access_log.sql),
  [isolated acceptance](builds/2026-10-27-recovery/runtime-append-only-data-access-log-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Replay the complete current schema through migration 652 under Docker
  linux/arm64 QEMU. All 643 migration files applied with zero pending/failed,
  no seeds, no host ports, and successful cleanup. This is software portability
  evidence only. See the [ARM64 replay record](builds/2026-10-27-recovery/arm64-schema-652-disposable.json).
- [x] Build the current Kernel app OCI image for AMD64 and ARM64 and validate
  the release lock: all 72 Python packages match across architectures. The
  ARM64 image smoke imports the Gateway factory and migration-652 runtime-role
  policy in a no-network, read-only container; temporary artifacts were
  removed. See the [build/smoke record](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json).
- [x] Build and validate the optional ClickHouse dependency superset for both
  architectures: 75 locked Python packages match. The ARM64 smoke imports
  `clickhouse_connect` offline. The minimal, edge, standard, and analytics
  Compose selections also pass ARM64 `config --quiet` with synthetic
  placeholders; no services or profile resources were started. See the same
  [build/profile record](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json).
- [x] Replay all 643 schema migrations through 652 on ARM64/QEMU with the
  disposable database limited to 1.5 GiB memory, no additional swap, and two
  CPUs. All migrations applied with zero failures/pending, no seeds, no OOM
  kill, and successful temporary-resource cleanup. See the
  [resource-limited evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-652.json).
- [x] Exercise migration 653's read-only advisory-rule ACL on the local ARM64
  PostgreSQL image. The disposable synthetic-table check replays the migration,
  verifies reads, denies insert/update/delete and references, and confirms the
  runtime provisioner removes simulated broad and column grants. This validates
  the migration slice on Docker's ARM64 platform; the full ARM64 schema chain
  remains through migration 652 ([evidence](builds/2026-10-27-recovery/advisory-rule-runtime-read-only-arm64-disposable.json)).
- [x] Launch the current Kernel Gateway on ARM64 under a 512 MiB memory, one-CPU,
  64-PID, no-network, read-only-root container budget. Docker reports the exact
  limits, and `/health` returns `status=ok`, `service=gateway`, and
  `audit_capture=ok`; the checker removes its temporary container and image.
  This is process liveness with no PostgreSQL/provider connectivity, not schema
  readiness or Pi hardware acceptance ([checker](../../scripts/check-kernel-app-resource-disposable.py);
  [evidence](builds/2026-10-27-recovery/kernel-app-arm64-constrained-runtime.json)).
- [x] Verify age-encrypted single-database dump/restore plumbing using two
  synthetic rows, a wrong-key rejection, and restoration into a fresh
  `template0` database. The checker uses network-disabled containers and
  removes its uniquely labeled volumes. This does not exercise the full
  `kernel-checkpoint.sh`/role-bootstrap recovery sequence or provider/media
  state ([checker](../../scripts/check-kernel-backup-restore-disposable.py);
  [evidence](builds/2026-10-27-recovery/kernel-synthetic-backup-restore.json)).
- [x] Exercise the actual `kernel-checkpoint.sh` plus fresh-cluster role
  prerequisites and full database restore. All 643 migrations through 652
  restore atomically from the age-encrypted checkpoint with matching migration
  fingerprint and synthetic sentinel. The recovery Compose target raises
  `max_locks_per_transaction` to 4096 to accommodate the full schema. The
  uniquely named, internal-only source and target projects and temporary
  checkpoint were removed. No seeds, farm data, candidate, or legacy state was
  used ([evidence](builds/2026-10-27-recovery/kernel-checkpoint-restore-disposable.json);
  [recovery procedure](recovery-preparation.md)). This is synthetic local
  acceptance only; populated data, external media/providers, R2, full platform,
  constrained restore runtime, and 24-hour recovery remain open.
- [x] Make the analytics write-candidate inventory distinguish DML targets
  from tables read by a statement. Runtime SQL inventory version 2 now records
  conservative targets for simple leading INSERT/UPDATE/DELETE/MERGE statements;
  the analytics join uses those targets and keeps unmatched ACL candidates
  visible. This corrected two `INSERT ... SELECT` false positives: `advisory_rule`
  and `farm` are source reads, not the insert targets. The report now covers 275
  ACL candidate relations and 425 target sites identified by the conservative
  matcher across 89 files; those two rows are explicitly unmatched for source
  review. No grants or database
  state changed ([inventory](builds/2026-10-27-recovery/analytics-runtime-write-candidate-inventory.json);
  [scanner](../../scripts/worker_sql_inventory.py)).
- [x] Keep shared advisory rule configuration readable but immutable to the
  general runtime role. Source review found the application reads
  `advisory_rule` to create farm recommendations; no application writer was
  found, and seed/admin processes remain the configuration path. Migration 653
  removes table and residual column write/reference grants, restores `SELECT`,
  and the runtime provisioner reapplies that boundary after compatibility
  grants. Disposable PostgreSQL 16 confirms migration replay, read success,
  insert/update/delete denial, and stale grant cleanup. A clean 644-migration
  replay through 653 passed full runtime provisioning and the two-tenant
  signed-context probe. The refreshed report covers 94 boundaries with no
  gaps; 1,025 relations retain effective DML while RLS is disabled, so broader
  C1 work remains open. The analytics inventory now has 274 candidate ACL
  relations and 425 write-target sites across 89 files; `farm` is the remaining
  unmatched source candidate. Source review traced the analytics reference to
  `INSERT ... SELECT` statements that write other tables; the complete writer
  set and optional Directus behavior for this core relation are not established,
  so its grants remain unchanged. See [migration](../schemas/postgres/653_runtime_advisory_rule_read_only.sql),
  [disposable ACL check](builds/2026-10-27-recovery/advisory-rule-runtime-read-only-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-653-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Make the shared `crop_family` taxonomy read-only to the general runtime.
  Source review found eight analytics SELECT sites and no service, extension,
  app, script, or migration writer after seed initialization; taxonomy changes
  remain a seed/admin operation. Migration 654 clears table and residual
  column INSERT/UPDATE/REFERENCES grants and restores SELECT. The provisioner
  reapplies the same rule after compatibility grants. A focused disposable
  PostgreSQL check confirms migration replay, read success, write/truncate and
  reference denial, and stale-grant cleanup. A clean native replay through all
  645 migrations passes runtime provisioning and the two-tenant signed-context
  probe. The report now covers 95 boundaries across 1,511 relations with zero
  gaps; 1,024 relations retain effective DML while RLS is disabled. The
  analytics candidate inventory remains 274 relations and 425 target sites
  across 89 files, with `farm` unmatched pending complete writer/Directus
  review. The focused 129-test selection, Ruff, compilation, source inventory,
  and matrix validation pass. Candidate and legacy databases were untouched.
  Rollback may revert application code while retaining migration 654; restoring
  writes requires a separately reviewed forward migration. See
  [migration](../schemas/postgres/654_runtime_crop_family_read_only.sql),
  [disposable ACL check](builds/2026-10-27-recovery/crop-family-runtime-read-only-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-654-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Verify migrations 652–654 and the read-only `crop_family` boundary on
  the local ARM64 PostgreSQL image. The loopback-restricted disposable synthetic
  ACL check confirms migration apply/replay, SELECT success, mutation,
  REFERENCES, and stale table/column grant denial for all three policies.
  Docker reports `linux/arm64`; temporary resources were removed. This is
  focused QEMU software-portability evidence, not a full schema replay through
  654 or Raspberry Pi hardware acceptance ([evidence](builds/2026-10-27-recovery/crop-family-runtime-read-only-arm64-disposable.json)).
  The full ARM64/QEMU chain subsequently passed all 645 files through 654
  under the resource limits recorded below.
- [x] Keep `crop_nutrient_removal_factor` readable but immutable to the general
  runtime. Source audit found the relation is initialized by migration 151 and
  read by `services/analytics/nutrient_budget.py`; no application writer was
  found. Migration 655 clears table and column mutation/reference grants, and
  the runtime provisioner reapplies the policy after compatibility grants. A
  disposable PostgreSQL 16 check confirms replay, SELECT success, and mutation,
  truncate, reference, and stale-column-grant denial. A clean native replay of
  all 646 migrations through 655 passes provisioner setup and the two-tenant
  signed-context probe. The refreshed source report covers 96 declared
  boundaries with zero gaps; 1,023 relations retain effective table-level DML
  while RLS is disabled. The target-aware analytics inventory remains 274
  relations and 425 write sites across 89 files, with `farm` unmatched pending
  source/Directus review. All 130 focused tests pass, along with Ruff,
  compilation, source inventories, dependency/provider checks, and capability
  validation. Candidate and legacy databases were untouched. Retain migration
  655 on code rollback; restoring runtime writes requires a separately reviewed
  forward migration ([migration](../schemas/postgres/655_runtime_crop_nutrient_removal_factor_read_only.sql);
  [ACL evidence](builds/2026-10-27-recovery/crop-nutrient-factor-runtime-read-only-disposable.json);
  [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-655-disposable.json);
  [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Replay the complete 645-file schema through migration 654 on ARM64/QEMU
  under a verified 1.5 GiB memory/swap and two-CPU database limit. All files
  applied with zero failures or pending migrations, no seeds or farm data, no
  OOM kill, and successful temporary-resource cleanup. This is software
  portability evidence only; it is not a full replay through 655 or physical
  Raspberry Pi acceptance ([evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-654.json)).
- [x] Verify the read-only `crop_nutrient_removal_factor` ACL on ARM64/QEMU
  together with migrations 652–654. The disposable PostgreSQL check confirms
  migration apply/replay, SELECT success, and table/column mutation, truncate,
  REFERENCES, and stale-grant denial for the 15 mutation-denied relations; all
  79 private relations remain inaccessible. Temporary resources were removed.
  This is focused software portability evidence, not Raspberry Pi hardware
  acceptance ([evidence](builds/2026-10-27-recovery/crop-nutrient-factor-runtime-read-only-arm64-disposable.json)).
- [x] Keep migration-seeded `certification_type` lookup data read-only to the
  general runtime. The service/Gateway callsites only resolve the shared
  reference; migration 143 initializes it, and no application or extension
  writer was found. Migration 656 removes table and residual column
  mutation/reference grants and restores `SELECT`; the runtime provisioner
  reapplies that contract after compatibility grants. Disposable PostgreSQL 16
  checks pass on native AMD64 and ARM64/QEMU. A clean native replay of all 647
  migrations through 656 passes full runtime provisioning and the two-tenant
  signed-context probe. The refreshed report covers 97 declared boundaries
  with zero gaps, and 1,022 public relations retain effective table DML while
  RLS is disabled. The 131-test focused selection and static boundary checks
  pass. Candidate and legacy databases were untouched. Retain migration 656 on
  code rollback; restoring runtime writes requires a separately reviewed
  forward migration ([migration](../schemas/postgres/656_runtime_certification_type_read_only.sql);
  [native ACL check](builds/2026-10-27-recovery/certification-type-runtime-read-only-disposable.json);
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-656-disposable.json);
  [source-policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Verify migration 656's read-only `certification_type` policy on ARM64/QEMU.
  The synthetic PostgreSQL 16 fixture confirms migration apply/replay, SELECT
  success, write/truncate/reference denial, and stale table/column-grant
  removal after provisioner reapplication. All 79 private relations remain
  inaccessible and all 16 mutation-denied relations remain read-only. This is
  focused software portability evidence, not a full ARM64 replay through 656
  or physical Raspberry Pi acceptance ([evidence](builds/2026-10-27-recovery/certification-type-runtime-read-only-arm64-disposable.json)).
- [x] Protect migration-seeded `cooperative_type` and
  `dfs_insurance_product_type` reference catalogs from runtime mutation. Their
  service callsites only read the shared catalogs, the schema migrations seed
  them, and no service, extension, or script writer was found. Migration 657
  clears table and residual column INSERT/UPDATE/REFERENCES grants, restores
  SELECT, and the runtime provisioner reapplies the boundary after compatibility
  grants. Native and ARM64/QEMU disposable PostgreSQL 16 checks pass migration
  replay, reads, mutation/truncate/reference denial, stale-grant cleanup, and
  provisioner reapplication. A clean native replay of all 648 migrations
  through 657 passes full runtime provisioning and the signed two-tenant
  context probe. The refreshed report covers 99 boundaries with zero gaps;
  1,020 public relations still retain table DML while RLS is disabled. All 132
  focused migration/runtime-boundary/report/inventory tests pass, along with
  Ruff, compilation, SQL/worker inventories, dependency/provider checks, and
  matrix validation. Candidate and legacy databases were untouched. Retain
  additive migration 657 on code rollback; restoring writes requires a
  separately reviewed forward migration ([migration](../schemas/postgres/657_runtime_reference_catalogs_read_only.sql);
  [native ACL](builds/2026-10-27-recovery/reference-catalogs-runtime-read-only-disposable.json);
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-657-disposable.json);
  [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Verify migration 657's reference-catalog ACL on ARM64/QEMU. The synthetic
  PostgreSQL 16 fixture confirms apply/replay, SELECT success,
  mutation/truncate/reference denial, and stale table/column-grant removal
  after provisioner reapplication across 18 mutation-denied relations. All 79
  private relations remain inaccessible. The full ARM64 schema chain remains
  through 654; this is focused software-portability evidence, not Raspberry Pi
  hardware acceptance ([evidence](builds/2026-10-27-recovery/reference-catalogs-runtime-read-only-arm64-disposable.json)).
- [x] Keep private Gateway routes out of the versioned public OpenAPI and SDK
  generation path. The exporter now retains only policy-approved public GET
  reads and fails closed if a public operation is not a read. A regression
  checks the exported contract against the checked-in snapshot and asserts
  that private Baal governance operations are excluded. The public API, route
  policy, and governance-focused selections pass 39 tests. The broader Python
  SDK method/schema/gRPC selection passes 118 tests; JavaScript passes 56 and
  TypeScript passes 35, with both JS/TS packages building successfully. The
  generated Python/TypeScript public SDK files match the OpenAPI snapshot;
  Ruff, Python compilation, and schema parity checks pass. No provider or
  database was contacted ([exporter](../../scripts/export_public_api_openapi.py);
  [regression](../../tests/test_public_api_openapi.py)).
- [x] Validate retirement-certificate location references for `retirement_id`,
  `credit_id`, and `credit_batch_id` on Directus create/update; the shared
  credit-class reference remains global. Focused tenant-hook checks pass (21)
  and TypeScript checking passes.
- [x] Require UUID location scope for location-required strategy reports before
  database access while retaining network-scoped behavior. The regenerated
  inventory covers 94 report types and 167 query sites with no unresolved or
  bind-mismatch sites; the focused report selection passes 107 tests with four
  database-dependent skips.
- [x] Enforce the operating-pilot resource-category page response contract,
  binding location and requested pagination and checking ordering, continuation,
  and small-count suppression. The focused Gateway selection passes 15 tests.

The combined batch also passes Ruff, Python compilation, report-query inventory
validation, TypeScript checking, and `git diff --check`. The capability matrix
remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and now records
62 strict private Gateway response endpoints. No migration, database, provider,
candidate, or legacy service was used. Evidence:
[batch](builds/2026-10-28-recovery/kernel-directus-operating-report-contracts.json).
Checklist: 1,446 complete / 25 open; TODO: 153 checked / 16 open.
- [x] Validate the `revenue_event` sales and financial-transaction references
  against the event's location for create and update. Leave optional
  global-capable treasury/value-flow references unchanged pending an explicit
  cross-scope contract.
- [x] Require an explicit UUID location for direct forecast-report calls before
  cursor creation; report query inventory remains at zero unresolved or
  bind-mismatch sites.
- [x] Make malformed Python Directus error responses use the JavaScript SDK's
  stable `HTTP <status>` fallback rather than arbitrary response text; retain
  valid server messages and attached response metadata.
- [x] Add strict request-bound response validation for Delphi draft-study pages
  and suppress `has_more` when pagination cannot continue within the 10,000
  offset ceiling.
- [x] Validate the Comprehensive Status `crop_noi` section against the
  generator's exact nested projection and selected location; retain the
  sanitized section error contract and leave remaining section bodies pending
  audit ([holistic-wellbeing contract](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json)).
- [x] Validate `expense_event.farm_task_id` against the same location on Directus
  create/update; schema 061 and migration 361 establish the relationship.
- [x] Reject invalid, `all`, and multi-location IDs for direct climate-impact
  report generation before database/helper access; keep the shared protocol
  lookup unchanged.
- [x] Type the Comprehensive Status environmental section from its four
  explicit SQL projections, including PostgreSQL Decimal normalization and
  selected-location binding. Existing unfiltered lifecycle selection, ignored
  period arguments, and free-text notes/causes still need semantic review.

This batch passes 459 focused Python tests, 90 JavaScript tests, 24 Directus
tenant-hook tests, TypeScript builds/checks, Ruff, compilation, report-query
inventory validation, and diff checks. Evidence:
[parallel contract batch](builds/2026-10-28-recovery/kernel-parallel-tenant-report-sdk-contracts.json).

- [x] Reject malformed location UUIDs before cursor or analyzer access across
  eleven operations reports plus ecological-modeling, trophic-pyramid, and
  adaptive-stewardship reports.
- [x] Preflight location UUIDs before database setup for cooperative creation,
  credit enrollment listing, spreadsheet export, energy monitoring, digital
  finance, marketplace, extension, pest management, data governance, and
  optional farmer-identity location filters.
- [x] Enforce strict request-bound success projections for the private
  Governance tactical-item queue and Data Stream attestation read; align
  action-text bounds with migration 445.
- [x] Add read-only, grant-scoped Directus tenant handling for
  `digital_lego_usage`; unassigned/out-of-grant rows fail closed.
- [x] Regenerate report source and query-scope inventories after source-line
  changes from the report preflight guards.

This parallel batch passes 715 focused Python tests and 143 Directus extension
tests. Build/typecheck, Ruff, Python compilation, report inventories,
capability-matrix validation, and diff checks pass. Checklist: 1,487 complete /
25 open; TODO: 193 checked / 16 open. The matrix remains 67 rows (24
baseline-retained, 7 deployed, 36 prepared) with 75 strict private Gateway
response endpoints; the optional Directus adapter covers 28 location-scoped
collections. No database, provider, live Directus runtime, candidate, legacy
service, or live network was used. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-report-cli-gateway-directus-guards.json).

- [x] Reject malformed location UUID scope before cursor access across the 19
  remaining registered location-scoped report generators in Bio Factory,
  Liberation, Stewardship, Scaling, Wellbeing, and Core Environmental reports.
- [x] Add a strict request-bound OpenAPI/runtime response contract for the
  private operating-pilot own-resource-request history page, matching the
  migration 567/568 field bounds, item order, location, and continuation.
- [x] Audit the optional Directus adapter after adding `digital_lego_usage`;
  no further managed-read collection with direct location lineage is safe to
  add. Polymorphic approval, workflow-history, and file-like collections still
  need a verified source-lineage contract.
- [x] Regenerate report source and query-scope inventories after report guard
  changes shifted registered source locations.

The combined focused report and Gateway selection passes 712 Python tests
with 7 skips. Ruff, compilation, inventories, capability-matrix validation,
and diff checks pass. Checklist: 1,491 complete / 25 open; TODO: 197 checked /
16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared) with 76 strict private Gateway response endpoints; the optional
Directus adapter covers 28 location-scoped collections. No database, provider,
live Directus runtime, candidate, legacy service, or live network was used.
Evidence: [batch](builds/2026-10-28-recovery/kernel-parallel-report-gateway-acceptance.json).

- [x] Validate the private mobile-enrollment success payload, OpenAPI schema,
  one-time code bounds, and sanitized no-store failures
  ([evidence](builds/2026-10-29-recovery/mobile-enrollment-prefect-weather-contracts.json)).
- [x] Let Prefect composites skip default-off signed weather safely, while
  direct weather worker execution remains fail-closed
  ([same evidence](builds/2026-10-29-recovery/mobile-enrollment-prefect-weather-contracts.json)).
- [x] Verify migration 686 apply/replay preserves revenue rows and totals while
  suppressing a mismatched-location crop-cycle label
  ([evidence](builds/2026-10-29-recovery/revenue-stream-location-join-disposable.json)).
- [x] Verify the strict Delphi study-item response contract, including exact
  OpenAPI fields, request-bound location/study IDs, malformed-output rejection,
  NUMERIC(8,4) bounds, and 200/201 create/replay behavior
  ([evidence](builds/2026-10-29-recovery/delphi-study-item-response-contract.json)).
- [x] Publish and validate a strict response for authenticated
  `/api/health/services`; malformed probes fail with a generic no-store error,
  and authorization remains before dependency probing
  ([evidence](builds/2026-10-29-recovery/health-and-pest-projection-contracts.json)).
- [x] Replace the pest-trend and biocontrol report wildcards with exact
  migration-047 projections while preserving filters, binds, ordering, and
  report output ([same evidence](builds/2026-10-29-recovery/health-and-pest-projection-contracts.json)).
- [x] Skip weekly climate work before location fanout while the signed worker
  is default-off; keep the enabled and direct-worker boundaries intact
  ([evidence](builds/2026-10-29-recovery/climate-tco-sdk-parity.json)).
- [x] Replace the TCO wildcard with its exact migration-196 view projection,
  preserving filters, bind order, sorting, and serialized rows
  ([same evidence](builds/2026-10-29-recovery/climate-tco-sdk-parity.json)).
- [x] Align Python REST SDK timeout bounds to JavaScript and reject finite
  oversized values before networking
  ([same evidence](builds/2026-10-29-recovery/climate-tco-sdk-parity.json)).

## Code work to continue without owner input

Work in this order. Each item is a bounded implementation batch, not a claim
that its full source-plan phase is complete.

- [ ] **C1 — Replace broad runtime database privileges with scoped contracts.**
  Initial pre-provisioning inventory remains a historical baseline: 1,101
  relations had runtime DML and RLS disabled. The latest native, network-
  disabled replay applies all 672 ordered schema files through migration 681
  and passes the synthetic two-tenant/operator scope probe. It verifies 128
  declared controls (79 private relations, 46 mutation-denied relations, two
  append-only relations, plus the API-key column boundary), with zero direct
  table/column privilege violations. The observed report still has 992
  relations with effective DML while RLS is disabled, so broad runtime access
  and universal application tenant isolation remain open. ARM64/QEMU now also
  replays all 675 schema files through migration 684 under network-disabled
  1.5 GiB/two-CPU limits, with zero pending/failed files and cleanup complete.
  That run did not execute the optional operator-scope probe; it is
  schema/portability evidence only, not ARM64 ACL-probe or physical Raspberry
  Pi evidence.

  Migrations 676 and 677 keep governed `reference_class` and seeded
  `farmer_credential_type` guidance readable but immutable to
  `kokonut_runtime`; source review found prediction readers but no reference-
  class writer, and credential records keep their type as free text. Both
  migrations and role provisioning preserve the separate Directus/admin grant
  path. Migration 678 applies the same boundary to schema-defined
  `market_reference_data` commodity and unit labels; source inventory found no
  application writer, and separate Directus/admin grants remain intact. Native
  and ARM64/QEMU disposable ACL checks pass apply/replay, table
  and residual-column denial, provisioner reapplication, and Directus-grant
  preservation. Migration 679 applies the same runtime-only read boundary to
  schema-seeded `quantity_unit` labels; source review found no application SQL
  writer or relation reader, and native/ARM64 checks pass with Directus grants
  preserved. Migration 680 adds a narrowly supported read-only boundary for
  `yield_benchmark`: one location-scoped analytics reader and no application
  write path were found; its DML is denied to `kokonut_runtime`, while the
  optional Directus role remains unchanged. This does not establish RLS or
  tenant isolation. The conservative SQL inventory now records 4,960 execution
  sites across 984 files, 1,243 relation candidates, and 587 write-target
  relations. It resolves 51 SQL templates stored in one unambiguous local
  assignment and eight same-module constants with an unambiguous immutable
  binding; dynamic identifiers, reassigned variables, and ambiguous/helper
  expressions remain unresolved. It surfaced `service_registry` INSERT/UPDATE
  in `services/analytics/service_catalog.py`; repository search found no
  internal API, CLI, SDK, or scheduled caller, but the public helper and
  bootstrap/catalog ownership still need reconciliation, so grants remain
  unchanged. `process_benchmark` has no repository reader/writer, seed, or
  Directus rule; its location-linked schema does not establish immutability or
  exclude external imports, so grants also remain unchanged. The
  `farm_task_framework_step` relation is an operational many-to-many edge with
  cascades and no direct location key; historic reconciliation found 20
  unresolved scope edges among 41 links, and the owner deferred those links.
  A separate unresolved-write review ledger now tracks 39 existing candidates
  (eight unresolved direct DML targets and 31 conservative `WITH` statements).
  Its legacy fingerprint set is pinned in source. Scope-AST fingerprints and
  per-scope ordinals catch same-scope source-binding edits and distinguish
  duplicate calls; hosted `ci-check.sh` invokes the inventory gate and fails
  when a new candidate lacks reviewed metadata that explicitly disclaims ACL
  approval. Thirty-four scanner tests pass. Parameter, import, mutable-global, and helper-provided values
  remain beyond fingerprint reach. This is source drift detection only: it
  does not change grants, classify existing debt as safe, or establish
  tenant isolation
  ([evidence](builds/2026-10-28-recovery/runtime-sql-unresolved-write-drift-gate.json)).
  It cannot be treated as a static catalog. A follow-up source audit also
  reviewed the seed-managed `sdg`, `pillar_of_value`, `form_of_capital`, and
  `regeneration_principle` tables. Repository code reads these labels but does
  not write them outside the seed; however, their Kokonut-specific definitions
  may be intentionally owner-customizable, and `sdg` has signed-worker RLS
  policy. They remain review candidates rather than safe runtime revocations
  until the management path and ownership are confirmed. These are
  heuristic/source audits, not proof that external writes are absent or
  tenant-authorized. The three pest-reference catalogs also have service
  writers reachable from the pest-management CLI; their runtime DML remains
  part of current customization behavior, so no read-only migration is safe
  ([audit](builds/2026-10-28-recovery/pest-reference-runtime-write-audit.json)).
  Migration 681 now applies a narrow read-only boundary to
  `metric_definition`: its 25 service SQL sites across 15 files are reads,
  while curated changes remain on the admin seed/migration path. It revokes
  table and residual column mutation/reference privileges, restores SELECT,
  and preserves the separate Directus role. Runtime provisioning reapplies
  the boundary after compatibility grants. The disposable PostgreSQL 16
  acceptance applies/replays the migration, reads a synthetic definition,
  rejects writes and residual privileges, and verifies Directus grants remain
  unchanged. The harness covers 127 synthetic relations (79 private, 46
  mutation-denied, two append-only); this does not establish RLS or tenant
  isolation. The fresh native full-schema ACL replay now reaches migration 681
  ([migration](../schemas/postgres/681_runtime_metric_definition_read_only.sql);
  [focused acceptance](builds/2026-10-28-recovery/runtime-scoped-write-boundary-disposable.json);
  [full-schema replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json)).
  The source review found
  dynamic curriculum definitions in `competency_framework` with no source-owned
  management contract; its grants remain unchanged until the Gateway or
  optional Directus administration path is explicit. Other unresolved
  candidates include dynamic configuration/retention registries and
  `process_benchmark`, `farm_task_framework_step`, and governed reference data
  without complete caller/consumer ownership proof. Review remaining callers
  and management paths before changing grants. Do not blanket-revoke based on
  static absence. A 28 October follow-up also found that `app_role` has only a
  read callsite in the source inventory, but it stores application
  authorization data and its editor/consumer ownership is unknown; it is not a
  safe revoke candidate without that reconciliation. Preserve rollback and
  distinguish table grants from RLS, worker, Directus, and production
  enforcement. A fresh source audit also examined `consent_data_type`: although
  no application callsite or Directus hook/permission seed uses it and the
  runtime currently has DML with RLS disabled, schema 148 reseeds rows with
  `ON CONFLICT DO UPDATE` and migration 401 changes retention fields. Its Data
  Governance/Consent ownership means this is not a safe fixed-catalog revoke
  without owner confirmation. A second audit rejected
  `bio_ingredient_composition_reference`: its status lifecycle and explicit
  agent-write allowlist contradict an immutable-catalog assumption, and
  Directus/admin mutation paths are not proven absent. No migration was added.
  The current report shows
  245 unprotected DML relations without an inventoried callsite and 420 without
  an inventoried write-target site; the report does not include all Directus,
  external, ownership, security-definer, column-ACL, or populated-runtime paths.
  Trace signed-context/write boundaries for the remaining 281 analytics and 25
  credit-class write-target relations, then reconcile unlocated Directus and
  external callers before selecting further revocations. The first credit-
  class trace found gRPC `CreateBatch` accepts a global
  `ecocredit:batch:write` API-key scope and writes a caller-supplied location
  without signed tenant context; the SQL setter supports exact-location grants
  but this RPC is not wired to it. Other credit-batch writers and the lack of
  active-client/API-key inventory mean changing this path or revoking runtime
  DML could break deployed clients, so no code change is safe until the
  contract is reconciled.
  Sources: [runtime boundary](batches.md#c1-market-reference-catalog-acl--28-october-2026),
  [full native schema replay through 681](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json),
  [ARM64 schema replay through 684](builds/2026-10-29-recovery/arm64-resource-limited-schema-684.json),
  [market-reference ACL](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-arm64-disposable.json),
  [quantity-unit ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-arm64-disposable.json),
  [analytics candidate inventory](builds/2026-10-28-recovery/analytics-runtime-write-candidate-inventory.json),
  [local SQL template resolution](builds/2026-10-28-recovery/runtime-sql-local-query-resolution.json).
  The refreshed ACL report observes the full schema and source policy through
  migration 681, including the `metric_definition` read-only boundary. It
  records 128 migration-backed controls and 992 relations retaining DML while
  RLS is disabled; external writers, populated tenant isolation, and
  production state remain outside the report
  ([report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json)).
  After migrations 682–683, the documented disposable runtime-role check also
  passes against the current provisioner: it reapplies the role boundary after
  compatibility grants and preserves 79 private, 47 mutation-only, and two
  append-only controls across 128 synthetic tables. This check does not install
  the source migration chain or exercise bounded Gateway functions; the full
  schema replay evidence remains through migration 681, and tenant isolation
  remains open ([check](builds/2026-10-28-recovery/runtime-scoped-write-boundary-disposable.json)).
- [ ] **C2 — Finish Gateway and SDK contract parity.** Audit registered routes,
  auth/action/scope policy, pagination, error models and SDK behavior; close
  source-verifiable gaps without exposing generic CRUD or weakening default
  denial. The public OpenAPI exporter now excludes private policy routes and
  allows only public GET/read operations in the generated contract. Python and
  TypeScript report and export SDK surfaces now expose read-only collection
  methods. Attestation records likewise remain read-only projections of
  governed workflow and indexed chain state; dedicated EAS workflows retain
  publication and revocation. Calculated NOI snapshots also expose read-only
  SDK methods; reconciliation remains in service/worker paths. Typed list
  accessors now share arbitrary Directus query extensions; Python detail reads
  also preserve explicit `fields=[]` like the pinned TypeScript transport. The
  TypeScript `ReportSnapshot` model now matches canonical SQL and Python. A
  further audit found no additional static SDK mismatch across the 109-model/
  2,150-column check and 15 method/public API tests. Parallel route work now
  aligns service-backed pagination bounds across 32 Gateway list families,
  including all 25 solution-lifecycle routes and 21 operating-pilot routes;
  invalid paging fails before readers run. The expanded changed-route and
  operator integration selection now passes 732 tests, including the Delphi
  participant workspace and six operator list routes. The additional
  data-stream attachment route now publishes `limit=1..100` and
  `offset=0..5,000`; its focused Gateway/auth selection passes 52 tests.
  The public federation-node route now uses `limit=1..100` and
  `offset=0..10,000`; its `nodes` payload now includes exact continuation and
  offset-ceiling metadata, with 36 focused route/error-redaction checks passing.
  The trusted CLI retains its full-list behavior. Data-stream post lists now publish `limit=1..100`
  (default 20) and `offset=0..5,000` (three route checks); Baal proposal lists
  publish `limit=1..100` (default 50) and reject invalid values before reading
  (26 governance checks). The JavaScript SDK now has the Python client's default
  10-second deadline; `timeoutMs` accepts only finite values in the timer-safe
  range 1..2,147,483,647, and explicit `null` is rejected. This prevents Node's
  overflow clamp from aborting a request after 1 ms. Fake-timer coverage checks
  success, rejection, timeout, and cleanup; 18 JavaScript tests, 8 Python
  tests, and the TypeScript build pass. The credit-custody summary now has an explicit response model
  matching its existing service fields; seven focused checks pass and auth
  behavior is unchanged. A fresh list-route sweep found the pollution-incident
  queue is already capped at 100 rows and exposes its bounded offset; it has no
  configurable limit, so no new parameter was invented. Produce traceability
  list/detail reads now have explicit strict response models derived from their
  service projections and schema enums; the models exclude actor names/IDs,
  GPS, notes/reasons, evidence URLs, and arbitrary JSON. Eleven focused checks
  pass while auth and no-store error behavior stay unchanged. Authorization
  parity, authenticated live runtime behavior, and broader SDK route/auth
  runtime parity remain open. The OIDC location-attestation list now has a
  strict 100-record OpenAPI/runtime response model that preserves its current
  payload and `no-store`/`Vary: Cookie` headers while excluding claim, evidence,
  and reviewer data; the focused route selection passes 20 checks
  ([model evidence](builds/2026-10-28-recovery/attestation-response-model-contract.json)).
  The detailed `/api/health/services` route now requires `service_health:read`
  before it probes optional infrastructure; anonymous access is denied while
  public `/health` liveness remains available. Two focused auth/policy checks
  pass ([evidence](builds/2026-10-28-recovery/detailed-health-route-auth-boundary.json)).
  The ecocredit batch list now also has a strict bounded response contract that
  excludes undeclared service fields while preserving tenant authorization and
  cache headers; 13 focused route/OpenAPI tests pass
  ([evidence](builds/2026-10-28-recovery/ecocredit-batch-response-contract.json)).
  The operating-pilot capacity review and solution scale-gate target routes
  now validate exact migration-backed projections, request location and page
  bounds, ordering, and domain invariants before returning. Report export
  status, detail, and artifact reads are restricted to the original signed-in
  requester even when another operator shares the location; source candidates
  remain location-shared. Migrations 683–685 pass isolated PostgreSQL 16
  replay and requester-isolation checks. Python SDK integer response fields
  now accept finite integral JSON numbers and reject booleans/fractions, in
  parity with JavaScript. The combined Gateway, SDK, export and related
  regression selection passes 480 tests
  ([batch evidence](builds/2026-10-29-recovery/kernel-next-contract-batch.json);
  [migration evidence](builds/2026-10-29-recovery/report-snapshot-export-migration-disposable.json)).
  The public location IRI resolver now validates its exact JSON-LD document,
  canonical same-location predecessor version, and public-projection digest;
  OpenAPI advertises the `application/ld+json` schema and malformed documents
  fail closed with a sanitized no-store error. Thirteen focused resolver tests
  pass ([evidence](builds/2026-10-29-recovery/public-location-iri-jsonld-response-contract.json)).
  The Data Stream draft-create route now has a strict allowlisted request and
  UUID-only response schema. The 15 accepted post types are checked against
  the domain service; creator/lifecycle/metadata/source fields are rejected
  before writes, and request validation is sanitized/no-store. Thirty-nine
  focused route/auth checks pass
  ([evidence](builds/2026-10-29-recovery/data-stream-create-gateway-contract.json)).
  Python SDK timeouts now reject boolean, nonnumeric, non-finite, nonpositive,
  and overflow-sized values before networking while preserving the 10-second
  default; 17 focused tests pass
  ([evidence](builds/2026-10-28-recovery/sdk-python-public-api-timeout-parity.json)).
  The enabled driver catalog now also has a versioned `/api/v1/drivers`
  contract with generated typed Python/TypeScript clients, bounded pagination,
  and a generic no-store 500 on registry failure; it no longer reports a false
  empty page. The 47-test Gateway/OpenAPI/Python-SDK selection and full 73-test
  JavaScript SDK suite pass ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
  The private cooperative summary now publishes a strict OpenAPI success
  model and validates the projection before returning its raw response; its
  ten-test selection covers undeclared fields and preserved error/cache
  contracts ([evidence](builds/2026-10-28-recovery/cooperative-summary-response-contract.json)).
  The yield-monitoring summary now has the same explicit boundary for its
  grouped aggregates and bounded recent-harvest projection; fourteen route
  tests verify its OpenAPI schema, malformed-field rejection, and unchanged
  authorization/error headers
  ([evidence](builds/2026-10-28-recovery/yield-summary-response-contract.json)).
  The coordination-governance summary now publishes its migration-458 schema
  with 19 strict nonnegative counts; 16 route tests cover projection, OpenAPI,
  and existing auth/error/cache behavior
  ([evidence](builds/2026-10-28-recovery/coordination-governance-response-contract.json)).
  The emergency-response summary now publishes bounded aggregate models with
  schema-backed incident/severity enums, strict counts and percentages, and
  sanitized failure for invalid projections; 18 route tests preserve its
  existing authorization/error/cache behavior
  ([evidence](builds/2026-10-28-recovery/emergency-response-summary-contract.json)).
  Comprehensive Status validates its one-location envelope and exact canonical
  section set, with strict typed success/error contracts for all 14 sections.
  Farm and plot geometry is projected as GeoJSON, with Polygon/Point structure
  and the farm/plot/crop-cycle location hierarchy validated at the Gateway. The
  environmental model binds its four explicit SQL arrays to the enclosing
  location and accepts PostgreSQL Decimal values; the holistic section derives
  exact row contracts from three consent/publication-filtered views. Stakeholder
  outcomes retain their verified/published filter and location binding. Training
  sessions retain their verified/published public-view projection, exact location,
  and generator aggregate math; its selection covers nullable scores and Decimal
  half-even rounding. Capital accounting preserves all four partial-failure
  sections, exact location/period and derived-field parity, advisory-only
  status, and a draft-only credit ledger. The combined farm-summary and
  Comprehensive Status route selection passes 145 tests
  ([holistic evidence](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json);
  [stakeholder evidence](builds/2026-10-29-recovery/comprehensive-status-stakeholder-outcomes-contract.json);
  [training evidence](builds/2026-10-29-recovery/comprehensive-status-training-impact-contract.json);
  [capital evidence](builds/2026-10-29-recovery/comprehensive-status-capital-accounting-contract.json);
  [GeoJSON evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).
  Training records still expose participant names, trainers, and notes under the
  legacy public view; strict shape validation does not settle content privacy or
  broader-stakeholder disclosure.
  The farm-summary queries use explicit current-schema projections and strict
  nested models. PostGIS geometry is now emitted as GeoJSON rather than raw
  driver values, and returned farms, plots, and crop cycles are cross-checked
  against the selected location hierarchy. Nested JSONB metadata and assumption
  fields remain flexible because their schema explicitly defines them as JSON.
  The remaining semantic issue is that legacy
  `financial_transaction` has no lifecycle/status column while `expense_event`
  includes only verified/published rows. Do not infer a financial inclusion
  policy or add a filter without reconciling the source lifecycle. The original envelope
  selection has 20 route tests
  ([evidence](builds/2026-10-28-recovery/comprehensive-status-response-contract.json)).
  Energy monitoring validates nested source, renewable, efficiency, and cost
  aggregates against schema values and query bounds; 23 route tests include
  request-location matching ([evidence](builds/2026-10-28-recovery/energy-summary-response-contract.json)).
  True-cost validates all six nested aggregate sections, schema categories,
  finite numeric values, extra-field rejection, and request-location matching;
  12 route tests pass ([evidence](builds/2026-10-28-recovery/true-cost-summary-response-contract.json)).
  Business architecture now validates mission/mapping fields, schema enums,
  nullability and page continuation; 31 route/pagination tests pass
  ([evidence](builds/2026-10-28-recovery/business-architecture-summary-response-contract.json)).
  Extension learning now validates both the module catalog and its aggregate
  summary, including enum-derived bounds and requested location identity; 20
  route/pagination tests pass
  ([evidence](builds/2026-10-28-recovery/extension-learning-response-contract.json)).
  Waste management now validates all nested summary sections, domain enums,
  count/finite-number rules, period and location identity; 22 route tests pass
  ([evidence](builds/2026-10-28-recovery/waste-summary-response-contract.json)).
  Export-log fields
  match the canonical table; the earlier pending-
  create API was removed because the table lacks its request fields and no
  worker consumes pending rows. Report snapshots remain generated by the
  exporter and preserve governed lifecycle through review surfaces. Gateway-
  backed export requests and broader route/SDK parity remain open. The private
  mobile-disposition inventory now has a strict nested success model, request
  collection/location binding, count invariants, and sanitized no-store failure
  behavior; 13 focused Gateway/auth checks pass. Strict response contracts now
  cover public Delphi participant invite preview, consent acceptance and
  withdrawal, questionnaire contribution, and minority-report submission.
  Operator invite issue/revoke routes now also validate strict OpenAPI/runtime
  contracts, including first-issue versus replay token behavior and path binding;
  45 focused checks pass ([evidence](builds/2026-10-29-recovery/delphi-operator-invite-response-contracts.json)). A strict
  private coaching-session create response now binds its exact location,
  lifecycle, date and replay fields and distinguishes HTTP 201 creation from
  HTTP 200 replay; 19 focused route checks pass
  ([evidence](builds/2026-10-29-recovery/operating-pilot-coaching-create-response-contract.json)). The capacity-profile draft create response binds location, enforces
  source-defined lifecycle values, and distinguishes 201 creation from 200
  replay; 20 focused checks pass
  ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-draft-create-response-contract.json)). The revision response binds old and replacement profile IDs
  and location, requires a new draft on first write, and preserves HTTP 200;
  12 focused checks pass
  ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-draft-revision-response-contract.json)).
  The capacity submit and independent-review routes now also expose strict
  response models, bind location/profile IDs, enforce first-write lifecycle
  and decision/status invariants, and sanitize malformed output; 25 focused
  checks pass ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-submit-review-response-contracts.json)).
  The demand draft create/revise/submit/review routes now enforce the same
  response boundary with migration-defined terminal replay states; 28 focused
  checks pass ([evidence](builds/2026-10-29-recovery/operating-pilot-demand-lifecycle-response-contracts.json)).
  Resource-request create/revise/submit/review routes now also validate exact
  migration-backed responses and path identities; 27 focused checks pass
  ([evidence](builds/2026-10-29-recovery/operating-pilot-resource-lifecycle-response-contracts.json)).
  Sources:
  [API/SDK gates](batches.md#L3226),
  [Phase 7](implementation-plan-alignment.md#L27).
- [x] Add strict OpenAPI/runtime contracts for Delphi participant invite
  preview, consent acceptance/withdrawal, questionnaire contribution, and
  minority-report submission; reject extra service fields.
- [x] Validate consent/session timestamps and lifecycle states, bind the
  contribution item to its request, and preserve cookie/replay behavior.
- [x] Add/run mock-only route checks for exact response fields, OpenAPI,
  malformed-result sanitization, no-store headers, and acceptance cookies
  ([evidence](builds/2026-10-29-recovery/delphi-participant-write-response-contracts.json)).
- [x] Declare strict operator invite issue/revoke response schemas and bind
  returned location, study, and invite identities to the route.
- [x] Preserve one-time token semantics: return only on first issue and null
  on request replay; require `revoked` on the revoke result.
- [x] Add/run 45 focused mock-only operator invite route checks for OpenAPI,
  exact fields, path binding, replay behavior, and sanitized failures
  ([evidence](builds/2026-10-29-recovery/delphi-operator-invite-response-contracts.json)).
- [x] Add a strict private coaching-session create response contract with
  request-location binding and source-defined private/completed state.
- [x] Return HTTP 201 for creation and 200 for idempotent coaching replay;
  reject malformed private-session output with a sanitized no-store response.
- [x] Add/run 19 focused mocked route/OpenAPI checks for coaching response
  fields, location, lifecycle, date, replay, and malformed output
  ([evidence](builds/2026-10-29-recovery/operating-pilot-coaching-create-response-contract.json)).
- [x] Declare and validate the capacity-profile create response against its
  migration-defined lifecycle and bind returned location to the route.
- [x] Preserve 201 new-draft / 200 replay statuses and sanitized no-store
  handling for malformed create results.
- [x] Add/run 20 focused mocked route/OpenAPI checks for exact fields, status,
  location, replay, and malformed service output
  ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-draft-create-response-contract.json)).
- [x] Add the strict capacity-draft revision response with request-bound
  location and replaced profile, distinct replacement ID, and draft-only
  first-write invariant.
- [x] Preserve existing lifecycle state on replay and keep revision PUT at
  HTTP 200; sanitize malformed output.
- [x] Add/run 12 focused mock-only route/OpenAPI checks for binding, lifecycle,
  replay, and sanitized failures
  ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-draft-revision-response-contract.json)).
- [x] Verify generated OpenAPI and Python compilation for the capacity revision
  response model; preserve HTTP 200 and no-store failure behavior.
- [x] Declare strict capacity submission and independent-review responses with
  path-bound location/profile IDs and source-defined lifecycle/decision rules.
- [x] Preserve current lifecycle on exact submission/review replay and return
  sanitized no-store failures for malformed service output.
- [x] Add/run 25 focused mock-only route/OpenAPI checks for both responses,
  replay, path binding, and malformed results
  ([evidence](builds/2026-10-29-recovery/operating-pilot-capacity-submit-review-response-contracts.json)).
- [x] Declare strict demand create, revision, submission, and review responses;
  bind returned location/signal identities and preserve source lifecycle states.
- [x] Align the demand-create OpenAPI success status with its existing HTTP 201
  runtime response; constrain replay and review invariants.
- [x] Add/run 28 focused mock-only route/OpenAPI checks for exact output,
  terminal replay, binding, and sanitized failures
  ([evidence](builds/2026-10-29-recovery/operating-pilot-demand-lifecycle-response-contracts.json)).
- [x] Add strict resource-request create, revision, submission, and review
  response models with path-bound identities and lifecycle/decision limits.
- [x] Match the documented resource-create HTTP 201 status to runtime behavior
  and preserve exact idempotent response semantics.
- [x] Add/run 27 focused mock-only route/OpenAPI checks for the four routes,
  replay, path binding, and sanitized failures
  ([evidence](builds/2026-10-29-recovery/operating-pilot-resource-lifecycle-response-contracts.json)).
- [ ] **C3 — Finish the optional Directus adapter boundary.** Close code-verifiable
  role, field, row and hook gaps for collections still retained; keep native
  farm activity in Gateway. Workflow-role authorization cache freshness is
  fixed; a source audit found unfiltered reads for `workflow_history` and
  `approval` without tenant-scoped hooks. These permissions also expose wildcard
  fields, including notes and rejection reasons. A source-only aggregate
  preflight now maps 24 direct-location sources plus the explicit protocol
  intent-to-location relation, sanitizes unsupported collection names, and
  emits no row identifiers or contents. Eight offline tests pass. Its
  disposable schema check replayed all 671 schema migrations through migration
  680, found all 29 required relations and 60 columns, and executed both queries
  in a read-only repeatable-read transaction. The empty database returned no
  historical rows; it does not prove populated lineage or effective Directus
  permissions. Select a populated read-only copy and inspect aggregate
  unresolved/unsupported counts before designing tenant filters. Avoid
  revoking an existing operator feature based on schema-only evidence. Record
  surfaces that cannot be proven without a live runtime separately. Tenant
  reads now also reject relationship traversal in filters, `_some`/`_none`,
  sorting, and grouping until the related collection has a tenant contract;
  scalar/logical filters and JSON containment remain supported. The focused
  hook suite passes 12 tests and the TypeScript check. This closes the
  source-level relation-query oracle but does not prove live API permissions
  or populated-row parity
  ([evidence](builds/2026-10-28-recovery/directus-relation-query-boundary.json)).
  The known writable-reference lookups now carry the requested location and
  return the same unavailable error for missing and foreign valid UUIDs; 14
  focused predicate/non-disclosure tests and the extension build pass
  ([evidence](builds/2026-10-28-recovery/directus-tenant-reference-nondisclosure.json)).
  A follow-up audit confirms the typed direct-location references now have
  explicit validators, including the recent MRV sensor-device and sensor-alert
  mappings; polymorphic `source_record_ids` remains unresolvable without a
  discriminator. A 28 October collection audit found no further safe managed
  read candidate with direct location lineage: all such collections are in the
  28-collection adapter. `approval`, `workflow_history`, and file-like reads
  still rely on polymorphic source links without a verified tenant join. No
  further safe field mapping was found. Pinned-runtime permissions and
  populated-row parity remain open. The Auditor now has a read-only,
  location-hook-scoped retirement-certificate projection with an explicit
  allowlist; user-authored reason text, private rendered-content hash,
  beneficiary fields, HTML and metadata are excluded. The permission seed
  repairs any prior field selection to this allowlist. Source inventory now
  records 176 permission declarations, including 54 explicit-field rows; it
  does not prove effective deployed permissions
  ([inventory](builds/2026-10-29-recovery/directus-permission-auditor-certificate-source.json);
  [batch checks](builds/2026-10-29-recovery/kernel-next-contract-batch.json)).
  Sources:
  [Directus parity](batches.md#L2117),
  [preflight](directus-polymorphic-lineage-preflight.md),
  [transport/Directus gates](batches.md#L3320).
- [ ] **C4 — Port repository-defined provider jobs and workflows.** Compare each
  source module against the owned scheduler/job contract, add missing adapters
  and operator controls, and keep external schedules disabled until ownership
  and active state are reconciled. The 23-entry catalog matches its generated
  contract, and five Prefect deployments use catalog-backed pipelines; the
  legacy health-check flow is undeployed and weather-forecast remains
  default-off. The signed forecast worker now consumes its dedicated
  `KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY`, routed through standard
  and portability Compose profiles; live provider/scheduler acceptance remains
  open ([evidence](builds/2026-10-28-recovery/weather-forecast-provider-key-routing.json)).
  A source audit of climate ingestion found manual dataset/UUID
  preflight and the scheduled location-bound default-off signed worker already
  align; its 174-test climate/CLI/scheduler selection passes without contacting
  a provider or database. No owner or production schedule was inferred.
  A follow-up inventory review found the legacy Yahoo price-feed flow is not a
  safe new JobSpec: it writes audit rows but no `price_observation`, reports an
  empty fetch as success, and its documented attestation step is never invoked.
  Defer registration until persistence/retry semantics and separate human
  attestation approval are defined ([audit](builds/2026-10-28-recovery/yahoo-price-feed-contract-audit.json)).
  A separate source review found the unmatched legacy health-check flow assumes
  the full legacy PostgreSQL/Directus/ClickHouse/Docker topology and has no
  Kernel scheduler CLI contract, so it also remains unregistered until a
  profile-aware health contract exists
  ([audit](builds/2026-10-28-recovery/prefect-health-check-contract-audit.json)).
  A new source audit also confirmed the 23-entry native job inventory already
  matches its generated contract. The legacy weekly flow claimed ML model
  retraining although the scheduled Prefect function only refreshed climate
  data; that description is corrected. The underlying legacy retraining path
  uses the shared database role and has no signed bounded task contract, so it
  remains unregistered pending an isolated design. No owner schedule was
  inferred. Location fan-out now rejects any required job inputs it cannot
  supply before querying owner locations; sensor fan-out clearly fails until a
  driver-instance mapping exists. Seven focused mocked checks pass without
  database/provider access ([batch evidence](builds/2026-10-29-recovery/kernel-next-contract-batch.json)).
  A further source audit found composite analytics and six-hour Prefect flows
  still dispatch the legacy stored-SQL dashboard job when its feature is off
  by default. The composite paths now skip that stage with an explicit reason
  and continue credit/remote-sensing work; standalone refresh remains
  fail-closed. The same audit found the daily/integration composites invoked
  the default-off isolated market-data worker unconditionally; Prefect dispatch
  now reports an explicit skip until enabled, with direct worker access still
  fail-closed. Focused workflow/worker tests pass 30 checks, and Prefect runtime
  acceptance passes five more through the approved host path. These slices
  remain open pending CI and completion of analytics acceptance.
  Sources: [provider/job inventory](batches.md#L2288),
  [worker recovery](batches.md#L2358).
- [ ] **C5 — Close source-verifiable analytics and reporting gaps.** Port
  registered queries/cards and deterministic projections, fix correctness and
  access gaps, and preserve ClickHouse as rebuildable optional projection.
  Direct report generators now reject missing location scope before database
  access, consistent with the registry and CLI; reviewed global rows remain
  visible only under a selected location, and unlineaged network rows are
  omitted from farm-scoped reports. The integrated report suite passes 563
  tests with four database-dependent skips. Its generated inventory records 94
  report types, 167 direct query sites, 166 positional-bind sites, and zero
  unresolved sites or bind mismatches. `climate_impact`,
  `revenue_multiplier`, `environmental`, and `ecological_modeling` also reject
  missing location before opening a cursor or starting the analyzer; focused
  selections pass 2, 125, 2, and 2 tests respectively. The EBF scorecard now
  rejects a missing/empty location before cursor creation; the focused source
  selection passes 324 checks. The inventory's 13 entries with no visible
  location-bound SQL signal were reviewed: twelve are deliberate network
  reports with explicit network-scope guards, and `business_plan` rejects
  missing scope while its all-location mode is intentional. Do not infer
  populated-farm parity from synthetic fixtures. Tactical-layer companion
  lookups now keep target threats within the selected location, and the
  State-of-Kokonut actor/funding sections filter all four queries to selected
  locations while rejecting empty selections; network-wide mode is unchanged.
  Their focused suites pass 73 and 285 tests respectively, with report
  inventory freshness checks ([tactical scope](builds/2026-10-28-recovery/tactical-layer-companion-location-scope.json);
  [State of Kokonut scope](builds/2026-10-28-recovery/state-of-kokonut-selected-actor-scope.json)).
  The latest source audit found remaining location-unfiltered report cases are
  explicit network/public projections, an explicit all-location operation, or
  stakeholder/global surfaces whose audience and scope cannot be safely
  changed without populated fixtures and owner review; no additional query
  change was selected. Ecological residual averages now exclude rows without
  measurements and weight only measured input mass in both report and analytics
  adapters. The focused report/analytics suite passes 56 tests, including mixed
  and all-unmeasured cases
  ([batch evidence](builds/2026-10-29-recovery/kernel-next-contract-batch.json)).
  A subsequent correctness audit found the weather-growth query summed harvest
  and rainfall after joining each harvest to every matching 30-day weather
  observation. The query now aggregates verified harvest totals and distinct
  matched weather observations separately, preserves the existing result grain
  and response shape, and excludes harvest/cycle location mismatches. A second
  audit found revenue and expense rows were joined directly at crop-cycle grain
  before both sums; the analytics query now aggregates each event family per
  eligible cycle first and rejects event/cycle location mismatches. Disposable
  PostgreSQL 16 acceptance now passes with synthetic rows: overlapping weather
  windows return 15 kg harvest, two events, three unique observations, 10 mm
  rainfall, and exclude mismatched event/cycle locations; revenue totals $300
  against $60 expense (400% ROI), with no-event cycles at zero and mismatched
  locations excluded. The analytics source slice is verified, while C5 remains
  open for broader parity and reporting work
  ([evidence](builds/2026-10-29-recovery/analytics-event-aggregation-disposable.json)).
  Completed source slices: stakeholder trust/identity readers now use exact
  migration-backed projections; pest-management and marketplace CLI date/JSON
  inputs fail before PostgreSQL access; the migration-517 configuration own-
  drafts queue now has a strict, location/page-bound Gateway and console
  contract with bounded continuation. These improve source contracts but do
  not close the broader populated-data reporting parity gate.
  - [x] Pin migration-222/227 stakeholder trust and identity-resolution read
    projections while preserving their current filters, order, payload, and
    access boundary.
  - [x] Preflight all pest-management CLI dates and marketplace harvest dates
    and buyer JSON objects before database acquisition.
  - [x] Validate the private migration-517 configuration own-drafts response
    and operator-console page, including ordering and the 10,000-offset cap.
  Sources:
  [report/query parity](batches.md#L2334),
  [consumer scope](batches.md#L3139).
- [ ] **C6 — Complete source-only capability slices.** Continue unresolved
  route, lifecycle, lineage, provenance and review functionality for CAP-035,
  CAP-036, CAP-037 and CAP-038 where code can be completed without populated
  farm records or production identity. The latest audit found no further safe
  independent source-only slice: CAP-035 sharing/tranche custody needs policy
  decisions; CAP-036 already excludes unscoped sensitive events and needs a
  populated/archived corpus to establish additional subject lineage; CAP-037
  has no identified first-party workflow gap; CAP-038 needs live identity and
  populated-source acceptance. Sources: [CAP-035](batches.md#L3484),
  [CAP-036](batches.md#L3574), [CAP-037](batches.md#L3582),
  [CAP-038](batches.md#L3652).
- [ ] **C7 — Finish software-only ARM64 and recovery evidence.** The latest
  ARM64/QEMU schema replay passes all 675 files through migration 684
  under a verified 1.5 GiB/two-CPU database budget. The network was disabled,
  no ports, seeds, or farm data were used, no OOM occurred, and cleanup passed.
  That replay did not enable its optional operator-scope probe. The native full
  replay through 681 separately passes the synthetic two-tenant/operator
  assertions; candidate and legacy state stayed untouched. Focused native and
  ARM64/QEMU ACL checks cover migrations 672–680. A separate
  network-disabled schema check replayed all 671 schema files through migration
  680 and executed both Directus lineage queries; this demonstrates SQL/schema
  compatibility only, not ARM64 behavior, populated lineage, RLS, or effective
  Directus permissions. Both Kernel app images and profile selections have
  ARM64 build and
  import evidence. This remains software-only evidence: no physical Raspberry
  Pi, populated data, external provider/media, R2, whole-platform production
  recovery, or 24-hour RPO/RTO drill has been accepted. The minimal Gateway
  startup was also exercised with optional analytics, ML, GIS, Web3, ClickHouse,
  Prefect, Redis/MQTT, gRPC, OIDC, and S3 libraries blocked; 16 routes loaded
  with no attempted or loaded optional imports, and dependency/provider checks
  passed. This supports the existing profile boundary but does not replace
  ARM64 image build/runtime or physical-device acceptance.
  The new opt-in `core` image uses an independent hash-locked dependency
  closure, with Web3, spreadsheet/S3, and local-media overlays. The multiarch
  release gate validates both core-only and all-overlays images for AMD64 and
  ARM64; local profile/import checks pass, while hosted CI remains pending.
  Existing full-capability profiles are unchanged, and core OIDC is rejected
  until that composition is implemented. The edge Compose profile also has an
  offline regression locking its declared 1 GiB/two-CPU app and database caps;
  this checks configuration only and is not physical Raspberry Pi runtime
  acceptance ([evidence](builds/2026-10-28-recovery/edge-compose-resource-contract.json)).
  Resource-limit preflight now also rejects a positive CPU value that rounds to
  zero nanocpus before creating a disposable database container; normal 0.5 and
  2 CPU conversions retain exact Docker units. The focused runner selection
  passes 26 tests ([evidence](builds/2026-10-28-recovery/arm64-resource-limit-nanocpu-preflight.json)).
  Sources: [Phase 8](implementation-plan-alignment.md#L28),
  [latest native full replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json),
  [ARM64 full replay](builds/2026-10-29-recovery/arm64-resource-limited-schema-684.json),
  [core profile](builds/2026-10-28-recovery/kernel-core-profile-contract.json),
  [multiarch profile gate](kernel-release-inputs.md),
  [migration 679 ARM64 ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-arm64-disposable.json),
  [build and profile evidence](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json),
  [recovery gates](batches.md#L2159).
- [ ] **C8 — Reconcile all ledgers after each batch.** Keep the sprint TODO,
  `batches.md`, `progress.md`, capability matrix and migration/evidence links
  consistent. Preserve the 25 open composite checklist entries until their
  individual acceptance criteria close.

### Current batch — parallel Kernel hardening — 28 October 2026

This batch closed ten checklist/audit items without changing capability
classifications: the metric-definition runtime ACL, ecocredit response
contract, Python SDK timeout preflight, Directus relation-query boundary,
legacy health-check flow audit, edge-profile resource regression, detailed
health-route authorization, forecast-worker provider-key routing, runtime ACL
report provenance, and the next-catalog source review. The combined
Gateway/report selection passes 385 tests; Directus passes 12 focused tests
and TypeScript; the Python SDK passes 17 tests; the edge profile check passes
one test. The disposable PostgreSQL 16 role-boundary harness passes migration
681 apply/replay and verifies runtime read-only behavior plus preservation of
Directus grants. The full schema/ACL report remains through migration 679, and
no candidate or legacy database was changed.

This batch also protected `/api/health/services` behind `service_health:read`
while keeping `/health` public, fixed dedicated forecast-worker provider-key
routing, and corrected ACL-report provenance so migration-679 observations
are not confused with migration-681 policy. The TypeScript client is gRPC-only;
REST deadline parity does not justify imposing a default deadline on streaming
or long-running gRPC calls. The C5 re-audit found no additional safe
selected-location leak outside the report fixes already closed. C4 confirms the
legacy health-check flow is not profile-independent and remains unregistered.
C6 found no further source-only capability change that avoids populated data,
live identity, or owner decisions. The next C1 candidate,
`competency_framework`, remains unchanged pending its curator and supported
administration path. The C1 migration is a relation-specific DML restriction;
it does not establish RLS or tenant isolation. Checklist: 1,377 complete / 25
open (1,402 total);
the matrix remains 24 baseline-retained, 7 deployed, and 36 prepared across
67 rows. MAN-CAP acceptance is unchanged.

### Completed continuation — Gateway response and SDK catalog contracts — 28 October 2026

The private farm-activity summary routes, pollution incident resolution, and
governance-tension detail now validate their exact source projection and
request scope before returning a response. The native Python and JavaScript
REST SDKs now validate the public driver catalog against its generated bounds,
enum, and exact fields. The 92-test Python selection and 38-test JavaScript
selection pass; TypeScript build, Ruff, Python compilation, and diff checks
pass. The matrix records 61 strict private Gateway response endpoints across
67 capabilities (24 baseline-retained, 7 deployed, 36 prepared). No migration,
database, provider, candidate, or legacy service was used. See
[evidence](builds/2026-10-28-recovery/kernel-gateway-sdk-contract-batch.json).

Checklist: 1,446 complete / 25 open (1,471 total); TODO: 153 checked / 16 open.
MAN-CAP acceptance and capability classifications are unchanged.

## Owner or environment gates after code work

- [ ] **H1 — Live ZITADEL login:** confirm issuer discovery, provision/register
  the OIDC client and callback, create the test operator, supply generated
  secrets through SOPS, and run trusted-HTTPS browser login/session/logout and
  scoped-grant acceptance. Startup/discovery alone is complete.
  Source: [identity follow-up](open-follow-ups.md#L28).
- [ ] **H2 — Browser trust:** trust the local development CA or provide an
  approved certificate before Caddy HTTPS browser acceptance. Never bypass the
  browser warning. Source: [certificate follow-up](open-follow-ups.md#L32).
- [ ] **H3 — Populated data and report review:** ingest the owner-held Genesis,
  Seeds, Adelphi and V1 records, then compare repository-backed outputs and
  review access with the intended stakeholder audience. Terra Viva follows its
  design phase. The intended audience is not blanket authorization.
  Sources: [data follow-up](open-follow-ups.md#L40),
  [report owner review](batches.md#L2356).
- [ ] **H4 — Retention operations:** accountable owners configure dynamic
  purpose-specific periods, archive access, legal holds and erasure/disposition
  approval before any pruning is enabled. Do not hardcode a universal period.
  Source: [retention follow-up](open-follow-ups.md#L19).
- [ ] **H5 — External delivery and storage:** provide alert recipient/severity
  routing/on-call ownership; provision R2 access for the reviewed test prefix
  and rehearse restore before production backup claims. Source:
  [delivery](open-follow-ups.md#L21), [R2](open-follow-ups.md#L29).
- [ ] **H6 — Production topology and recovery:** supply trusted proxy hops,
  TLS, RPO and topology details; run the 24-hour recovery and scale check when
  the production target can be scheduled. Replicas/failover remain deferred
  until production. Sources: [topology](open-follow-ups.md#L22),
  [timed acceptance](batches.md#L3343).
- [ ] **H7 — Physical device check:** if a Raspberry Pi becomes available,
  measure power-loss, thermal, storage and device restart behavior. Until then,
  report software ARM64 evidence only. Source: [physical acceptance](batches.md#L2012).
- [ ] **H8 — Release and cutover:** obtain green required CI/Security checks on
  the exact PR head and perform the already-approved cutover only after all
  readiness gates pass. Protocol Bridge work remains deferred by owner request.
  Sources: [CI](batches.md#L3396), [cutover](batches.md#L3399).

## Working cadence

Implement C1–C8 in coherent local commits on the current feature branch. Group
pushes into reviewable PR batches targeting `develop`, as requested by the
owner. Do not mark a release/cutover gate complete from local source checks,
emulation, internal OIDC discovery, or synthetic-only parity.

### Previous continuation — C1 versioned graph type boundary

Migration 661 makes the versioned `graph_node_type` and `graph_edge_type`
registries read-only to `kokonut_runtime`; source review found their only
definitions in migration 173, while runtime projection code writes graph
generations and materialized nodes/edges. Native and ARM64/QEMU focused ACL
checks pass for apply/replay, read access, mutation/reference denial, stale
column-grant cleanup, and provisioner reapplication. The focused migration,
role, report, ARM64-contract, and migration suite passes 122 tests; Ruff,
dependency/provider boundaries, and SQL inventory checks pass. The static
report now declares 105 boundaries with no mapping gaps. The focused checks
were followed by a complete ARM64/QEMU replay through migration 662; the later
probe verifies all 106 declared boundaries on the full chain. Disposable checks
used no seeds or farm data and did not touch candidate/legacy databases.
Broader runtime DML/RLS boundaries and physical Raspberry Pi acceptance remain
open ([full-chain evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json)).
Checklist: 1,264 complete / 26 open (1,290 total). Capability
classifications remain 24 baseline-retained, 7 deployed, and 36 prepared
across 67 rows.

### Current continuation — C1 capability audit ledger boundary

Migration 662 makes `access_audit_log` SELECT/INSERT-only for
`kokonut_runtime`, after source review found only audit insert and read paths.
The role provisioner reapplies the policy after broad grants. Native and
ARM64/QEMU disposable checks pass migration replay, column-grant cleanup,
read/append success, and mutation denial. Focused suites pass 126 tests. The
full 653-file ARM64/QEMU schema replay through migration 662 now passes
under the verified 1.5 GiB/two-CPU budget. Its two-tenant probe passes all 17
assertions and verifies 106 declared boundaries, including the new append-only
audit policy, with zero direct table/column privilege violations. No retention
period is selected; cleanup stays outside runtime authority and must follow
the future configurable policy. The probe still reports 1,014 relations with
effective table DML while RLS is disabled, so C1 remains open. Checklist:
1,266 complete / 25 open (1,291 total); capability classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

### Current continuation — C2 SDK parameter-name contract

- [x] Extend the Python/TypeScript method-parity regression to compare
  positional parameter names with an explicit alias map for the reviewed
  `itemId`/`id`, `sensorId`/`deviceId`, and attestation subject/entity naming
  pairs. The focused three-test suite, Ruff, compilation, and diff checks pass.
  No public method signatures changed. This closes only the static parameter-
  name inventory subgate; C2 remains open for parameter types and runtime
  serialization, authenticated route/action/scope and pagination/error
  behavior, broader SDK/runtime parity, live OIDC, and populated acceptance.
  See the [batch record](batches.md) and
  [progress evidence](progress.md#sdk-parameter-name-parity-contract--27-october-2026).
- [x] Historical interim step: align the Python `ExportFormat` type with the
  TypeScript union. A subsequent schema audit found `format` absent from the
  canonical table and no process consuming pending requests, so that type and
  create helper were then removed as part of the current read-only SDK contract
  ([current record](#current-continuation--c2-canonical-export-log-sdk-contract);
  [earlier batch history](batches.md#L4766)).

### Current continuation — C1 full-schema runtime-role revalidation

- [x] Revalidate the native full schema and runtime boundary through migration
  662 under a 1.5 GiB/two-CPU database limit. All 653 files applied, and all 17
  signed synthetic operator/scope assertions passed with zero direct table or
  column violations among 106 declared boundaries. The refreshed report
  distinguishes referenced relations from actual DML targets; the analytics
  inventory now has 273 target relations / 425 sites and no unmatched
  candidates. `farm` is only an `INSERT … SELECT` source for two other target
  tables. The probe still finds 1,014 public relations with effective DML while
  RLS is disabled, so C1 remains open and universal tenant isolation is not
  established. Thirteen report/inventory tests plus Ruff, compilation, SQL
  inventory freshness, capability validation, and diff checks pass. No seeds,
  candidate, or legacy database were used ([batch](batches.md); [evidence](progress.md#correct-analytics-dml-target-classification--27-october-2026)).
- [x] Separate SQL-referenced relations from actual DML targets in the C1
  reports. The false `farm` source classification is removed; the inventory
  now covers 273 write-target relations / 425 sites with no unmatched
  candidates. Thirteen focused report/inventory tests and static checks pass.
  C1 remains open because 1,014 public relations still retain effective DML
  while RLS is disabled ([batch](batches.md); [progress](progress.md#correct-analytics-dml-target-classification--27-october-2026)).
- [x] Track `TRUNCATE` SQL targets and effective runtime `TRUNCATE` privileges
  separately from ordinary table DML. The migration-662 native snapshot reports
  zero runtime `TRUNCATE` grants. The scanner, ACL report, and analytics
  inventory selection passes 41 tests plus static checks; this does not close
  broad table-DML or universal RLS gaps ([batch](batches.md); [progress](progress.md#track-runtime-truncate-targets-and-privileges--27-october-2026)).
- [x] Make the legacy `agent_action_log` read-only to `kokonut_runtime` while
  retaining export reads and the separate Directus role's existing writes.
  Migration 663 and the role provisioner revoke runtime table/column writes;
  native and ARM64/QEMU disposable checks, a 654-file full-schema replay, and
  the 17-check two-tenant probe pass. The six-module regression suite passes
  135 tests. C1 remains open because 1,013 relations retain effective DML while
  RLS is disabled ([batch](batches.md); [progress](progress.md#progress-addendum--agent_action_log-runtime-read-only-boundary--27-october-2026)).
- [x] Keep seeded `carbon_benchmark` references readable but immutable to the
  Kernel runtime. Migration 664, native/ARM64 disposable ACL checks, and the
  655-file full-schema replay pass; 136 focused tests pass. The report records
  108 declared controls and 1,012 relations with effective DML while RLS is
  disabled; C1 remains open ([batch](batches.md); [progress](progress.md#progress-addendum--carbon_benchmark-runtime-read-only-boundary--27-october-2026)).
- [x] Keep seeded `ghg_emission_factor` references readable but immutable to
  the Kernel runtime. Migration 665, native/ARM64 disposable ACL checks, and
  the 656-file native full-schema replay with 18 operator-scope checks pass;
  137 focused tests pass. The report records 109 declared controls and 1,011
  relations with effective DML while RLS is disabled; C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--ghg_emission_factor-runtime-read-only-boundary--27-october-2026)).
- [x] Keep shared seeded `operations_protocol` handbook entries readable but
  immutable to the Kernel runtime. Migration 666, native/ARM64 disposable ACL
  checks, and the 657-file native full-schema replay with 19 operator-scope
  checks pass; 138 focused tests pass. The report records 110 declared
  controls and 1,010 relations with effective DML while RLS is disabled; C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--operations_protocol-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `process_maturity_level` and `pollinator_species_reference`
  readable but immutable to the Kernel runtime. Migration 667 passes native and
  ARM64/QEMU focused PostgreSQL checks and a 658-file native replay with 21
  two-tenant scope checks; 139 focused tests pass. The report records 112
  controls and 1,008 relations with effective DML while RLS is disabled. C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--static-taxonomy-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the GRI reporting and governance-framework registries readable but
  immutable to `kokonut_runtime`. Migration 668 passes native and ARM64/QEMU
  focused PostgreSQL checks and a 659-file native replay with 23 two-tenant
  scope checks; 141 focused tests pass. The report records 114 controls and
  1,006 relations with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--reporting-and-governance-registries-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `impact_framework` and `impact_dimension` readable but immutable to
  `kokonut_runtime`. Migration 669 passes native and ARM64/QEMU focused ACL
  checks and a 660-file native replay with 25 two-tenant scope checks; 142
  focused tests pass. The report records 116 controls and 1,004 relations
  with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--impact-framework-catalogs-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the seeded `expense_category` taxonomy readable but immutable to
  `kokonut_runtime`. Migration 670 passes native and ARM64/QEMU focused ACL
  checks and a 661-file native replay with 26 two-tenant scope checks; 143
  focused tests pass. The report records 117 controls and 1,003 relations
  with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--governed-expense-category-runtime-read-only-boundary--27-october-2026)).

- [x] Keep shared CRISP risk-dimension definitions readable but immutable to
  `kokonut_runtime` while retaining location-specific weight overrides.
  Migration 671 passes native and ARM64/QEMU focused ACL checks and a 662-file
  native replay with 27 two-tenant scope checks; the six-module focused suite
  passes 145 tests. The refreshed report records 118 runtime controls and
  1,002 relations with effective table DML while RLS is disabled. C1 remains
  open ([batch](batches.md); [progress](progress.md#progress-addendum--crisp-risk-dimension-runtime-read-only-boundary--27-october-2026)).

- [x] Encode caller-controlled collection and item IDs in the Python and
  JavaScript Directus SDKs as single path segments. The pinned Directus helper
  interpolates those values directly; focused regressions verify slashes and query/fragment delimiters staying encoded
  in the serialized route, with dot-segment rejection before transport. The
  full SDK suites pass (98 Python, 56 JavaScript), with TypeScript build, Ruff,
  and compilation clean. This closes one C2 serialization slice only;
  route/action/scope and runtime parity gates remain open
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-path-segment-parity.json)).

- [x] Align pagination serialization across Python and JavaScript SDK list calls.
  Merged options now use consistent offset/limit/page precedence, and invalid
  zero-limit offset requests fail before transport. The full SDK suites pass
  99 Python and 57 JavaScript tests; TypeScript build, Ruff, compilation, and
  109-model schema-parity checks pass. C2 remains open for route/auth, error and
  runtime parity ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-pagination-contract.json)).

- [x] Re-run the full schema on ARM64/QEMU through migration 671. All 662
  ordered files applied on `aarch64` under verified 1.5 GiB/two-CPU limits in a
  network-disabled disposable project, with no seeds, farm rows, host ports,
  OOM, or candidate/legacy access; cleanup passed. This replay did not include
  the operator-scope probe. C7 remains open for physical-device/power testing,
  populated data, and production recovery acceptance
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-671.json)).

- [x] Make `dfs_currency` read-only to the general Kernel runtime. Migration 672
  and native/ARM64 disposable PostgreSQL checks cover reads, table/column write
  denial, provisioner reapplication, and preservation of Directus grants. The
  complete native schema through 672 passes all 28 two-tenant probe assertions;
  119 declared ACL policies have zero mismatches, while 1,001 relations still
  have effective DML with RLS disabled, so C1 remains open. The three focused
  regression modules pass 103 tests. This is software-only synthetic evidence;
  physical Pi, populated operational data, and production acceptance remain
  open ([batch](batches.md); [progress](progress.md#progress-addendum--currency-reference-catalog-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the shared `crop_gdd_config` reference readable but immutable to
  `kokonut_runtime`. Migration 673 and native/ARM64 disposable PostgreSQL checks
  cover table and column mutation denial, reads, provisioner reapplication, and
  preservation of Directus grants. The 664-file native replay passes all 29
  two-tenant probe assertions. It loads no seeds, so populated GDD parity is
  still open. The three focused regression modules pass 104 tests; 120 ACL
  policies have zero mismatches while 1,000 relations still retain effective
  DML with RLS disabled, so C1 remains open. No candidate or legacy database
  was touched ([batch](batches.md); [progress](progress.md#progress-addendum--crop-gdd-configuration-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `pest_degree_day_config` readable but immutable to
  `kokonut_runtime`. Migration 674 passes native and ARM64/QEMU disposable ACL
  checks, including provisioner reapplication and Directus-grant preservation.
  The 665-file native replay passes all 30 two-tenant assertions and reads the
  schema-defined `fall_armyworm` default. The three focused regression modules
  pass 105 tests; 121 ACL policies have zero mismatches while 999 relations
  retain effective DML with RLS disabled, so C1 remains open. No candidate or
  legacy database was touched ([batch](batches.md); [progress](progress.md#progress-addendum--pest-degree-day-configuration-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `revenue_multiplier_config` readable but immutable to
  `kokonut_runtime`. Migration 675 passes native and ARM64/QEMU disposable ACL
  checks, including provisioner reapplication and Directus-grant preservation.
  The 666-file native replay passes all 31 two-tenant assertions and confirms a
  runtime query succeeds. Optional seeds 015/069 were not loaded, so configured
  values are not covered by this replay. The three focused regression modules
  pass 106 tests and the service module passes 14; 122 ACL policies have zero
  mismatches while 998 relations retain effective DML with RLS disabled, so C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--revenue-multiplier-configuration-runtime-read-only-boundary--27-october-2026)).

### Current continuation — C1 governed reference-class runtime boundary

- [x] Keep governed `reference_class` records readable but immutable to
  `kokonut_runtime`. Migration 676 denies table and residual column
  INSERT/UPDATE/REFERENCES privileges, restores SELECT, and is reapplied by the
  runtime provisioner after compatibility grants. Native and ARM64/QEMU
  disposable checks pass replay, reads, mutation/TRUNCATE/REFERENCES denial,
  and synthetic Directus grant preservation. The complete native schema replay
  through 676 passes all 31 two-tenant assertions under verified 1.5 GiB/two-CPU
  limits. The refreshed ACL report has zero policy mismatches across 123
  controls; 997 relations still retain effective DML with RLS disabled, so C1
  remains open. The combined regression selection reports 173 passed and one
  skipped. No seeds, farm data, candidate, or legacy state was used ([batch](batches.md#L4810);
  [progress](progress.md); [native replay evidence](builds/2026-10-27-recovery/runtime-role-full-schema-676-native-disposable.json)).

### Current continuation — C2 canonical export-log SDK contract

- [x] Remove unsupported export-log mutation from both SDKs and match the
  model to all ten canonical `export_log` columns. Source audit found the
  previously advertised request payload included columns absent from the
  schema, and no worker consumes pending requests; the established exporter
  writes audit rows after generating files. The SDK now offers only `list` and
  `get`, while file generation remains available through the exporter CLI.
  Python/method-parity tests pass 100, JavaScript tests pass 53, TypeScript
  builds, and the 109-model/2,150-column SDK schema guard passes. Ruff,
  compilation and diff checks pass; calls were mocked, with no database or
  provider. The earlier C2 export-create lifecycle note is superseded. A
  Gateway-backed request queue, authenticated attribution and async processing
  remain open ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-export-audit-read-only-contract.json)).

### Current continuation — C2 report snapshot SDK boundary

- [x] Remove generic report-snapshot mutations from Python and TypeScript SDKs.
  The report generator creates hashed, unfrozen draft snapshots with public-
  interest context; lifecycle review is a separate governed operation. The
  Gateway review routes are read-only, and the SDK had no source callsites for
  create/update/delete. Both SDKs now expose list/detail/type-filtered reads
  only. The focused Python SDK, parity, and report-governance selection passes
  107 tests; JavaScript passes 53; TypeScript builds. Ruff, compilation, and
  diff checks pass; the SDK schema guard is checked in the same batch. All API
  clients are mocked; no database/provider was used. No capability status
  changes. A Gateway report-generation and reviewer decision workflow remains
  open ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-report-snapshot-read-only-contract.json)).

### Current continuation — C2 attestation record SDK boundary

- [x] Remove generic attestation-record mutations from Python and TypeScript
  SDKs. The table contains governed workflow rows and chain-indexer projections;
  inserting a row directly cannot publish or independently verify an EAS
  attestation. Keep list/detail, pending-state, and subject-filtered reads, and
  leave actual publish/revoke actions in the dedicated EAS service and approved
  signing flow. Both workflow examples now read indexed attestations instead of
  writing misleading draft rows. The focused Python SDK/parity/report-governance
  selection passes 109 tests; JavaScript passes 54; TypeScript builds; Ruff and
  Python compilation pass. No database/provider was used. This does not add a
  Gateway attestation-request workflow or change capability/MAN-CAP status
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-attestation-read-only-contract.json)).

### Current continuation — C2 calculated NOI snapshot SDK boundary

- [x] Remove generic NOI snapshot mutations from both SDKs. `noi_snapshot`
  stores calculated values with source inputs and calculation version; SDK
  callers had no repository mutation callsites and could supply outputs without
  running that calculation. Preserve list/detail/crop-cycle reads. Existing
  CLI, signed-worker, and Directus-extension writer paths were not changed or
  runtime-validated. The focused Python SDK/parity/report-governance selection
  passes 111 tests; JavaScript passes 55; TypeScript builds; Ruff and compilation
  pass. No database/provider was used. This does not establish tenant isolation
  or change capability/MAN-CAP status ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-noi-snapshot-read-only-contract.json)).

### Current continuation — CI Kernel release-input lock repair

- [x] Update the Kernel release input lock to match the existing OIDC Dockerfile
  dependency change and hash both OIDC requirement manifests. The local lock
  gate and 36 focused profile/release tests pass; the failed hosted run has not
  yet been rerun on the repaired commit ([batch](batches.md); [evidence](builds/2026-10-28-recovery/ci-kernel-release-lock-repair.json)).

### Current continuation — C1 farmer credential-type catalog boundary

- [x] Keep seeded `farmer_credential_type` guidance readable but immutable to
  `kokonut_runtime`. Schema migration 148 seeds the catalog; farmer credential
  records store `credential_type` as free text, with no foreign key or
  application SQL callsite using the guidance table. Migration 677 removes
  runtime table and residual column INSERT/UPDATE/REFERENCES grants, restores
  SELECT, and the role provisioner reapplies the boundary after compatibility
  grants. Native and ARM64/QEMU PostgreSQL 16 acceptance passes migration
  replay, read access, mutation/TRUNCATE/REFERENCES and column-grant denial,
  provisioner reapplication, and preservation of synthetic Directus grants.
  The full native schema replay through 677 passes all 32 two-tenant checks and
  reads the schema-seeded catalog row. The refreshed ACL report has zero
  mismatches across 124 controls; 996 relations still retain effective DML
  while RLS is disabled, so C1 remains open. The focused parser/migration tests
  pass 68 tests. No optional seeds or farm data were loaded; candidate and
  legacy databases were untouched. Directus API parity, populated credential
  records, physical Raspberry Pi, and production acceptance remain open
  ([batch](batches.md#L4814); [migration](../schemas/postgres/677_runtime_farmer_credential_type_read_only.sql);
  [native ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-disposable.json);
  [ARM64 ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-arm64-disposable.json);
  [full schema and tenant probe](builds/2026-10-27-recovery/runtime-role-full-schema-677-native-disposable.json);
  [source/ACL report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).

### Current continuation — parallel report-scope and Gateway contract batch — 28 October 2026

- [x] Require explicit location scope for the three location-only Kokonut
  Commons reports. Network-only federation and participatory-signal reports
  keep their explicit global contract. Focused tests and the integrated report
  suite pass; no database/provider was used
  ([evidence](builds/2026-10-28-recovery/kokonut-commons-report-location-scope.json)).
- [x] Require scope for all 18 location-only strategy reports. Remove the
  unscoped stakeholder-outcomes branch; network-wide value-stream links remain
  available through `stakeholder_value_streams`. Farm-scoped fork detection
  excludes `insight_transfer` until it has trustworthy location lineage, while
  network-wide detection retains it. Focused suite: 158 passed
  ([evidence](builds/2026-10-28-recovery/stakeholder-outcomes-direct-scope.json)).
- [x] Require location scope for direct `perpetual_value_stress` report calls
  before cursor creation. Preserve selected-farm and reviewed shared rows;
  focused report checks pass 285 cases
  ([evidence](builds/2026-10-28-recovery/perpetual-value-stress-location-scope.json)).
- [x] Publish FastAPI/OpenAPI bounds for the authenticated Delphi participant
  workspace (`limit=1..50`, `offset=0..10,000`) and reject invalid paging
  before service access. Twenty-two focused checks pass
  ([evidence](builds/2026-10-28-recovery/delphi-participant-workspace-pagination-openapi.json)).
- [x] Publish the existing `limit=1..100` bound (default `50`) on six operator
  list routes and reject invalid values before service access. The operator and
  farm-activity selection passes 138 checks
  ([evidence](builds/2026-10-28-recovery/operator-list-pagination-openapi-bounds.json)).
- [x] Reconcile report query inventory after removing unsafe unscoped branches.
  It now records 94 report types, 167 direct queries, 166 positional-bind
  sites, zero unresolved sites, and zero bind mismatches. The integrated report
  suite passes 563 tests with four database-dependent skips.
- [x] Validate the combined changed Gateway/operator contracts: 732 tests pass.
  The focused platform-integrity selection passes 374 tests and six subtests;
  changed Python Ruff and compilation, Directus hook tests/build, SDK tests/build,
  dependency/provider checks, matrix validation, and diff checks pass. No
  candidate or legacy database, migration, or provider was used.

Capability classifications remain unchanged at 67 rows (24 baseline-retained,
7 deployed, 36 prepared); no MAN-CAP is accepted. The current checklist is
1,350 complete / 25 open (1,375 total). Remaining human/runtime gates stay open
([combined evidence](builds/2026-10-28-recovery/parallel-report-gateway-contracts.json)).

### Completed continuation — parallel Kernel hardening — 28 October 2026

- [x] Bound the public driver catalog to enabled, display-safe entries with a
  stable database order, a 50-row maximum page, an offset ceiling, and
  continuation metadata. Loader paths, class names, and registration notes are
  excluded ([evidence](builds/2026-10-28-recovery/public-driver-catalog-projection.json)).
- [x] Require explicit location scope for location-only tactical analytics
  CLI operations and reject malformed or contradictory scope before database
  access ([evidence](builds/2026-10-28-recovery/analytics-tactical-cli-scope-preflight.json)).
- [x] Pass the ClickHouse password only to the isolated `clickhouse_outbox`
  worker while preserving the existing environment boundary for other worker
  identities ([evidence](builds/2026-10-28-recovery/worker-clickhouse-secret-routing.json)).
- [x] Derive operator-scope replay ACL expectations from the current runtime
  policy lists and reject stale hard-coded counts.
- [x] Replay all 672 ordered schema files through migration 681 on a
  network-disabled native PostgreSQL 16 container with verified 1.5 GiB/two-CPU
  limits, no host ports or seed/farm data, passing synthetic two-tenant checks,
  and successful cleanup. Refresh the ACL report to the observed source and
  migration head ([full replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json);
  [report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json)).

The combined focused selection passes 165 tests. This is synthetic evidence;
candidate/legacy state, production deployment, physical Raspberry Pi behavior,
and global tenant isolation are not established. The current checklist is
1,382 complete / 25 open (1,407 total); capability classifications and
MAN-CAP acceptance are unchanged. This TODO ledger now has 92 checked and 16
open entries.

### Completed continuation — public driver and tenant-reference contracts — 28 October 2026

- [x] Add the stable versioned public driver catalog route and typed Python/TypeScript SDK methods. Generated OpenAPI/SDK parity, pagination bounds, response allowlist, and mocked transport checks pass ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
- [x] Make Directus writable-reference lookups location-qualified and conceal whether a valid UUID is missing or belongs to another location. Fourteen focused predicate/non-disclosure tests, the full 124-test extension suite, and the extension build/type check pass ([evidence](builds/2026-10-28-recovery/directus-tenant-reference-nondisclosure.json)). Live Directus role/field/row parity remains open.
- [x] Replay the full schema on ARM64/QEMU through migration 681 with verified 1.5 GiB/two-CPU limits, network disabled, no seeds or host ports, and cleanup success. The optional operator-scope probe did not run, and no physical Raspberry Pi was used ([evidence](builds/2026-10-28-recovery/arm64-resource-limited-schema-681.json)).
- [x] Keep driver catalog database failures distinct from an empty catalog: failures propagate to a generic no-store Gateway 500. The 47-test Gateway/OpenAPI/Python-SDK selection, Ruff, compilation, and diff checks pass with fake database/transport behavior ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
- [x] Require source review for new unresolved direct SQL DML/`WITH` candidates through the runtime inventory check. Existing candidates remain explicitly tracked and the fingerprint baseline is pinned; this does not reduce the observed broad grants ([evidence](builds/2026-10-28-recovery/runtime-sql-unresolved-write-drift-gate.json)).
- [x] Publish and validate a strict success model for the private yield-monitoring summary, preserving the existing auth and error/cache contracts ([evidence](builds/2026-10-28-recovery/yield-summary-response-contract.json)).
- [x] Publish and validate a strict success model for the migration-458 coordination-governance summary, preserving its tenant and error/cache contracts ([evidence](builds/2026-10-28-recovery/coordination-governance-response-contract.json)).
- [x] Publish and validate a strict success model for the emergency-response aggregate summary, preserving its tenant and error/cache contracts ([evidence](builds/2026-10-28-recovery/emergency-response-summary-contract.json)).
- [x] Validate the Comprehensive Status location envelope, canonical section names, and existing response-size bound ([evidence](builds/2026-10-28-recovery/comprehensive-status-response-contract.json)).
- [x] Publish and validate the nested energy summary response against source schema and query bounds ([evidence](builds/2026-10-28-recovery/energy-summary-response-contract.json)).
- [x] Publish and validate the nested true-cost summary response and requested-location identity ([evidence](builds/2026-10-28-recovery/true-cost-summary-response-contract.json)).
- [x] Publish and validate the location-scoped business-architecture summary and pagination contract ([evidence](builds/2026-10-28-recovery/business-architecture-summary-response-contract.json)).
- [x] Publish strict response contracts for the extension-learning module catalog and aggregate summary ([evidence](builds/2026-10-28-recovery/extension-learning-response-contract.json)).
- [x] Publish and validate the nested waste-management summary response ([evidence](builds/2026-10-28-recovery/waste-summary-response-contract.json)).

The batches checklist is 1,398 complete / 25 open (1,423 total). This TODO
ledger now has 106 checked and 16 open entries; capability classifications and
MAN-CAP acceptance remain unchanged.


### Completed in the current continuation — three private Gateway summaries

- [x] Add a strict irrigation status response contract, including nested row
  allowlists, schema-backed state values, requested-location identity, and
  consistent bounded pagination.
- [x] Add strict landscape-conservation and pollinator aggregate contracts
  with nested allowlists, bounded groups, source-aligned enums, finite numeric
  values, and requested-location identity.
- [x] Refresh the shared route fixtures and run the combined selection: 77
  tests pass; Ruff, Python compilation, capability-matrix validation, and diff
  checks pass. No database or provider was used. Evidence is recorded in
  [the batch log](batches.md).

The checklist is now 1,401 complete / 25 open (1,426 total). This TODO ledger
has 109 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance remain unchanged; live OIDC, populated-data parity, and broader
tenant isolation remain open.

### Completed continuation — nutrient, strategy, and competitive-landscape response contracts — 28 October 2026

- [x] Validate nutrient-balance projections, including strict aggregates,
  request binding, and safe pagination at the 10,000-offset ceiling.
- [x] Add a schema-aligned, privacy-limited response model for location-scoped
  strategy plans and enforce SQL-consistent page and offset bounds.
- [x] Add a strict aggregate-only competitive-landscape response contract
  that excludes participant identities and private evidence/content fields.
- [x] Make runtime-SQL review fingerprints stable across Python 3.11 and 3.12
  without changing the pinned digest or existing unresolved-write ledger.

The combined Gateway response selection passes 182 tests and the runtime SQL
inventory suite passes 24. Ruff, compilation, capability-matrix validation,
and inventory freshness on Python 3.11/3.12 pass. Candidate/legacy databases
and providers were not used ([evidence](builds/2026-10-28-recovery/gateway-nutrient-strategy-competitive-response-contract-batch.json)).
The checklist is now 1,405 complete / 25 open (1,430 total); this TODO ledger
has 113 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance are unchanged.

### Completed parallel continuation — six private Gateway response families — 28 October 2026

- [x] Add strict source-derived response models and request binding for crop
  simulation run list/detail; correct `has_more` at the 10,000 offset ceiling.
- [x] Add the spatial-autocorrelation response model with source enums,
  numeric bounds, and request-bound location/page metadata.
- [x] Enforce response contracts for the five private trend-analysis GET
  endpoints, including metric and pagination identity.
- [x] Validate the management workload summary's SQL projection, counts,
  timestamp, privacy allowlist, and location.
- [x] Validate business-planning canvas list content and bounded continuation.
- [x] Validate planning-budget summaries and stop pagination beyond the
  supported offset ceiling.

The combined selection passes 188 tests; crop-specific offset-boundary tests
pass at 9,975, 9,976, and 10,000. Ruff, compilation, capability-matrix
validation, JSON evidence parsing, runtime SQL inventory checks on Python
3.11/3.12, and diff checks pass. The 37-entry unresolved-write ledger is
unchanged. No candidate/legacy database or provider was used
([evidence](builds/2026-10-28-recovery/gateway-private-response-contracts-batch-2.json)).
The checklist is now 1,411 complete / 25 open (1,436 total); this TODO ledger
has 119 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance remain unchanged.


### Completed continuation — geostatistics and pollinator detail contracts — 28 October 2026

- [x] Publish strict OpenAPI/runtime contracts for all remaining private
  geostatistics GET routes, including nested folds, summaries, and bounded
  point projections; bind location/run/page identity and stop continuation at
  the offset ceiling.
- [x] Publish strict review-queue, habitat, and hive response contracts for
  pollinator reads; retain record-type-specific detail validation, location
  grants, and sanitized no-store errors.

The combined focused Gateway selection passes 158 tests. Ruff, Python
compilation, capability validation, runtime-SQL inventory tests (24), current
inventory checks on Python 3.11/3.12, and diff checks pass. The 37-candidate
inventory keeps two source-reviewed SELECT-only `WITH` scopes in `reviewed_sites`;
this review does not approve ACLs or change grants. No live database/provider,
candidate, or legacy service was used ([evidence](builds/2026-10-28-recovery/gateway-geostatistics-pollinator-response-contracts.json)).

The checklist is now 1,414 complete / 25 open (1,439 total); this TODO ledger
has 121 checked and 16 open entries. Capability classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


### Completed parallel continuation — private read response contracts — 28 October 2026

- [x] Add an AI-summary review-list response contract that accepts the full
  migration-backed source catalog, preserves network/location scope labels,
  and recognizes worker-attribution blockers.
- [x] Add a strict business-canvas version-history contract, including the
  canonical snapshot blocks and bounded response size.
- [x] Add strict sequential-evidence summary and event response contracts
  aligned to their current SQL projections and pagination bounds.
- [x] Add strict nutrient soil-test and input/removal response contracts,
  including source enums, totals, cost classification, and offset-ceiling
  behavior.

The combined Gateway selection passes 157 tests; Ruff, compilation, capability
validation, Python 3.11/3.12 runtime-SQL freshness, and the 24-test inventory
regression pass. Evidence is recorded in [the batch log](batches.md). This
ledger now has 125 checked / 16 open entries; the batches checklist records
1,418 complete / 25 open. Capability classifications and MAN-CAP acceptance
remain unchanged.


### Completed continuation — private Delphi, stakeholder, and incident reads — 28 October 2026

- [x] Add strict request-bound response validation for private Delphi consent
  notices and consultation reads, including nested aggregate privacy.
- [x] Add bounded response and continuation checks for the Delphi independent
  minority-report and recommendation review queues.
- [x] Add cursor-order and exact location/party binding for stakeholder
  identity and trust review pages.
- [x] Add the exact bounded response contract for the pollution-incident
  review queue and parse the nested Delphi JSONB timestamp wire value.

The combined focused Gateway selection passes 198 tests. Ruff, compilation,
capability-matrix validation, runtime SQL inventory freshness on Python
3.11/3.12, and diff checks pass. No database, provider, candidate, or legacy
service was used. Evidence is recorded in [the batch log](batches.md). This
ledger has 129 checked / 16 open entries; the batches checklist records
1,422 complete / 25 open. The matrix now records 51 strict private Gateway
response endpoints; classifications and MAN-CAP acceptance remain unchanged.


### Completed parallel continuation — direct report scope and response contracts — 28 October 2026

- [x] Validate Directus `farm_activity.farm_task_id` against the location on
  create/update.
- [x] Validate Directus `expense_event.weekly_plan_id` against the location on
  create/update.
- [x] Reject invalid `crop_noi` location scope before cursor creation.
- [x] Reject invalid `resource_efficiency` location scope before cursor
  creation.
- [x] Reject invalid `holistic_wellbeing` location scope before cursor
  creation.
- [x] Reject invalid `revenue_multiplier` location scope before analyzer
  access.
- [x] Strictly validate and request-bind both farm-activity detail responses.
- [x] Strictly validate and request-bind governance-role detail.
- [x] Strictly validate the submitted-report review-queue projection while
  preserving authorization, errors, timestamp formatting, and cache headers.

The Directus `workflow_history` and `approval` audit remains an open gate:
both tables have polymorphic IDs without tenant keys, and their historical
lineage and visibility rules need populated-data review before filtering.

The integrated selection passes 411 Python tests, 27 Directus tenant-hook
tests, and the Directus TypeScript check. Ruff, compilation, report source/query
inventories, matrix validation, and diff checks pass. No migrations, databases,
providers, candidate, legacy service, or live network were used. See [evidence](builds/2026-10-28-recovery/kernel-parallel-report-and-gateway-contracts.json).

Checklist: 1,455 complete / 25 open (1,480 total); TODO: 162 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and
records 66 strict private Gateway response endpoints. MAN-CAP acceptance and
capability classifications are unchanged.


### Completed continuation — Directus, report scope, and private queue contracts — 28 October 2026

- [x] Narrow the Analyst `stakeholder_feedback` field allowlist without
  changing its existing row predicates; retain source-only evidence limits.
- [x] Audit remaining Analyst/Auditor wildcard reads; leave the all-status
  Auditor forensic permission unchanged because no approved private-field
  contract supports a safe narrower projection.
- [x] Require explicit valid location scope for direct `farm_summary` calls
  before cursor creation; keep output projections unchanged pending review.
- [x] Require explicit valid location scope for direct
  `regenerative_outcomes` calls before cursor creation.
- [x] Add an exact, request-location-bound response contract for the private
  mobile collection review queue.
- [x] Add an exact, request-location-bound response contract for the private
  farm-activity intake queue.

The integrated focused selection passes 400 tests. Ruff, compilation, report
source/query inventories, the Directus permission inventory, capability-matrix
validation, and diff hygiene pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-directus-mobile-report-scope-contracts.json).
Checklist: 1,461 complete / 25 open (1,486 total); TODO: 168 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and
records 68 strict private Gateway response endpoints. MAN-CAP acceptance and
capability classifications are unchanged.


### Completed parallel continuation — GNH, mobile inventory, and forecast scope — 28 October 2026

- [x] Reject invalid direct `generate_gnh_alignment` location scope before
  database access.
- [x] Enforce a strict request-location-bound response contract for the private
  mobile operations inventory.
- [x] Add fail-closed tenant reads and read-only enforcement for Directus
  `forecast_output` rows.

The integrated selection passes 422 Python tests and 138 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-gnh-mobile-inventory-forecast-output-boundary.json).
Checklist: 1,464 complete / 25 open (1,489 total); TODO: 171 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 69 strict private Gateway response endpoints. These checks do not prove
live Directus role behavior or historical forecast lineage.


### Completed parallel continuation — reports, CLI, retirement reads, and Directus scope — 28 October 2026

- [x] Reject invalid direct cultural-preservation report location scope before
  opening a cursor.
- [x] Preflight crop-rotation CLI location arguments before database setup.
- [x] Enforce the exact request-bound retirement-candidate response and page
  continuation contract.
- [x] Scope Directus `capex_breakdown` reads to operator grants and deny
  Directus mutations.

The integrated selection passes 551 Python tests and 141 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-culture-crop-solution-capex-boundaries.json).
Checklist: 1,473 complete / 25 open (1,498 total); TODO: 180 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 71 strict private Gateway response endpoints. The optional Directus hook
now covers 26 scoped collections; runtime behavior remains unverified.


### Completed parallel continuation — reports, CLI, Governance API, and Directus reads — 28 October 2026

- [x] Reject invalid direct capital-provider report location scope before
  database access.
- [x] Enforce a strict request-bound Governance roles page response contract.
- [x] Add a fail-closed read-only Directus tenant boundary for `noi_snapshot`.
- [x] Add a fail-closed read-only Directus tenant boundary for `water_access`.
- [x] Reject invalid traceability `create-batch` and `certs` location UUIDs
  before the CLI opens PostgreSQL.

The integrated selection passes 459 Python tests (3 skipped) and 140 Directus
extension tests. Build/typecheck, Ruff, compilation, report inventories,
capability-matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-report-cli-governance-directus-reads.json).
Checklist: 1,469 complete / 25 open (1,494 total); TODO: 176 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 70 strict private Gateway response endpoints. Directus runtime acceptance
and populated parity remain open.


### Completed parallel continuation — renewable report, pollinator CLI, capacity page, and attestation — 28 October 2026

- [x] Reject invalid direct renewable-energy report location scope before
  database access.
- [x] Preflight the pollinator health CLI's active location-scoped read
  commands before database setup.
- [x] Enforce the exact signed own-capacity response and pagination contract.
- [x] Add a fail-closed, read-only Directus tenant boundary for
  `attestation_plan`.

The integrated selection passes 573 Python tests and 142 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
capability-matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-renewable-pollinator-capacity-attestation.json).
Checklist: 1,477 complete / 25 open (1,502 total); TODO: 184 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 72 strict private Gateway response endpoints. The optional Directus hook
covers 27 location-scoped collections; live runtime parity remains open.


### Local continuation — wellbeing scope, energy CLI, Delphi response, and Directus source audit

- [x] Fail closed on invalid direct vulnerable-access and
  foundational-wellbeing report location scope before database access.
- [x] Preflight the energy-monitoring source-registration CLI location UUID
  before database setup.
- [x] Validate the private Delphi participant workspace against its exact
  session-derived projection, consent scopes, and requested page.
- [x] Complete the source-only audit of direct-required-location collections
  with managed Directus read rules; all twelve are covered by the existing
  tenant adapter. Broader runtime and relationship parity remain open.

Checklist: 1,482 complete / 25 open (1,507 total); TODO: 188 checked / 16
open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared), with 73 strict private Gateway response endpoints.


### Completed continuation — scope preflight and private competency response — 28 October 2026

- [x] Reject malformed location UUIDs before cursor/helper access for the
  three Kokonut governance reports, scaling economics, and value-stream map;
  preserve documented network-wide modes.
- [x] Add a strict, request-bound response model for the private
  operating-pilot own competency assessment history page.
- [x] Preflight location UUIDs across Capital, Certificates, Drivers, Events,
  Finance, Forecast, Fortune500, Geostatistics, Graph Projection, Management,
  Office, Planning, RDF, Revenue Multiplier, Sandbox, Strategic Reserve, and
  Threatcasting CLIs while preserving intentional global modes.

The combined focused route/report/CLI selection passes 745 tests (2 skipped).
Ruff, Python compilation, report source/query inventories, capability-matrix
validation, and diff checks pass. The strict private Gateway response count is
77. Evidence:
[batch](builds/2026-10-28-recovery/kernel-scope-preflight-competency-response.json).

Checklist: 1,494 complete / 25 open (1,519 total); TODO: 200 checked / 16
open. Live tenant isolation and authenticated Gateway/database acceptance
remain separate gates.


### Completed parallel continuation — work opportunities, governance detail, and CLI normalization — 28 October 2026

- [x] Add a strict request-bound response contract to the private
  operating-pilot work-opportunities page, validating the migration projection,
  own-claim consistency, ordering, bounds, location, and continuation.
- [x] Add a strict request-bound response contract to private governance-circle
  detail, matching the seven-field query projection and requested location and
  circle IDs.
- [x] Validate and canonicalize supplied CRISP location UUIDs before its
  database branches, including persisted rating; preserve mode-specific
  missing-location errors.
- [x] Canonicalize already-validated Data Governance location filters before
  dispatch in both `--location-id VALUE` and `--location-id=VALUE` forms.
- [x] Audit all 94 registered report generators for pre-query location-scope
  validation; all are covered inline or through a checked pre-cursor helper.

The combined operating-pilot/Gateway/CLI regression selection passes 262 tests;
the adjacent governance selection passes 44 tests with 5 skips. Additional
focused CRISP and Data Governance selections pass 97 and 9 tests respectively;
the work-opportunity and governance-circle response selections pass 110 and 39
tests. These focused selections overlap. Ruff, Python compilation, the report
source inventory check, capability-matrix validation, and `git diff --check`
pass. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared); strict private Gateway response endpoints now total 81, and 25 CLI
groups have location UUID preflight. No database, provider, candidate, legacy
service, or live network was used. Live OIDC, tenant isolation, and populated
parity remain separate gates. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-governance-work-opportunity-boundaries.json).

Checklist: 1,503 complete / 25 open (1,528 total); TODO: 209 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed parallel continuation — solution lifecycle gates and CLI UUID preflight — 28 October 2026

- [x] Add a strict request-bound response contract for the private
  solution-lifecycle gate page, including its exact migration projection,
  bounded maturity, unique IDs, stable order, pagination, and continuation.
- [x] Preflight and canonicalize location UUIDs for all 13 database-backed
  Analytics CLI operations before module dispatch or database access.
- [x] Apply the same fail-before-dispatch UUID contract to Credit Class batch
  and enrollment location operations.

The combined Gateway/CLI regression selection passes 159 tests. Ruff,
compilation, matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-solution-lifecycle-cli-boundaries.json).
Strict private Gateway response contracts: 82; CLI location UUID preflight:
27 groups. No live database/provider was used; this does not prove tenant row
isolation or populated parity.

Checklist: 1,506 complete / 25 open (1,531 total); TODO: 212 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed parallel continuation — solution lifecycle read contracts and CLI normalization — 28 October 2026

- [x] Contract the private solution stage-transition target, aggregate summary,
  and experiment list responses against their exact migration-backed
  projections; bind location and pagination and reject malformed output.
- [x] Canonicalize valid supplied location UUIDs before database dispatch in
  the Digital Finance, Crop Rotation, Marketplace, Extension, Pest Management,
  Energy Monitoring, and Farmer Identity CLIs while preserving global and
  optional-scope behavior.
- [x] Record integrated acceptance and refresh the capability/progress ledgers.

The integrated Gateway/CLI selection passes 295 tests. Ruff, compilation,
matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-solution-lifecycle-read-and-cli-canonicalization.json).
The strict private Gateway response count is 85; the existing 27 counted CLI
groups retain their UUID-preflight status. No live database/provider or
populated tenant data was used.

Checklist: 1,510 complete / 25 open (1,535 total); TODO: 215 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed continuation — lifecycle, demand response, and pollinator CLI — 28 October 2026

- [x] Enforce strict response validation for solution-lifecycle funding
  targets, bound to migration 488's exact projection, location, and page.
- [x] Enforce the redacted migration-479 demand-signals response contract,
  including ordering, pagination, status, and numeric bounds.
- [x] Canonicalize pollinator-health location UUIDs before database dispatch.

The integrated selection passes 564 tests. Ruff, compilation, capability
matrix validation, and diff checks pass. Strict private Gateway response
contracts now total 87; the 27 counted CLI groups retain UUID preflight.
Evidence: [batch](builds/2026-10-28-recovery/kernel-parallel-lifecycle-demand-pollinator.json).
No live database/provider was used; live OIDC, tenant row isolation, and
populated-data parity remain open.

Checklist: 1,513 complete / 25 open (1,538 total); TODO: 218 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed C2 foundation slices — private storage and snapshot validation — 28 October 2026

- [x] Implement a private local artifact store with canonical UUID keys,
  restrictive permissions, symlink-safe paths, atomic replacement, and
  explicit deletion only.
- [x] Validate and serialize exact-location verified/published report
  snapshots with a matching content hash and 512 KiB limit; exclude the legacy
  file URL from output.

The focused suites pass 33 tests across both modules. C2 remains open because
the request queue, authorized reader integration, worker, Gateway download,
and R2 delivery are not yet implemented. Evidence:
[C2 foundation](builds/2026-10-28-recovery/kernel-c2-private-export-primitives.json).

Checklist: 1,515 complete / 25 open (1,540 total); TODO: 220 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed C1 continuation — service registry runtime boundary — 28 October 2026

- [x] Make `service_registry` read-only to `kokonut_runtime` in migration 682
  and runtime-role provisioning, while preserving catalog reads, Directus
  CRUD, and capability-service mapping writes.
- [x] Reconcile the pre-existing unresolved-write fingerprint for
  `generate_farm_summary`; source review confirms a SELECT-only CTE and keeps
  the site tracked as `reviewed_unresolved`, not as ACL approval.

Focused source/policy checks passed (118 tests), migration checks passed (37),
and the post-reconciliation inventory/privilege selection passed (32). The
disposable PostgreSQL 16 harness replayed migration 682 and confirmed the
boundary after compatibility-grant reapplication across 128 synthetic tables.
The current 37-candidate inventory gate passes. Evidence:
[service registry](builds/2026-10-28-recovery/kernel-c1-service-registry-boundary.json).
No candidate or legacy database was used; this is not tenant/RLS acceptance.

Checklist: 1,517 complete / 25 open (1,542 total); TODO: 222 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed C2 slice — durable private report snapshot export — 28 October 2026

- [x] Connect the private artifact store and snapshot serializer to an
  idempotent, tenant-qualified export request queue, strict operator
  create/read/download routes, and a default-off dedicated one-shot worker.
  Migration 683 restricts each API and worker identity to bounded functions,
  binds reads/downloads to current location grants, and denies direct access to
  export request/attempt tables. Retries are delayed and bounded; artifacts
  stay private and are never automatically pruned.
- [x] Bound artifact bytes at the storage read boundary using the
  database-authorized expected size, rejecting oversized files before content
  is loaded and detecting growth during streaming.

The integrated Gateway, route-policy, worker, migration-contract, runtime-role,
and static worker-inventory selection passes **238 tests**. The bounded-read
follow-up passes **65 storage/Gateway/worker tests**, and the refreshed worker function graph regression passes **13 tests**. Ruff, Python compilation,
all seven worker/runtime SQL inventory checks, capability matrix validation,
dependency-group alignment, provider-boundary checks, and diff checks pass.
Network-disabled disposable PostgreSQL 16 acceptance applies
and replays migration 683 on both native x86_64 and ARM64/QEMU (`aarch64`),
validating synthetic tenant grants, source lifecycle, role boundaries, forced
RLS, retries, and worker lease fencing. ARM64/QEMU is code-level portability
evidence, not a physical Raspberry Pi run. The signed-context Gateway reads use
normal transactions because the context setter takes `FOR SHARE` locks; routes
then call only fixed bounded read functions. Static inventories now include
the isolated report worker. The aggregate worker preflight remains
`review_required` for existing broader boundary debt. Candidate and legacy
databases remain untouched. C2 remains open pending live OIDC, candidate
rollout, browser acceptance, worker runtime recovery, artifact orphan
reconciliation, R2 inventory/deletion, configurable retention, broader report
parity, stakeholder access contracts, and MAN-CAP review. Evidence:
[contract](report-snapshot-export-contract.md),
[bounded-read checks](builds/2026-10-28-recovery/report-snapshot-export-bounded-read-checks.json),
[integrated checks](builds/2026-10-28-recovery/report-snapshot-export-integration-checks.json),
[native migration acceptance](builds/2026-10-28-recovery/report-snapshot-export-migration-disposable.json),
[ARM64 migration acceptance](builds/2026-10-28-recovery/report-snapshot-export-migration-arm64-disposable.json).

Checklist: 1,519 complete / 25 open (1,544 total); TODO: 224 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.


### Completed parallel continuation — operating-pilot response, report scope, and CLI preflight — 28 October 2026

- [x] Add strict request-bound OpenAPI/runtime response contracts for the
  private operating-pilot capacity-period and work-claim pages, including
  migration-derived suppression, ordering, page bounds, and location binding.
- [x] Reject invalid selected location UUIDs before query/helper access in the
  business-plan adapter and State-of-Kokonut status, graph, comprehensive, and
  strategic-reserve report paths; preserve intentional network-wide modes.
- [x] Preflight and canonicalize supplied location UUIDs across Data Stream,
  Security verification, Precision Irrigation, stakeholder grievances,
  Treasury, Cooperative, and Traceability CLIs. Preserve supported unfiltered
  modes when optional scope is omitted.
- [x] Regenerate report source/helper/query inventories and record the focused
  batch evidence.

The integrated regression selection passes 961 tests; adjacent grievance,
Treasury, Cooperative, and Traceability checks pass 94 tests with 2 skips and 4
passing subtests. Ruff, Python compilation, all report inventory checks,
capability-matrix validation, and `git diff --check` pass. The capability
matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared); strict
private Gateway response endpoints now total 79, and 24 CLI groups have
location UUID preflight. No database, provider, candidate, legacy service, or
live network was used. Broader tenant isolation and live OIDC/database
acceptance remain open. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-response-report-cli-boundaries.json).

Checklist: 1,498 complete / 25 open (1,523 total); TODO: 204 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Completed C2 continuation — optional S3-compatible private artifact adapter — 28 October 2026

- [x] Add an optional S3-compatible implementation behind the private artifact
  port while keeping the local store as default. Object keys are UUID-derived
  under a private prefix; reads require a byte cap and stream bounded data.
- [x] Separate Gateway read-only object credentials from worker write/delete
  credentials. Neither identity needs bucket listing; provider exceptions and
  object paths are redacted, and boto3 stays lazy behind the exports group.

The focused storage/Gateway/worker selection passes 77 tests, and the worker-inventory regression selection passes 67 tests with all seven generated reports current. Ruff,
compilation, dependency-group alignment, and provider-boundary checks pass.
All checks use a synthetic S3 client; no R2 account, database, candidate,
legacy stack, or production bucket was contacted. Live bucket policy and
connectivity, R2 inventory/deletion acceptance, backup/retention, and orphan
reconciliation remain open. Evidence:
[storage contract](report-snapshot-export-contract.md),
[adapter checks](builds/2026-10-28-recovery/report-snapshot-export-s3-adapter-checks.json).

Checklist: 1,528 complete / 25 open (1,553 total); TODO: 231 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Previous local continuation — response and report projection contracts — 28 October 2026

The current continuation adds the strict regenerative-outcomes section
contract, runtime JSON validation for federation capabilities, and explicit
schema projections for stakeholder outcomes and Green Paper publication
status. Its integrated regression selection passes 525 tests; lint,
compilation, report inventories, capability validation, and diff checks pass.
Content-level privacy and populated-data parity remain open. See
[batch evidence](builds/2026-10-28-recovery/kernel-parallel-regenerative-federation-report-projections.json).

Checklist: 1,532 complete / 25 open (1,557 total); TODO: 235 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Previous local continuation — GNH, public reports, and SDK location validation — 28 October 2026

Comprehensive Status now checks the GNH report location, assessment rows, and
rounded average. Regenerative-outcomes and time-liberation reports explicitly
select their complete public-view projections, and both REST SDKs validate the
public location list/detail response shape at runtime. The integrated focused
Python selection passes 186 tests and the TypeScript selection passes 43;
inventories and static checks pass. Content-level privacy and populated-data
parity remain open. See
[batch evidence](builds/2026-10-28-recovery/kernel-parallel-gnh-sdk-report-projection-contracts.json).

Checklist: 1,536 complete / 25 open (1,561 total); TODO: 239 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Previous local continuation — capital efficiency, wellbeing projections, and CRISP SDK parity — 28 October 2026

The strict capital-efficiency contract now binds both nested row families to
the requested location. GNH, cultural-preservation, and renewable-energy
reports use explicit full public-view projections. Python and TypeScript
validate CRISP responses, including requested-location matching. The
integrated Python selection passes 209 tests, TypeScript passes 75, and the
SDK build, lint, compilation, inventories, and matrix checks pass. Content
privacy and populated-data parity remain open. See
[batch evidence](builds/2026-10-28-recovery/kernel-parallel-capital-wellbeing-crisp-contracts.json).

Checklist: 1,541 complete / 25 open (1,566 total); TODO: 244 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Latest local continuation — community wellbeing and public SDK summary contracts — 28 October 2026

The strict Comprehensive Status contracts preserve globally shared
community-governance rows with null location scope and allow qualitative-only
foundational-wellbeing observations. Three reports now select their exact
public-view fields, and both REST SDKs validate metrics and nested location
summaries against the request location. The integrated Python selection passes
278 tests, TypeScript passes 121, and build/lint/compilation/inventory checks
pass. Content privacy and populated parity remain open. See
[batch evidence](builds/2026-10-28-recovery/kernel-parallel-wellbeing-community-sdk-contracts.json).

Checklist: 1,548 complete / 25 open (1,573 total); TODO: 251 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Latest local continuation — Data Stream, report projection, and SDK contracts — 28 October 2026

- [x] Add and test a strict private Data Stream post-list contract with exact
  response fields, no-store failure behavior, and requested-location binding.
- [x] Replace the replication-readiness report’s wildcard projection with all
  19 public-view columns and verify shared null-scope rows and payload parity.
- [x] Replace the adaptive-stewardship report’s wildcard projection with all
  19 public-view columns and verify serialized output parity.
- [x] Replace the capital-alignment report’s wildcard projection with all 17
  public-view columns and verify risk aggregation and payload parity.
- [x] Require exact `{data}` success envelopes in both REST SDKs.
- [x] Require location-detail responses to match the requested UUID in both
  SDKs while retaining path encoding and normalized UUID behavior.

The integrated focused Python selection passes 232 tests and the TypeScript
public-API selection passes 125; build, Ruff, compilation, inventory, matrix,
and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-report-sdk-datastream-contracts.json).

Checklist: 1,554 complete / 25 open (1,579 total); TODO: 257 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Latest local continuation — operations reports and governance summary contract — 28 October 2026

- [x] Add and verify a strict location-governance summary contract with
  requested-location binding and sanitized no-store failures.
- [x] Replace and parity-check the resource-efficiency public-view wildcard
  projection.
- [x] Replace and parity-check the revenue-stream public-view wildcard
  projection.
- [x] Replace and parity-check the prediction-accuracy public-view wildcard
  projection.

The integrated focused selection passes 386 tests. Ruff, compilation, report
inventories, capability validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-operations-governance-contracts.json).

Checklist: 1,558 complete / 25 open (1,583 total); TODO: 261 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Latest local continuation — operations projections, tactical sessions, and SDK errors — 28 October 2026

- [x] Add exact response and page/cursor validation to the location-scoped
  governance tactical-session reader.
- [x] Replace and parity-check the feature-importance public-view projection.
- [x] Replace and parity-check the livestock-feed-intake public-view
  projection.
- [x] Replace and parity-check the organic-compliance-dashboard projection.
- [x] Align Python and TypeScript application error-envelope parsing while
  preserving framework 422 details.

The integrated selection passes 578 Python tests and 131 TypeScript tests;
build, Ruff, compilation, report inventories, matrix validation, and diff
checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-operations-governance-sdk-error-contracts.json).

Checklist: 1,563 complete / 25 open (1,588 total); TODO: 266 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.

### Latest local continuation — report projections and operating-pilot response — 29 October 2026

- [x] Replace all five ecological-modeling report wildcards with the exact
  ordered public-view columns and preserve output, scope, and aggregates.
- [x] Replace the Bio Factory regional-input wildcard with the complete
  schema-backed public-view projection and preserve payload behavior.
- [x] Replace the Open Source Impact wildcard with its complete public-view
  projection and preserve counts and reuse totals.
- [x] Add a strict, location-bound own-learning-plans response contract with
  pagination, ordering, review metadata, and sanitized-failure validation.

The approved synthetic selection passes 41 tests. Ruff, compilation, all three
report inventories, capability-matrix validation, and diff checks pass. No
database, provider, candidate, legacy service, or production resource was
used. These source checks do not prove populated-data parity, content privacy,
live OIDC, or tenant isolation. Evidence:
[batch](builds/2026-10-29-recovery/kernel-parallel-ecological-biofactory-operating-pilot-contracts.json).

Checklist: 1,567 complete / 25 open (1,592 total); TODO: 266 checked / 16
open. The capability matrix remains 67 rows (24 baseline-retained,
7 deployed, 36 prepared), with 98 strict private Gateway response contracts.
MAN-CAP acceptance and classifications remain unchanged.

### Latest local continuation — wellbeing, governance, and scaling projections — 29 October 2026

- [x] Replace the network-scaling target wildcard with the exact 20-column
  public-view projection; preserve date bounds, network scope, and totals.
- [x] Replace governance-inclusion `SELECT *` with all 16 public-view columns
  while retaining shared null-location observations and report aggregates.
- [x] Replace the EBF scorecard summary wildcard with its 17-column view
  projection and preserve the pillar payload.
- [x] Replace financial-sustainability `SELECT *` with all 21 public-view
  fields and preserve its location/date filters and payload.

The focused mocked selection passes 4 tests. Ruff, compilation, all three
report inventories, capability-matrix validation, and diff checks pass. No
database, provider, candidate, legacy service, or production resource was
used. Evidence:
[batch](builds/2026-10-29-recovery/kernel-parallel-report-projection-batch-2.json).

Checklist: 1,571 complete / 25 open (1,596 total); TODO: 270 checked / 16
open. Capability classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows; strict private Gateway response contracts
remain 98. MAN-CAP acceptance is unchanged.

### Latest local continuation — report projections and governance readback — 29 October 2026

- [x] Replace token-reward distribution and calibration wildcards with exact
  ordered projections; preserve location scope, ordering, totals, and payload.
- [x] Replace the capital-provider utility wildcard with its complete
  16-column public-view projection and preserve location/order behavior.
- [x] Replace stakeholder representation `SELECT *` with all 8 public-view
  columns and the equity-distribution wildcard with its 10-column projection,
  preserving network-shared rows and aggregate output.
- [x] Publish and enforce a strict request-bound response contract for private
  governance assignment-proposal pages, including timestamp, order, cursor,
  scope, page-bound, and sanitized no-store failure checks.

The combined synthetic/mock selection passes 22 tests. Ruff, Python
compilation, all three report inventories, capability-matrix validation, and
diff checks pass. No database, migration, candidate, legacy service, provider,
or production resource was used. The checks do not establish populated-data
parity, content privacy, live OIDC, or tenant isolation. Evidence:
[batch](builds/2026-10-29-recovery/kernel-parallel-governance-and-report-projection-batch-3.json).

Checklist: 1,575 complete / 25 open (1,600 total); TODO: 274 checked / 16
open. Capability classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows; strict private Gateway response contracts now
total 99. MAN-CAP acceptance is unchanged.

### Latest local continuation — wellbeing risk, capital, and governance reports — 29 October 2026

- [x] Replace the risk-mitigation wildcard with all 20 migration-035 view
  fields; preserve location/date filtering, null review dates, ordering, and
  serialized rows.
- [x] Replace the scaling-roadmap wildcard with its 16 migration-035 fields;
  preserve location plus shared rows, date bounds, ordering, and totals.
- [x] Replace the capital-efficiency scenario wildcard with its complete
  16-column migration-036 projection.
- [x] Replace the regenerative-efficiency observation wildcard with its
  complete 16-column migration-036 projection.
- [x] Replace governance-throughput `SELECT *` with all 16 migration-036
  fields; preserve selected-location/shared rows and average latency.

The focused synthetic/mock selection passes 4 tests. Ruff, Python
compilation, all report inventories, capability-matrix validation, and diff
checks pass. No database, migration, candidate, legacy service, provider, or
production resource was used. These checks do not establish populated-data
parity, tenant isolation, content privacy, or live OIDC. Evidence:
[batch](builds/2026-10-29-recovery/kernel-wellbeing-risk-capital-governance-projections.json).

Checklist: 1,580 complete / 25 open (1,605 total); TODO: 279 checked / 16
open. Capability classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows; strict private Gateway response contracts
remain 99. MAN-CAP acceptance is unchanged.

### Latest local continuation — Bio Factory public report projections — 29 October 2026

- [x] Replace the Bio Factory batch wildcard with all 21 migration-043 fields.
- [x] Replace input-provenance `SELECT *` with its complete 20-column view.
- [x] Replace recipe-library `SELECT *` with its complete 23-column view.
- [x] Replace quality-test `SELECT *` with its complete 18-column view.

The focused synthetic selection passes 1 test. It validates exact field order,
location-plus-network and date predicates, output payloads, and report
aggregates. Ruff, Python compilation, report inventories, matrix validation,
and diff checks pass. No database/provider or candidate was used. Evidence:
[batch](builds/2026-10-29-recovery/kernel-bio-factory-report-projection-batch.json).

Checklist: 1,584 complete / 25 open (1,609 total); TODO: 283 checked / 16
open. Capability classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows; strict private Gateway response contracts
remain 99. MAN-CAP acceptance is unchanged.

### Latest local continuation — scaling-economics report projections — 29 October 2026

- [x] Replace both network and location `v_public_farm_launch_unit_economics`
  wildcards with its complete 27-column migration-040 projection.
- [x] Replace adoption-barrier wildcard with all 17 public-view columns,
  preserving selected/shared scope, date filtering, and active counts.
- [x] Replace perpetual-value stress wildcard with all 20 public-view
  columns, preserving selected/shared scope, date filtering, and watchlist.

The focused synthetic selection passes 1 test. It validates exact order,
network/location query branches, request scope and dates, sorting, output
payloads, and aggregates. Ruff, Python compilation, report inventories,
capability validation, and diff checks pass. No database/provider or candidate
was used. Evidence:
[batch](builds/2026-10-29-recovery/kernel-scaling-report-projection-batch.json).

Checklist: 1,587 complete / 25 open (1,612 total); TODO: 286 checked / 16
open. Capability classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows; strict private Gateway response contracts
remain 99. MAN-CAP acceptance is unchanged.

### Latest local continuation — private report-export operator-console flow — 29 October 2026

- [x] Add a bounded, exact-location eligible-snapshot database projection
  with the independent export `read` grant and reviewed-status/hash/size filters.
- [x] Bind the strict Gateway route, page contract, no-store validation errors,
  route policy, and runtime-function allowlist to migration 684.
- [x] Add a console flow that keeps read/create/download grants independent,
  retries with a stable session idempotency key, polls active requests, and
  only downloads completed artifacts.
- [x] Apply/replay migrations 683 and 684 on disposable PostgreSQL 16 and
  verify exact scope, separate grants, eligibility, pagination, and role limits.

Focused migration, Gateway, route-policy, OpenAPI, and console checks pass 88
tests. Ruff, runtime SQL inventory, provider-boundary, capability-matrix,
JavaScript syntax, and diff checks pass. The disposable acceptance is
network-disabled; candidate and legacy databases are untouched. Evidence:
[migration acceptance](builds/2026-10-29-recovery/report-snapshot-export-migration-disposable.json),
[focused checks](builds/2026-10-29-recovery/report-snapshot-export-console-contracts.json).

Checklist: 306 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged.

### Latest local continuation — public location IRI JSON-LD contract — 29 October 2026

- [x] Define a strict JSON-LD response model for the exact public location
  projection, including bounded identity/version fields and optional lineage.
- [x] Verify canonical version linkage and recompute the public projection
  digest before returning JSON-LD with its documented media type.
- [x] Preserve nullable address fields, omitted absent predecessor, no-store
  headers, and nonrevealing private/unavailable behavior under focused checks.

The focused public IRI Gateway selection passes 13 tests. Ruff, Python
compilation, and `git diff --check` pass. No database, provider, candidate, or
legacy service was used. This does not establish live IRI/populated-data parity,
external JSON-LD interoperability, or tenant/RLS isolation. Evidence:
[contract checks](builds/2026-10-29-recovery/public-location-iri-jsonld-response-contract.json).

Checklist: 309 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged.

### Latest local continuation — Data Stream draft-create contract — 29 October 2026

- [x] Publish the source-aligned 15-value post-type allowlist and strict
  location/title/content/expiry request contract in OpenAPI.
- [x] Reject undeclared identity, lifecycle, metadata, and source fields before
  invoking the database service; return sanitized no-store validation errors.
- [x] Validate the created post UUID and preserve the minimal `post_id` success
  payload, tenant authorization, and default draft-only creation path.

The focused Gateway create/auth selection passes 39 tests. Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database,
provider, candidate, or legacy service was used. Live OIDC/browser and populated
data acceptance remain open. Evidence:
[focused checks](builds/2026-10-29-recovery/data-stream-create-gateway-contract.json).

Checklist: 312 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged.

### Latest local continuation — stakeholder identity write contracts — 29 October 2026

- [x] Add migration-aligned proposal and decision request/response contracts.
- [x] Publish strict OpenAPI schemas and reject invalid input before invoking
  the service, with generic no-store errors.
- [x] Validate proposal/decision output and retain the independent-review
  service boundary.

The focused stakeholder-identity Gateway/service/OpenAPI checks pass 36 tests;
Ruff, Python compilation, matrix validation, and diff checks pass. Mock-only;
no database, provider, candidate, legacy, or production resource was used.
Live identity-provider/browser behavior, populated data, and tenant/RLS
acceptance remain open. Evidence:
[focused checks](builds/2026-10-29-recovery/stakeholder-identity-write-gateway-contracts.json).

Checklist: 315 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged; strict private Gateway response contracts now
total 103.

### Latest local continuation — signed trend-forecast creation contract — 29 October 2026

- [x] Define and document strict request bounds for the signed forecast writer.
- [x] Validate created and reused response variants against the requested
  location, metric, and horizon.
- [x] Add focused no-store and service-boundary regressions.

The focused Gateway and forecast-compute selection passes 66 tests. Ruff,
Python compilation, and diff checks pass. Synthetic/fake dependencies only;
no live service or database was used. Evidence:
[focused checks](builds/2026-10-29-recovery/trend-forecast-create-gateway-contract.json).

Checklist: 318 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged; strict private Gateway response contracts now
total 104.

### Latest local continuation — registered AI-synthesis task receipt contract — 29 October 2026

- [x] Document strict registered task and summary inputs and enforce their
  cross-field pairing before dispatch.
- [x] Validate exact, location-bound authorization receipt output.
- [x] Keep idempotent retry status and no-store errors intact.

The focused Gateway task-request/draft selection passes 30 tests. Ruff,
compilation, matrix validation, and diff checks pass. No live DB/provider was
used. Evidence:
[focused checks](builds/2026-10-29-recovery/ai-synthesis-task-receipt-gateway-contract.json).

Checklist: 321 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged; strict private Gateway response contracts now
total 105.

### Latest local continuation — governance assignment review queue contract — 29 October 2026

- [x] Add the strict migration-aligned review item/page contract.
- [x] Enforce page location, limit, order, uniqueness, and cursor invariants.
- [x] Preserve no-store handling and reviewer authorization.

The focused governance queue and pagination/OpenAPI selection passes 24 tests.
Ruff, compilation, and diff checks pass. No live database/provider was used.
Evidence:
[focused checks](builds/2026-10-29-recovery/governance-assignment-review-queue-contract.json).

Checklist: 324 checked / 16 open. Capability classifications and MAN-CAP
acceptance remain unchanged; strict private Gateway response contracts now
total 106.

## Completed in the 29 October operations-contract batch

- [x] Publish strict Field Collector collection-detail OpenAPI and runtime
  contracts with request-bound IDs, bounded flexible payloads, review-event
  limits, and sanitized no-store errors.
- [x] Add scheduler CLI support for the driver-instance input required by
  sensor plans, with offline missing-input rejection and disabled output.
- [x] Correct resource-efficiency aggregation and location binding in a
  disposable PostgreSQL 16 check using multiple event rows and two crop types.
- [x] Record focused test and static-check evidence for this batch in
  `builds/2026-10-29-recovery/kernel-next-operations-contract-batch.json`.

## Completed in the 29 October reliability and projection continuation

- [x] Reject NaN, infinities, zero, and negative event-worker poll intervals
  before feature evaluation or database access; preserve finite positive
  polling recovery behavior.
- [x] Use the exact migration-284 competitive-health view projection and
  verify ordered columns, UUID binding, payload normalization, and not-found
  behavior with focused mock-cursor tests.
- [x] Use migration 212's exact roadmap-overview view projection and verify
  every status/entity-type filter combination, binding order, and serialized
  row contract with mock cursors.
- [x] Validate EventBus CLI batch-size bounds before connections while
  retaining the notification-only outbox's 500-item limit.

Checklist: 370 checked / 16 open (8 code work groups and 8 owner/environment
gates remain). Capability acceptance remains partial; evidence is recorded in
`batches.md` and the capability matrix.

## Completed in the 29 October analytics and SDK continuation

- [x] Replace the capability-dashboard wildcard with the migration-207
  ordered view projection and verify guild filter/order/payload parity.
- [x] Validate Predictive BPM CLI numbers before database acquisition,
  retaining zero and threshold boundary values.
- [x] Validate Ecocredit TypeScript gRPC list limits locally and keep cursor
  forwarding unchanged.

Checklist: 373 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/kernel-analytics-and-ecocredit-input-contracts.json`.

## Completed in the 29 October public read and verify preflight continuation

- [x] Pin the public governance cockpit to its migration-defined aggregate
  projection while preserving the existing payload.
- [x] Block generic REST SDK mutations for report, NOI, attestation, and export
  audit projections while preserving reads and unrelated writes.
- [x] Reject malformed report-snapshot verification identifiers before
  database acquisition; accept UUID and SHA-256 forms.

Checklist: 376 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/kernel-public-read-and-verify-preflight.json`.

## Completed in the 29 October Data Stream signer CLI continuation

- [x] Bound signer CLI batches to 1–100 and verify malformed values fail
  before database acquisition while valid limits are forwarded unchanged.

Checklist: 377 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/datastream-signer-cli-batch-bound.json`.

## Completed in the 29 October sensor stream continuation

- [x] Bound CLI and direct stream-processing batches to 1–500 and verify
  invalid values fail before worker construction/database acquisition.

Checklist: 378 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/stream-processor-batch-size-preflight.json`.

## Completed in the 29 October Gateway OpenAPI security continuation

- [x] Document the session-cookie requirement for private operator APIs and
  authenticated session/logout endpoints while preserving public auth flows.

Checklist: 379 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/gateway-openapi-operator-cookie-security.json`.

## Completed in the 29 October PRM outcome-correlation continuation

- [x] Pin the outcome-correlation reader to migration 196's exact seven-column
  view contract and verify order plus row serialization.

Checklist: 380 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/prm-outcome-correlation-projection.json`.

## Completed in the 29 October strategy advantage projection continuation

- [x] Pin the strategy advantage performance reader to migration 286's exact
  15-column view shape and verify scope, order, and UUID serialization.

Checklist: 381 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/strategy-advantage-performance-projection.json`.

## Completed in the 29 October standard Gateway auth documentation continuation

- [x] Publish API-key/capability-token alternatives for private Data Stream
  and detailed health routes without marking public or device-token routes.

Checklist: 382 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/gateway-standard-auth-openapi.json`.

## Completed in the 29 October marketplace pagination continuation

- [x] Bound marketplace list pages and reject invalid CLI/service pagination
  before PostgreSQL connection or cursor acquisition.

Checklist: 383 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/marketplace-pagination-preflight.json`.

## Completed in the 29 October value-stream projection continuation

- [x] Pin value-stream performance reads to migration 210's ordered 16-column
  contract and verify scope, sort, and UUID/datetime serialization.

Checklist: 384 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/value-stream-performance-projection.json`.

## Completed in the 29 October analytics, CLI, and Gateway continuation

- [x] Pin value-stream summary and coordination-health readers to the exact
  ordered migration-defined view projections and preserve filters, ordering,
  empty results, and date/UUID serialization.
- [x] Reject invalid graph-projection CLI values before opening PostgreSQL,
  using the service's depth/node bounds and the schema's UUID/edge-type rules.
- [x] Add strict OpenAPI and runtime response contracts for the four waste
  capture operations, including location binding, idempotent 201/200 status,
  and sanitized no-store failures.
- [x] Record focused evidence and reconcile the capability, batch, progress,
  and active TODO ledgers.

Checklist: 388 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/analytics-view-projection-contracts.json`,
`builds/2026-10-29-recovery/graph-projection-cli-preflight.json`, and
`builds/2026-10-29-recovery/waste-capture-response-contracts.json`.

## Completed in the 29 October stakeholder/cooperative projection continuation

- [x] Pin stakeholder engagement summary to migration 217's 16-column shape.
- [x] Pin commitment detail and health-list reads to migration 216's 14-column
  shape, retaining optional filters and ordering.
- [x] Pin cooperative governance health to migration 222's seven-column shape.
- [x] Record mock-cursor evidence and reconcile batch/progress/capability logs.

Checklist: 392 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/analytics-stakeholder-cooperative-view-projections.json`.

## Completed in the 29 October precision-irrigation CLI continuation

- [x] Preflight priority against migration 146's 0–100 constraint before DB
  access.
- [x] Parse and validate readings as a JSON object before connecting.
- [x] Parse schedule start timestamps before connecting and preserve valid
  datetime forwarding.

Checklist: 395 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/precision-irrigation-cli-preflight.json`.

## Completed in the 29 October governance proposal lineage continuation

- [x] Append `created_at` in a forward migration so the existing list ordering
  is executable without altering migration 246.
- [x] Use an explicit 24-column proposal lineage projection in detail/list
  readers.
- [x] Verify transactional apply/replay and the real ordered service query on
  disposable PostgreSQL 16; leave candidate and legacy databases untouched.

Checklist: 398 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/governance-proposal-created-at-disposable.json`.

## Completed in the 29 October business-canvas response continuation

- [x] Define exact OpenAPI/runtime contracts for caller-authored and generated
  draft creation, including created-versus-replayed status.
- [x] Bind location and enforce the source-defined status, provenance, block,
  timestamp, version, UUID, and replay fields.
- [x] Verify malformed service output is rejected with sanitized no-store
  errors using focused mocked routes.

Checklist: 401 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/business-canvas-draft-create-contracts.json`.

## Completed in the 29 October CRISP, pollinator, and governance-tension continuation

- [x] Reject malformed, impossible, noncanonical, and reversed CRISP periods
  before database access while preserving canonical valid periods
  ([evidence](builds/2026-10-29-recovery/crisp-cli-period-preflight.json)).
- [x] Add strict migration-aligned pollinator observation create/replay
  response validation, request binding, OpenAPI schemas, and sanitized no-store
  failures ([evidence](builds/2026-10-29-recovery/pollinator-observation-create-response-contract.json)).
- [x] Add migration 688 for the missing governance-tension `created_at`
  projection, pin service reads, and prove apply/replay plus real scoped sort
  on disposable PostgreSQL 16
  ([evidence](builds/2026-10-29-recovery/governance-tension-created-at-disposable.json)).
- [x] Refresh runtime SQL inventory and reconcile capability/progress records.

Checklist: 405 checked / 16 open. Capability matrix: 67 rows; 24
baseline-retained, 7 deployed, 36 prepared. Strict private Gateway response
contracts: 123.

## Completed in the 29 October pesticide and strategy-fit continuation

- [x] Validate the private pesticide-report create/replay response against
  migration 620, bind request scope and fields, and verify sanitized errors
  ([evidence](builds/2026-10-29-recovery/pesticide-impact-create-response-contract.json)).
- [x] Pin the strategy-fit view projection in all three readers, preserve
  filters/order/output, and verify mock-cursor parity
  ([evidence](builds/2026-10-29-recovery/strategy-advantage-fit-projections.json)).
- [x] Refresh the runtime SQL inventory and reconcile progress records.

Checklist: 408 checked / 16 open. Capability matrix: 67 rows; 24
baseline-retained, 7 deployed, 36 prepared. Strict private Gateway response
contracts: 124.

## Completed — contracts and analytics projection acceptance, 29 October

- [x] Pin the stakeholder landscape reader to migration 316's ordered columns
  and fix its status alias.
- [x] Preflight prediction CLI UUIDs, aware timestamps, bounded text, and
  `NUMERIC(20,8)` values before opening PostgreSQL.
- [x] Add strict, request-bound Delphi study draft and consent create/replay/
  decision response contracts.
- [x] Pin internal governance, strategy execution, stakeholder representation,
  and equity view projections to their migration contracts.
- [x] Pin both stakeholder-decision lineage reads to migration 229's
  projection and bind Delphi recommendation-draft output to its strict schema
  and requested study.
- [x] Pin governance link/registry/assignment, tactical health, and strategy
  execution reads to their migration-defined projections.
- [x] Refresh stale Directus permission and report-helper source inventories
  identified by PR #71 CI; local freshness gates now pass.
- [x] Test the migration-316 stakeholder list projection and status filter.
- [x] Test prediction CLI UUID/date/numeric/text preflight before DB access.
- [x] Test Delphi study-draft create/replay response schema and binding.
- [x] Test Delphi consent create/replay and decision response schemas.
- [x] Test the internal governance-cockpit projection against migration 249.
- [x] Test the strategy execution projection against migration 208.
- [x] Test stakeholder representation/equity projections and record grouped
  evidence.
- [x] Test stakeholder-decision service projections and filter/order behavior.
- [x] Test Delphi recommendation-draft schema, study binding, lifecycle, and
  sanitized malformed-output handling.
- [x] Test governance link/registry/assignment, tactical health, and strategy
  execution projections with focused mock-cursor checks.

The approved offline grouped selection passes 173 tests. Static checks pass:
Ruff, compilation, Directus permission inventory, report-helper scope
inventory, runtime SQL inventory, capability matrix, and diff. Tests use
synthetic/mocked data only; no database, candidate, legacy service, or external
provider was used. Checklist: 425 checked / 16 open. Capability matrix: 67
rows; 24 baseline-retained, 7 deployed, 36 prepared. Strict private Gateway
response contracts: 128. Hosted CI must rerun after push to verify the
inventory refresh. Evidence:
`builds/2026-10-29-recovery/kernel-next-contract-projection-checks.json`.

## In progress — Delphi review-decision response contracts, 29 October

- [x] Declare strict six-field response schemas for recommendation and
  minority-report review decisions, bind record IDs and decisions to the
  request, and enforce the corresponding resulting status.
- [x] Add/run focused mocked tests for OpenAPI fields, response binding,
  decision/status consistency, and sanitized no-store malformed results.

Twelve focused checks pass. Source changes pass Ruff, Python compilation, and
diff checks. Strict private Gateway response contracts total 130. Checklist:
427 checked / 16 open. Evidence:
`builds/2026-10-29-recovery/delphi-review-decision-response-contracts.json`.

## In progress — Delphi study lifecycle response contracts, 29 October

- [x] Declare strict open/close transition response fields and validate
  request-bound study/location IDs, resulting action status, and timestamps.
- [x] Declare a strict stopping-evaluation response and validate item fields,
  result enums, aggregate stop-state consistency, and path binding.
- [x] Publish the response schemas in OpenAPI and sanitize malformed service
  results without changing lifecycle transitions.
- [x] Add/run focused mocked tests for OpenAPI fields, valid lifecycle results,
  malformed result rejection, location/study binding, and no-store errors.

The focused lifecycle response selection passes 20 tests. Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database
or provider was used. Checklist: 431 checked / 16 open; strict private Gateway
response contracts total 133. Evidence:
`builds/2026-10-29-recovery/delphi-study-lifecycle-response-contracts.json`.

## Completed — operating-pilot competency lifecycle response contracts, 29 October

- [x] Add strict OpenAPI/runtime response models for competency draft create,
  revision, submission, and independent review.
- [x] Verify request binding, distinct revision IDs, first-write lifecycle,
  replay, review decisions, and sanitized no-store failures with focused tests.
- [x] Record machine-readable evidence and reconcile the progress ledgers.

The approved focused selection passes 22 tests; Ruff, Python compilation,
capability-matrix validation, and diff checks pass. No database or provider was
used. Checklist: 459 checked / 16 open; strict private Gateway response
contracts total 157. Evidence:
`builds/2026-10-29-recovery/operating-pilot-competency-lifecycle-response-contracts.json`.

## Completed — operating-pilot learning-plan review and activation responses, 29 October

- [x] Publish strict OpenAPI/runtime response models for independent learning-
  plan review and activation.
- [x] Verify location/path binding, approval/rejection/activation lifecycle,
  replay, and sanitized no-store handling with focused tests.
- [x] Record machine-readable evidence and reconcile the progress ledgers.

The approved focused selection passes 13 tests; Ruff, Python compilation, and
diff checks pass. No database or provider was used. Checklist: 462 checked /
16 open; strict private Gateway response contracts total 159. Evidence:
`builds/2026-10-29-recovery/operating-pilot-learning-plan-review-activation-response-contracts.json`.

## Completed — operating-pilot learning-plan write responses, 29 October

- [x] Add strict OpenAPI/runtime response models for draft create, revision,
  and submission.
- [x] Verify path binding, timestamp and lifecycle invariants, replay, create
  status, and sanitized no-store behavior across the lifecycle.
- [x] Record machine-readable evidence and reconcile progress ledgers.

The approved focused lifecycle selection passes 32 tests; Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database
or provider was used. Checklist: 465 checked / 16 open; strict private Gateway
response contracts total 162. Evidence:
`builds/2026-10-29-recovery/operating-pilot-learning-plan-write-response-contracts.json`.

## Completed — operating-pilot work-claim lifecycle responses, 29 October

- [x] Add strict OpenAPI/runtime response models for proposal, independent
  review, and separate allocation.
- [x] Verify path binding, lifecycle states, replay, HTTP status, and sanitized
  no-store failures with focused Gateway checks.
- [x] Record machine-readable evidence and reconcile progress ledgers.

The approved focused selection passes 18 tests; Ruff, Python compilation,
capability-matrix validation, and diff checks pass. No database or provider was
used. Checklist: 468 checked / 16 open; strict private Gateway response
contracts total 165. Evidence:
`builds/2026-10-29-recovery/operating-pilot-work-claim-lifecycle-response-contracts.json`.

## Completed — operating-pilot resource fulfillment response, 29 October

- [x] Add the strict OpenAPI/runtime fulfillment response and bind request
  identities to the location/resource path.
- [x] Preserve the migration's closed/fulfilled lifecycle and exact replay
  while returning only a sanitized no-store error on malformed output.
- [x] Run the approved focused checks, record evidence, and reconcile ledgers.

The focused route selection passes 7 tests; Ruff, Python compilation,
capability-matrix validation, and diff checks pass. No database or provider was
used. Checklist: 471 checked / 16 open; strict private Gateway response
contracts total 166. Evidence:
`builds/2026-10-29-recovery/operating-pilot-resource-fulfillment-response-contract.json`.

## Completed — farm-activity draft and transition response contracts, 29 October

- [x] Add exact OpenAPI/runtime response contracts for draft create/edit and
  the six supported lifecycle commands.
- [x] Verify response field allowlists, route identity/action binding,
  draft-only writes, state transitions, reason requirements, and HTTP 201
  create documentation.
- [x] Verify malformed service output fails closed with sanitized no-store
  behavior and record the focused evidence.

The approved focused Gateway route suite passes 45 tests; Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database or
provider was used. Checklist: 474 checked / 16 open; strict private Gateway
response contracts total 169. Evidence:
`builds/2026-10-29-recovery/farm-activity-write-response-contracts.json`.

## Completed — operating-pilot work-claim review/allocation queue contracts, 29 October

- [x] Add strict OpenAPI/runtime schemas for both migration-backed work-claim
  queues.
- [x] Validate exact item fields, the separate identity exposure policy,
  request-bound location/page metadata, SQL ordering, and continuation rules.
- [x] Verify tenant denial and sanitized no-store handling; add/run the
  approved focused route/pagination selection and record evidence.

The focused Gateway/pagination selection passes 70 tests; Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database or
provider was used. Checklist: 477 checked / 16 open; strict private Gateway
response contracts total 171. Evidence:
`builds/2026-10-29-recovery/operating-pilot-work-claim-queue-contracts.json`.

## Completed — business-canvas edit response contracts, 29 October

- [x] Add strict OpenAPI/runtime response models for both draft edit routes.
- [x] Verify path/version/time/replay and allowlisted block/metadata binding,
  including sanitized no-store rejection behavior.
- [x] Record focused test evidence and update the capability/progress ledgers.

The approved mock-only Gateway selection passes 71 tests; Ruff, Python
compilation, capability-matrix validation, and diff checks pass. No database
or provider was used. Checklist: 480 checked / 16 open; strict private
Gateway response contracts total 173. Evidence:
`builds/2026-10-29-recovery/business-canvas-edit-response-contracts.json`.

## Completed — competency review queue and PESTEL projections, 29 October

- [x] Add the strict migration-577 competency review queue response contract.
- [x] Replace PESTEL wildcard reads with the migration-203 explicit columns.
- [x] Verify response, ordering, pagination, filtering, and serialization using
  the approved mock-only checks; record evidence and update progress ledgers.

The focused selection passes 25 Gateway checks, one operator-console
offset-cap check, and three PESTEL checks. Ruff, Python compilation,
capability validation, and diff checks pass; no database or provider was used.
Checklist: 483 checked / 16 open; strict private Gateway response contracts
total 174. Evidence:
`builds/2026-10-29-recovery/competency-queue-and-pestel-projections.json`.

## Completed — adoption review, competitive projections, and trust CLI, 29 October

- [x] Add the strict migration-520 adoption-program review queue response,
  consent-policy coherence checks, request binding, and bounded continuation.
- [x] Align the operator console with the response contract and identify when
  additional records are beyond the 10,000-offset cap.
- [x] Replace the two competitive-report wildcard reads with migration-backed
  explicit columns and preserve filtering, ordering, and row cleanup.
- [x] Fail malformed stakeholder-trust UUID CLI inputs before database access
  and normalize supplied valid identifiers.
- [x] Run approved offline regressions and record evidence.

The focused selection passes 23 Gateway, two console, two competitive-report,
20 CLI preflight, five unified-CLI parameter cases, and one JavaScript syntax
check (53 total). Ruff, compilation, matrix validation, and diff checks pass.
No database or provider was used. Checklist: 488 checked / 16 open; strict
private Gateway response contracts total 175. Evidence:
`builds/2026-10-29-recovery/adoption-review-competitive-projections-trust-cli.json`.

## Completed — adoption drafts, benchmark projection, and energy CLI, 29 October

- [x] Add the strict migration-520 adoption-drafts page and item response,
  including consent tuple, draft-only, SQL order, and offset-cap invariants.
- [x] Update the operator console to verify page echo and report capped results.
- [x] Replace the customer-value benchmark wildcard projection with explicit
  migration-285 columns and verify payload parity.
- [x] Validate energy CLI dates before connection acquisition while preserving
  optional date behavior.
- [x] Run approved focused checks and record the evidence.

The focused selection passes 14 Gateway, one console, one benchmark, eight CLI,
and one JavaScript syntax check (25 total). Ruff, compilation, matrix
validation, and diff checks pass. No database or provider was used. Checklist:
493 checked / 16 open; strict private Gateway response contracts total 176.
Evidence:
`builds/2026-10-29-recovery/adoption-drafts-benchmark-energy-preflight.json`.

## Completed — adoption redesign, grievance health, and crop-date preflight, 29 October

- [x] Publish a strict, request-bound migration-519 redesign queue contract,
  validate its stable order, and stop continuations at offset 10,000.
- [x] Validate the queue response in the operator console and report when the
  remaining records lie beyond the supported paging range.
- [x] Pin the internal grievance-health reader to migration 218's exact
  21-column projection while preserving filters, order, serialization, and
  the current access boundary.
- [x] Parse crop-rotation impact dates before the CLI can open PostgreSQL.
- [x] Run the approved offline checks, refresh SQL inventory, and record the
  evidence and capability/progress counters.

The combined selection passes 120 tests with two skips. Ruff, compilation,
capability validation, runtime SQL inventory freshness, provider-boundary and
dependency-group checks, and diff checks pass. No database/provider or
candidate/legacy state was used. Checklist: 498 checked / 16 open; the matrix
remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 177
strict private Gateway response contracts. Evidence:
`builds/2026-10-29-recovery/adoption-redesign-grievances-crop-date.json`.

## Completed — consent, readiness review, and CLI preflight, 29 October

- [x] Pin consent check/list readers to migration 320's exact projection and
  verify filters, parameter order, sort, and serialized payload.
- [x] Reject malformed consent UUIDs before database acquisition and
  canonicalize valid inputs.
- [x] Preflight farmer date/datetime values and digital-finance evidence JSON
  before opening PostgreSQL.
- [x] Publish the strict migration-516 adopter-readiness queue schema and
  validate location/page binding, levels, text, timestamps, order, and IDs.
- [x] Bound queue continuation at 10,000 and align console validation and
  capped-results messaging.
- [x] Run approved offline checks, refresh the SQL inventory, and record
  evidence plus progress counters.

The combined selection passes 157 tests with four skips. Ruff, compilation,
capability validation, runtime SQL inventory, provider-boundary and dependency
checks, and diff checks pass. No database/provider or candidate/legacy state
was used. Checklist: 504 checked / 16 open; matrix remains 67 rows
(24 baseline-retained, 7 deployed, 36 prepared), with 178 strict private
Gateway response contracts. Evidence:
`builds/2026-10-29-recovery/consent-readiness-cli-preflight.json`.

## Completed — governance CLI, carbon-credit source, and configuration review, 29 October

- [x] Reject malformed or non-object governance-domain constraints before
  database acquisition and preserve decoded-object semantics.
- [x] Pin the annual carbon-credit climate-summary lookup to migration 028's
  location, reporting year, verified/published status, and exact projection.
- [x] Validate migration-517 configuration-review item/page contracts,
  request binding, ordering, IDs, payload bounds, and capped continuation in
  the Gateway and operator console.
- [x] Run the approved 110-test mock-only selection and refresh/check SQL
  inventory; record evidence and progress counters.

Ruff, compilation, capability-matrix validation, provider-boundary,
dependency-group, SQL-inventory, and diff checks pass. No database, provider,
candidate, or legacy state was used; no migration was applied. Checklist:
511 checked / 16 open; strict private Gateway response contracts total 180.
Evidence:
`builds/2026-10-29-recovery/governance-cli-carbon-lookup-configuration-review-queue.json`.

## Completed — consent expiry, capacity projection, and operating-pilot summary, 29 October

- [x] Require and preflight an explicit timezone on consent expiry datetimes
  before PostgreSQL access.
- [x] Pin operating-capacity gap reads to migration 251's exact ten-column
  projection and verify optional scope/bind/order/payload behavior.
- [x] Validate the strict migration-461 operating-pilot summary shape, path
  location, suppression/nullability, and authenticated error behavior.
- [x] Run 211 approved focused checks and refresh/check SQL inventory; record
  evidence and progress updates.

Ruff, compilation, capability-matrix validation, provider-boundary,
dependency-group, SQL-inventory, and diff checks pass. No database, provider,
candidate, or legacy state was used; no migration was applied. Checklist:
515 checked / 16 open; strict private Gateway response contracts total 181.
Evidence:
`builds/2026-10-29-recovery/consent-capacity-operating-pilot-contracts.json`.

## Completed — equipment timestamps, carbon balance, and learning-plan review, 29 October

- [x] Require timezone-aware equipment usage timestamps and reject malformed
  `--start`/`--end` before database acquisition.
- [x] Pin carbon-balance annual climate-summary reads to migration 028's exact
  fields for both requested-year and latest-year paths.
- [x] Enforce migration-610 learning-plan review page/item response schemas,
  source-defined JSON-array limits, path binding, ordering, uniqueness, and
  continuation consistency.
- [x] Run the approved 218-test selection and refresh/check SQL inventory;
  record evidence and progress updates.

CI security Ruff, compilation, capability-matrix, provider-boundary,
dependency-group, SQL-inventory, and diff checks pass. Default Ruff's remaining
`F841` is an existing unused capacity local in `equipment._update_utilization`
outside the changed CLI path. No database/provider, candidate, or legacy
state was used; no migration was applied. Checklist: 519 checked / 16 open;
strict private Gateway response contracts total 182. Evidence:
`builds/2026-10-29-recovery/equipment-carbon-balance-learning-queue-contracts.json`.

## Completed — yield, nutrient, and pollinator contracts, 29 October

- [x] Preflight `yield_monitoring record --date` as an ISO calendar date before
  database acquisition; pass valid dates as `date` objects and preserve omitted
  dates.
- [x] Make migration-601 nutrient summary order stable across input type, rate
  unit, and cost currency.
- [x] Add strict OpenAPI/runtime validation for migration-621 pollinator habitat
  capture creates and replays, including request binding and sanitized no-store
  errors.
- [x] Run 134 approved mock-only checks and refresh/check the runtime SQL
  inventory; record evidence and progress counters.

CI security Ruff, compilation, capability validation, provider-boundary,
dependency-group, SQL-inventory, and diff checks pass. No database/provider,
candidate, or legacy state was used; no migration was applied. Checklist:
523 checked / 16 open; strict private Gateway response contracts total 183.
Evidence:
`builds/2026-10-29-recovery/yield-nutrient-pollinator-contracts.json`.

## Completed — private coaching read contracts, 29 October

- [x] Add strict OpenAPI/runtime models for consent-filtered coaching
  participants and private own-session history, grounded in migrations 611 and
  612 and the session bounds from migration 253.
- [x] Bind both responses to the requested location and page, reject malformed
  or extra identity fields, and preserve existing coach authorization and
  tenant context.
- [x] Verify exact schemas, content bounds, SQL order, duplicate IDs,
  continuation, and sanitized no-store failures with 101 approved mock-only
  tests; refresh/check runtime SQL inventory.
- [x] Record evidence and progress counters; no database migration or rollout
  is required.

Default and CI-security Ruff, compilation, capability validation, runtime SQL
inventory, and diff checks pass. No database/provider, candidate, or legacy
state was used. Checklist: 527 checked / 16 open; strict private Gateway
response contracts total 185. Evidence:
`builds/2026-10-29-recovery/operating-pilot-coaching-read-contracts.json`.

## Completed — private own-demand read contract, 29 October

- [x] Publish the migration-561 private demand item/page projection in
  OpenAPI and enforce its source-defined bounds and lifecycle.
- [x] Bind location and pagination; validate exact count, continuation,
  unique IDs, SQL order, and the Gateway's 10,000-offset cap.
- [x] Preserve numeric JSON serialization, existing `read_own` authorization,
  signed tenant context, and sanitized no-store failures.
- [x] Run 42 approved mock-only checks; refresh/check runtime SQL inventory,
  capability matrix, source security lint, and evidence/progress records.

No database/provider, candidate, or legacy state was used; no migration was
applied. Checklist: 531 checked / 16 open; strict private Gateway response
contracts total 186. Evidence:
`builds/2026-10-29-recovery/operating-pilot-own-demand-read-contract.json`.

## Completed — independent demand-review response contract, 29 October

- [x] Publish migration 560's exact identity-free item/page schemas in
  OpenAPI and enforce the submitted-only review projection.
- [x] Bind location and pagination; check source bounds, totals, page length,
  descending SQL order, duplicate IDs, and the 10,000-offset cap.
- [x] Preserve `operating_pilot:review`, signed tenant context, no-store
  behavior, and sanitized errors while excluding narrative and identity.
- [x] Run 35 approved mock-only checks and refresh/check refactor evidence and
  inventories.

No database/provider, candidate, or legacy state was used; no migration was
applied. Checklist: 535 checked / 16 open; strict private Gateway response
contracts total 187. Evidence:
`builds/2026-10-29-recovery/operating-pilot-demand-review-response-contract.json`.

## Completed — independent resource-review response contract, 29 October

- [x] Publish migration 571's exact identity-blind item/page schemas in
  OpenAPI and enforce its source-defined fields and bounds.
- [x] Bind location and pagination; validate total, page count, continuation,
  unique request IDs, and `requested_by DESC, id DESC` ordering.
- [x] Preserve `operating_pilot:review`, signed tenant context, no-store
  behavior, and sanitized failures while excluding requester identity/receipts.
- [x] Run 35 approved mock-only checks and refresh/check refactor evidence and
  inventories.

No database/provider, candidate, or legacy state was used; no migration was
applied. Checklist: 539 checked / 16 open; strict private Gateway response
contracts total 188. Evidence:
`builds/2026-10-29-recovery/operating-pilot-resource-review-response-contract.json`.


## Completed — independent resource-fulfillment queue response contract, 29 October

- [x] Publish migration 573's exact identity-blind item/page response schema in OpenAPI and runtime validation.
- [x] Bind location and pagination; validate source bounds, count, continuation, uniqueness, and deterministic SQL order.
- [x] Preserve `operating_pilot:fulfill`, signed tenant context, read-only access, and sanitized no-store failures without exposing requester/fulfiller identities or receipt data.
- [x] Run 33 approved mock-only checks and refresh the refactor evidence and inventories.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 543 checked / 16 open; strict private Gateway response contracts total 189. Evidence: `builds/2026-10-29-recovery/operating-pilot-resource-fulfillment-queue-response-contract.json`.


## Completed — learning-plan activation queue response contract, 29 October

- [x] Publish migration 629's exact item/page schemas in OpenAPI and validate the activation queue response at runtime.
- [x] Bind location/page inputs; check source bounds, row count, continuation, unique IDs, eligible status, timestamps, and bounded JSON values.
- [x] Preserve the separate `operating_pilot:activate` grant and signed context with sanitized no-store failures.
- [x] Run 30 approved mock-only checks and refresh refactor evidence/inventories.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 547 checked / 16 open; strict private Gateway response contracts total 190. Evidence: `builds/2026-10-29-recovery/operating-pilot-learning-plan-activation-queue-response-contract.json`.


## Completed — solution-adoption event-summary response contract, 29 October

- [x] Publish migration 493's exact event-summary fields in OpenAPI and validate service output strictly at runtime.
- [x] Bind location/program IDs to the route and enforce the five-count cohort-suppression invariant.
- [x] Preserve the private exact-location read grant, signed context, privacy projection, and sanitized no-store failures.
- [x] Run 7 approved mock-only checks; refresh source, capability, and evidence records.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 551 checked / 16 open; strict private Gateway response contracts total 191. Evidence: `builds/2026-10-29-recovery/solution-adoption-event-summary-response-contract.json`.


## Completed — metadata-generation CLI JSON preflight, 29 October

- [x] Validate metadata JSON and its top-level object shape before importing or opening the database connection.
- [x] Reject non-standard numeric constants; pass valid objects unchanged to the resolver.
- [x] Preserve the resolver's successful output and return a clear exit-2 error for invalid input.
- [x] Run 9 approved mock-only checks and refresh refactor progress/evidence.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 554 checked / 16 open; strict private Gateway response contracts remain 191. Evidence: `builds/2026-10-29-recovery/metadata-api-generate-cli-json-preflight.json`.


## Completed — scale-gate review-detail response contract, 29 October

- [x] Publish migration 501's exact response fields in OpenAPI and enforce the private review detail at runtime.
- [x] Bind location/assessment to request paths; validate the gate enum, numeric comparator/threshold pair, measured values, sample size, and evidence JSON bounds.
- [x] Preserve the exact private review grant, signed context, evaluator-conflict boolean, and sanitized no-store errors without returning identity.
- [x] Run 21 approved mock-only checks and refresh capability, source-inventory, and evidence records.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 558 checked / 16 open; strict private Gateway response contracts total 192. Evidence: `builds/2026-10-29-recovery/scale-gate-review-detail-response-contract.json`.


## Completed — replication-review detail response contract, 29 October

- [x] Publish the exact migration-495 15-field private detail schema in OpenAPI and enforce it at runtime.
- [x] Bind the returned replication ID to the request; validate enums, bounded text/protocol, timestamp consistency, and response shape.
- [x] Preserve exact-location review authorization, signed context, no-store behavior, and sanitized malformed-result failures without exposing proposer identity.
- [x] Run 21 approved mock-only checks and refresh capability, source, and evidence records.

No database/provider, candidate, or legacy state was used; no migration was applied. Checklist: 562 checked / 16 open; strict private Gateway response contracts total 193. Evidence: `builds/2026-10-29-recovery/solution-replication-review-detail-response-contract.json`.
