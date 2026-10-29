# Capability preservation matrix

**Source continuation — strategy advantage projection — 29 October 2026:** the strategy performance reader now pins migration 286's 15 ordered columns while preserving the plan filter, ordering, and UUID serialization. Its mock-cursor regression passes with Ruff, compilation, and diff checks; no database/provider was used. Checklist: 1,696 complete / 25 open; TODO: 381 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Evidence: [strategy advantage projection](builds/2026-10-29-recovery/strategy-advantage-performance-projection.json).

**Source continuation — PRM outcome-correlation projection — 29 October 2026:** `outcome_correlation()` now pins migration 196's seven ordered columns and preserves serialized rows. The focused mock-cursor check passes with Ruff, compilation, and diff checks; no database/provider was used. Checklist: 1,695 complete / 25 open; TODO: 380 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Evidence: [PRM projection](builds/2026-10-29-recovery/prm-outcome-correlation-projection.json).

**Source continuation — Gateway OpenAPI operator-cookie security — 29 October 2026:** all private `/operator/api/` operations and the authenticated session/logout routes now advertise the middleware-enforced `kokonut_operator_session` cookie; login, callback, console landing, public drivers, and health stay public. Sixteen focused tests pass with Ruff, compilation, and diff checks; only a synthetic OIDC provider was used. Checklist: 1,694 complete / 25 open; TODO: 379 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Evidence: [Gateway OpenAPI security](builds/2026-10-29-recovery/gateway-openapi-operator-cookie-security.json).

**Source continuation — sensor stream batch preflight — 29 October 2026:** CLI and direct-service batch sizes now fail closed outside 1–500 before processor/database work; valid 1 and 500 are forwarded unchanged. Thirteen mock-only checks pass with Ruff, compilation, and diff checks. No database/provider state was used. Checklist: 1,693 complete / 25 open; TODO: 378 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Evidence: [stream batch preflight](builds/2026-10-29-recovery/stream-processor-batch-size-preflight.json).

**Latest C2/C4/C5 continuation — 29 October 2026:** the private mobile-disposition inventory, one-time enrollment, Delphi study-item create/replay, and authenticated service-health response now have strict request-bound validation. The health route validates exact dependency states and consistent aggregates, returns sanitized no-store errors, and remains authorization-gated before probes. Pest-trend, biocontrol, and total-cost-of-ownership analytics now use exact migration-backed view columns while preserving scope and payloads. Prefect composites skip default-off legacy dashboards, market-data, weather, and weekly climate stages while keeping direct workers fail-closed. The Python public SDK shares JavaScript's timer-safe timeout ceiling and rejects finite oversized values before network calls. Weather-growth/revenue queries aggregate independent event families and reject location mismatches. Migration 686 location-qualifies the revenue-stream crop-cycle label join; network-disabled PostgreSQL 16 apply/replay preserves contribution rows/totals and same-location labels while hiding a foreign label. Delphi publishes all 11 migration-aligned fields, binds study/location IDs, validates numeric bounds, and preserves 201 create/200 replay; 37 focused checks pass. Current selections pass: enrollment 15, Prefect 30 + 2 weekly climate, direct weather 2, direct climate 1, health 9, pest 2, TCO 4, Python public SDK 156, and JavaScript timeout 6; migration 686 passes nine assertions. Ruff, compilation, SQL/worker inventory checks, migration-source validation, and diff checks pass. Production OIDC, populated-data parity, and candidate/legacy migration state remain unchanged. Checklist: 1,681 complete / 20 open; TODO: 366 checked / 11 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts remain 116 ([enrollment/weather](builds/2026-10-29-recovery/mobile-enrollment-prefect-weather-contracts.json); [migration](builds/2026-10-29-recovery/revenue-stream-location-join-disposable.json); [analytics](builds/2026-10-29-recovery/analytics-event-aggregation-disposable.json); [Delphi](builds/2026-10-29-recovery/delphi-study-item-response-contract.json); [health/pest](builds/2026-10-29-recovery/health-and-pest-projection-contracts.json); [climate/TCO/SDK](builds/2026-10-29-recovery/climate-tco-sdk-parity.json)).

**Previous Gateway/operations contract batch — 29 October 2026:** the private Field Collector collection-detail endpoint now has strict OpenAPI/response validation, request-bound collection and location IDs, a flexible form payload capped at 512 KiB, and bounded review-event/evidence metadata with sanitized no-store errors. Scheduler sensor plans now accept and forward the required registered driver-instance UUID and remain disabled until reviewed. Resource-efficiency analytics pre-aggregates harvest and labor per cycle, resolves crop through `crop_cycle.crop_id`, and excludes events with a location that disagrees with the cycle. Focused checks pass: 32 Gateway/mobile, 155 scheduler/command, and disposable PostgreSQL 16 resource-efficiency assertions; Ruff, compilation, capability validation, and diff checks pass. This is source-level/isolated-database acceptance only; production OIDC, populated-data parity, and candidate/legacy migration state are unchanged. Checklist: 1,669 complete / 25 open; TODO: 357 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 112 ([evidence](builds/2026-10-29-recovery/kernel-next-operations-contract-batch.json)).

**Latest C2 farm-summary GeoJSON contract — 29 October 2026:** farm and plot PostGIS geometry now uses explicit `ST_AsGeoJSON(...)::jsonb` projections rather than raw driver serialization. The Gateway publishes strict Polygon/Point schemas, validates coordinates and polygon rings, accepts null/empty values, and binds farms, plots, crop cycles, and embedded location to the authorized location hierarchy. The focused report/Gateway selection passes 145 tests; Ruff, compilation, all report-inventory freshness checks, capability validation, and diff checks pass. Mock fixtures only; no database/provider, candidate, or legacy state was used. Checklist: 1,657 complete / 25 open; TODO: 352 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private response endpoints remain 109 ([evidence](builds/2026-10-29-recovery/comprehensive-status-farm-geojson-contract.json)).

**Latest C2 Comprehensive Status capital-accounting contract — 29 October 2026:** the private one-location response now validates all four capital-accounting projections with strict schemas, location and period binding, derived-field consistency, safe partial failures, and a draft-only credit ledger under the advisory-only boundary. The focused route suite passes 127 tests; Ruff, compilation, and diff checks pass. Synthetic route fixtures only; no database/provider, candidate, or legacy state was used. This shape validation does not establish populated-data parity or content privacy. Checklist: 1,653 complete / 25 open; TODO: 348 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private response endpoints remain 109 ([evidence](builds/2026-10-29-recovery/comprehensive-status-capital-accounting-contract.json)).

**Latest C2 Comprehensive Status training-impact contract — 29 October 2026:** the private one-location response now validates training sessions against the report generator's exact 15-field public-view projection, binds the section and every session to the request location, restricts lifecycle/type values to schema filters, and matches session counts, participant counts, hours, and mean improvement to source rows. Nullable scores remain valid, including the source generator's Decimal half-even average rounding. The focused Comprehensive Status route suite passes 117 tests; Ruff, compilation, and diff checks pass. Synthetic route fixtures only; no database/provider or candidate/legacy state was used. The view continues to include participant names, trainers, and notes; this shape contract does not establish content privacy for the wider report audience. Checklist: 1,650 complete / 25 open; TODO: 345 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private response endpoints remain 109 ([evidence](builds/2026-10-29-recovery/comprehensive-status-training-impact-contract.json)).

**Latest C2 Comprehensive Status stakeholder-outcomes contract — 29 October 2026:** the private one-location report now validates its stakeholder-outcomes section and rows against the exact source projection. The section and every row bind to the composed location; only verified/published lifecycle rows and schema importance values pass; aggregate count must equal row count. Nullable schema fields are preserved, while undeclared data and the currently unimplemented link projection fail closed. The focused Comprehensive Status route suite passes 106 tests; Ruff, compilation, and diff checks pass. Synthetic route fixtures only; no database/provider or candidate/legacy state was used. Checklist: 1,647 complete / 25 open; TODO: 342 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private response endpoints remain 109 ([evidence](builds/2026-10-29-recovery/comprehensive-status-stakeholder-outcomes-contract.json)).

**Latest C2 Comprehensive Status holistic-wellbeing contract — 29 October 2026:** the private one-location response now validates its holistic-wellbeing section against exact cultural-context, wellbeing-metric, and participatory-action projections from the three consent/publication-filtered views. The section binds to its enclosing location and rejects undeclared fields, out-of-range evidence maturity, and invalid numeric types while preserving the established section error shape. The focused Comprehensive Status route suite passes 99 tests; Ruff, compilation, and diff checks pass. Synthetic response fixtures only; no database/provider or candidate/legacy state was used. Checklist: 1,644 complete / 25 open; TODO: 339 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; the number of strict private response endpoints remains 109 because this strengthens an existing route contract ([evidence](builds/2026-10-29-recovery/comprehensive-status-holistic-wellbeing-contract.json)).

**Latest C2 submitted-report detail contract — 29 October 2026:** the private report-review detail route now publishes an exact `data` response model for the submitted summary fields plus its dynamic JSON report object, bounded to 512 KiB. Runtime validation binds the returned report UUID to the requested path and rejects extra fields, non-object payloads, or oversized output. Invalid input, denial, missing reports, oversized service results, malformed projections, and provider/database errors now retain generic no-store responses. The focused report/detail selection passes 23 tests and the operator authorization integration adds 2; Ruff, compilation, matrix validation, and diff checks pass. Mocks only; no database/provider or candidate/legacy state was used. Checklist: 1,641 complete / 25 open; TODO: 336 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 109 ([evidence](builds/2026-10-29-recovery/submitted-report-detail-gateway-contract.json)).

**Latest C2 AI-summary review-page integrity — 29 October 2026:** review items now fail closed if summary IDs repeat or the page departs from the database's ascending `created_at, id` projection. The route also requires a truncated-content flag to correspond to the 20,000-character bounded projection. Existing null-last ordering, page/location binding, cursor-independent offset bounds, and private no-store errors remain intact. The focused review route selection passes 58 tests; Ruff, compilation, and diff checks pass. Mocked service output only; no database/provider or candidate/legacy state was used. Checklist: 1,638 complete / 25 open; TODO: 333 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts remain 108 ([evidence](builds/2026-10-29-recovery/ai-summary-review-page-integrity.json)).

**Latest C2 AI-summary human decision contract — 29 October 2026:** the location-scoped review decision route now publishes strict OpenAPI request/response schemas from migration 521/522. The request allows only approve/reject, UUID retry ID, and enumerated reason codes with matching decision semantics; path identifiers and body are checked before dispatch. Responses must contain only the five migration-defined fields and bind summary ID, decision, and resulting lifecycle (`approve` → `verified`; `reject` → `rejected`); malformed output fails with a sanitized no-store error. The existing HTTP 200 behavior and human review boundary are preserved. The focused draft/review selection passes 77 tests; Ruff, compilation, matrix validation, and diff checks pass. Mock-only; no database/provider or candidate/legacy state was used. Checklist: 1,635 complete / 25 open; TODO: 330 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 108 ([evidence](builds/2026-10-29-recovery/ai-summary-human-review-decision-contract.json)).

**Latest C2 AI-summary draft response contract — 29 October 2026:** authenticated draft creation now has strict request and response schemas grounded in migrations 522/523/540/551. Requests bind a supported summary type and UUID retry key before service dispatch; responses bind location/type and validate lifecycle, bounded content, declared source tables, source IDs/count/truncation, and location/network scope. Both draft and review projections accept the migration-backed 20-source bound, including combined synthesis. OpenAPI publishes both schemas and errors; malformed output returns a sanitized no-store failure while 201 creation/200 replay behavior and private content are preserved. The focused draft/task/review selection passes 86 tests; Ruff, compilation, matrix validation, and diff checks pass. Mocks and synthetic connections only; no database/provider, candidate, legacy, or production state was used. Checklist: 1,632 complete / 25 open; TODO: 327 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 107 ([evidence](builds/2026-10-29-recovery/ai-summary-draft-response-contract.json)).

**Latest C2 governance assignment review queue contract — 29 October 2026:** the private location-scoped review queue now validates all 14 migration-backed fields and publishes strict page/item/cursor schemas. Runtime validation enforces requested-location and page-size binding, assignment uniqueness and descending order, and input/continuation cursor consistency while retaining no-store errors and the signed reviewer boundary. The focused governance assignment review and pagination/OpenAPI selection passes 24 tests; Ruff, compilation, and diff checks pass. Mocked routes and synthetic connections only; no live database/provider, candidate, or legacy state was used. Checklist: 1,629 complete / 25 open; TODO: 324 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 106 ([evidence](builds/2026-10-29-recovery/governance-assignment-review-queue-contract.json)).

**Latest C2 AI-synthesis task receipt contract — 29 October 2026:** the authenticated synthesis-request Gateway now publishes registered task/summary enums, rejects invalid task-to-summary pairings before dispatch, and returns only the exact location-bound authorization receipt. It preserves 201 new/200 retry status and returns generic no-store errors for malformed output. The focused AI-summary task-request/draft selection passes 30 tests; Ruff, Python compilation, matrix validation, and diff checks pass. Synthetic connections and mocks only; no database/provider, candidate, or legacy state was used. Checklist: 1,626 complete / 25 open; TODO: 321 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 105 ([evidence](builds/2026-10-29-recovery/ai-synthesis-task-receipt-gateway-contract.json)).

**Latest C2 trend-forecast creation contract — 29 October 2026:** the signed trend forecast POST now enforces a strict bounded request and publishes a created/reused response union in OpenAPI. Runtime validation binds returned location, metric, and horizon to the request while preserving 201 for newly persisted forecasts and 200 for idempotent reuse; malformed results fail closed with a generic no-store error. The focused route/compute selection passes 66 tests; Ruff, Python compilation, and diff checks pass. Fake connections and forecasting mocks only; no live database, provider, candidate, or legacy state was used. Checklist: 1,623 complete / 25 open; TODO: 318 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 104 ([evidence](builds/2026-10-29-recovery/trend-forecast-create-gateway-contract.json)).

**Latest C2 stakeholder-identity write contract — 29 October 2026:** location-scoped proposal and independent-decision routes now have migration-aligned strict request/response models and exact OpenAPI schemas. Invalid UUID, enum, confidence, precision, extra-field, and malformed service-response cases are rejected with sanitized no-store errors; the service still enforces signed location scope and independent review. The focused route/service/OpenAPI selection passes 36 tests, with Ruff, Python compilation, matrix validation, and diff checks passing. Mock-only; no database/provider, candidate, or legacy state was used. Live OIDC/browser, populated data, and broader tenant/RLS acceptance remain open. Checklist: 1,620 complete / 25 open; TODO: 315 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 103 ([evidence](builds/2026-10-29-recovery/stakeholder-identity-write-gateway-contracts.json)).

**Latest C2 Data Stream write contract — 29 October 2026:** the draft-create Gateway route now publishes a strict OpenAPI request with exactly the 15 post types from the domain service, bounded title, exact location, optional content, and timezone-aware expiry. It accepts no caller-supplied creator, lifecycle, metadata, or source fields, returns only the created UUID, and sanitizes no-store request-validation failures. The focused Gateway/auth selection passes 39 tests; Ruff, Python compilation, matrix validation, and diff checks pass. No database, provider, candidate, or legacy service was used; live OIDC/browser and populated-data acceptance remain open ([evidence](builds/2026-10-29-recovery/data-stream-create-gateway-contract.json)). Checklist: 1,617 complete / 25 open; TODO: 312 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; the 101 private Gateway response contracts are unchanged.

**Latest C2 public linked-data contract — 29 October 2026:** the public location IRI resolver now validates an exact JSON-LD document, canonical location/version identity, immediate same-location predecessor, and the SHA-256 digest of the returned public projection. OpenAPI describes the success media type as `application/ld+json`; malformed resolver data returns a sanitized no-store error. The focused route/service selection passes 13 tests, with Ruff, Python compilation, and diff checks passing. No database, provider, candidate, or legacy service was used. External JSON-LD interoperability and live/populated IRI parity remain open; the 67 capability classifications and 101 private Gateway response contracts are unchanged ([evidence](builds/2026-10-29-recovery/public-location-iri-jsonld-response-contract.json)). Checklist: 1,614 complete / 25 open; TODO: 309 checked / 16 open.

**Latest C2 report-export console continuation — 29 October 2026:** migration 684 now provides a bounded, exact-location list of verified/published snapshots eligible for the existing private export worker. The strict Gateway route keeps snapshot listing, export creation, request status, and completed artifact download under separate location grants. The operator console adds eligibility pagination, session-stable retry IDs, status polling, and completed-only private JSON downloads. Focused Gateway, route-policy, migration-contract, and console checks pass 88 tests; disposable PostgreSQL 16 applies/replays migrations 683 and 684 and verifies scope, grant separation, digest/size filters, pagination, and role boundaries. Ruff, runtime SQL inventory, provider-boundary, matrix validation, inline JavaScript syntax, and diff checks pass. The candidate and legacy databases remain untouched; live OIDC/browser, populated report parity, live worker recovery, and R2 remain open. Checklist: 1,611 complete / 25 open (1,636 total); TODO: 306 checked / 16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 101 strict private Gateway response contracts. MAN-CAP acceptance is unchanged ([contract](report-snapshot-export-contract.md); [disposable acceptance](builds/2026-10-29-recovery/report-snapshot-export-migration-disposable.json); [focused checks](builds/2026-10-29-recovery/report-snapshot-export-console-contracts.json)).

**Latest C2 response-contract continuation — 29 October 2026:** the Data Stream attachment route now publishes and enforces its exact 17-field private response, binds records to the requested post, and rejects unexpected/sensitive fields with no-store errors. CRISP evidence maturity is bounded to levels 0–6 across Gateway and both REST SDKs. The focused checks pass 197 Python and 141 JavaScript tests; OpenAPI and generated SDK checks, Ruff, compilation, TypeScript build, capability validation, and diff checks pass. No database/provider or candidate was accessed; broader live OIDC, browser, populated-data and tenant-isolation gates remain open ([evidence](builds/2026-10-29-recovery/kernel-c2-file-and-crisp-contracts.json)). The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 100 strict private Gateway response contracts.

**Latest report projection and SDK response-contract batch — 29 October 2026:** six commons reads and the additional technology/stakeholder/trust/value-stream/governance reports now use explicit schema-backed projections. Gateway, Python, and JavaScript summary contracts enforce source-backed metric and attestation count relationships, and the TypeScript gRPC DataService normalizes its declared RPC responses with bounded streaming. Seven focused mocked selections pass 130 tests, including Python server protobuf serialization; Ruff, TypeScript lint, JavaScript type-check, capability validation, report inventories, and diff checks pass. No database, provider, candidate, or live service was accessed. The helper inventory records ten allowlisted dynamic projection sites as statically unresolved; MAN-CAP acceptance and populated-data parity remain open ([evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)). The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts.

**Latest internal cockpit projection batch — 29 October 2026:** the stakeholder cockpit and ecosystem now select all 20 columns from the internal summary view; coordination cockpit selects all 22 fields from its internal view. The focused synthetic check covers all three callsites and preserves network scope, ordering, and result payloads. Ruff, compilation, report inventories, matrix validation, and diff checks pass; no database/provider or candidate was used ([evidence](builds/2026-10-29-recovery/kernel-strategy-internal-cockpit-projections.json)). Checklist: 1,599 complete / 25 open (1,624 total); TODO: 294 checked / 16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest stakeholder/coordination cockpit projection batch — 29 October 2026:** the public stakeholder cockpit and coordination-alliance reports now select the exact 13 migration-238 fields, preserving network-wide behavior and internal/public response separation. The focused mock regression passes; Ruff, compilation, report inventories, matrix validation, and diff checks pass. A source scan finds no remaining `SELECT * FROM v_public_*` in `services/export/reports`; private/internal and direct-table wildcard queries are not included ([evidence](builds/2026-10-29-recovery/kernel-strategy-cockpit-report-projections.json)). Checklist: 1,597 complete / 25 open (1,622 total); TODO: 292 checked / 16 open. Matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest organic report projection batch — 29 October 2026:** the readiness, transition, certification, prohibited-substance, input-audit, and harvest-segregation reports now select their exact 24-, 23-, 21-, 17-, 20-, and 16-column migration-055 public-view projections. One focused mock regression verifies all six lists, location scope, payloads, and report aggregates. Ruff, compilation, report inventories, matrix validation, and diff checks pass; no database/provider or candidate was used. Populated-data parity, live OIDC, content privacy, and tenant isolation remain separate gates ([evidence](builds/2026-10-29-recovery/kernel-organic-report-projections.json)). Checklist: 1,595 complete / 25 open (1,620 total); TODO: 290 checked / 16 open. Matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) with 99 strict private Gateway response contracts; MAN-CAP acceptance is unchanged.

**Latest operations report projection batch — 29 October 2026:** training-impact and reward-calibration reports now select all 15 ordered fields from their migration-defined public views. Focused mocked report and response-contract checks pass 37 tests; scope, order, aggregates, and payload are preserved. Ruff, compilation, all report inventories, matrix validation, and diff checks pass. No database/provider or candidate was used; populated-data parity, live OIDC, tenant isolation, and content-level privacy remain separate acceptance gates ([evidence](builds/2026-10-29-recovery/kernel-operations-training-reward-report-projections.json)). Checklist: 1,589 complete / 25 open (1,614 total); TODO: 288 checked / 16 open. Matrix classifications remain 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest scaling report projection batch — 29 October 2026:** farm-launch unit economics now select all 27 migration-040 columns in both network and location modes; adoption barriers and perpetual-value stress use their exact 17- and 20-column views. The focused mock test preserves scope/date filters, ordering, payload, and aggregates. Ruff, compilation, report inventories, matrix validation, and diff checks pass; no DB/provider or candidate was used ([evidence](builds/2026-10-29-recovery/kernel-scaling-report-projection-batch.json)). Checklist: 1,587 complete / 25 open (1,612 total); TODO: 286 checked / 16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest Bio Factory report projection batch — 29 October 2026:** batch, input-provenance, recipe-library, and quality-test reports now select the complete 21-, 20-, 23-, and 18-column projections defined in migration 043. The focused mock test checks exact columns and retains scope/date filters, ordering, aggregates, and payload. Ruff, compilation, report inventories, matrix validation, and diff checks pass. No DB/provider or candidate was used ([evidence](builds/2026-10-29-recovery/kernel-bio-factory-report-projection-batch.json)). Checklist: 1,584 complete / 25 open (1,609 total); TODO: 283 checked / 16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest wellbeing report projection batch — 29 October 2026:** risk mitigation, scaling roadmap, capital-efficiency, regenerative-efficiency, and governance-throughput reports now select exact ordered columns from migrations 035 and 036. The four focused mock tests preserve location/date scope, shared rows, order, aggregates, and payload. Ruff, compilation, report inventories, matrix validation, and diff checks pass. No DB/provider or candidate was used ([evidence](builds/2026-10-29-recovery/kernel-wellbeing-risk-capital-governance-projections.json)). Checklist: 1,580 complete / 25 open (1,605 total); TODO: 279 checked / 16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared), with 99 strict private Gateway response contracts. MAN-CAP acceptance is unchanged.

**Latest governance-readback/report-projection batch — 29 October 2026:** token-reward distributions/calibrations, capital-provider utility, and stakeholder participation/equity distribution now use exact migration-defined projections; the private governance assignment-proposal page has a strict location, item, timestamp, ordering, and cursor contract with sanitized no-store errors. The synthetic/mock selection passes 22 tests; Ruff, compilation, all three report inventories, matrix validation, and diff checks pass. No database/provider or candidate was used. This does not establish populated-data parity, live OIDC, content privacy, or tenant isolation ([evidence](builds/2026-10-29-recovery/kernel-parallel-governance-and-report-projection-batch-3.json)). Checklist: 1,575 complete / 25 open (1,600 total); TODO: 274 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts now total 99. MAN-CAP acceptance is unchanged.

**Latest parallel report-projection batch — wellbeing, governance, and scaling (29 October 2026):** network-scaling targets, governance inclusion, EBF scorecards, and financial-sustainability reports now select their complete migration-defined public-view columns. Focused mocked checks pass 4 tests; Ruff, compilation, all three report inventories, matrix validation, and diff checks pass. Existing location/date filters, network-shared rows, ordering, and output aggregates are preserved. No database/provider or candidate was used. These source checks do not establish populated-data parity, content privacy, OIDC, or tenant isolation ([evidence](builds/2026-10-29-recovery/kernel-parallel-report-projection-batch-2.json)). Checklist: 1,571 complete / 25 open (1,596 total); TODO: 270 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; strict private Gateway response contracts remain 98. MAN-CAP acceptance is unchanged.

**Latest parallel C2/C5 operations, Gateway, and SDK batch — 28 October 2026:**
the governance tactical-session page now has an exact location-bound response
contract, bounded cursor validation, and sanitized no-store failure behavior.
Feature importance, livestock feed intake, and the organic compliance
dashboard select all 13, 17, and 25 public-view columns explicitly. Both SDKs
require exact application error envelopes and preserve framework 422 details.
Focused checks pass 578 Python and 131 TypeScript tests; the SDK build, Ruff,
compilation, report inventories, capability validation, and diff checks pass.
No database, migration, provider, candidate, legacy service, or production
resource was used. Matrix classifications remain 67 rows (24 baseline-
retained, 7 deployed, 36 prepared), with 97 strict private Gateway response
contracts. Checklist: 1,563 complete / 25 open (1,588 total); TODO: 266
checked / 16 open; MAN-CAP acceptance and classifications are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-operations-governance-sdk-error-contracts.json)).

**Latest parallel continuation — ecological, Bio Factory, Open Source Impact, and operating-pilot contracts (29 October 2026):** five ecological report queries, Bio Factory regional inputs, and Open Source Impact now use exact ordered public-view projections. The private own-learning-plans route validates its strict response schema, request-bound pagination and continuation, review metadata, and returned order/location. The combined mocked selection passes 41 tests; Ruff, compilation, all three report inventories, capability validation, and diff checks pass. No live database/provider or candidate was used. This is source-level evidence only; populated-data parity, content privacy, live OIDC, and tenant isolation remain open ([evidence](builds/2026-10-29-recovery/kernel-parallel-ecological-biofactory-operating-pilot-contracts.json)). Checklist: 1,567 complete / 25 open (1,592 total); TODO: 266 checked / 16 open. Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows, with 98 strict private Gateway response contracts; MAN-CAP acceptance is unchanged.

**Previous parallel C2/C5 operations and Gateway batch — 28 October 2026:** the
location-governance summary now has an exact location-bound response and
OpenAPI contract; malformed results fail closed. Resource-efficiency,
revenue-stream, and prediction-accuracy reports select their full 16-, 16-,
and 19-column public views explicitly. Focused mocked checks pass 386 Python
tests; Ruff, compilation, report inventories, capability validation, and diff
checks pass. No database, migration, provider, candidate, legacy service, or
production resource was used. The matrix remains 67 rows (24 baseline-retained,
7 deployed, 36 prepared), with 96 strict private Gateway response contracts.
Checklist: 1,558 complete / 25 open (1,583 total); TODO: 261 checked / 16
open; MAN-CAP acceptance and classifications are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-operations-governance-contracts.json)).

**Previous parallel C2/C5 and SDK contract batch — 28 October 2026:** the private
Data Stream post-list route now validates the exact fixed response projection
and requested location; malformed or cross-location rows fail with a
sanitized no-store server error. Replication readiness, adaptive stewardship,
and capital alignment now explicitly select all 19, 19, and 17 public-view
columns. Python and TypeScript SDKs require data-only success envelopes and
bind location-detail responses to the requested UUID. Focused checks pass 232
Python and 125 TypeScript tests; the SDK build, Ruff, compilation, report
inventories, capability validation, and diff checks pass. No database,
migration, provider, candidate, legacy service, or production resource was
used. These source contracts do not establish populated-data parity or
content-level privacy. Matrix classifications remain 67 rows (24
baseline-retained, 7 deployed, 36 prepared); strict private Gateway response
contracts now total 95. Checklist: 1,554 complete / 25 open (1,579 total);
TODO: 257 checked / 16 open; MAN-CAP acceptance and classifications are
unchanged ([evidence](builds/2026-10-28-recovery/kernel-parallel-report-sdk-datastream-contracts.json)).

**Previous parallel C2/C5 and SDK summary batch — 28 October 2026:**
Comprehensive Status now validates community governance while retaining
location-null shared mechanisms, and validates foundational-wellbeing rows
without rejecting qualitative-only observations. Vulnerable-access,
foundational-wellbeing, and community-governance reports use full explicit
public-view projections. Python and TypeScript now validate public metrics and
nested location summaries against the requested location. The integrated
focused selection passes 278 Python and 121 TypeScript tests; the TypeScript
build, Ruff, compilation, report inventories, matrix validation, and diff
checks pass. No database, migration, provider, candidate, legacy service, or
production resource was used. Existing public content is preserved; populated
parity and content-level privacy remain open. Matrix classifications stay at
67 rows (24 baseline-retained, 7 deployed, 36 prepared); private Gateway
response contracts remain 94. Checklist: 1,548 complete / 25 open
(1,573 total); MAN-CAP acceptance and classifications remain unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-wellbeing-community-sdk-contracts.json)).

**Latest parallel C2/C5 and SDK CRISP batch — 28 October 2026:** the
Comprehensive Status capital-efficiency section now has strict nested models
and verifies both scenario and regenerative-efficiency rows match the requested
location. GNH alignment, cultural preservation, and renewable energy now use
explicit full projections from their stable public views. The Python and
TypeScript SDKs validate CRISP assessment fields and enforce requested-path
location matching. Focused verification passes 209 Python and 75 TypeScript
tests; the SDK build, Ruff, compilation, report inventories, matrix validation,
and diff checks pass. Existing public narratives/metadata remain, so this is
not content-level privacy or populated-data parity evidence. No database,
migration, provider, candidate, legacy service, or production resource was
used. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared); strict private Gateway response contracts remain 94. Checklist:
1,541 complete / 25 open (1,566 total); MAN-CAP acceptance and classifications
are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-capital-wellbeing-crisp-contracts.json)).

**Latest parallel C2/C5 and SDK contract batch — 28 October 2026:**
Comprehensive Status validates the GNH public-view projection, report and row
location, and the generator's rounded score average. Regenerative-outcomes and
time-liberation reports now use explicit full projections of their public
views. Python and TypeScript public-location list/detail clients enforce the
Gateway's exact field, UUID, nullability, and active-status contract. Focused
checks pass: 186 Python tests and 43 TypeScript tests; Ruff, compilation, all
report inventories, capability validation, and diff checks pass. No database,
provider, candidate, legacy service, or production resource was used. These
checks do not establish content-level privacy or populated-data parity. Matrix
classifications remain 67 rows (24 baseline-retained, 7 deployed, 36
prepared); strict private Gateway response contracts remain 94. Checklist:
1,536 complete / 25 open (1,561 total); MAN-CAP acceptance and classifications
are unchanged ([evidence](builds/2026-10-28-recovery/kernel-parallel-gnh-sdk-report-projection-contracts.json)).

**Latest parallel C2/C5 contract and projection batch — 28 October 2026:**
Comprehensive Status now validates regenerative-outcome report and row scope,
period order, and hectares aggregation while retaining existing summary and
metadata fields. Federation `shared_capabilities` now rejects non-JSON values
without narrowing JSONB payloads or changing route/SDK behavior; Pydantic's
recursive `JsonValue` still produces an empty OpenAPI schema component.
Stakeholder outcomes and Green Paper publication status now use explicit
22-column and 14-column projections. The integrated focused selection passes
525 tests; Ruff, compilation, report inventories, matrix validation, and diff
checks pass. Existing output fields remain, so content-level privacy and
populated-data parity remain open. No database, migration, provider, candidate,
legacy service, or production resource was used. The matrix remains 67 rows
(24 baseline-retained, 7 deployed, 36 prepared); strict private Gateway
response contracts remain 94. Checklist: 1,532 complete / 25 open
(1,557 total); MAN-CAP acceptance and classifications are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-regenerative-federation-report-projections.json)).

**Latest C2/C5 climate and Statement of Work contracts — 28 October 2026:**
the private Comprehensive Status climate-impact section now validates its
nested projection and binds its calculations/stored summary to the selected
location and year while preserving shared protocols and current content.
Statement of Work now explicitly projects all columns for the main record and
three child tables. The combined Gateway/report/SOW/scope/inventory selection
passes 457 tests; Ruff, compilation, three report inventories, and diff checks
pass. Existing evidence paths, reviewer IDs/notes, invoice numbers, metadata,
and raw-source fields remain unchanged, so this does not decide content-level
privacy or populated-data parity. No database, migration, provider, candidate,
legacy service, or production resource was used. Matrix: 67 rows (24
baseline-retained, 7 deployed, 36 prepared); strict private Gateway response
contracts remain 94. Checklist: 1,528 complete / 25 open (1,553 total).
MAN-CAP acceptance and classifications are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-climate-sow-contracts.json)).

**Latest C2/C5 composite-report contracts — 28 October 2026:** Comprehensive
Status now strictly validates its current farm-summary and published
financial-sustainability projections, including location binding, nested
fields, and the existing per-section error response. Climate-impact explicitly
selects all 24 current `climate_impact_summary` columns. The combined
Gateway/report/climate selection passes 56 tests; Ruff, compilation, all three
report inventories, and diff checks pass. Existing field contents and
lifecycle semantics are preserved. Geometry, metadata, actor IDs, public
summary text, and populated-data privacy/parity still need separate review. No
database, migration, provider, candidate, legacy service, or production
resource was used. The capability matrix remains 67 rows: 24 baseline-retained,
7 deployed, and 36 prepared; checklist: 1,526 complete / 25 open
(1,551 total). MAN-CAP acceptance and classifications are unchanged
([evidence](builds/2026-10-28-recovery/kernel-parallel-comprehensive-report-contracts.json)).

**Latest parallel source-contract batch — 28 October 2026:** the runtime SQL
inventory now resolves eight additional unambiguous same-module constants and
fingerprints their source bindings; ambiguous/dynamic cases still fail closed.
Two preflight `WITH` candidates and the changed farm-summary query were
recorded as source-reviewed, not ACL-approved. Four protected Baal Gateway
reads now have strict runtime/OpenAPI response contracts and remain outside
the public API/SDK. Farm-summary SQL uses explicit current-schema projections
instead of `SELECT *`, without changing financial lifecycle semantics. The
75-test focused selection, 67-test worker/inventory selection, report and
worker inventories, Ruff, compilation, provider/dependency checks, and matrix
validation pass. No database, provider, candidate, legacy service, or
production resource was used. Parallel Directus and SDK audits found no safe
unattended Directus expansion or missing public SDK operation; the ACL audit
found no new relation safe to revoke from source evidence alone. The legacy
Prefect health flow remains unregistered pending a profile-aware alert/retry
contract. Aggregate worker preflight remains `review_required`. The matrix
remains 67 rows (24
baseline-retained, 7 deployed, 36 prepared), with strict private Gateway
response contracts now totaling 94. Checklist: 1,524 complete / 25 open
(1,549 total); MAN-CAP acceptance and classifications are unchanged ([evidence](builds/2026-10-28-recovery/kernel-parallel-c1-c2-c5-code-batch.json)).

**Latest C2 report-export slice — 28 October 2026:** migration 683 and the Gateway now provide a durable, idempotent private report-snapshot export path with separate location-qualified create/read/download grants and a dedicated default-off worker. Its provider-neutral artifact port keeps local storage as the default and adds an optional S3-compatible/R2 adapter with separate read-only Gateway and write/delete worker credentials. The API exposes strict create/list/detail response models; downloads return only verified private artifact bytes after the current grant and source lifecycle are rechecked. Network-disabled disposable PostgreSQL 16 runs apply and replay migration 683 on native x86_64 and ARM64/QEMU (`aarch64`) and verify exact tenant authorization, worker fencing/retry, forced-RLS source reads, and function/table boundaries. The integrated route/worker/migration/runtime-role and worker-inventory selection passes **238 tests**; a follow-up storage/Gateway/worker selection passes **65 tests** for bounded artifact reads, and the regenerated worker-function graph selection passes **13 tests**; mocked S3/storage/Gateway/worker checks pass **77 tests** for the optional private R2 adapter; worker-inventory regressions pass **67 tests** after all seven reports are refreshed. Ruff, compilation, seven inventory checks, dependency-group alignment, provider-boundary checks, matrix validation, and diff checks pass. ARM64/QEMU is portability evidence, not a physical Raspberry Pi run. The static inventory includes the isolated report worker; the aggregate worker preflight remains `review_required` for broader existing boundary debt. This source and disposable-database evidence does not establish live OIDC, candidate rollout, browser/worker runtime recovery, live R2 connectivity or bucket policy, retention, populated report parity, or stakeholder access. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared); documented strict private Gateway response contracts now total 90. Checklist: 1,520 complete / 25 open (1,545 total); MAN-CAP acceptance and classifications are unchanged ([contract](report-snapshot-export-contract.md); [integrated checks](builds/2026-10-28-recovery/report-snapshot-export-integration-checks.json); [bounded-read checks](builds/2026-10-28-recovery/report-snapshot-export-bounded-read-checks.json); [S3 adapter checks](builds/2026-10-28-recovery/report-snapshot-export-s3-adapter-checks.json); [native evidence](builds/2026-10-28-recovery/report-snapshot-export-migration-disposable.json); [ARM64 evidence](builds/2026-10-28-recovery/report-snapshot-export-migration-arm64-disposable.json)).

**Previous parallel continuation — solution lifecycle read contracts and CLI UUID normalization (28 October 2026):** the stage-transition target, aggregate summary, and experiment pages now enforce strict request-bound response contracts from migrations 503, 459, and 467. Seven domain CLIs now pass canonical UUIDs to database handlers after preflight while retaining existing scope requirements. The combined Gateway/CLI selection passes 295 tests; Ruff, compilation, matrix validation, and diff checks pass. These source checks do not establish live Gateway/database behavior, tenant isolation, OIDC, or populated-data parity ([evidence](builds/2026-10-28-recovery/kernel-parallel-solution-lifecycle-read-and-cli-canonicalization.json)). Checklist: 1,510 complete / 25 open (1,535 total); strict private Gateway response endpoints: 85; counted CLI location UUID preflight groups: 27; matrix: 67 rows (24 baseline-retained, 7 deployed, 36 prepared).

**Previous parallel continuation — solution lifecycle gate response and CLI scope (28 October 2026):** the private solution-lifecycle gate page now has a strict request-bound contract with exact migration projection, pagination, unique IDs, stable order, and continuation validation; all 13 database-backed Analytics CLI commands and Credit Class batch/enrollment location operations reject malformed UUIDs before dispatch and canonicalize valid ones. The combined Gateway/CLI selection passes 159 tests; Ruff, compilation, matrix validation, and diff checks pass. These source checks do not prove tenant row-level isolation, live OIDC, or populated-data parity ([evidence](builds/2026-10-28-recovery/kernel-parallel-solution-lifecycle-cli-boundaries.json)). Checklist: 1,506 complete / 25 open (1,531 total); strict private Gateway response endpoints: 82; CLI location UUID preflight: 27 groups; matrix: 67 rows (24 baseline-retained, 7 deployed, 36 prepared).

**Previous parallel continuation — operating-pilot/governance response contracts and CLI scope (28 October 2026):** the private operating-pilot work-opportunities page and governance-circle detail now publish strict request-bound OpenAPI/runtime contracts; CRISP location UUIDs are validated before database access, Data Governance normalizes validated location filters, and a source audit confirms all 94 registered report generators validate location scope before query access. The integrated route/CLI selection passes 262 tests and adjacent governance tests pass 44 with 5 skips; focused CRISP and Data Governance slices pass as well. Ruff, compilation, report inventory, matrix validation, and diff checks pass. This hardens boundaries without proving tenant row-level isolation, live OIDC, or populated-data parity ([evidence](builds/2026-10-28-recovery/kernel-parallel-governance-work-opportunity-boundaries.json)). Checklist: 1,503 complete / 25 open (1,528 total); strict private Gateway response endpoints: 81; CLI location UUID preflight: 25 groups; matrix: 67 rows (24 baseline-retained, 7 deployed, 36 prepared).

**Previous parallel continuation — report scope, operating-pilot response, and Directus source audit (28 October 2026):** all 19 remaining single-location report generators found by source audit now reject malformed/missing UUID scope before cursor access; the private operating-pilot own-resource-request history page has a strict migration-backed response and pagination contract; and the Directus audit found no further safe managed read with direct location lineage after `digital_lego_usage`. The combined focused report/Gateway selection passes 712 tests with 7 skips; Ruff, compilation, report inventories, matrix validation, and diff checks pass. Effective Directus permissions, populated parity, live OIDC/database behavior, and polymorphic source lineage remain open ([evidence](builds/2026-10-28-recovery/kernel-parallel-report-gateway-acceptance.json)). Checklist: 1,491 complete / 25 open (1,516 total); strict private Gateway response endpoints: 76; tenant adapter: 28 location-scoped collections.

**Latest parallel continuation — renewable report, pollinator CLI, own-capacity page, and Directus attestation (28 October 2026):** renewable-energy reports reject invalid location scope before database access; active pollinator CLI reads preflight UUIDs; the signed own-capacity page validates its exact projection and pagination; and Directus applies fail-closed read scope to `attestation_plan`, with writes denied. The integrated checks pass 573 Python tests and 142 Directus extension tests; build/typecheck, Ruff, compilation, report inventories, matrix validation, and diff checks pass. These source checks do not prove live Directus permissions or populated-data parity ([evidence](builds/2026-10-28-recovery/kernel-parallel-renewable-pollinator-capacity-attestation.json)). Checklist: 1,477 complete / 25 open (1,502 total); strict private Gateway response endpoints: 72.

**Latest parallel continuation — report scope and tenant response boundaries (28 October 2026):** direct `generate_gnh_alignment` calls reject invalid location scope before database access; the private mobile operations inventory now has a strict request-bound response contract; and the optional Directus hook applies fail-closed, read-only location scope to `forecast_output`. The integrated focused selection passes 422 Python tests and 138 Directus extension tests; the extension build/typecheck, Ruff, compilation, report inventories, matrix validation, and diff checks pass. This is source-level acceptance only; live Directus behavior and historical forecast lineage remain open ([evidence](builds/2026-10-28-recovery/kernel-parallel-gnh-mobile-inventory-forecast-output-boundary.json)). Checklist: 1,464 complete / 25 open (1,489 total); strict private Gateway response endpoints: 69.

**Latest parallel implementation batch (28 October 2026):** the Directus
polymorphic-history tool now reports aggregate-only lineage for explicitly
mapped sources, and its schema-only PostgreSQL replay validates both generated
queries through migration 680. It does not establish populated lineage or
effective Directus permissions; broad history/approval fields remain
permission-sensitive and unchanged. Gateway pagination now covers additional
data-stream, federation, and Baal proposal reads; the JavaScript public API has
a bounded default timeout matching Python. Federation's public list retains
the `nodes` field and now documents exact page continuation metadata, including
when its hard offset ceiling prevents another page. Five report generators reject
missing direct-call location scope before database access. Runtime SQL
inventory resolution remains conservative and the service-catalog and
benchmark-table grants stay unchanged until ownership and external writers are
reconciled; the framework-step relation also awaits a location/lifecycle
contract. No capability classification or MAN-CAP acceptance changed. The
credit-custody summary and private traceability list/detail routes now publish
strict service-derived response models; traceability preserves existing JSON
number/datetime formats and omits sensitive unneeded fields. The JavaScript SDK
rejects timer-overflow deadlines and verifies abort-timer cleanup. The full
ARM64/QEMU PostgreSQL schema replay now passes all 672 schema files through
migration 681 under verified 1.5 GiB/two-CPU limits, with network disabled,
zero seeds, and cleanup complete. That run did not include the optional
operator-scope probe; physical-device and production recovery acceptance remain
open. The ARM64 replay runner now rejects CPU limits that round to zero before
creating the disposable database; a tiny positive value previously passed
preflight and became an invalid zero-nanocpu Docker update. A further
framework-catalog review found no safe grant
revoke without owner customization-path confirmation. An additive low-dependency
`core` profile now has separately locked base dependencies and optional Web3,
spreadsheet/S3, and local-media overlays; existing full-capability profiles
remain unchanged. The release gate checks core-only and all-overlay images on
AMD64 and ARM64, with hosted CI still pending. A strict response model now
covers the location-scoped OIDC attestation list, while selected-location
tactical and State-of-Kokonut report queries keep related rows within the
requested farm and reject an empty selection. Source audits confirmed pest-
reference DML is a current CLI customization path and the legacy Yahoo price
flow is not safe to register as a scheduled job. The detailed service-health
route now requires `service_health:read` before it probes optional dependencies;
public `/health` liveness is unchanged. The default-off signed forecast worker
now reads its namespaced provider key, routed through both Kernel worker
profiles. The runtime ACL report now uses a fresh network-disabled native
replay through migration 681 and verifies current source policy, including the
`metric_definition` read-only boundary. The public driver catalog returns only
enabled display fields through bounded pagination and now propagates database
failures to a generic Gateway error; location-only tactical CLI
operations require explicit scope; and the isolated ClickHouse outbox worker
receives its dedicated password without exposing it to other isolated workers.
The replay parser derives expected ACL counts from current policy and rejects
stale counts. No additional catalog revoke was selected because
`competency_framework` may be owner-managed. The latest checklist is 1,477
complete / 25 open (1,502 total). Seventy-two private Gateway response
endpoints now publish OpenAPI success models and reject undeclared fields
while preserving existing authorization and cache behavior. The latest
contracts cover farm-activity summaries, pollution-incident resolution,
governance-tension detail, the operating-pilot resource-category page, and the
Delphi draft-study inventory. The native REST SDKs validate bounded driver
catalog shapes and requested page values; malformed HTTP error bodies use a
stable status fallback in both SDKs. Comprehensive Status now validates its
crop-NOI section against its generator while other section bodies remain
JSON-compatible pending their own audits. In particular, `farm_summary` uses
`SELECT *` on four relations and has mixed lifecycle filters, so its field
allowlist and measure semantics need review before tightening its contract.
The environmental section now validates all four explicit source projections;
its current lifecycle, ignored period, and narrative-field semantics remain
unchanged pending review. Farm-activity detail, governance-role detail,
report-review queue, Field Collector review queue, and farm-activity intake
queue responses have strict contracts. Four single-location report generators
now reject invalid IDs before database or analyzer access; direct `farm_summary`
and `regenerative_outcomes` calls also reject invalid location scope before
cursor creation.
The runtime
SQL inventory also requires explicit review for new unresolved DML/`WITH` sites;
its existing unresolved candidates remain tracked debt and the gate does not
change database grants.
Migration 681 makes `metric_definition` read-only to the general runtime and
passes disposable PostgreSQL 16 replay, read/write denial, provisioner replay,
and Directus-role preservation checks; tenant isolation remains unestablished.
The location-scoped ecocredit batch route now has a bounded response model,
the Python public SDK rejects invalid request deadlines before networking,
and Directus tenant reads deny unresolved relationship filters/sort/grouping.
The legacy health-check Prefect flow remains unregistered because it assumes
the retired full-stack topology and lacks a Kernel health contract. A static
edge Compose check locks app/database limits at 1 GiB and two CPUs; it does
not claim physical Pi runtime acceptance.
matrix classifications remain 24 baseline-retained, 7 deployed, and 36
prepared across 67 rows. The preceding private-read continuation added response
contracts for Delphi consent and consultation, independent Delphi review,
stakeholder identity/trust pages, and the waste incident review queue. Cursor
ordering, blockers, pagination ceilings, and source-backed nested projections
are checked at runtime; the consultation JSONB timestamp parser requires an
explicit UTC offset. The combined focused selection passes 198 tests and the
SQL inventory remains current on Python 3.11/3.12. This parallel batch adds
strict private list/detail response contracts for Delphi participant invites
and threatcasting backcast plans, closes the two typed MRV sensor references in
the optional Directus tenant hook, and makes four State-of-Kokonut funding
queries statically auditable with named scope binds. The focused Python
selection passes 279 tests; the Directus tenant-hook suite passes 16 tests and
its extension build/typecheck succeeds. Report inventories are current, and
the runtime SQL inventory is current on Python 3.11/3.12 with the same 37
unresolved candidates. No database, provider, candidate, or legacy service was
used. That batch recorded 54 strict private Gateway response endpoints
([evidence](builds/2026-10-28-recovery/kernel-parallel-contract-and-scope-batch.json)).
This continuation adds the strict governance-tension review-queue response
contract and corrects the weekly Prefect flow description to match its actual
climate-only execution. Its governance/Prefect selection passes 39 tests;
Ruff, compilation, and runtime SQL inventory checks on Python 3.11/3.12 pass.
That batch recorded 55 endpoints. This continuation adds a strict minimal
response contract for the private stakeholder identity resolution route; its
focused three-file selection passes 31 tests, and runtime SQL inventory checks
remain current on Python 3.11/3.12. The current endpoint count is 56. A source
audit found no safe runtime ACL migration: `consent_data_type` remains owner-
configurable and is updated by migrations. C6's remaining gaps still require
policy or populated/runtime acceptance. This continuation adds a strict
location/study-bound response contract for Delphi study-open readiness and
aligns Python and JavaScript REST SDK errors to retain the received HTTP
response object. The combined Delphi/policy/SDK selection passes 67 Python
tests and 28 JavaScript tests; the SDK TypeScript build passes. A second C1
candidate, `bio_ingredient_composition_reference`, remains mutable under its
governed lifecycle and agent-write allowlist, so its grants stay unchanged.
The current endpoint count is 57. No capability classification or MAN-CAP
acceptance changed.

The latest response-contract continuation adds strict contracts for AI-summary
review-list, business-canvas version history, sequential-evidence summary and
events, and nutrient soil-test/input/removal reads. It preserves migration-
defined network source scopes and worker-attribution blockers, validates the
canonical projections and request identities, and prevents pagination beyond
offset 10,000. The combined selection passes 157 tests; no capability
classification or MAN-CAP acceptance changes ([evidence](builds/2026-10-28-recovery/gateway-private-read-contracts-batch-4.json)).

The enabled public driver catalog now has a stable versioned `/api/v1/drivers`
read with bounded pagination and generated typed Python/TypeScript clients.
The optional Directus tenant hook also scopes writable-reference lookups by the
requested location and uses one generic unavailable response for missing and
foreign-location references. These are source/API contract checks; they do not
establish live Directus role/field/row parity or populated-data parity.
Checklist: 1,401 complete / 25 open (1,426 total).

**Latest parallel batch — irrigation, landscape, and pollinator response contracts (28 October 2026):** the private irrigation status route now publishes and enforces a strict nested response model, including zone-state enums, requested-location identity, and query-consistent pagination. Landscape conservation and pollinator health summaries now validate their nested aggregate projections against source enums, bounded group dimensions, strict counts, finite values, and the requested location. All three preserve existing authorization and cache/error behavior and return sanitized no-store errors for invalid projections. The combined route selection passes 77 tests; Ruff, compilation, capability-matrix validation, and diff checks pass. No live database/provider was used. This closes source/API contracts only; live OIDC, populated-data parity, and tenant isolation remain open ([irrigation evidence](builds/2026-10-28-recovery/irrigation-status-response-contract.json); [landscape evidence](builds/2026-10-28-recovery/landscape-summary-response-contract.json); [pollinator evidence](builds/2026-10-28-recovery/pollinator-summary-response-contract.json); [combined evidence](builds/2026-10-28-recovery/irrigation-landscape-pollinator-response-contract-batch.json)). Checklist: 1,401 complete / 25 open (1,426 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Previous parallel batch — nutrient, strategy, and competitive-landscape response contracts (28 October 2026):** Three additional private Gateway endpoints now publish strict OpenAPI success models and validate service projections at runtime. Nutrient balances validate aggregate types and terminal pagination; strategy plans match migration 452's page/offset bounds and omit private rationale, party identities, amounts, and execution authority; competitive-landscape summaries expose aggregate fields while excluding identities, evidence, and signal content. The combined route suite passes 182 tests. CI's Python 3.12 runtime-SQL inventory failure was traced to empty `type_params=[]` in AST dumps and fixed with version-stable normalization; the 37-candidate ledger and pinned digest are unchanged. The inventory gate passes under Python 3.11 and 3.12, and its 24-test regression suite, Ruff, compilation, matrix validation, and diff check pass. No database/provider or candidate/legacy service was used. These are source/API contracts only; live OIDC, populated-data parity, and broader tenant isolation remain open ([nutrient](builds/2026-10-28-recovery/nutrient-balances-response-contract.json); [strategy](builds/2026-10-28-recovery/strategy-plan-response-contract.json); [competitive landscape](builds/2026-10-28-recovery/competitive-landscape-response-contract.json); [Python 3.12 inventory repair](builds/2026-10-28-recovery/runtime-sql-inventory-python312-ast-normalization.json); [combined evidence](builds/2026-10-28-recovery/gateway-nutrient-strategy-competitive-response-contract-batch.json)). Checklist: 1,405 complete / 25 open (1,430 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest parallel batch — crop, geostatistics, trend, management, business-planning, and budget response contracts (28 October 2026):** Eleven private GET endpoints across six Gateway families now publish strict OpenAPI response models and validate their service projections, request identities, schema values, and bounded pages. The contracts preserve current authorization and sanitized error/cache behavior while excluding raw simulation configuration/errors/costs, unneeded analytic metadata, participant evidence/identity, task text, and budget assumptions/counterparty detail. Crop simulation, business-planning canvases, and planning budgets now stop continuation when the next page would exceed offset 10,000. The combined focused selection passes 188 tests; crop boundary regressions cover offsets 9,975, 9,976, and 10,000. Ruff, compilation, capability validation, evidence JSON parsing, and diff checks pass. No live database/provider, candidate, or legacy service was used. These source/API contracts do not establish populated-data parity, live OIDC/browser behavior, broader tenant isolation, or physical Pi acceptance ([crop](builds/2026-10-28-recovery/crop-simulation-response-contract.json); [geostatistics](builds/2026-10-28-recovery/geostatistics-autocorrelation-response-contract.json); [trend analysis](builds/2026-10-28-recovery/trend-analysis-get-response-contracts.json); [management work](builds/2026-10-28-recovery/management-work-summary-response-contract.json); [business planning](builds/2026-10-28-recovery/business-planning-canvas-response-contract.json); [planning budget](builds/2026-10-28-recovery/planning-budget-summary-response-contract.json); [combined evidence](builds/2026-10-28-recovery/gateway-private-response-contracts-batch-2.json)). Checklist: 1,411 complete / 25 open (1,436 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

The regenerated runtime SQL inventory is current on Python 3.11 and 3.12; all 37 unresolved-write review entries remain unchanged. The 24-test inventory regression suite also passes.

Evidence: [Directus schema check](builds/2026-10-28-recovery/directus-polymorphic-lineage-schema-disposable.json),
[report query inventory](report-generator-query-scope-inventory.json),
[runtime SQL resolution](builds/2026-10-28-recovery/runtime-sql-local-query-resolution.json),
[data-stream pagination](builds/2026-10-28-recovery/data-stream-post-list-pagination-openapi.json),
[federation pagination](builds/2026-10-28-recovery/federation-node-list-pagination.json),
[Baal proposal pagination](builds/2026-10-28-recovery/baal-proposal-list-pagination-openapi.json),
[credit-custody response contract](builds/2026-10-28-recovery/credit-custody-response-model-contract.json),
[traceability response contract](builds/2026-10-28-recovery/traceability-response-contract.json),
[SDK timer overflow check](builds/2026-10-28-recovery/sdk-javascript-timeout-overflow.json),
[ARM64 schema replay through 681](builds/2026-10-28-recovery/arm64-resource-limited-schema-681.json),
[core profile contract](builds/2026-10-28-recovery/kernel-core-profile-contract.json),
[attestation response contract](builds/2026-10-28-recovery/attestation-response-model-contract.json),
[tactical report scope](builds/2026-10-28-recovery/tactical-layer-companion-location-scope.json),
[State of Kokonut scope](builds/2026-10-28-recovery/state-of-kokonut-selected-actor-scope.json),
[pest-reference audit](builds/2026-10-28-recovery/pest-reference-runtime-write-audit.json),
[Yahoo price-flow audit](builds/2026-10-28-recovery/yahoo-price-feed-contract-audit.json),
[metric-definition ACL](builds/2026-10-28-recovery/runtime-scoped-write-boundary-disposable.json),
[ecocredit response contract](builds/2026-10-28-recovery/ecocredit-batch-response-contract.json),
[Python SDK deadline](builds/2026-10-28-recovery/sdk-python-public-api-timeout-parity.json),
[Directus relation boundary](builds/2026-10-28-recovery/directus-relation-query-boundary.json),
[health-check flow audit](builds/2026-10-28-recovery/prefect-health-check-contract-audit.json),
[edge resource contract](builds/2026-10-28-recovery/edge-compose-resource-contract.json),
[detailed health route boundary](builds/2026-10-28-recovery/detailed-health-route-auth-boundary.json),
[forecast provider-key routing](builds/2026-10-28-recovery/weather-forecast-provider-key-routing.json),
[runtime ACL report provenance](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json),
[full native schema and operator-scope replay through 681](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json),
[public driver catalog](builds/2026-10-28-recovery/public-driver-catalog-projection.json),
[tactical analytics CLI scope](builds/2026-10-28-recovery/analytics-tactical-cli-scope-preflight.json),
[ClickHouse worker secret routing](builds/2026-10-28-recovery/worker-clickhouse-secret-routing.json),
[competency framework write audit](builds/2026-10-28-recovery/competency-framework-runtime-write-audit.json),
[impact-framework catalog audit](builds/2026-10-28-recovery/impact-framework-catalog-candidate-audit.json),
[EBF scope](builds/2026-10-28-recovery/ebf-scorecard-location-scope.json),
[versioned driver API/SDK parity](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json),
[Directus tenant-reference non-disclosure](builds/2026-10-28-recovery/directus-tenant-reference-nondisclosure.json).

**Latest runtime-role boundary — migration 680 (28 October 2026):** the
location-scoped `yield_benchmark` table is now SELECT-only for
`kokonut_runtime`. Source review found one application caller, the read in
`services/analytics/yield_monitoring.py::compare_benchmark`, and no application
write path. The prior migration-679 full-schema ACL evidence showed runtime
SELECT/INSERT/UPDATE/DELETE and disabled RLS. Migration 680 removes runtime
table and column mutation/reference grants, restores SELECT, and leaves
`kokonut_directus_runtime` grants unchanged; the runtime provisioner reapplies
the same boundary after broad compatibility grants. Focused PostgreSQL 16
disposable checks pass migration replay, a synthetic-row read, table write,
TRUNCATE, REFERENCES, TRIGGER and column-write denials, plus Directus-grant
preservation before and after provisioner reapplication ([migration](../schemas/postgres/680_runtime_yield_benchmark_read_only.sql);
[evidence](builds/2026-10-28-recovery/yield-benchmark-runtime-read-only-disposable.json)).
This is only a DML boundary: RLS remains disabled, tenant isolation is not
established, and full-schema replay remains through 679. Candidate/legacy,
seed, and farm data were untouched. No capability classification or MAN-CAP
acceptance changed. Checklist: 1,351 complete / 25 open (1,376 total).

**Latest full native schema and ACL replay — migration 681 (28 October 2026):**
all 672 ordered schema files applied in a network-disabled PostgreSQL 16
container with verified 1.5 GiB/two-CPU limits, no host ports, seeds, or farm
data, and successful cleanup. The runtime/operator probe passed the synthetic
two-tenant checks, including 79 private relations, 46 mutation-denied
relations, two append-only ledgers, and zero direct table/column privilege
violations. The refreshed source/ACL report observes migration 681 and current
runtime policy; `metric_definition` is now effectively SELECT-only. This is
disposable synthetic evidence: candidate/legacy databases were untouched,
tenant isolation is not established globally, and 992 relations still have
table DML while RLS is disabled. Physical Raspberry Pi and production
acceptance remain open ([replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json);
[ACL report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json)).

**Latest parallel report-scope and Gateway contract batch (28 October 2026):**
direct generation now requires location scope for the location-only strategy,
Kokonut Commons, and perpetual-value-stress reports; unlineaged stakeholder
and fork data stays in explicit network reports. The generated report inventory
records 94 report types, 167 direct queries, 166 positional-bind sites, and
zero unresolved or mismatched sites. Gateway/operator routes now publish and
enforce their existing pagination bounds; the changed route selection passes
732 tests. Integrated report checks pass 563 tests with four
database-dependent skips; the platform-integrity selection passes 374 tests
and six subtests. Directus hooks pass 120 tests and build/typecheck, JavaScript
SDK tests pass 56 with a successful TypeScript build, and the focused Python
SDK/outbox/worker selection passes 113 tests. Ruff, Python compilation,
dependency/provider boundaries, capability validation, and diff checks pass.
No migration, provider, candidate, or legacy database was used. Capability
classifications remain 24 baseline-retained, 7 deployed, and 36 prepared
across 67 rows; no MAN-CAP acceptance changed. Checklist: 1,350 complete /
25 open (1,375 total) ([report inventory](report-generator-query-scope-inventory.json);
[Kokonut Commons](builds/2026-10-28-recovery/kokonut-commons-report-location-scope.json);
[strategy scope](builds/2026-10-28-recovery/stakeholder-outcomes-direct-scope.json);
[perpetual stress](builds/2026-10-28-recovery/perpetual-value-stress-location-scope.json);
[Delphi workspace](builds/2026-10-28-recovery/delphi-participant-workspace-pagination-openapi.json);
[operator lists](builds/2026-10-28-recovery/operator-list-pagination-openapi-bounds.json);
[combined verification](builds/2026-10-28-recovery/parallel-report-gateway-contracts.json)).

**Latest parallel source/portability batch (28 October 2026):** the optional
Directus hook resolves current workflow role names on each authorization check;
the adoption-barrier, bio-recipe, community-governance, governance-inclusion,
governance-throughput, replication-readiness, and scaling-roadmap reports now
require explicit location scope before direct database access, consistent with
their registry/CLI contracts. Four location-lineaged stakeholder reports keep
the same explicit-scope contract. The full ARM64/QEMU replay applied all 670
schemas through migration 679 under verified 1.5 GiB/two-CPU limits, with no
seeds, failures, OOM, or leftover resources. Delphi source rows are checked
against requested study and location; Python/TypeScript field projections and
report-snapshot schema types now align. Notification bounds reject booleans.
Gateway list routes for ecocredits, attestations, Field Activity, nutrients,
irrigation, crop simulations, traceability, geostatistics, trend analysis,
extension learning, and pollinator health publish and enforce downstream
page-size/offset limits. Competitive-landscape, business-architecture,
Delphi-consultation, Delphi draft-study/review, stakeholder identity, and
business-planning/history, strategy, sequential-decision, governance-role,
and planning-budget lists also publish service bounds in OpenAPI and reject
invalid paging before service access; threatcasting and Delphi invite/consent queues do the same. All 21 operating-
pilot list routes and 25 solution-lifecycle list routes now expose their service-aligned
limits. Nutrient offsets and the pollution-incident queue offset now publish
the service caps in OpenAPI too.
The integrated report selection passes 516 tests with four database-dependent
skips; Gateway route checks pass 113 tests before the latest geostatistics,
trend-analysis, extension-learning, pollinator, Delphi, and business-route additions. Directus hook tests pass 120,
notification tests 40, schema parity tests 13, and Delphi tests 3. QEMU is
software portability evidence only, not physical Pi or production-recovery
acceptance. C4 review found no safe schedule to activate without owner/runtime
confirmation. No capability classification or MAN-CAP acceptance changed
([Directus evidence](builds/2026-10-28-recovery/directus-role-resolution-freshness.json); [report-scope evidence](builds/2026-10-28-recovery/replication-readiness-location-scope.json); [roadmap evidence](builds/2026-10-28-recovery/scaling-roadmap-location-scope.json); [Gateway pagination evidence](builds/2026-10-28-recovery/gateway-pagination-openapi-bounds.json); [Field Activity](builds/2026-10-28-recovery/farm-activity-pagination-openapi-bounds.json); [nutrients](builds/2026-10-28-recovery/nutrient-pagination-openapi-bounds.json); [nutrient offsets](builds/2026-10-28-recovery/nutrient-pagination-offset-bounds.json); [irrigation](builds/2026-10-28-recovery/irrigation-pagination-openapi-bounds.json); [crop simulations](builds/2026-10-28-recovery/crop-simulation-pagination-openapi-bounds.json); [traceability](builds/2026-10-28-recovery/traceability-pagination-openapi-bounds.json); [geostatistics](builds/2026-10-28-recovery/geostatistics-pagination-openapi-bounds.json); [trend analysis](builds/2026-10-28-recovery/trend-analysis-pagination-openapi-bounds.json); [extension learning](builds/2026-10-28-recovery/extension-learning-pagination-openapi-bounds.json); [pollinator health](builds/2026-10-28-recovery/pollinator-pagination-openapi-bounds.json); [Delphi consultation](builds/2026-10-28-recovery/delphi-consultation-pagination-openapi-bounds.json); [competitive landscape](builds/2026-10-28-recovery/competitive-landscape-pagination-openapi-bounds.json); [business architecture](builds/2026-10-28-recovery/business-architecture-pagination-openapi-bounds.json); [Delphi recommendation drafts](builds/2026-10-28-recovery/delphi-draft-study-pagination-openapi-bounds.json); [stakeholder identity](builds/2026-10-28-recovery/stakeholder-identity-pagination-openapi-bounds.json); [business planning](builds/2026-10-28-recovery/business-planning-pagination-openapi-bounds.json); [stakeholder trust](builds/2026-10-28-recovery/stakeholder-identity-trust-pagination-openapi-bounds.json); [Delphi minority review](builds/2026-10-28-recovery/delphi-minority-review-pagination-openapi-bounds.json); [Delphi recommendation review](builds/2026-10-28-recovery/delphi-recommendation-review-pagination-openapi-bounds.json); [AI-summary review](builds/2026-10-28-recovery/ai-summary-review-pagination-openapi-bounds.json); [strategy](builds/2026-10-28-recovery/strategy-pagination-openapi-bounds.json); [sequential decisions](builds/2026-10-28-recovery/sequential-decision-pagination-openapi-bounds.json); [governance roles](builds/2026-10-28-recovery/governance-role-pagination-openapi-bounds.json); [planning budgets](builds/2026-10-28-recovery/planning-budget-pagination-openapi-bounds.json); [business-planning history](builds/2026-10-28-recovery/business-planning-edit-history-pagination-openapi.json); [threatcasting](builds/2026-10-28-recovery/threatcasting-pagination-openapi-bounds.json); [Delphi invites](builds/2026-10-28-recovery/delphi-participant-invite-pagination-openapi.json); [Delphi consent](builds/2026-10-28-recovery/delphi-consent-notice-pagination-openapi-bounds.json); [operating pilot](builds/2026-10-28-recovery/operating-pilot-pagination-openapi-bounds.json); [solution lifecycle](builds/2026-10-28-recovery/solution-lifecycle-pagination-openapi-bounds.json); [waste incident offset](builds/2026-10-28-recovery/waste-incident-offset-bounds.json)).
Checklist: 1,345 complete / 25 open (1,370 total); classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest SDK parity update — typed list extension queries (28 October 2026):**
Python now exposes `ListOptions.extra_params` through typed accessors, matching
TypeScript `ListOptions.extraParams`. Both clients retain Directus-specific
query extensions while standard list controls and the location helper's scope
remain authoritative. The focused Python SDK/method-parity suite passes 107
tests, JavaScript passes 56, and the TypeScript build and targeted Ruff pass;
all client checks use mocks. This is a query-shape improvement only and does
not establish authorization or tenant isolation. Broader SDK parity remains
open ([evidence](builds/2026-10-28-recovery/sdk-typed-extension-query-parity.json)).
Checklist: 1,300 complete / 25 open (1,325 total); classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Previous runtime-role acceptance update — migration 679 (28 October 2026):**
Migration 112 defines and seeds nine shared `quantity_unit` labels. Runtime
SQL and source review found no relation read or application write target.
Migration 679 and runtime provisioning keep the catalog readable but immutable
to `kokonut_runtime`, with separate Directus administration grants preserved.
Focused native and ARM64/QEMU PostgreSQL 16 checks pass migration replay,
SELECT, write/column denial, provisioner reapplication, and Directus grant
preservation. A network-disabled native replay applies all 670 ordered schemas
through 679 and passes 34 synthetic two-tenant checks under verified 1.5
GiB/two-CPU limits. It verifies 126 declared runtime controls with no direct
privilege violations. The refreshed report has zero source-policy mismatches
across 1,511 relations; 994 retain effective DML while RLS is disabled, so C1
remains open. Candidate/legacy databases are untouched; no optional seeds or
farm data were loaded. QEMU is software portability evidence only, not physical
Raspberry Pi acceptance. Capability classifications and MAN-CAP acceptance
are unchanged. Checklist: 1,299 complete / 25 open (1,324 total).
[Migration](../schemas/postgres/679_runtime_quantity_unit_read_only.sql),
[native ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-disposable.json),
[ARM64/QEMU ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-arm64-disposable.json),
[full native replay](builds/2026-10-28-recovery/runtime-role-full-schema-679-native-disposable.json),
[source/ACL report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json).

**Previous runtime-role acceptance update — migration 678 (28 October 2026):**
Schema 142's shared `market_reference_data` catalog has no service or extension
write callsite. Migration 678 keeps SELECT and denies table/column mutation to
`kokonut_runtime`, and runtime provisioning reapplies the boundary while the
separate Directus administration grants remain unchanged. Native and
ARM64/QEMU PostgreSQL 16 checks pass migration replay, read access, write and
stale column-grant denial, provisioner reapplication, and synthetic Directus
grant preservation. A fresh network-disabled native replay applies all 669
ordered schemas through 678 and passes 33 synthetic two-tenant checks under
verified 1.5 GiB/two-CPU limits. It verifies 125 runtime controls (79 private,
43 mutation-denied, two append-only, plus the API-key column boundary) with no
direct table/column violations. The refreshed report has zero source-policy
mismatches across 1,511 relations; 995 relations still retain effective DML
while RLS is disabled, so C1 remains open. Candidate and legacy databases are
untouched; no optional seeds or farm data were loaded. This is synthetic
software-portability evidence and ARM64/QEMU does not establish physical
Raspberry Pi acceptance. Capability classifications remain 24
baseline-retained, 7 deployed, and 36 prepared across 67 rows; MAN-CAP
acceptance is unchanged. Checklist: 1,298 complete / 25 open (1,323 total).
[Migration](../schemas/postgres/678_runtime_market_reference_data_read_only.sql),
[native ACL](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-disposable.json),
[ARM64/QEMU ACL](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-arm64-disposable.json),
[full native replay](builds/2026-10-28-recovery/runtime-role-full-schema-678-native-disposable.json),
[source/ACL report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json).

**Historical runtime-role acceptance update (27 October 2026):** Focused native and
ARM64/QEMU disposable PostgreSQL 16 checks pass migrations 673–677. A fresh
native AMD64 replay of all 668 ordered schema files through migration 677 passes
the full provisioner and all 32 two-tenant operator-scope checks under verified
1.5 GiB memory/swap and two-CPU database limits. The probe verifies 124
declared runtime-role controls: 79 private relations, 42 mutation-denied
relations, two append-only relations, and the API-key read-only column
boundary. It reports zero direct table or column privilege violations across
1,511 public relations; 996 relations retain effective table-level DML while
RLS is disabled. Broad compatibility DML and non-universal application-table
RLS remain open C1 concerns. The replay loaded no optional seed files or farm
data, published no ports, was not OOM-killed, and removed temporary resources.
It read the USD currency inserted by the ordered finance migration, the
schema-defined `fall_armyworm` degree-day default, and the seeded farmer
credential-type guidance catalog. Optional seeds 015, 069, and 088 and other
seed-dependent catalogs were not loaded, so revenue-multiplier configuration
and crop GDD seed parity remain unverified. Focused ACL checks use synthetic
relations and verify grants, not general populated-data parity. This is
synthetic software-portability evidence, not candidate/production state,
universal tenant isolation, populated-data acceptance, or physical Raspberry
Pi acceptance ([full native schema and scope evidence through 677](builds/2026-10-27-recovery/runtime-role-full-schema-677-native-disposable.json);
[farmer credential-type native ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-disposable.json);
[farmer credential-type ARM64/QEMU ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-arm64-disposable.json);
[native revenue-multiplier ACL](builds/2026-10-27-recovery/revenue-multiplier-config-runtime-read-only-disposable.json);
[ARM64/QEMU revenue-multiplier ACL](builds/2026-10-27-recovery/revenue-multiplier-config-runtime-read-only-arm64-disposable.json);
[native pest degree-day ACL](builds/2026-10-27-recovery/pest-degree-day-config-runtime-read-only-disposable.json);
[ARM64/QEMU pest degree-day ACL](builds/2026-10-27-recovery/pest-degree-day-config-runtime-read-only-arm64-disposable.json);
[native crop GDD ACL](builds/2026-10-27-recovery/crop-gdd-config-runtime-read-only-disposable.json);
[ARM64/QEMU crop GDD ACL](builds/2026-10-27-recovery/crop-gdd-config-runtime-read-only-arm64-disposable.json);
[native currency ACL](builds/2026-10-27-recovery/dfs-currency-runtime-read-only-disposable.json);
[ARM64/QEMU currency ACL](builds/2026-10-27-recovery/dfs-currency-runtime-read-only-arm64-disposable.json);
[expense-category native ACL](builds/2026-10-27-recovery/expense-category-runtime-read-only-disposable.json);
[CRISP-dimension native ACL](builds/2026-10-27-recovery/crisp-risk-dimension-runtime-read-only-disposable.json);
[CRISP-dimension ARM64/QEMU ACL](builds/2026-10-27-recovery/crisp-risk-dimension-runtime-read-only-arm64-disposable.json);
[prior policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
No optional seed files or farm data were loaded, no ports were published,
temporary resources were removed, and no physical Raspberry Pi acceptance is
claimed; these are software-portability results only. Schema-defined rows from
migrations, including the credential-type guidance catalog, were applied.
The current base and ClickHouse-superset Kernel app OCI targets build for
AMD64/ARM64 with 72 and 75 matching locked Python packages, respectively.
Offline ARM64 smokes import the Gateway/runtime-role policy and optional
ClickHouse client, and the minimal, edge, standard, and analytics Compose
selections validate for ARM64. The current Gateway also passes a no-network
ARM64 runtime liveness check under verified 512 MiB, one-CPU, 64-PID limits,
with a read-only root filesystem and bounded writable tmpfs. This checks
process health only, not schema readiness or database/provider paths. The four
remaining optional Dockerfile targets (gRPC, MQTT, OIDC, and ML anomaly) now
also build for ARM64 from revision 8da25cfd and pass bounded, network-disabled,
read-only import and CLI-help smokes. The OIDC smoke found and verified a fix
for Authlib's missing HTTP client dependency. No external service was started;
broader profile, provider, and physical-device gates remain open
([optional target evidence](builds/2026-10-27-recovery/arm64-optional-kernel-targets-8da25cfd.json)).
The synthetic age-encrypted single-database rehearsal was repeated against
the 653-migration schema through migration 662; later migrations, including
667, have not yet been added to that restore rehearsal. The repository checkpoint
command produced an encrypted archive without a plaintext disk dump; the
documented role prerequisites and atomic restore yielded matching migration
fingerprints and a synthetic sentinel in a fresh database. This remains
synthetic local evidence, not populated-data, provider/media, R2, whole-platform
or production RPO/RTO acceptance
([build/profile evidence](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json);
[prior 643/652 rehearsal](builds/2026-10-27-recovery/kernel-checkpoint-restore-disposable.json);
[current 653/662 rehearsal](builds/2026-10-27-recovery/kernel-checkpoint-restore-current-schema.json)).
The complete schema through migration 662 replays on ARM64/QEMU under a
verified 1.5 GiB memory/swap and two-CPU database budget with all 653 files
applied, no OOM kill, and successful cleanup; this does not verify physical Pi
hardware
([resource-limited replay](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json)).
See [synthetic backup/restore evidence](builds/2026-10-27-recovery/kernel-synthetic-backup-restore.json).
The app runtime limit result is recorded in
[constrained ARM64 runtime evidence](builds/2026-10-27-recovery/kernel-app-arm64-constrained-runtime.json).

**C1 analytics write-candidate inventory (27 October 2026):** The refreshed
source-line report joins the runtime ACL snapshot with SQL inventory v2, which
separates DML targets from source relations. It identifies 273 candidate
relations and 425 target sites across 89 source files, with no unmatched
candidate sites. The full migration-675 probe verifies 122 declared runtime
controls with zero policy mismatches; 998 relations still retain effective
DML while RLS is disabled. This is not universal tenant isolation. The source
report is heuristic and candidate writers still need callsite review. Recent
read-only runtime policies include seeded factor and benchmark catalogs,
`operations_protocol`, `process_maturity_level`,
`pollinator_species_reference`, `gri_indicator`, `governance_framework`,
`impact_framework`, `impact_dimension`, `expense_category`,
`crisp_risk_dimension`, `dfs_currency`, `crop_gdd_config`,
`pest_degree_day_config`, `revenue_multiplier_config`, and `reference_class`; migrations 668–676
change only the Kernel runtime
role and preserve SELECT. Directus
grants are preserved by focused ACL checks, but Directus API row/role parity is
not implied. Seeded registry, impact, expense-category, and CRISP-dimension
contents were not loaded in the full replay. Runtime relation and function scope limits remain
documented in the report
([inventory](builds/2026-10-27-recovery/analytics-runtime-write-candidate-inventory.json);
[generator](../scripts/runtime-analytics-write-candidate-inventory.py);
[ACL report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).

**C2 public OpenAPI export boundary (27 October 2026):** The native contract
exporter now excludes routes whose registered policy is private and accepts
only public GET/read operations. This keeps versioned but authenticated Gateway
routes out of the public OpenAPI snapshot and SDK generation input. A regression
confirms the checked-in snapshot matches current source and omits the private
Baal governance operations; 39 public API, policy, and governance tests pass.
The broader Python SDK method/schema/gRPC selection passes 118 tests, the
JavaScript SDK passes 56, and the TypeScript SDK passes 35; JavaScript and
TypeScript builds and the generated public SDK freshness check also pass. This
does not close route-level authorization, all SDK/service parity, or release acceptance
([exporter](../scripts/export_public_api_openapi.py);
[regression](../tests/test_public_api_openapi.py)). Checklist: 1,265 complete /
26 open (1,291 total); capability classifications remain 24 baseline-retained,
7 deployed, and 36 prepared across 67 rows.

**Sprint tenant and identity evidence (26 October 2026):** CAP-053's real
runtime and operator-auth principals passed a two-tenant synthetic forced-RLS
probe after a clean 642-migration replay. The pre-provisioning inventory counted
1,101 public tables with runtime table-level DML and RLS disabled; the full
provisioning probe reduced that count to 1,026, but neither measurement proves
universal tenant isolation
([evidence](builds/2026-10-26-recovery/sprint-full-schema-operator-scope.json)).
The optional ZITADEL provider now starts on a fresh isolated volume and returns
its expected issuer internally after a token-volume permissions fix
([evidence](builds/2026-10-26-recovery/sprint-zitadel-provider-smoke.json)).
This advances CAP-053 and the shared workflow prerequisite for CAP-001/CAP-047;
browser, HTTPS and end-to-end authorization remain open. Classifications and
MAN-CAP acceptance do not change.

**Historical baseline (26 October 2026):** The pre-provisioning relation
inventory counted 1,101 ordinary/partitioned public tables with effective
runtime DML while RLS was disabled. After the provisioner ran, that full-schema
snapshot counted 1,026 such tables. The static source comparison at that time
covered 91 scoped table policies plus the API-key read-only column allowlist,
with zero missing or mismatched policy. The current 27 October results above
supersede that snapshot. The callsite inventory remains heuristic and is not a
complete SQL reachability or authorization proof. The migration-installed
bootstrap, API-key boundary, and bounded operator-context behavior passed on a
disposable full-schema database. No candidate or production role rollout
occurred
([ACL inventory](builds/2026-10-26-recovery/sprint-runtime-relation-privilege-inventory.json);
[callsite report](builds/2026-10-26-recovery/sprint-runtime-privilege-callsite-report.json)).
The tracker now records 1,287 completed and 25 open checklist items (1,312
total); the 67 capability classifications remain 24 baseline-retained, 7
deployed, and 36 prepared.

**Sprint planning checkpoint (26 October 2026):** On `develop` at `ef29f193`,
the matrix validates 67 rows: 24 baseline-retained, seven deployed, and 36
prepared; the 67 MAN-CAP checks remain separately open. The proposed
[authenticated farm workflow sprint](sprint-kernel-workflow-acceptance.md)
advances CAP-001, CAP-047, and CAP-053 with a narrow CAP-007 reporting slice.
Planning does not change their classifications or constitute acceptance.

**Directus metric-value location boundary (26 October 2026):** The optional Directus adapter now requires an exact location grant for `metric_value` reads, denies null-location rows on result recheck, and rejects create/update/delete. The Auditor field allowlist exposes metric results while excluding source-record IDs, metadata, reviewer identity, and verification notes. All 118 Directus hook tests and two permission-inventory tests pass; build/typecheck, Ruff, inventory freshness, capability validation, and a pinned Directus 12.1.1 disposable seed apply/replay pass. Replay repairs a simulated old wildcard, preserves the permission snapshot, and cleans its temporary project. No populated metric rows or candidate/legacy databases were used. Directus parity remains open for populated API behavior, live grants, other collections, and hooks/schedules ([evidence](builds/2026-10-26-recovery/directus-metric-value-location-scope.json)). Checklist: 1,233 complete / 25 open (1,258 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Directus dashboard field permission defense-in-depth (26 October 2026):** The repository-managed Auditor policy now has an explicit dashboard metadata field allowlist that excludes archived `query_sql`. The idempotent permission seed repairs an existing wildcard and preserves non-wildcard explicit field lists. A fresh pinned Directus 12.1.1 profile confirms the 175 managed permission rows, applies and replays the seed, and restores a simulated pre-existing wildcard to the explicit list without changing the permission snapshot. The source-inventory selection passes 6 tests; Ruff, Python compilation, seed-inventory freshness, and matrix validation pass. No candidate or legacy database was used. This records effective stored permissions for a fresh managed profile, not API behavior for populated dashboard data or operator-created policies ([evidence](builds/2026-10-26-recovery/directus-dashboard-field-allowlist-disposable.json); [source inventory](builds/2026-10-20-recovery/directus-permission-source-inventory.json)). Checklist: 1,232 complete / 25 open (1,257 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Dashboard SQL query-side-channel guard (26 October 2026):** The Directus hook denies explicit or aliased `query_sql` projections and its use in filters, sorting, grouping, and aggregates; broad collection search is denied while the archived SQL field remains stored. These requests receive a generic 403 before collection data access. Normal metadata queries and wildcard/default projections remain available, and the read hook removes the legacy field from returned items/pages without mutating source records. The full 117-test hook suite and extension build/typecheck pass. No database or live Directus runtime was used; effective field permissions, pinned-version runtime acceptance, and populated dashboard parity remain open ([evidence](builds/2026-10-26-recovery/dashboard-query-sql-query-oracle.json)). Checklist: 1,232 complete / 25 open (1,257 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


**Dashboard query SQL response redaction (26 October 2026):** Current Directus dashboard dataset reads omit archived `query_sql`, including single items and pages; the hook preserves source objects and existing database rows. The OpenAPI response schema no longer exposes the field, while SDK types retain a deprecated optional property for older servers. The write hook continues to reject attempts to set it. The 106-test Directus extension suite, 94 OpenAPI/SDK checks, extension and SDK builds, Ruff, compilation, matrix validation, and diff checks pass. No Directus runtime or database was used. Effective deployed field permissions and pinned-version runtime acceptance remain open ([evidence](builds/2026-10-26-recovery/dashboard-query-sql-read-redaction.json)). Checklist: 1,232 complete / 25 open (1,257 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Dashboard OpenAPI query-ID contract (26 October 2026):** The Directus OpenAPI create/update schemas now use registered `query_id` and omit stored `query_sql`; the read model retains that legacy field only as deprecated, read-only compatibility data. A Directus hook rejects writes that include `query_sql`, including null assignments, with a client error; Python/TypeScript SDK documentation and export guides match the runtime query registry. The focused OpenAPI, SDK, reader, and refresher selection passes 139 tests; all 103 Directus hook tests and the extension build/typecheck pass; Ruff, Python compilation, OpenAPI YAML parsing, and diff checks pass. Deployed Directus field masking, populated semantic output, external consumer authorization, and dashboard ownership remain open ([evidence](builds/2026-10-26-recovery/dashboard-openapi-query-id-contract.json)). Checklist: 1,231 complete / 25 open (1,256 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Unsupported dashboard rows skip cleanly (26 October 2026):** `dataset_refresh --all` now preflights each active row against the fixed query registry and valid exact-location contract. Legacy rows with no query ID, unknown IDs, and missing/invalid location scope are counted as skipped without opening the reporting reader or writing a refresh-failure record. Explicit `--dataset-id` attempts reject unsupported configuration before metadata writes. The 198-test reporting-reader, refresher, and scheduler-contract selection passes with Ruff, compilation, generated inventories, and matrix validation; no database/provider/candidate/legacy service was used ([implementation](../services/export/dataset_refresh.py); [evidence](builds/2026-10-26-recovery/dashboard-query-refresh-preflight.json)). This improves the registered-query boundary only; report-owner decisions, populated semantic output, durable materialization, and external consumer authorization remain open. Checklist: 1,230 complete / 25 open (1,255 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Registered dashboard query IDs (26 October 2026):** The legacy dataset refresher now dispatches a stable `dashboard_dataset.query_id` through a source-controlled registry; it never selects or executes stored `query_sql`. Migration 651 adds the nullable field without assigning IDs to existing datasets. Three count-only contracts operate on the current curated reporting views and require a valid exact `location_id`; unknown IDs or missing scope fail closed. Forecast summaries remain draft metadata, and the writer clears legacy/generated SQL. Focused reader, refresh, forecast, migration, and SDK checks pass (182 tests); the migration applies/replays in network-disabled disposable PostgreSQL 16 and enforces its ID format. This closes the free-form SQL execution boundary, not saved-dashboard parity or a capability classification: owner-selected outputs, semantic fixtures, durable materialization, external consumers, and production grants remain open ([contract](reporting-parity-inventory.md); [migration](../schemas/postgres/651_dashboard_dataset_query_registry.sql); [evidence](builds/2026-10-26-recovery/dashboard-query-id-registry.json)). Checklist: 1,229 complete / 25 open (1,254 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Typed public location-directory query (26 October 2026):** `/api/locations` and `/api/v1/locations` now use the existing typed analytics port instead of issuing SQL from the Gateway service. The PostgreSQL adapter executes a fixed query against `v_public_farm_summary`, preserves the exact-location detail bind and 100-row list bound, and retains the read-only transaction plus 5-second statement and 2-second lock limits. The existing public-metric query is unchanged. The 13 focused adapter/route tests pass with Ruff, Python compilation, and diff checks; mocks only, with no database, provider, candidate, or legacy access ([evidence](builds/2026-10-26-recovery/typed-public-location-directory-query.json)). Checklist: 1,228 complete / 25 open (1,253 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Directus retirement-certificate read scope (26 October 2026):** `retirement_certificate` is now the twenty-first collection in the fail-closed exact-location read adapter. Reads require the `read` grant; Directus create/update/delete are rejected before identity resolution or row lookup because issuance and revocation are governed elsewhere. The full extension suite passes 102 tests, and the bundle/TypeScript check passes. This is source-level acceptance only; effective Directus role/field permissions, pinned-runtime behavior, verification behavior, and RLS remain open ([inventory](directus-parity-inventory.md); [evidence](builds/2026-10-26-recovery/directus-retirement-certificate-readonly.json)). Checklist: 1,227 complete / 25 open (1,252 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Directus location-scoped lifecycle expansion (26 October 2026):** nine additional direct-location lifecycle collections now use the same exact organization/location grant hooks as the original eleven: forecast scenarios, report snapshots, dashboard datasets, farm registry records, inventory events, maintenance events, stakeholder outcomes, credit batches, and credit-class enrollments. Scenario-parent and infrastructure-asset references are checked against the same location. The full extension suite passes 101 tests, and the Directus bundle/TypeScript check passes. At this expansion point, impact claims, MRV events, retirement certificates, and Data Stream posts remained gated on explicit polymorphic/child-reference contracts; retirement certificates were subsequently added as read-only scope. Pinned-runtime and effective permission parity remain open ([inventory](directus-parity-inventory.md); [evidence](builds/2026-10-26-recovery/directus-location-lifecycle-scope.json)). Checklist: 1,226 complete / 25 open; capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Directus schedules default off (26 October 2026):** root Compose now matches the Kernel profile and requires explicit `true` for NOI reconciliation or weekly activity aggregation. The signed, default-off NOI worker remains available as the location-scoped path. Three Compose compatibility tests pass; active schedule/credential reconciliation remains open ([evidence](builds/2026-10-26-recovery/directus-schedules-default-off.json)). Checklist: 1,225 complete / 25 open; capability classifications remain unchanged.

**Directus NOI action request context (26 October 2026):** harvest, sales, and expense create actions now use the event context database for NOI view reads and snapshot writes, and missing context never falls back to the extension-global connection. The calculator keeps its existing default for other callers. The 99-test extension suite and bundle/TypeScript checks pass; runtime behavior and durable retry remain open ([evidence](builds/2026-10-26-recovery/directus-noi-action-request-context.json)). Checklist: 1,224 complete / 25 open; capability classifications remain unchanged.

**Metric-proposal audit transaction (26 October 2026):** the specialized tenant-scoped update now records status-transition history through the Directus request database and no longer uses a post-write global connection. Only actual transitions are recorded; validation and discussion notes are preserved. The full extension suite passes 98 tests and bundle/TypeScript checks pass. Pinned-runtime transaction behavior and populated parity remain open ([evidence](builds/2026-10-26-recovery/directus-metric-proposal-audit-transaction.json)). Checklist: 1,223 complete / 25 open; capability classifications remain unchanged.

**Directus tenant lifecycle audit transaction (26 October 2026):** the ten tenant-scoped collections using the shared lifecycle workflow now write `workflow_history` through the Directus request database before the item update; audit failure blocks the update, and their extension-global post-write audit actions are removed. The 96-test extension suite and bundle/TypeScript checks pass. This improves the optional Directus adapter but does not close its capability row: pinned-runtime transaction behavior, the specialized `metric_proposal` path, broader permissions/hooks, and populated parity remain open ([evidence](builds/2026-10-26-recovery/directus-tenant-lifecycle-audit-transaction.json)). Checklist: 1,222 complete / 25 open; capability classifications remain unchanged.

**Directus feedback-review transaction boundary (26 October 2026):** feedback publish/reject review rows are now inserted in the request-bound pre-update filter after workflow validation and before Directus persists the item. A review-storage failure rejects the update and clears the pending transition marker. The 93-test extension suite, Directus bundle, and TypeScript check pass; no runtime database was used ([inventory](directus-parity-inventory.md); [evidence](builds/2026-10-26-recovery/directus-feedback-review-atomicity.json)). Pinned-runtime transaction semantics and populated review parity remain open. Checklist: 1,213 complete / 25 open (1,238 total); capability classifications remain unchanged.

**Directus tenant update transaction boundary (26 October 2026):** all downstream lifecycle/business update filters for the 11 tenant-scoped collections now resolve the request database through one shared helper. Missing or malformed request context fails closed even when a downstream filter is called independently; the extension-global handle remains available to non-tenant hooks. The full extension suite passes 93 tests, the Directus bundle and TypeScript check pass, and no runtime database was used ([inventory](directus-parity-inventory.md); [evidence](builds/2026-10-26-recovery/directus-tenant-update-transaction-boundary.json)). This is source/unit evidence only; wider Directus parity and pinned-runtime context semantics remain open. Checklist: 1,212 complete / 25 open (1,237 total); capability classifications remain unchanged.

**Directus tenant request-transaction fail-closed boundary (26 October 2026):** the 11 location-scoped collection hook families and the feedback-review create hook now require Directus's request database handle and return a generic 403 if it is absent; they no longer fall back to the extension-global database. The full extension suite passes 91 tests, seven Python fixture/source checks pass, and the extension build/type check pass. No live database or Directus runtime was accessed ([inventory](directus-parity-inventory.md); [evidence](builds/2026-10-26-recovery/directus-request-transaction-boundary.json)). Broader runtime, role/field, and effect parity remain open; capability classifications are unchanged. Checklist: 1,211 complete / 25 open (1,236 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Isolated EventBus disabled-mode boundary (26 October 2026):** invoking `--isolated-event-worker` with isolation disabled now stops before database access instead of falling through to the legacy shared-identity dispatcher. Focused tests cover both the isolated flag disabled and the parent EventBus disabled; the 23-test/6-subtest selection passes with Ruff and compilation. No database, provider, or candidate/legacy stack was used ([implementation](../services/events/cli.py); [test](../tests/test_event_worker_recovery.py); [evidence](builds/2026-10-26-recovery/event-dispatch-disabled-fail-closed.json)). This is a fail-closed mode-selection correction; legacy worker mode and capability classifications are unchanged. Checklist: 1,210 complete / 25 open (1,235 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Isolated EventBus dispatcher reconnect acceptance (26 October 2026):** the migration-648 worker now survives a real disposable PostgreSQL stop/start using a synthetic dedicated-login credential. It observes the outage, reconnects, and completes a fresh unregistered event under the same worker ID without creating handler receipts. Existing event and notification retry/crash acceptance remains in the same harness. The database was loopback-only; migrations 116, 165, 375, and 648 were replayed; candidate/legacy state and external providers were untouched ([recovery harness](../scripts/check-event-worker-reconnect-disposable.py); [evidence](builds/2026-10-26-recovery/event-worker-isolated-dispatch-reconnect.json)). This closes only isolated dispatcher database reconnect acceptance; live credential rollout, reviewed migration from the legacy dispatcher, real handler/provider recovery, production duration, and MAN-CAP acceptance remain open. Capability classifications are unchanged. Checklist: 1,209 complete / 25 open (1,234 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Isolated one-shot ML anomaly source reader (26 October 2026):** Migration 650 and the default-off `sensor_anomaly_ml_source` worker separate manual ML checks and training from the shared database role. A signed `sensor_anomaly_ml/analyze` scope binds each run to one location; the source view permits only `good`/`estimated` readings and the reader cannot access source tables or write alerts. The retained CLI routes `--ml-check`/`--ml-train` only when the feature is enabled and rejects aggregate all-location requests before importing the worker. A dedicated optional image/profile keeps ML dependencies out of the default Kernel image; the model manifest is a five-package subset, with a separate PostgreSQL driver input. The 119-test focused selection, Ruff, compilation, dependency-group alignment, inventory checks, and AMD64/ARM64 Compose configuration checks pass. Standalone AMD64 and ARM64 images build using target-specific wheels resolved on `BUILDPLATFORM`; network-disabled, read-only import smokes and `pip check` pass for both. Docker image metadata reports 955 MB/987 MB, about 20% smaller than their previous builds ([slim image evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-builds.json); [AMD64 smoke](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-native-smoke.json); [ARM64 smoke](builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-arm64-smoke.json)). Optional ML dependencies now use an exact, SHA-256-hashed wheel lock for Python 3.11 Linux AMD64/ARM64. The new lock generator and profile tests pass (27 total), and Ruff, group alignment, matrix validation, and release-input checks pass ([locked build evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-hash-locked-image-builds.json)). A synthetic IsolationForest run also passes under a 1 GiB memory cap and 2-CPU quota, with peak RSS of 188 MiB on AMD64 and 325 MiB on ARM64/QEMU in the locked-image run ([locked build evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-hash-locked-image-builds.json)). ARM64 reports `aarch64` under QEMU; these are software portability/resource checks only, not physical Raspberry Pi behavior. Disposable PostgreSQL 16 applies/replays migrations 405/419/650 under forced RLS and verifies exact-location filtering, context reset/denial, direct-table denial, and the SET-only reader boundary ([source checks](builds/2026-10-26-recovery/sensor-anomaly-ml-source-checks.json); [contract](sensor-anomaly-ml-worker-contract.md); [migration](../../schemas/postgres/650_signed_sensor_anomaly_ml_source.sql); [worker](../../services/ingestion/sensor_anomaly_ml_worker.py); [evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-source-disposable.json)). No candidate/legacy rollout, real credential/grant, or model artifact was provisioned. CAP-040 remains partial and MAN-CAP-040/047 remain open. Checklist: 1,208 complete / 25 open (1,233 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Multi-location sensor-anomaly scope (26 October 2026):** the retained CLI ML check groups sensor-type time series and model loading/training by source location, preserves same-time findings from different locations during deduplication, and applies an explicit sensor filter to both Prophet training and prediction. Sensor-specific checks bypass the location/type cache and skip multivariate scoring; invalid sensor UUIDs fail before database access. The persisted training command rejects `--sensor` because its cache is location/type-scoped. The baseline checker also preserves each baseline's location through device lookup, cooldown, alert creation, and event lineage during explicit all-location runs. Focused ML/anomaly/CLI/runtime and baseline/CLI regressions pass with Ruff and compilation; database calls are mocked ([ML evidence](builds/2026-10-26-recovery/ml-anomaly-location-scope.json); [baseline evidence](builds/2026-10-26-recovery/baseline-anomaly-location-scope.json)). These fixes do not isolate baseline/ML access from the legacy shared database role. CAP-040 remains partial, and MAN-CAP-040/047 remain open. Checklist: 1,206 complete / 25 open (1,231 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Signed scheduled sensor-anomaly replay inventory (26 October 2026):** migration 649 exposes a bounded, signed-location inventory of canonical sensor-reading events whose enabled rules lack durable effect receipts. The default-off Kernel JobSpec reuses the existing idempotent event worker; the feature-off compatibility route and manual baseline/ML CLI remain available. Focused worker/scheduler coverage passes 221 tests, and isolated PostgreSQL 16 migration/replay, forced-RLS, location denial, duplicate suppression, and direct-table denial pass ([migration](../schemas/postgres/649_signed_sensor_anomaly_replay_inventory.sql); [worker](../services/ingestion/sensor_anomaly_scan_worker.py); [evidence](builds/2026-10-26-recovery/sensor-anomaly-replay-inventory-disposable.json)). No candidate/legacy rollout, provider, worker credential, or schedule activation occurred. This is source and disposable-database acceptance, not populated-data parity; CAP-040 remains partial and MAN-CAP-040/047 remain open. Checklist: 1,204 complete / 25 open (1,229 total); matrix remains 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Current-source ARM64 application smoke (26 October 2026):** local commit
`403ea03d` builds the default Kernel image for `linux/arm64`. A no-network,
read-only QEMU container reports `aarch64`, constructs the Gateway, imports
both Python SDK clients and six isolated worker modules, including scheduled
sensor-anomaly replay, and loads all 23 JobSpecs. It observes 16 direct route
objects, makes no database/provider calls, and receives no credentials; its
temporary image and container are removed ([evidence](builds/2026-10-26-recovery/arm64-kernel-current-source-smoke-403ea03d.json)).
This refreshes software portability evidence only; physical Pi and power/resource
acceptance remain open. Capability classifications remain 24 baseline-retained,
7 deployed, and 36 prepared across 67 rows.


**Isolated global EventBus dispatcher (26 October 2026):** Migration 648 adds a dedicated global queue identity and seven bounded functions for claims, handler receipts, leases, completion, retry, and dead-letter. The default-off worker preserves caller-owned event publication, exact child-handler credential filtering, and operator-only statistics/replay/disposition; the legacy dispatcher remains available for rollback. Completion requires successful receipts for all enabled handlers; retry requires a recorded handler failure. The focused selection passes 262 tests and 4 subtests; regenerated source/function/SQL/effect/preflight inventories pass. Network-disabled disposable PostgreSQL 16 applies/replays migration 648 and verifies forced-RLS behavior, exact function ACLs, no direct table access, success/error receipts, state-guard denial, retry/dead-letter, rollback, and expired-lease fencing on native x86_64 and ARM64/QEMU (`aarch64`) ([worker](../services/events/dispatch_worker.py); [migration](../schemas/postgres/648_isolated_event_dispatch_worker.sql); [source checks](builds/2026-10-26-recovery/event-dispatch-worker-source-checks.json); [native evidence](builds/2026-10-26-recovery/event-dispatch-worker-disposable.json); [ARM64 evidence](builds/2026-10-26-recovery/event-dispatch-worker-arm64-disposable.json)). QEMU demonstrates software portability only; no physical Raspberry Pi is available or claimed. The opt-in profile remains inactive pending a dedicated DSN/credential and a reviewed dispatcher handoff. Candidate and legacy were not rolled out; no live handler or provider ran. Checklist: 1,201 complete / 25 open (1,226 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP acceptance is claimed.


**Isolated notification delivery worker (25 October 2026):** Migration 647 and a default-off worker separate durable notification sending from the EventBus/runtime database identity. The dedicated login can call only bounded claim/completion functions; operator stats and dead-letter operations remain on the reviewed CLI. The worker commits claims before webhook, Directus, or SMTP calls, records lease-fenced attempt receipts, retains bounded retries, and preserves the legacy `--notification-worker` path. The focused delivery, outbox, worker identity, runtime-role, Compose profile, and scheduler contract selection passes 359 tests; Ruff, compilation, and refreshed worker source/function/SQL/effect/preflight inventories pass across 39 roots with no unresolved entrypoints. Network-disabled PostgreSQL 16 applies and replays migration 647 against forced-RLS fixtures and verifies actual-login permissions, worker/token fencing, success/retry/dead-letter transitions, bounded lease recovery, and transaction rollback on native x86_64 and emulated ARM64/aarch64 ([worker](../services/events/notification_delivery_worker.py); [migration](../schemas/postgres/647_isolated_notification_delivery_worker.sql); [tests](../tests/test_notification_delivery_worker.py); [native evidence](builds/2026-10-25-recovery/notification-delivery-worker-disposable.json); [ARM64 evidence](builds/2026-10-25-recovery/notification-delivery-worker-arm64-disposable.json)). This demonstrates software portability only; no physical Raspberry Pi or endurance acceptance is claimed. The optional `notification-isolated` profile remains inactive until the dedicated credential and DSN are provisioned. No candidate rollout, live SMTP/provider delivery, or credential provisioning occurred. Checklist: 1,200 complete / 25 open (1,225 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP acceptance is claimed.

**Isolated ClickHouse outbox delivery (25 October 2026):** Migration 646 adds a default-off scheduled delivery worker with a dedicated login and bounded claim/completion functions. The existing operator CLI remains available for reconciliation and dead-letter actions; the existing ClickHouse provider remains optional. Focused source/runtime-role/scheduler checks pass; network-disabled PostgreSQL 16 migration/replay acceptance passes on native x86_64 and emulated aarch64 ([source evidence](builds/2026-10-25-recovery/clickhouse-outbox-worker-source-checks.json); [native database evidence](builds/2026-10-25-recovery/clickhouse-outbox-worker-disposable.json); [ARM64 evidence](builds/2026-10-25-recovery/clickhouse-outbox-worker-arm64-disposable.json)). No candidate rollout, credentials, or live ClickHouse delivery occurred. CAP-040/047 classifications remain prepared; production parity and MAN-CAP acceptance are still open. Classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; checklist: 1,199 complete / 25 open (1,224 total).

**ClickHouse outbox projection boundary (25 October 2026):** The optional ClickHouse sink now accepts only six repository-owned tables and columns that exist in the current ClickHouse schema. Required identity fields, unique columns, non-empty rows, and row widths are validated before provider connection. Unsupported data is written to the existing durable dead-letter state with a fixed reason; valid delivery retains the existing lease, retry, and deduplication behavior ([evidence](builds/2026-10-25-recovery/clickhouse-outbox-projection-contract.json)). Thirty-eight focused tests and the schema-column regression pass with Ruff and compilation. No database/provider was accessed. This does not establish production delivery, populated parity, or MAN-CAP acceptance; classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Checklist: 1,198 complete / 25 open (1,223 total).

**Global freshness worker ARM64 software acceptance correction (26 October 2026):** The earlier isolated fixture used a synthetic `price_observation.observation_date TIMESTAMPTZ` column and therefore did not validate the repository's canonical `price_date DATE` and nullable `location_id` contract. Migration 645 now grants and reads the canonical columns; DATE-backed weather, remote-sensing, and market-data timestamps are normalized to UTC midnight. The corrected disposable acceptance uses a non-UTC session timezone and competing locations, and passes on PostgreSQL 16 native x86_64 and ARM64/aarch64. More importantly, the full network-disabled ARM64/QEMU bootstrap now applies all 642 ordered migrations through 651 with zero pending or failed migrations, no seeds, no farm data, and successful cleanup ([native acceptance](builds/2026-10-26-recovery/freshness-worker-disposable.json); [ARM64 acceptance](builds/2026-10-26-recovery/freshness-worker-arm64-disposable.json); [full-chain evidence](builds/2026-10-26-recovery/arm64-qemu-current-schema-refresh-after-645-fix.json); [pre-fix failure](builds/2026-10-26-recovery/arm64-qemu-current-schema-refresh.json)). The 25 October fixture evidence remains archived but is superseded for canonical-schema proof. This demonstrates container/QEMU software portability only; no physical Raspberry Pi, power-loss, or sustained-load test is claimed. CAP-047 remains prepared; capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP capability is accepted. Checklist: 1,234 complete / 25 open (1,259 total).

**Isolated global data-freshness worker (25 October 2026):** Migration 645 and a default-off scheduled worker now route freshness source reads, checks, alert-state/history writes, and durable event enqueue through nine bounded functions under a dedicated global control-plane login. Location-scoped observations are queried only for their requested location; global sources remain explicit and this worker does not claim farm tenant context. The legacy freshness CLI remains available; the Prefect `run_job` adapter uses it while the feature is disabled, while new native Kernel plans remain review-only and target the isolated worker. The 322-test focused selection and 36-test migration-catalog regression pass; Ruff, compilation, inventory freshness, Compose profile parsing, and matrix validation pass. Network-disabled PostgreSQL 16 applies/replays migration 645 with forced RLS enabled, verifies scoped/global timestamp reads, atomic check/state/history/event writes, rollback on rejected enqueue, exact function grants, and direct-access denial ([worker](../../services/ingestion/freshness_worker.py); [migration](../../schemas/postgres/645_isolated_data_freshness_worker.sql); [tests](../../tests/test_freshness_worker.py); [corrected disposable evidence](builds/2026-10-26-recovery/freshness-worker-disposable.json)). No candidate rollout or credential provisioning occurred. Live SMTP/provider routing, retention ownership, active schedule reconciliation, and CAP-047 owner acceptance remain open. Checklist at that historical point: 1,196 complete / 25 open (1,221 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Isolated Baal governance worker (25 October 2026):** migration 644 and a default-off dedicated worker now isolate Baal indexing behind bounded cursor, protocol/wallet lookup, governance-event, and status functions. Event writes and cursor checkpoints commit together per block batch; the legacy manual CLI remains compatible until the feature is enabled. The 240-test focused worker/CLI/recovery/scheduler/runtime-role/command-contract selection passes, along with Ruff, compilation, refreshed worker inventories, and network-disabled PostgreSQL 16 migration/replay/forced-RLS acceptance. The runtime-role bootstrap provisions only the dedicated login and execute grants; its password is not given to other workers. No candidate rollout, credential provisioning, or activation occurred. Live RPC/reorg recovery and operational activation remain open ([worker](../services/ingestion/baal_worker.py); [migration](../schemas/postgres/644_isolated_baal_indexer.sql); [tests](../tests/test_baal_worker.py); [disposable evidence](builds/2026-10-25-recovery/baal-indexer-worker-disposable.json)). Checklist: 1,195 complete / 25 open (1,220 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP check is accepted.

**Isolated Gnosis Moloch worker (25 October 2026):** Scheduled Moloch indexing now has an optional dedicated worker login and migration 643 SECURITY DEFINER contract. The database functions bind governance, Withdraw treasury, and dLEGO writes to matching event receipts, and outbox intents to existing canonical source rows with fixed wallet-event/dLEGO shapes; Withdraw projections now identify `treasury_event` as their source. The feature remains default-off, while the legacy manual CLI remains available. The 307-test focused Gnosis/outbox/runtime-role/migration selection passes, along with Ruff, compilation, and the network-disabled PostgreSQL 16 migration/replay/forced-RLS acceptance ([worker](../services/ingestion/gnosis_worker.py); [migration](../schemas/postgres/643_isolated_gnosis_moloch_indexer.sql); [tests](../tests/test_gnosis_worker.py); [disposable evidence](builds/2026-10-25-recovery/gnosis-indexer-worker-disposable.json)). Candidate rollout and worker credential provisioning were not performed. Live provider/reorg recovery, historical receipt reconciliation, and activation remain open. Checklist: 1,194 complete / 25 open (1,219 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP check is accepted.

**Latest worker/driver boundary work (25 October 2026):** the static function graph follows the native scheduled sensor worker's immutable `SCHEDULED_SENSOR_DRIVER_TARGETS` entry to the allowlisted CSV class and its invoked methods; the effect inventory traces its bounded file access. The general driver registry now resolves all nine seeded built-ins through a source-owned target map and third-party adapters through one exact installed `kokonut.drivers` entry point. Registration rejects uninstalled or mismatched plugin metadata before database access without importing plugin code; loading validates the adapter class after the registry transaction ends. Sixty-one focused registry/sensor tests pass; source closure, function/SQL/effect inventories, preflight, provider boundaries, dependency alignment, Ruff, compilation, and matrix validation pass. A linux/arm64 Kernel image built from pushed head `2b877bae` and passed a network-disabled, read-only QEMU smoke importing all nine built-ins. This does not sandbox installed packages or establish provider/runtime safety, grants, active schedules, database effects, or physical Raspberry Pi acceptance ([worker map](worker-operation-map.md); [scheduled trace](builds/2026-10-25-recovery/scheduled-sensor-driver-static-callgraph.json); [driver boundary](builds/2026-10-25-recovery/driver-entry-point-loading.json); [ARM64 smoke](builds/2026-10-25-recovery/arm64-kernel-driver-import-smoke-2b877bae.json)). Checklist: 1,192 complete / 25 open (1,217 total). Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP check is accepted.

**Driver instance configuration preflight (25 October 2026):** instance creation now validates a JSON-object config with the selected registered adapter before persistence, rejects disabled registrations, and locks the enabled registry row through insertion. The 66-test driver/scheduled-sensor selection, Ruff, compilation, and diff checks pass with mocked database use. Installed third-party packages remain trusted in-process code; PostgreSQL lock behavior and runtime plugin/provider acceptance are not claimed ([implementation](../services/drivers/registry.py); [evidence](builds/2026-10-25-recovery/driver-instance-config-preflight.json)). Checklist: 1,192 complete / 25 open (1,217 total). Capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; no MAN-CAP check is accepted.

**Bounded Gnosis provider recovery (25 October 2026):** the legacy Moloch indexer processes at most 10,000 blocks per invocation; oversized manual intervals fail before provider/database setup, and automatic catch-up advances only the committed checkpoint. The 161-test Gnosis/scheduled-command selection, Ruff, compilation, and matrix checks pass with mocks only. A default-off isolated worker and migration 643 now implement a dedicated identity; candidate provisioning/rollout and live provider behavior remain open ([implementation](../services/ingestion/gnosis_indexer.py); [evidence](builds/2026-10-25-recovery/gnosis-indexer-run-bound.json)). Checklist: 1,193 complete / 25 open (1,218 total).

**Latest CAP-027 participant-submitted minority reports (25 October 2026):** Migration 642 adds a first-party participant submission path only when the invite-bound, accepted versioned notice explicitly includes `minority_reports`. The study must be open; optional questions are study-scoped; content is bounded; evidence references are not accepted. A dedicated non-login database role creates a submitted row and digest-only idempotency receipt. Runtime and Directus cannot directly read or write report rows or inspect receipts. Withdrawal serializes with submission, blocks future use, and keeps existing content private for disposition. Migration 640 provides the separate exact-location operator review queue and verified/rejected decision; it returns only submissions linked to a currently consenting participant and never publishes. The focused Gateway, route-policy, participant asset, and migration selection passes 103 tests. Network-disabled PostgreSQL 16 applies and replays migrations 637–642 and passes eight grouped scope, retry, withdrawal, and privilege assertions ([migration](../schemas/postgres/642_location_scoped_delphi_minority_report_submission.sql); [runner](../scripts/check-delphi-minority-report-submission-disposable.py); [evidence](builds/2026-10-25-recovery/cap-027-delphi-minority-report-submission-disposable.json)). Ruff, compilation, participant JavaScript syntax, runtime SQL inventory, and capability checks pass. Candidate and legacy databases remain untouched; migrations 640–642 are not rolled out. CAP-027 remains prepared pending live OIDC/browser acceptance, populated parity, universal ACL/RLS, SMTP, and MAN-CAP-027 owner acceptance. Checklist: 1,189 complete / 25 open (1,214 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**CAP-027 structured Delphi participant activity consent (25 October 2026):** Migration 641 adds immutable `questionnaire_responses` and optional `minority_reports` scopes to versioned notices. The text and canonical scope list are bound into the notice digest, invite preview, and consent acceptance; the participant sees the scopes before accepting. New invites cannot use legacy unscoped notices, while already issued invitations retain their existing behavior. The operator console requires questionnaire scope, displays scope to reviewers, and prevents approval of unscoped legacy drafts. The focused Gateway, console, participant-bundle, and migration regression passes 87 tests. Network-disabled disposable PostgreSQL 16 applies/replays migration 641 and passes eight grouped assertions for scope validation, immutable digest binding, independent review, invite gating, acceptance binding, and Directus/runtime boundaries ([migration](../schemas/postgres/641_location_delphi_consent_activity_scopes.sql); [disposable runner](../scripts/check-delphi-consent-scopes-disposable.py); [evidence](builds/2026-10-25-recovery/cap-027-delphi-consent-scopes-disposable.json)). Candidate and legacy databases remain untouched; migration 641 is not rolled out. CAP-027 remains prepared: live OIDC/browser acceptance, populated parity, universal ACL/RLS, SMTP, and MAN-CAP-027 owner acceptance remain open. Checklist: 1,188 complete / 25 open (1,213 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest CAP-027 consent notice author/reviewer console controls (25 October 2026):**
The operator console now provides immutable notice drafting for an exact-location
operator with same-location `delphi:read` plus `delphi:consent_draft`, and a
separate review queue for `delphi:consent_review`. It displays the submitted
notice text as text, blocks author self-review, uses CSRF/no-store requests,
bounded paging, reason-code allowlists, confirmation, and retry-stable request
IDs. Approval only selects the notice for future invites; it does not open the
study or distribute invites. The focused consent, invite, route-policy, and
console selection passes 36 tests; inline JavaScript syntax and diff checks
pass. No database or provider was used. CAP-027 remains prepared pending
participant minority-report submission, live OIDC/browser, populated parity,
universal ACL/RLS, SMTP, and owner acceptance. Checklist: 1,187 complete / 25
open (1,212 total); classifications remain 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows ([contract](delphi-consultation-kernel-contract.md);
[console](../apps/operator-console/index.html);
[tests](../tests/test_operator_console_delphi_consent_notices.py)).

**Latest CAP-027 existing minority-report review slice (25 October 2026):**
Migration 640 and two exact-location Gateway endpoints provide a private,
bounded review queue for submitted reports whose linked participant still has
active consent. The console records only reason-coded `verified` or `rejected`
dispositions; no route publishes content or creates participant reports.
Withdrawal/unlinked rows stay hidden pending disposition. Fifty focused
Gateway, route-policy, and console checks pass; network-disabled disposable
PostgreSQL 16 applies/replays migration 640 and passes five scope, consent,
retry, privacy, and runtime/Directus privilege assertions. Candidate and
legacy databases remain untouched; migration 640 is not rolled out. CAP-027
remains prepared pending participant report submission, live OIDC/browser,
populated parity, universal ACL/RLS, SMTP, and owner acceptance. Checklist:
1,186 complete / 25 open (1,211 total); classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([contract](delphi-consultation-kernel-contract.md);
[migration](../schemas/postgres/640_location_scoped_delphi_minority_report_review.sql);
[evidence](builds/2026-10-25-recovery/cap-027-delphi-minority-review-disposable.json)).

**Latest CAP-027 consent-aware stopping evaluation (25 October 2026):**
Migration 639 adds a location-scoped evaluator that recomputes from currently
consented contributions and uses only prior consent-filtered Kernel snapshots
for stability. Its response omits panel counts, score statistics, answer text,
and identities; a private append-only ledger and retry receipt preserve
evaluation history. The OIDC console gates the advisory action by same-location
read/evaluate grants, CSRF, confirmation, and stable request IDs. It never
closes a study; a separate `delphi:close` action remains required. The focused
Gateway, route-policy, console, and migration selection passes 80 tests.
Network-disabled PostgreSQL 16 applies/replays migrations 449–451 and 630–639
and passes seven grouped consent, consensus, stability, retry, scope, and role
checks. Candidate and legacy databases remain untouched; migration 639 is not
rolled out. Live OIDC/browser, SMTP, populated parity, universal ACL/RLS, and
MAN-CAP-027 owner acceptance remain open. Checklist: 1,179 complete / 25 open
(1,204 total); classifications remain 24 baseline-retained, 7 deployed, and
36 prepared across 67 rows. Evidence:
[contract](delphi-consultation-kernel-contract.md),
[migration](../schemas/postgres/639_location_scoped_delphi_stopping_evaluation.sql),
[disposable acceptance](builds/2026-10-25-recovery/cap-027-delphi-stopping-evaluation-disposable.json).

**CAP-027 lifecycle inventory reconciliation (25 October 2026):** migrations
630–639 now cover signed study/question authoring, opening and closure,
versioned consent notices, pseudonymous single-use invites, participant
acceptance/withdrawal and answer submission, advisory stopping evaluation,
facilitator draft creation, and independent recommendation review. The legacy
CLI and all three legacy Delphi service facades remain disabled before database
access; direct panel administration, diversity assessment, minority-report
workflow, and calibration remain unavailable. This corrects older cumulative notes that
described Gateway lifecycle parity as wholly open. Live OIDC/browser, SMTP
delivery, populated legacy parity, universal ACL/RLS, and MAN-CAP-027 owner
acceptance remain open; CAP-027 stays prepared. Retention periods and scope
codes remain runtime policy data: no durations are hardcoded, unresolved
jurisdiction/purpose scopes fail closed, and cleanup stays disabled until
approved policy data and target-specific hold controls exist.

**Earlier ARM64 Kernel smoke (25 October 2026):** commit `e9d68670` built as
`linux/arm64` and passed the SDK, worker, and JobSpec import checks. It is
superseded by the refreshed current-source smoke for `9385eeb9` below, which
also inspects the lazy route groups. Both are software-emulation evidence;
physical Pi and power/resource acceptance remain open ([earlier evidence](builds/2026-10-25-recovery/arm64-kernel-current-source-smoke-e9d68670.json)).

**CAP-038 signed agent output provenance inventory (25 October 2026):** the
current database-backed worker outputs are classified by row-level references,
query-scope metadata, or privacy-limited aggregates. The inventory records
remaining gaps for legacy/background paths, property-to-row CIDS lineage,
populated parity, production identities/grants, and owner acceptance. CIDS
graph nodes now identify their contributing source views. This source audit
does not change capability classifications: 24 baseline-retained, 7 deployed,
and 36 prepared across 67 rows.
Evidence: [agent output provenance inventory](agent-output-provenance-inventory.md).

**CAP-038 AI-summary inspection output scope (25 October 2026):** list rows
identify the safe list view and normalized location; an additive structured
result also retains that scope when `items` is empty, while the legacy
list-returning helper remains compatible. The metadata-only digest identifies
its safe view plus normalized summary/location keys; a structured not-found
result retains those keys beside a null item while the legacy digest helper
still returns `None`. The focused worker/CLI files pass all 91 tests, including
mixed-case UUID normalization, empty-result scope, and digest content exclusion;
Ruff, compilation, matrix validation, and diff checks pass. This is query-scope
metadata, not a content snapshot or operator attribution. Live OIDC, deployed
worker credentials/grants, runtime recovery, and MAN-CAP-038 owner acceptance
remain open. Classifications remain 24 baseline-retained, 7 deployed, and 36
prepared across 67 rows.
Evidence: [summary inspection scope](builds/2026-10-25-recovery/cap-038-summary-inspection-source-scope.json),
[empty-result scope](builds/2026-10-25-recovery/cap-038-summary-list-empty-source-scope.json).

**CAP-038 CIDS export output source scope (25 October 2026):** the signed
worker includes its six canonical views and normalized location in required
task output metadata. Each JSON-LD graph node now carries a sorted
`kokonut:sourceViews` union plus per-property `kokonut:propertySourceViews`;
stakeholder nodes combine the outcome and feedback views when both contribute.
The registered task validator rejects empty graphs and source scopes that drift
from the normalized location and six signed views; it also requires every
emitted data property to have a deterministically sorted allowlisted view map.
The 14-test focused CIDS selection, Ruff, compilation, and matrix validation
pass. This is field-to-view attribution, not exact source-row lineage or a
source snapshot. Live OIDC, deployed worker credentials/grants, populated
parity, and MAN-CAP-038 owner acceptance remain open. Classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows. Evidence: [CIDS source scope](builds/2026-10-25-recovery/cap-038-cids-output-source-scope.json),
[node attribution](builds/2026-10-25-recovery/cap-038-cids-node-source-attribution.json),
[property attribution](builds/2026-10-25-recovery/cap-038-cids-property-source-attribution.json),
[output contract](builds/2026-10-25-recovery/cap-038-cids-provenance-output-contract.json).

**CAP-038 Delphi facilitator output scope (25 October 2026):** the signed
read-only worker names `kokonut_agent_source.delphi_live_summary` and returns
normalized study/location scope; the facilitator preserves the metadata. Three
focused mocked checks pass with Ruff, compilation, matrix validation, and diff
checks. This is query-scope metadata, not participant-level provenance or a
snapshot of returned rows. Live OIDC, deployed worker credentials/grants,
runtime recovery, and MAN-CAP-038 owner acceptance remain open. Classifications
remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.
Evidence: [Delphi source scope](builds/2026-10-25-recovery/cap-038-delphi-output-source-scope.json).

**CAP-027/038 Delphi CLI database boundary (25 October 2026):** the ten legacy
study/panel commands that lack authenticated location context now fail before
database import or connection. Signed aggregate summary and in-memory draft
commands remain available. The focused CLI selection passes 19 tests; Ruff,
compilation, and matrix validation pass. This prevents shared-login bypass but
does not port the blocked lifecycle operations to Gateway; those contracts,
live OIDC, populated parity, and MAN-CAP review remain open. Capability
classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across
67 rows. Evidence: [Delphi CLI boundary](builds/2026-10-25-recovery/cap-027-delphi-cli-study-panel-boundary.json).

**CAP-038 EBF evidence-gap output scope (25 October 2026):** the signed,
read-only worker now returns the exact safe summary view and normalized
scorecard/location query scope, and its task contract requires that metadata.
The focused worker/task selection passes 91 tests; Ruff, compilation, matrix
validation, and diff checks pass. These checks use mocks only. This describes
query scope, not source-row snapshots, and does not close live OIDC, deployed
credentials/grants, runtime recovery, or MAN-CAP-038 acceptance. The matrix
remains 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.
Evidence: [worker scope](builds/2026-10-25-recovery/cap-038-ebf-output-source-scope.json).

**Directus tenant-reference location resolution (25 October 2026):** the hook
derives a plot's location through its owning farm, validates writable
`stakeholder_feedback.farm_id`, scopes editable staff references to staff
assigned or farm-linked to the authorized location, and derives feedback-review
create scope from its parent feedback row under an exact child-collection grant.
All 84 Directus hook tests, the extension build/type check, and 10 Python tenant
and compatibility tests pass; the matrix validator passes. No live Directus
service or database was used. Review reads/updates/deletes, polymorphic MRV
source IDs, and broader collection, field, relation, runtime, and schedule
parity remain open. Checklist: 1,149 complete / 25 open (1,174 total);
classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across
67 rows.

**CAP-038 synthesis receipt console (25 October 2026):** the operator console
now exposes a grant-gated form for creating receipts for the 12 registered
synthesis workers. It validates task/type and isolated Compose service/profile
pairs against the Gateway and Compose registries, persists a non-secret request
ID in tab-scoped storage across reloads and uncertain retries, and displays a
task-specific command only after validating
the matching authorized response. A source regression verifies each profile
exposes only that task's source DSN/credential pair plus non-secret runtime
settings. The command runs the selected profile with its dedicated credentials
while the profile's default remains read-only. The
UI states that it does not start a worker. The focused console/Gateway selection
passes 22 tests, including JavaScript syntax; Compose renders all 12 worker
profiles with placeholders; Ruff, compilation, and diff checks pass
([console](../apps/operator-console/index.html); [tests](../tests/test_operator_console_ai_summary_task_requests.py);
[evidence](builds/2026-10-25-recovery/cap-038-synthesis-request-console.json)).
No database, provider, candidate, legacy service, or credential was used.
Automatic dispatch, task credential provisioning, live OIDC, populated parity,
and MAN-CAP-038 acceptance remain open.

**CAP-038 authenticated synthesis request receipt (25 October 2026):** migration
628 adds an immutable exact-location receipt binding the authenticated operator,
registered task, and summary type. The OIDC Gateway route only authorizes a
request; it does not launch a worker. Deterministic and synthesis workers must
verify the receipt before retry lookup, source reads, and draft creation, and a
database trigger checks the receipt at the write boundary. The review queue
displays operator/task attribution without exposing receipt digests. The focused
Python/Gateway/console/migration selection passes 208 tests; network-disabled
PostgreSQL 16 apply/replay passes 91 grouped assertions natively and under
ARM64/QEMU (`aarch64`); QEMU is software portability evidence, not physical
Raspberry Pi acceptance. Ruff, compilation, SQL/worker inventory, and matrix
checks pass. No candidate or legacy DB was touched; the migration and real
credentials/grants are not deployed. CAP-038 remains prepared and MAN-CAP-038
is not accepted. Automatic dispatch, live OIDC, exact production grants,
populated parity, and physical Raspberry Pi acceptance remain open ([migration](../schemas/postgres/628_authenticated_agent_task_requests.sql);
[native evidence](builds/2026-10-25-recovery/cap-038-authenticated-task-request-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-25-recovery/cap-038-authenticated-task-request-arm64-disposable.json);
[Gateway](../services/gateway/ai_summary_task_request.py)).

**CAP-038 synthesis worker registry (25 October 2026):** task module, isolated
source identity, and reader role now live in one frozen Python registry used by
the worker CLI. All twelve contracts resolve to the matching registered agent
and have unique identities/readers; 219 focused worker, source-reference,
database-boundary, and Compose profile tests, Ruff, compilation, and matrix
validation pass. This is source configuration
consistency evidence, not live credentials, deployed grants, or runtime
acceptance ([implementation](../services/agents/worker_cli.py);
[evidence](builds/2026-10-25-recovery/cap-038-single-worker-registry.json)).

**CAP-038 worker CLI error redaction (25 October 2026):** worker failures now
log only a validated exception class, suppressing database/provider messages
and Python tracebacks from operator terminal output while retaining a nonzero
exit. A synthetic redaction regression passes in the 220-test worker/source/
database/profile selection; Ruff, compilation, and matrix checks pass. No live
service was used ([evidence](builds/2026-10-25-recovery/cap-038-worker-cli-error-redaction.json)).

**CAP-038 source-reference coverage (25 October 2026):** all registered
synthesis sources must now map to a public provenance view or have an explicit
bounded exclusion reason. The organic compliance checklist remains excluded
for its unreviewed sensitive evidence; the location subject remains excluded
as request scope. An unclassified source fails before database access. The
239-test source/agent/worker/profile selection passes with Ruff, compilation,
and matrix validation ([evidence](builds/2026-10-25-recovery/cap-038-source-reference-exclusions.json)).

**CAP-038 deterministic summary provenance (25 October 2026):** operations,
financial, environmental, and combined summaries now enforce their fixed source
inventories and require an exact matching reference for each source. Missing or
extra provenance fails before a result is returned or a draft is written. The
focused two-suite selection passes 106 tests; Ruff, compilation, matrix
validation, and diff checks pass ([evidence](builds/2026-10-25-recovery/cap-038-deterministic-source-coverage.json)).

**CAP-038 empty synthesis source references (25 October 2026):** all mapped
public source views now appear in the manifest even when they return no rows,
with a zero count and the appropriate scope label. The worker rejects incomplete
manifests before draft writes. The focused source/worker selection passes 169
tests; Ruff, compilation, matrix validation, and diff checks pass ([evidence](builds/2026-10-25-recovery/cap-038-empty-synthesis-source-references.json)).

The CAP-038 source audit now records the operator receipt mint, worker receipt
verification, and review projection in the generated write-boundary inventory.
It confirms the EBF draft templates and Delphi suggestion remain in memory and
that no literal direct DML sites remain in `services/agents`; dynamic SQL and
runtime privileges remain separate review gates ([inventory](agent-write-boundary-inventory.json);
[attribution audit](agent-task-attribution-inventory.md)).

The legacy deterministic AI-summary CLI now rejects `--store` before worker
dispatch unless it receives the request ID issued by the authenticated Gateway;
it no longer invents a UUID that cannot authorize work. The focused 97-test
CLI/safety/worker/inventory selection passes. CAP-038 remains prepared and the
change does not provide automatic dispatch or live OIDC acceptance.

**CAP-038 route attribution regression (25 October 2026):** a focused test now
keeps generic operator agent-task execution routes unregistered until an
immutable operator/request/task attribution contract is implemented. Four
route-policy tests and Ruff pass. CLI, scheduler, and background initiator
attribution remain open; capability classifications and named acceptance are
unchanged. See the [source inventory](agent-task-attribution-inventory.md) and
[evidence](builds/2026-10-25-recovery/cap-038-generic-agent-route-guard.json).

The original 66 core capabilities are frozen from README Core Capabilities at
commit ad806f504bfef15cba41446d777cb22f6bd8fe6a. CAP-067 separately tracks the
Protocol execution bridge added after that baseline.

Each row assigns a code/domain owner and a named manual acceptance check. Existing Python test names are verified source paths, not passing results. The domain registry and repository-inventory.json provide table, migration, route and service-group references. Broad owners require collection-level refinement before their implementation slice.

All 67 named MAN-CAP acceptance checks remain **not accepted**; implementation and deployment progress are tracked separately in the progress column. Some source, unit, disposable-database, and local-runtime checks have run and are recorded below, but none substitutes for a named capability acceptance unless its exact result is recorded. Execute each with a representative scoped fixture and retain outputs, identifiers, evidence links, and audit history before provider cutover. Chain write behavior is evaluated with local/mocked contracts; these checks do not authorize mainnet transactions. Contract capabilities also retain the existing Foundry suite in contracts/test/.

**Current implementation status (25 October 2026):** 1,158 checklist items are complete and 25 remain open (1,183 total). The 67-row matrix remains 24 baseline-retained, 7 deployed, and 36 prepared; 0/67 named MAN-CAP checks are accepted. CAP-002 has tenant-scoped yield, irrigation, crop-simulation, nutrient-balance, soil-test, and currency-qualified event reads; CAP-003 has traceability list/detail and console views; CAP-004 has a tenant-scoped learning overview, public module catalog, and console views; CAP-006 has grant-gated energy, waste, landscape, and pollinator summaries plus location-scoped pollinator capture, self-reported habitat/hive inventory, recorded hive inspections, audited habitat and hive status/maintenance changes, and independent review of recorded pollinator observations, pesticide-impact reports, and hive inspections. Reviewed records feed the existing reviewed summaries; pesticide review is not treatment approval or a safety certification. Other CAP-006 code-defined calculations and waste capture/review are recorded in the batches and progress logs. These results do not establish populated-data parity or named capability acceptance.

**Latest Directus tenant-integrity slice (25 October 2026):** Scoped create and update filters validate writable farm references, plot-through-farm references, crop cycles, harvests, and editable staff references against the authorized location. Staff must be directly assigned to that location or have an explicit farm-membership edge through a farm at that location. Feedback-review creates resolve their parent feedback on the request transaction and require the exact child collection `create` grant at the parent location; optional reviewers are location-qualified. Plot location resolves through its owning farm; updates validate against every authorized row, so cross-location and incompatible bulk references fail closed. The full extension suite passes 84 tests, including request-transaction parent-scope and foreign-parent denial; the build/type check and 10 Python tenant/compatibility tests pass. The two scheduled hooks remain independent opt-ins, with legacy Compose preserving enabled defaults and the Kernel Directus profile defaulting them off. Polymorphic MRV source IDs, feedback-review read/update/delete parity, and other relations remain open; source/mock checks do not establish live runtime or full field/relation parity ([reference evidence](builds/2026-10-25-recovery/directus-reference-location-resolution.json); [review evidence](builds/2026-10-25-recovery/directus-feedback-review-parent-scope.json)).

**Latest local CAP-037 learning-plan activation batch (25 October 2026):** Migration 629 adds a separately granted activation queue/action for only the latest receipt-backed submitted plan version with an independent approved decision. The plan owner cannot activate their own submission; activation atomically changes `submitted` to `active` and appends a private retry receipt. The 430-test focused Gateway, route-policy, console, and migration-integrity suite passes. Network-disabled disposable PostgreSQL 16 applies/replays the selected CAP-037 sequence ending at migration 629 with 266 grouped assertions on native AMD64 and ARM64/QEMU ([builds/2026-10-25-recovery/cap-037-learning-plan-activation-disposable.json](builds/2026-10-25-recovery/cap-037-learning-plan-activation-disposable.json); [builds/2026-10-25-recovery/cap-037-learning-plan-activation-arm64-disposable.json](builds/2026-10-25-recovery/cap-037-learning-plan-activation-arm64-disposable.json)). QEMU is software portability evidence only, not Raspberry Pi hardware acceptance. Candidate and legacy databases remain untouched; migration 629 is not rolled out. CAP-037 remains prepared and MAN-CAP-037 is not accepted; populated parity, live ZITADEL/browser, broader ACL/RLS, recovery, privacy review, and owner acceptance remain open. Checklist: 1,143 complete / 25 open (1,168 total); capability classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted.
**Latest local CAP-006 hive-inspection review batch (25 October 2026):** migration 627 extends the exact-location review queue to hive inspections and adds a dedicated bounded decision function. Hive source rows receive an optimistic `updated_at`; reasoned decisions are append-only and transactionally update only review state. The migration also withholds historical observation, pesticide, and inspection rows with unknown submitter attribution and adds an immutable-ledger guard, so independent review fails closed for unattributed records. The reviewer console presents inspection fields as self-reported and labels review as distinct from colony-health certification. The 58-test focused Gateway/console/policy selection and 450-test plus 8-subtest broader CAP-006 regression pass. Disposable PostgreSQL 16 applies/replays through migration 627 and passes 14 groups on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-inspection-review-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-inspection-review-arm64-disposable.json)). Candidate and legacy are untouched; migration 627 is not rolled out. QEMU is software portability evidence only. Inspection review code is prepared; populated-data parity, live OIDC/browser, broader ACL/RLS, Directus parity, physical-device acceptance, and MAN-CAP-006 remain open. Checklist: 1,136 complete / 25 open (1,161 total).
**Latest local CAP-006 independent pollinator-review batch (25 October 2026):** Migration 626 adds signed exact-location review queue and decision functions for recorded observations and pesticide-impact reports. Submitters cannot review their own records; decisions require a reason and current source timestamp, replay only for identical request/input, and atomically append immutable operator-attributed history. Runtime uses only bounded functions; Directus and direct source/ledger access are denied. A grant-gated, CSRF/no-store console panel renders allowlisted values as text and preserves retry IDs. The focused 88-test Gateway/console/policy/migration selection and broader CAP-006 regression (444 tests plus 8 subtests) pass with Ruff, Python compilation, dependency/provider-boundary and matrix checks. Disposable PostgreSQL 16 apply/replay passes 11 grouped assertions on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-independent-review-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-independent-review-arm64-disposable.json)). Candidate and legacy remain untouched; migration 626 is not rolled out. QEMU is software portability evidence only. Independent hive-inspection review, populated parity, live OIDC/browser, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,134 complete / 23 open (1,157 total); all 67 named MAN-CAP checks remain not accepted.
**Latest local CAP-006 managed-hive lifecycle batch (25 October 2026):** migration 625 adds a private paginated hive-detail route under `pollinator_health:read_detail` and location-scoped status/maintenance updates under `pollinator_health:edit`. Updates require a reason and expected `updated_at`, reject stale writes, and append immutable operator-attributed before/after events atomically. Runtime and Directus cannot directly change hive state or access the private event ledger. The console keeps management separate from recorded inspections and does not present operational status as health verification. The 34-test Gateway/console/policy selection and 316-test broader CAP-006
and waste regression pass. Disposable PostgreSQL 16 applies/replays migrations 155/602/619/620/621/622/623/624/625 with 17 grouped assertions on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-hive-lifecycle-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-hive-lifecycle-arm64-disposable.json)). Candidate and legacy remain untouched; migration 625 is not rolled out. QEMU is software portability evidence only. Populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,133 complete / 23 open (1,156 total).
**Latest local CAP-006 pollinator habitat lifecycle batch (25 October 2026):** migration 624 adds a separate `pollinator_health:read_detail` inventory route and exact-location `pollinator_health:edit` updates for status, condition, and maintenance date. Updates require a reason and expected `updated_at`, fail closed on stale writes, and atomically append an immutable operator-attributed before/after event. Runtime and Directus cannot directly change habitat rows or access the private ledger. The console separates detail/edit grants and preserves the source domain vocabulary; reported state is not ecological verification. The combined CAP-006 Gateway/console/policy/ecology/waste/migration selection passes 297 tests. Disposable PostgreSQL 16 apply/replay passes nine authorization, stale-write, retry, audit, and ACL groups on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-habitat-lifecycle-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-habitat-lifecycle-arm64-disposable.json)). Candidate and legacy are untouched; migration 624 is not rolled out. QEMU is software portability evidence only. Hive status/maintenance, populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,133 complete / 23 open (1,156 total).
**Latest local CAP-006 pollinator-capture batch (24 October 2026):** migration 619 adds recorded-only observation capture under exact `pollinator_health:create`, operator attribution, private digest-only retry receipts, same-location plot/hive checks, and a separate least-privilege function owner. The legacy observation CLI fails before database access; the console create form and verified/reviewed summary reads remain separately grant-gated. A transaction audit also corrected success-path rollback in waste, compost, recycling, and pollution incident Gateway capture/resolution wrappers. The focused ecology/capture/console selection passes 162 tests. Disposable PostgreSQL 16 applies and replays 155/602/619 with 12 assertion groups on native AMD64 and ARM64/QEMU ([native](builds/2026-10-24-recovery/cap-006-pollinator-observation-capture-disposable.json); [ARM64/QEMU](builds/2026-10-24-recovery/cap-006-pollinator-observation-capture-arm64-disposable.json)). Candidate and legacy remain untouched; migration 619 is not rolled out. QEMU is software evidence only. Populated-data parity, live OIDC/browser, independent observation review, habitat, hive, and inspection writers, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,127 complete / 25 open (1,152 total).
**Latest local CAP-006 pesticide-impact report batch (25 October 2026):** migration 620 adds completed-application reports under exact `pollinator_health:create`, operator attribution, digest-only retry receipts, and a separate least-privilege function owner. Reports remain `recorded`; the Gateway and console do not approve pesticide use or determine safety. The legacy pesticide CLI fails before database access. The 80-test capture selection and 218-test combined CAP-006 regression pass; disposable PostgreSQL 16 apply/replay passes nine authorization, retry, lifecycle and ACL groups on native AMD64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pesticide-impact-capture-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pesticide-impact-capture-arm64-disposable.json)). Candidate and legacy remain untouched; migration 620 is not rolled out. Habitat, hive and inspection writes, populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity and MAN-CAP-006 remain open. QEMU is software evidence only. Checklist: 1,128 complete / 25 open (1,153 total).
**Latest local CAP-006 managed-hive inspection capture (25 October 2026):** migration 623 appends `recorded` inspection rows under exact location `pollinator_health:create`, checks signed operator context and a unique active hive at that location, attributes the inspector, and records digest-only retries. The function updates the hive snapshot in the same transaction. Runtime and Directus cannot directly mutate inspections or those snapshot fields; legacy `record-inspection` fails before database access. The 103-test focused selection and 277-test combined CAP-006 regression pass. Disposable PostgreSQL 16 migration apply/replay passes 14 groups on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-hive-inspection-capture-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-hive-inspection-capture-arm64-disposable.json)). Candidate and legacy remain untouched; migration 623 is not rolled out. QEMU is software evidence only. Hive status/maintenance, habitat status/maintenance, populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,131 complete / 25 open (1,156 total).
**Latest local CAP-006 managed-hive registration batch (25 October 2026):** migration 622 registers hives through exact `pollinator_health:create`, validates signed location context and bounded fields, prevents case-insensitive duplicate hive IDs within a location, attributes the operator, and stores digest-only retries. Runtime and Directus cannot directly insert hives or read receipts; existing update/inspection paths remain for the next slice. The `active` state is operational inventory only and colony strength remains self-reported. The legacy `add-hive` CLI fails before database access. A 116-test selection passes within the 254-test combined CAP-006 regression, with Ruff, compilation, Node syntax and diff checks; disposable PostgreSQL 16 apply/replay passes eight groups on native x86_64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-hive-capture-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-hive-capture-arm64-disposable.json)). Candidate and legacy are untouched; migration 622 is not rolled out. Habitat status/maintenance, hive inspections/status maintenance, populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity, and MAN-CAP-006 remain open. QEMU is software evidence only. Checklist: 1,130 complete / 25 open (1,155 total).
**Latest local CAP-006 pollinator-habitat capture batch (25 October 2026):** migration 621 adds self-reported active habitat inventory capture under exact `pollinator_health:create`, with operator attribution, a separate function owner, bounded species/features and digest-only retries. Active is the legacy domain inventory state, not ecological review or outcome verification; runtime and Directus cannot write directly or read receipts. The legacy habitat-create CLI fails before database access. The 235-test combined CAP-006 selection passes. Disposable PostgreSQL 16 apply/replay passes ten authorization, retry, domain-state and ACL groups on native AMD64 and ARM64/QEMU ([native](builds/2026-10-25-recovery/cap-006-pollinator-habitat-capture-disposable.json); [ARM64/QEMU](builds/2026-10-25-recovery/cap-006-pollinator-habitat-capture-arm64-disposable.json)). Candidate and legacy remain untouched; migration 621 is not rolled out. Habitat status/maintenance and hive inspection writers, populated parity, live OIDC/browser, independent review, broader ACL/RLS, Directus parity and MAN-CAP-006 remain open. QEMU is software evidence only. Checklist: 1,129 complete / 25 open (1,154 total).
**ARM64/QEMU portability evidence (25 October 2026):** the current working-tree image based on `9385eeb9`, including the Delphi service boundary changes, reports `aarch64`, creates the Gateway, recursively inspects 347 route templates across four included router groups, imports both Python SDK clients plus worker/Delphi modules, and loads all 18 JobSpecs. The no-network container used a read-only root and read-only SDK source mount ([app smoke](builds/2026-10-25-recovery/arm64-kernel-current-source-smoke-9385eeb9.json)). A separate clean, network-disabled PostgreSQL 16 ARM64/QEMU replay applies all 630 current schema files through migration 639 with zero pending/failed, no seeds or farm data, no host ports, and successful cleanup; the database reports `aarch64` ([full schema replay](builds/2026-10-25-recovery/arm64-qemu-current-schema-639.json)). Candidate and legacy are untouched. This is software-emulation evidence only, not physical Raspberry Pi, power-failure, thermal, or endurance acceptance.
**Latest local CAP-006 waste-summary reader batch (24 October 2026):** Migration 618 routes verified waste, composting, and recycling aggregates through a no-login function owner that checks signed location context and the exact `waste_management:read` grant. Runtime and Directus lose direct reads on all three tables and both legacy summary views; only Gateway runtime can execute the function. The two unscoped analytics summary CLI paths fail before database access. Authenticated Gateway output preserves the legacy 1–3650-day verified waste totals by type/disposal and compost totals, method averages, and latest-ten numeric quality readings; the console offers 7/30/90/365-day windows. Thirty-eight focused Gateway, analytics, and console tests pass. Ruff, Python compilation, JavaScript syntax, dependency boundaries, requirements alignment, matrix, runtime SQL inventory, and diff checks pass. Disposable PostgreSQL 16 applies/replays migrations 153 and 613–618, verifies selected-window behavior and synthetic output parity, and denies direct table/view access on native AMD64 and ARM64/QEMU ([native](builds/2026-10-24-recovery/cap-006-waste-summary-reader-disposable.json); [ARM64/QEMU](builds/2026-10-24-recovery/cap-006-waste-summary-reader-arm64-disposable.json)). Candidate and legacy remain untouched; migration 618 is not rolled out. QEMU does not prove physical Pi behavior. Broader waste ACL/RLS, populated-data parity, live OIDC/browser, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,126 complete / 25 open (1,151 total).
**Latest local CAP-006 incident reader-boundary batch (24 October 2026):** Migration 617 routes both narrative review and aggregate incident summaries through separate least-privilege database functions. Each function checks active operator/location context and the exact `waste_management:review` or `waste_management:read` grant; shared runtime and Directus roles lose table- and column-level incident reads and access to the legacy narrative view. The review-only and read-only synthetic grants are tested independently, along with wrong-location denials and direct-read rejection. Twenty-seven focused Gateway tests pass with Ruff and compilation, and disposable PostgreSQL 16 migration apply/replay and ACL acceptance passes on native AMD64 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-24-recovery/cap-006-waste-incident-review-reader-disposable.json); [ARM64 evidence](builds/2026-10-24-recovery/cap-006-waste-incident-review-reader-arm64-disposable.json)). A separate clean network-disabled ARM64/QEMU replay applied all 607 schema files through migration 616 with zero pending or failed and successful cleanup ([full-schema evidence](builds/2026-10-24-recovery/arm64-qemu-current-schema-616.json)); its source predates migration 617. QEMU demonstrates software portability, not physical Raspberry Pi, power, thermal, or endurance acceptance. Candidate and legacy databases are untouched; migration 617 is not rolled out. This closes the direct incident-read path only; broader waste-table ACL/RLS, populated parity, live OIDC/browser, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,125 complete / 25 open (1,150 total).
**Latest local CAP-006 incident-detail CLI retirement (24 October 2026):** The unscoped `open-incidents` and mixed waste `dashboard` helper/CLI paths now fail before database access, closing the local shared-credential bypass of the incident review grant. The aggregate summary remains on the Gateway `waste_management:read` route and narrative queue/resolution require `waste_management:review`. The focused waste/Gateway/console/route-policy selection passes 52 tests plus five subtests; Ruff, compilation, migration-153 disposable PostgreSQL acceptance, matrix validation, SQL inventory, and diff checks pass. Candidate and legacy databases remain untouched. Incident source/populated parity, live OIDC/browser, canonical ACL/RLS, Directus parity, and MAN-CAP-006 remain open. Checklist: 1,124 complete / 25 open (1,149 total).
**Latest local CAP-006 pollution-incident batch (24 October 2026):** Migration 616 adds location-scoped incident capture under `waste_management:create` and a separate queue/resolution surface under `waste_management:review`. Distinct least-privilege function owners, signed tenant context, bounded inputs, reviewer attribution, private retry receipts, direct-write denial, and separately gated text-only console forms are covered. The focused selection passes 156 tests plus five subtests; Ruff and compilation pass. Disposable PostgreSQL 16 applies/replays through migration 616 and verifies lifecycle, retries, authorization, and runtime/Directus ACLs on native AMD64 and linux/arm64 Docker/QEMU; QEMU is software portability evidence only ([native](builds/2026-10-24-recovery/cap-006-waste-incident-capture-disposable.json); [ARM64/QEMU](builds/2026-10-24-recovery/cap-006-waste-incident-capture-arm64-disposable.json)). Unscoped legacy writers fail before database access. Candidate and legacy databases are untouched; migration 616 is not rolled out. CAP-006 remains prepared pending populated parity, live OIDC/browser acceptance, remaining ACL/RLS and Directus parity, and MAN-CAP-006 review. Checklist: 1,123 complete / 25 open (1,148 total).
**Previous local CAP-006 recycling-capture batch (24 October 2026):** Migration 615 adds an exact-grant Gateway route, separately gated console form, recorded-only function/receipt boundary, bounded preservation of freeform material labels, destination, optional revenue, and notes. The legacy helper and CLI fail before database access; runtime and Directus direct writes to recycling rows are revoked while SELECT is preserved. The focused Gateway, read/write, console, route-policy, and migration selection passes 134 tests plus five subtests. Ruff, Python compilation, dependency alignment, matrix validation, and diff checks pass. Disposable PostgreSQL 16 apply/replay and authorization/receipt/ACL checks pass on native AMD64 and linux/arm64 Docker/QEMU; QEMU is software portability evidence only ([native](builds/2026-10-24-recovery/cap-006-waste-compost-recycling-capture-disposable.json); [ARM64/QEMU](builds/2026-10-24-recovery/cap-006-waste-compost-recycling-capture-arm64-disposable.json)). Candidate and legacy databases remain untouched; migration 615 is not rolled out. CAP-006 remains prepared pending populated parity, live OIDC/browser acceptance, canonical ACL/RLS and Directus parity, and MAN-CAP-006 review. Checklist: 1,122 complete / 25 open (1,147 total).
**Latest local CAP-006 composting-capture batch (24 October 2026):** Migration 614 adds an exact-grant Gateway compost route, a separately gated console form, and a recorded-only function/receipt boundary with bounded freeform-label preservation; the old helper and CLI fail before database access. The focused selection passes 118 tests plus five subtests, Ruff and compilation pass, and disposable PostgreSQL 16 applies/replays migrations 153/613/614 with tenant, retry, receipt-privacy, and function-owner checks ([evidence](builds/2026-10-24-recovery/cap-006-waste-and-compost-capture-disposable.json)). The legacy migration-153 runner now uses synthetic compost read fixtures. Candidate/legacy databases and providers remain untouched; migration 614 is not rolled out. Native and linux/arm64 Docker/QEMU acceptance passes (software portability only; no physical Pi claim) ([ARM64 evidence](builds/2026-10-24-recovery/cap-006-waste-and-compost-capture-arm64-disposable.json)). CAP-006 remains prepared; populated parity, canonical ACL/RLS, live OIDC/browser, and MAN-CAP-006 remain open. Checklist: 1,121 complete / 25 open (1,146 total).
**Latest local CAP-006 legacy-writer retirement batch (24 October 2026):** The `record_waste` helper now rejects before cursor acquisition and its CLI fails before database connection, directing operators to the exact-grant Gateway capture form. The focused waste/Gateway/console/route-policy selection passes 61 tests plus five subtests; Ruff and Python compilation pass. The migration-153 disposable PostgreSQL 16 check now uses synthetic read fixtures and confirms the retired helper fails closed ([evidence](builds/2026-10-24-recovery/cap-006-legacy-waste-writer-retirement.json); [disposable evidence](builds/2026-10-24-recovery/cap-006-waste-management-disposable.json)). The only database was an isolated disposable PostgreSQL 16 instance; no candidate/legacy migration rollout or provider was used. Other local waste writers still lack tenant context; canonical ACL/RLS, populated parity, live OIDC/browser, Directus field parity, and MAN-CAP-006 remain open. Checklist: 1,120 complete / 25 open (1,145 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.
**Previous local CAP-006 waste-stream capture batch (24 October 2026):** Migration 613 adds a location-scoped `waste_management:create` Gateway operation and an isolated function owner with a private exact-retry receipt. The console independently gates create and verified-summary access; records remain `recorded` and require separate human verification. The dedicated 32-test and broader 98-test selections (the latter includes migration checks and five subtests) pass, and disposable PostgreSQL 16 applies/replays migrations 153/613 with five grouped authorization, retry, lifecycle and ACL checks on native AMD64 and linux/arm64 Docker/QEMU. QEMU does not establish physical Raspberry Pi acceptance. Candidate and legacy databases remain untouched; migration 613 is not rolled out. At that capture-batch boundary the legacy `record_waste` helper and CLI still allowed an unscoped write; the following batch retires that path. Other local write CLIs remain trusted and unscoped. Canonical-table ACL/RLS and Directus field parity remain open. CAP-006 remains prepared and MAN-CAP-006 is not accepted. Checklist: 1,119 complete / 25 open (1,144 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.
**Latest local CAP-037 consent-filtered coaching console batch (24 October 2026):** Migration 612 adds an exact-location coach-grant participant selector limited to active verified people with the latest active location-specific coaching consent. The Gateway and console expose bounded search, paging, private capture and own-history only; capture rechecks consent. Native and linux/arm64 Docker/QEMU disposable PostgreSQL 16 replay through 612 pass 278 assertion groups; the focused Gateway/write/policy/console/migration selection passes 283 tests. QEMU is portability evidence only. Candidate and legacy databases are untouched and migration 612 is not rolled out. CAP-037 remains prepared; MAN-CAP-037 is not accepted. Checklist: 1,118 complete / 25 open (1,143 total).
**Latest local CAP-037 private coaching-session batch (24 October 2026):** Migration 611 adds a location-scoped `operating_pilot:coach` POST for private session capture and a GET for the authenticated operator’s own history. The Gateway validates bounded content before connecting and binds signed tenant context to the transaction; the migration rechecks the active human binding, exact farm/location mapping, active participant, and latest exact coaching consent. Append-only receipts make exact retries idempotent and reject changed reuse; withdrawal suppresses prior history and blocks new capture. Runtime and Directus have no direct session/receipt access. The focused Gateway, route-policy, and migration-integrity selection passes 234 tests; native network-disabled PostgreSQL 16 replay through migration 611 passes 269 assertion groups. linux/arm64 Docker/QEMU replay also passes all 269 assertions ([ARM64 evidence](builds/2026-10-24-recovery/cap-037-private-coaching-session-arm64-disposable.json)); the route contract and remaining gates are recorded in [the contract](operating-pilot-kernel-read-contract.md), [batches](batches.md), and [progress](progress.md). Candidate and legacy databases remain untouched; migration 611 is not rolled out. CAP-037 remains prepared, and MAN-CAP-037 is not accepted.
**Previous local CAP-037 learning-plan review-decision batch — independent approve/reject (24 October 2026):** Migration 610 adds an exact-location decision route for receipt-backed submitted plans. Approval remains `submitted` and does not activate; rejection returns the plan to `draft` and makes bounded feedback visible only in the owner’s own history. Decisions bind to the latest exact submission version, exclude self-review, and use a private append-only idempotency ledger. Revisions/resubmissions start a new undecided version. The console uses the exact review grant, acknowledgement, CSRF/no-store, and stable retry IDs. Migration 610 removes stale PUBLIC/runtime/Directus table- and column-level ledger grants before applying the bounded function-owner privileges. The focused Gateway, policy, console, and migration selection passes 401 tests; Ruff and compilation pass. Network-disabled PostgreSQL 16 applies/replays through 610 with 260 assertions on native AMD64 and linux/arm64 Docker/QEMU ([migration](../schemas/postgres/610_location_operating_pilot_learning_plan_review_decision.sql); [contract](operating-pilot-kernel-read-contract.md); [native evidence](builds/2026-10-24-recovery/cap-037-learning-plan-review-decision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-24-recovery/cap-037-learning-plan-review-decision-arm64-disposable.json)). QEMU is software portability evidence only. Candidate and legacy are untouched; migration 610 is not rolled out. At that point the legacy unscoped coaching writer had been disabled before database access; the following coaching-session slice adds the signed location-scoped private path, while aggregate-only counts remain available. CAP-037 remains prepared pending populated parity, live ZITADEL/browser acceptance, broader ACL/RLS, recovery, privacy review, and named owner acceptance. Checklist: 1,115 complete / 25 open (1,140 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Previous local CAP-037 learning-plan review-queue batch — read-only independent review (24 October 2026):** Migration 609 adds a bounded exact-location review queue for the latest receipt-backed submission per plan that remains `submitted`. It requires signed tenant context, the live `operating_pilot:review` grant, one active human binding, and the Adelphi farm mapping; self-review, receiptless legacy rows, other farms, and stale receipts are excluded. The console exposes content-only read access with bounded paging and no lifecycle action. The focused Gateway, route-policy, console, and migration-integrity selection passes 230 tests; network-disabled PostgreSQL 16 apply/replay passes 240 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-24-recovery/cap-037-learning-plan-review-queue-disposable.json); [ARM64/QEMU evidence](builds/2026-10-24-recovery/cap-037-learning-plan-review-queue-arm64-disposable.json)). Candidate and legacy are untouched, migration 609 is not rolled out, and QEMU is not physical Raspberry Pi acceptance. CAP-037 remains prepared pending review decisions, populated parity, live OIDC/browser behavior, broader ACL/RLS, recovery, privacy review, and named owner acceptance. Checklist: 1,114 complete / 25 open (1,139 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-037 submission batch — owner-only learning-plan submission (24 October 2026):** Exact location `operating_pilot:submit_own` exposes a one-way owner submission from receipt-backed `draft` to `submitted`; migration 608 repeats signed location, active human binding, grant, ownership, receipt, and active-farm checks and adds an append-only idempotency receipt. The console requires both own-history and submit-own grants, confirmation, CSRF/no-store, and stable retry IDs. Independent review remains separate. 202 focused Gateway, route-policy, and console tests plus 36 migration-integrity tests pass; native and linux/arm64 QEMU disposable PostgreSQL 16 replay through 608 passes 232 grouped assertions. QEMU is software portability evidence only. Candidate and legacy remain untouched; CAP-037 remains prepared pending review/decision parity and named owner acceptance.

**Previous local CAP-037 console batch — private own learning-plan history (24 October 2026):** The operator console adds a hidden-by-default read-only learning-plan history panel under the exact location `read_own` grant. It uses same-origin no-store requests, bounded pagination, stale-location protection, and text-only rendering with capped structured values; no write or review action is exposed. All 36 operator-console operating-pilot tests pass, including the new contract and JavaScript syntax regression. No database or migration was used for this UI slice ([contract](operating-pilot-kernel-read-contract.md)). CAP-037 remains prepared pending write/review parity, populated data comparison, live OIDC/browser acceptance, broader ACL/RLS, recovery, and owner acceptance. Checklist: 1,110 complete / 25 open (1,135 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.
**Latest local CAP-037 draft creation batch — private learning-plan drafts (24 October 2026):** The exact-location `operating_pilot:create` route creates only an attributed canonical draft after the Gateway and migration 606 independently validate bounded input, signed tenant context, the active person binding, and the farm-to-location mapping. An append-only receipt replays unchanged requests and rejects changed request-ID reuse. The create-only console form is CSRF-protected and no-store; retries accept a valid current lifecycle status without repeating the write. The 188-test Gateway/route-policy/console selection passes with Ruff, Python compilation, dependency-group alignment, runtime SQL inventory (4,792 execution sites), capability validation, and diff checks. Network-disabled disposable PostgreSQL 16 applies/replays migration 606 and passes 214 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([migration](../schemas/postgres/606_location_operating_pilot_learning_plan_draft.sql); [contract](operating-pilot-kernel-read-contract.md); [native evidence](builds/2026-10-24-recovery/cap-037-learning-plan-draft-disposable.json); [ARM64/QEMU evidence](builds/2026-10-24-recovery/cap-037-learning-plan-draft-arm64-disposable.json)). QEMU is software portability evidence only, not physical Raspberry Pi acceptance. Candidate and legacy are untouched; migration 606 is not rolled out. CAP-037 remains prepared pending lifecycle review/submission, populated parity, live OIDC/browser, broader ACL/RLS, recovery, privacy review, and owner acceptance. Checklist: 1,111 complete / 25 open (1,136 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.
**Latest local CAP-037 learning-plan revision batch — owner-only draft editing (24 October 2026):** The console now offers editing only for the operator's receipt-backed `draft` and only when the exact location `operating_pilot:edit_own` grant is present. PUT uses a 32 KiB body cap, CSRF/no-store, stable retry IDs, and optimistic concurrency against `updated_at`. Migration 607 limits edits to content columns, preserves draft status, checks current ownership/location/grant, rejects receiptless legacy and submitted plans, replays exact retries, and rejects changed or stale requests. The Gateway, route-policy, console, and migration selection passes 196 tests; Ruff, compilation, dependency-group alignment, provider boundaries, runtime SQL inventory, capability validation, and diff checks pass. Network-disabled disposable PostgreSQL 16 applies/replays through migration 607 and passes 224 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([migration](../schemas/postgres/607_location_operating_pilot_learning_plan_revision.sql); [contract](operating-pilot-kernel-read-contract.md); [native evidence](builds/2026-10-24-recovery/cap-037-learning-plan-revision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-24-recovery/cap-037-learning-plan-revision-arm64-disposable.json)). QEMU verifies software portability only, not physical Raspberry Pi hardware. Candidate and legacy remain untouched; migration 607 is not rolled out. Roll back by disabling the PUT route, exact policy, and edit control while preserving the additive migration and receipts if applied. CAP-037 remains prepared pending submission/review parity, populated-data comparison, live OIDC/browser behavior, broader ACL/RLS, recovery, privacy review, and MAN-CAP-037 acceptance. Checklist: 1,112 complete / 25 open (1,137 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-039 implementation batch — dataset inventory failure redaction (24 October 2026):** The `--list` and initial `--all` inventory failure paths print and raise only a fixed operation label plus a sanitized exception class, and still close their connection. Twenty dataset-refresh tests and five scheduler/feature checks pass with Ruff, compilation, six inventory checks, matrix validation, and diff checks. The saved-SQL feature remains disabled; no database/provider was used ([evidence](builds/2026-10-24-recovery/cap-039-dataset-inventory-error-redaction.json)). Checklist: 1,099 complete / 25 open (1,124 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-039 implementation batch — dataset-refresh definition cursor failure cleanup (24 October 2026):** The initial saved-dataset lookup cursor closes on execute and row-fetch failures; injected regressions verify the reporting reader is not invoked. Twenty dataset-refresh tests and five scheduler/feature checks pass with Ruff, compilation, six static inventory checks, matrix validation, and diff checks. The saved-SQL feature remains disabled by default, and no database/provider was used. Broader query and tenant policy and populated parity remain open ([evidence](builds/2026-10-24-recovery/cap-039-dataset-refresh-definition-cursor-cleanup.json)). Checklist: 1,098 complete / 25 open (1,123 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-039 implementation batch — dataset-refresh CLI selector and cleanup (24 October 2026):** The legacy stored-SQL refresh CLI rejects conflicting `--all` selectors before feature or database access and closes inventory cursors/connections when listing or bulk inventory queries fail. The 18-test refresher suite and five scheduler/feature contract checks pass with Ruff, compilation, six static SQL/worker inventory checks, matrix validation, and diff checks. Stored-SQL refresh remains disabled by default; no database, provider, candidate, or legacy stack was used. No migration is needed. Query-ID policy, location parameterization and tenant scope, and populated report/dashboard parity remain open ([evidence](builds/2026-10-24-recovery/cap-039-dataset-refresh-cli-cleanup.json)). Checklist: 1,097 complete / 25 open (1,122 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-008 implementation batch — configurable conditional-simulation mode count (24 October 2026):** GSTools RandMeth now accepts a bounded `--mode-no` from 1 to 1,000 with the previous 1,000-mode default. Lower counts trade spectral fidelity for runtime; successful persisted realizations record the mode count, generator, sampling policy, and GSTools version in existing JSONB metadata. The CLI and database runner preflight settings. Deterministic 128-draw fixtures compare spherical and Gaussian conditional moments at 100 modes; Matérn remains finite-draw smoke coverage. The full geostatistics module passes 145 tests; focused checks, Ruff, compilation, and diff checks pass. No migration or database was used. This is synthetic consistency and configurable execution, not scientific or populated-data acceptance. CAP-008 remains prepared pending populated parity, independent scientific review, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-mode-count-and-family-moments.json)). Checklist: 1,096 complete / 25 open (1,121 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-008 implementation batch — synthetic conditional-simulation moment reference (24 October 2026):** a deterministic synthetic regression samples 512 seeded GSTools conditional realizations, checks pointwise sample means and variances against ordinary-kriging conditional moments within four-standard-error tolerances, verifies zero-nugget observations are honored, and confirms E-type/percentile outputs match those draws. The full geostatistics module passes 130 tests; Ruff and Python compilation pass. No provider or database was used. The previous algorithm used a Simple-Kriging mean plus globally standardized unconditional residuals, so exact legacy draw equality is not a valid scientific oracle. This test adds model-consistency evidence but does not close populated-data parity, independent scientific review, or MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-synthetic-simulation-moments.json)). Checklist: 1,094 complete / 25 open (1,119 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-008 implementation batch — saved kriging prediction point pages (24 October 2026):** the exact-location `geostatistics:read` Gateway now reads one saved kriging run’s prediction points through a no-store, repeatable-read route. Signed tenant context is set before queries, and parent, count, and page lookups all qualify by requested location; pages contain at most 50 ordered points. The projection contains only sequence, WGS84 coordinates, prediction, variance, and standard deviation; IDs, model references, thresholds, weights, neighbor counts, search radii, and metadata are omitted. A hidden-by-default console action loads and text-renders the advisory point detail. The 45-test Gateway/route-policy/console selection passes with Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks. No migration or database was used. CAP-008 remains prepared pending scientific/populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-kriging-point-kernel-read.json)). Checklist: 1,093 complete / 25 open (1,118 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Latest local CAP-008 implementation batch — saved simulation point pages (24 October 2026):** the exact-location `geostatistics:read` Gateway now reads one realization’s saved points through a no-store, repeatable-read route. It establishes signed tenant context before queries, selects the run by both ID and location, repeats location qualification on the point count and page query, and returns at most 50 deterministic points per request. The console exposes a “View points” action from each summary and renders point number, WGS84 coordinates, and advisory simulated value as text; the realization UUID is carried only as an internal request handle and is not displayed. The 39-test Gateway, route-policy, and console-contract selection passes with Ruff, compilation, inline JavaScript parsing, current runtime SQL inventory, and diff checks. No migration or database was used. CAP-008 remains prepared pending populated/scientific parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-realization-point-kernel-read.json)). Checklist: 1,092 complete / 25 open (1,117 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows; 0/67 MAN-CAP checks accepted.

**Previous local CAP-008 implementation batch — bounded conditional field simulation (24 October 2026):** the legacy dense grid-covariance/Cholesky path is replaced by seeded GSTools `CondSRF` conditional fields using ordinary kriging, with legacy result fields and CLI names retained. Input and variogram settings are validated before simulation; source rows fail closed; grid, realization, and aggregate-value caps are 100,000, 1,000, and 1,000,000 respectively. Local-meter persistence converts coordinates to WGS84 before writing `geometry(4326)`, rejects unusable origins before database access, and samples deterministically. The complete geostatistics module passes 129 tests; Ruff, compilation, current runtime SQL inventory, matrix validation, and diff checks pass. No migration or database was used. The engine change requires numerical/populated parity and scientific review; CAP-008 remains prepared pending those checks, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-bounded-conditional-simulation.json)). Checklist: 1,091 complete / 25 open (1,116 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted.

**Current clean-schema and lifecycle guard checks — 23 October 2026:** a
network-disabled ARM64/QEMU PostgreSQL 16 replay applied all 588 schema files
through migration 597 with zero pending/failed files and successful cleanup.
CI #771 then exposed that a PostgreSQL superuser was implicitly classified as
a worker by migration 579's role-membership check during pilot seeding. New
migration 598 excludes superuser sessions from that inference while retaining
terminal-state denial for explicit worker roles and non-superuser worker
logins. A repeatable role-boundary regression now runs in the full CI script
using the digest-pinned Compose PostgreSQL image. The focused source/migration
selection passes 49 tests (nine existing database-dependent skips); disposable
PostgreSQL 16.4 and 16.15 replay/role checks pass with admin/operator
publication allowed and worker publication denied. This does not change
capability classification or MAN-CAP acceptance. Evidence: [ARM64/QEMU schema
replay](builds/2026-10-23-recovery/arm64-qemu-current-schema-597-after-bootstrap-retry.json),
[repeatable worker/admin check](builds/2026-10-23-recovery/agent-safety-superuser-ci-regression.json),
[PostgreSQL 16.15 boundary check](builds/2026-10-23-recovery/agent-safety-superuser-session-disposable.json).

**Migration 599 ARM64 portability — 23 October 2026:** the targeted disposable
credit-adjustment acceptance passes on the ARM64 PostGIS image under QEMU and
on a native PostGIS image. The containers report `aarch64` and `x86_64`,
respectively; migrations 405, 419, and 599 apply, migration 599 replays, and all
six signed-scope, fallback-parity, privilege, and read-only checks pass on each
architecture. A separate full clean-schema attempt through 599 reached database
health after the five-minute startup grace period but failed at the first
`000_extensions.sql` command before any schema was applied; the runner captured
no PostgreSQL diagnostic and cleaned up its temporary project. Full current
schema replay through 599 remains open; this evidence does not establish
physical Raspberry Pi behavior or MAN-CAP acceptance ([targeted ARM64
acceptance](builds/2026-10-23-recovery/credit-adjustment-worker-arm64-disposable.json);
[native acceptance](builds/2026-10-23-recovery/credit-adjustment-worker-native-postgis-disposable.json);
[full replay attempt](builds/2026-10-23-recovery/arm64-qemu-current-schema-599.json)).

**Fresh-bootstrap compatibility for optional Directus — 23 October 2026:**
the ordered bootstrap now creates the historical `directus` role as a locked
`NOLOGIN` placeholder only when absent. This satisfies the role revocations in
migrations 595–597 while leaving an existing role and the distinct
`kokonut_directus_runtime` account unchanged. The focused migration/checker
selection passes 40 tests, with Ruff and compilation. An isolated ARM64/QEMU
PostgreSQL 16 check applied the bootstrap twice and verified the login,
inheritance, superuser, database/role creation, replication, and RLS-bypass
flags are all disabled ([evidence](builds/2026-10-23-recovery/optional-directus-placeholder-role-arm64.json)).
This closes the missing clean-bootstrap prerequisite, not current-source full
schema replay or Raspberry Pi hardware/power acceptance.

**Directus effective permission baseline — 23 October 2026:** the pinned Directus 12.1.1 profile applied and replayed the repository permission seed in a fresh disposable Kernel database under `kokonut_directus_runtime`. The snapshot contains 175 rows from nine repository-managed policies: 125 wildcard-field and 50 explicit-field rows; zero managed `farm_activity` permissions remain, and the second seed application leaves the complete snapshot unchanged (SHA-256 `93eec38a…f7877`). A synthetic API probe returns 403 `RESOURCE_RESTRICTED` when creating a custom permission; Agent Write remains read-only and Agent Write/Field Worker writes fail closed without rows. This identifies the unlicensed profile boundary, not successful role/field parity. Built-in/custom policies, broader API authorization, hook effects, populated targets, and MAN-CAP acceptance remain open. Evidence: [effective rows](builds/2026-10-23-recovery/directus-effective-permission-rows.json), [runtime probe](builds/2026-10-23-recovery/directus-effective-permissions.json).

**CAP-038 isolated Holistic Wellbeing source identity — 23 October 2026:** migration 584 gives this synthesis task a dedicated signed login and a NOLOGIN reader limited to three consent-filtered summaries; the shared synthesis reader loses them. Worker/profile routing uses separate source credentials while keeping draft writing separate. Focused worker/database/profile/migration checks pass (137); network-disabled PostgreSQL 16 applies/replays through 584 with 51 grouped assertions on native AMD64 and ARM64/QEMU. The fixture uses synthetic own/foreign rows through the real signed scope function. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and real grants are not deployed. CAP-038 remains prepared pending credential provisioning, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, physical Raspberry Pi, and human acceptance ([migration](../schemas/postgres/584_isolated_holistic_wellbeing_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-holistic-wellbeing-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-holistic-wellbeing-identity-arm64-disposable.json)). Checklist: 1,010 complete / 24 open (1,034 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Feedback source identity — 23 October 2026:** migration 585 gives Feedback Synthesis a dedicated signed login and a NOLOGIN reader limited to its one consent-safe stakeholder summary; the shared synthesis reader loses that projection. Worker/profile routing uses task-specific credentials while draft writing remains separate. Focused worker/database/profile/migration checks pass (140); network-disabled PostgreSQL 16 applies/replays through 585 with 54 grouped assertions on native AMD64 and ARM64/QEMU. The synthetic consent fixture includes owned public, private, and foreign public rows, and the real signed source view exposes only the owned record. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and worker grants are not deployed. CAP-038 remains prepared pending grant provisioning, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, Raspberry Pi hardware, and human acceptance ([migration](../schemas/postgres/585_isolated_feedback_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-feedback-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-feedback-identity-arm64-disposable.json)). Checklist: 1,011 complete / 24 open (1,035 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Commons Liberation source identity — 23 October 2026:** migration 586 gives this task a dedicated signed login and NOLOGIN reader limited to four location-filtered projections; the shared reader loses them. Worker/profile routing uses its own source credential while draft writing remains separate. Focused worker/database/profile/migration checks pass (143); network-disabled PostgreSQL 16 applies/replays through 586 with 57 grouped assertions on native AMD64 and ARM64/QEMU. Each real signed security-barrier view returns its synthetic own-location row and excludes the foreign row. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and worker grants are not deployed. CAP-038 remains prepared pending grants, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, physical Raspberry Pi, and human acceptance ([migration](../schemas/postgres/586_isolated_commons_liberation_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-commons-liberation-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-commons-liberation-identity-arm64-disposable.json)). Checklist: 1,012 complete / 24 open (1,036 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated GNH Alignment source identity — 23 October 2026:** migration 587 gives this task a dedicated signed login and NOLOGIN reader limited to five location-filtered projections; the shared reader loses them. Worker/profile routing uses its own source credential while draft writing remains separate. Focused worker/database/profile/migration checks pass (146); network-disabled PostgreSQL 16 applies/replays through 587 with 60 grouped assertions on native AMD64 and ARM64/QEMU. Each real signed security-barrier view returns its synthetic own-location row and excludes the foreign row. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and worker grants are not deployed. CAP-038 remains prepared pending grants, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, physical Raspberry Pi, and human acceptance ([migration](../schemas/postgres/587_isolated_gnh_alignment_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-gnh-alignment-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-gnh-alignment-identity-arm64-disposable.json)). Checklist: 1,013 complete / 24 open (1,037 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Regenerator source identity — 23 October 2026:** migration 588 gives Regenerator synthesis a dedicated signed login and NOLOGIN reader limited to four location-filtered public projections; the shared synthesis reader loses them. Worker/profile routing uses a task-specific source credential while draft writing remains separate. Focused worker/database/profile/migration checks pass (149); network-disabled PostgreSQL 16 applies/replays the focused chain through 588 with 63 grouped assertions on native AMD64 and ARM64/QEMU. Each real signed security-barrier view returns its synthetic own-location row and excludes the foreign row. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and worker grants are not deployed. CAP-038 remains prepared pending grants, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, physical Raspberry Pi, and human acceptance ([migration](../schemas/postgres/588_isolated_regenerator_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-regenerator-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-regenerator-identity-arm64-disposable.json)). Checklist: 1,014 complete / 24 open (1,038 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Capital Efficiency source identity — 23 October 2026:** migration 589 gives Capital Efficiency synthesis a dedicated signed login and NOLOGIN reader limited to four location-filtered projections; the shared synthesis reader loses them. Worker/profile routing uses a task-specific source credential while draft writing remains separate. Focused worker/database/profile/migration checks pass (152); network-disabled PostgreSQL 16 applies/replays the focused chain through 589 with 66 grouped assertions on native AMD64 and ARM64/QEMU. Each real signed security-barrier view returns its synthetic own-location row and excludes the foreign row. QEMU is software portability evidence only. Candidate and legacy are untouched; migration and worker grants are not deployed. CAP-038 remains prepared pending grants, populated parity, live OIDC/provider/browser checks, broader ACL/RLS, recovery, physical Raspberry Pi, and human acceptance ([migration](../schemas/postgres/589_isolated_capital_efficiency_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-capital-efficiency-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-capital-efficiency-identity-arm64-disposable.json)). Checklist: 1,015 complete / 24 open (1,039 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Financial Resilience source identity — 23 October 2026:** migration 590 gives Financial Resilience synthesis a task-specific signed login and NOLOGIN reader limited to three location-filtered projections plus the explicitly network-wide Green Paper publication-status view; the shared synthesis reader loses all four. Worker dispatch, named connection mapping, restore prerequisites, `.env.example`, and the optional Compose profile use the task-specific source identity while draft writing remains separate. The focused worker/database/profile/migration selection passes 155 tests; migration integrity passes 36. Ruff, compilation, Compose profile configuration, dependency/provider boundaries, refreshed inventories, capability validation, and diff checks pass. Network-disabled disposable PostgreSQL 16 applies/replays the chain through 590 with 69 grouped assertions on native AMD64 ([native evidence](builds/2026-10-23-recovery/cap-038-financial-resilience-identity-native-disposable.json)) and ARM64/QEMU ([ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-financial-resilience-identity-arm64-disposable.json)). Synthetic foreign rows are excluded by signed location context; the explicitly public Green Paper status remains readable. QEMU is software portability evidence only. Candidate and legacy remain untouched; migration 590 and real worker credentials/grants are not deployed. Disable the task/profile to roll back and retain the additive migration if applied. CAP-038 remains prepared pending credential/grant provisioning, populated parity, live OIDC/provider/browser acceptance, broader ACL/RLS, production recovery, physical Raspberry Pi acceptance, and human review. Checklist: 1,016 complete / 24 open (1,040 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 named MAN-CAP checks accepted.

**CAP-038 isolated Open Source Capitalist source identity — 23 October 2026:** migration 592 gives this task a dedicated signed login and NOLOGIN reader for three location-or-network views plus two network-wide catalogs; the shared reader loses these views and retains the five Kokonut Commons projections. The worker/profile uses dedicated source credentials while draft writing stays separate. Focused tests pass (161), and the network-disabled PostgreSQL 16 chain applies/replays through 592 with 75 grouped assertions on native AMD64 and ARM64/QEMU. Synthetic owned, unassigned, and foreign rows confirm mixed-scope filtering; QEMU is software portability evidence, not physical Pi acceptance. Candidate and legacy are untouched, and migration 592 is not deployed. CAP-038 remains prepared pending credential grants, populated parity, live provider/browser behavior, broader ACL/RLS, production recovery, physical Pi, and human acceptance ([migration](../schemas/postgres/592_isolated_open_source_capitalist_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-open-source-capitalist-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-open-source-capitalist-identity-arm64-disposable.json)). Checklist: 1,018 complete / 24 open (1,042 total); the 66 capability rows remain 30 baseline-retained, 7 deployed, and 29 prepared, with 0/66 MAN-CAP checks accepted.

**CAP-038 isolated Bio Factory source identity — 23 October 2026:** migration 591 gives Bio Factory synthesis a task-specific signed login and NOLOGIN reader limited to four location-filtered projections plus the explicitly network-wide regional input catalogue; the shared synthesis reader loses all five. Worker dispatch, named connection mapping, restore prerequisites, .env.example, and the optional Compose profile use the task-specific source identity while draft writing remains separate. The focused worker/database/profile/migration selection passes 158 tests; migration integrity passes 36. Ruff, compilation, Compose profile configuration, dependency/provider boundaries, refreshed inventories, capability validation, and diff checks pass. Network-disabled disposable PostgreSQL 16 applies/replays the chain through 591 with 72 grouped assertions on native AMD64 ([native evidence](builds/2026-10-23-recovery/cap-038-bio-factory-identity-native-disposable.json)) and ARM64/QEMU ([ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-bio-factory-identity-arm64-disposable.json)). Synthetic foreign farm rows are excluded by signed location context; signed context retains access to the explicitly public regional catalogue. QEMU is software portability evidence only. Candidate and legacy remain untouched; migration 591 and real worker credentials/grants are not deployed. Disable the task/profile to roll back and retain the additive migration if applied. CAP-038 remains prepared pending credential/grant provisioning, populated parity, live OIDC/provider/browser acceptance, broader ACL/RLS, production recovery, physical Raspberry Pi acceptance, and human review. Checklist: 1,017 complete / 24 open (1,041 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 named MAN-CAP checks accepted.

**CAP-038 authenticated worker lifecycle insert guard — 22 October 2026:**
migration 579 adds replay-safe terminal-status insert triggers to the same 43
tables already guarded for updates. The disposable PostgreSQL 16 chain passes
30 grouped checks across migrations 405, 578, and 579, including worker denial
through a security-definer wrapper, terminal insert denial on all 43 governed
table names, allowed drafts, and human-path preservation. The fixture excludes
an unrelated status table without a lifecycle trigger. The migration unit suite
passes 36 tests with Ruff, compilation, and diff checks. A network-disabled
ARM64/QEMU replay applies all 570 current schema files through migration 579
with zero pending/failed, no seeds or ports, `aarch64`, and verified cleanup.
The lifecycle fixture uses minimal synthetic table definitions; this does not
establish physical Raspberry Pi behavior. Per-task identities, broader source
least privilege, and MAN-CAP-038 acceptance remain open
([migration](../schemas/postgres/579_agent_safety_insert_guard.sql);
[disposable evidence](builds/2026-10-22-recovery/cap-038-agent-safety-insert-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/arm64-qemu-current-schema-579.json)).

**CAP-038 authenticated worker lifecycle guard — 22 October 2026:** migration
578 makes the existing governed-status trigger recognize authenticated worker
database logins and their security-definer calls; `app.agent_id` remains only an
additional restrictive compatibility marker. Disposable PostgreSQL 16 replay
and 22 grouped checks pass, along with the 36-test migration suite, Ruff,
compilation, and diff checks. This covers protected status updates only; it
does not provide per-agent identities, insert protection, least-privilege
source grants, or MAN-CAP-038 acceptance
([migration](../schemas/postgres/578_authenticated_agent_safety_trigger.sql);
[evidence](builds/2026-10-22-recovery/cap-038-agent-safety-trigger-disposable.json)).

**CAP-038 deterministic summary output scope — 22 October 2026:** the signed
source worker now rejects non-object output and rejects a returned
`location_id` that differs from the requested location before creating a draft.
All 47 agent worker CLI tests pass, including mismatch, malformed output,
successful draft, and read-only scope cases, with Ruff, compilation, capability
validation, and diff checks passing. This closes output-to-scope correlation
only; authenticated task identity, least-
privilege roles, populated parity, and MAN-CAP-038 acceptance remain open
([implementation](../services/agents/worker_cli.py);
[test](../tests/test_agent_worker_cli.py);
[evidence](builds/2026-10-22-recovery/cap-038-deterministic-summary-output-scope.json)).

**CAP-037 independent competency review — 22 October 2026:** migration 577
adds a bounded exact-location review queue and one-time verify/reject action
for receipt-backed submitted competency drafts. It enforces self-review
separation and append-only decision receipts; rejection feedback is visible
only in the submitter's own history. Native and linux/arm64 Docker/QEMU disposable PostgreSQL 16 replay through
migration 577 pass 199 grouped assertions, and the focused Gateway/route-policy/
console selection passes 317 tests. QEMU is software portability evidence;
physical Raspberry Pi, power, populated farm parity, live OIDC/browser, broader
ACL/RLS, production recovery, and MAN-CAP-037 acceptance remain open.

**CAP-037 competency self-service console — 22 October 2026:** the operator
console now supports private draft creation, own history, owner revision, and
submission for independent review under separate exact location grants. Reads
are bounded and no-store; writes use CSRF and stable retry IDs; values render as
text. An uncertain write remains bound to the original location and payload,
and the editor clears on a location switch. Focused console/Gateway/policy/
migration checks passed 333 tests ([evidence](builds/2026-10-22-recovery/cap-037-competency-console-contract.json)).
At that earlier console-only checkpoint, independent review/verification,
populated farm parity, live OIDC/browser, broader ACL/RLS, production recovery,
and MAN-CAP-037 acceptance remained open.

**CAP-037 competency draft revision and submission — 22 October 2026:**
Migration 576 adds exact `edit_own` and `submit_own` competency actions. The
Gateway validates and forwards both actions with signed location context;
revision retains a superseded version and submission moves only an owned draft
to `submitted`. Exact retries are idempotent. The 131-test Gateway/policy
selection and 198-group native disposable PostgreSQL 16 apply/replay acceptance
pass; native and ARM64/QEMU acceptance both pass 198 grouped assertions. QEMU
establishes software portability only, not physical Raspberry Pi acceptance.
Runtime and Directus have no direct table access. This is prepared
source/database acceptance only: independent review, candidate rollout,
populated-data parity, live OIDC/browser, broader ACL/RLS, production recovery,
and MAN-CAP-037 acceptance remain open
([migration](../schemas/postgres/576_location_operating_pilot_competency_draft_lifecycle.sql);
[tests](../tests/test_gateway_operating_pilot_writes.py);
[native evidence](builds/2026-10-22-recovery/cap-037-competency-draft-lifecycle-disposable.json)).

**CAP-047 freshness alert durable dispatch — 22 October 2026:** freshness
checks now persist each alert transition as a `data_stale` platform event in
the same transaction as its check and history row. Webhook, optional Directus,
and email intents are handled asynchronously through the existing notification
outbox with leases, retries, and dead-letter operations; no provider call runs
inside the freshness transaction. Existing migration 297 already routes
`data_stale` to the allowlisted callable handler, and the regression pins that
contract. The focused freshness, notification, event-runner, migration, and
worker-inventory
selection passes 202 tests, with Ruff, Python compilation, refreshed SQL/call
inventories, and capability-matrix validation passing. No PostgreSQL migration
was applied and no provider, candidate, or legacy service was contacted.
Destination ownership, live provider delivery/recovery, and
MAN-CAP-047 acceptance remain open ([implementation](../../services/ingestion/data_freshness.py);
[outbox](../../services/events/notification_outbox.py);
[existing handler registration](../../schemas/postgres/297_event_handler_registration_fix.sql);
[tests](../../tests/test_data_freshness_notification_outbox.py);
[evidence](builds/2026-10-22-recovery/freshness-alert-outbox-atomicity.json)).

**CAP-038 ecological-modeling provenance capacity and candidate rollout — 22 October 2026:** ecological modeling now captures bounded row-level provenance for 13 of its 14 input relations; the location subject is implicit in the signed summary scope. Migration 551 raises the shared source-manifest limit from 10 to 20 and adds minimal, exact-location projections for verified harvest events, active livestock groups, and verified feed-intake records. Draft, inactive, and non-location-matching rows remain excluded. The focused synthesis/worker/draft selection passes 123 tests. Network-disabled PostgreSQL 16 migration 550–551 apply/replay passes seven grouped checks on native AMD64 and ARM64/QEMU. A separate full ARM64/QEMU replay applied all 542 current schema files through migration 551 with zero pending or failed, no seeds, no host ports/network, and verified cleanup ([full replay evidence](builds/2026-10-22-recovery/arm64-qemu-current-schema-551.json)); this is software-emulation evidence only, not physical Raspberry Pi acceptance. After an age-encrypted checkpoint was successfully restore-rehearsed, the ordered runner applied migration 551 to the restored clone and local candidate; both have 542 schema entries through 551 and zero pending. Only the candidate app was recreated, and it is healthy. No seed or farm data was written; Metabase, proxy, PostgreSQL container, and legacy stack were not recreated. The candidate and checkpoint contain no location rows, so populated output parity remains unverified. A source-map audit across all 12 registered synthesis agents found only two intentional hints: location is the signed summary subject, and organic-compliance checklist rows have no governed review lifecycle and contain sensitive inspection evidence, so only their count-only ID/location projection is available and their IDs are omitted from reviewer provenance. Live OIDC, production worker credentials, physical Raspberry Pi acceptance, and MAN-CAP-038 owner acceptance remain open ([agent](../services/agents/ecological_modeling_agent.py); [migration](../schemas/postgres/551_ecological_synthesis_provenance_capacity.sql); [tests](../tests/test_synthesis_source_references.py); [native evidence](builds/2026-10-22-recovery/cap-038-ecological-modeling-provenance-capacity-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-ecological-modeling-provenance-capacity-arm64-disposable.json); [checkpoint and rollout](builds/2026-10-22-recovery/candidate-migration-551-rollout.json)).

**CAP-038 signed worker search-path hardening — 22 October 2026:** the five
remaining signed source-reader paths now set
`search_path = kokonut_agent_source, pg_catalog`. Deterministic summaries,
summary inspection, EBF evidence gaps, CIDS export, and Delphi reads cannot fall
through to a relation in `public`; their view dependencies are explicitly
available in the scoped source schema. The focused worker/EBF selection passes
56 tests, with Ruff and compilation passing. No migration or database was used.
This closes a source name-resolution boundary only; authenticated runtime
identity, populated parity, Directus parity, and MAN-CAP-038 acceptance remain
open ([worker](../services/agents/worker_cli.py);
[tests](../tests/test_agent_worker_cli.py);
[evidence](builds/2026-10-22-recovery/cap-038-agent-source-search-path.json)).

**Local candidate migration update — 22 October 2026:** the local candidate now
has 539 applied schema migrations through 548 and zero pending schema migrations.
The 104 migrations after 444 were first replayed on an isolated restored clone;
the candidate app was then rebuilt and verified healthy (`/health` 200, anonymous
operator review request 401). This is a candidate-only database rollout, not
production deployment or MAN-CAP acceptance. Worker/provider credentials,
real OIDC, production recovery, and Raspberry Pi hardware checks remain open.
See the [checkpoint and rollout evidence](builds/2026-10-22-recovery/candidate-migrations-445-548-rollout.json).

**CAP-038 synthesis source-login stale ACL cleanup — 22 October 2026:**
migration 541 now clears stale direct table, sequence, function, and public-schema
`CREATE` grants from the source login before establishing its bounded reader
role. This complements the existing removal of inherited public query-statistics
access. The focused disposable PostgreSQL 16 chain through migration 548 passes
36 assertions on native AMD64 and ARM64/QEMU (`aarch64`); migration regression
tests also pass (36). The candidate and legacy databases remain untouched. This
is database-privilege and software-emulation evidence only; credential
provisioning, live identity, populated parity, other agent paths, and
MAN-CAP-038 acceptance remain open
([migration](../schemas/postgres/541_agent_synthesis_source_reader.sql);
[native evidence](builds/2026-10-22-recovery/cap-038-source-login-stale-acl-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-source-login-stale-acl-arm64-disposable.json)).

**CAP-038 deterministic source-login schema ACL cleanup — 22 October 2026:**
migration 544 now revokes stale `CREATE` on `public` from the deterministic
summary source login and fails closed if that privilege remains. The disposable
PostgreSQL 16 chain through migration 548 passes 37 grouped assertions on native
AMD64 and ARM64/QEMU (`aarch64`), including a synthetic pre-existing grant.
Migration tests pass (36); candidate and legacy databases remain untouched.
This does not complete broader agent credential, populated-parity, or
MAN-CAP-038 acceptance
([migration](../schemas/postgres/544_tenant_scoped_deterministic_summary_source_views.sql);
[native evidence](builds/2026-10-22-recovery/cap-038-deterministic-login-schema-create-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-deterministic-login-schema-create-arm64-disposable.json)).

**CAP-038 NOLOGIN reader schema ACL cleanup — 22 October 2026:** migrations
541 and 542 now revoke stale `public CREATE` from the synthesis and
deterministic-summary reader roles before validating their allowlists. Synthetic
pre-existing grants are removed during replay; the focused PostgreSQL 16 chain
through migration 548 passes 38 grouped assertions on native AMD64 and
ARM64/QEMU (`aarch64`). `tests/test_migration.py` passes 36 tests. Candidate and
legacy databases remain untouched. This does not establish the deployed worker
credential boundary or MAN-CAP-038 acceptance
([native evidence](builds/2026-10-22-recovery/cap-038-reader-schema-create-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-reader-schema-create-arm64-disposable.json)).

**CAP-038 synthesis execution fallback — 22 October 2026:** generic shared
synthesis no longer has a shared-runtime database path. All ten registered
classes require a signed source-view contract and exact location; read-only
and draft runs delegate to the registered worker. The unused `run_fetch()`
helper and the unused `store_summary(conn, ...)` compatibility writer both fail
closed before opening or using a shared caller connection. The focused
agent/source/worker selection passes 125 tests with Ruff and compilation. This
closes only the generic fallback and legacy writer; MAN-CAP-038 and credential,
populated-parity, operator-attribution, and non-synthesis gates remain open.

**CAP-038 Delphi CLI read boundary — 22 October 2026:** the legacy
`services.delphi.cli live-summary` and `consensus` commands now require an
explicit location UUID and call the consent-aware signed source adapter rather
than the shared runtime connection. The unscoped `list-studies` command exits
before database access; the authenticated location-scoped Gateway remains the
inventory path. The focused Delphi, worker, preflight, and unified CLI selection
passes 173 tests ([summary evidence](builds/2026-10-22-recovery/cap-038-delphi-cli-summary-boundary.json);
[study-list evidence](builds/2026-10-22-recovery/cap-038-delphi-study-list-cli-boundary.json)).
Panel operations, stopping evaluation, deployment credentials/grants, and
MAN-CAP-038 acceptance remain open; the capability is not marked accepted.

**ARM64/QEMU runtime refresh — 18 October 2026:** the current-source ARM64 app
and PostgreSQL/PostGIS images were exercised through migration 434 on an
internal-only, resource-capped disposable stack. All 425 ordered schema
migrations passed; health and anonymous protected-route checks returned 200
and 401. The wrapper returned a false negative by misreading the null host-port
binding and comparing changing uptime text; captured runtime values confirmed
no published port and unchanged candidate containers. This updates software
compatibility evidence only. No physical Raspberry Pi, performance,
power-loss, provider, or MAN-CAP acceptance is claimed
([evidence](builds/2026-10-18-recovery/arm64-qemu-current-schema-434.json)).

**CAP-038 source-reader ARM64/QEMU check — 22 October 2026:** the disposable
PostgreSQL 16 migration chain through 541 passed 29 grouped assertions in a
network-disabled ARM64 PostGIS image under emulation (`aarch64`). This is a
focused database-slice compatibility check, not physical Raspberry Pi,
full-schema, power-loss, or performance acceptance
([evidence](builds/2026-10-22-recovery/cap-038-agent-synthesis-source-reader-arm64-disposable.json)).

**CAP-038 deterministic-summary reader — 22 October 2026:** migration 542
isolates the built-in AI-summary source queries behind a read-only identity
with a 13-relation allowlist. Its 31-check disposable PostgreSQL apply/replay
also passes in ARM64/QEMU emulation. Location filters remain application-side;
this does not establish tenant RLS or physical Raspberry Pi acceptance
([native evidence](builds/2026-10-22-recovery/cap-038-deterministic-summary-source-reader-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-deterministic-summary-source-reader-arm64-disposable.json)).

**CAP-038 signed shared-synthesis source scope — 22 October 2026:** migration
543 replaces the synthesis reader's raw-view grants with 40 signed,
location-filtered security-barrier wrappers. Native disposable PostgreSQL 16
applies and replays migrations 529–543 with 31 grouped assertions, including
exact, shared, and network scope plus denial of ungranted locations and direct
raw-view access. The 189-test focused selection, Ruff, and compilation pass.
This closes a database boundary for the ten shared synthesis agents only;
deterministic summary and other worker paths, credential/grant rollout, and
MAN-CAP-038 owner acceptance remain open. No candidate or legacy database was
changed ([evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-agent-synthesis-source-views-disposable.json)).

**CAP-038 deterministic-summary tenant scope — 22 October 2026:** migration
544 extends signed database scope to all 13 relations used by the four built-in
summary types. Eleven operational sources are filtered to the exact granted
location; shared crop and expense-category catalogs require a valid signed
location context. The source login can call only the bounded context setter and
cannot read the raw public relations; its NOLOGIN reader role receives the 13
security-barrier wrappers only. Native PostgreSQL 16 applies and replays
migrations 529–544 with 31 grouped assertions, including no-context and
ungranted-location denial, raw-relation denial, write denial, and stale-grant
cleanup; the same chain passes in ARM64/QEMU emulation (`aarch64`). The focused
worker/context/profile/source selection passes 134 tests; the broader CAP-038
worker/context regression set passes 190. Ruff and Python compilation pass.
This is software-emulation evidence, not physical Raspberry Pi acceptance.
Candidate and legacy databases remain
untouched; migration 544, its worker credential and location grants are not
deployed. Other agent and worker paths, universal RLS, populated parity, and
MAN-CAP-038 acceptance remain open ([migration](../schemas/postgres/544_tenant_scoped_deterministic_summary_source_views.sql);
[worker](../services/agents/worker_cli.py);
[native evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-deterministic-summary-source-views-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-deterministic-summary-source-views-arm64-disposable.json)).

**CAP-038 feedback source boundary — 22 October 2026:** shared wellbeing and
feedback synthesis now read only the registered consent-safe public views.
Language and feedback aggregates are derived from those view rows; private
feedback totals and harm counts are explicitly unavailable to the worker. This
is source-code and focused-test evidence, not tenant RLS or populated-output
parity.

**CAP-038 synthesis query allowlist — 22 October 2026:** an offline fake-cursor
regression executes each of the ten shared synthesis entry points and checks
that every `FROM`/`JOIN` relation belongs to that agent's registered public-view
map. It also checks exact-location binds, the explicit inclusion of unassigned
rows for mixed-scope views, and unfiltered network catalogs. A companion
assertion requires the combined registered maps to match migration 541's
explicit SELECT grants exactly. This protects the relation-level reader
boundary and application query shape; it does not prove populated data parity
or tenant RLS.

**CAP-038 synthesis location preflight — 22 October 2026:** all ten shared
synthesis task contracts and CLIs require a location UUID, the shared runner
rejects a missing location before opening a connection, and direct synthesis
functions reject missing or malformed UUIDs before cursor access. Network
reference views remain available inside a location-scoped summary. This closes
accidental all-farm reads, but caller-to-location authorization and database
tenant isolation remain open.

The default Kernel image from commit `9e02eeff` also builds for `linux/arm64`;
QEMU imported the isolated RPC worker and constructed a synthetic snapshot with
networking disabled. This adds image and worker-import evidence only; no
ARM64 database/app stack or migration-436 replay was performed in that smoke
([evidence](builds/2026-10-18-recovery/arm64-rpc-worker-image-smoke.json)).

**Protocol-catalog SDK note — 18 October 2026:** Python and TypeScript now
represent the canonical `protocol` catalog fields and metadata. This data type
does not query providers, sign transactions, or submit on-chain actions; MAN-CAP
classifications and acceptance remain unchanged ([evidence](builds/2026-10-18-recovery/sdk-protocol-parity.json)).

**EAS schema-catalog SDK note — 18 October 2026:** the clients now preserve
stored attestation schema UIDs, definitions, resolver addresses, version, and
active state. This does not create schemas or produce attestations, and MAN-CAP
acceptance remains unchanged ([evidence](builds/2026-10-18-recovery/sdk-attestation-schema-parity.json)).

**SDK query-operator parity note — 18 October 2026:** Python and JavaScript
specialized collection methods now produce the same explicit Directus `_eq` and
`_in` filter expressions while preserving caller options. These client-side
filters are not an authorization boundary; MAN-CAP status is unchanged
([evidence](builds/2026-10-18-recovery/sdk-filter-operator-parity.json)).

**SDK session parity note — 18 October 2026:** local JavaScript credentials are
cleared even when the remote logout request fails, matching Python's
best-effort behavior. This does not affect Gateway session authorization or
MAN-CAP status ([evidence](builds/2026-10-18-recovery/sdk-session-logout-parity.json)).

**SDK export projection parity note — 18 October 2026:** both clients now accept
an optional field projection when reading an export record and forward it to
the Directus item read. This does not change server permissions, tenant scope,
or MAN-CAP status ([evidence](builds/2026-10-18-recovery/sdk-export-field-projection-parity.json)).

**SDK login-response parity note — 18 October 2026:** TypeScript now preserves
the Directus access/refresh token and expiry fields while retaining its prior
`token` and `refreshToken` aliases. Synthetic offline checks pass; this does
not change Gateway sessions or MAN-CAP status ([evidence](builds/2026-10-18-recovery/sdk-login-response-parity.json)).

**SDK aggregate-query parity note — 18 October 2026:** TypeScript exposes the
generic Directus aggregation command, and Python now uses the same collection
route and top-level array encoding. Fake-fetch acceptance confirms the pinned
TypeScript command requests `/items/{collection}` with nested aggregate JSON and
comma-separated groupBy values. This does not establish authorization, tenant
scope, or MAN-CAP acceptance ([wire evidence](builds/2026-10-18-recovery/sdk-aggregate-query-wire-parity.json); [client feature](builds/2026-10-18-recovery/sdk-generic-aggregate-parity.json)).

**SDK list-query option parity note — 18 October 2026:** TypeScript now forwards
additional Directus list-query parameters like Python's generic list helper,
while retaining explicit pagination precedence. The pinned SDK's real REST
transport is exercised with a stubbed fetch, including nested aggregate/deep
serialization. Caller-supplied query options do not establish authorization or
tenant scope; MAN-CAP acceptance is unchanged
([evidence](builds/2026-10-18-recovery/sdk-list-query-parameter-parity.json)).

**SDK generic CRUD contract note — 18 October 2026:** offline tests now check
Python Directus item URLs, body/query fields and data-envelope unwrapping against
the matching TypeScript SDK commands for detail reads, single/bulk creates,
updates, and deletes. These request-shape checks do not establish live API,
authorization, tenant scope, or MAN-CAP acceptance
([evidence](builds/2026-10-18-recovery/sdk-generic-crud-contract.json)).

**Python SDK error handling note — 18 October 2026:** known Directus HTTP
statuses map to stable exception classes, and malformed response envelopes
fall back to response text or the HTTP status. Synthetic checks do not
establish live API error behavior, authorization, tenant scope, or MAN-CAP
acceptance ([evidence](builds/2026-10-18-recovery/sdk-python-error-envelope-parity.json)).

**Cross-language SDK error parity note — 18 October 2026:** TypeScript now
normalizes the pinned Directus SDK's HTTP error envelopes into the same named
exception classes as Python, retains HTTP status and response context, and
leaves response-less network errors native. Stubbed transport checks verify the
real SDK 403 path; this does not establish live API behavior, authorization,
tenant scope, or MAN-CAP acceptance
([evidence](builds/2026-10-18-recovery/sdk-error-normalization-parity.json)).

**SDK export creation signature note — 18 October 2026:** TypeScript accepts the
existing request object, export type plus options, and the positional field
order supported by Python. These forms create the same pending export payload;
permissions, tenant scope, and MAN-CAP status are unchanged ([evidence](builds/2026-10-18-recovery/sdk-export-create-signature-parity.json)).

The six-column matrix is checked by `python3 scripts/check-capability-matrix.py`
and the fast-fail CI workflow. This verifies all 66 IDs, row shape, named manual
checks, status labels, and referenced source/test paths. It does not evaluate
capability behavior or mark any MAN-CAP check accepted.

**Infrastructure-asset SDK note — 18 October 2026:** clients now represent
stored equipment inventory and its constrained lifecycle status. Condition
labels remain free-form as in SQL. Python and TypeScript now also expose
location-scoped, read-only access to stored assets; the SDK does not assess
condition or certify infrastructure ([model evidence](builds/2026-10-18-recovery/sdk-infrastructure-asset-parity.json); [read-method evidence](builds/2026-10-18-recovery/sdk-infrastructure-asset-read-methods.json)).

**Reference-catalog SDK reads — 18 October 2026:** Python and JavaScript now
offer typed, read-only list/detail access to stored crops, protocols, sensor
types, and attestation schemas. The methods do not mutate catalogs, submit
transactions, or establish authorization; MAN-CAP status is unchanged
([evidence](builds/2026-10-18-recovery/sdk-reference-catalog-read-methods.json)).

**Cash-flow SDK contract note — 18 October 2026:** Python and TypeScript expose
stored period summaries and input provenance. The SDK does not calculate,
reconcile, or verify the figures and changes no MAN-CAP classification
([evidence](builds/2026-10-18-recovery/sdk-cash-flow-snapshot-parity.json)).

**Crop SDK contract note — 18 October 2026:** Python and TypeScript expose the
canonical crop reference row and migration-added schema version. Expected-yield
fields are stored values only; this does not calculate or verify a yield and
changes no MAN-CAP classification ([evidence](builds/2026-10-18-recovery/sdk-crop-parity.json)).

**Farm-activity SDK contract note — 18 October 2026:** Python and TypeScript
now model the stored `farm_activity` record and schema-added fields. This
source contract does not establish write, lifecycle, Directus, or tenant
parity and changes no MAN-CAP classification ([evidence](builds/2026-10-18-recovery/sdk-farm-activity-parity.json)).

**Farm-task SDK contract note — 18 October 2026:** Python and TypeScript also
model stored `farm_task` data with SQL-constrained category, priority, and
status. It does not implement task assignment, scheduling, completion, or
dependency operations and changes no MAN-CAP classification ([evidence](builds/2026-10-18-recovery/sdk-farm-task-parity.json)).

**Farm-task SDK reads — 18 October 2026:** Python and JavaScript provide typed,
read-only location-scoped list/detail access to stored farm task plans. The
location filter is a client query convenience and does not establish
authorization; these methods do not assign, schedule, or complete work. MAN-CAP
acceptance remains unchanged ([evidence](builds/2026-10-18-recovery/sdk-farm-task-read-methods.json)).

**Farm-task relationship SDK note — 18 October 2026:** clients now preserve
dependency, framework-step, and weekly-plan associations with their source
identity fields. They do not evaluate or execute these workflows; MAN-CAP
acceptance remains unchanged ([evidence](builds/2026-10-18-recovery/sdk-farm-task-relations-parity.json)).


**SDK schema implementation note — 18 October 2026:** Python and TypeScript
now expose stored `price_observation` records and the SQL-constrained oracle
aggregation method. The source guard covers 57 models and 1,237 canonical
columns; focused evidence is in
[the SDK parity record](builds/2026-10-18-recovery/sdk-price-observation-parity.json).
This implementation note does not change the matrix classifications or mark
any MAN-CAP acceptance check accepted.


**Oracle SDK schema note — 18 October 2026:** The native Python and TypeScript
SDKs now expose `oracle_price_log` records with saved feed and attestation
references. This remains data-model parity only; it does not query providers or
submit attestations. See [the parity record](builds/2026-10-18-recovery/sdk-oracle-price-log-parity.json).


**Actuation SDK schema note — 18 October 2026:** the typed record preserves
command and approval history while providing no command execution API. The
schema guard also now includes qualified additive migrations for MRV and sensor
alert records. These are SDK source checks only and do not accept MAN-CAP-040.
See [the parity record](builds/2026-10-18-recovery/sdk-actuation-log-parity.json).


**Anomaly receipt SDK note — 18 October 2026:** clients now represent the
durable per-reading/rule outcome receipt as data, including its location scope.
This does not run detection or change MAN-CAP-040 acceptance. See [the parity
record](builds/2026-10-18-recovery/sdk-sensor-anomaly-effect-parity.json).

**CAP-040 / CAP-047 sensor-anomaly SQL operation boundary — 23 October 2026:** the anomaly worker's database helpers now take literal operation names from an immutable twelve-entry map of fixed SQL instead of accepting SQL strings from their callers. An AST check ensures every use is a registered literal; an unknown operation fails before opening a cursor. The focused anomaly, worker inventory, function reachability, and boundary preflight selection passes 62 tests; Ruff, compilation, and generated inventory checks pass. The generic SQL scanner still reports the helper's local execute argument as unknown because it does not resolve the operation map; the explicit map and source regression cover that limitation. No database/provider or candidate/legacy service was used. This improves the worker boundary but does not accept MAN-CAP-040/047 ([implementation](../services/ingestion/sensor_anomaly_worker.py); [evidence](builds/2026-10-23-recovery/worker-anomaly-named-sql-operations.json)). Checklist: 1,023 complete / 24 open (1,047 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted.


**SDK method inventory note — 18 October 2026:** the offline cross-language
regression now checks method names, inherited generic methods, and argument
requiredness/optionality, including TypeScript overloads. Parameter types and
runtime behavior are not compared; no API, tenant, or transport MAN-CAP gate is
accepted ([signature evidence](builds/2026-10-18-recovery/sdk-method-signature-parity.json);
[method evidence](builds/2026-10-18-recovery/sdk-method-inventory-parity.json)).

The repository owner authorized ongoing focused test execution. Current
owner-only decisions and external acceptance inputs are listed in [Open Follow
Ups](open-follow-ups.md). Passing source tests do not close the named manual
acceptance rows.

**17 October 2026 scheduled sensor boundaries (CAP-040 / CAP-047):** scheduled pulls compare persisted driver metadata with an immutable source-controlled allowlist before importing code. The built-in CSV driver's scheduled fetch is additionally confined beneath `/var/lib/kokonut/sensor-inputs` in Compose, mounted read-only from `KOKONUT_SENSOR_CSV_HOST_DIR`; traversal, outside-root paths, symlinked components, and non-regular files are rejected. The manual CSV CLI remains unchanged. The combined focused sensor schedule/CLI/command-contract/worker-map suite passes 179 tests, along with Ruff, compilation, and three Compose profile config checks. Synthetic temporary files were used; no live configured sensor source, database, provider, or schedule was accessed. Signed worker identity, bounded database functions, tenant authorization/RLS, live input parity, and MAN-CAP-040/047 remain open ([contract](sensor-driver-scheduled-contract.md); [implementation](../services/ingestion/drivers/sensor_csv.py); [tests](../tests/test_sensor_driver_schedule.py); [allowlist evidence](builds/2026-10-17-recovery/scheduled-sensor-driver-code-allowlist.json); [path evidence](builds/2026-10-17-recovery/scheduled-sensor-csv-path-confinement.json)).

**17 October 2026 driver failure redaction (CAP-040 / CAP-047):** registry
health results and import/lifecycle logs, plus `BaseDriver.run` logs, now
omit raw exception messages while preserving false health status, rollback,
failure continuation, and exception propagation. Thirty driver-registry tests,
Ruff, compilation, and the local full-history Gitleaks scan pass using mocked
failures only. This does not establish live provider health or data parity
([evidence](builds/2026-10-17-recovery/driver-error-redaction.json)).

**17 October 2026 scheduler failure-output containment (CAP-047):** task-run
failures no longer persist child stdout/stderr or raw process-launch exception
text; exit codes, failed status, normal retry policy, immediate launch retry,
and lease checks remain. Twelve mocked scheduler durability/worker tests pass
with Ruff and compilation. This does not replace live worker outage and
long-duration recovery acceptance
([evidence](builds/2026-10-17-recovery/scheduler-failure-output-redaction.json)).

**17 October 2026 KGP worker error containment (CAP-042 / CAP-047):** KGP
cursor failure records and worker rollback/lease/reconnect/close logs omit raw
RPC and database exception details. Four mocked durability tests pass with
Ruff and compilation; lease recovery remains covered and unchanged. No live
chain or database recovery, reorganization acceptance, or MAN-CAP-042 closure
is claimed ([evidence](builds/2026-10-17-recovery/kgp-worker-error-redaction.json)).

**17 October 2026 migration and MQTT failure-output containment (CAP-040 / CAP-047):** the ordered migration runner no longer copies raw PostgreSQL stdout/stderr or subprocess timeout details into its CLI error; MQTT TLS startup reports only the exception class and continues to fail closed. The migration module passes 32 tests, and the focused MQTT/IoT/outbox suites pass 75 checks with Ruff and compilation. Checks used mocked subprocess and TLS failures; no database, broker, or provider was contacted. Live migration rollback and MQTT certificate/broker acceptance remain open; MAN-CAP-040/047 are not accepted ([migration evidence](builds/2026-10-17-recovery/migration-cli-error-redaction.json); [MQTT evidence](builds/2026-10-17-recovery/mqtt-subscriber-error-redaction.json)).

The migration status parser also replaces malformed database-returned tracking
rows with a fixed diagnostic, preventing unexpected contents from reaching the
CLI error log. The migration module passes 42 tests with Ruff and compilation;
the regression uses a synthetic query result only. No capability acceptance
status changes
([evidence](builds/2026-10-17-recovery/migration-tracking-output-redaction.json)).

**17 October 2026 projection failure containment (CAP-021 / CAP-047):** failed
synchronized graph rebuilds persist a class-only error after rolling back
partial projection writes, while continuing to raise the original exception to
the caller. Thirteen mocked graph-projection checks pass with Ruff and
compilation. No live projection or database parity is implied; MAN-CAP-021
remains unaccepted ([evidence](builds/2026-10-17-recovery/graph-projection-error-redaction.json)).

**17 October 2026 advisory action and revenue analysis containment (CAP-010 / CAP-056):** approved decision-adapter failures return class-only summaries while retaining rollback and cursor cleanup; Revenue Multiplier analyzer failures omit raw diagnostics while retaining other dimension results and connection cleanup. The 21-test decision-policy suite and one mocked Revenue Multiplier regression pass with Ruff and compilation. No live action, provider, or database was used; named MAN-CAP checks remain open ([decision evidence](builds/2026-10-17-recovery/decision-policy-error-redaction.json); [analysis evidence](builds/2026-10-17-recovery/revenue-multiplier-error-redaction.json)).

**17 October 2026 climate provider persistence contract (CAP-040 / CAP-047):**
climate location lookup now uses the canonical `location.center` point with the
stored latitude/longitude fallback. MODIS, SMAP, Sentinel-1, and ERA5-Land now
write columns present in the canonical schema; provider identifiers and band
units are normalized, MODIS scaling and ERA5 precipitation accumulation are
applied, and SMAP uses the current collection/band. The four location-level
summary writes use migration 428's guarded `(location_id, target_date, source)`
partial keys, preserving independent plot-level records. Ingestion audit rows
share the same transaction, provider failures return nonzero, and the batch
reports failed sources explicitly. Twenty-five focused climate checks, Ruff,
Python compilation, and four disposable PostgreSQL 16 migration/replay,
duplicate-rejection, retry-upsert, and plot-row checks pass. No real provider,
candidate, legacy database, or schedule was used. The scheduled path now uses
the default-off signed climate worker; its 156-test focused suite and nine
disposable forced-RLS checks pass. Credentials, location grants, live source
parity, candidate rollout, and MAN-CAP acceptance remain open
([migration](../../schemas/postgres/428_climate_summary_idempotency.sql);
[runner](../../scripts/check-climate-summary-idempotency-disposable.py);
[evidence](builds/2026-10-17-recovery/climate-summary-idempotency-disposable.json);
[official band references](builds/2026-10-17-recovery/climate-provider-contract.json); [worker evidence](builds/2026-10-17-recovery/climate-worker-disposable.json)).

**17 October 2026 remote-sensing worker boundary (CAP-040 / CAP-047):** native
scheduled remote-sensing jobs now route through a default-off dedicated worker.
GEE and Copernicus fetching is separated from database persistence; migration
432 gives the worker a signed `remote_sensing/run` location grant and bounded
claim plus atomic attempt, observation, ingestion-audit, ClickHouse-outbox, and
job-state functions. The 238-test focused provider/worker/scheduler suite, Ruff,
Python compilation, refreshed inventories, and disposable PostgreSQL 16/PostGIS
migration-replay and forced-RLS acceptance pass. Acceptance covers location
denial, fallback, canopy-field persistence, duplicate replay, rollback,
projection/audit atomicity, direct-table denial, and context cleanup. No live
provider, credential, schedule, candidate, or legacy database was used; the
runtime-role bootstrap now supports this distinct login after migration 432.
No password or active grant is provisioned. The 22-check no-egress PostgreSQL
role acceptance verifies bootstrap, application-table denial, SET-only
execution, and unscoped-claim rejection
([runtime-role evidence](builds/2026-10-17-recovery/runtime-remote-sensing-role-disposable.json)).
The candidate is applied through migration 432; the feature stays off, and live
data parity and MAN-CAP-040/047 remain open
([worker](../../services/ingestion/remote_sensing_worker.py);
[migration](../../schemas/postgres/432_signed_remote_sensing_worker.sql);
[tests](../../tests/test_remote_sensing_worker.py);
[disposable runner](../../scripts/check-remote-sensing-worker-disposable.py);
[evidence](builds/2026-10-17-recovery/signed-remote-sensing-worker-disposable.json)).

**17 October 2026 remote-sensing error containment (CAP-040 / CAP-047):** both
the signed worker and legacy job runner now persist fixed outcome summaries or
exception-class names instead of provider response/exception text. GEE,
Copernicus, and connection-free ClickHouse adapter logs also omit raw exception
details. The 74-test mocked worker/scheduler/automation suite and Ruff pass; no
provider or database was contacted. Legacy ClickHouse outbox errors preserve rollback
and error type while using a fixed summary. Live provider parity and MAN-CAP acceptance
remain open ([evidence](builds/2026-10-17-recovery/remote-sensing-error-sanitization.json)).

**17 October 2026 EAS error containment (CAP-040 / CAP-047):** legacy and
isolated EAS indexing now redact provider exception text from chain status,
ingestion audit, logs, and scheduler-facing errors. Fixed persistence summaries
hide database exception details; outbox errors remain typed and preserve
rollback. The 184-test focused EAS/provider/scheduler/operation-map suite and
Ruff pass without live provider or database access. Live pagination, recovery,
and MAN-CAP acceptance remain open
([evidence](builds/2026-10-17-recovery/eas-error-sanitization.json)).

**17 October 2026 ClickHouse outbox error containment (CAP-040 / CAP-047):**
enqueue errors remain typed and transactional while hiding raw database causes;
delivery failures now persist a bounded class-only summary and logs omit
provider response/exception text. The 101-test outbox and producer suite plus
Ruff pass without database or ClickHouse access. Live delivery recovery and
MAN-CAP acceptance remain open
([evidence](builds/2026-10-17-recovery/clickhouse-outbox-error-sanitization.json)).
The RPC wallet indexer now applies the same bounded failure reporting to
provider and outbox errors without changing transactional recovery; six focused
mocked tests and Ruff pass
([evidence](builds/2026-10-17-recovery/rpc-indexer-error-sanitization.json)).
The legacy subgraph caller also redacts provider failures from durable status,
audit, and logs; its three mocked failure-path checks and Ruff pass without
external access ([evidence](builds/2026-10-17-recovery/subgraph-indexer-error-sanitization.json)).

**16 October 2026 RPC wallet transaction integrity (CAP-040 / CAP-047):**
wallet activity, chain status, and ClickHouse outbox intent now share one
transaction, with per-wallet savepoints and explicit partial-failure status.
Focused mocked recovery/contract/outbox/scheduler checks pass 133 tests. This
does not prove transaction-history coverage, confirmation depth, reorg recovery,
provider parity, or live runtime behavior; related MAN-CAP checks remain
unaccepted ([evidence](builds/2026-10-16-recovery/rpc-indexer-atomicity.json);
[operation map](worker-operation-map.json)).

**16 October 2026 explicit EAS/RPC scheduler chain scope (CAP-047):** native
EAS and RPC job dispatch and disabled schedule planning now require exactly one
supported chain. Optional Prefect adapters preserve all three EAS chains in
Celo-first order and all seven RPC CLI-supported networks as separate runs;
direct interactive indexers retain their multi-chain behavior. The RPC
indexer also closes its database connection on empty-chain and lookup-error
paths. The focused dispatcher, command-contract, RPC cleanup, and flow suites
pass 156 tests with subprocesses mocked. No chain endpoint, database, persisted
schedule, or Prefect deployment was used. This is a source-level scheduler
contract; MAN-CAP-018 and MAN-CAP-047 remain unaccepted
([EAS evidence](builds/2026-10-16-recovery/eas-chain-scoped-job-contract.json);
[RPC evidence](builds/2026-10-16-recovery/rpc-chain-scoped-job-contract.json)).

**16 October 2026 EAS recipient cursor recovery (CAP-040 / CAP-047):**
migration 421 adds an independent timestamp cursor per supported chain and
tracked recipient. Migration 422 then resets inherited cursors to zero because
the old chain-wide maximum may be ahead of a slower recipient; UID conflict
handling makes that one-time history rescan idempotent. New recipients also
start at zero. The scan revisits the saved timestamp second on each run, so a
newly indexed same-second attestation is not skipped; UID conflict handling
suppresses repeats. Each recipient's canonical attestations, ClickHouse outbox
intents, and cursor advancement commit together; failed recipient pages roll
back to a savepoint and make the run retryable, while outbox failure rolls back
the whole transaction. The focused EAS, producer, scheduler, and migration
suite passes 188 tests. A disposable PostgreSQL 16 check verifies both
migrations' replay, the unsafe legacy watermark followed by the zero
rebaseline, independent cursor movement, and rollback coupling. Earlier-time
late arrivals and concurrent offset-page shifts still need provider/runtime
reconciliation; migrations 421–422 are applied on the candidate, but named
MAN-CAP acceptance is not claimed
([migration](../../schemas/postgres/421_eas_recipient_cursors.sql);
[rebaseline](../../schemas/postgres/422_eas_cursor_rebaseline.sql);
[tests](../../tests/test_eas_indexer_recovery.py);
[disposable evidence](builds/2026-10-16-recovery/eas-recipient-cursor-disposable.json)).

**17 October 2026 isolated EAS scheduled worker (CAP-040 / CAP-047):** native
Kernel EAS work now has a default-off worker identity and bounded migration 433
functions. The dedicated login has no direct application-table privileges;
forced-RLS disposable PostgreSQL 16 checks pass for recipient lookup, cursor
advance, attestation plus outbox atomicity, replay suppression, status audit,
and migration replay. Migration 433 is applied on the local candidate after an
age-encrypted checkpoint was restore-rehearsed; both EAS roles remain `NOLOGIN`,
and no worker credential, endpoint, or persisted schedule was enabled or used.
The database-independent adapter now rejects GraphQL errors and malformed or
partial responses instead of treating them as empty pages. The worker also
validates newest-first page ordering and stops after it crosses below the saved
timestamp cursor, while retaining the inclusive cursor second; 22 mocked
provider, worker, and cursor checks pass. This bounds repeated history reads but
does not resolve concurrent offset-pagination movement, earlier-than-cursor
arrivals, or live provider acceptance. The worker also rejects missing, null,
boolean, negative, fractional, malformed, and out-of-range timestamps before page persistence
or cursor advancement. Seven fail-closed cases and the combined 36-test EAS
provider/worker/cursor suite pass. An explicit `--replay-lookback-seconds`
option reprocesses an operator-selected interval below the saved cursor with
idempotent writes and monotonic cursor retention; zero remains the default.
Six replay/argument/output checks pass, and successful worker results report
the selected interval. This does not automatically recover late
arrivals beyond the chosen interval or resolve concurrent offset-page movement.
The worker rejects duplicate attestation IDs within an in-scope page and
overlap with the previous full `skip` page, including a shorter terminal page.
It retains only the preceding page's IDs, stops before persisting an
overlapping page, and leaves the cursor unchanged; earlier page writes remain
safe for idempotent retry. The 39-test mocked EAS provider/worker/cursor suite
passes. This catches adjacent overlap but does not establish stable provider
snapshots or detect gaps without overlap, non-adjacent cycles, or late arrivals
([evidence](builds/2026-10-17-recovery/eas-offset-overlap-guard.json)).
The 130-test scheduled-command contract suite confirms automated EAS tasks
remain limited to a single explicit chain and cannot pass the replay option.
No live endpoint or database was contacted
([timestamp evidence](builds/2026-10-17-recovery/eas-timestamp-contract.json);
[replay evidence](builds/2026-10-17-recovery/eas-explicit-replay-lookback.json)).
Prefect intentionally stays on the legacy entrypoint until feature and
credential provisioning. Existing task reconciliation, provider parity, and
live runtime acceptance remain open ([worker](../../services/ingestion/eas_worker.py);
[migration](../../schemas/postgres/433_isolated_eas_indexer.sql);
[disposable runner](../../scripts/check-eas-indexer-worker-disposable.py);
[evidence](builds/2026-10-17-recovery/eas-indexer-worker-disposable.json)).

**17 October 2026 isolated-worker import boundary (CAP-040 / CAP-047):** all
eight allowlisted scheduled workers now import their CLI help path with shared
PostgreSQL credentials removed. The internal child marker bypasses shared
dotenv loading and production shared-DB validation; the canonical shared
connection factory rejects use before connecting. EventBus handlers preserve
the shared-identity compatibility path while their isolated feature flag is
off, and receive the dedicated identity only when enabled. The focused suite
passes 130 checks with Ruff and compilation; subprocesses use synthetic
credentials and do not contact a database or provider. This is import and
credential-boundary evidence only; worker authorization, configured grants,
provider parity, and named MAN-CAP acceptance remain open
([evidence](builds/2026-10-17-recovery/isolated-worker-import-boundary.json)).

**16 October 2026 market-data provider recovery (CAP-040 / CAP-047):** World
Bank download and unusable-response errors now fail before PostgreSQL opens;
reference seed rows have a separate source key, and price rows plus their
ingestion audit commit atomically. The audit reports actual inserts even when
natural-key conflicts are ignored. Sixteen focused mocked checks, Ruff, and
compilation pass. No live provider, database, or schedule was used; historical
correction semantics and live parity remain open ([tests](../../tests/test_market_data_recovery.py);
[evidence](builds/2026-10-16-recovery/market-data-provider-atomicity.json)).

**16 October 2026 Gnosis indexer checkpoint and replay guard (CAP-023 / CAP-047):**
each Gnosis block range commits indexed events, outbox intents, and its status
checkpoint together; failures roll back and preserve the last committed block.
Migration 423 adds transaction-hash/log-index receipts for newly processed
events, skips identical replay, and fails closed on a reused identity with
changed block hash, number, or event type. The 165-test Gnosis/outbox/command/
migration suite, Ruff, compilation, and disposable PostgreSQL 16 apply/replay,
duplicate, mismatch, and rollback checks pass. Migration 424 moves the Moloch
indexer to its own `gnosis_moloch` cursor, seeded from the last shared boundary
as paused with provenance while preserving `(gnosis, rpc)` for wallet activity.
The indexer requires an explicit `--from-block` to accept this inherited cursor
and records review in the first successful transaction. A network-disabled
disposable PostgreSQL 16 check confirms migration apply/replay and that neither
cursor is overwritten. Legacy events are not
backfilled; removed-log/deep reorg rollback remains unresolved. Migrations
423–424 are applied on the candidate, but no provider or schedule was exercised ([receipt migration](../../schemas/postgres/423_gnosis_event_log_receipts.sql);
[cursor migration](../../schemas/postgres/424_gnosis_indexer_cursor_namespace.sql);
[tests](../../tests/test_gnosis_indexer_recovery.py);
[receipt evidence](builds/2026-10-16-recovery/gnosis-event-receipts-disposable.json);
[cursor evidence](builds/2026-10-16-recovery/gnosis-indexer-cursor-disposable.json)).

**17 October 2026 Gnosis error containment (CAP-023 / CAP-047):** RPC and
ClickHouse outbox exception details are no longer persisted in the indexer
status or returned through scheduler errors; fixed summaries preserve the
failure category without logging endpoint URLs or secret-bearing provider
text. The 13-test mocked Gnosis recovery suite passes. No provider or database
was contacted. Reorg receipt reconciliation, live provider acceptance, and
MAN-CAP-023/047 remain open
([evidence](builds/2026-10-17-recovery/gnosis-error-sanitization.json)).

**17 October 2026 Baal event-query recovery (CAP-023):** a failed provider
query now aborts its current block batch instead of skipping the failed event
type and advancing the cursor. Failure status preserves the last committed
block, including after protocol-lookup and event-persistence failures; provider
and database details are reduced to safe summaries. Four mocked recovery tests
and Ruff pass. No provider or database was contacted; historical receipt
completeness, reorg recovery, live provider parity, and MAN-CAP-023 remain open
([evidence](builds/2026-10-17-recovery/baal-indexer-error-recovery.json)).

**16 October 2026 forecast projection atomicity (CAP-040 / CAP-047):** the
weather-forecast producer now rolls back a whole location batch to a PostgreSQL
savepoint on any row failure, records ingestion audit state in the same
transaction, queues ClickHouse rows only after successful PostgreSQL
persistence, and aborts/cleans up the transaction when durable outbox enqueue
fails. Six mocked regressions and existing forecast/scope/shared-producer tests
pass 36 tests. Live provider/database acceptance and MAN-CAP-040/047 remain open
([evidence](builds/2026-10-16-recovery/weather-forecast-atomic-projection.json)).

**17 October 2026 legacy weather error containment (CAP-040 / CAP-047):**
current-weather and forecast runners now persist only bounded exception-class
summaries for per-location failures, and their direct ClickHouse fallback logs
omit raw exception details. Four new mocked regressions pass within the
26-test weather scope and atomicity suite with Ruff. No provider, database, or
ClickHouse endpoint was contacted; live recovery and MAN-CAP-040/047 remain
open ([evidence](builds/2026-10-17-recovery/weather-legacy-error-redaction.json)).

**17 October 2026 GEE climate error containment (CAP-040 / CAP-047):**
credentialed/default initialization and MODIS, SMAP, Sentinel-1, and ERA5
failures now expose only bounded summaries; failed fetches retain transaction
rollback. Six new mocked regressions pass within the 44-test climate suite with
Ruff. No Earth Engine endpoint or database was accessed; live source and
MAN-CAP-040/047 acceptance remain open
([evidence](builds/2026-10-17-recovery/gee-climate-error-redaction.json)).

**17 October 2026 MQTT sensor error containment (CAP-040 / CAP-047):** MQTT
callback and direct ClickHouse fallback logs omit raw exception details; QoS 1
failures retain the unacknowledged broker-retry behavior and raise only a
bounded summary. Three new mocked checks pass within the 74-test MQTT/producer
suite with Ruff. No broker, database, or ClickHouse service was contacted;
live delivery and MAN-CAP-040/047 remain open
([evidence](builds/2026-10-17-recovery/mqtt-subscriber-error-redaction.json)).

**17 October 2026 HTTP sensor error containment (CAP-040 / CAP-047):** device
credential and reading-processing errors now keep request/database details out
of logs and HTTP responses while retaining retryable 503 behavior, rollback,
and cleanup. The direct ClickHouse fallback is also bounded. Three new
TestClient regressions pass within a 50-test HTTP/MQTT sensor suite with Ruff;
no live service was contacted ([evidence](builds/2026-10-17-recovery/http-sensor-error-redaction.json)).

**17 October 2026 anomaly notification error containment (CAP-040 / CAP-047):**
SMTP, Directus, and actuator failure logs now omit raw exception details while
preserving existing best-effort delivery and cleanup. Critical-severity
actuation still requires human approval. Three new mocked checks pass within
the 72-test anomaly/IoT suite with Ruff; no delivery service or database was
contacted ([evidence](builds/2026-10-17-recovery/anomaly-notification-error-redaction.json)).
Direct actuator MQTT client-creation and broker publish failures also log only
exception classes, retaining the prior false-result behavior. Two new mocked
checks pass within the 64-test actuator/anomaly suite with Ruff; no broker was
contacted ([evidence](builds/2026-10-17-recovery/mqtt-actuator-error-redaction.json)).

**17 October 2026 shared ingestion error containment (CAP-047):** owned
connection failures in the canonical ingestion audit and indexer-status
helpers now log only exception classes; caller-owned errors still propagate,
and owned connections still close. Two mocked regressions pass with Ruff; no
database was contacted
([evidence](builds/2026-10-17-recovery/ingestion-base-error-redaction.json)).

**17 October 2026 commodity price error containment (CAP-040 / CAP-047):**
Yahoo Finance provider and audit failures now log only exception classes;
Oracle synchronization failures use a bounded error result and log without raw
provider text. Three new mocked redaction regressions pass within the 74-test
price, Oracle, shared-ingestion, market-data, and outbox suite with Ruff and
compilation. No provider or database was contacted. Live price parity and chain behavior remain open
([evidence](builds/2026-10-17-recovery/price-provider-error-redaction.json)).

**17 October 2026 price-attestation error containment (CAP-040 / CAP-047):**
best-effort EAS initialization failures now log only the exception class while
preserving the committed audit result and successful response with a null
attestation UID. One new mocked regression passes within the 76-test combined
price/Oracle/ingestion suite with Ruff and compilation; no EAS endpoint or
database was contacted. This does not implement an on-chain attestation
([evidence](builds/2026-10-17-recovery/price-attestation-error-redaction.json)).

**17 October 2026 legacy sensor-ingestion error containment (CAP-040 / CAP-047):**
CSV parse and row-processing errors no longer expose raw sensor input or
exception text in warnings/audit; the demo-only direct ClickHouse fallback logs
only exception classes. Canonical transaction-backed projection failures still
propagate, and row rollback/connection cleanup remain intact. Four new checks
pass within an 88-test sensor/driver/outbox suite with Ruff and compilation; no
live source or service was contacted
([evidence](builds/2026-10-17-recovery/sensor-ingester-error-redaction.json)).

**17 October 2026 ClickHouse fallback error containment (CAP-040 / CAP-047):**
demo-only EAS, Gnosis dLEGO/activity, and remote-sensing fallbacks now log only
exception classes; transaction-backed outbox failures continue to propagate.
Four new mocked regressions pass within 63 outbox/indexer/worker tests with
Ruff and compilation. No database, ClickHouse service, or provider was used
([evidence](builds/2026-10-17-recovery/clickhouse-fallback-error-redaction.json)).

**17 October 2026 geospatial import error containment (CAP-040 / CAP-047):**
GIS and remote-sensing CSV paths no longer echo invalid coordinates, unknown
source input, or raw row/database exceptions into logs or audit messages. Row
rollback remains intact. Five new mocked regressions pass within 67
GIS/remote-sensing/outbox tests with Ruff and compilation; only temporary
files and fake connections were used
([evidence](builds/2026-10-17-recovery/geospatial-import-error-redaction.json)).

**17 October 2026 EAS signer failure containment (CAP-018 / CAP-047):** failed
attestation requests retain failed status and attempt increments, while their
persisted/returned error summaries and logs omit raw EAS exception details.
One mocked regression passes within 52 attestation/EAS tests with Ruff and
compilation; no provider or database was contacted
([evidence](builds/2026-10-17-recovery/attestation-signer-error-redaction.json)).

**17 October 2026 reporting-cadence output containment (CAP-007 / CAP-047):**
automated report stdout/stderr are no longer returned, and subprocess failures
retain only exit status/code or exception class while preserving cadence
completion boundaries. Three mocked regressions pass within a 34-test
cadence/source suite with Ruff and compilation; no process or database was
started ([evidence](builds/2026-10-17-recovery/reporting-cadence-output-redaction.json)).

**17 October 2026 process-simulation failure containment (CAP-011 / CAP-047):**
calculation failures now return only a bounded exception-class summary, while
rollback and the existing cancelled record state remain intact. One mocked
regression passes with Ruff and compilation; no database was used
([evidence](builds/2026-10-17-recovery/process-simulation-error-redaction.json)).

**17 October 2026 feedback-automation failure containment (CAP-047):** evaluation
and full-cycle failure summaries are bounded before being returned or stored in
the automation log. Two mocked regressions pass within a 14-test automation
suite with Ruff and compilation; no database was used
([evidence](builds/2026-10-17-recovery/feedback-automation-error-redaction.json)).

**17 October 2026 legacy KML/Shapefile error containment (CAP-040 / CAP-047):**
parser, per-feature, and file-read failures omit raw coordinate, source-name,
and driver details while preserving successful-record counts. Three new
synthetic regressions and two compatibility checks pass with Ruff and
compilation; no live Fiona reader or database was used
([evidence](builds/2026-10-17-recovery/legacy-geo-import-error-redaction.json)).

**17 October 2026 spatial-import error containment (CAP-040 / CAP-047):**
GeoJSON/KML per-feature/audit failures and malformed XML omit raw source,
coordinate, and database details from responses, persisted audit messages, and
logs while retaining partial-import behavior. Four new regressions pass within
a 22-test spatial-import/security suite with Ruff and compilation; no PostGIS
database or live file was used
([evidence](builds/2026-10-17-recovery/spatial-import-error-redaction.json)).

**17 October 2026 remote harvest error containment (CAP-040 / CAP-047):**
stored URL references omit user-info, query data, and fragments; provider
failures omit raw exception text in persisted and returned results, while known
safe URL validation guidance remains. Two mocked regressions pass with Ruff
and compilation; no DNS, database, or external request was used
([evidence](builds/2026-10-17-recovery/harvest-manager-error-redaction.json)).

**17 October 2026 local harvest path containment (CAP-040 / CAP-047):** local
file paths are replaced with a generic source marker in ingestion logs and are
not echoed by missing-file or read-failure responses. Two mocked regressions
pass within seven harvest tests with Ruff and compilation; no real file or
database was used
([evidence](builds/2026-10-17-recovery/local-harvest-error-redaction.json)).

**17 October 2026 spatial cross-validation failure containment (CAP-047):**
block and leave-one-out fold failures omit raw kriging-library and data details,
while failed-fold aggregation remains unchanged. Two mocked regressions and six
existing cross-validator checks pass with Ruff and compilation; no database or
model-fitting provider was used
([evidence](builds/2026-10-17-recovery/spatial-cv-error-redaction.json)).

**17 October 2026 forecast error containment (CAP-002 / CAP-047):** batch
scenario failures and best-effort dashboard-write failures omit raw exception
details; dashboard projection connections close on both successful and failed
writes. Two mocked regressions pass within the ten-test forecast suite with
Ruff and compilation; no database or BI consumer was used
([evidence](builds/2026-10-17-recovery/forecast-error-redaction.json)).

**17 October 2026 EventBus handler error containment (CAP-047):** the isolated
handler protocol returns bounded execution failures, and the parent rejects
arbitrary child error text before durable delivery persistence. The focused
runner/durability suite passes 34 tests with Ruff and compilation; no worker
process or database was started
([evidence](builds/2026-10-17-recovery/event-handler-error-redaction.json)).

**17 October 2026 composite report failure containment (CAP-047):** state,
graph, comprehensive-status, and strategic-reserve section failures omit raw
exception text while preserving partial report generation. Four mocked
regressions pass with Ruff and compilation; no database was used
([evidence](builds/2026-10-17-recovery/report-state-error-redaction.json)).

**17 October 2026 report-generator failure containment (CAP-007 / CAP-047):**
single-report output/errors and automatic run-item error storage omit raw
exception details; failed automatic items still allow the batch to finish.
Two new regressions pass within the 22-test CLI/read-only suite with Ruff and
compilation using mocked boundaries
([evidence](builds/2026-10-17-recovery/report-generator-error-redaction.json)).

**17 October 2026 saved-dataset refresh failure containment (CAP-007 / CAP-047):**
single and batch refresh output omit thrown exception contents and returned
query-error text; batch refresh continues after a failed item, and single mode
closes its connection. Four new regressions pass within the 12-test
read-only/CLI suite with Ruff and compilation using fake connections
([evidence](builds/2026-10-17-recovery/dataset-refresh-error-redaction.json)).

**17 October 2026 nested-report error containment (CAP-007 / CAP-047):**
business-plan sections and reference-class estimates, reward-calibration
guardrails, and simulation reserve-clash summaries now omit raw exception
details inside successful report payloads. Four mocked regressions pass within
the 41-test report/business-plan compatibility suite; two database-backed
integration tests skipped. Ruff and compilation pass
([evidence](builds/2026-10-17-recovery/nested-report-error-redaction.json)).

**17 October 2026 governed export error containment (CAP-047):** failed file
exports now raise only a bounded exception-class summary, clear partial output,
and best-effort failure logging plus its cleanup path no longer print database
details. Three new mocked regressions pass with the three export reliability
checks, Ruff, and compilation
([evidence](builds/2026-10-17-recovery/export-error-redaction.json)).

**17 October 2026 capital-accounting report error containment (CAP-049 / CAP-047):**
the composite advisory report now records only a stable section label and
exception class for capacity, diversion, capture-risk, and deferred-credit
failures. Successful section output remains intact; focused mocked section
failures and the existing accounting suite pass with Ruff and compilation
([evidence](builds/2026-10-17-recovery/capital-accounting-error-redaction.json)).

**17 October 2026 advisory simulation error containment (CAP-011 / CAP-047):**
Monte Carlo draw exceptions and simulator-returned error strings are bounded;
tactical clash sweeps retain their failure count and scenario continuation.
The 11-test simulation resolution suite passes with Ruff and compilation
([evidence](builds/2026-10-17-recovery/simulation-error-redaction.json)).

**17 October 2026 variogram fit error containment (CAP-041 / CAP-047):**
parametric model-fit failures return only a stable operation label and
exception class. The 11-test variogram suite passes with Ruff and compilation
on synthetic coordinates and an injected model failure
([evidence](builds/2026-10-17-recovery/variogram-error-redaction.json)).

**17 October 2026 SAFE attestation error containment (CAP-018 / CAP-047):**
failed SAFE proposals persist and return only a bounded exception-class
summary; per-request failure counts and request-state updates are preserved.
Five mocked attestation tests pass with Ruff and compilation; no chain, SAFE
service, or database was used
([evidence](builds/2026-10-17-recovery/safe-attestation-error-redaction.json)).

**17 October 2026 EAS CLI failure containment (CAP-018 / CAP-047):** top-level
attestation command errors and best-effort signer status omit raw provider,
key, and RPC details while preserving nonzero command failure and status
output. Seven focused attestation tests pass with Ruff and compilation
([evidence](builds/2026-10-17-recovery/attestation-cli-error-redaction.json)).

**17 October 2026 EAS reconciliation error containment (CAP-018 / CAP-047):**
provider failures during on-chain verification now produce a fixed discrepancy
summary with only the exception class; request/UID context and the existing
issue classification remain. The 20-test focused attestation suite passes
with Ruff and compilation on fake connections and a mocked EAS client. No
provider, chain, or database was contacted. This source regression does not
close MAN-CAP-018 or live attestation validity acceptance
([evidence](builds/2026-10-17-recovery/attestation-reconciliation-error-redaction.json)).

**17 October 2026 ingestion status output containment (CAP-040 / CAP-047):**
the operator CLI now shows that ingestion and indexer failures were recorded
without printing persisted provider/database diagnostics. Its documented
module-qualified help path also starts without loading database configuration
or SOPS secrets. Three mocked checks plus Ruff and compilation pass. No
database or provider was accessed; this improves diagnostic privacy without
establishing live-source recovery or MAN-CAP acceptance
([evidence](builds/2026-10-17-recovery/ingestion-status-output-redaction.json)).

**17 October 2026 gRPC health error containment (CAP-064 / CAP-047):** the
optional health adapter now returns only the bounded remote exception class,
and still closes the channel on failure. The 29-test gRPC suite, Ruff, and
compilation pass with a mocked RPC failure; no endpoint was contacted. This
does not close TLS, authenticated transport, tenant-scope, or MAN-CAP-064
acceptance ([evidence](builds/2026-10-17-recovery/grpc-health-error-redaction.json)).

**17 October 2026 durable worker history output containment (CAP-047):**
scheduler-run, event dead-letter, MQTT delivery, and ClickHouse outbox
dead-letter listings now retain failure state and record identity while
redacting persisted raw errors from earlier attempts. Impact Office status
redacts stored run and step errors, and sandbox run history redacts stored
execution errors while preserving failure state. Agent-action audit writes now
store a redacted failure marker, history reads redact legacy details, and
database-write failure logs retain only the exception class. Four
operator-listing regressions pass within 29 outbox/CLI tests; Impact Office and
sandbox reads pass within the combined 34-test suite; agent-audit checks report
11 passed and nine database-dependent tests skipped. Ruff and compilation
pass, with fake connections only. Gateway audit database-write and local
journal failures now also log only exception classes, retaining the journal
fallback; both mocked regressions pass within nine Gateway audit checks with
Ruff, compilation, and targeted Gitleaks. No database or journal was accessed.
Gateway internal-error logs also omit exception messages and tracebacks while
retaining the generic HTTP 500 response; 34 route-policy/auth checks pass.
Core PostgreSQL, ClickHouse, and Directus health-probe failures likewise log
only exception classes while preserving generic unhealthy status; three new
checks pass within a 33-test health/driver-registry suite.
The sandbox module runner now type-checks and validates module names before
whitelist lookup, does not echo rejected input to logs or responses, and
continues to fail closed when no restricted worker is configured. Five
synthetic input cases pass within a 14-test sandbox suite with Ruff and
compilation; no module executes and no capability acceptance status changes
([evidence](builds/2026-10-17-recovery/sandbox-module-input-validation.json)).
This source-level display change does not
substitute for live worker retry or dead-letter acceptance
([worker history](builds/2026-10-17-recovery/worker-status-cli-error-redaction.json);
[ClickHouse outbox](builds/2026-10-17-recovery/clickhouse-outbox-history-error-redaction.json);
[Impact Office](builds/2026-10-17-recovery/impact-office-history-error-redaction.json);
[sandbox](builds/2026-10-17-recovery/sandbox-history-error-redaction.json);
[agent action audit](builds/2026-10-17-recovery/agent-action-log-error-redaction.json);
[Gateway audit fallback](builds/2026-10-17-recovery/gateway-audit-error-log-redaction.json);
[Gateway internal errors](builds/2026-10-17-recovery/gateway-internal-error-redaction.json);
[core health probes](builds/2026-10-17-recovery/core-health-error-redaction.json)).

**17 October 2026 Data Stream anchor failure containment (CAP-022 / CAP-047):**
batch anchor results omit raw failure text while preserving successful pending
requests and correct partial-success counts. One new mocked regression passes
within the 47-test Data Stream suite with Ruff and compilation; no database or
attestation provider was contacted
([evidence](builds/2026-10-17-recovery/data-stream-anchor-error-redaction.json)).

**17 October 2026 credit-chain failure containment (CAP-020 / CAP-047):** RPC
initialization errors omit endpoint details; mint/retirement logs and raised
errors contain only bounded exception summaries; best-effort issuance returns a
safe summary; failed balance queries cannot appear as a matching zero balance.
Five new mocked regressions pass within a 27-test credit-chain/batch suite with
Ruff and compilation; no database or provider was contacted
([evidence](builds/2026-10-17-recovery/credit-chain-error-redaction.json)).

**17 October 2026 carbon-retirement chain error containment (CAP-020 / CAP-047):**
post-confirmation chain-sync failures now return and log bounded exception
summaries, preserving the independently reviewed, committed retirement and its
non-blocking chain-sync behavior. One new mocked regression passes within 53
carbon-credit/chain-sync tests with Ruff and compilation; no chain or database
was contacted ([evidence](builds/2026-10-17-recovery/carbon-retirement-chain-error-redaction.json)).

**16 October 2026 canonical ingestion projection failure handling (CAP-040 /
CAP-047):** PostgreSQL-backed weather, remote-sensing, attestation, governance,
and RPC producers now propagate outbox failures. `OutboxEnqueueError` keeps
remote-sensing provider recovery from treating a source/projection mismatch as
a normal provider outage; transaction owners rollback before continuing or
committing. Connection-free direct ClickHouse maintenance behavior remains
available. Focused producer, outbox, weather, remote-sensing, and attestation
checks pass 158 tests; live PostgreSQL/provider behavior and MAN-CAP acceptance
remain open ([evidence](builds/2026-10-16-recovery/ingestion-outbox-failure-atomicity.json)).

**16 October 2026 ClickHouse outbox retry resilience (CAP-040 / CAP-047):**
failed projection deliveries now use capped exponential backoff from 60 seconds
to one hour, including client-setup failures. The existing lease fence,
idempotency token, and eight-attempt dead-letter threshold are preserved.
Fifty-seven focused outbox, failure-injection, and producer checks pass using
mocked boundaries. This is source-level resilience evidence; live outage and
MAN-CAP acceptance remain open
([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json)).

**16 October 2026 scheduled anomaly scope (CAP-040 / CAP-047):** hourly
scheduled anomaly scans and baseline checks now require one explicit location;
the Prefect adapter fans out over active Kokonut Network locations. Scoped
scans avoid bootstrapping shared alert-rule references, while an unscoped
interactive run retains its existing behavior. Focused source, scheduler,
inventory, and Prefect checks pass 167 tests. This is source-level scoping only:
the shared runtime identity remains, so signed worker context, RLS, external
schedule reconciliation, and MAN-CAP acceptance stay open
([evidence](builds/2026-10-16-recovery/anomaly-location-scoping.json)).

**16 October 2026 Gateway farm-activity role bridge (CAP-001 / CAP-047 / CAP-053):**
the owner selected Gateway operations while keeping Directus optional. Six
legacy farm-activity roles now expand atomically into explicit organization-
and location-qualified grants after active membership and owner/share checks.
Analyst routes filter to verified/published status and exclude Field Collector
records that are no longer eligible for use; canonical activity detail no
longer requires the separate private capture-detail grant. The 104-test focused
role, route, query, and lifecycle suite passes; four additional disposable
PostgreSQL checks confirm atomic tenant-qualified provisioning and owner/share
rejection behavior. The role mapping covers the native Field Collector 1.2.0 workflow. A
separate migration-404 Gateway slice now provides bounded non-Field-Collector
farm-activity reads, draft operations, and governed transitions with an
append-only operator ledger; its 13 focused tests and 11 disposable PostgreSQL
checks pass. Historical records without Gateway actor history still require
reconciliation, and other collections, full field/relation parity, Directus
hooks and schedules remain open. No MAN-CAP row is accepted and no Directus
permission was broadened ([role evidence](builds/2026-10-16-recovery/farm-activity-gateway-role-mapping.json);
[operations evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json);
[inventory](directus-parity-inventory.md)).

**16 October 2026 native farm-activity operations (CAP-001):** migration 404
and the Gateway now add bounded non-Field-Collector record reads, draft
creation/editing, and human lifecycle decisions with tenant-qualified grants
and a separate append-only operator audit ledger. A separate operator-console
panel now exposes these operations according to the current location grants.
Six focused console contract and JavaScript syntax checks pass, including
grant-filtered reads/actions, CSRF-protected writes, and safe detail rendering.
Create/edit forms cover all Gateway-editable content fields, including
location-checked plot/crop-cycle identifiers, bounded materials JSON, and
evidence URLs.
Thirteen focused HTTP,
service, and route-policy tests pass; an isolated PostgreSQL 16 fixture passes
11 migration, tenant-grant, lifecycle-separation, and ledger-boundary checks.
Historical rows without Gateway actor history remain ineligible for lifecycle
transition until reconciled. Migration 404 is applied on the candidate and its
app image was rebuilt from pushed source commit `4805e621`; health returned 200
and an unauthenticated farm-activity request returned 401. No OIDC session or
populated workflow rows are configured, so authenticated operations and named
MAN-CAP-001 acceptance remain open. Other
Directus collections, fields, relations, hooks, and schedules remain open
([contract](gateway-farm-activity-operations.md);
[evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json)).

The operator console now exposes the Gateway farm-activity API through a
separate grant-filtered panel. Create/edit forms include all API-editable
content, and lifecycle controls remain human-reviewed. Six focused UI contract
and JavaScript syntax checks pass; authenticated browser acceptance and
migration-404 candidate deployment remain open. No MAN-CAP acceptance or
capability status changed
([evidence](builds/2026-10-16-recovery/operator-console-farm-activity-contract.json)).

**16 October 2026 Directus farm-activity retirement (CAP-001 / CAP-047 / CAP-053):**
the owner-selected Gateway path is now enforced in the optional Directus seed:
all nine repository-managed roles have no `farm_activity` permission inserts,
and replay cleanup removes stale rows only for those managed policy IDs. A
fresh pinned Directus 12.1.1 runtime applies and replays the seed with zero
managed farm-activity permissions while retaining 14 unrelated curated role
permissions; health and authentication pass. Twenty-four focused tests cover
the source and authorization boundary. Unknown custom policies are preserved
for owner review. This narrows the Directus bypass surface but does not close
other collection, field, relationship, hook, schedule, or live identity
parity. MAN-CAP checks remain unaccepted
([seed](../../config/directus/permissions.sql);
[runtime evidence](builds/2026-10-15-recovery/directus-profile-disposable.json);
[parity inventory](directus-parity-inventory.md)).

**18 October 2026 Directus fixture contract correction (CAP-001 / CAP-047 / CAP-053):**
the synthetic API fixture now expects farm-activity requests to be denied by
the optional Directus API even when the operator has matching tenant grants;
those operations belong to the Gateway. It still checks allowed own-location
Field Note reads and hidden cross-location reads. Seven source/fixture checks, Ruff, and
Python compilation pass. No live Directus runtime was exercised and MAN-CAP
acceptance/classifications remain unchanged
([evidence](builds/2026-10-18-recovery/directus-gateway-only-source-contract.json)).

**14 October 2026 Directus parity preflight (CAP-001 / CAP-047 / CAP-053):**
the disposable Directus parity fixture now stops before synthetic user or farm
activity writes when the historical `$CURRENT_USER.location_id` scope cannot
exist in the cloned `directus_users` schema. The owner later selected
organization/location grants as the Directus target model. Three source checks
and one fake-schema preflight execution pass, but this guard only avoids
unsafe/inapplicable fixture writes; it does not establish Directus permissions
or accept a named MAN-CAP check
([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)).

**15 October 2026 Directus extension host contract (CAP-001 / CAP-047 / CAP-053):**
the hook package now declares compatibility with the exact pinned Directus
12.1.1 image, enforced by a source regression check. Collection listeners now
use the documented `collection.items.create` / `collection.items.update`
event names; a registration test invokes the extension and checks all
registered item events. The 54-test extension suite and TypeScript build pass.
This is source evidence only; runtime hook dispatch, organization/location
authorization, and named MAN-CAP acceptance remain open. A fresh isolated
Directus 12.1.1 runtime loaded both discoverable extensions, returned the
Field Collector endpoint redirect, and rejected a malformed location create
with `400 INVALID_PAYLOAD` without inserting a row. Kokonut identity/grant and
full permission parity remain open
([host evidence](builds/2026-10-15-recovery/directus-extension-host-contract.json); [event evidence](builds/2026-10-15-recovery/directus-hook-event-registration.json); [runtime evidence](builds/2026-10-15-recovery/directus-extension-runtime.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 Directus principal/grant guard (CAP-001 / CAP-047 / CAP-053):**
the hook now resolves an authenticated Directus user's OIDC subject only under
the exact configured issuer, maps it to an enabled `operator_identity`, applies
the current organization-qualified collection/action/location grant to list
reads and returned read records plus each create, update, or delete target,
excludes legacy grants without organization scope, and rejects bulk partial
access and row moves. Focused
extension tests and the TypeScript build pass. This is source-level protection
only: the issuer/operator/grants are not provisioned, Directus role/field and
expanded-relation behavior is not yet accepted, the legacy Directus service
still uses the database superuser, and this does not establish signed tenant
context or RLS. MAN-CAP checks remain unaccepted
([unit evidence](builds/2026-10-15-recovery/directus-tenant-authorization-unit.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 Directus permission seed repair (CAP-001 / CAP-047 / CAP-053):**
the seed no longer depends on the nonexistent `directus_users.location_id`;
it removes only the obsolete filter and create validation, preserves other
business predicates, and aborts on an unexpected legacy shape. The grant hook
now covers all 11 tenant-scoped collections, including `revenue_event`. Five
focused Python checks, 61 extension tests, the TypeScript build, and a
network-disabled PostgreSQL 16 seed-repair/replay check pass. The isolated
Directus 12.1.1 API check confirms that the loaded hook allows an own-location
Field Note read and hides a cross-location row. It also confirms the Field
Worker's `farm_activity` read/create/update requests remain denied: those
stored rules include custom source filters, field limits, or lifecycle filters
that the unlicensed Directus API hides. Do not broaden them to get a passing
probe. Operational Directus use now requires either a valid custom-permission
license or routing operations through the Kokonut Gateway with Directus kept
optional. Role/field/relation parity and all named MAN-CAP checks remain
unaccepted ([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 optional Directus database identity (CAP-001 / CAP-047 / CAP-053):**
the candidate now has an opt-in Directus overlay with a loopback-only
`cli.js start` runtime, separate owner-backed metadata bootstrap, extension
mounts, and a DML-only `kokonut_directus_runtime` provisioner. It denies
database/schema ownership and DDL, limits the login to the dedicated candidate
database, and keeps Directus out of the default profiles. Focused role-input and
profile-planner checks pass. The role bootstrap revokes `PUBLIC CONNECT` across
its dedicated PostgreSQL instance, so it must not run on a shared/legacy
server. Seventeen focused role/planner tests and internal-only PostgreSQL
acceptance pass; a fresh-volume run through the actual Compose overlay also
passed owner bootstrap, runtime health, synthetic admin login, and runtime
database-identity checks. This closes a deployment identity gap only; Directus
API role/field/row/relation/hook parity remains open ([profile](kernel-directus-profile.md);
[role policy](optional-database-roles.md); [role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json); [profile evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)).

**15 October 2026 sensor source contract guard (CAP-040 / CAP-047):** the
sensor CLI now rejects absent, incomplete, or conflicting operation inputs
before loading database/SOPS configuration, and `--help` remains available
without secrets. The shared `sensors` scheduled command already rejects the
missing recurring source contract before launching the legacy no-op CLI. Sixty-
nine focused source/command checks and Ruff pass. No sensor provider or
schedule ran. This prevents false success but does not define a recurring
sensor source or accept MAN-CAP-040/047
([evidence](builds/2026-10-15-recovery/sensor-ingester-explicit-input-contract.json); [schedule inventory](schedule-ownership-inventory.md)).

**16 October 2026 location-bound scheduled sensor pull (CAP-040 / CAP-047):**
the `sensors` JobSpec, disabled plan builder, dispatch, CLI, and registry now
require one location UUID and one driver-instance UUID. The registry enforces an
enabled sensor instance at the exact location; installed pull drivers must opt
in. CSV reads cap at 100 sources and 10,000 records, with MQTT remaining
event-driven. The 162-test focused sensor/scheduler/Prefect/inventory suite
passes, as do the 49 worker-operation/SQL/closure inventory checks. Source and
mock evidence only: no provider, driver instance, schedule, or database was
accessed. Tenant context, live source replay, and MAN-CAP-040/047 acceptance
remain open ([evidence](builds/2026-10-16-recovery/sensor-driver-scheduled-source-contract.json);
[operation map](worker-operation-map.json); [schedule ownership](schedule-ownership-inventory.md)).

**15 October 2026 shared dispatcher contract (CAP-040 / CAP-047):** focused
checks confirm each catalog operation uses its fixed interpreter, module,
arguments, and timeout, retains nonzero exit codes with diagnostics capped at
500 characters, requires climate location scope, and blocks recurring sensor
dispatch before process creation. Sixty-eight
dispatcher/command checks and Ruff pass with subprocesses substituted. The
runtime SQL inventory now covers 806 service source files. A follow-up worker
inventory refresh after dynamic-retention, projection, and remote-sensing
contracts recorded 257 SQL sites across 20 roots and 77 source files,
including four event-retention queries. The source-only JobSpec inventory now distinguishes
10 accepted default argument lists, four validated per-schedule location
inputs for climate, weather, metrics, and credit adjustment, and the still-missing
recurring sensor source contract. External-provider operations remain limited to explicit
bounded contracts. No provider, database, Prefect server, or schedule was accessed
for this source refresh. Live retry/recovery, provider outcomes, and
MAN-CAP-040/047 remain
open ([dispatcher evidence](builds/2026-10-15-recovery/job-dispatch-contract.json);
[inventory evidence](builds/2026-10-15-recovery/sql-inventory-refresh.json)).

**16 October 2026 scheduler worker outage recovery (CAP-040 / CAP-047):** a
current-source disposable PostgreSQL stop/start check confirms the scheduler
worker remains alive through the connection outage and completes ticks before
and after recovery. The scheduler engine was stubbed, so the check does not
exercise task SQL, lease ownership/reclaim, provider delivery, or long-duration
recovery. No MAN-CAP status changed
([evidence](builds/2026-10-16-recovery/scheduler-worker-postgres-reconnect.json)).

**15 October 2026 ARM64 candidate profile (CAP-047):** the planner now selects
an isolated ARM64 app/PostGIS profile for minimal, edge, and standard; analytics
and optional service images remain blocked pending architecture verification.
Planner tests, merged Compose configuration, and a current-source QEMU runtime
pass. The ARM64 app/PostGIS images applied all 391 schemas through migration
400; a logical restore matched all migration fingerprints and had zero pending
schemas. Health returned 200, a protected write returned 401, and short
database/app restart checks recovered. `postgis_raster` was enabled manually in
the disposable database because the ordered schema does not currently install
it. Physical Pi performance is not claimed ([profile evidence](builds/2026-10-15-recovery/kernel-arm64-profile-config.json);
[runtime evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-400.json);
[deployment record](arm64-database.md)).

**16 October 2026 current-source ARM64 smoke (CAP-047):** Buildx exported the
default Kernel target for `linux/arm64` from the current source. The loaded
image reported ARM64 and its configured non-root user; runtime CLI help and
the image-manifest command passed in a network-disabled QEMU container. This
does not claim Raspberry Pi performance, power-loss, storage, or full service
acceptance ([evidence](builds/2026-10-16-recovery/kernel-arm64-qemu-smoke.json)).
The optional Kokonut OIDC application target also built and passed its
network-disabled CLI/manifest smoke on ARM64; this does not verify ZITADEL's
service images or the full identity profile
([evidence](builds/2026-10-16-recovery/kernel-arm64-oidc-smoke.json)).
The selected ZITADEL API/Login, identity PostgreSQL, and Caddy digest-pinned
defaults expose ARM64 manifests. The planner now composes their explicit ARM64
overlays and the merged profile config passes with synthetic, process-only
values. Live provider, login, secret, and browser acceptance remain open
([evidence](builds/2026-10-16-recovery/zitadel-arm64-profile.json)).

**16 October 2026 ARM64 optional transport smoke (CAP-047):** Buildx built the
gRPC and MQTT subscriber targets for `linux/arm64`; network-disabled QEMU runs
passed CLI help, generated gRPC stub imports, and the Paho MQTT import. The
pinned Mosquitto image exposes an ARM64 child and its broker binary reported
`aarch64`. Compose/planner checks confirm every selected gRPC/MQTT service is
configured for ARM64. No gRPC/PostgreSQL server, MQTT traffic, credentials, or
mTLS session was exercised. The ARM64 software image/profile path is now
prepared; live adapter behavior, physical Pi operation, and the named MAN-CAP
checks remain open ([evidence](builds/2026-10-16-recovery/kernel-arm64-transport-smokes.json)).

**17 October 2026 current-schema ARM64 replay (CAP-047):** a fresh QEMU
project applied all 423 schema sources through migration 432 with zero failures
and zero pending; the current-source ARM64 app image built and its Gateway CLI
help passed with networking disabled. The HTTP health and protected-route
assertions did not run because the evidence harness failed while resolving the
app image by manifest-list digest after Compose started it. The project and
volume were removed; current-schema ARM64 HTTP acceptance remains open
([evidence](builds/2026-10-17-recovery/arm64-qemu-current-schema-432.json)).

**15 October 2026 Kernel startup schema gate (CAP-047):** the default and OIDC
image commands and both standard-profile roles now require complete schema
readiness before spawning API or worker processes. A focused supervisor test
proves a readiness failure launches no child, and profile checks cover the
image/Compose commands. The isolated linux/arm64 QEMU replay confirmed zero
child starts against an empty ledger and API/scheduler/event startup after 393
schemas; health was 200, anonymous write was 401, and the app reached Docker
healthy under a 1 GiB/two-CPU limit. The disposable volume was removed. This
does not accept MAN-CAP-047 or physical Pi behavior
([evidence](builds/2026-10-15-recovery/kernel-schema-startup-guard.json)).

**17 October 2026 constrained ARM64 app run (CAP-047):** the current-source
ARM64 app ran under QEMU with a 1 GiB/two-CPU cap against a fresh database
limited to 1.5 GiB/two CPUs. All 423 ordered schema sources replayed through
migration 432 with zero pending; health returned 200 and an anonymous protected
read returned 401. A single Docker stats sample is retained as an observation,
not a capacity benchmark. The database was amd64, and no Pi hardware, sustained
load, or 24-hour recovery was tested. This updates implementation evidence only;
MAN-CAP-047 remains unaccepted ([evidence](builds/2026-10-17-recovery/arm64-resource-limited-current-schema.json)).

**15 October 2026 fake-provider route contract (CAP-001 / CAP-047 / CAP-053):**
six no-network tests cover OIDC login state handoff, callback rejection,
opaque session/CSRF cookie issuance, scope response, CSRF-gated logout, and
actual-adapter rejection of invalid issuer/subject claims before database access.
This pins route wiring and a pre-database claim guard only; Authlib/provider verification, identity/session SQL,
real grants, browser acceptance, and the named MAN-CAP checks remain open
([evidence](builds/2026-10-15-recovery/operator-oidc-provider-contract.json)).

**15 October 2026 self-hosted ZITADEL deployment contract (CAP-001 / CAP-047 /
CAP-053):** an opt-in Compose selection now combines the Gateway OIDC client,
HTTPS Caddy ingress, ZITADEL API and Login V2, and a dedicated PostgreSQL
service with a bounded non-superuser role. Compose/planner source checks pass
26 tests, and the database bootstrap was exercised against an isolated,
network-disabled PostgreSQL 17 container. No IdP container, secret, operator
identity, grant, or browser session was created; all three named MAN-CAP checks remain open
([profile](zitadel-provider.md); [evidence](builds/2026-10-15-recovery/zitadel-compose-profile.json)).

**15 October 2026 report CLI scope contract (CAP-001 / CAP-047):** bulk
generation across the 94-source report registry now requires an explicit
location or `--all`; ambiguous and conflicting selectors fail before opening a
database. Snapshot verification works without a report-generation type. Eleven
focused checks and Ruff pass without database/provider access. This closes a
CLI safety gap only: report output parity, report ownership, external consumer
authorization, and all named MAN-CAP checks remain open
([evidence](builds/2026-10-15-recovery/report-generator-cli-scope.json)).

**15 October 2026 event-retention gate (CAP-047):** completed-event pruning is
was disabled by default and required a caller-supplied positive retention
window. The later dynamic policy/hold implementation below removes that
caller-selected window and adds active-hold eligibility. The cleanup query
continues to protect undisposed dead letters and non-success durable handler
deliveries. One focused source-unit regression for the handler-delivery guard
passed; prior 34-test/Ruff evidence predates that SQL change
([focused evidence](builds/2026-10-15-recovery/event-retention-handler-delivery-guard.json)).
USA and Dominican Republic were selected as jurisdictions, but no category
schedule is configured, so cleanup remains disabled and this safety gate does
not authorize pruning or accept MAN-CAP-047
([evidence](builds/2026-10-15-recovery/event-retention-cleanup-gate.json)).

**15 October 2026 generic retention gate (CAP-051):** the separate
data-governance CLI blocks before opening PostgreSQL and its service fails
closed before creating a cursor unless
`KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT=true`; dry-run and help remain
available; new policies default to `auto_enforce=false`, and nonpositive or
noninteger windows and unsupported actions fail before database access. Forty-two
focused checks cover default denial, dry-run access, help, CLI connection
avoidance, legal-hold skip, and policy-input validation. No schedule, policy owner, or
entity-level hold model was inferred. The switch must remain off until those
controls are approved and implemented; MAN-CAP-051 remains open
([implementation](../../services/analytics/retention.py); [evidence](builds/2026-10-15-recovery/data-retention-enforcement-gate.json)).

**15 October 2026 dynamic retention policy and legal-hold model (CAP-047 / CAP-051):** migration 401 removes period defaults from policy/category reference data, permits an unset window, and demotes policies lacking explicit approval. New schedules are drafts; an operator must approve a positive configured window before activation, and auto-enforcement plus the independent feature flag remain separate gates. Record-level holds require an actor and reason, retain append-only placement/release history, and are checked by the generic sweeper and event cleanup. Event cleanup derives the window only from exactly one approved global `event_bus` / `platform_event` policy and fails closed on none or ambiguity. A bounded read-only CLI inventory now lists policy status/scope and active or released holds while omitting free-text audit reasons; it does not authenticate or authorize the local operator. No period, policy, or hold has been configured. Migrations 401/402 are now applied on the candidate after an encrypted checkpoint and isolated restore/replay; the disposable migration/hold acceptance remains separate evidence. Notification/attempt/operator-audit pruning remains unimplemented. This prepares a dynamic policy path; it does not select legal periods or accept MAN-CAP-047/051. [Operations](retention-policy-operations.md); [inventory evidence](builds/2026-10-17-recovery/retention-inventory-cli.json)

**16 October 2026 EventBus/outbox worker separation (CAP-047):** event dispatch
and durable notification delivery now have independent CLI modes and Kernel
supervisor children; the legacy `--worker` mode remains compatible. Each CLI
mode checks its feature flag before connecting, and combined mode runs only
enabled loops. The default notification feature follows the event-bus setting,
with an independent override reflected in both Kernel and legacy Compose
profiles. One hundred sixty focused tests and three subtests pass, as do Ruff,
compilation, Compose parsing, and generated worker inventories. No database or
provider was contacted. This separates process responsibilities only: event
handlers still use the shared runtime database identity and destination
configuration to create outbox intents. Provider delivery, worker database
boundaries, long-duration recovery, and MAN-CAP-047 remain open
([evidence](builds/2026-10-16-recovery/event-notification-worker-separation.json)).

**15 October 2026 worker reconnect contract (CAP-047):** scheduler ticks now
use fresh bounded-timeout PostgreSQL connections while keeping a stable worker
identity; two fault-injection tests prove that connection and tick failures do
not prevent a later tick from succeeding. The EventBus worker now recreates its
event bus and notification database connection for each iteration and retries
logged failures with a five-second connection timeout; 10 scheduler tests and
20 event-worker/EventBus tests pass,
with Ruff clean. The continuous KGP indexer now also opens a fresh bounded
connection for each scan cycle and survives rollback/failure-record errors in
its source loop; 14 focused KGP service/indexer tests pass with Ruff and
compilation. A stronger scheduler check replays migrations 116, 117, 164, 165,
337, and 371 and uses the real SchedulerEngine to claim and complete bounded
EventBus tasks before and after restart under one worker ID. The task used an
empty queue and no provider. A separate SchedulerEngine check kills the real
claimant after lease commit but before subprocess dispatch; after forced lease
expiry, a replacement worker records the first run failed and completes the
task as attempt two. This proves claim-to-dispatch recovery only. The EventBus
worker check replays migrations 116,
165, and 375, invokes the real allowlisted alert-notification handler, and
completes synthetic events before and after restart. A fake webhook bound to
`127.0.0.1` returns one synthetic `503`; the outbox records a failed attempt
and retryable row, then succeeds on retry with the same idempotency key. A
worker is also killed after the fake receiver gets a third notification but
before it can return the HTTP response. After fixture lease expiry, a
replacement reclaims the row; attempt status advances from `lease_lost` to
`succeeded`, with the same idempotency key. A second event is delivered after
the database restart with a distinct notification ID. No remote provider is
contacted. The KGP acceptance replays all 394 current ordered PostgreSQL
schema files, then uses the real `kgp_protocol_deployment`,
`kgp_indexer_cursor`, and migration-403 governance-policy table with synthetic
rows. The real indexer processes seven `GuildCreated`, `DomainCreated`,
`TaskCreated`, target/selector permission, and guild-scope policy logs and links
each state row to its source event. A repeated target permission event
confirms the latest value wins. Duplicate canonical replay creates no rows. A
simulated tip change orphans all seven events and removes their projections;
the stable local guild-key anchor and canonical replay rebuild the guild,
domain, task, and governance policy state on the replacement branch. The
governance table is informational; the smart contract remains authoritative
for execution. The worker stays alive through a PostgreSQL stop/start and
advances its lease heartbeat; after the worker is killed and its lease expires,
a replacement owner advances the heartbeat. Live RPC, seeds, and providers
are not used. This does not establish other event-type parity or live-chain
behavior. A separate fresh encrypted checkpoint and isolated restore rehearsal
then preceded candidate application of migration 403; the candidate now has 394
applied schemas and zero pending, but its app image was not rebuilt, the policy
table is empty, and application-table RLS remains off
([rollout evidence](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json)).
Production-duration lease/RPC/event processing, real-provider delivery,
scheduler recovery after task side effects, and long-duration acceptance remain
open.
MAN-CAP-047 is not
accepted
([scheduler unit evidence](builds/2026-10-15-recovery/scheduler-worker-connection-recovery.json); [stub-engine runtime evidence](builds/2026-10-16-recovery/scheduler-worker-postgres-reconnect.json); [real-engine runtime evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json); [event worker evidence](builds/2026-10-15-recovery/event-worker-connection-recovery.json); [EventBus runtime evidence](builds/2026-10-16-recovery/event-worker-postgres-reconnect.json); [KGP evidence](builds/2026-10-15-recovery/kgp-worker-connection-recovery.json); [KGP runtime evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json); [KGP crash-recovery script](../../scripts/check-kgp-worker-reconnect-disposable.py)).

**14 October 2026 supervisor contract (CAP-047):** four focused tests cover
graceful shutdown, process-group escalation, unexpected zero exit, and
partial-launch cleanup; one POSIX integration case verifies SIGTERM delivery
to a child and grandchild. Database-outage and lease-recovery acceptance remain
open, and MAN-CAP-047 is not accepted
([evidence](builds/2026-10-14-recovery/kernel-supervisor-unit-contract.json)).

**14 October 2026 projection delivery failures (CAP-007 / CAP-047):** twelve
focused unit tests cover optional-provider no-claim behavior, client setup and
outcome failures, partial batches, completion errors, stale fences, cleanup,
and one-shot CLI exit codes. A separate disposable-PostgreSQL fixture passes
nine checks, including durable retry/success state and actual CLI exit behavior;
it uses controlled ClickHouse outcomes and does not prove live-provider
interoperability or cross-store crash deduplication. This does not accept either
named MAN-CAP check ([unit evidence](builds/2026-10-14-recovery/clickhouse-outbox-failure-injection.json);
[PostgreSQL evidence](builds/2026-10-14-recovery/clickhouse-outbox-cli-disposable.json)).

**14 October 2026 notification delivery failure boundaries (CAP-047):** eight
focused mocked tests cover exception-class-only provider failure recording,
independent batch progress, completion database failure propagation, stale
lease accounting, SMTP idempotency headers/closure, and real CLI argument
parsing with failure/lease-loss exit codes. No real provider or database was
used; this does not accept MAN-CAP-047 or provider availability
([evidence](builds/2026-10-14-recovery/notification-outbox-failure-injection.json)).

**17 October 2026 freshness alert reliability (CAP-047):** the legacy
data-freshness sender closes webhook responses on success and failure, and
reduces webhook/SMTP error details to an HTTP status or exception class before
logging or persistence. Failed database measurements no longer replace the
last known stale/critical alert state, preserving a later recovery transition.
Thirty-three focused freshness checks pass with mocked providers/reads; no
destination or database was used. Production delivery, destination ownership,
retention, and MAN-CAP-047 acceptance remain open
([delivery evidence](builds/2026-10-17-recovery/freshness-alert-error-containment.json);
[state evidence](builds/2026-10-17-recovery/freshness-alert-state-recovery.json)).
Failed freshness measurements now also store a bounded evaluation summary and
log only the exception class; savepoint rollback and preservation of prior
alert state remain intact. The 33-test mocked suite passes with a synthetic
secret-bearing database error
([query evidence](builds/2026-10-17-recovery/freshness-query-error-redaction.json)).

**17 October 2026 worker inventory refresh (CAP-047):** after the EAS provider
extraction, freshness-alert helper changes, and CI #431 correction, the current
static inventories cover 31 operation roots and 93 source files, 639 function
memberships, 875 direct-call edges, 322 worker SQL sites, 249 SQL sites with
static operation paths, and 73 sites without a static function match. The
runtime SQL inventory covers 4,006 execution sites across 826 files. The latest
30 focused worker-inventory tests and all five generated worker checks pass,
but the boundary preflight remains `review_required`; source reachability does
not prove runtime grants, tenant context, active schedules, or RLS. MAN-CAP-047
remains unaccepted ([latest worker evidence](builds/2026-10-17-recovery/ci-431-worker-inventory-fix.json);
[runtime inventory evidence](builds/2026-10-17-recovery/worker-inventory-refresh-current.json)).

**14 October 2026 runtime default-privilege boundary (CAP-047 / CAP-053):**
the opt-in runtime bootstrap now removes default table and sequence privileges
for future public objects while retaining existing-table behavior. The
disposable PostgreSQL 16 role check passed the existing handler and credential
checks and confirmed a post-provisioning synthetic table and its sequence are
inaccessible to the runtime login. Broad grants on existing public tables,
worker identity, and RLS remain open; this does not accept either MAN-CAP row
([evidence](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json)).

**14 October 2026 candidate schema rollout (CAP-047 / CAP-053):** migrations
392–397 were applied to the local candidate after a fresh encrypted checkpoint
and isolated restore rehearsal. This historical rollout had 388 applied schemas
through 397 and no application-table RLS. The later candidate state is recorded
below; implementation progress does not accept any named MAN-CAP check
([historical evidence](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json)).

The current runtime SQL inventory covers 3,894 direct execution sites across
815 service modules, includes summaries for 67 packages, and identifies 1,041
regex-derived relation-name candidates. It records 289 sites with worker
operation references. Literal SQLAlchemy `text()` and psycopg `SQL()` wrappers
are unwrapped; 145 unknown-statement sites, 24 `WITH` sites, 394 sites without
relation candidates, 492 non-literal sites, and dynamic or indirect paths
require review before narrowing runtime grants. The
report is not an ACL and does not accept a MAN-CAP check ([inventory](runtime-sql-inventory.json);
[latest evidence](builds/2026-10-16-recovery/runtime-sql-inventory-refresh-latest.json);
[previous evidence](builds/2026-10-14-recovery/runtime-sql-inventory-check.json)).

**Last recorded GitHub status (CAP-001 / CAP-047 / CAP-053), checked 15 October:**
PR #68 is at `4ad4b06ed19629f1ec71c25c47ef78597fdf2322`. Security run
[#44](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38681693883)
passed on this head. CI #320
([run](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38681693999))
is in progress. This head adds reference-only seed scope, the selected
self-hosted ZITADEL provider contract, and code-first mapping of remaining
gates. The earlier Security #39 source-digest false positive was corrected
with a file-scoped allowlist; local full-history Gitleaks and hosted Security
#44 pass. The earlier
CI #307 OIDC fixture failure was corrected in `7953afe`; runs #308/#32 are
historical, not current-head coverage. The named MAN-CAP checks remain open.
See [the code-first execution plan](code-first-execution-plan.md) for the
remaining work order and the Raspberry Pi code-only assessment scope.

**14 October 2026 database restore/bootstrap (CAP-047 / CAP-053
implementation follow-up):** the exact encrypted pre-400 candidate checkpoint
was restored into an internal-only template0 clone, migration 400 was replayed
with zero pending/drift, and the runtime/operator-auth bootstrap passed its
repeatability, grant, denial, and synthetic DML checks. The archive had 1,010
public tables but zero public location rows; this proves database/role recovery
and not farm-data parity. The recovery volume is retained with its container
stopped. It does not provision candidate credentials, enable RLS, or accept
either named MAN-CAP check ([evidence](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json)).

The preceding CI #304 on `8aa33e24f169f15afb249a53ae3d281ed8d843a2`
completed with five failures, 4,632 passed tests, and 75 passed subtests; its
local fix batch passed the focused regression, operator-auth, and Compose
checks. The approved eight-suite platform-integrity suite now passes 290 tests
on local commit `238e2ef` ([verification record](builds/2026-10-14-recovery/platform-integrity-290-tests.json));
the earlier 288-test record remains historical.

The focused reviewer-note service/auth slice also passed 14 service and three
route tests, including rollback/connection cleanup on tenant denial. Directus
parity, worker/direct-database isolation, RLS, and named manual acceptance
checks remain open; no full capability acceptance is implied.

**14 October 2026 Gateway mobile mutation context (CAP-053):** API-key and
capability enrollment/revocation handlers now require the authenticated
Gateway's internal `mobile_device` action/location marker, then establish
current-owner transaction context before the write. Owner lookup is locked in
the same transaction; missing/stale owner context fails before mutation. The
tenant-context, mobile API, and OIDC operator-auth suites passed 126 tests;
Ruff and Python compilation passed. This closes those application call paths,
not a database identity boundary: the ordinary app role can still set custom
PostgreSQL context values, so worker/direct-database isolation and RLS remain
open ([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/gateway-mobile-tenant-context.json)).

**14 October 2026 mobile credential lookup boundary (CAP-053):** the local
migration 392 source moves token-hash resolution and single-use enrollment
redemption behind narrow PostgreSQL functions owned by a dedicated
NOLOGIN/NOBYPASSRLS role. The existing owner-binding trigger now uses a fixed
search path and schema-qualified relations. A network-isolated PostgreSQL 16
acceptance passed direct-table denial, migration replay, current/legacy/unknown
token outcomes, enrollment conflict/expiry/single-use behavior, a concurrent
redemption race (exactly one device/code consumption), and owner transfer. The
56-test mobile API/tenant suite and Ruff pass. Migration 392 has
not been applied to the candidate; RLS and MAN-CAP-053 remain open
([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/mobile-credential-functions-disposable.json)).

**14 October 2026 signed mobile tenant context (CAP-053):** migration 393
replaces trust in caller-set mobile tenant labels with a database-signed HMAC
proof bound to the PostgreSQL backend and transaction. Its private key is
unreadable by the application role, and `current_tenant_context()` verifies
the signature before returning tenant scope. Narrow definer-role row-lock
policies were required for forced RLS and are dormant until an operator enables
RLS separately. PostgreSQL 16 disposable acceptance applied and replayed
migrations 392–393, forced RLS only on its synthetic tables, and passed
cross-tenant filtering, forged/tampered context rejection, invalid-token
clearing, transaction cleanup, key/table denial, and credential operations
under forced RLS. Seventy-six focused Python tests, Ruff, Python compilation,
and ordered migration validation (505 source files) pass. The candidate remains
at migration 391 and RLS remains disabled; operator/Gateway context, worker,
Directus/view access, candidate rollout, and MAN-CAP-053 remain
open ([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json)).

**13 October 2026 local source update (CAP-053):** migration 391 and the
working tree now pin new mobile device enrollments to the current verified
owner. Device forms, media writes, sync, and sync-status validate that identity
inside their PostgreSQL transaction. After owner transfer the old device is
denied until re-enrollment; its local encrypted queue is preserved and
quarantined from upload under a replacement device. Legacy rows remain
unbound and require re-enrollment. Sixty-seven focused Python checks, two
offline-shell Node checks, Ruff, Python syntax, dependency alignment, and
provider-boundary checks passed. A disposable PostgreSQL 16 fixture replayed
migration 391 twice and checked legacy NULL preservation, wrong-owner rejection,
binding immutability, and old-owner denial after transfer. The candidate rollout
completed on 14 October after an encrypted checkpoint; live authenticated
re-enrollment remains open and RLS remains disabled
([rollout evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)). An isolated Chrome browser check also passed actual client-offline behavior: `navigator.onLine=false`, service-worker shell reopen, encrypted note capture, preservation through a synthetic 503, and queue clearing after a synthetic retry success. Because all mobile API calls were intercepted, live authenticated sync and MAN-CAP-053 remain open ([browser evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)).

**14 October 2026 legacy CLI boundary (CAP-053):** all historic
`services.analytics.mobile_offline` service helpers and CLI commands now fail
closed before database access because the legacy path has no authenticated
tenant identity and bypasses form/consent policy. Enrollment, capture and sync
continue through the consent-aware Gateway. Focused boundary tests cover every
helper and command and verify no connection is opened. The OIDC console now
provides a location-scoped device inventory and content-free queue summary;
both device-read and collection-review grants for that location are required.
The 83-test focused route/service/console run passes, but live OIDC and database
acceptance remain open. Worker and other CLI review also remain open. This
source change does not accept the named capability check.
MAN-CAP-053 stays partial pending live OIDC and reconnect, human disposition,
database-role-backed tenant isolation, and retention acceptance. The source-only
[tenant/RLS call-site audit](mobile-tenant-rls-callsite-audit.md) records why
pre-context device/enrollment lookups and non-OIDC mutation paths must be
closed at both application and database-role boundaries before enabling row
policies.

**14 October 2026 tenant readiness source slice (CAP-053 / CAP-047):** the
aggregate tenant preflight now compares schema sources with the applied ledger,
reports connected-role privilege/RLS indicators, and validates enabled
scheduler arguments using counts only, and requires a dedicated read-only
preflight role before running after RLS is enabled. Four new focused source
checks plus six existing tenant-preflight tests pass with Ruff. A separate
disposable PostgreSQL 16 acceptance ran the actual catalog queries against
synthetic migration-ledger, privilege, RLS, and scheduled-command rows on an
internal network with egress blocked and no published ports. Its sanitized
output detected the expected matched, pending, drifted, and removed-source
migration states; DML/RLS bypass risks; and valid/rejected/unbounded
scheduled-command counts. Identifier-leak assertions and cleanup passed. No
candidate or legacy database was accessed and no migration was applied. This
does not establish worker isolation or RLS readiness ([source evidence](builds/2026-10-14-recovery/tenant-database-readiness-check.json); [PostgreSQL evidence](builds/2026-10-14-recovery/tenant-database-readiness-postgres.json)).

**14 October 2026 seed-ledger preflight (CAP-053):** the migration runner
previously omitted the range-prefixed `064-068_impact_network.sql`; source
discovery now includes all 121 candidate-pending seeds and validates 503 total
migration files. The curated `seed.sh` list now goes through selective ordered
migration execution and checksummed ledger writes. A pending form seed accepts
only empty state or a full match of the source columns and active revision
snapshots; the check runs before the curated batch and repeats under table locks
inside the seed transaction. A read-only comparison found the candidate's five
active 1.2.0 forms and five matching active revisions exact, with five retired
1.1.0 revisions preserved. The follow-up candidate reconciliation then
recorded `seed:140_mobile_forms.sql` as applied without changing business rows;
At the 14 October checkpoint, 120 other seed files remained pending. See the
[preflight evidence](builds/2026-10-14-recovery/candidate-seed-ledger-reconciliation-preflight.json)
and [ledger reconciliation evidence](builds/2026-10-14-recovery/candidate-mobile-form-seed-ledger-reconciliation.json). A subsequent read-only inventory found 50 empty curated target tables; only the already-tracked mobile forms and base service catalog contain rows. The full 31-seed ordered list applied to an isolated checkpoint restore and skipped cleanly on a second invocation. A separate `template0` bootstrap then passed all 382 schemas through 391 and all 31 curated seeds. At the 14 October checkpoint, the candidate had one recorded seed and 90 non-curated seeds remained unselected ([inventory](builds/2026-10-14-recovery/candidate-curated-seed-target-inventory.json); [snapshot replay](builds/2026-10-14-recovery/curated-seed-disposable-replay.json); [fresh bootstrap](builds/2026-10-14-recovery/fresh-curated-seed-bootstrap.json)). A fresh encrypted checkpoint was restore-rehearsed with matching migration and extension fingerprints and selected form/service counts. The old 30-file rollout proposal was superseded on 15 October: only the five reference catalogs in [the selected scope](reference-seed-scope.md) were approved and applied to the local candidate; pilot rows stay held. The separate rollout evidence is linked below.

The current migration-400 checkpoint for that five-file scope was then restored
transactionally into a fresh isolated `template0` database. Migration and
extension fingerprints, all 1,010 public tables, the five catalog target
counts, and selected mobile-form/service counts matched the candidate. The
checkpoint remains encrypted; the temporary restore container/network were
removed and its isolated recovery volume is retained. At this preflight stage it was recovery evidence only; owner approval and candidate seed execution
followed and are recorded below ([preflight](builds/2026-10-15-recovery/candidate-reference-seed-checkpoint-preflight.json)).

**15 October 2026 reference catalog rollout (CAP-001 / CAP-053):** after
separate owner approval, the exact five selected seeds were applied to the
local migration-400 candidate through the ordered checksummed runner. All five
ledger rows are applied with no failed/pending migration rows; target counts
are 19 expense categories, 20 metric definitions, 19 emission factors, 8
benchmarks, and 5 protocols. Existing mobile forms, form versions, and service
catalog counts were preserved. The candidate remains healthy (`/health` 200),
and an unauthenticated protected review route returns 401. The other curated,
pilot, and unselected seeds remain held. These are reference definitions/model
defaults, not farm observations, verified outcomes, report-owner acceptance,
tenant/RLS acceptance, or a MAN-CAP pass ([rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json); [scope](reference-seed-scope.md)).

**13 October 2026 source update (CAP-001 / CAP-053):** migration 386 and
current-use filters now cover canonical Field Collector activity reporting,
analytics, process metrics, repository-owned dashboards, and exports; ineligible rows stay visible to
authorized operators for disposition, while edits and forward lifecycle
transitions are blocked. Focused PostgreSQL 16 synthetic migration checks
passed with Directus present and absent; 56 focused application/query/console
tests passed (18 skipped). The Directus permission seed repair also passed a
second-run no-change check with nested location scopes and NULL permissions.
The final ordered/checksummed migration replay passed on a fresh populated
archive clone with zero pending schemas and no checksum drift. All 8/8 existing
Directus read permissions route Field Collector reads through scoped Gateway
paths. MAN-CAP-001 and MAN-CAP-053 remain not run. The separately approved
migration-386 rollout is now complete on the
local Kernel candidate: 377 applied schemas, zero pending, app health 200, and
anonymous farm-activity/review routes return 401. Its database checkpoint was
restore-rehearsed with matching migration fingerprints, extension versions, and
selected row counts. See [rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json).

**13 October 2026 tenant-owner decision (CAP-001 / CAP-053):** the repository
owner confirmed that Kokonut Network exclusively owns the two seeded locations,
Kokonut Adelphi and Kokonut Genesis. Source now includes ordered migration 387,
a final pilot ownership seed, and updated legacy seed assignments. A network-
disabled PostgreSQL 16 compatibility fixture passed clean-bootstrap ordering,
idempotent replay, legacy owner-link deactivation, exact owner assertions, and
refusal/rollback for an unrelated owner ([evidence](builds/2026-10-13-recovery/tenant-ownership-disposable-acceptance.json)). This closes the owner-decision and
focused source acceptance gates for those two records only. A read-only review
found no source-grounded location/tenant mapping for the 38 unlocated dashboard
definitions or three report snapshots, so those records remain unassigned
([lineage evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).
The clean full-schema replay of all 380 ordered migrations has passed,
including the 384–385–389 trigger stack
([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
Migration 390 transfer and tenant-context acceptance passed 14 disposable
PostgreSQL checks, and eight context unit tests passed
([acceptance](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).

**16 October 2026 operating-tenant source reconciliation (CAP-001 / CAP-053):**
the owner-confirmed map now covers Kokonut Genesis, Kokonut Seeds, Kokonut
Adelphi, Kokonut Terra Viva, and Kokonut V1 through rerunnable seed 122. It
applies only to exact name/slug matches that already exist, skips locations
pending import, and fails closed on identity, owner, or revoked-verification
conflicts. Five disposable PostgreSQL checks pass for missing locations,
all-five reconciliation, replay, unknown-location preservation, and
transactional rollback. This records operating-tenant access and does not
assert land title or grant sharing. The read-only tenant preflight now reports
aggregate mapping readiness without emitting location names or identifiers.
Its owner-confirmed count excludes inactive locations, matching the runtime
tenant-context contract.
No candidate/legacy database was changed;
operator affiliations, imported source data, remaining Gateway/worker scopes,
and direct-database/RLS boundaries remain open. MAN-CAP-001 and MAN-CAP-053
remain not run ([seed](../../schemas/seeds/122_kokonut_network_operating_tenant_map.sql);
[evidence](builds/2026-10-16-recovery/network-location-owner-map-disposable.json);
[procedure](tenant-owner-map-reconciliation.md)).
The ownership/transfer rollout applied migrations 387–390 after a fresh
age-encrypted checkpoint; the follow-up device-binding rollout applied 391 from
a separate checkpoint. All 382 schema migrations are now applied with zero
pending, while 121 seed files remain pending in the ledger. Five mobile-form rows and
ten revisions exist without applied seed history and require reconciliation
before any seed rollout. Only the app was recreated in each rollout;
app/database/Metabase are healthy and anonymous protected routes return 401
([ownership rollout](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json),
[device-binding rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)).
Worker isolation, RLS, and MAN-CAP-001 / MAN-CAP-053 remain open.
This mapping does not establish user access or end-to-end tenant isolation.

**14 October 2026 Gateway context progress (CAP-001 / CAP-053):** report-review
queue and detail reads now validate tenant-qualified scope and set transaction-
local context on the same connection as their protected query. The routes keep
the existing location/grant predicates and return 403 for legacy NULL-tenant
grants. Route-specific verification is pending; this is a first bounded
integration only. Seventeen disposable PostgreSQL acceptance checks and two
focused Gateway HTTP denial checks passed, including owner/shared reads,
same-transaction context, legacy denial, and cleanup. The broader operator-auth
file yielded 33 passed and three older `Vary` assertion failures, which remain
open for follow-up. Other Gateway/worker paths, direct-database boundaries,
and RLS remain open, so both capabilities remain partial and their manual
acceptance checks remain not run.

The Field Collector review queue and detail query paths now set tenant context
within their read transaction and map legacy-grant denial to HTTP 403. Twenty-
two synthetic disposable PostgreSQL checks and 31 focused context, mobile
service, and route checks pass, including owner/shared reads, same-connection
context, cleanup, pre-query legacy denial, and same-tenant/cross-tenant
multi-grant behavior for the content-free disposition inventory. Human
retention/erasure decisions, other Gateway and worker paths, direct-database
boundaries, and RLS remain open; tenant isolation remains partial.

Append-only reviewer-note writes now set context before the INSERT on the same
connection and require the `review` and `read_detail` grants to resolve to one
tenant. Fourteen mobile-review service checks, eleven tenant-context checks,
and three focused auth-route checks pass. The tests confirm context precedes
the INSERT, scope denial rolls back and closes the transaction without writing,
and the route returns HTTP 403 for cross-tenant denial. Candidate and legacy
databases were not used. This closes only the reviewer-note write path;
remaining Gateway/worker paths and RLS are still open.

OIDC participant-link creation and revocation now use same-origin
`/operator/api/mobile/.../participants` routes so the operator session cookie is
sent to the endpoint. Each route requires its location-scoped action and CSRF;
its service transaction sets tenant context before the party lookup or link
write. Tenant denial returns 403 before those queries. The original
`/api/mobile/.../participants` endpoints retain Gateway API-key/capability
authorization. Five focused operator route and transaction tests plus one
API-key regression check pass, and both success and error responses are
no-store. Real OIDC/browser acceptance,
other Gateway and worker paths, direct-database boundaries, and RLS remain open.

The farm-activity intake and canonical list/detail reads, draft promotion,
draft correction, and lifecycle transitions now establish transaction-local
context before protected queries or writes. Multi-grant operations require all
grants to resolve to the same tenant; route handlers map context denials to
HTTP 403. The workflow service suite passed 10 tests, the lifecycle suite 31,
and 26 focused auth-route checks passed. Ruff and syntax checks pass; no
database was accessed. CAP-001 and CAP-053 remain partial pending the other
Gateway/worker paths, tenant ownership reconciliation, and direct-database/RLS
gates.

OIDC operator enrollment and revocation for mobile devices now validate the
`mobile_device:enroll` or `mobile_device:revoke` tenant-qualified grant in the
same transaction as the write. The public API-key enrollment contract stays
unchanged. Ten focused operator-route tests and the public enrollment
authorization test pass; Ruff and syntax checks pass. Remaining operator/API
and worker paths still need a bounded tenant-context review.

The tenant-aware source foundation is now present in migrations 388–389:
explicit operator organization memberships, verified seed-location ownership,
revocable organization shares, tenant-qualified resource/action grants, and
Field Collector write-trigger checks. Actual migrations 387–389 and focused
authorization/trigger cases passed on a network-disabled disposable PostgreSQL
16 schema; migrations 388–389 also passed idempotent replay
([evidence](builds/2026-10-13-recovery/tenant-grants-migrations-disposable.json)).
Legacy NULL-tenant grants remain compatible and unbackfilled. The operator CLI
membership/share lifecycle and in-place legacy owner-grant conversion passed
against disposable migrations 387–389
([evidence](builds/2026-10-13-recovery/tenant-grants-cli-disposable.json)). A
separate migration-390 CLI/database acceptance passed its ten transfer,
authorization, rollback, cancellation, revocation, audit immutability, and
replay checks with synthetic records only
([evidence](builds/2026-10-13-recovery/tenant-owner-transfer-disposable.json)). A
clean full-schema replay then validated and applied all 380 ordered migrations
with zero pending or failed, including the combined 384–385–389 trigger stack
(11 registered activity/workflow triggers); the candidate remained healthy and
untouched ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
This was not a populated/archive or pilot-seed replay. The local candidate
rollout is now complete, but worker/direct-database isolation, RLS, and
MAN-CAP-001 / MAN-CAP-053 remain open.

The Directus source inventory and isolated runtime probe map the CAP-001/CAP-053
boundary, but do not establish API parity. The archived `directus_users` table
has no `location_id` despite staff filters using `$CURRENT_USER.location_id`;
synthetic Field Worker requests returned 403 with no rows visible, which is
fail-closed but does not prove own-location access or cross-location isolation.
Field/write visibility, hook, and schedule acceptance remain open
([inventory](directus-parity-inventory.md); [runtime evidence](builds/2026-10-13-recovery/directus-api-parity.json)).

**13 October 2026 Phase 4 reporting safety update:** legacy
`dashboard_dataset.query_sql` execution now has an explicit
`KOKONUT_FEATURE_LEGACY_DATASET_SQL` gate that defaults off; read-only dataset
listing remains available. This reduces the default Kernel execution surface,
and the compatibility switch reaches candidate, portability, and standard app
and worker profiles. Twenty-three focused core and Compose-profile tests pass,
with Ruff, shell syntax, and whitespace checks clean. It does not establish
saved-dashboard ownership, query safety, least-privilege
grants, location scoping, or report parity ([implementation](provider-configuration.md);
[inventory](reporting-parity-inventory.md)).

**14 October 2026 follow-on:** the first-party legacy saved-query refresher now
uses a dedicated analytics login restricted to the three curated reporting
views, with live ACL verification, a read-only bounded transaction, and
metadata-only writes through the application connection. Its synthetic
PostgreSQL acceptance passed, and the feature remains disabled by default.
This narrows the repository-owned runner boundary; external dashboard roles,
report ownership/reference fixtures, and tenant scope remain open. No
MAN-CAP status or acceptance count changes ([evidence](builds/2026-10-14-recovery/saved-reporting-reader-disposable.json)).

**16 October 2026 CLI boundary:** explicit `--all` and `--dataset-id` refresh
requests now reject the disabled compatibility feature before opening the
application connection. `--list` remains available while disabled, and
invoking the CLI without an operation prints help without connecting. This is
an invocation-boundary improvement only; it does not approve saved SQL, grant
tenant scope, or close external dashboard/report parity. Eight focused CLI
tests pass, and the capability matrix remains valid at 66 rows
([evidence](builds/2026-10-16-recovery/dashboard-refresh-cli-boundary.json)).

**15 October 2026 bounded carbon-credit scheduler operation (CAP-040 / CAP-047):**
the existing `credit_adjustment` job was initially restricted to a read-only
operation. The dedicated entrypoint and required single-location check are
recorded in the 16 October follow-on. Automatic adjustment and retirement
review actions remain rejected. No job was registered or activated.

**16 October 2026 location-scoped carbon-credit scheduler follow-on (CAP-040 / CAP-047):**
the dedicated check now requires exactly one location in the CLI, shared job
dispatcher, disabled schedule planner, and database-driven command contract.
The scheduler contract rejects missing scope before process creation, and the
CLI rejects it before opening a database connection. Ninety-three focused
command/contract checks pass; the then-current JobSpec inventory distinguished
nine no-input jobs, five required-location jobs, and one source-less sensor job.
Anomaly and sensor-scope slices later changed that inventory to eight no-input
jobs and seven validated-input jobs. The current 18-job catalog has five no-input jobs
and twelve validated-input jobs after EAS/RPC chain, NOI, and newer native worker scoping; the sensor
location/driver-instance pair remains required.
This remains a source contract: workers inherit the shared runtime identity
without signed tenant context, RLS remains blocked, and no MAN-CAP status or
acceptance count changes ([evidence](builds/2026-10-16-recovery/worker-credit-adjustment-location-scope.json);
[operation map](worker-operation-map.json);
[JobSpec inventory](worker-job-contract-inventory.json)).

The read-only check reads verified/published credit and carbon-balance inputs
and performs no writes. No job was registered or activated. MAN-CAP-020 credit
custody/retirement parity, worker identity, and tenant context remain unaccepted
([historical command evidence](builds/2026-10-15-recovery/scheduled-credit-adjustment-command-contract.json)).

**23 October 2026 signed credit-adjustment worker (CAP-020 / CAP-047):**
migration 599 adds a default-off signed `credit_adjustment` worker whose bounded
function verifies `carbon_credit_adjustment/read`, enforces the exact signed
location, and reads only the source columns needed for the legacy recomputation
and 0.1% report threshold. The existing Prefect adapter keeps the prior
read-only command until the feature is enabled; new native plans still target
the default-off worker and remain disabled. The focused worker/job selection
passes 256 tests, Ruff passes, and disposable PostgreSQL 16 replay passes six
grouped checks for summary/fallback parity, cross-location denial, direct-table
denial, and zero writes ([worker](../../services/analytics/carbon_credit_adjustment_worker.py);
[migration](../../schemas/postgres/599_signed_credit_adjustment_check_worker.sql);
[evidence](builds/2026-10-23-recovery/credit-adjustment-worker-disposable.json)).
No candidate or legacy database, schedule, provider, or worker credential was
used. CAP-020 stays prepared; grant/credential provisioning, schedule/output
ownership, broader credit-ledger parity, and MAN-CAP acceptance remain open.

Python and TypeScript SDKs now expose schema-checked read models for the
`carbon_credit`, `credit_adjustment`, `credit_retirement`, and `credit_transfer`
tables. Their SQL lifecycle and transfer/adjustment literals are checked in
both SDKs. This adds stored-record representation only; it does not expose
ledger mutation methods, establish route permissions, or change CAP-020's
baseline-retained classification. See the [schema-parity evidence](builds/2026-10-18-recovery/sdk-carbon-credit-ledger-parity.json).

**16 October 2026 per-location metric schedule contract (CAP-040 / CAP-047):**
the native scheduled `metrics` JobSpec now uses `--compute --all` with one
required `--location-id`; its command contract rejects `--all-locations`.
Disabled plan generation requires one UUID. The optional Prefect adapter
preserves its prior aggregate intent by invoking the scoped job once for each
active location assigned to `kokonut-network`; the weather, credit, and climate
adapters use the same location selector. Synthetic tests cover the owner filter,
empty inventory, one-location dispatch, and schedule planning. The selection is
code-level scope only: workers have no signed tenant context, RLS remains
blocked, and none of the 66 manual capability checks is accepted ([evidence](builds/2026-10-16-recovery/prefect-location-scoped-job-fanout.json);
[schedule inventory](schedule-ownership-inventory.md)).

**16 October 2026 per-location remote-sensing operations (CAP-040 / CAP-047):**
the scheduled JobSpec and every manual CLI/helper path now require one UUID
location. Listing, specific-job lookup, due claims, explicit-bbox reads, job
creation, and provider dispatch bind or verify that same location. The
optional Prefect adapter keeps its active Kokonut Network fan-out. The 138-test
focused suite covers the source contract; a disposable PostgreSQL 16 fixture
confirms two locations claim only their own jobs, while an unscoped claim is
rejected before SQL and the unselected third-location job remains unclaimed
([database evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-postgres.json);
[reusable check](../scripts/check-remote-sensing-location-claim-disposable.py)).
This location UUID scopes queries but is not signed worker context or database
authorization. Provider credentials/outcomes, persisted-task reconciliation,
and MAN-CAP acceptance remain open; the capability status is unchanged
([source evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-scope.json);
[operation map](worker-operation-map.json); [JobSpec inventory](worker-job-contract-inventory.json)).

**16 October 2026 explicit manual weather scope (CAP-040 / CAP-047):** manual
current-weather ingestion requires one canonical `--location-id` or deliberate
`--all-locations`; omitted scope prints offline help and invalid UUIDs fail
before database access. The aggregate query is explicit, and the Kernel
scheduler continues to reject aggregate mode. Eighty-six focused mocked
weather/scheduler checks pass. Forecast ingestion now follows the same manual
contract, with 18 focused mocked CLI/unit checks passing; its location-bound
summary helpers remain unchanged. Climate-data ingestion also canonicalizes
its required location UUID and rejects conflicting dataset modes before DB
access; 116 focused climate/CLI/scheduler/import checks pass. These are
CLI/query contracts only: they do not establish operator authorization, signed
worker context, provider success, persisted schedule state, or RLS. Remote-
sensing CSV imports now require one location or explicit aggregate mode, use
plot/farm lineage checks, and preserve multi-location input behind that explicit
selector. Fifty-five focused ingestion, smoke, and remote-sensing checks pass.
No MAN-CAP acceptance is implied
([current-weather evidence](builds/2026-10-16-recovery/weather-cli-location-scope.json);
[forecast evidence](builds/2026-10-16-recovery/weather-forecast-cli-location-scope.json);
[climate evidence](builds/2026-10-16-recovery/climate-cli-location-preflight.json);
[remote-sensing CSV evidence](builds/2026-10-16-recovery/remote-sensing-csv-location-scope.json)).

**16 October 2026 explicit manual anomaly scope (CAP-040 / CAP-047):** the
standalone anomaly CLI now prints help without scope; anomaly, baseline, and ML
checks require one `--location-id` or explicit `--all-locations`, while model
training requires one location and `--list-rules` remains an explicit global
read. Ninety-five focused mocked CLI/scheduler checks pass. Scheduled execution
still requires one location, and the signed event handler is unchanged. This
is a CLI/query contract only; worker authorization, provider delivery, schedule
reconciliation, and RLS remain open. No MAN-CAP status changed
([evidence](builds/2026-10-16-recovery/anomaly-cli-location-scope.json)).

**14 October 2026 worker boundary update:** a machine-readable inventory now
matches the scheduler and event-handler allowlists and records their
source-visible data effects, scopes, providers, and replay limits. A regression
test prevents a new allowlisted entry from appearing without an inventory row.
Module-specific argument schemas now validate scheduler operations at
activation and dispatch, excluding unsupported human/destructive operations.
The source graph now follows locally inferred instance methods and all 20
literal metrics-registry entries. Its SQL join has a static function path for
175 of 196 unique execution sites; the remaining 21 belong to functions absent
from all current worker-root graphs, which does not prove they are dead code.
This improves code review but is not an authorization boundary:
other dynamic calls, existing task reconciliation, worker-specific identity,
and RLS remain open. The new static-only boundary preflight reports all 17 roots
as lacking signed tenant context and explicitly leaves live grants, migrations,
active schedules, and ownership unassessed. No MAN-CAP status or acceptance
count changes ([map](worker-operation-map.md); [function graph](worker-function-reachability.json); [SQL reachability](worker-sql-reachability.json); [static preflight](worker-boundary-preflight.json); [worker check evidence](builds/2026-10-14-recovery/worker-function-reachability-check.json); [SQL join evidence](builds/2026-10-14-recovery/worker-sql-reachability-check.json); [preflight evidence](builds/2026-10-14-recovery/worker-boundary-preflight-check.json); [inventory evidence](builds/2026-10-14-recovery/worker-operation-map-check.json); [argument-contract evidence](builds/2026-10-14-recovery/scheduled-command-contract-check.json)).

**13 October 2026 OIDC configuration update (CAP-001 / CAP-053):** the optional
OIDC overlay remains disabled unless explicitly selected. `.env.example` now
lists the required provider settings and identifies client/state secrets as
SOPS-only inputs; Compose checks confirm the default profile omits OIDC and the
selected overlay fails closed when settings are missing. The profile planner
now exposes `--oidc` only alongside the HTTPS proxy selection. The contract
suite also covers the minimal, edge, standard, analytics, and portability
manifests; 18 profile checks pass, including the explicit ARM64 guard. No real
provider credentials or browser session were configured, so login, grant
provisioning, CSRF, and console acceptance remain open.

**13 October 2026 platform-integrity source check (CAP-047):** the focused
migration, Gateway authorization, scheduler durability, event-bus durability,
carbon-credit, threatcasting, backcasting, and Delphi suites pass 279 tests.
Host-run Gateway app tests now use a private temporary audit journal, matching
the container's writable-spool contract. Ruff passes. The current source also
passes provider-boundary review (17 vendor import sites), and 12 dependency
groups/32 requirements align. Release-input locks match; no OCI archives were
supplied to the local release checker. This source-level evidence does not close
live provider state, external delivery, or broader recovery gates.

**13 October 2026 Phase 8 update:** the minimal app/PostGIS build inputs now
have a SHA-256 lock, and GitHub Actions is configured to build AMD64/ARM64 OCI
archives and compare resolved Python/PostGIS package versions. The current
local AMD64 app build succeeded; its ARM64 counterpart stopped at package-host
DNS failure. The first GitHub CI run built the images but failed archive
validation because the OCI index omitted platform labels; the checker now reads
missing labels from each image config and awaits a fresh run. Security surfaced
544 Gitleaks matches. Review traced them to
vendored OpenZeppelin fixtures, public EVM addresses, reproducibility hashes,
test identifiers, and documented credential placeholders. A narrow checked-in
Gitleaks allowlist and explicit config invocation now cover those reviewed
patterns; the full-history Security workflow passed on 13 October 2026. Two CI
runs exposed nested OCI indexes that the checker did not traverse; the current
PR fix recursively inspects nested manifests and falls back to image config
metadata. CI run 287 passed the AMD64/ARM64 app and PostGIS builds, locked
package comparison, and complete test workflow on commit `6549043`. Later PR
changes postdate that run, so current-head CI acceptance remains open.
Deployment settings remain pending, and no ARM64 runtime is certified
([release-input contract](kernel-release-inputs.md);
[local attempt evidence](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).
Hash-locked Python closures for the default app and optional ClickHouse profile
are now wired into the Kernel image; multi-architecture acceptance is pending.
The PostGIS build uses a dated Debian snapshot and exact PGDG package versions.
[CI run 284](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38449176283)
confirmed the signed-snapshot CA bootstrap and built both architecture images.
The inventory check then found the amd64-only `libquadmath0` package; its exact
version and absence on arm64 are now part of the SHA-256-locked package
contract. The checker permits only that exact reviewed difference and still
fails on any other package inventory mismatch. A clean CI rerun and hardware
acceptance remain open.

**CAP-038 isolated Kokonut Commons source identity — 23 October 2026:** migration 593 gives Kokonut Commons synthesis a dedicated signed login and reader for three location-or-network policy views plus two network-wide public catalogs; the broad shared synthesis reader retains no operational source projections. Each task now requires an explicit isolated source mapping, and the generic shared synthesis profile/environment template is removed. The focused worker/database/profile/migration selection passes 165 tests (36 migration-integrity tests); Ruff and Python compilation pass. Network-disabled PostgreSQL 16 applies/replays through 593 with 79 grouped assertions on native AMD64 and ARM64/QEMU. Signed synthetic rows verify owned/unassigned visibility, foreign exclusion, network catalog context, and no shared-reader projection grants ([migration](../schemas/postgres/593_isolated_kokonut_commons_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-kokonut-commons-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-kokonut-commons-identity-arm64-disposable.json)). QEMU is software portability evidence only. Candidate and legacy are untouched; migration 593 and real credentials/grants are not deployed. CAP-038 remains prepared pending grants, populated parity, live OIDC/provider/browser acceptance, broader ACL/RLS, production recovery, physical Raspberry Pi, and human review. Checklist: 1,019 complete / 24 open (1,043 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.
**CAP-038 retired shared synthesis source identity — 23 October 2026:** Migration 594 makes the historical shared synthesis login and reader inert after task-specific identities have replaced their source projections. It sets both roles to NOLOGIN/NOINHERIT, removes their reader membership and direct schema/relation/sequence/function privileges, and refuses unexpected ownership, memberships, or default ACLs. A disposable PostgreSQL 16 regression seeds stale grants and login/membership state, reapplies 594 after historical migration replays, then confirms the roles are inert; the 79-assertion native migration/source chain passes ([migration](../schemas/postgres/594_retire_shared_agent_source_identity.sql); [evidence](builds/2026-10-23-recovery/cap-038-retired-shared-agent-source-native-disposable.json)). Candidate and legacy remain untouched; migration 594 and real worker credentials/grants are not deployed. CAP-038 remains prepared, with credential provisioning, populated parity, live provider/browser acceptance, broader ACL/RLS, recovery, physical Raspberry Pi acceptance, and human review still open. Checklist: 1,020 complete / 24 open (1,044 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks accepted.

| ID | Capability | Owning code area | Named manual check and required result | Existing Python test candidates | Implementation / deployment progress |
|---|---|---|---|---|---|
| CAP-001 | Governed farm operations | schemas/postgres/; extensions/kokonut-hooks/ | MAN-CAP-001: Scoped farm draft, submit, independent verification and public eligibility | tests/test_phase5_source_of_truth.py | D — additive OpenAPI-backed `/api/v1/locations` list/detail routes use strict native response envelopes; legacy unversioned location routes now use the same governed five-field native projection and preserve their wrapper regardless of Directus feature flag. The `farm_activity_v1` source map and declarative workflow define human publication and rejection rework/exception disposition. Feature branch implements the OIDC/location-scoped private intake queue/detail, content-reviewed canonical draft promotion, and submit/verify/reject/rework/publish/exception-close transitions. Migration 383 adds source idempotency and draft evidence; migration 384 guards native 1.2.0 source lineage, legal status changes, active operator grants, independent submitter/verifier/rejection reviewer/publisher actors, immutable post-submission content, and append-only events while preserving legacy Field Collector rows. 77 focused migration, workflow, service, and OIDC tests passed; Ruff passed; migration and successful/denied lifecycle behavior passed in disposable PostgreSQL. Candidate migrations 383–384 and the lifecycle-write app are deployed to the healthy local candidate; 375 schemas and zero pending, with an exact-target encrypted checkpoint and isolated restore parity [rollout](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json). Latest source adds location-scoped canonical activity list/detail reads, explicit draft promotion and lifecycle controls, plus migration 385 and a native draft editor validated against the exact immutable form revision. The 95-test focused migration/workflow/lifecycle/OIDC/console suite and Ruff pass; all 376 ordered schemas replayed in disposable PostGIS 16, where a synthetic edit verified its changed-field list and content digest, append-only event protection, and rollback after injected event failure. Migration 385 is applied on the local candidate (376 applied schemas, zero pending) after a fresh encrypted checkpoint restore with matching migration fingerprints, extension versions, and workflow counts. Only the app was rebuilt from `f854d47`; health returned 200, unauthenticated review/activity/draft-edit routes returned 401, and PostgreSQL, Metabase, and proxy stayed up. The candidate has no farm-activity workflow rows. Migration 386 is now applied on the local candidate (377 applied schemas, zero pending) after a separate encrypted checkpoint restore rehearsal; only the app was rebuilt from `d22fa49`, health returned 200, and anonymous farm-activity/review routes returned 401 ([rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)). See [source evidence](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json) and [rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json). Directus remains optional; the six-role template covers the native Field Collector 1.2.0 workflow, while migration 404 adds a separate scoped Gateway path for non-Field-Collector farm-activity reads, drafts, and human lifecycle actions with append-only audit. Thirteen focused service/HTTP/policy tests and 11 disposable PostgreSQL checks pass; historical rows without Gateway audit provenance need reconciliation, migration 404 is applied on the candidate; other Directus collection/field/relation/hook parity remains open ([role mapping](builds/2026-10-16-recovery/farm-activity-gateway-role-mapping.json); [migration evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json)). The Directus create-time reference hook now rejects malformed explicit `location_id` values; the extension TypeScript build passes, but this does not authorize the user's tenant scope. CAP-001 remains partial pending configured-provider acceptance, populated workflow acceptance, and MAN-CAP-001. Report/metric implementation and full-schema PostGIS 16 integration pass; the expanded Batch 3 suite passes 90 tests and Ruff, including wrong-location query guards and injected event-write rollback; a real PostgreSQL trigger failure also rolled back the transition status and both event ledgers after all 375 schema migrations were applied to disposable PostGIS. Two simultaneous PostgreSQL duplicate-promotion calls passed; higher-contention stress, configured-provider acceptance, and MAN-CAP-001 remain open; capability is still partial. [Location contract](location-api-contract.md); [workflow map](farm-activity-workflow-map.md); [report/metric evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json) The optional Directus 12.1.1 fresh-profile seed baseline captures 175 effective stored rows across nine managed policies, including zero `farm_activity` permissions; seed replay is stable. A pinned-runtime API probe returns 403 `RESOURCE_RESTRICTED` for custom permission management, exposes Agent Write as read-only, and denies both Agent Write and Field Worker creates without persisting rows. This records the unlicensed Directus boundary and fail-closed behavior, not role/field parity or MAN-CAP acceptance ([permission snapshot](builds/2026-10-23-recovery/directus-effective-permission-rows.json); [runtime probe](builds/2026-10-23-recovery/directus-effective-permissions.json)). |
| CAP-002 | Precision agriculture | services/analytics/; services/gateway/yield_monitoring.py; services/gateway/yield_monitoring_routes.py; services/gateway/irrigation_status.py; services/gateway/irrigation_routes.py; services/gateway/crop_simulations.py; services/gateway/crop_simulation_routes.py; services/gateway/nutrient_balances.py; services/gateway/nutrient_soil_tests.py; services/gateway/nutrient_events.py; services/gateway/nutrient_balance_routes.py; schemas/postgres/601_nutrient_input_cost_currency.sql | MAN-CAP-002: Yield, irrigation, crop simulation and nutrient outputs match frozen fixtures | tests/test_yield_monitoring.py; tests/test_precision_irrigation.py; tests/test_digital_twin.py; tests/test_gateway_yield_monitoring.py; tests/test_gateway_irrigation_status.py; tests/test_gateway_crop_simulations.py; tests/test_gateway_nutrient_balances.py; tests/test_gateway_nutrient_soil_tests.py; tests/test_gateway_nutrient_events.py; tests/test_operator_console_yield_monitoring.py; tests/test_operator_console_irrigation_status.py; tests/test_operator_console_crop_simulations.py; tests/test_operator_console_nutrients.py | P — tenant-scoped Gateway reads cover verified/published yield summaries grouped by stored unit, bounded active irrigation-zone status, completed crop-simulation run summaries and paginated run detail/daily-state reads with deterministic seeded weather regression coverage, grouped N/P/K balances from the verified/published latest-budget view, paginated recorded/verified soil-test observations with advisory N/P/K rates, and paginated input/removal records with explicit event/parent lifecycle statuses. Each read requires an exact location grant and signed context; irrigation status location-matches sensor readings, while simulation summaries/details expose no raw parameters/errors/metadata/financial values and state pages remain bounded; nutrient balances omit plot/budget identifiers, product-level inputs, and costs; soil-test and event reads omit notes/metadata and suppress plot IDs whose farm is outside the requested location; event reads also omit costs and unreviewed source text. The simulation routes read persisted outputs only; they do not run the model. The legacy engine now uses process-independent SHA-256 weather jitter keyed by `weather_seed` (default 0); a two-seed synthetic fixture passes under two Python hash seeds, but is not legacy/populated parity or agronomic validation. Synthetic tests pass. The operator console exposes yield summaries under exact `yield_monitoring:read`, advisory irrigation status under separate exact `precision_irrigation:read`, completed crop-simulation runs/daily states under exact `digital_twin:read`, and allowlisted nutrient balance, soil-test, input, and removal views under exact `nutrient_budget:read` location grants. Reads use same-origin/no-store paging, response scope/page correlation, stale-response guards, and fixed text-rendered fields; yield units remain separate, classified nutrient costs retain currency, and simulation reads never execute a model. The combined CAP-002 console/Gateway/domain/route-policy selection passes 191 tests, including inline JavaScript syntax; Ruff, matrix validation, and diff checks pass. No migration, provider, candidate, or legacy database was used ([yield evidence](builds/2026-10-23-recovery/cap-002-yield-monitoring-console.json); [irrigation evidence](builds/2026-10-23-recovery/cap-002-irrigation-console.json); [simulation evidence](builds/2026-10-23-recovery/cap-002-crop-simulation-console.json); [nutrient evidence](builds/2026-10-23-recovery/cap-002-nutrient-console.json)). Historic cost-currency reconciliation, simulation model and frozen-fixture/populated parity, live OIDC/browser acceptance, RLS, and MAN-CAP-002 remain open ([yield contract](yield-monitoring-kernel-read-contract.md); [irrigation contract](irrigation-status-kernel-read-contract.md); [simulation contract](crop-simulation-runs-kernel-read-contract.md); [nutrient operations console contract](nutrient-operations-console-contract.md); [nutrient balance contract](nutrient-balances-kernel-read-contract.md); [soil-test contract](nutrient-soil-tests-kernel-read-contract.md); [nutrient-events contract](nutrient-events-kernel-read-contract.md)). |
| CAP-003 | Traceability | services/analytics/traceability.py; services/gateway/traceability.py; services/gateway/traceability_routes.py | MAN-CAP-003: Forward/backward custody trace and quality records match reference batch | tests/test_traceability.py; tests/test_gateway_traceability.py; tests/test_operator_console_traceability.py | P — initial read-only Kernel path exposes exact-location batch list/detail with bounded custody, quality, certification, food-safety, and provenance records under `traceability:read`. Sensitive actor identities, free text, GPS, evidence URLs, and arbitrary metadata are omitted. The operator console also provides a grant-gated bounded batch list/detail surface with status filtering, same-origin no-store requests, stale-response guards, and text-only fixed-field rendering. The 18-test console/Gateway/route-policy selection and inline JavaScript syntax pass; Ruff and capability validation pass. No migration, candidate, legacy database, provider, or chain was used. Populated legacy-output parity, live ZITADEL/browser acceptance, broader RLS/runtime-role boundaries, audience review, and MAN-CAP-003 remain open ([contract](traceability-kernel-read-contract.md); [read evidence](builds/2026-10-23-recovery/cap-003-traceability-kernel-read.json); [console evidence](builds/2026-10-23-recovery/cap-003-traceability-console.json)). |
| CAP-004 | Extension & peer learning | services/analytics/extension.py; services/gateway/extension_learning_reads.py; services/gateway/extension_learning_routes.py; services/gateway/operator_auth.py; docs/refactor/extension-learning-kernel-read-contract.md | MAN-CAP-004: Enroll, deliver and assess learning with peer-group scope preserved | tests/test_extension.py; tests/test_gateway_extension_learning_reads.py; tests/test_operator_console_extension_learning.py; tests/test_operator_route_policy_inventory.py | P — exact-location OIDC reads provide a paginated active public module catalog and group learning progress, content delivery, assessment counts, and peer-network/member counts. The repeatable-read transaction sets signed tenant context before location-filtered queries; the response contains no participant identities, individual scores, narratives, contacts, delivery errors, or arbitrary metadata. The OIDC console displays grouped counts and a paginated active public catalog only for exact location grants; fixed fields render via textContent, requests are same-origin/no-store, and stale responses are discarded. Allowlisted filters, bounded pages, source/mock checks, and exact route-policy coverage pass; the combined 15-test selection, Ruff, inline JavaScript syntax, and matrix validation pass. No migration, provider, candidate, or legacy database was used. Populated parity, audience/privacy review, live OIDC/browser behavior, direct-database ACL/RLS, and MAN-CAP-004 remain open ([contract](extension-learning-kernel-read-contract.md); [summary evidence](builds/2026-10-23-recovery/cap-004-extension-learning-summary.json); [console evidence](builds/2026-10-23-recovery/cap-004-extension-learning-console.json)). |
| CAP-005 | Farmer identity & cooperatives | services/analytics/; services/gateway/cooperative_management_reads.py; services/gateway/cooperative_management_routes.py; apps/operator-console/index.html; docs/refactor/cooperative-management-kernel-read-contract.md | MAN-CAP-005: Profile credentials, membership and asset-booking scopes remain isolated | tests/test_farmer_identity.py; tests/test_cooperative.py; tests/test_gateway_cooperative_management_reads.py; tests/test_operator_console_cooperative_management.py; tests/test_operator_route_policy_inventory.py | P — first exact-location Kernel read at `GET /operator/api/cooperatives/{location_id}/summary` requires `cooperative_management:read`, sets signed tenant context before read-only aggregate queries, and returns cooperative/type/status counts, active membership counts, asset type/status counts, and booking status counts. Memberships require their exact location; asset/booking joins remain anchored to the same-location cooperative, and booking rows also require same-location membership. The hidden-by-default operator panel renders only fixed aggregate fields as text; member identities, credentials/KYC, booking detail, financial values, GPS, evidence, and metadata stay omitted. Twelve focused Gateway/console/route-policy checks pass; Ruff, Python compilation, inline JavaScript syntax, runtime SQL inventory, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-005 remains prepared: profile/credential workflows, populated-output parity, live OIDC/browser acceptance, least-privilege database roles/RLS, audience/privacy review, and MAN-CAP-005 remain open ([contract](cooperative-management-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-005-cooperative-management-kernel-read.json)). |
| CAP-006 | Energy, waste & landscape | services/analytics/; services/gateway/energy_monitoring.py; services/gateway/energy_monitoring_routes.py; services/gateway/waste_management_reads.py; services/gateway/waste_management_routes.py; services/gateway/waste_management_writes.py; services/gateway/operator_auth.py; schemas/postgres/613_location_waste_stream_capture.sql; schemas/postgres/614_location_composting_capture.sql; schemas/postgres/615_location_recycling_capture.sql; schemas/postgres/616_location_pollution_incident_gateway.sql; services/gateway/waste_management_incidents.py; scripts/check-waste-stream-capture-disposable.py; scripts/check-waste-management-disposable.py; services/gateway/landscape_conservation_reads.py; services/gateway/landscape_conservation_routes.py; services/gateway/pollinator_health_reads.py; services/gateway/pollinator_health_routes.py; services/gateway/pollinator_health_writes.py; schemas/postgres/619_location_pollinator_observation_capture.sql; schemas/postgres/620_location_pesticide_impact_capture.sql; schemas/postgres/621_location_pollinator_habitat_capture.sql; schemas/postgres/622_location_pollinator_hive_capture.sql; schemas/postgres/623_location_pollinator_hive_inspection_capture.sql; schemas/postgres/624_location_pollinator_habitat_lifecycle.sql; scripts/check-pollinator-habitat-lifecycle-disposable.py; tests/test_gateway_pollinator_habitat_lifecycle.py; schemas/postgres/625_location_pollinator_hive_lifecycle.sql; scripts/check-pollinator-hive-lifecycle-disposable.py; tests/test_gateway_pollinator_hive_lifecycle.py; schemas/postgres/626_location_pollinator_independent_review.sql; schemas/postgres/627_location_pollinator_hive_inspection_review.sql; scripts/check-pollinator-review-disposable.py; tests/test_gateway_pollinator_review.py; scripts/check-pollinator-observation-capture-disposable.py; scripts/check-pollinator-hive-inspection-disposable.py; scripts/check-pollinator-hive-capture-disposable.py; scripts/check-pesticide-impact-capture-disposable.py; scripts/check-pollinator-habitat-capture-disposable.py; apps/operator-console/index.html; schemas/postgres/154_landscape_conservation.sql; schemas/postgres/155_pollinator_health.sql; schemas/postgres/602_pollinator_health_kernel_alignment.sql; schemas/postgres/603_location_bound_landscape_references.sql; schemas/postgres/604_energy_reading_cost_currency.sql; services/analytics/landscape_reference_preflight.py; scripts/check-energy-reading-cost-currency-disposable.py; scripts/check-pollinator-health-disposable.py; scripts/check-landscape-reference-location-disposable.py; scripts/landscape-reference-preflight.py; docs/refactor/landscape-pollinator-kernel-read-contract.md; docs/refactor/energy-monitoring-kernel-read-contract.md; docs/refactor/waste-management-kernel-read-contract.md | MAN-CAP-006: Energy, waste, habitat and pollinator calculations preserve units and evidence | tests/test_gateway_energy_monitoring.py; tests/test_operator_console_energy_monitoring.py; tests/test_gateway_waste_management_reads.py; tests/test_gateway_waste_management_writes.py; tests/test_gateway_waste_management_incidents.py; tests/test_operator_console_waste_management.py; tests/test_migration.py; tests/test_gateway_landscape_pollinator_reads.py; tests/test_gateway_pollinator_observation_capture.py; tests/test_gateway_pollinator_habitat_lifecycle.py; tests/test_gateway_pollinator_hive_lifecycle.py; tests/test_gateway_pollinator_review.py; tests/test_operator_console_landscape_pollinator.py; tests/test_operator_route_policy_inventory.py; tests/test_energy_monitoring.py; tests/test_waste_management.py; tests/test_landscape_conservation.py; tests/test_pollinator_health.py; tests/test_landscape_reference_location.py; tests/test_landscape_reference_preflight.py | P — exact-location energy_monitoring:read, waste_management:read, landscape_conservation:read, and pollinator_health:read grants now expose signed-context, read-only Gateway summaries and independently grant-gated console panels. Energy includes verified/approved kWh plus 30-day consumption/production/net, legacy-defined renewable-use share, a seven-day trend, an explicitly advisory fixed-factor carbon estimate plus monthly carbon-offset and net-emissions compatibility estimates derived from active registered offsets, both explicitly advisory and unclamped; active energy-source counts/capacity by fixed source type, and active registered-renewable count/capacity/annual-generation/offset aggregates with capped indicative generation coverage based on reviewed 365-day consumption; reviewed 30-day energy-cost totals are grouped by recorded currency, unclassified historic amounts are counted but withheld, and mixed/incomplete currency totals are omitted; its latest 12 daily efficiency-log entries are filtered to verified/approved status and omit notes, metadata, and unclassified cost-per-unit output, with persisted metrics labeled advisory; waste includes verified waste, compost, and recycling totals without cross-unit conversion plus descriptive incident counts; migrations 613–616 add exact-location `waste_management:create` capture for waste streams, composting, recycling, and pollution incidents with recorded/open lifecycles, bounded category mapping, isolated writer functions, and private append-only SHA-256 retry receipts; incident review queues and resolution require a separate `waste_management:review` grant and attribute the reviewer; capture/review forms are independently gated and never verify or publish; legacy waste, composting, recycling, incident, pollinator-observation, pesticide-report, habitat-create, add-hive, and record-inspection CLI writers fail closed before database access; migrations 615/616/619 revoke the migrated runtime and Directus direct writes while preserving required reads; migrations 619–623 add attributed recorded-only observation, pesticide-impact, and hive-inspection capture plus self-reported habitat and managed-hive inventory under exact `pollinator_health:create`, private digest receipts, and same-location plot/hive validation; legacy `open-incidents` and mixed `dashboard` helper/CLI paths now fail before cursor or connection access, preserving the independent authenticated summary and review surfaces; landscape inventories retain statuses and units and expose legacy active-habitat/corridor aggregates; buffer rates use verified checks only, and biodiversity means use verified/published states; pollinator observations and pesticide reports use verified/reviewed states, separately from descriptive habitat and active-hive inventory. Pollinator trend aggregates preserve the 30-day/equal-15-day comparison and +/-10% thresholds; the 90-day pesticide advisory preserves legacy mortality/high-toxicity thresholds while excluding unreviewed rows; active-hive summaries include the mean scored 0–10 strength. These indicators remain advisory and do not determine ecological condition or pesticide safety. Responses omit names, geometry, narrative, plot/species/hive IDs, notes, and arbitrary metadata. The initial combined Gateway, console, and route-policy selection passes 42 tests; the later 40-test CAP-006 Gateway/console/domain selection covers trend thresholds, pesticide-risk classification, and hive-score calculations. Ruff, Python compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. The new legacy-service slice applied/replayed migrations 155/602 only in disposable PostgreSQL; candidate/legacy databases and providers were untouched. CAP-006 remains prepared pending habitat status/maintenance and hive registration/inspection capture, populated-fixture parity, independent review, broader database ACL/RLS and Directus parity, live OIDC/browser acceptance, and MAN-CAP-006. Migration 602 additively aligns the legacy pollinator analytics service to migration 155, restores structured source and measurement fields, adds location-bound hive inspection history, and enforces same-location hive links. Fifteen service tests pass within the 35-test CAP-006 selection; disposable PostgreSQL 16 applies/replays 155/602 and passes six grouped schema/read-write/location-link checks. The candidate remains unchanged and 602 is not rolled out. The legacy CLI still uses a shared-identity database connection and is not tenant-safe; operator context/ACL/RLS remains a gate. Migration 603 adds NOT VALID location-composite FKs for corridor and buffer habitat links and location-qualifies the legacy summary/status/compliance views. Historical mismatches remain unrewritten but no longer resolve foreign habitat names/counts; new cross-location writes fail, and eight disposable PostgreSQL checks pass on apply/replay. An operator-run repeatable-read/read-only preflight now returns only global counts for the three fixed reference types; four unit checks pass and a synthetic disposable fixture verifies mismatch counts without leaking identifiers. This tool does not authorize repairs or close historical constraint validation. The 71-test migration/landscape/Gateway selection passes; candidate and legacy remain untouched, while historical review and later FK validation remain open. ([energy contract](energy-monitoring-kernel-read-contract.md); [waste contract](waste-management-kernel-read-contract.md); [landscape and pollinator contract](landscape-pollinator-kernel-read-contract.md); [energy evidence](builds/2026-10-23-recovery/cap-006-energy-kernel-read.json); [waste evidence](builds/2026-10-23-recovery/cap-006-waste-kernel-read.json); [landscape and pollinator evidence](builds/2026-10-23-recovery/cap-006-landscape-pollinator-kernel-read.json); [pollinator schema acceptance](builds/2026-10-23-recovery/cap-006-pollinator-health-disposable.json); [landscape reference acceptance](builds/2026-10-23-recovery/cap-006-landscape-reference-location-disposable.json); [pollinator calculation parity](builds/2026-10-23-recovery/cap-006-pollinator-calculation-parity.json); [landscape calculation parity](builds/2026-10-23-recovery/cap-006-landscape-calculation-parity.json); [energy calculation parity](builds/2026-10-23-recovery/cap-006-energy-calculation-parity.json); [registered renewable metrics](builds/2026-10-24-recovery/cap-006-registered-renewable-parity.json)). The landscape summary now returns active habitat/corridor calculations and a verified-only buffer rate; its explicitly named legacy connectivity ratio is labeled as a compatibility formula, not a network metric. The 54-test focused Gateway/console/reference selection passes with eight migration subtests; Ruff, Python compilation, Node syntax, runtime SQL inventory, matrix validation, and diff checks pass. The waste Gateway summary now reports verified compost output, weighted and mean batch yield, duration, temperature/moisture averages, and graded-batch counts by feedstock/method; the console labels them descriptive and advisory. It omits grade labels, pH, and raw records. Eleven focused Gateway/console checks plus Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks pass without a migration or database. Compost quality scoring/certification and populated parity remain open ([contract](waste-management-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-composting-efficiency.json)). The legacy waste CLI summary now reads canonical migration-153 `waste_stream` / `record_date` fields, keeps its response shape, binds a positive day window, and filters verified rows; 22 waste-management tests (including five invalid-window subtests), Ruff, and compilation pass. No database or migration was used. This trusted CLI path does not add tenant authorization ([compatibility evidence](builds/2026-10-24-recovery/cap-006-legacy-waste-summary-schema-alignment.json)). The legacy composting-efficiency reader uses canonical `finished_volume_kg` and `compost_date`, computes yield, reads verified rows only, and returns numeric pH from JSONB metadata when present. The legacy writer now inserts canonical migration-153 fields as `recorded`, maps accepted category and method aliases, preserves freeform inputs and pH in metadata, and closes its cursor on errors. The 24-test waste-management module with five invalid-window subtests, Ruff, compilation, runtime SQL inventory, matrix validation, and diff checks pass without database or migration access; other legacy waste parity and tenant isolation remain open ([evidence](builds/2026-10-24-recovery/cap-006-legacy-composting-efficiency-schema-alignment.json)). The legacy `record_waste` CLI now writes canonical `waste_stream` rows in `recorded` state, maps the supported organic alias, and preserves other labels and source in metadata. Its schema regression is included in the 24-test suite; no database or migration was used. Recycling and incident CLI paths now use canonical migration-153 tables and lifecycle states; populated parity remains open ([evidence](builds/2026-10-24-recovery/cap-006-legacy-waste-stream-write-schema-alignment.json)). The legacy recycling CLI writer now inserts canonical `recycling_log` rows with `record_date` and `recorded` status while preserving destination, revenue, notes, and metadata. Its schema regression is covered by the same 24-test module; no migration or database was used. Incident CLI schema alignment is documented in the following slice ([evidence](builds/2026-10-24-recovery/cap-006-legacy-recycling-write-schema-alignment.json)). A follow-up maps unsupported recycling material labels to `other` and retains the supplied value in metadata; the synthetic `steel_scrap` regression passes in the existing 24-test module ([evidence](builds/2026-10-24-recovery/cap-006-recycling-material-fallback.json)). The legacy incident report/resolve/summary CLI paths now use canonical migration-153 fields, retain reporter and unsupported type labels in metadata, set the resolved flag and timestamp, and include all unresolved lifecycle states in the queue. The 24-test module covers this SQL contract without database access. Tenant authorization and populated incident parity remain open ([evidence](builds/2026-10-24-recovery/cap-006-legacy-incident-lifecycle-schema-alignment.json)). The full legacy CLI schema contract also passes against migration 153 on disposable PostgreSQL 16: all writers, default states, category mappings, verified/scoped reads, and incident resolution passed seven acceptance groups. Candidate and legacy databases were not used ([runner](../scripts/check-waste-management-disposable.py); [evidence](builds/2026-10-24-recovery/cap-006-waste-management-disposable.json)). |
| CAP-007 | Metrics & analytics | services/metrics/; services/analytics/ | MAN-CAP-007: Compute draft values; independent reviewer verifies; analytics totals match fixture | tests/test_metrics.py | D — native public metric reads/models deployed, now also exposed through the explicitly public `/api/v1/metrics/{location_id}` route; projection/job boundaries prepared; Directus and Metabase roles verified in isolated copies; pinned Metabase starts on populated metadata, with its only saved board classified as generic e-commerce demo content. The source-aligned scratch applied all 369 current migrations through 378, reported zero pending, and passed actual-view grants and rollback-only reporting probes. The transactional runner replay validated all 369 current schema checksums and rollback of injected DDL plus ledger state (both were zero after injected failure); the separate populated clone accepted all 25 pending archived migrations, with zero pending and unchanged original-column fingerprints across 16 tables. The archived app plan remains at zero checksum drift and 25 unapplied migrations. Focused migration suite: 22 passed. SAFE seed values were verified against Gnosis Chain. Six historical NOI snapshots were stale; migration 379 and the reconciliation path brought the isolated clone to zero view mismatches. The active candidate checkpoint and isolated restore passed; all 370 current schema sources also passed on a fresh scratch. The candidate's exact historical `schema:000_extensions.sql` checksum was repaired through the audited path after all six extension effects were verified; migrations 371–379 applied transactionally and the exact-target plan now reports zero pending across 370 applied schema files. Its reporting views and NOI unique index exist. The candidate API still uses its owner credential. A separate `kokonut_analytics_ro` login is provisioned and passed real-login checks for the three curated views, denial on application tables/private policy/DDL/temp tables, and denial on all other candidate databases. Eight extension metadata relations and 1,165 extension functions remain accessible through inherited PUBLIC grants; none of the public-executable extension functions is SECURITY DEFINER. The candidate Metabase profile now registers the read-only `Kokonut Reporting Views` source, filters it to `kokonut_reporting`, and lists only its three approved views. Three first-party cards and a dashboard execute successfully with zero rows on the empty candidate; exact exported card SQL passed populated-fixture output parity, including publication and date-window rules, and the full metadata restore matched inventory ([card output parity](builds/2026-10-11-recovery/metabase-card-output-parity.json)). The populated source has zero published metric policies; the rollback-only synthetic fixture passed the nonempty period/method/review-field probe. Farm-summary and Celo-attestation view parity passed on a disposable populated copy. All 94 report generators now have read-only calculation guards; a disposable PostgreSQL acceptance found and closed an autocommit escape, while the application identity remains a writer and populated output parity remains open ([report guard](builds/2026-10-15-recovery/report-generator-readonly-disposable.json)). [NOI reconciliation](noi-snapshot-reconciliation.md); [NOI evidence](builds/2026-10-11-recovery/noi-snapshot-parity.json); [NOI index migration](../../schemas/postgres/379_noi_snapshot_crop_cycle_key.sql); [Report contract](metabase-reporting-contract.md); [populated view parity](builds/2026-10-11-recovery/populated-report-view-parity.json); [candidate preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json); [compatibility review](pending-migration-compatibility-review.md); [drift triage](migration-checksum-drift.md); [reporting migration](../../schemas/postgres/377_kokonut_reporting_contract.sql); [reads](native-metric-reads.md); [roles](optional-database-roles.md); [source disposition](metabase-source-inventory.md); [reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json); [transaction evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json); [populated clone evidence](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json); [report/query source map](reporting-parity-inventory.md); [archive metadata](builds/2026-10-13-recovery/reporting-archive-inventory.json)  Location-scoped, read-only SDK groups now expose stored `metric_value`, forecast scenario/output, time-series and demand forecast, and market-size records. They do not compute or verify outputs. Public-interest report context now closes its database cursor on every success/error exit; its focused governance suite passes five tests, Ruff and compilation pass, and the runtime SQL source inventory is current. This is resource cleanup only; report authorization, populated parity, and MAN-CAP-007 remain open ([cursor evidence](builds/2026-10-22-recovery/report-context-cursor-cleanup.json); [SDK evidence](builds/2026-10-18-recovery/sdk-forecast-read-methods.json)). The 29 October source-only query hardening now includes exact nine-column TCO, 17-column technology-roadmap, and migration-284 competitive-health projections; focused mock-cursor checks preserve filters, binding, and payload ([TCO evidence](builds/2026-10-29-recovery/climate-tco-sdk-parity.json); [roadmap and competitive-health evidence](builds/2026-10-29-recovery/kernel-worker-input-and-competitive-projection.json)). Populated report parity and MAN-CAP-007 acceptance remain open. Migration-207 `v_capability_dashboard` now uses the exact 15-column projection, and Predictive BPM rejects non-finite/negative age and SLA inputs before database access; 20 focused Python checks pass ([evidence](builds/2026-10-29-recovery/kernel-analytics-and-ecocredit-input-contracts.json)). These source checks do not close populated parity or MAN-CAP-007. |
| CAP-008 | Trend analysis & geostatistics | services/trends/; services/geostatistics/; services/gateway/trend_analysis_reads.py; services/gateway/trend_analysis_routes.py; services/gateway/trend_forecast_compute.py; services/gateway/geostatistics_reads.py; services/gateway/geostatistics_routes.py; apps/operator-console/index.html; docs/refactor/trend-analysis-kernel-read-contract.md; docs/refactor/geostatistics-kernel-read-contract.md | MAN-CAP-008: Forecast, variogram and spatial validation outputs match tolerance-defined fixtures | tests/test_geostatistics.py; tests/test_gateway_trend_analysis_reads.py; tests/test_gateway_geostatistics_reads.py; tests/test_operator_console_trend_analysis.py; tests/test_operator_console_geostatistics.py; tests/test_operator_route_policy_inventory.py | P — the first Kernel path exposes each location's latest stored `trend_estimate` per metric through a bounded exact-location `trend_analysis:read` route after signed tenant context. Its projection contains period, data-point count, saved slope/fit/confidence fields, and timestamp; IDs, raw measurements, model parameters, metadata, and forecasts are omitted. Non-finite saved doubles become `null`. The hidden-by-default operator panel pages estimates and loads smoothing, change-point, seasonal-decomposition, and forecast outputs on demand for a selected estimate. A separate exact `trend_analysis:compute` grant exposes CSRF-protected advisory forecast generation from verified location observations, with transactional persistence and identical-input reuse. A shared exact `geostatistics:read` panel exposes saved spatial-autocorrelation, cross-validation, fitted-variogram, sensor-network-design, aggregate kriging, and realization summaries, plus on-demand paged kriging predictions and simulation points. Aggregate summaries omit point records/coordinates/values; kriging detail adds prediction variance and standard deviation, while simulation detail returns simulated values; both use hidden request handles, fixed fields, and text-only rendering; the point detail returns only sequence, WGS84 position, and advisory simulated value under the granted location. Its UUID is an internal request handle, never displayed; point UUIDs, seeds, variogram IDs, notes, interpretation, and arbitrary metadata remain omitted; spatial-block CV includes only bounded aggregate folds with sample suppression, while leave-one-out point diagnostics stay private. The legacy cross-validation runner also requires an explicitly selected variogram model to match the requested location and property before loading points, returning a generic not-found result on mismatch. Leave-one-out aggregates also keep successful predictions paired with their matching held-out observations when a fold fails. The database paths for variogram fitting, spatial autocorrelation, kriging, simulation, and cross-validation share a fixed location/property query helper: only `soil_carbon`, `soil_moisture`, `soil_ph`, and `ndvi` are supported, each soil key maps to a fixed column, and unsupported keys fail before connect. Explicit kriging and simulation variogram IDs must match location and property. Legacy variogram fitting now uses GSTools nonlinear robust optimization; synthetic curves verify all four model families. Matérn smoothness remains at the library default because it is not persisted by the current schema. Empirical lag fitting now uses fixed-width bins, centered tolerance selection, and a maximum pair-distance bandwidth, with counts and semivariances derived from the same selected pairs; the CLI exposes and preflights these settings. Legacy ordinary, simple, and indicator kriging enforce nearest-neighbor/search-radius limits, return null for cells outside the search radius, and persist local meter grids only after inverse conversion to WGS84. Legacy simulation uses seeded GSTools `CondSRF` conditional fields rather than a dense grid covariance/Cholesky factor, with pre-generation resource caps, WGS84 persistence, and a bounded configurable RandMeth mode count (`--mode-no`, default 1,000) recorded alongside generator/version settings in JSONB metadata. A 512-realization synthetic regression compares exponential conditional moments for nugget 0 and 0.2 against ordinary kriging; spherical and Gaussian have additional 128-draw moment checks at 100 RandMeth modes and nugget 0.2, while Matérn retains finite-draw smoke coverage. This remains synthetic model-consistency evidence, not populated parity or scientific acceptance. The panel validates location/page/strategy/model correlation; suppresses stale results; bounds component previews to 200 values and forecasts to 100 steps; and renders fixed fields as text. Trend outputs, CV measures, spatial statistics, variogram fits, sensor-network estimates, kriging summaries, and realization aggregates are advisory, while change-point status is displayed as recorded without lifecycle actions. The focused 43-test forecast-generation selection and 60-test geostatistics-summary selection pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, and capability validation. No migration, provider, candidate, or legacy database was used. CAP-008 remains prepared pending scientific and populated-data parity, per-point kriging output parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 ([contract](trend-analysis-kernel-read-contract.md); [generation evidence](builds/2026-10-24-recovery/cap-008-forecast-generation.json); [saved-read evidence](builds/2026-10-24-recovery/cap-008-saved-forecast-kernel-read.json)). |
| CAP-009 | Systems thinking | services/systems/ | MAN-CAP-009: Causal-loop, leverage and stock-flow model outputs preserve linked evidence | tests/test_stock_flow_mental.py | B — baseline code retained; persisted systems-thinking SDK reads partially implemented; computational parity remains unassessed. Causal-loop and stock-flow definitions, saved runs, location variables, archetypes, leverage assessments, time delays, and structural assumptions now have typed read-only access; causal links are constrained to their loop ID. Stakeholder `mental_model` reads remain unexposed because that table has no location scope. The SDK does not evaluate loops, simulate models, detect archetypes, or select interventions ([evidence](builds/2026-10-18-recovery/sdk-systems-thinking-read-methods.json)). |
| CAP-010 | OODA loop & adaptive decisions | services/orientation/; services/decision/ | MAN-CAP-010: Observe/orient/decide outputs remain advisory until approved action | tests/test_ooda_cycles.py; tests/test_decision_policy.py | B — baseline code retained; persisted situation assessments, assessment evidence, and OODA cycle logs now have schema-parity-guarded read-only Python/TypeScript access scoped by location or parent assessment. This exposes saved advisory records only; decision-policy approval and action execution remain outside these SDK methods. Approved adapter execution errors are class-only in returned failures with rollback and cursor cleanup covered. MAN-CAP-010, live-provider behavior, and decision/action parity remain open ([evidence](builds/2026-10-18-recovery/sdk-ooda-advisory-read-methods.json)). |
| CAP-011 | Process intelligence | services/analytics/ | MAN-CAP-011: Variants, cycle times, conformance and SLA estimates match fixture | tests/test_process_mining.py; tests/test_predictive_bpm.py | B — baseline code retained; Kernel capability path and parity unassessed. Process-simulation failure responses now redact raw calculation exception details; this does not establish output parity. |
| CAP-012 | Process architecture & costing | services/analytics/process_architecture.py | MAN-CAP-012: Process maps, interfaces and cost totals preserve ownership and lineage | tests/test_process_architecture.py; tests/test_process_costing.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-013 | Impact accountability | services/analytics/; services/registry/; services/agents/cids_agent.py; services/agents/worker_cli.py; schemas/postgres/546_signed_cids_export_source.sql | MAN-CAP-013: Evidence maturity, impact claims, participation and CIDS public export enforce consent | tests/test_ebf_gates.py; tests/test_cids_export.py; tests/test_agent_worker_cli.py; scripts/check-agent-worker-ai-summary-disposable.py | P — the CIDS CLI/agent now reads six minimal security-barrier projections through a dedicated `cids_export/read` scope in a repeatable-read, read-only source-worker transaction. Migration 546 preserves exact-location RLS under forced policies and the existing `ai_summary/read` path while withholding raw feedback text. Focused unit, native, and ARM64/QEMU disposable PostgreSQL checks pass; populated output parity, grant provisioning, live OIDC/runtime acceptance, and MAN-CAP-013 remain open ([native evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-arm64-disposable.json)). |
| CAP-014 | CRISP risk scoring | services/crisp/ | MAN-CAP-014: Five dimensions, configured weights and composite rating match baseline | tests/test_crisp_scoring.py | D — published-assessment GET and additive `/api/v1/crisp/{location_id}` alias are source-defined. Typed, schema-parity-guarded Python/TypeScript read-only methods now expose private stored assessments and all five location/assessment-linked dimension records; weights/configuration are not exposed. The SDK reads persisted scores and evidence only; five-dimension scoring, configured-weight, and output parity remain open ([contract](public-summary-contracts.md); [evidence](builds/2026-10-18-recovery/sdk-crisp-stored-assessment-reads.json)). |
| CAP-015 | Organic certification readiness | services/analytics/organic_certification.py | MAN-CAP-015: Input, buffer and segregation evidence produce same readiness score | tests/test_organic_certification.py | P — typed, schema-parity-guarded, read-only Python/TypeScript SDK groups prepare Directus-backed reads for location-scoped certification, transition, prohibited-substance, buffer, input-audit, harvest-handling, compliance-checklist, and readiness-assessment records. Directus remains optional, so these reads do not establish the Kernel access path. Readiness scoring, standard-specific rules, Gateway parity, and baseline output parity remain open ([evidence](builds/2026-10-18-recovery/sdk-organic-compliance-reads.json)). |
| CAP-016 | True cost accounting | services/analytics/true_cost_accounting.py; services/gateway/true_cost.py | MAN-CAP-016: Hidden costs, valuations and cross-capital flows match fixture | tests/test_true_cost_accounting.py; tests/test_gateway_true_cost.py | P — a location-scoped OIDC operator route now returns the existing true-cost statement, hidden-cost, natural/social valuation, and cross-capital aggregate outputs from one read-only transaction after database-verified tenant context. The response includes aggregates only; Directus is not required. Calculation/output parity, domain-table RLS, live candidate/provider acceptance, and MAN-CAP-016 remain open ([evidence](builds/2026-10-18-recovery/gateway-true-cost-aggregate-read.json)). |
| CAP-017 | Emergency response | services/analytics/emergency_response.py; services/gateway/emergency_response.py | MAN-CAP-017: Incident, response and recovery workflow retains approval/evidence history | tests/test_emergency_response.py; tests/test_gateway_emergency_response.py | P — an OIDC-protected, location-scoped Gateway summary returns incident counts, recovery timing, deadline compliance, affected-area and financial aggregates from read-only SQL after signed tenant context. It omits incident narratives and actions. Incident CRUD, governed workflow/audit history, calculation parity, domain-table RLS, populated fixtures, and MAN-CAP-017 remain open ([evidence](builds/2026-10-18-recovery/gateway-emergency-response-summary.json)). |
| CAP-018 | EAS on Celo | services/attestation/; services/gateway/attestations.py | MAN-CAP-018: Prepare and verify proof metadata without broadcasting or exposing private evidence | tests/test_attestation.py; tests/test_gateway_attestations.py | P — an OIDC-protected location route returns stored Celo attestation/schema identifiers, lifecycle status, and chain references after database-verified tenant context. Claim data, evidence hashes/CIDs/URLs, and reviewer notes are excluded. This is stored metadata only, not live chain verification; publish/revoke remains human-approved, and candidate/provider, full proof, RLS, and MAN-CAP-018 acceptance remain open ([evidence](builds/2026-10-18-recovery/gateway-attestation-metadata-read.json)). |
| CAP-019 | Ecocredit module | services/credit_class/; services/gateway/ecocredits.py | MAN-CAP-019: Class, batch, basket, fee, enrollment and bridge state preserve supply and custody | tests/test_credit_batch_manager.py; tests/test_credit_balance.py; tests/test_gateway_ecocredits.py | P — an OIDC-protected location-scoped route lists batch status and quantities plus account-aggregated tradable/retired/escrowed ledger totals after signed tenant context in a read-only transaction. It excludes wallet addresses and keeps batch values separate from ledger aggregates for reconciliation. Class/basket/fee/enrollment/bridge route parity, custody writes, supply reconciliation, domain RLS, populated output parity, and MAN-CAP-019 remain open ([evidence](builds/2026-10-18-recovery/gateway-ecocredit-batch-read.json)). |
| CAP-020 | Credit custody & retirement | services/analytics/carbon_credits.py; services/certificates/; services/gateway/credit_custody.py; sdk/python/kokonut/; sdk/javascript/src/ | MAN-CAP-020: Atomic retirement reservation and independent confirmation prevent duplicate balance changes | tests/test_carbon_credits.py; tests/test_gateway_credit_custody.py | P — an OIDC-protected location summary requires both `carbon_credit:read` and `credit_retirement:read`, then establishes signed tenant context in a read-only transaction. It returns aggregate issuance/reservation/availability and retirement status totals while excluding beneficiaries, wallets, statements, evidence, idempotency keys, and reviewer notes. It preserves reservation totals separately from retirement-ledger requests; no approve/reject/cancel or chain action is exposed. Atomic reservation, independent confirmation parity, populated output parity, domain-table RLS, and MAN-CAP-020 remain open ([evidence](builds/2026-10-18-recovery/gateway-credit-custody-summary.json)). |
| CAP-021 | Linked data infrastructure | services/iri/; services/rdf/; services/storage/; services/gateway/public_iri.py | MAN-CAP-021: Resolve versioned IRI, hashes, RDF and lineage without private data disclosure | tests/test_linked_data.py; tests/test_evidence_lineage_integrity.py; tests/test_iri_public_projection.py; tests/test_gateway_public_iri.py; tests/test_iri_cli_offline.py | P — a native Gateway JSON-LD path now resolves only explicitly snapshotted location IRIs while the location remains in the governed public view. Generation copies four allowlisted public fields; migration 420 stores immutable per-version projections; response hashes cover the returned public projection, not the potentially private registry hash, and predecessor links are checked against the same entity/version chain. The 217-test focused linked-data/Gateway/migration suite passes, including offline IRI and Metadata API CLI help; the reproducible disposable PostgreSQL 16 runner verifies migration apply/replay plus object/null constraints. Migrations through 432 and the current app are deployed to the candidate; an unknown location IRI returned the expected 404. The candidate has no eligible published IRI, so positive projection, hidden/private snapshot and historical backfill acceptance remain open. Other entity types, RDF graph/SPARQL and storage parity, live runtime/RLS, source-data parity, and MAN-CAP-021 acceptance remain open ([contract](../iri-system.md#native-gateway-public-location-resolution); [runner](../../scripts/check-iri-public-projection-disposable.py); [evidence](builds/2026-10-16-recovery/public-iri-projection.json); [candidate rollout](builds/2026-10-17-recovery/candidate-migrations-404-432-rollout.json)). |
| CAP-022 | Data Stream | services/data_stream/; services/gateway/data_stream.py | MAN-CAP-022: Post, search, file references and proof verification preserve scope | tests/test_data_stream.py; tests/test_gateway_data_stream.py | P — protected Gateway draft creation, location-required list/search, attachment metadata, and stored attestation reads establish signed DB tenant context for exact resource/action/location grants. Queries bind posts/files to the verified location; projections omit source lineage, arbitrary metadata, evidence URLs, object URLs, and Directus identifiers. All private route responses now carry `Cache-Control: no-store`; stored attestation reads make no live-chain claim. A dry-run-first source provisioner uses a separate maintenance DSN and create-only inserts, while focused provisioner and disposable forced-RLS owner/location/actor checks pass. Signed attachment-byte delivery, live EAS validity checks, broader output parity, actual candidate key provisioning, domain RLS, and MAN-CAP-022 remain open ([evidence](builds/2026-10-18-recovery/gateway-data-stream-no-store.json)). |
| CAP-023 | Governance framework abstraction | services/governance/; services/gateway/governance.py; services/gateway/router.py; services/ingestion/gnosis_indexer.py; services/ingestion/gnosis_worker.py; services/migration/runtime_role.py; schemas/postgres/643_isolated_gnosis_moloch_indexer.sql | MAN-CAP-023: Read Baal configuration/proposals/members; legacy Moloch identity remains distinct | tests/test_governance_framework.py; tests/test_gnosis_indexer_recovery.py; tests/test_gnosis_worker.py; tests/test_runtime_role_boundary.py; tests/test_migration.py; tests/test_gateway_governance.py; tests/test_gateway_route_policy_inventory.py | P — protected, read-only Gateway routes expose global Baal configuration, bounded newest-first proposals, one proposal, and a requested member position under `governance:read`. The adapter verifies Gnosis chain ID 100; projections omit raw provider/event fields, bound proposal text, serialize large share/loot/vote quantities as decimal strings, and fail closed on incomplete required config reads. Location-scoped keys cannot authorize this global resource. No farm tenant context is asserted because DAO state is global. The legacy Moloch path now has a default-off dedicated worker login and bounded migration 643 functions with disposable forced-RLS evidence; candidate provisioning/rollout, populated-chain parity, RPC outage/live behavior, and MAN-CAP-023 remain open ([evidence](builds/2026-10-18-recovery/gateway-governance-read.json)). |
| CAP-024 | Governance circles & roles | services/analytics/; services/gateway/governance_roles.py; services/gateway/governance_tension_actions.py; services/gateway/governance_tension_review.py; services/gateway/governance_operations.py; services/gateway/governance_assignment_proposals.py; services/gateway/governance_assignment_proposal_reads.py; services/gateway/governance_assignment_review.py; services/gateway/governance_tactical_actions.py; services/gateway/governance_tactical_session_mutations.py; services/gateway/governance_definition_actions.py; services/gateway/governance_definition_mutations.py; services/gateway/governance_role_routes.py; apps/operator-console/index.html; schemas/postgres/438_governance_role_assignment_proposals.sql; schemas/postgres/439_governance_role_assignment_proposal_readback.sql; schemas/postgres/440_governance_role_assignment_review.sql; schemas/postgres/441_governance_tactical_actions.sql; schemas/postgres/442_governance_definition_lifecycle.sql; schemas/postgres/443_governance_definition_mutations.sql; schemas/postgres/444_governance_tactical_session_creation.sql; services/gateway/governance_tactical_mutations.py; schemas/postgres/445_governance_tactical_content_mutations.sql | MAN-CAP-024: Circle roles, tensions and tactical items enforce authority and approval | tests/test_governance_roles.py; tests/test_governance_role_authority.py; tests/test_governance_role_authority_unit.py; tests/test_gateway_governance.py; tests/test_gateway_governance_roles.py; tests/test_gateway_governance_tension_actions.py; tests/test_gateway_governance_tension_review.py; tests/test_gateway_governance_operations.py; tests/test_gateway_governance_assignment_proposals.py; tests/test_gateway_governance_assignment_proposal_reads.py; tests/test_gateway_governance_assignment_review.py; tests/test_gateway_governance_tactical_actions.py; tests/test_gateway_governance_definition_actions.py; tests/test_gateway_governance_definition_mutations.py; tests/test_gateway_governance_tactical_session_mutations.py; tests/test_operator_console_governance_assignment_proposals.py; tests/test_operator_console_governance_tensions.py; tests/test_operator_console_governance_tactical_sessions.py; tests/test_operator_route_policy_inventory.py; tests/test_gateway_governance_tactical_mutations.py | P — OIDC operators with exact location grants can read scoped governance summaries, circle/role registries and details, tension queues/details, and tactical items; create and submit attributed tension drafts; create proposal-only role nominations; review nominations independently; and start, dispose, or cancel authorized tactical items; create planned sessions in active same-location circles with the exact `governance_tactical:create` grant; create open tactical items and edit open-item/planned-session content through exact `governance_tactical:create/update` grants. Migration 442 provides audited circle/role lifecycle transitions. Migration 443 creates location-owned circles and roles as drafts and permits descriptive edits only while draft, under exact `governance_roles:create` or `:update`, signed tenant context, and active person binding. Circle hierarchy and role-parent links are location-qualified; cycles are rejected. Every create/edit writes private immutable request, actor, reason, and before/after history. Runtime and Directus direct definition writes are revoked and trigger-guarded. Circle edit fields use a separate exact-location no-store read route; aggregate summary free text remains excluded. The focused mutation slice passes 19 tests; the broader CAP-024 Gateway, route-policy, and console regression set passes 182 tests with five skips; disposable PostgreSQL 16 applies/replays migrations 437–445 and verifies signed scope, active person binding, same-location references, lifecycle boundaries, exact retries/collisions, private immutable before/after history, narrow row-lock privileges, and direct-write denial. Ruff, Python compilation, JavaScript syntax, capability validation, diff checks, and runtime SQL inventory (852 source files / 4,119 execution sites) pass. The local candidate now has migrations 438–444 applied after a fresh age-encrypted checkpoint and offline restore rehearsal (435 schema entries, six existing seed entries, zero pending schema migrations, and zero failed rows; no seeds ran). The app was rebuilt from branch commit `7ad161e` (image `sha256:4c76b210debf88d588bfa4a85e850dc7e78029f4e95def49005314c8f8dc146f`) and only that container was recreated; `/health` returned 200 and the assignment-proposal route returned 401 without credentials. The candidate database was not recreated; its only intended change is migrations 438–444. Metabase and proxy were not recreated or changed, and the legacy stack was untouched. The candidate still uses administrative `kokonut`, so runtime-role enforcement remains unproven. See [candidate rollout](builds/2026-10-19-recovery/candidate-migrations-438-444-rollout.json). The code-level tactical create/edit implementation is ready for owner review; CAP-024 remains prepared, not accepted. Open: least-privilege rollout, remaining report and populated-fixture parity, tenant RLS, live OIDC/browser behavior, and named MAN-CAP-024 acceptance. For application rollback after the candidate rollout, retain the additive migration-443/444 audit ledgers and write guards; do not reverse ordered migrations ([definition contract](governance-definition-lifecycle-contract.md); [migration](../schemas/postgres/443_governance_definition_mutations.sql); [tests](../tests/test_gateway_governance_definition_mutations.py); [database evidence](builds/2026-10-18-recovery/governance-definition-mutations-disposable.json)). |
| CAP-025 | Stakeholder ecosystem | services/analytics/; services/gateway/stakeholder_identity.py; services/gateway/stakeholder_identity_routes.py; services/gateway/stakeholder_identity_resolution.py; services/gateway/stakeholder_identity_resolution_routes.py; services/gateway/stakeholder_trust.py; services/gateway/stakeholder_trust_routes.py; apps/operator-console/index.html; schemas/postgres/446_location_scoped_stakeholder_identity_review.sql; schemas/postgres/447_location_scoped_identity_trust_projection.sql; schemas/postgres/448_location_scoped_identity_resolution.sql; docs/refactor/stakeholder-identity-kernel-contract.md | MAN-CAP-025: Resolve stakeholder identity/trust while raw feedback stays private | tests/test_consent_privacy_p0.py; tests/test_gateway_stakeholder_identity.py; tests/test_gateway_stakeholder_identity_resolution.py; tests/test_gateway_stakeholder_trust.py; tests/test_operator_console_stakeholder_identity.py; tests/test_operator_route_policy_inventory.py; scripts/check-stakeholder-identity-disposable.py; scripts/check-stakeholder-trust-disposable.py; scripts/check-stakeholder-identity-resolution-disposable.py | P — first Kernel identity-review slice adds exact location-scoped OIDC proposal/review routes, signed tenant context, an allowlisted farmer-profile source, current personal/internal-use consent checks at proposal and approval, structured-only match evidence, independent OIDC reviewers, append-only decision history, and runtime/Directus direct-table denial. The queue omits source IDs and exposes source names only with current consent; raw feedback and arbitrary notes are rejected. Existing legacy-global verified source links and already-approved Kernel sources fail closed; new approvals remain in the location-scoped ledger and are not copied to the legacy global `party_identifier` views. A no-score, location-scoped trust projection derives identity evidence only from independently approved cases and suppresses it after consent withdrawal or when the party is private/inactive. A distinct-grant `stakeholder_identity:resolve` route returns an approved farmer-profile mapping only in its source location while consent and party visibility remain valid; legacy conflicts and unavailable mappings fail closed. The operator reviewer console appears only with the exact location-scoped `stakeholder_identity:review` grant, renders consent-filtered fields, disables decisions when names are withheld, and submits confirmed CSRF-protected decisions with fixed reason codes and stable retry IDs; independent review remains database-enforced. Six console contract checks and the focused CAP-025 Gateway/trust/resolver/policy selection pass 36 tests with Ruff and JavaScript parsing. General trust evidence for delivery/payment/governance, identity sources beyond farmer profiles, live OIDC/browser and populated parity, RLS, completed-review consent disposition, and MAN-CAP-025 acceptance remain open. [contract](stakeholder-identity-kernel-contract.md). |
| CAP-026 | Threatcasting & backcasting | services/threatcasting/; services/gateway/threatcasting_reads.py; services/gateway/threatcasting_routes.py; apps/operator-console/index.html; services/gateway/operator_auth.py | MAN-CAP-026: Threat/cascade/backcast outputs remain advisory with evidence and acyclic milestones | tests/test_threatcasting.py; tests/test_backcasting_enhancements.py; tests/test_gateway_threatcasting_reads.py; tests/test_operator_console_threatcasting.py; tests/test_operator_route_policy_inventory.py | P — bounded, no-store Kernel GET routes expose location-granted backcast-plan summaries and milestone evidence with `advisory_only: true`; exact `threatcasting:read` policy, signed tenant context before read-only SQL, explicit location joins, 100-plan paging, and 500-milestone detail cap are covered by synthetic checks. Existing source/database checks reject cyclic and cross-plan dependencies. No write, publication, or intervention route is exposed. The console now lists location-granted advisory backcasts and reads milestone detail with keyset paging, fixed text rendering, and no write/approval actions. A 1 MiB detail-response cap returns HTTP 413 before oversized JSON is returned; the focused console/Gateway/policy selection passes 23 tests and Ruff. No database or provider was contacted. This is not universal tenant isolation: runtime ACL/RLS, live OIDC/browser behavior, populated output/evidence parity, and MAN-CAP-026 owner acceptance remain open. [read contract](threatcasting-kernel-read-contract.md). |
| CAP-027 | Real-time Delphi | services/delphi/; apps/operator-console/index.html; services/gateway/delphi_consultation.py; services/gateway/delphi_consultation_routes.py; services/gateway/delphi_recommendation_review.py; services/gateway/delphi_recommendation_review_routes.py; services/gateway/delphi_recommendation_drafts.py; services/gateway/delphi_recommendation_draft_routes.py; services/gateway/delphi_study_drafts.py; services/gateway/delphi_study_draft_routes.py; services/gateway/delphi_study_lifecycle.py; services/gateway/delphi_study_lifecycle_routes.py; schemas/postgres/631_location_scoped_delphi_study_lifecycle.sql; schemas/postgres/449_location_scoped_delphi_consultation_read.sql; schemas/postgres/450_location_scoped_delphi_recommendation_review.sql; schemas/postgres/451_location_scoped_delphi_recommendation_drafts.sql; schemas/postgres/630_location_scoped_delphi_study_drafts.sql; docs/refactor/delphi-consultation-kernel-contract.md; services/gateway/delphi_study_items.py; services/gateway/delphi_study_item_routes.py; schemas/postgres/632_location_scoped_delphi_study_items.sql; schemas/postgres/633_location_delphi_study_open_readiness.sql; services/gateway/delphi_consent_notices.py; services/gateway/delphi_consent_notice_routes.py; schemas/postgres/634_location_delphi_consent_notice_review.sql; services/gateway/delphi_participant_invites.py; services/gateway/delphi_participant_invite_routes.py; schemas/postgres/635_location_scoped_delphi_participant_invites.sql; services/gateway/delphi_participant_acceptance.py; services/gateway/delphi_participant_routes.py; schemas/postgres/636_location_scoped_delphi_participant_acceptance.sql; services/gateway/delphi_participant_workspace.py; apps/delphi-participant/index.html; apps/delphi-participant/app.js; apps/delphi-participant/styles.css; schemas/postgres/637_location_scoped_delphi_participant_workspace.sql; schemas/postgres/638_location_scoped_delphi_invite_inventory.sql; Dockerfile.gateway; Dockerfile.kernel; services/core/image_manifest.py; schemas/postgres/639_location_scoped_delphi_stopping_evaluation.sql; services/gateway/delphi_minority_review.py; services/gateway/delphi_minority_review_routes.py; schemas/postgres/640_location_scoped_delphi_minority_report_review.sql; schemas/postgres/641_location_delphi_consent_activity_scopes.sql; services/gateway/delphi_participant_minority_reports.py; schemas/postgres/642_location_scoped_delphi_minority_report_submission.sql| MAN-CAP-027: Pseudonymous consultation and facilitator drafts require human approval | tests/test_delphi.py; tests/test_gateway_delphi_consultation.py; tests/test_gateway_delphi_recommendation_review.py; tests/test_operator_console_delphi_recommendation_review.py; tests/test_gateway_delphi_recommendation_drafts.py; tests/test_gateway_delphi_study_drafts.py; tests/test_gateway_delphi_study_lifecycle.py; tests/test_operator_console_delphi_recommendation_drafts.py; tests/test_operator_console_delphi_study_drafts.py; tests/test_operator_console_delphi_study_lifecycle.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-delphi-consultation-disposable.py; scripts/check-delphi-recommendation-review-disposable.py; scripts/check-delphi-recommendation-drafts-disposable.py; scripts/check-delphi-study-drafts-disposable.py; scripts/check-delphi-study-lifecycle-disposable.py; tests/test_gateway_delphi_study_items.py; scripts/check-delphi-study-items-disposable.py; scripts/check-delphi-study-open-readiness-disposable.py; tests/test_operator_console_delphi_study_items.py; tests/test_gateway_delphi_consent_notices.py; scripts/check-delphi-consent-notice-review-disposable.py; tests/test_gateway_delphi_participant_invites.py; tests/test_operator_console_delphi_participant_invites.py; tests/test_operator_route_policy_inventory.py; scripts/check-delphi-participant-invite-disposable.py; scripts/check-delphi-participant-invite-console-disposable.py; tests/test_gateway_delphi_participant_acceptance.py; scripts/check-delphi-participant-acceptance-disposable.py; tests/test_gateway_delphi_participant_workspace.py; tests/test_delphi_participant_image_bundle.py; tests/test_operator_console_delphi_consent_notices.py; scripts/check-delphi-consent-scopes-disposable.py; scripts/check-delphi-participant-workspace-disposable.py; scripts/check-delphi-stopping-evaluation-disposable.py; tests/test_gateway_delphi_minority_review.py; tests/test_operator_console_delphi_recommendation_review.py; scripts/check-delphi-minority-review-disposable.py; scripts/check-delphi-consent-scopes-disposable.py; tests/test_gateway_delphi_participant_minority_reports.py; scripts/check-delphi-minority-report-submission-disposable.py| P — the first native Kernel path adds a paged, no-store OIDC consultation read at `/operator/api/delphi/{location_id}/studies` under exact `delphi:read` and signed tenant context. Migration 449 returns location-matched study/question metadata and consent-aware aggregates, suppressing counts/statistics below `max(3, ceil(min_participants))`; it omits participant identity/tokens, raw reasoning, metadata, recommendations, and minority reports. Migration 450 and the Gateway add an exact `delphi:review` queue plus draft-only human approve/reject decisions, block creator self-review, require a diversity assessment and closed minority-report review for approval, bind retries to exact decision content, and record an immutable private audit. Focused Gateway, route-policy, and migration metadata checks pass (119 tests), Ruff and Python compilation pass. Migration 449 disposable PostgreSQL 16 acceptance passes. Migration 450 applies and replays in disposable PostgreSQL 16 and passes seven runtime assertions for scope, self-review, readiness gates, exact retries/collisions, append-only audit, and runtime/Directus direct-table denial. Its non-login function owner has only `UPDATE(id)` for the study row lock. The operator console gates review by exact `delphi:review`, shows blockers, and sends CSRF-protected reason-code decisions with retry-stable request IDs; five focused console checks pass. Migration 451 and the Gateway add a separate exact `delphi:draft` path: the operator console pages only open/closed studies for the granted location and provides a CSRF-protected form; signed tenant context is set before bounded database functions. Draft insertion is column-limited, exact request retries return the original draft, changed-content reuse fails, and a private append-only ledger stores request identity and row references without duplicating draft text. Drafts stay `draft`; a different operator with `delphi:review` is still required for decisions. The 33 focused Gateway, exact route-policy, and console checks pass (91 tests across the selected Delphi/migration regression set). Disposable PostgreSQL 16 applies and replays migrations 449–451 and passes ten assertions for location/grant scope, eligible study states, retry and collision handling, payload bounds, draft-only state, ledger privacy and immutability, narrow study-row locking, and runtime/Directus privilege boundaries. Ruff, compilation, inline JavaScript parsing, capability validation, runtime SQL inventory, provider-boundary checks, and diff checks pass. Candidate and legacy remain untouched; migration 451 is not rolled out. CAP-027 remains prepared (`P`), not accepted. Live OIDC/browser, populated legacy parity, universal runtime ACL/RLS, and MAN-CAP-027 owner acceptance remain open. The legacy public consensus view may expose aggregates after approval when a verified/published farm registry record exists; it does not expose recommendation text. Remaining: live OIDC/browser; populated legacy parity; universal runtime ACL/RLS; and MAN-CAP-027 owner acceptance ([contract](delphi-consultation-kernel-contract.md); [draft migration](../schemas/postgres/451_location_scoped_delphi_recommendation_drafts.sql); [review migration](../schemas/postgres/450_location_scoped_delphi_recommendation_review.sql); [review evidence](builds/2026-10-19-recovery/cap-027-delphi-recommendation-review-disposable.json); [draft evidence](builds/2026-10-19-recovery/cap-027-delphi-recommendation-drafts-disposable.json)).  Migration 630 and `POST /operator/api/delphi/{location_id}/studies` add exact-grant, signed-context study creation that inserts only `draft`; a private append-only receipt stores a SHA-256 request digest, exact retries replay, and changed-content/scope failures fail closed. Focused Gateway/policy checks pass 29 tests, and disposable PostgreSQL 16 applies/replays migrations 449–451 and 630 with six grouped assertions. The grant-gated console now exposes study creation with bounded stopping criteria, CSRF/no-store, and retry-stable request IDs; 13 focused Delphi console tests pass across the study-create, facilitator-draft, and review panels, including Node syntax parsing. Migration 631 adds exact-location `delphi:open` and `delphi:close` actions with signed context and append-only retry receipts. Open requires a question plus the configured minimum of consented panel members; close only transitions an open study and prevents reopening. Its selected API/route-policy/draft tests pass 47 checks, and disposable PostgreSQL 16 applies/replays 449–451, 630, and 631 with six grouped lifecycle assertions. Panel/item authoring, contributions, and stopping evaluation, live OIDC/browser, populated parity, universal runtime ACL/RLS, and MAN-CAP-027 acceptance remain open; CAP-027 stays prepared, not accepted ([study migration](../../schemas/postgres/630_location_scoped_delphi_study_drafts.sql); [evidence](builds/2026-10-25-recovery/cap-027-delphi-study-drafts-disposable.json)). Migration 632 and `POST /operator/api/delphi/{location_id}/studies/{study_id}/items` add bounded questions only to draft studies under exact `delphi:draft` and signed tenant context. The dedicated non-login writer rechecks current grant, study/location ownership, and draft status; immutable private receipts provide exact retry replay and reject changed-content reuse. The grant-gated console requires same-location `delphi:read` and `delphi:draft`, filters the bounded study read to draft status, and submits CSRF-protected no-store requests with retry-stable IDs. The 32-test Gateway/policy selection and 25-test Delphi console selection pass; disposable PostgreSQL 16 applies/replays migrations 449–451 and 630–632 with six grouped acceptance assertions. Candidate and legacy databases remain untouched; migration 632 is not rolled out. Migration 633 and `GET /operator/api/delphi/{location_id}/studies/{study_id}/open-readiness` add an exact `delphi:open` read that returns only readiness booleans and fixed blockers, never panel counts or identities. The console fails closed until a fresh same-location response succeeds; migration 631 rechecks all open prerequisites at write time. The 272-test focused suite passes, and disposable PostgreSQL 16 applies/replays 449–451 and 630–633 with six grouped readiness/ACL assertions. Candidate and legacy are untouched; migration 633 is not rolled out. Participant invitation and independently recorded consent, panel membership and contribution, stopping evaluation, location-safe target-entity links, live OIDC/browser, populated parity, broader ACL/RLS, and MAN-CAP-027 remain open. Migration 634 adds immutable versioned consent notices for draft studies, independent location review, exact retry receipts, and one-approved-version supersession; eight grouped PostgreSQL acceptance assertions and the 59-test focused suite pass. The user selected study-scoped single-use invites with no canonical party linkage. Invite issuance, participant acceptance/withdrawal, console controls, live OIDC/browser, populated parity, broad ACL/RLS, and MAN-CAP-027 remain open. Migration 635 adds exact-location invite issuance/revocation bound to an approved notice and draft study. The SHA-256 token digest is stored; the raw bearer is returned only once. Nine grouped disposable PostgreSQL assertions and 58 focused tests pass. Public preview/redemption, consent acceptance/withdrawal, participant sessions/contributions, console controls, SMTP delivery, live OIDC/browser, populated parity, broad ACL/RLS, and MAN-CAP-027 remain open; do not distribute tokens before redemption is implemented. Migration 637 adds a first-party self-hosted participant page at `/api/participation/delphi`, plus a paged session workspace and answer upsert route. Invite tokens are accepted only in a URL fragment and immediately removed from browser history; participant session/CSRF credentials use scoped Secure cookies, and no third-party assets are loaded. Draft studies expose no questions; open and closed studies return only the current participant’s own answers. The write function serializes with withdrawal and study closure, checks item range and consent, preserves the legacy upsert plus consensus/history behavior, and records a digest-only append-only retry receipt. Eight grouped network-disabled disposable PostgreSQL 16 assertions pass after migration apply/replay. The focused Gateway/route-policy/migration/image-bundle selection passes 76 tests; the self-hosted image boundary and JS syntax are verified. Candidate and legacy remain untouched; migration 637 is not rolled out. Migration 638 adds a same-location token-free invite inventory and operator controls that issue/copy one-time links, list safe status metadata, and revoke only with the separate invite_revoke grant; no recipient details are stored and no email is sent. The focused Gateway, route-policy, and console selection passes 69 tests, and the network-disabled disposable PostgreSQL 16 chain passes five scope, privacy, pagination, and role assertions. Migration 640 adds private location-scoped review of existing submitted minority reports while participant consent remains active; its retry ledger is append-only and not directly readable by runtime or Directus. Fifty focused Gateway/route-policy/console tests pass, and disposable PostgreSQL 16 passes five apply/replay, scope, consent, retry, and role assertions. Migration 639 adds the exact-location advisory stopping evaluator, recomputes only currently consented responses, uses prior consent-filtered snapshots for stability, omits participant counts and raw answer/statistic content, and never closes the study. The focused Gateway/route-policy/console/migration selection passes 80 tests; the network-disabled disposable PostgreSQL 16 chain applies/replays 449–451 and 630–639 and passes seven grouped checks. Migration 641 binds canonical `questionnaire_responses` and optional `minority_reports` scopes to immutable notice, invite, and consent digests, requires explicit scope for new invitations, and displays the scope before participant acceptance. The 87-test consent/Gateway/console/migration regression passes; a network-disabled disposable PostgreSQL 16 apply/replay passes eight scope, digest, review, invite, acceptance, and role assertions. Candidate and legacy remain untouched; migrations 639–641 are not rolled out. CAP-027 remains prepared, not accepted. Live OIDC/browser, SMTP, populated parity, universal runtime ACL/RLS, and MAN-CAP-027 owner acceptance remain open ([migration](../schemas/postgres/639_location_scoped_delphi_stopping_evaluation.sql); [evidence](builds/2026-10-25-recovery/cap-027-delphi-stopping-evaluation-disposable.json)). Migration 642 adds participant-submitted minority reports only for explicitly consented, open studies; reports are bounded, retry-safe, and independently reviewed. The 103-test focused selection and eight disposable PostgreSQL 16 assertions pass; runtime and Directus lack direct report/receipt access. Candidate and legacy remain untouched and migration 642 is not rolled out. Live OIDC/browser, populated parity, universal ACL/RLS, SMTP, and owner acceptance remain open; CAP-027 remains prepared. Checklist: 1,189 complete / 25 open (1,214 total).|
| CAP-028 | Strategy system | services/analytics/; services/gateway/strategy_reads.py; services/gateway/strategy_routes.py; apps/operator-console/index.html; schemas/postgres/452_location_scoped_strategy_plan_read.sql; docs/refactor/strategy-kernel-read-contract.md | MAN-CAP-028: Plan, allocation, cascade, consultation, execution and gate behavior preserve lineage | tests/test_strategy_kernel.py; tests/test_gateway_strategy_reads.py; tests/test_operator_console_strategy.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-strategy-kernel-read-disposable.py | P — the first native Kernel path adds `GET /operator/api/strategy/{location_id}/plans` under exact location `strategy:read` and signed tenant context. Migration 452 creates a bounded security-definer projection and a non-login reader role. It returns location plan metadata, cascade state, structural gate status, and aggregate objective, initiative, investment, coherence, review, and allocation counts; diagnosis, guiding policy, cascade/decision rationale, evidence, party identities, costs, and parent organization plan details are excluded. The focused Gateway, exact route-policy, and migration metadata selection passes 48 tests; 13 tests directly cover the projection. Disposable PostgreSQL 16 applies and replays migration 452 and passes six authorization, scope, page-bound, lineage, output-contract, and role-privilege assertions. Ruff, Python compilation, capability validation, provider-boundary checks, and runtime SQL inventory (868 source files / 4,154 execution sites) pass. Candidate and legacy databases are untouched; migration 452 is not rolled out. The operator console now shows bounded location strategy plan cards with fixed metadata/aggregate fields under exact `strategy:read`; structural gate state is clearly marked as informational rather than approval. Its focused console/Gateway/policy selection passes 21 tests with JavaScript syntax validation and Ruff; no database was accessed. CAP-028 remains prepared: full allocation, consultation, cascade, execution and lifecycle parity; populated fixtures; live OIDC/browser; universal runtime ACL/RLS; and MAN-CAP-028 owner acceptance remain open ([contract](strategy-kernel-read-contract.md); [migration](../schemas/postgres/452_location_scoped_strategy_plan_read.sql); [disposable evidence](builds/2026-10-19-recovery/cap-028-strategy-read-disposable.json)). |
| CAP-029 | Competitive landscape | services/analytics/; services/gateway/competitive_landscape_reads.py; services/gateway/competitive_landscape_routes.py; apps/operator-console/index.html; schemas/postgres/453_location_scoped_competitive_landscape_read.sql; docs/refactor/competitive-landscape-kernel-read-contract.md | MAN-CAP-029: Competitive observations and advantage outcomes match scoped fixture | tests/test_competitive_landscape.py; tests/test_advantage_assessment.py; tests/test_gateway_competitive_landscape_reads.py; tests/test_operator_console_competitive_landscape.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-competitive-landscape-disposable.py | P — the first native Kernel slice adds a paged, no-store OIDC read at `/operator/api/competitive-landscape/{location_id}/summaries` under exact location `competitive_landscape:read` and signed tenant context. Migration 453 rechecks the signed scope/grant and exposes only same-location landscape metadata, aggregate actor/threat, force-pressure, signal, verified advantage and verified outcome signals. Actor identity, narrative, evidence, source references, advantage statements and individual outcome values are excluded. The focused Gateway/route-policy selection passes 16 tests, and the combined Gateway, policy, migration-metadata, and legacy parity selection passes 56 tests with two skips; disposable PostgreSQL 16 applies/replays migration 453 and passes seven aggregate, scope, grant, paging, output-contract and privilege assertions. Candidate and legacy databases are untouched; migration 453 is not rolled out. The operator console now renders the allowlisted location summary with fixed aggregate fields, no-store reads, stale-response guards, and bounded pages; it reveals no landscape identifiers or individual records. The focused console/Gateway/policy selection passes 22 tests with JavaScript syntax validation and Ruff; no database was accessed. CAP-029 remains prepared, not accepted: complete workflow/report/dashboard parity, populated reference-fixture comparison, live OIDC/browser behavior, universal runtime ACL/RLS, and MAN-CAP-029 owner review remain open ([contract](competitive-landscape-kernel-read-contract.md); [migration](../schemas/postgres/453_location_scoped_competitive_landscape_read.sql); [disposable evidence](builds/2026-10-19-recovery/cap-029-competitive-landscape-disposable.json)). |
| CAP-030 | Management workflow | services/management/; services/gateway/management_work_reads.py; services/gateway/management_work_routes.py; apps/operator-console/index.html; schemas/postgres/454_location_scoped_management_work_summary.sql; docs/refactor/management-work-kernel-read-contract.md | MAN-CAP-030: Work assignment, SLA and escalation preserve authority and audit | tests/test_management_workflow.py; tests/test_gateway_management_work_reads.py; tests/test_operator_console_management_work.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-management-work-summary-disposable.py | P — the first native Kernel slice adds `GET /operator/api/management/{location_id}/summary` under exact location `management_workflow:read` and signed tenant context. Migration 454 returns work lifecycle, open priority, overdue/SLA, claim, escalation, and audit-recency aggregates for exact `work_item.location_id` matches. Task text, assignee/actor identities, claimants, effort, skill requirements, notes, and escalation reasons are excluded. The focused Gateway, route-policy, and migration-metadata selection passes 42 tests; disposable PostgreSQL 16 applies/replays migration 454 and passes seven scope, aggregate, privacy, and privilege assertions. Candidate and legacy databases are untouched; migration 454 is not rolled out. The operator console now displays the 17 fixed workload/status/urgency/SLA/claim/escalation aggregates under exact `management_workflow:read`, with text-only rendering and no state-changing controls. The focused console/Gateway/policy selection passes 15 tests with JavaScript syntax validation and Ruff; no database was accessed. CAP-030 remains prepared, not accepted: assignment and transition parity, selection/claim review, dynamic SLA policy, escalation creation/resolution, detailed audit behavior, unscoped legacy work items, populated fixtures, live OIDC/browser behavior, universal ACL/RLS, and MAN-CAP-030 owner review remain open ([contract](management-work-kernel-read-contract.md); [migration](../schemas/postgres/454_location_scoped_management_work_summary.sql); [disposable evidence](builds/2026-10-19-recovery/cap-030-management-work-summary-disposable.json)). |
| CAP-031 | Planning & budgeting | services/planning/; services/gateway/planning_budget_reads.py; services/gateway/planning_budget_routes.py; apps/operator-console/index.html; schemas/postgres/455_location_scoped_budget_summary.sql; sdk/python/kokonut/; sdk/javascript/src/; docs/refactor/planning-budget-kernel-read-contract.md | MAN-CAP-031: Budget variance, objectives, portfolio and S&OP results match fixture | tests/test_planning_budget.py; tests/test_portfolio.py; tests/test_gateway_planning_budget_reads.py; tests/test_operator_console_planning_budget.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-planning-budget-summary-disposable.py | D — the adjacent public location roll-up and read-only Python/TypeScript stored finance accessors remain deployed. A new internal Kernel read at `GET /operator/api/planning/{location_id}/budgets` is prepared under exact location `planning_budget:read` and signed tenant context. Migration 455 includes only plans owned by the location's current organization with explicitly location-assigned budget lines; organization-only lines are not apportioned. It reports plan state/currency/period, planned amount, verified same-currency expenses and variance, foreign-currency expense count, and scenario count; labels, categories, objectives, assumptions, and transaction details are excluded. The focused Gateway, route-policy, and migration-metadata selection passes 49 tests; disposable PostgreSQL 16 applies/replays migration 455 and passes seven lineage, currency, scope, privacy, and privilege assertions. Candidate and legacy databases are untouched; migration 455 is not rolled out. The operator console now renders location-scoped plan summaries under exact `planning_budget:read`, keeping native currencies separate and excluding plan/transaction details. The focused console/Gateway/policy selection passes 22 tests with JavaScript syntax validation and Ruff; no database was accessed. CAP-031 remains partial: budget lifecycle edits, revenue/cash-flow reconciliation, objectives/KPIs, portfolio allocation, production/capacity S&OP, exchange-rate conversion, populated-fixture parity, live OIDC/browser, universal ACL/RLS, and MAN-CAP-031 owner acceptance remain open ([contract](planning-budget-kernel-read-contract.md); [migration](../schemas/postgres/455_location_scoped_budget_summary.sql); [evidence](builds/2026-10-19-recovery/cap-031-budget-summary-disposable.json)). [Public finance contract](public-summary-contracts.md) |
| CAP-032 | Business architecture | services/analytics/capability_map.py; services/analytics/technology_roadmap.py; services/analytics/value_stream_defs.py; services/analytics/vision_mission.py; services/gateway/business_architecture_reads.py; services/gateway/business_architecture_routes.py; apps/operator-console/index.html; schemas/postgres/456_location_scoped_business_architecture_read.sql; docs/refactor/business-architecture-kernel-read-contract.md | MAN-CAP-032: Capability/value-stream/mission mappings retain governed relationships | tests/test_capability_map.py; tests/test_strategy_map.py; tests/test_gateway_business_architecture_reads.py; tests/test_operator_console_business_architecture.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-business-architecture-disposable.py | P — a location-scoped, read-only OIDC path is prepared at `/operator/api/business-architecture/{location_id}/summary` under exact `business_architecture:read` and signed tenant context. Migration 456 exposes the latest approved location vision/mission/value statement and bounded capability/value-stream/strategy mappings from approved location roadmaps; cross-scope strategy links, descriptions, evidence, identity, owners, and rationale are excluded. The focused Gateway, exact route-policy, and migration-metadata checks pass; disposable PostgreSQL 16 applies/replays migration 456 and verifies location/grant scope, approval filters, output allowlisting, and reader/runtime/Directus boundaries. Candidate and legacy databases are untouched; migration 456 is not rolled out. The operator console now renders approved statements and bounded location roadmap mappings under exact `business_architecture:read`; fixed text-only fields, no-store reads, stale-location guards, and 25-row paging are used. The 21-test console/Gateway/policy selection passes with JavaScript syntax validation and Ruff, with no database access. CAP-032 remains prepared pending populated parity, live OIDC/browser behavior, broader ACL/RLS, and MAN-CAP-032 owner acceptance ([contract](business-architecture-kernel-read-contract.md); [migration](../schemas/postgres/456_location_scoped_business_architecture_read.sql); [evidence](builds/2026-10-19-recovery/cap-032-business-architecture-disposable.json)). |
| CAP-033 | Pitch & business planning | services/analytics/pitch.py; services/analytics/business_model_canvas.py; services/export/business_plan.py; services/gateway/business_planning_reads.py; services/gateway/business_planning_writes.py; services/gateway/business_planning_routes.py; apps/operator-console/index.html; schemas/postgres/457_location_scoped_business_canvas_read.sql; schemas/postgres/463_location_scoped_business_canvas_create.sql; docs/refactor/business-planning-kernel-read-contract.md; docs/refactor/business-planning-kernel-write-contract.md | MAN-CAP-033: Pitch, plan and canvas retain evidence links and report content | tests/test_pitch.py; tests/test_business_plan.py; tests/test_gateway_business_planning_reads.py; tests/test_operator_console_business_planning.py; tests/test_gateway_business_planning_writes.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-business-canvas-disposable.py; scripts/check-business-canvas-create-disposable.py | P — the Kernel now has a location-scoped canvas read and an OIDC/CSRF-protected `POST /operator/api/business-planning/{location_id}/canvases` draft-create path under exact `business_planning:create`. Migration 457 returns bounded location canvases with lifecycle, nine content blocks, and source references; migration 463 creates version-one drafts through a non-login column-scoped role, checks signed context/grant in PostgreSQL, and uses an append-only SHA-256 idempotency ledger. The 105-test focused Gateway/auth/policy/migration/report selection passes; disposable PostgreSQL 16 applies/replays 457 and 463 and passes eight acceptance groups covering creation, exact retry/collision, scope/grant denial, block validation, ledger privacy, and unchanged legacy DML. The migration is additive and does not revoke CLI/Directus table writes; universal ACL/RLS remains open. Candidate and legacy are untouched; neither migration is rolled out. The operator console now lists bounded location canvases and renders fixed metadata plus the nine content blocks under the same exact read grant; it adds no state-changing actions. Its 21-test focused console/Gateway/policy selection passes with JavaScript syntax validation and Ruff, with no database access. CAP-033 remains prepared pending generated-pitch and assembled-plan parity, populated reference fixtures, live OIDC/browser acceptance, broader ACL/RLS, and MAN-CAP-033 owner review ([read contract](business-planning-kernel-read-contract.md); [write contract](business-planning-kernel-write-contract.md); [migration](../schemas/postgres/463_location_scoped_business_canvas_create.sql); [evidence](builds/2026-10-19-recovery/cap-033-business-canvas-disposable.json); [create evidence](builds/2026-10-19-recovery/cap-065-business-canvas-create-disposable.json)). |
| CAP-034 | Coordination & alliance system | services/analytics/coordination.py; services/analytics/coordination_strategy.py; services/analytics/coordination_accounting.py; services/gateway/coordination_reads.py; services/gateway/coordination_routes.py; apps/operator-console/index.html; schemas/postgres/458_location_scoped_coordination_summary.sql; docs/refactor/coordination-kernel-read-contract.md | MAN-CAP-034: Alliance triggers, learning and integrity guards preserve approval boundaries | tests/test_coordination_end_to_end.py; tests/test_coordination_governance.py; tests/test_gateway_coordination_reads.py; tests/test_operator_console_coordination.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-coordination-summary-disposable.py | P — the operator console now displays the aggregate counts through a read-only grant-gated overview; the first Kernel slice adds `GET /operator/api/coordination/{location_id}/summary` under exact location `coordination:read` and signed tenant context. Migration 458 returns aggregate-only counts for exact location-scoped alliances, lifecycle, overdue review, conflict/harm/appeal/remedy, preserved minority views, consent-gated exchanges, learning links, and metric observation states; identities and narratives are excluded. Focused Gateway, route-policy, and migration-metadata checks pass; disposable PostgreSQL 16 applies/replays migration 458 and verifies scope, aggregates, grant enforcement, and runtime/Directus boundaries. Candidate and legacy databases are untouched; migration 458 is not rolled out. CAP-034 remains prepared pending populated alliance parity, live OIDC/browser, trigger/worker recovery acceptance, broader ACL/RLS, and MAN-CAP-034 owner review ([contract](coordination-kernel-read-contract.md); [migration](../schemas/postgres/458_location_scoped_coordination_summary.sql); [evidence](builds/2026-10-19-recovery/cap-034-coordination-summary-disposable.json)). |
| CAP-035 | Solution lifecycle | services/innovation/solution_scale.py; services/innovation/solution_lifecycle.py; services/innovation/solution_adoption.py; services/innovation/solution_funding.py; services/gateway/solution_lifecycle_reads.py; services/gateway/solution_lifecycle_routes.py; apps/operator-console/index.html; services/gateway/operator_auth.py; schemas/postgres/459_location_scoped_solution_lifecycle_summary.sql; schemas/postgres/466_location_scoped_solution_gates.sql; schemas/postgres/467_location_scoped_solution_experiments.sql; schemas/postgres/468_location_scoped_solution_funding.sql; schemas/postgres/469_location_scoped_solution_adoption.sql; schemas/postgres/470_location_scoped_solution_scale_gates.sql; schemas/postgres/471_location_scoped_solution_replications.sql; schemas/postgres/472_location_scoped_solution_learning.sql; schemas/postgres/473_location_scoped_solution_retirements.sql; schemas/postgres/474_solution_retirement_independent_review.sql; docs/refactor/solution-lifecycle-kernel-read-contract.md; services/gateway/solution_lifecycle_actions.py; schemas/postgres/475_location_solution_retirement_review.sql; schemas/postgres/476_location_solution_retirement_proposal.sql; schemas/postgres/477_location_solution_learning_proposal.sql; schemas/postgres/481_location_solution_retirement_candidates.sql; schemas/postgres/482_location_solution_retirement_review_queue.sql; scripts/check-solution-retirement-review-disposable.py; schemas/postgres/483_location_solution_gate_evaluation.sql; schemas/postgres/484_location_solution_gate_review.sql; schemas/postgres/485_solution_gate_nonhuman_approval_compatibility.sql; schemas/postgres/486_location_solution_gate_transition.sql; schemas/postgres/487_location_solution_experiment_review.sql; schemas/postgres/488_location_solution_funding_proposals.sql; schemas/postgres/489_location_solution_funding_submission.sql; docs/refactor/solution-lifecycle-kernel-write-contract.md; schemas/postgres/490_location_solution_funding_review.sql; schemas/postgres/491_location_solution_funding_approval.sql; schemas/postgres/492_location_solution_funding_tranche_review.sql; schemas/postgres/493_location_solution_adoption_event_summary.sql; schemas/postgres/494_location_solution_replication_proposal.sql; schemas/postgres/495_location_solution_replication_review.sql; scripts/check-solution-replication-review-disposable.py; docs/refactor/solution-lifecycle-kernel-write-contract.md; schemas/postgres/496_location_solution_replication_activation.sql; scripts/check-solution-replication-activation-disposable.py; tests/test_gateway_solution_replication_activation.py; docs/refactor/solution-lifecycle-kernel-write-contract.md; schemas/postgres/497_location_solution_replication_completion_proposal.sql; tests/test_gateway_solution_replication_completion_proposals.py; scripts/check-solution-replication-completion-proposal-disposable.py; docs/refactor/solution-lifecycle-kernel-write-contract.md; schemas/postgres/498_location_solution_replication_completion_review.sql; services/gateway/solution_lifecycle_actions.py; services/gateway/solution_lifecycle_reads.py; services/gateway/solution_lifecycle_routes.py; scripts/check-solution-replication-completion-review-disposable.py; schemas/postgres/499_location_solution_learning_review.sql; schemas/postgres/500_location_solution_learning_application.sql; schemas/postgres/501_location_solution_scale_gate_evaluation_review.sql; scripts/check-solution-scale-gate-review-disposable.py; services/gateway/solution_lifecycle_actions.py; tests/test_gateway_solution_scale_gate_reviews.py; tests/test_operator_console_solution_lifecycle.py; docs/refactor/builds/2026-10-20-recovery/cap-035-scale-gate-review-disposable.json; schemas/postgres/502_location_solution_retirement_execution.sql; scripts/check-solution-retirement-execution-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-retirement-execution-disposable.json; schemas/postgres/503_location_solution_nonpromotion_stage_transition.sql; tests/test_gateway_solution_lifecycle_nonpromotion_transitions.py; tests/test_operator_console_solution_lifecycle_stage_transitions.py; scripts/check-solution-nonpromotion-stage-transition-disposable.py; docs/refactor/solution-lifecycle-source-route-audit.md; schemas/postgres/504_location_solution_create.sql; scripts/check-solution-create-disposable.py; schemas/postgres/505_location_solution_gate_definition.sql; scripts/check-solution-gate-create-disposable.py; services/innovation/solution_experiments.py; schemas/postgres/506_location_solution_experiment_create.sql; scripts/check-solution-experiment-create-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-create-disposable.json; schemas/postgres/507_location_solution_experiment_submission.sql; scripts/check-solution-experiment-submission-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-submission-disposable.json; schemas/postgres/508_location_solution_experiment_protocol_review.sql; scripts/check-solution-experiment-protocol-review-disposable.py; tests/test_gateway_solution_lifecycle_experiment_protocol_review.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-protocol-review-disposable.json; schemas/postgres/509_location_solution_experiment_start.sql; scripts/check-solution-experiment-start-disposable.py; tests/test_gateway_solution_lifecycle_experiment_start.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-start-disposable.json; schemas/postgres/510_location_solution_experiment_observation_capture.sql; scripts/check-solution-experiment-observation-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-observation-disposable.json; schemas/postgres/511_location_solution_experiment_sequential_analysis.sql; tests/test_gateway_solution_lifecycle_experiment_analysis.py; schemas/postgres/512_location_solution_experiment_completion.sql; tests/test_gateway_solution_lifecycle_experiment_completion.py; schemas/postgres/513_location_solution_adoption_program_create.sql; scripts/check-solution-adoption-program-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-adoption-program-disposable.json; schemas/postgres/514_location_solution_adoption_write_boundary.sql; scripts/check-solution-adoption-write-boundary-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-adoption-write-boundary-disposable.json; schemas/postgres/515_location_solution_adoption_preparation.sql; schemas/postgres/516_location_solution_adoption_readiness_review.sql; tests/test_gateway_solution_lifecycle_adoption_readiness.py; scripts/check-solution-adoption-program-disposable.py; schemas/postgres/517_location_solution_configuration_draft_review.sql; schemas/postgres/518_location_solution_adoption_program_review.sql; tests/test_gateway_solution_lifecycle_adoption_program_review.py; tests/test_gateway_solution_lifecycle_configuration.py; schemas/postgres/520_location_solution_adoption_consent_events.sql | MAN-CAP-035: Experiment, funding, adoption, scale and retirement follow sequential gates | tests/test_solution_lifecycle.py; tests/test_solution_scale.py; tests/test_solution_adoption.py; tests/test_solution_funding.py; tests/test_gateway_solution_lifecycle_reads.py; tests/test_operator_console_solution_lifecycle.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-solution-lifecycle-summary-disposable.py; scripts/check-solution-lifecycle-gates-disposable.py; scripts/check-solution-lifecycle-experiments-disposable.py; scripts/check-solution-lifecycle-funding-disposable.py; scripts/check-solution-lifecycle-adoption-disposable.py; scripts/check-solution-lifecycle-scale-gates-disposable.py; scripts/check-solution-lifecycle-replications-disposable.py; scripts/check-solution-lifecycle-learning-disposable.py; scripts/check-solution-lifecycle-retirements-disposable.py; scripts/check-solution-retirement-independent-review-disposable.py; tests/test_gateway_solution_lifecycle_actions.py; scripts/check-solution-retirement-approval-disposable.py; tests/test_gateway_solution_lifecycle_proposals.py; scripts/check-solution-retirement-proposal-disposable.py; tests/test_gateway_solution_learning_proposals.py; scripts/check-solution-learning-proposal-disposable.py; scripts/check-solution-lifecycle-retirements-disposable.py; scripts/check-solution-retirement-review-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-retirement-review-disposable.json; tests/test_gateway_solution_lifecycle_gate_evaluations.py; tests/test_gateway_solution_lifecycle_gate_review.py; scripts/check-solution-gate-evaluation-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-gate-evaluation-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-gate-review-disposable.json; tests/test_gateway_solution_lifecycle_gate_transitions.py; tests/test_gateway_solution_lifecycle_experiment_review.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-gate-transition-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-review-disposable.json; tests/test_gateway_solution_lifecycle_funding_proposals.py; tests/test_gateway_solution_replication_proposals.py; scripts/check-solution-replication-proposal-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-funding-proposal-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-funding-review-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-funding-approval-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-funding-tranche-approval-disposable.json; tests/test_gateway_solution_replication_review.py; scripts/check-solution-replication-review-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-review-disposable.json; tests/test_gateway_solution_replication_activation.py; scripts/check-solution-replication-activation-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-activation-disposable.json; tests/test_gateway_solution_replication_completion_proposals.py; scripts/check-solution-replication-completion-proposal-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-completion-proposal-disposable.json; tests/test_gateway_solution_replication_completion_review.py; scripts/check-solution-replication-completion-review-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-completion-review-disposable.json; tests/test_gateway_solution_learning_review.py; scripts/check-solution-learning-review-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-learning-review-disposable.json; tests/test_gateway_solution_learning_application.py; scripts/check-solution-learning-application-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-learning-application-disposable.json; scripts/check-solution-scale-gate-review-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-scale-gate-review-disposable.json; tests/test_gateway_solution_retirement_execution.py; scripts/check-solution-retirement-execution-disposable.py; tests/test_gateway_solution_lifecycle_nonpromotion_transitions.py; tests/test_operator_console_solution_lifecycle_stage_transitions.py; scripts/check-solution-nonpromotion-stage-transition-disposable.py; docs/refactor/builds/2026-10-20-recovery/cap-035-nonpromotion-stage-transition-disposable.json; tests/test_gateway_solution_lifecycle_create.py; tests/test_gateway_solution_lifecycle_gate_create.py; tests/test_gateway_solution_lifecycle_experiment_create.py; tests/test_gateway_solution_lifecycle_experiment_submission.py; tests/test_solution_experiments.py; tests/test_gateway_solution_lifecycle_experiment_observation.py; tests/test_operator_route_policy_inventory.py; tests/test_runtime_role_boundary.py; tests/test_operator_console_solution_lifecycle.py; tests/solution_lifecycle_fixtures.py; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-create-disposable.json; docs/refactor/builds/2026-10-20-recovery/cap-035-solution-create-disposable.json; tests/test_gateway_solution_lifecycle_adoption_program.py; tests/test_gateway_solution_lifecycle_configuration.py; tests/test_gateway_solution_lifecycle_adoption_program_revision.py | P — migration 516 adds exact-location adoption-readiness assessment and independent review; unreviewed historical ready rows expire, and only an independent review of the current immutable assessment can mark readiness ready. Migration 517 adds versioned configuration drafts, creator submission, and independent review; unverifiable historical approvals are preserved and returned to draft. Program enablement review remains open. The operator console now provides a read-only aggregate overview and bounded stage-gate status list under the exact location grant; the list renders fixed solution labels, transitions, structural requirement thresholds, gate state, and latest evaluation result/time, while omitting evidence and reviewer identities; it also pages experiment status with fixed lifecycle metadata and only the latest explicitly reviewed outcome, while withholding protocol narratives, metric names/values, observations, adverse-event detail, evidence, and reviewer identities; the funding view pages case/tranche labels, currency, and timestamps without amounts, terms, rationale, evidence, or submitter/approver/releaser identities; five supplemental console views page adoption programs, scale gates, replications, learning, and retirements under the same exact location grant, with fixed status fields and no IDs, narratives, evidence, or person-level details; adoption cohort counts remain suppressed below the database threshold; a grant-gated learning-proposal form now selects only completed, actively reviewed replications and submits bounded, CSRF-protected proposals with stable retry IDs; it creates only `proposed` records for independent review and exposes no approve/reject/apply control; the combined CAP-025/CAP-035 selection passes 166 tests with Ruff and inline JavaScript parsing; the first Kernel slice adds `GET /operator/api/solution-lifecycle/{location_id}/summary` under exact location `solution_lifecycle:read` and signed tenant context. Migration 459 enables explicit location links in `solution_link` and reports aggregate-only stages, gates/latest evaluations, experiments/outcomes, funding decision states, location adoption/configuration/readiness/scale, learning, and retirement counts for exact location-linked solutions. It omits identities, solution IDs/names, narratives, evidence, funding amounts, and raw JSON; lifecycle gate behavior is unchanged. The focused Gateway/route-policy/migration-metadata selection passes 44 tests; disposable PostgreSQL 16 applies/replays migration 459 and passes six scope, aggregate, privacy, and privilege assertions. Candidate and legacy databases are untouched; migrations 459 and 466–474 are not rolled out. The item-level `GET /operator/api/solution-lifecycle/{location_id}/gates` route uses the exact location read grant and returns only allowlisted gate metadata plus the latest pass/fail timestamp; migration 466 applies/replays in disposable PostgreSQL and passes six scope, ordering, paging, privacy, and ACL assertions. The 54-test Gateway/route-policy/migration selection passes. The experiments status route adds a 30-test Gateway/route-policy selection (63 with migration metadata) and migration 467 disposable acceptance with eight scope, paging, grant, privacy, unreviewed-result suppression, and privilege assertions. The experiments status read returns lifecycle fields, protocol version, metric-key counts, timestamps, and only a result with a non-null review timestamp; rows without `reviewed_at` are suppressed. It excludes protocol narratives, raw observations/results, evidence, adverse-event details, and party identities. The funding read adds case/tranche status and timestamps under the same scope. It omits amounts, terms, rationale, evidence, and party IDs; the reader role has column-level access only to the fields its function needs. The 72-test Gateway/route-policy/migration selection and nine-check migration 468 disposable acceptance pass, including continued migration-459 aggregate-summary access after the funding grants are narrowed. The adoption read adds `GET /operator/api/solution-lifecycle/{location_id}/adoption`; migration 469 returns bounded location-targeted program status and timestamps, plus only the exact count of distinct, nonempty consent-checked adopter references after case/whitespace normalization when at least five are present. Repeated or blank references and non-consented events do not meet the threshold; source references, event details, evidence, and party IDs never leave the function. This is not a verified natural-person count. The focused Gateway/route-policy/migration selection passes 81 tests, and disposable PostgreSQL 16 applies/replays migrations 459 and 466–469 with seven grouped acceptance checks, including small-cohort suppression, duplicate-event resistance, existing summary compatibility, and runtime/Directus boundaries. Ruff, compilation, matrix validation, inventory checks, and diff checks pass. The scale-gate read adds `GET /operator/api/solution-lifecycle/{location_id}/scale-gates` under the same exact location grant and signed context. Migration 470 lists location-targeted gate type/status and approval presence/timestamp without exposing requirements, thresholds, measured values, metrics, units, evidence, or approver identity. Ninety focused tests pass; disposable PostgreSQL 16 applies/replays migrations 459 and 466–470 with seven grouped checks for scope, approval presence, field privacy, paging, summary compatibility, and role boundaries. The source reader has column-level access only to fields needed for the projection and existing aggregate. Candidate and legacy remain untouched; migration 470 is not rolled out. The replication status read adds `GET /operator/api/solution-lifecycle/{location_id}/replications` under the same exact read grant and signed context. Migration 471 requires both the target location and exact solution lineage. It returns lifecycle/result state, evidence-maturity level, review presence, and timestamps while excluding source experiment IDs, context, adaptation plans, protocol, evidence, and reviewer identity. Ninety-nine focused tests pass; disposable PostgreSQL 16 applies/replays migrations 459 and 466–471 with seven grouped scope, privacy, pagination, aggregate-compatibility, and privilege checks. Candidate and legacy remain untouched; migration 471 is not rolled out. The learning read adds `GET /operator/api/solution-lifecycle/{location_id}/learning`; migration 472 includes only records linked to a human-reviewed replication targeting the exact location and exact solution lineage. It exposes status bands and timestamps, omitting lesson content, recommendations, evidence, source IDs, versions, and identities. The 108-test focused selection passes; disposable PostgreSQL 16 applies/replays migrations 459 and 466–472 with eight grouped lineage, redaction, grant, paging, summary-compatibility, and role-boundary checks. Candidate and legacy remain untouched; migration 472 is not rolled out. The retirement read adds `GET /operator/api/solution-lifecycle/{location_id}/retirements`; migration 473 returns redacted retirement status only for solutions originated at the exact location because the source has no target scope. Shared-solution retirement state is excluded for link-only locations. The 117-test focused selection passes; disposable PostgreSQL 16 applies/replays migrations 459 and 466–473 with eight scope, authorization, privacy, pagination, summary-compatibility, and role-boundary checks. Candidate and legacy remain untouched; migration 473 is not rolled out. Migration 474 and the legacy service now require an attributed proposer and a distinct approver, prevent attribution changes after approval, and leave legacy rows untouched at install. The 120-test non-database selection passes with the default-database integration test excluded; disposable PostgreSQL 16 applies/replays migrations 459 and 466–474 with five independent-review checks. Candidate and legacy remain untouched; migration 474 is not rolled out. The Gateway now exposes the first retirement write at `POST /operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/approve` under exact `solution_lifecycle:review` and signed tenant context. Migration 475 requires exact location-origin lineage, an active OIDC-to-person binding distinct from the proposer, evidence, a migration plan, and a replacement for superseded decisions; it atomically writes status plus an append-only idempotent receipt. The 125-test Gateway/route-policy/migration-metadata selection passes; disposable PostgreSQL 16 applies/replays migrations 459 and 466–475 with five authorization, prerequisite, retry/atomicity, and privilege groups. Runtime cannot access the source or receipt tables directly, and Directus cannot execute the action. Candidate and legacy remain untouched; migration 475 is not rolled out. The proposal action adds `POST /operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/retirements` under exact `solution_lifecycle:create` context. Migration 476 requires an active OIDC-to-person proposer, exact location-origin lineage, bounded evidence and plan, and a location-visible replacement for superseded decisions; proposal plus append-only receipt are atomic and idempotent. The function explicitly supplies IDs, `proposed` status, and timestamp for legacy tables without defaults; a separate non-login proposal owner has no retirement update or approval-attribution privileges. The 137-test focused selection passes, and disposable PostgreSQL 16 applies/replays migrations 459 and 466–476 with five proposal acceptance groups. Candidate and legacy remain untouched; migration 476 is not rolled out. The learning proposal action adds POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning under exact signed create scope. Migration 477 accepts only completed, actively reviewed replications targeting the exact location and linked to exact solution lineage, with active OIDC-to-person proposer attribution. It creates a proposed learning record and append-only idempotent receipt; bounded allowlisted lesson fields are validated in Gateway and PostgreSQL, retries return the same receipt, and changed-input request reuse is rejected. Runtime has no direct learning-record or receipt access; Directus cannot call the function. The 16-test Gateway/route-policy selection passes; disposable PostgreSQL 16 applies/replays migration 477 and passes nine acceptance groups. Migration 477 is not rolled out. Evidence: builds/2026-10-19-recovery/cap-035-solution-learning-proposal-disposable.json. CAP-035 remains prepared pending gate evaluation/approval and remaining lifecycle write/review workflows, populated reference fixtures, live OIDC/browser acceptance, broader ACL/RLS, recovery acceptance, and MAN-CAP-035 owner review ([contract](solution-lifecycle-kernel-read-contract.md); [migration](../schemas/postgres/459_location_scoped_solution_lifecycle_summary.sql); [evidence](builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json); [gate migration](../schemas/postgres/466_location_scoped_solution_gates.sql); [gate evidence](builds/2026-10-19-recovery/cap-035-solution-gates-disposable.json); [experiment migration](../schemas/postgres/467_location_scoped_solution_experiments.sql); [experiment evidence](builds/2026-10-19-recovery/cap-035-solution-experiments-disposable.json); [funding migration](../schemas/postgres/468_location_scoped_solution_funding.sql); [funding evidence](builds/2026-10-19-recovery/cap-035-solution-funding-disposable.json); [adoption migration](../schemas/postgres/469_location_scoped_solution_adoption.sql); [adoption evidence](builds/2026-10-19-recovery/cap-035-solution-adoption-disposable.json); [scale-gate migration](../schemas/postgres/470_location_scoped_solution_scale_gates.sql); [scale-gate evidence](builds/2026-10-19-recovery/cap-035-solution-scale-gates-disposable.json); [replication migration](../schemas/postgres/471_location_scoped_solution_replications.sql); [replication evidence](builds/2026-10-19-recovery/cap-035-solution-replications-disposable.json); [approval action](../../services/gateway/solution_lifecycle_actions.py); [migration 475](../schemas/postgres/475_location_solution_retirement_review.sql); [approval evidence](builds/2026-10-19-recovery/solution-retirement-approval-disposable.json); [proposal migration](../schemas/postgres/476_location_solution_retirement_proposal.sql); [proposal evidence](builds/2026-10-19-recovery/solution-retirement-proposal-disposable.json)).; migration 481 adds a bounded exact-origin-only retirement-candidate read under signed location context and exact read grant, with runtime function execution and Directus denial; the retirement proposal form requires exact read/create grants, CSRF, bounded evidence/plan fields, and retry-stable requests, and creates only proposed records for independent review; the 176-test focused selection passes and disposable PostgreSQL 16 applies/replays migration 481 with nine scope, grant, pagination, privacy, and role-boundary groups; candidate and legacy databases are untouched and migration 481 is not rolled out; Migration 482 adds a separately owned, exact-review-grant inbox/detail projection and a text-only approval panel; the review role has narrow tenant-check and proposal-column access, proposer identity is never returned, self-review is blocked, and cross-location replacement approval is rejected; 122 focused tests and seven disposable PostgreSQL 16 review/trigger groups pass; candidate/legacy remain untouched and migration 482 is not rolled out; migration 483 adds exact-location-origin pass/fail evaluation submission under signed `solution_lifecycle:create` and active OIDC-to-person attribution. The console form requires both read and create grants and keeps gate approval separate. Bounded observations/evidence append through a dedicated non-login function owner with same-payload idempotency receipts; runtime cannot access receipt/source tables directly and Directus cannot execute the function. The 38-test Gateway/route-policy/console selection and disposable PostgreSQL 16 apply/replay with eight acceptance groups pass. Candidate and legacy remain untouched; migration 483 is not rolled out. Migration 484 adds private gate-evidence review at `/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/review` and independent approval at `.../approve`. The review projection requires exact signed review scope and a current human binding, returns bounded latest evidence without evaluator identity, and uses a separate non-login function owner. For gates marked as requiring human approval, approval requires a latest passing evaluation and a distinct active human reviewer; gates without that flag preserve the legacy confirmation path for an active operator; the gate status update and append-only idempotency receipt are atomic, while solution-stage transition remains separate. Migration 485 preserves the legacy confirmation path for gates that do not require independent human review, while human-required gates still enforce a distinct reviewer. The console labels these actions separately under the same exact review grant and keeps evaluation behind the create grant. The combined focused selection passes 82 tests; disposable PostgreSQL 16 applies/replays migrations 483/484 and passes eight evaluation plus seven review/approval groups. Candidate/legacy are untouched and migration 484 is not rolled out. Migration 486 adds the separate exact-location `solution_lifecycle:transition` action. It revalidates the approved current-stage gate, latest passing evaluation, positive minimum pass count, independent reviewer when required, and legacy maturity/experiment/funding/adoption/scale prerequisites. Stage, attributed lifecycle event, and immutable retry receipt are atomic; runtime has function-only access and Directus cannot execute it. The grant-gated console requires rationale, evidence, acknowledgement, CSRF/no-store, and stable retries. Thirty-five focused tests and 22 grouped disposable PostgreSQL acceptance groups pass; candidate and legacy remain untouched and migration 486 is not rolled out. CAP-035 remains prepared pending live and owner acceptance. Migration 487 adds private exact-location experiment review detail and one independent result-submission action. The read is bounded to protocol, analysis, and 100 recent observations; result, status, and immutable receipt writes are atomic and idempotent, reviewers must be distinct from the experiment owner and protocol approver, and solution stage is unchanged. The 74-test focused selection and ten additional disposable PostgreSQL acceptance groups pass; candidate and legacy databases are untouched and migration 487 is not rolled out. Migration 488 adds an exact-location funding target list and an idempotent draft/proposed-tranche action. It requires signed read/create scope and an active human binding, returns no financial payload, and cannot submit, approve, release, or advance lifecycle stage. The focused Gateway/route/console/migration selection passes 189 tests; disposable PostgreSQL 16 applies/replays migration 488 and verifies exact-origin targeting, identity/grant checks, payload bounds, retry collision rejection, draft/proposed states, private receipt ACLs, and unchanged stage. Candidate and legacy are untouched; migration 488 is not rolled out. Migration 489 adds the separate signed `solution_lifecycle:submit` action for exact-location drafts created by the same active operator and human party. It atomically changes only `draft` to `submitted` with a private retry receipt; tranches remain proposed, and no approval, release, or solution-stage transition occurs. The 196-test focused selection and disposable PostgreSQL 16 apply/replay checks for migrations 488–489 pass, including retries, collisions, duplicate-submit rejection, role boundaries, and unchanged stage. Candidate and legacy remain untouched; migration 489 is not rolled out. CAP-035 remains prepared pending populated parity, live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-035 owner review. Private funding review queue and detail now use migration 490 under signed exact-location `solution_lifecycle:review` and active human binding; a separate non-login owner has column-scoped access, the queue omits narratives/person IDs, detail returns bounded private terms/evidence/proposed tranches, self-authorship and attribution are labeled, legacy unattributed cases remain unattributed, and no approval/release/stage-transition action is implemented. The 100-test migration/Gateway/route-policy/console selection passes with Ruff, Python compilation, inline JavaScript syntax, capability-matrix validation, and refreshed runtime SQL inventory; disposable PostgreSQL migration apply/replay/authorization/role-boundary acceptance passes, and candidate and legacy remain untouched. Migration 491 adds separately acknowledged independent approval of attributed submitted funding cases under the exact review grant; it changes only case decision/reviewer attribution, preserves proposed tranches and solution stage, and passes 108 focused tests plus disposable PostgreSQL apply/replay/authorization/privilege acceptance. Candidate and legacy remain untouched; migration 491 is not rolled out. Migration 492 adds bounded exact-location tranche review and independent approval after case approval; an active human distinct from submitter and case approver may approve one proposed tranche. It records only tranche approval and reviewer attribution with an immutable retry receipt; no release or stage transition occurs. The 117-test Gateway/route/console/migration selection and disposable PostgreSQL 16 apply/replay acceptance pass; candidate and legacy remain untouched, and migration 492 is not rolled out. Migration 493 adds a protected adoption-event summary by five coarse progress phases; only consent-checked normalized distinct references are counted; references may overlap between phases, so the counts are not additive or verified person totals. The complete phase breakdown is suppressed if any populated phase has fewer than five references. The focused Gateway, console, route-policy, and migration-metadata selection passes 175 tests; disposable PostgreSQL 16 applies/replays migration 493 and passes 13 grouped scope, consent, suppression, and privilege checks. Candidate and legacy remain untouched; migration 493 is not rolled out ([contract](solution-lifecycle-kernel-read-contract.md); [evidence](builds/2026-10-20-recovery/cap-035-solution-adoption-event-summary-disposable.json)). Migration 494 adds a location-scoped replication proposal action requiring an exact create grant, active human attribution, an active solution visible by exact location origin or explicit location link (including a distinct context within the same farm), and a validated source experiment with an actively reviewed validated result whose reviewer is distinct from the experiment owner and protocol approver. The proposal and immutable retry receipt are atomic; status stays proposed and solution stage is unchanged. The console uses read/create-grant-gated source selection, CSRF/no-store requests, and stable retry IDs. The focused Gateway/console/route-policy/migration selection passes 85 tests; disposable PostgreSQL 16 applies/replays migration 494 and passes nine authorization, lineage, retry, state, and role-boundary groups. Candidate and legacy remain untouched; migrations 494–495 are not rolled out. Migration 495 adds private exact-location queue/detail and independent approve/reject for proposed replications; reviewers must be active humans distinct from attributed proposers, rejection requires a reason, and immutable receipts make exact retries safe. Decisions do not activate or complete replication or change solution stage. The 97-test focused Gateway/proposal/console/route-policy/migration selection passes; disposable PostgreSQL 16 applies/replays 495 and passes nine grouped checks. Ruff, compilation, inline JavaScript, matrix validation, and refreshed runtime SQL inventory pass. Candidate and legacy remain untouched ([write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/495_location_solution_replication_review.sql); [tests](../tests/test_gateway_solution_replication_review.py); [disposable check](../../scripts/check-solution-replication-review-disposable.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-replication-review-disposable.json)). Migration 496 adds exact-location independently approved replication activation with an append-only retry receipt and trigger-guarded lifecycle fields; ten disposable PostgreSQL groups and the 108-test focused selection pass, with candidate and legacy untouched and rollout pending. Migration 497 adds a bounded exact-location completion-report proposal API for active started replications; it requires submit grant, active human attribution, current independent approval and validated source lineage, bounded evidence, and idempotent retries. It records only a private pending report; the replication and solution remain unchanged. Migration 498 adds an independent completion-review queue and decision with immutable receipts and reviewer attribution; the console requires exact review scope, current source lineage, non-conflicting human actors, CSRF/acknowledgement, and stable retry IDs. Acceptance completes the replication while preserving the solution stage; rejection leaves it active for a revised report. A submit-grant console form now lets exact-location readers submit bounded completion reports for active replications; same-origin CSRF, acknowledgement, validation, and unchanged-request retry IDs preserve the pending-report boundary. Migration 499 adds an independent exact-location learning-review queue/detail and accept/reject action; review revalidates current source lineage and separates the reviewer from all upstream actors. Decisions use immutable retry receipts and do not apply learning or advance solution stage; legacy application helper is retired and fails closed; separately authorized application is provided through migration 500. The focused selection passes 94 tests with one skip, and disposable PostgreSQL 16 migration apply/replay passes eleven grouped checks. Candidate and legacy are untouched and migration 499 is not rolled out ([migration](../schemas/postgres/499_location_solution_learning_review.sql); [tests](../tests/test_gateway_solution_learning_review.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-learning-review-disposable.json)). Migration 500 adds a separate exact-location accepted-learning application queue/action under `solution_lifecycle:apply`, with current source-lineage revalidation, active human attribution, applier/reviewer separation, explicit acknowledgement, bounded version, and immutable retry receipt. Application does not change solution stage. The focused application/Gateway/console/route-policy selection passes 64 tests with one database-backed skip; disposable PostgreSQL 16 applies/replays migration 500 and passes nine grouped checks. Candidate and legacy are untouched; migration 500 is not rolled out ([migration](../schemas/postgres/500_location_solution_learning_application.sql); [tests](../tests/test_gateway_solution_learning_application.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-learning-application-disposable.json)). The legacy direct retirement proposal and approval helpers are now fail-closed before database access; scoped Gateway proposal/review actions remain available. Retirement execution and sunset workflows remain open, and MAN-CAP-035 acceptance is unchanged. Migration 501 adds exact-location, evidence-backed scale-gate assessment with PostgreSQL-derived typed comparator results and independent human accept/reject review; neither decision changes solution stage. Disposable PostgreSQL 16 apply/replay and nine acceptance groups pass; candidate and legacy are untouched and migration 501 is not rolled out. The legacy direct scale-gate helper fails closed. Migration 502 adds exact-location migration start, effective-date sunset, and independent post-retirement review with append-only retries and no deletion; focused Gateway, route-policy, console, legacy, and migration checks pass (134 passed, 1 skipped), and disposable PostgreSQL 16 apply/replay plus nine acceptance groups pass. Candidate and legacy remain untouched; migration 502 is not rolled out. CAP-035 remains prepared pending populated parity and owner acceptance. Repository-only source audit disabled the legacy direct learning insert and verifies fail-before-cursor behavior; remaining direct solution, experiment, adoption, and funding helpers are inventoried; the unsafe adoption-event helper and legacy gate approval/evaluation helpers now fail closed; consent-aware event ingestion and separately governed funding release remain open; the legacy stage-transition writer now fails closed, migration 486 covers gate-backed promotions, and migration 503 now covers the remaining non-promotion stage transitions. Migration 503 adds exact-location non-promotion stage target/read and transition routes with acknowledgement, active-human attribution, expected-stage compare-and-set, atomic lifecycle event and private retry receipt; adopting retains readiness/configuration checks, while promotion, retirement, and supersession remain in their dedicated workflows. The 38-test focused selection and 14-group disposable PostgreSQL 16 apply/replay pass; candidate and legacy remain untouched and migration 503 is not rolled out. Migration 504 adds exact-location discovered-solution creation at `POST /operator/api/solution-lifecycle/{location_id}/solutions`, with signed create scope, active-human attribution, an opening lifecycle event, and a private immutable retry receipt. The console requires exact read/create grants, acknowledgement, CSRF, no-store, and stable retries. It does not expose cross-location linking. Migration 505 adds exact-origin promotion-gate draft definition. Legacy create/link/gate helpers now fail before database access; link sharing remains an explicit policy gate; gate evaluation, independent approval, and transition remain separate. The focused Gateway, console, route-policy, legacy, and migration selection passes 123 tests with four database-backed skips; Ruff and Python compilation pass. Disposable PostgreSQL 16 applies/replays migration 504 and passes nine grouped authorization, validation, origin, event atomicity, retry, and receipt-boundary checks. Candidate and legacy remain untouched; migration 504 is not rolled out. Migration 505 adds a bounded exact-origin draft-gate route and console form, exposes criteria only to the owning location, and passes 214 focused tests plus ten disposable PostgreSQL 16 acceptance groups; migration 505 is not rolled out. Migrations 506–512 now provide experiment draft, submission, independent approval, start, consent-aware observation capture, protocol-bound advisory analysis, and stopping-boundary completion. Forced RLS hides withdrawn and unassessed observations and derived analyses; immutable completion receipts do not bypass independent result review. The focused completion/Gateway/console/route-policy/migration selection passes 161 tests; disposable PostgreSQL 16 applies/replays migrations 510–512 and passes 20 consent, directional-analysis, stopping-boundary, retry, withdrawal, RLS, and ACL groups. Candidate and legacy remain untouched; migration 512 is not rolled out. CAP-035 remains prepared pending populated parity, live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance ([write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/510_location_solution_experiment_observation_capture.sql); [disposable evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-observation-disposable.json)). Six legacy funding proposal and decision helpers now fail before database access; tranche disbursement remains explicitly disabled pending a separate custody contract. The focused funding/Gateway/route-policy selection passes 163 tests and changes no database or migration ([source-to-route audit](solution-lifecycle-source-route-audit.md); [regression](../tests/test_solution_funding.py)). Current checklist: 766 complete / 24 open; matrix classifications remain 31 baseline-retained, 7 deployed, and 28 prepared. Migrations 513 and 515 provide exact-location, active-human adoption-program draft creation at `POST /operator/api/solution-lifecycle/{location_id}/adoption/programs`; migration 515 extends eligibility to active exact-origin `pilot_active` solutions so preparation can happen before the adoption-ready gate. Drafts have location target scope, empty target population, and a private immutable retry receipt; the legacy `create_program` helper is retired. The console requires exact read/create grants. The focused lifecycle selection passes 109 tests; disposable PostgreSQL 16 apply/replay passes seven grouped checks. Candidate and legacy remain untouched; migration 513 is not rolled out. Readiness, configuration approval, consent-aware events, and launch remain open. Migration 514 retires the legacy direct readiness and configuration writers and revokes runtime/Directus table- and column-level DML while preserving reads. The five focused service tests pass; disposable PostgreSQL 16 apply/replay passes five privilege groups. Scoped readiness proposal/review and configuration draft/approval routes remain open. Migration 515 resolves the adoption-ready draft-creation cycle by allowing preparation for active exact-origin `pilot_active` solutions while retaining separate readiness, configuration, and enablement reviews. The combined focused selection passes 110 tests; disposable PostgreSQL 16 replays migrations 513/515 with eight groups. Neither migration is rolled out. Migration 520 now binds an immutable exact-purpose/version consent policy to submitted adoption programs and adds `solution_lifecycle:collect` event capture. The Gateway hashes participant references before database access; PostgreSQL requires an active exact-location participant link and current matching consent, stores only provenance IDs, supports immutable retries, and excludes withdrawn/revoked participants from projections with suppression below five. The focused Gateway/console selection passes 113 tests, and the expanded migration-metadata/route-policy selection passes 149 tests; disposable PostgreSQL 16 acceptance for migrations 513–520 passes 51 groups; the migration has not been rolled out to candidate or legacy. Populated parity, live ZITADEL/browser, broader runtime ACL/RLS, recovery, and MAN-CAP-035 owner acceptance remain open. |
| CAP-036 | Sequential evidence & decisions | services/decision/; services/gateway/sequential_decision_reads.py; services/gateway/sequential_decision_routes.py; apps/operator-console/index.html; schemas/postgres/460_location_scoped_sequential_decision_summary.sql; docs/refactor/sequential-decision-kernel-read-contract.md; schemas/postgres/478_location_sequential_evidence_timeline.sql; docs/refactor/sequential-evidence-subject-lineage-inventory.md| MAN-CAP-036: Ordered ledger, odds and decisions retain sequence and evidence integrity | tests/test_sequential_evidence.py; tests/test_sequential_integration.py; tests/test_gateway_sequential_decision_reads.py; tests/test_operator_console_sequential_evidence.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-sequential-decision-summary-disposable.py; scripts/check-sequential-evidence-timeline-disposable.py; scripts/check-sequential-subject-lineage.py; docs/refactor/builds/2026-10-20-recovery/cap-036-subject-lineage-source-audit.json| P — the operator console now displays the protected aggregate summary and redacted ordered timeline under exact location grants, without writes; the first Kernel slice adds `GET /operator/api/sequential-evidence/{location_id}/summary` under exact location `sequential_evidence:read` and signed tenant context. Migration 460 returns aggregate hypothesis lifecycle, evidence-quality, posterior-update, applied-event, and latest threshold-action counts for hypotheses linked only through exact location strategy plans, threats, or explicitly location-linked solutions. It excludes statements, event IDs, source references, values, likelihoods, probabilities, identities, and unscoped subjects; ledger writes and calculation behavior are unchanged. Focused Gateway/route-policy/migration-metadata plus legacy decision checks pass 53 tests with two database-dependent skips; disposable PostgreSQL 16 applies/replays migration 460 and passes six scope, lineage, privacy, and privilege assertions. Candidate and legacy databases are untouched; migration 460 is not rolled out. CAP-036 remains prepared pending populated/archived corpus lineage, populated reference fixtures, live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-036 owner review ([contract](sequential-decision-kernel-read-contract.md); [migration](../schemas/postgres/460_location_scoped_sequential_decision_summary.sql); [evidence](builds/2026-10-19-recovery/cap-036-sequential-decision-disposable.json)). The item-level `GET /operator/api/sequential-evidence/{location_id}/events` route returns a bounded, stable timeline for exact location-scoped strategy-plan, threat, and solution hypotheses. It exposes sequence ordinals, timestamps, evidence class/quality, and posterior update sequence/version only; statements, source refs/IDs, values, likelihoods, probabilities, row IDs, and identities remain private. Unknown subject types remain excluded. The focused Gateway/route-policy suite passes 23 tests; Ruff and compilation pass. Disposable PostgreSQL 16 applies/replays migration 478 and passes eight ordering, paging, lineage, privacy, grant, and role-boundary groups. Candidate and legacy are untouched; migration 478 is not rolled out. The 20 October repository source audit found one generic sequential-ledger writer and no production callers; migrations 460 and 478 have the same three exact location lineages. Unknown subject types remain excluded, and populated/archived data still needs its own aggregate inventory ([source inventory](sequential-evidence-subject-lineage-inventory.md); [audit evidence](builds/2026-10-20-recovery/cap-036-subject-lineage-source-audit.json)).
| CAP-037 | Operating pilot | services/management/operating_pilot.py; services/management/operating_support.py; services/gateway/operating_pilot_reads.py; services/gateway/operating_pilot_writes.py; services/gateway/operating_pilot_routes.py; services/gateway/operator_auth.py; apps/operator-console/index.html; schemas/postgres/461_location_scoped_operating_pilot_summary.sql; schemas/postgres/479_location_operating_pilot_demand_signals.sql; schemas/postgres/480_location_operating_pilot_capacity_periods.sql; schemas/postgres/526_location_operating_pilot_work_claims.sql; schemas/postgres/538_location_operating_pilot_resource_categories.sql; schemas/postgres/552_location_operating_pilot_demand_draft.sql; schemas/postgres/553_location_operating_pilot_capacity_draft.sql; schemas/postgres/554_location_own_operating_pilot_capacity.sql; schemas/postgres/555_location_operating_pilot_capacity_draft_revision.sql; schemas/postgres/556_location_operating_pilot_capacity_draft_submission.sql; schemas/postgres/557_location_operating_pilot_capacity_review_queue.sql; schemas/postgres/558_location_operating_pilot_capacity_review_decision.sql; schemas/postgres/559_location_operating_pilot_demand_draft_submission.sql; schemas/postgres/560_location_operating_pilot_demand_review_queue.sql; scripts/check-operating-pilot-summary-disposable.py; docs/refactor/operating-pilot-kernel-read-contract.md; schemas/postgres/561_location_own_operating_pilot_demand.sql; schemas/postgres/562_location_operating_pilot_demand_draft_revision.sql; schemas/postgres/563_location_operating_pilot_demand_review_decision.sql; schemas/postgres/564_location_operating_pilot_work_opportunities.sql; schemas/postgres/565_location_operating_pilot_work_claim_review.sql; schemas/postgres/566_location_operating_pilot_work_claim_allocation.sql; schemas/postgres/567_location_operating_pilot_resource_request_draft.sql; schemas/postgres/568_location_own_operating_pilot_resource_requests.sql; schemas/postgres/569_location_operating_pilot_resource_draft_revision.sql; schemas/postgres/570_location_operating_pilot_resource_draft_submission.sql; schemas/postgres/571_location_operating_pilot_resource_review_queue.sql; schemas/postgres/572_location_operating_pilot_resource_review_decision.sql; schemas/postgres/573_location_operating_pilot_resource_fulfillment.sql; schemas/postgres/574_location_operating_pilot_competency_draft.sql; schemas/postgres/575_location_own_operating_pilot_competency_drafts.sql; schemas/postgres/576_location_operating_pilot_competency_draft_lifecycle.sql; schemas/postgres/577_location_operating_pilot_competency_review.sql; schemas/postgres/605_location_own_operating_pilot_learning_plans.sql; schemas/postgres/606_location_operating_pilot_learning_plan_draft.sql; schemas/postgres/607_location_operating_pilot_learning_plan_revision.sql; schemas/postgres/608_location_operating_pilot_learning_plan_submission.sql; schemas/postgres/609_location_operating_pilot_learning_plan_review_queue.sql; schemas/postgres/610_location_operating_pilot_learning_plan_review_decision.sql; schemas/postgres/611_location_scoped_operating_coaching_sessions.sql; tests/test_gateway_operating_pilot_learning.py; tests/test_gateway_operating_pilot_writes.py ; schemas/postgres/612_location_operating_pilot_coaching_participants.sql; tests/test_operator_console_operating_pilot.py; schemas/postgres/629_location_operating_pilot_learning_plan_activation.sql| MAN-CAP-037: Capacity planning, work claims and competencies preserve scope and review | tests/test_operating_pilot.py; tests/test_gateway_operating_pilot_reads.py; tests/test_gateway_operating_pilot_writes.py; tests/test_gateway_operating_pilot_work_claims.py; tests/test_gateway_operating_pilot_work_claim_reviews.py; tests/test_gateway_operating_pilot_work_claim_allocations.py; tests/test_operator_route_policy_inventory.py; tests/test_operator_console_operating_pilot.py; tests/test_migration.py; scripts/check-operating-pilot-summary-disposable.py | P — Protected aggregate summary, bounded redacted demand page, aggregate capacity-period page, suppressed work-claim and resource-request category pages, and a private draft-only demand-create path for active Adelphi farm scopes; the console gates read and create surfaces on separate exact location grants. Demand reads expose only work type, period, hours, priority, and status. Migration 552 adds a same-transaction signed Gateway writer with exact create authorization, active human-party attribution, a private SHA-256 retry receipt, and conflict rejection for changed retries; the console preserves request ID and payload for safe retry. Creation always begins as `planning` / `draft` and provides no submit, approval, fulfillment, or lifecycle mutation. Migration 553 adds a self-attributed, self-reported capacity draft writer with exact create authorization, bounded hours and periods, private notes, retry idempotency, duplicate-period conflict handling, and direct runtime/Directus capacity-write revocation; the console provides create-grant-only entry without exposing read surfaces. Migration 554 adds an independent bounded `operating_pilot:read_own` path that returns only the authenticated operator’s own capacity records, including private notes; generic read and create grants do not imply this access, and runtime/Directus cannot select notes directly. The console renders the personal history under the separate grant. Migrations 576–577 add exact owner-revision/submission and independent verify/reject actions with retained versions and private idempotency receipts; reviewers cannot decide their own party's submissions, rejection feedback appears only in the submitter's own history, and verification leaves self-assessed values unchanged. The 317-test focused Gateway/route-policy/console selection passes; native and linux/arm64 Docker/QEMU disposable PostgreSQL 16 replay through migration 577 pass 199 grouped assertions ([focused checks](builds/2026-10-22-recovery/cap-037-competency-review-checks.json); [native](builds/2026-10-22-recovery/cap-037-competency-review-disposable.json); [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-competency-review-arm64-disposable.json)); console create/history/revise/submit/review parity is implemented and statically checked. Migration 605 adds a bounded, read-only `my-learning-plans` history under a separate `operating_pilot:read_own` grant; it exposes only the authenticated human party’s own exact-location plans and keeps plan creation/edit/review outside this slice ([read contract](operating-pilot-kernel-read-contract.md); [disposable evidence](builds/2026-10-24-recovery/cap-037-learning-plan-own-read-disposable.json)). Migration 555 adds a distinct exact-location `operating_pilot:edit_own` revision path for the caller's own self-reported draft: it preserves the old version as superseded and creates a replacement draft atomically, with idempotent retry receipts and collision rollback; it cannot revise submitted/reviewed records or invoke lifecycle actions. The console exposes revision only when both own-history read and edit-own grants are present. Migration 556 adds a one-way draft-to-submitted action under a separate exact `operating_pilot:submit_own` grant. It requires the operator’s own self-reported draft, uses a private exact-request receipt for retry, and leaves verification/approval to an independent review action. The console requires read-own plus submit-own and an explicit confirmation. Migration 557 adds a read-only queue for submitted self-reported profiles under an exact `operating_pilot:review` grant; the signed location, active reviewer binding, and Adelphi scope are rechecked, and the reviewer’s own party is excluded. It omits submitter identity and private notes and provides no lifecycle decision. The console exposes this queue only under the separate review grant. Migration 558 adds an independent approval/rejection action: it locks the active reviewer binding, excludes self-review, transitions only submitted self-reported profiles, requires a reason for rejection, and writes an append-only private decision receipt atomically. Exact retries replay; changed request reuse and repeat decisions fail closed. Rejected records can be revised by their owner into a new draft while preserving the old version and receipt. Runtime and Directus cannot directly change capacity status or access receipts. The focused Gateway/policy/console/migration selection passes 179 tests; network-disabled PostgreSQL 16 applies and replays migrations 461–558 with 52 grouped assertions, including reviewer denial, retry collision, rejection revision, and role boundaries ([decision evidence](builds/2026-10-22-recovery/cap-037-capacity-review-decisions-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-capacity-review-decisions-arm64-disposable.json)). The console decision form requires explicit acknowledgement, CSRF/no-store, and retains request IDs for exact retries. Candidate and legacy remain untouched; migration 558 is not rolled out. Capacity groups submitted/approved profiles by period and suppresses all hours below three contributors, including in the console. Migration 526 adds a bounded work-claim category projection: free-form work types map to a fixed allowlist or `other`, categories with fewer than three claimants suppress claim counts, and claim/item IDs, lifecycle states, identities, evidence, titles, descriptions, and reasons remain private. The console renders only category and count/suppression with text-only fields. Migration 564 adds a bounded work-opportunity page and self-claim proposal under exact `operating_pilot:claim_own`; proposals remain unassigned. Migration 565 adds an identity-blind bounded review queue and independent accept/reject action under exact `operating_pilot:review`, prohibits self-review, records acceptance without assignment, and keeps private append-only retry receipts; the console uses CSRF/no-store and stable request IDs. Migration 566 adds a distinct exact `operating_pilot:allocate` queue/action, reveals claimant names only to allocate-scoped operators, excludes unresolved competing claims, prevents self-allocation, changes only `allocation_status` and `assignee_party_id`, and preserves work lifecycle and accepted review state. Its private append-only receipt replays exact retries and rejects changed or repeated allocation; Directus/runtime cannot update assignment columns or read receipts directly. The focused Gateway, route-policy, and console selection passes 39 tests with Ruff, compilation, and inline JavaScript syntax checks. Native PostgreSQL 16 and ARM64/QEMU apply/replay through migration 566 pass all 82 grouped assertions ([native evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-arm64-disposable.json)). Candidate and legacy remain untouched; migration 566 is not rolled out. CAP-037 remains prepared pending other workflows, live OIDC/browser, populated parity, broader ACL/RLS, recovery, privacy, and owner acceptance. Migration 538 adds a resource-request category projection: legacy free text maps to fixed buckets, counts suppress below three requesters, and requester identity, narrative, urgency, decision, status, and dates remain private. Migration 559 adds a separate one-way draft-to-submitted action for the operator’s own demand draft under exact operating_pilot:submit_own scope; signed location, human-party binding, Adelphi mapping, ownership, and draft state are rechecked atomically with the private idempotency receipt. The console confirms submission, preserves request IDs on transport retry, and cannot approve or fulfill. The focused Gateway, route-policy, console, and migration metadata selection passes 114 tests; Ruff, Python compilation, JavaScript syntax, dependency-group/provider-boundary checks, and current runtime SQL inventory pass (4,537 execution sites). Network-disabled disposable PostgreSQL 16 applies/replays migrations 461–559 and passes all 54 grouped assertions ([native evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-disposable.json)); the same migration and assertion suite passes under linux/arm64 Docker/QEMU emulation ([ARM64 evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-arm64-disposable.json)). This establishes emulated software portability only, not Raspberry Pi hardware, performance, power-loss, or recovery acceptance. Candidate and legacy remain untouched, and migration 559 is not rolled out. Migration 560 adds an exact-location independent demand review queue limited to receipt-backed Kernel submissions; it excludes the reviewer’s own party and omits descriptions, source references, and submitter identity. The focused Gateway, route-policy, console, and migration metadata selection passes 138 tests; Ruff, compilation, JavaScript syntax, dependency-group/provider checks, and capability validation pass. Network-disabled PostgreSQL 16 applies/replays migrations 461–560 with all 56 grouped assertions on native AMD64 ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-disposable.json)); the same suite passes under linux/arm64 Docker/QEMU emulation ([ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-arm64-disposable.json)). This is emulated software portability only, not Raspberry Pi hardware, performance, power-loss, or recovery acceptance. Candidate and legacy remain untouched; migrations 559–561 are not rolled out. Migration 561 adds a private own-demand history route under exact `operating_pilot:read_own`; it requires signed context, exactly one active human-party binding, active Adelphi mapping, and the original operator/location-scoped draft receipt, then returns only that operator’s receipt-backed records including their private descriptions. Legacy rows, other parties, and other farms are excluded. Runtime can execute the bounded function but cannot select descriptions/source directly; Directus cannot execute it or read those columns. The Gateway is read-only/no-store; the console safely renders the owner-only history and pages it without decisions. The focused selection passes 152 tests, and native plus linux/arm64 Docker/QEMU disposable PostgreSQL 16 passes all 58 grouped assertions for migrations 461–561 ([native](builds/2026-10-22-recovery/cap-037-own-demand-read-disposable.json); [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-own-demand-read-arm64-disposable.json)). QEMU is software portability evidence only, not physical Raspberry Pi acceptance. Candidate and legacy remain untouched; migration 561 is not rolled out.  Migration 562 adds exact `operating_pilot:edit_own` demand revisions: only the signed operator’s receipt-backed draft/rejected planning signal at the exact active Adelphi location can be superseded into a new private draft. The transaction writes an idempotent revision receipt and a normal demand receipt for own-history continuity; submitted, receiptless legacy, cross-owner, other-farm and missing-grant cases fail closed. The console gates edit actions on both own-history read and edit-own scopes. Focused Gateway/policy/console/migration checks pass 123 tests; disposable PostgreSQL 16 migration apply/replay passes 61 assertion groups on native AMD64 and ARM64/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-own-demand-revision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-own-demand-revision-arm64-disposable.json)). Emulation does not establish Raspberry Pi hardware acceptance. Candidate and legacy are untouched; migration 562 is not rolled out. Migration 563 adds independent approve/reject decisions for receipt-backed submitted demand under exact review scope, rejects self-review and stale/legacy targets, commits lifecycle status with a private append-only reason/idempotency receipt, and leaves fulfillment separate. The focused Gateway, route-policy, console, and migration selection passes 133 tests; Ruff, Python compilation, inline JavaScript syntax, and diff checks pass. Network-disabled PostgreSQL 16 applies/replays migrations 461–563 with 65 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-decision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-decision-arm64-disposable.json)). QEMU is software emulation only, not Raspberry Pi hardware acceptance. Candidate and legacy are untouched; migration 563 is not rolled out. Demand fulfillment; further capacity/work-claim/competency/learning/coaching/resource actions, populated mapping/parity, live OIDC/browser, broader ACL/RLS, recovery, privacy/audience review, and owner acceptance remain open ([capacity migration](../schemas/postgres/480_location_operating_pilot_capacity_periods.sql); [work-claim migration](../schemas/postgres/526_location_operating_pilot_work_claims.sql); [resource migration](../schemas/postgres/538_location_operating_pilot_resource_categories.sql); [draft migration](../schemas/postgres/552_location_operating_pilot_demand_draft.sql); [capacity draft migration](../schemas/postgres/553_location_operating_pilot_capacity_draft.sql); [own-capacity read migration](../schemas/postgres/554_location_own_operating_pilot_capacity.sql); [own-capacity acceptance](builds/2026-10-22-recovery/cap-037-own-capacity-private-read-disposable.json); [own-draft revision acceptance](builds/2026-10-22-recovery/cap-037-own-capacity-draft-revision-disposable.json); [own-draft submission acceptance](builds/2026-10-22-recovery/cap-037-own-capacity-draft-submission-disposable.json); [ARM64/QEMU migration acceptance](builds/2026-10-22-recovery/cap-037-own-capacity-draft-submission-arm64-disposable.json); [capacity review queue acceptance](builds/2026-10-22-recovery/cap-037-capacity-review-queue-disposable.json); [capacity review ARM64/QEMU acceptance](builds/2026-10-22-recovery/cap-037-capacity-review-queue-arm64-disposable.json); [contract](operating-pilot-kernel-read-contract.md); [disposable evidence](builds/2026-10-19-recovery/cap-037-operating-pilot-capacity-disposable.json); [work-claim acceptance](builds/2026-10-21-recovery/cap-037-operating-pilot-work-claims-disposable.json); [resource-category acceptance](builds/2026-10-21-recovery/cap-037-operating-pilot-resource-categories-disposable.json); [draft-create acceptance](builds/2026-10-22-recovery/cap-037-operating-pilot-demand-draft-disposable.json); [demand submission acceptance](builds/2026-10-22-recovery/cap-037-demand-draft-submission-disposable.json); [demand review-queue acceptance](builds/2026-10-22-recovery/cap-037-demand-review-queue-disposable.json); [demand review-queue ARM64/QEMU acceptance](builds/2026-10-22-recovery/cap-037-demand-review-queue-arm64-disposable.json)). [demand review-decision migration](../schemas/postgres/563_location_operating_pilot_demand_review_decision.sql); [native decision acceptance](builds/2026-10-22-recovery/cap-037-demand-review-decision-disposable.json); [ARM64/QEMU decision acceptance](builds/2026-10-22-recovery/cap-037-demand-review-decision-arm64-disposable.json). Migration 567 adds a self-attributed resource-request draft under the exact location create grant; migration 568 adds receipt-backed own history under exact read_own. It stores private request content in a separate Kernel table, so drafts do not enter legacy submitted-request aggregates; exact retries replay and changed request reuse fails closed. Runtime can execute only the bounded function; runtime and Directus cannot read draft rows or receipts, and the non-login function owner cannot mutate receipts. Its separate own-history function exposes only the authenticated operator’s records and never returns receipt digests. The resource-create selection passed 114 tests and migration 567 passed 88 groups; the added history selection passes 170 tests and migration 568 passes 96 groups on native PostgreSQL 16 and ARM64/QEMU ([history native](builds/2026-10-22-recovery/cap-037-own-resource-request-read-disposable.json); [history ARM64/QEMU](builds/2026-10-22-recovery/cap-037-own-resource-request-read-arm64-disposable.json)). Migration 569 adds receipt-backed own-draft revision under exact location `operating_pilot:edit_own`; it atomically supersedes the prior draft, creates a replacement, preserves both in own history, and rejects submitted, stale, foreign, and out-of-scope targets. Exact retries replay; changed payloads and create-receipt collisions fail closed. The focused Gateway, route-policy, console, and migration selection passes 161 tests; native PostgreSQL 16 and linux/arm64 Docker/QEMU apply/replay migrations 461–569 and pass 107 grouped assertions ([revision native](builds/2026-10-22-recovery/cap-037-own-resource-request-revision-disposable.json); [revision ARM64/QEMU](builds/2026-10-22-recovery/cap-037-own-resource-request-revision-arm64-disposable.json)). QEMU is software portability evidence, not physical Raspberry Pi acceptance. Migration 570 adds explicit own-draft submission under a separate exact `submit_own` grant: the transaction creates a canonical `submitted` / `pending` row, links the draft, and appends an idempotency receipt; it performs no review or fulfillment. Exact retries replay, changed targets and request-ID collisions fail closed, and the response omits the canonical row ID. Runtime and Directus cannot directly read or mutate canonical resource requests or submission receipts; legacy unscoped create/decision helpers now fail before database access. The console confirms submission, uses CSRF/no-store and stable retry IDs, and leaves the submitted request read-only. The focused Gateway, policy, console, management-helper, and migration selection passes 1272 tests with one database-backed test skipped; native PostgreSQL 16 and linux/arm64 Docker/QEMU replay migrations 461–570 with 123 grouped assertions ([submission native](builds/2026-10-22-recovery/cap-037-own-resource-request-submission-disposable.json); [submission ARM64/QEMU](builds/2026-10-22-recovery/cap-037-own-resource-request-submission-arm64-disposable.json)). Independent review, fulfillment, populated parity, live OIDC/browser, broader ACL/RLS, production recovery, and owner acceptance remain open; candidate and legacy are untouched and migrations 567–570 are not rolled out. Migration 571 adds an independent, bounded review-only queue for receipt-backed submitted Kernel requests under exact `operating_pilot:review`; it omits requester identity, excludes self-review and legacy receiptless rows, and does not decide or fulfill requests. Focused tests pass 146; native and ARM64/QEMU disposable PostgreSQL replay through 571 passes 130 grouped assertions. Candidate and legacy remain untouched; review decisions and fulfillment remain open. Evidence: [native](builds/2026-10-22-recovery/cap-037-resource-request-review-queue-disposable.json), [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-resource-request-review-queue-arm64-disposable.json). Migration 572 adds independent approve/reject for receipt-backed Kernel resource requests under exact location review scope, with a private append-only idempotency/audit receipt; it excludes self-review and legacy rows, omits rejection reasons from responses, and does not partially allocate or fulfill resources. Focused Gateway/read/policy/console checks pass 254 tests; native and ARM64/QEMU PostgreSQL 16 apply/replay through 572 passes 146 grouped assertions. Candidate and legacy are untouched; migration 572 is not rolled out. Fulfillment, populated parity, live OIDC/browser, broader ACL/RLS, production recovery, and owner acceptance remain open. Evidence: [native](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-disposable.json), [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-arm64-disposable.json). Migration 574 adds a private, self-reported competency draft at `POST /operator/api/operating-pilot/{location_id}/competency-assessments`; it validates levels/evidence and request retries, enforces signed exact-location context and an active human binding, and writes neither the canonical profile nor verified state. Ten focused Gateway/route-policy checks pass; network-disabled PostgreSQL 16 migration apply/replay passes 176 grouped assertions on native AMD64 and ARM64/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-competency-draft-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-competency-draft-arm64-disposable.json)). Migration 575 adds bounded private own-history under a separate exact read_own grant, returning only receipt-backed rows for the signed actor’s single active human binding and current Adelphi scope; the owner alone can see their evidence note. Native and ARM64/QEMU disposable PostgreSQL replays through 575 pass 184 grouped assertions and the 1272-test focused Gateway-read/migration/route-policy selection passes ([native evidence](builds/2026-10-22-recovery/cap-037-competency-own-read-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-competency-own-read-arm64-disposable.json)). Migrations 574–576 are not rolled out. Competency owner revision/submission is implemented; console parity, independent review, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance remain open. Migration 606 adds exact-location private learning-plan draft creation with a create-only grant, signed scope checks, bounded input, an append-only idempotency receipt, and no lifecycle transition; focused route/console checks and disposable PostgreSQL replay are recorded in the latest local batch. Migration 607 adds owner-only revision of receipt-backed learning-plan drafts under a separate exact edit-own grant, with optimistic updated_at concurrency, a private retry receipt, content-column-only updates, and no lifecycle transition; native and ARM64/QEMU disposable replay through 607 passes 224 assertions as recorded in the latest local batch. Migration 608 adds owner-only submission of receipt-backed learning-plan drafts under a separate exact submit-own grant; it transitions only draft to submitted, records an append-only retry receipt, preserves plan content, strips stale table/column privileges from runtime/Directus, and leaves independent review separate. Migration 609 adds the exact-location receipt-backed review queue; migration 610 adds independent approve/reject decisions bound to the exact latest submission, with approval separate from activation and rejection feedback private to owner history. The focused Gateway, route-policy, console, and migration selection passes 401 tests; native and linux/arm64 QEMU disposable PostgreSQL 16 apply/replay through migration 610 passes 260 grouped assertions ([native](builds/2026-10-24-recovery/cap-037-learning-plan-review-decision-disposable.json); [ARM64/QEMU](builds/2026-10-24-recovery/cap-037-learning-plan-review-decision-arm64-disposable.json)). Candidate and legacy remain untouched; migrations 610 and 611 are not rolled out. The legacy unscoped coaching writer remains disabled; migration 611 adds private coaching capture and author-only history under exact coach grants, latest-consent checks, transaction-bound tenant context, and append-only idempotency receipts. Native disposable PostgreSQL replays through migration 611 with 269 assertion groups. At this migration-611 boundary the console form remained open; the follow-up migration-612 batch adds it. Live OIDC/browser acceptance remains open. Migration 612 adds a bounded consent-filtered participant selector that returns only the verified active participant ID and display name under the exact coach grant; the console adds coach-only participant selection, private capture, and own-history display with bounded paging, consent revalidation, text-only rendering, CSRF/no-store, and stable same-session retries. Native and ARM64/QEMU PostgreSQL 16 replay through 612 pass 278 grouped assertions, and the 283-test focused Gateway/write/policy/console/migration selection passes. These checks do not constitute physical Raspberry Pi or MAN-CAP acceptance; migration 612 is not rolled out. Latest local slice adds separately granted learning-plan activation after independent approval, exact-version receipt validation, owner self-activation denial, atomic lifecycle transition, and immutable idempotency; native and ARM64/QEMU disposable PostgreSQL acceptance passes 266 groups, and the focused Gateway/console/policy/migration selection passes 430 tests. Candidate and legacy are untouched, migration 629 is not rolled out, and named CAP-037 acceptance remains open.|
| CAP-038 | Agent ecosystem | services/agents/safety.py; services/agents/tasks.py; services/agents/base.py; services/agents/ai_summary.py; services/agents/logging.py; services/agents/cids_agent.py; services/agents/ebf_evidence_gap_agent.py; services/agents/ebf_calibration_agent.py; services/agents/ebf_scorecard_agent.py; services/agents/delphi_facilitator_agent.py; services/delphi/facilitator.py; services/delphi/cli.py; extensions/kokonut-hooks/src/agent-safety.ts; services/gateway/ai_summary_review.py; services/gateway/ai_summary_review_routes.py; services/gateway/ai_summary_draft.py; services/gateway/ai_summary_draft_routes.py; services/gateway/ai_summary_task_request.py; schemas/postgres/521_location_scoped_ai_summary_review.sql; schemas/postgres/522_authenticated_ai_summary_drafts.sql; schemas/postgres/523_ai_summary_source_references.sql; schemas/postgres/524_ai_summary_global_source_references.sql; apps/operator-console/index.html; docs/refactor/agent-ecosystem-kernel-contract.md ; services/agents/worker_draft.py; services/agents/worker_cli.py; services/registry/cids_export.py; schemas/postgres/529_signed_agent_ai_summary_drafts.sql; schemas/postgres/530_signed_agent_ai_summary_source_references.sql; schemas/postgres/531_capital_efficiency_synthesis_source_references.sql; schemas/postgres/532_registered_agent_source_reference_views.sql; schemas/postgres/533_regenerator_synthesis_source_references.sql; schemas/postgres/534_public_synthesis_source_reference_views.sql; schemas/postgres/535_consent_safe_wellbeing_feedback_source_views.sql; schemas/postgres/536_location_scoped_kokonut_commons_source_views.sql; schemas/postgres/537_registered_worker_summary_types.sql; schemas/postgres/539_agent_worker_structured_result_replay.sql; schemas/postgres/540_scoped_agent_source_references.sql; schemas/postgres/541_agent_synthesis_source_reader.sql; schemas/postgres/542_agent_deterministic_summary_source_reader.sql; schemas/postgres/543_tenant_scoped_agent_synthesis_source_views.sql; schemas/postgres/544_tenant_scoped_deterministic_summary_source_views.sql; schemas/postgres/547_signed_ai_summary_inspection_source.sql; schemas/postgres/548_signed_delphi_agent_summary_source.sql; services/common/tenant_context.py; scripts/check-agent-worker-ai-summary-disposable.py; services/agents/capital_efficiency_agent.py; services/agents/bio_factory_agent.py; services/agents/regenerator_agent.py; services/agents/commons_agent.py; services/agents/gnh_agent.py; services/agents/resilience_agent.py; services/agents/open_source_capitalist_agent.py; services/agents/wellbeing_agent.py; services/agents/feedback_agent.py; services/agents/kokonut_commons_agent.py; tests/test_synthesis_source_references.py; tests/test_tenant_context.py; services/common/worker_database.py; docker-compose.worker.yml; scripts/agent_write_boundary_inventory.py; docs/refactor/agent-write-boundary-inventory.json; services/agents/organic_readiness_agent.py; schemas/postgres/549_signed_organic_readiness_synthesis_source.sql; schemas/postgres/550_signed_ecological_modeling_synthesis_source.sql; schemas/postgres/551_ecological_synthesis_provenance_capacity.sql; services/analytics/ecological_modeling_v2.py; schemas/postgres/580_agent_source_worker_identity_split.sql; schemas/postgres/581_isolated_ai_summary_inspection_worker.sql; schemas/postgres/582_isolated_organic_readiness_worker.sql; schemas/postgres/583_isolated_ecological_modeling_worker.sql; schemas/postgres/584_isolated_holistic_wellbeing_worker.sql; schemas/postgres/585_isolated_feedback_worker.sql; schemas/postgres/586_isolated_commons_liberation_worker.sql; schemas/postgres/587_isolated_gnh_alignment_worker.sql; services/common/worker_database.py; docker-compose.worker.yml; tests/test_agent_worker_cli.py; tests/test_agent_tasks.py; tests/test_cids_export.py; tests/test_worker_database.py; tests/test_agent_summary_worker_profile.py; scripts/check-agent-worker-ai-summary-disposable.py; services/gateway/ai_summary_review.py; schemas/postgres/595_agent_task_draft_attribution.sql; schemas/postgres/596_agent_task_run_review_attribution.sql; schemas/postgres/597_ai_summary_operator_run_review_attribution.sql; schemas/postgres/628_authenticated_agent_task_requests.sql; tests/test_gateway_ai_summary_review.py; tests/test_operator_console_ai_summary_review.py| MAN-CAP-038: Agents draft/submit only; self-verification/publication/attestation is denied | tests/test_agent_safety.py; tests/test_agent_tasks.py; tests/test_agents_base.py; tests/test_ebf_agents.py; tests/test_agent_source_metadata.py; tests/test_ai_summary_safety.py; tests/test_ai_summary_cli_lifecycle.py; tests/test_ai_summary_source_references.py; tests/test_agent_input_preflight.py; tests/test_cids_export.py; tests/test_delphi.py; tests/test_agent_action_log_redaction.py; extensions/kokonut-hooks/src/agent-safety.test.ts; extensions/kokonut-hooks/src/schemas.test.ts; tests/test_gateway_ai_summary_review.py; tests/test_gateway_ai_summary_draft.py; tests/test_operator_console_ai_summary_review.py; tests/test_operator_route_policy_inventory.py; scripts/check-ai-summary-review-disposable.py; scripts/check-ai-summary-draft-disposable.py ; tests/test_agent_worker_draft.py; scripts/check-agent-worker-ai-summary-disposable.py; tests/test_worker_database.py; tests/test_agent_worker_cli.py; tests/test_agent_summary_worker_profile.py; tests/test_capital_efficiency.py; tests/test_bio_factory_operations.py; tests/test_regenerative_outcomes.py; tests/test_synthesis_source_references.py; tests/test_agent_write_boundary_inventory.py; scripts/check-organic-readiness-synthesis-disposable.py; scripts/check-ecological-modeling-synthesis-disposable.py; tests/test_synthesis_source_references.py | P — first Kernel safety slice denies verify/publish/attest and other high-risk execution, validates registered task write capabilities before shared/standalone task database access, limits declarations to an explicit draft/submission allowlist, and returns task metadata copies. Focused Python, Directus-hook, build, Ruff, and compilation checks pass. Both shared and standalone AI-summary runners validate declared top-level output presence, types, and UUID formats before draft persistence; 86 focused checks across 12 agent test files confirm invalid output cannot insert or commit and connections still close ([evidence](builds/2026-10-20-recovery/cap-038-agent-draft-validation.json)). Shared and standalone entry points now also validate declared required inputs, types, UUIDs, and exact dates before processing; 172 checks across 19 files pass with nine skips ([input evidence](builds/2026-10-20-recovery/cap-038-agent-input-preflight.json)). Input shape does not establish caller identity or tenant authorization. A separate 15-test fake-connection selection confirms direct shared/standalone persistence helpers reject invalid drafts before cursor creation ([write-boundary evidence](builds/2026-10-20-recovery/cap-038-agent-draft-write-boundary.json)); the final broader agent selection passes 182 tests with nine PostgreSQL-trigger checks skipped. The registered input/output schema declarations are validated as a supported top-level subset; a separate 35-test selection rejects unsupported declarations before task use ([catalogue evidence](builds/2026-10-20-recovery/cap-038-agent-schema-catalog.json)). Migrations 521–524 provide exact-location review, operator-requested draft paths, and a private append-only source manifest. The manifest records exact row counts and up to 50 ordered, location-checked IDs per location-owned source table; sensor and expense references match the summary’s displayed top-three sensor types and top-five configured expense categories, with deterministic ties; shared crop and expense-category IDs are verified through this location’s sales and top-five expense rows; summary values and references use one REPEATABLE READ snapshot; retry and review functions return the manifest under exact grants. The focused source-reference/Gateway/route-policy/console/safety selection passes 64 tests with nine PostgreSQL-dependent skips; disposable PostgreSQL 16 replays migrations 521–524 with 12 grouped checks ([source-reference evidence](builds/2026-10-20-recovery/cap-038-ai-summary-global-source-references-disposable.json)). New Gateway drafts record the requester, use immutable idempotency receipts, and cannot be reviewed by that requester; legacy unattributed drafts are rejectable but cannot be verified. Independent review sets verified only, never published, and a distinct reviewer/timestamp is required for later publication. Pre-existing legacy rows remain unattributed; new shared synthesis drafts record the signed worker principal. Other non-synthesis CLI/background writers remain subject to the broader identity gate. Other global references remain table-name hints, while location-owned source IDs are bounded samples rather than full evidence snapshots. A follow-up integrity fix binds the synthesis source-reference view map and custom SQL to the registered agent class, rejecting instance overrides before receipt lookup; the two focused worker/source-reference files pass 52 tests with Ruff and compilation. This closes only an in-process metadata override, not runtime identity or least privilege. Authenticated provider/runtime identity, DB least privilege, Directus runtime-role parity (source inventory finds 125 wildcard fields across 175 literal permission inserts plus four updates and one deletion, not deployed state), populated task parity, linked evidence, live OIDC/browser acceptance, recovery, and MAN-CAP-038 remain open ([contract](agent-ecosystem-kernel-contract.md); [agent safety](../agent-safety.md); [evidence](builds/2026-10-19-recovery/cap-038-agent-safety-source.json)). Standalone AI-summary CLI preflight and cleanup are covered by seven offline checks; this does not establish operator authentication, database authorization, tenant isolation, or MAN-CAP-038 acceptance. Shared agent draft persistence closes its cursor on failed insert/fetch and commits only after cursor close; 29 focused offline regression tests pass. AI-summary `--verify` is read-only digest inspection, not lifecycle review; eight offline checks confirm it performs only a SELECT. AI-summary listing requires a location filter or explicit `--all-locations`; the global list omits narrative previews, covered by three offline checks. Shared SynthesisAgent writes also validate source table metadata before opening a cursor; 82 combined agent/summary checks pass with nine database skips. The legacy Python set_agent_context() compatibility helper now fails before SQL because app.agent_id is caller-controlled; this prevents false local identity claims but does not authenticate agent runs or add least privilege. An earlier agent write-boundary snapshot pinned one direct DML site, the generic legacy SynthesisAgent ai_summary insert; the current inventory has zero literal direct-DML sites. Standalone and shared synthesis draft writers now use the signed worker adapter, and legacy agent-action writes/reads fail before database access. The focused logging/write-inventory/safety selection passes 16 tests with nine existing database-dependent skips; Ruff and compilation pass ([action-log evidence](builds/2026-10-21-recovery/cap-038-agent-action-log-fail-closed.json)). It records one authenticated Gateway draft-function call and four signed-worker bounded-function calls (draft lookup/create and source-reference attach/read), and zero set_agent_context/audit_agent_action call sites; dynamic SQL may be missed, and source coverage is not runtime authorization. Migration 529 adds a signed-worker draft adapter with a dedicated worker login, exact-location write function, immutable retry receipt, and separate worker attribution; nine adapter tests and eight disposable PostgreSQL acceptance groups pass with network disabled, including migration replay. Migration 530 attaches bounded, location-checked source-row manifests in the same transaction and exposes them through the reviewer queue; 18 adapter tests and 11 disposable PostgreSQL assertions pass, including forced-RLS source checks, location-linked shared crop/category references, migration replay, and unchanged operator setter behavior. The one-shot worker CLI is wired through an opt-in Compose service; four offline entry checks pass, including stdout redaction. The standalone AI-summary `--store` path now delegates to this signed worker path, validates a stable request ID before source reads, and suppresses stored content from CLI output; its 80-test summary/worker/write-boundary selection passes without skips. The EBF evidence-gap agent now requires both a scorecard UUID and location UUID and binds both to its summary-view query; 44 focused agent/task checks pass. This narrows the query scope, while authenticated tenant authorization, RLS, and a least-privilege runtime identity remain open ([evidence](builds/2026-10-21-recovery/cap-038-ebf-evidence-location-scope.json)). The current static inventory records zero literal direct-DML sites in `services/agents`; all ten shared `SynthesisAgent` draft paths now use the signed worker adapter with exact location scope and request receipts. Capital-efficiency synthesis now attaches bounded row IDs for four exact-location published views; other generic task drafts retain table-name hints without row-level manifests, and exact retries now return their original bounded structured result through a private append-only receipt (migration 539); pre-migration receipts retain the content-only fallback. Migrations 529–542 and source/draft worker credentials remain required before use; deterministic source reads now have a separate 13-relation reader, while other non-synthesis agent tasks still need review. Migration 540 records three explicit provenance scopes across 40 migration-approved public views (28 exact-location, six network-wide, six location-plus-unassigned); its disposable PostgreSQL 16 apply/replay passes 28 assertions and the operator review queue preserves scope labels ([evidence](builds/2026-10-22-recovery/cap-038-scoped-agent-source-references-disposable.json)). Migration 541 gives shared synthesis a separate read-only login with explicit SELECT on those 40 public views; it permits only three PostGIS metadata catalog names when installed and already readable by PUBLIC. It denies other public-relation access, writes, and public-schema CREATE, and the source-only Compose profile has no shared database settings. The chain through migration 541 passed 29 grouped assertions; with migration 542 it passes 31 in native PostgreSQL 16 and ARM64/QEMU. This is relation-level least privilege and does not establish tenant RLS. No candidate rollout or credentials provisioning has occurred. Source manifests for unregistered and legacy/background tasks, runtime/Directus least privilege, populated provider parity, and owner acceptance remain open ([worker evidence](builds/2026-10-21-recovery/cap-038-agent-worker-draft-disposable.json); [source-reference evidence](builds/2026-10-21-recovery/cap-038-agent-worker-source-references-disposable.json); [worker CLI evidence](builds/2026-10-21-recovery/cap-038-agent-summary-worker-cli.json); [standalone store evidence](builds/2026-10-21-recovery/cap-038-agent-summary-legacy-writer-retirement.json); [structured-result replay evidence](builds/2026-10-21-recovery/cap-038-worker-structured-result-replay-disposable.json)). The shared compatibility writer also attaches its declared location-view references to signed worker drafts (61 focused tests); this helper alone does not establish repeatable-read or authenticated source-read isolation ([evidence](builds/2026-10-21-recovery/cap-038-shared-writer-source-references.json)). The EBF evidence-gap query also closes its cursor on SQL execution/fetch failures and the shared runner closes the connection (49 focused tests); authorization and runtime least privilege remain open ([evidence](builds/2026-10-21-recovery/cap-038-ebf-query-resource-cleanup.json)). The deterministic one-shot worker validates and canonicalizes location/request UUIDs and rechecks task capabilities, required inputs, read permission, and draft-only creation permission before retry lookup; malformed IDs or unsafe registry changes fail before receipt/source DB access (53 focused worker/task/safety tests; [UUID evidence](builds/2026-10-21-recovery/cap-038-worker-cli-uuid-preflight.json); [replay-policy evidence](builds/2026-10-21-recovery/cap-038-worker-replay-safety-preflight.json)). This is input/policy preflight only. Migration 543 also adds signed database scope for the ten shared synthesis agents through 40 security-barrier views; the 189-test focused selection and 31-group disposable PostgreSQL apply/replay pass ([evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-agent-synthesis-source-views-disposable.json)). Its credential and location grants are not deployed. Migration 544 now adds signed exact-location views for deterministic summary reads; other non-synthesis workers still need source-boundary review. MAN-CAP-038 remains open for authenticated runtime identities, broader database least privilege, populated parity, and owner acceptance. Standalone `--list` and `--verify` now require exact `--location-id` and read through migration 547 signed `ai_summary/read` views; the all-location inventory mode is removed. Native and ARM64/QEMU disposable PostgreSQL 16 apply/replay pass 34 grouped checks for forced-RLS scope, no-context and foreign-location denial, bounded previews, digest inspection, raw-table denial, and stale-grant cleanup. The focused worker/CLI/profile selection passes 62 tests. Production credentials/grants, human operator authentication, populated parity, other non-synthesis agent reads, and MAN-CAP-038 acceptance remain open. Organic-readiness synthesis is now registered with the signed worker; migration 549 exposes exact-location projections and seven provenance views, with 210 focused tests and eight disposable PostgreSQL 16 checks passing. Migrations 549–550 are now deployed locally after an encrypted checkpoint and restore rehearsal; candidate and restore ledgers match at 541 schema entries through 550 with zero pending. The app alone was rebuilt and is healthy (`/health` 200); this local profile has OIDC disabled, so the report-review route returns 404. The legacy stack was untouched. Real worker credentials, populated output parity, and MAN-CAP-038 acceptance remain open ([rollout](builds/2026-10-22-recovery/candidate-migrations-549-550-rollout.json); [native replay](builds/2026-10-22-recovery/cap-038-ecological-modeling-source-native-replay.json); [ARM64 replay](builds/2026-10-22-recovery/cap-038-ecological-modeling-source-arm64-replay.json)). The AI-summary registry and generator query helpers now close cursors on success and failure; eight failure-injection checks pass within a 45-test scoped selection, with Ruff, compilation, current runtime SQL inventory, and matrix validation. Five stale assertions were updated to reflect the existing signed-reader search path and worker dispatch; no database/provider was accessed and no migration was needed ([evidence](builds/2026-10-22-recovery/ai-summary-cursor-cleanup.json)). Migration 583 also isolates Ecological Modeling to fourteen calculation projections and thirteen provenance views under a task-specific signed login/reader; worker dispatch, DSN/credential mapping, restore prerequisites, and an optional profile use that identity while draft writes remain separate. The focused worker/database/profile selection passes 98 tests; migration integrity passes 36. Network-disabled disposable PostgreSQL 16 applies/replays through migration 583 with 48 grouped checks on native AMD64 and ARM64/QEMU, using synthetic own/foreign location sentinels through the real signed scope function because the focused chain omits historical farm/ecology schema setup. QEMU is software portability evidence only. Candidate and legacy remain untouched, and migration 583 plus real credentials/grants are not deployed ([migration](schemas/postgres/583_isolated_ecological_modeling_worker.sql); [native evidence](builds/2026-10-23-recovery/cap-038-ecological-modeling-identity-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-ecological-modeling-identity-arm64-disposable.json)). Migration 590 now gives Financial Resilience synthesis a distinct signed source identity: three exact-location projections and one explicit network-wide Green Paper status projection, with shared-reader access revoked and native plus ARM64/QEMU disposable replay passing 69 grouped assertions. The capability remains prepared; this implementation evidence does not close MAN-CAP-038. Migration 591 now gives Bio Factory synthesis a distinct signed source identity: four exact-location projections and one explicit network-wide regional input catalogue, with shared-reader access revoked and native plus ARM64/QEMU disposable replay passing 72 grouped assertions. The capability remains prepared; this implementation evidence does not close MAN-CAP-038. Operator-created deterministic drafts now expose their authenticated operator UUID and matching opaque request UUID through migration 597 and the exact-location review wrapper; this does not attribute background agent runs or close MAN-CAP-038. Migration 628 now mints an immutable exact-location operator/task/summary receipt through an OIDC-only Gateway route and requires registered workers to verify it before lookup, source reads, and draft persistence; the write trigger also enforces the receipt. Review attribution returns operator/task/request identifiers only. `worker_cli` accepts either read-only mode or `--persist-draft` with a matching Gateway request ID, while Compose worker profiles remain read-only. The route authorizes but does not dispatch work; no synthesis console form, live OIDC, production grants, populated parity, or MAN-CAP-038 acceptance is claimed. CIDS signed export now carries a separate validated `source_scope.property_source_records` sidecar mapping each node property to sampled signed projection-row IDs (up to 50 per property) with count and truncation metadata; IDs remain outside JSON-LD. A canonical SHA-256 digest binds the JSON-LD document and sidecar; it is an integrity identifier, not a signature or source snapshot. The optional public-schema lineage helper also maps public relation and stable natural keys while the legacy CLI output stays unchanged. The 110-test CIDS/task/worker selection passes; the validator cross-checks graph count, alignment tier, and version, and enforces the shared v3.2.0 Essential profile even when unsupported values agree across the output ([artifact digest evidence](builds/2026-10-25-recovery/cap-038-cids-artifact-digest.json); [public lineage evidence](builds/2026-10-25-recovery/cap-038-cids-public-source-lineage.json); [envelope evidence](builds/2026-10-25-recovery/cap-038-cids-envelope-consistency.json); [profile evidence](builds/2026-10-25-recovery/cap-038-cids-profile-contract.json)). Full source snapshots, populated parity, runtime grants, and MAN-CAP-038 owner acceptance remain open.|
| CAP-039 | Unified meta-CLI | services/cli.py; services/common/cli.py; services/common/db.py; services/ingestion/cli.py; services/forecast/cli.py; services/analytics/cli_governance_proposals.py; services/analytics/cli_governance_roles.py; services/analytics/cli_governance_links.py; services/analytics/cli_governance_tactical.py; services/analytics/cli_governance_tensions.py; services/analytics/cli.py; services/crisp/cli.py; services/delphi/cli.py; services/threatcasting/cli.py; services/export/report_generator.py; services/export/dataset_refresh.py; services/migration/cli.py; services/mobile/tenant_preflight.py; services/mobile/media_cleanup.py; services/mobile/media_reconcile.py; services/gateway/operator_cli.py; docs/refactor/kernel-operations-console.md; docs/refactor/unified-cli-kernel-contract.md; docs/refactor/operator-cli-boundary-inventory.md ; services/ingestion/mock_sensors.py; services/ingestion/baal_indexer.py; services/ingestion/gnosis_indexer.py; services/ingestion/gnosis_worker.py; services/migration/runtime_role.py; services/ingestion/price_attestation.py; services/ingestion/http_sensor_receiver.py; services/ingestion/mqtt_subscriber.py; services/ingestion/sensor_ingester.py; services/ingestion/status.py; services/ingestion/gis_import.py| MAN-CAP-039: Every existing service group help and argument-forwarding path remains callable | tests/test_dataset_refresh_readonly.py; tests/test_cli.py; tests/test_common_cli_lazy_database.py; tests/test_unified_cli_success_contract.py; tests/test_operator_cli_revocation_audit.py; tests/test_operator_cli_identity_provision.py; tests/test_operator_cli_identity_lifecycle.py; scripts/check-operator-identity-disable-audit-disposable.py ; tests/test_mock_sensors_cleanup.py; tests/test_mock_sensors_cli.py; tests/test_ingestion_cli_dispatch.py; tests/test_baal_indexer_cli.py; tests/test_gnosis_worker.py; tests/test_ingestion_cli_help_isolation.py; tests/test_price_attestation_cli.py; tests/test_http_sensor_receiver_cli.py; tests/test_mqtt_subscriber_cli.py; tests/test_sensor_ingester_csv_audit_scope.py; tests/test_sensor_ingester_error_redaction.py; tests/test_sensor_ingester_transaction_audit_scope.py; tests/test_ingestion_status_error_redaction.py; tests/test_ingestion_cli_dispatch.py; tests/test_gis_import.py; tests/test_gis_import_audit_scope.py; tests/test_geospatial_import_error_redaction.py| D — deployed command tree; root/wrapper help and synthetic forwarding cover every mounted group, and actual argparse help and invalid non-help argument rejection pass across all 37 groups with SOPS unavailable. Ingestion no longer returns success for an unknown top-level option. Offline successful standalone/unified output parity passes for nine invocations across eight groups: agent catalogue, ingestion catalogue, form validation and preview, missing-file audit-spool status, systems module listing, the local attestation schema catalogue, migration source validation, and operator farm-activity role templates. Thirty-one read-only database-backed or aggregate-service-stubbed invocations compare standalone and unified parsing, filters, and JSON output with synthetic results. A separate fake-connection operator `revoke-grant` case verifies required actor/reason forwarding and the persisted audit fields; it does not establish database authorization. A fake-connection `identity provision` parity case confirms active refresh preserves enabled state, and focused checks reject attempts to reactivate disabled identities; no reactivation command exists. These checks do not establish database authorization. A fake-connection identity-disable case confirms standalone/unified output, identity/session/audit ordering, and managed transaction use; injected session-revocation failure, audit-insert failure, or missing audit receipt rolls back the operation. Migration 525 persists a bounded caller-supplied actor label/reason and PostgreSQL login principal in a private append-only ledger; focused mocks and disposable PostgreSQL checks cover input validation, role ACLs, principal capture, and update/delete/truncate rejection. This does not authenticate the actor or establish local principal separation. A fake-connection `operator list` parity case returns synthetic identity, grant, membership, share, and transfer rows, closes its connection, and does not select sessions; the global unfiltered data remains DBA-only and its privacy boundary is open.  The governance proposal, circle, link, tactical, and tension read CLIs close owned connections after success and failure; grievance health, identity-resolution queue, representation summary, trust timeline, metric, forecast, analytics, CRISP, and Delphi reads verify success-path cleanup; forecast, CRISP, Delphi, and Threatcasting close resources on query failure. The cleanup dry-run avoids provider setup; reconciliation uses stubbed database and object inventory and performs no deletion. Native command trees and leaf parameter contracts match for standalone/unified kernel, dao, and treasury groups (global completion toggles are intentionally disabled in the unified root). Export snapshot verification, synthetic single-report generation, and automatic batch generation output match across standalone and unified entry points. Synthetic coverage verifies read-only calculation, subsequent draft-snapshot persistence, batch run/item success transitions, exact location scope, and connection cleanup; neither database is contacted. A synthetic per-report failure also confirms sanitized error persistence, continuation, and the final partial run status. Connection creation, list/verify queries, connection-close failures, and auto-run setup expose only exception-class summaries; cleanup is asserted whenever possible. Every mounted group now has at least one successful parity path. The documented DAO `framework list` path now works through standalone and unified invocations, preserves the old no-argument form, and has synthetic output/cleanup coverage; live database and authorization behavior remain unverified ([tests](../tests/test_governance_framework_cli.py); [evidence](builds/2026-10-20-recovery/cap-039-governance-framework-list-cli.json)). Operator identity administration and global-list privilege/privacy boundaries (identity-disable audit persistence is implemented, while actor authentication remains open), grant provisioning, membership/share/transfer authorization, real database/provider behavior, and privileged operator-action boundaries remain unassessed ([contract](unified-cli-kernel-contract.md); [success evidence](builds/2026-10-20-recovery/cap-039-offline-success-parity.json); [help evidence](builds/2026-10-19-recovery/cap-039-unified-cli-source.json); [argument evidence](builds/2026-10-19-recovery/cap-039-invalid-argument-preflight.json)). [Readiness](portability-database.md)  Mock sensor setup marks demo devices; generation and cleanup are restricted to those devices, preventing mock operations from touching live sensors or unrelated alerts. Cleanup preserves registry rows, rolls back on failure, and closes the connection ([scope evidence](builds/2026-10-21-recovery/mock-sensor-demo-scope.json)). The ingestion dispatcher requires callable module `main()` entry points and has no `runpy` execution fallback; missing entrypoints fail closed with process arguments restored, and all 19 mounted modules pass standalone/unified credential-free help checks ([dispatch evidence](builds/2026-10-21-recovery/cap-039-ingestion-dispatch-no-runpy.json)). Baal block inputs reject negative and reversed ranges before provider/database access, and an explicit block-zero endpoint is preserved ([Baal CLI evidence](builds/2026-10-21-recovery/cap-039-baal-indexer-cli-contract.json)). Dataset-refresh CLI selector conflicts now fail before feature/database access, and inventory cursor/connection cleanup is covered on failures; saved-SQL refresh remains disabled by default. Query-ID policy, location/tenant scope, and retained populated dashboard parity remain open. The initial saved-dataset lookup cursor also closes on execute and row-fetch failures before the reporting reader runs. Inventory-discovery failures in list and bulk modes also use sanitized exception-class output and close the connection.|
| CAP-040 | dMRV architecture | services/ingestion/; services/ingestion/sensor_anomaly_scan_worker.py; services/ingestion/sensor_anomaly_worker.py; services/ingestion/ml_anomaly_detector.py; schemas/postgres/649_signed_sensor_anomaly_replay_inventory.sql; services/ingestion/sensor_anomaly_ml_worker.py; services/ingestion/sensor_anomaly_ml_cli.py; schemas/postgres/650_signed_sensor_anomaly_ml_source.sql; docker-compose.kernel-sensor-anomaly-ml.yml; docker-compose.kernel-arm64-sensor-anomaly-ml.yml; requirements/ml-anomaly.txt; requirements/ml-anomaly-runtime.in; requirements/ml-anomaly-runtime.lock; scripts/compile-ml-anomaly-runtime-lock.sh | MAN-CAP-040: Satellite, HTTP/MQTT, anomaly and proof preparation retain quality and review gates | tests/test_remote_sensing_automation.py; tests/test_iot_sensor_push.py; tests/test_ml_anomaly.py; tests/test_ml_anomaly_scope.py; tests/test_market_data_recovery.py; tests/test_climate_worker.py; tests/test_market_data_worker.py; tests/test_weather_legacy_atomicity.py; tests/test_weather_forecast_atomicity.py; tests/test_sensor_driver_schedule.py; tests/test_remote_sensing_worker.py; tests/test_remote_sensing_provider_records.py; tests/test_runtime_role_boundary.py; tests/test_mqtt_delivery.py; scripts/check-mqtt-delivery-disposable.py; tests/test_sensor_anomaly_scan_worker.py; scripts/check-sensor-anomaly-worker-delivery-disposable.py; tests/test_sensor_anomaly_ml_worker.py; tests/test_anomaly_detector_cli_scope.py; tests/test_runtime_role_boundary.py; tests/test_kernel_profile.py; scripts/check-sensor-anomaly-ml-source-disposable.py; docs/refactor/builds/2026-10-26-recovery/sensor-anomaly-ml-source-disposable.json; docs/refactor/builds/2026-10-26-recovery/sensor-anomaly-ml-image-native-smoke.json; scripts/sensor_anomaly_ml_resource_smoke.py; docs/refactor/builds/2026-10-26-recovery/sensor-anomaly-ml-slim-image-resource-smoke.json | P — normal single-reading and CSV source paths exercised; authenticated HTTP single/batch tested through in-process ASGI and over TCP between containers on the private fixture network. The five CSV/ASGI rows created five platform events and succeeded outbox deliveries; raw ClickHouse and v3 location/day/type aggregates match. A later listener run accepted three readings, rejected invalid HMAC (401) and URL/payload mismatch (400), and detected duplicate timestamp; at listener capture three events/outbox rows were pending. A follow-up delivered those three rows once each with exact sink parity; their platform events remain pending and have no handler receipts. One selected anomaly handler produced a warning; durable-receipt acknowledgement recovery skipped duplicate execution, with three earlier failed attempts retained. First read was immediate in one run, but prior five-second visibility delay remains unexplained. Local legacy sensor lineage is reconciled (15 PostgreSQL sources, zero outbox rows, zero retained ClickHouse raw rows); remote/populated-target ownership remains unassessed. A bounded Caddy localhost TLS smoke passed (200 health, 308 redirect, security headers, unknown route 401, certificate reuse, no proxy host bindings). A follow-up host-published check confirmed loopback-only bindings, a redirect to configured port 8448, and a verified TLS health response of 200. A custom-port check confirmed the 18448 override also aligned the binding and redirect, with verified TLS health 200. Direct gateway preflight allowed `http://localhost:3000` for GET/x-api-key (200) and rejected `https://untrusted.invalid` (400, no allow-origin). A follow-up auth-denial response returned 401 for both origins, adding allow-origin only for the configured origin; two exact denied audit records were retained. A network-isolated ASGI source harness first checked injected limiter behavior [with evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json). A rebuilt local-provider canary then allowed 127 health GETs in 2.766 seconds before 429/`Retry-After: 1`, decorated throttling with the configured CORS origin, passed OPTIONS after exhaustion, and returned 429 on the next GET. Exact durable audit contained 127 allowed and two `rate_limited` denials. The image is promoted to the healthy active candidate app; a rollback snapshot is retained [with runtime evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json). The promoted image's isolated local contract admitted exactly five of 100 concurrent checks, verified oldest-caller eviction and fresh-instance reset [with evidence](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json). The active candidate app restart reset the same synthetic identity to allowed 200; PostgreSQL stayed healthy and exact audit counts were retained [with evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json). Minimal/edge profiles use the process-local limiter; standard now defaults to the PostgreSQL shared limiter after migration 373. Direct, ASGI multi-process, and two-container HTTP evidence covers shared consumption; production multi-host failover and public ingress remain unaccepted. See [profile policy](rate-limit-boundary.md). Non-loopback/public ingress, mobile/upload parity, browser/runtime authenticated/credentialed CORS (successful cookie-authenticated source response is covered), shared/multi-replica rate limits, multi-hop trusted-proxy policy, broader handler/concurrency and full transport acceptance remain open. [Proxy evidence](kernel-proxy.md), [runtime result](builds/2026-10-10-recovery/kernel-proxy-runtime.json), [forwarding audit](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json), [loopback ingress](builds/2026-10-10-recovery/proxy-loopback-ingress.json), [custom port](builds/2026-10-10-recovery/proxy-custom-port.json), [CORS preflight](builds/2026-10-10-recovery/proxy-cors-preflight.json), [auth-denial CORS](builds/2026-10-10-recovery/proxy-cors-auth-response.json). [Sensor evidence](sensor-entrypoint-recovery.md), [local lineage](builds/2026-10-10-recovery/legacy-sensor-lineage.json), [listener evidence](builds/2026-10-10-recovery/sensor-http-listener.json), [listener outbox delivery](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json), [handler evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json), [HTTP contract](http-sensor-transactions.md), [visibility evidence](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json), [CSV/HTTP evidence](builds/2026-10-10-recovery/sensor-csv-http.json); [HTTP optional profile](http-sensor-overlay.md); [MQTT optional profile](mqtt-overlay.md); original persisted broker backlog inventory empty: [Recovery](analytics-broker-recovery.md); source-level freshness-query checks now report unknown configured sources as errors rather than `no_data`; 29 tests pass ([evidence](builds/2026-10-14-recovery/freshness-query-contract-check.json)).; the `--worldclim` compatibility path now stores explicit `latitude_proxy_v1` estimates in schema-aligned fields, commits the upsert, and supplies location-level fallback to plot consumers; 51 climate/migration tests pass, but PostgreSQL migration execution remains unverified ([evidence](builds/2026-10-14-recovery/climate-worldclim-schema-alignment.json)). Scheduled sensor pull now requires a registered enabled driver instance bound to one explicit location; source-level transaction/idempotency and opt-in driver checks pass 162 focused tests, while configured source, runtime identity, and MAN-CAP-040 acceptance remain open ([evidence](builds/2026-10-16-recovery/sensor-driver-scheduled-source-contract.json)). The five-day forecast now also has a separate disabled native JobSpec requiring one location UUID and rejecting aggregate mode; the scheduler/worker inventory tests pass 154 checks, and forecast scope/rollback/outbox tests pass 43. No schedule, key, database, or provider was activated. Signed tenant context, credentials, live provider parity, and MAN-CAP-040 remain open ([evidence](builds/2026-10-16-recovery/weather-forecast-scheduled-job-contract.json)). The scheduled climate JobSpec now routes through the default-off signed `climate_worker`; migration 429 bounds five source-specific summary/audit writes. Its 154 focused worker/climate/scheduler tests pass, and a disposable forced-RLS PostGIS run passes nine scope, source, retry, audit, and privilege checks. No GEE key/provider, schedule, candidate or legacy database was used; migration 429 is applied on the candidate and worker credentials/grants remain unprovisioned ([worker](../../services/ingestion/climate_worker.py); [migration](../../schemas/postgres/429_signed_climate_worker.sql); [evidence](builds/2026-10-17-recovery/climate-worker-disposable.json)). The new native World Bank JobSpec routes to a default-off isolated worker; migration 430 adds a dedicated bounded price/audit function. The 199 focused worker/market/scheduler tests, Ruff, compilation, inventories, and six forced-RLS PostgreSQL 16 checks pass. Migrations 404–432 are applied on the local candidate after checkpoint/restore rehearsal; no provider/schedule was accessed, and MAN-CAP-040 remains open ([evidence](builds/2026-10-17-recovery/market-data-worker-disposable.json)). Scheduled sensor pulls now import only the source-controlled `sensor_csv` target after registry identity comparison; 174 focused scheduler/CLI/contract/worker-map tests pass. Native remote sensing now routes through a default-off signed worker; 238 focused checks and forced-RLS PostgreSQL 16/PostGIS migration-432 replay acceptance pass, including atomic fallback/persistence, duplicate suppression, and direct-table denial. The feature remains off; candidate schema is through migration 432, and worker credentials/grants remain unprovisioned; live provider parity, file-input acceptance, and MAN-CAP-040/047 remain open. Typed, read-only SDK accessors now expose stored weather, soil, remote-sensing, and MRV claim records by location; they do not run ingestion, verification, or attestation, and client filters are not authorization controls ([evidence](builds/2026-10-18-recovery/sdk-ecology-read-methods.json)). MQTT QoS 1 receipt/replay has 11 mocked cases within 59 focused tests and disposable PostgreSQL 16/Mosquitto acceptance. Twelve SQL assertions cover terminal outcomes, bounded dead-lettering, replay/disposal, concurrency, source/receipt crash recovery, lock timeout, payload constraints, CLI output, and redaction. The real Paho subscriber was killed after a retryable receipt and before ACK; Mosquitto redelivered with `DUP=1` to the replacement process, which accepted attempt two, wrote one synthetic source effect, ACKed, and saw no further delivery after reconnect. Containers were no-volume and loopback-only; candidate/legacy and providers were untouched. Real sensor/outbox parity, replay after device-authorization changes, production TLS/ACL/HMAC, broker restart, and live provider acceptance remain open ([recovery](mqtt-recovery.md); [broker evidence](builds/2026-10-19-recovery/mqtt-delivery-postgresql-mosquitto.json); [state-machine evidence](builds/2026-10-19-recovery/mqtt-delivery-state-machine.json)). Scheduled Kernel anomaly replay now has a default-off signed inventory path (migration 649): one canonical event per reading, 24-hour window, 100-event cap, same idempotent handler, and legacy fallback. Focused tests and disposable PostgreSQL 16 forced-RLS acceptance pass; no candidate/provider/credential was used. CAP-040 remains partial pending worker-secret/grant rollout, populated parity, external delivery, and MAN-CAP-040/047 acceptance. Manual ML checks/training also now have a default-off signed exact-location source view and separate read-only worker, verified on disposable PostgreSQL 16 with migration 650. Candidate rollout, real worker grant/credential, populated output parity, and physical ARM64 acceptance remain open. |
**CAP-040 MQTT durable delivery and broker recovery — 19 October 2026:** eleven mocked state-machine checks pass within a 59-test MQTT/IoT group. Disposable PostgreSQL 16 applied migration 372 and passed twelve SQL assertions for receipt persistence, bounded retries, replay/disposal audit, concurrency, source/receipt crash recovery, lock timeout, payload limits, and redaction. A real Paho subscriber then crashed after a retryable receipt committed and before ACK; disposable Mosquitto redelivered with `DUP=1` to a replacement using the same persistent client ID, which accepted attempt two, committed one synthetic source effect, and ACKed. A follow-up connection received no redelivery. Both containers were no-volume and loopback-only, then removed; candidate, legacy, production broker, and providers were untouched. Anonymous plaintext was used only in this isolated broker test; TLS, ACL, device HMAC, actual sensor/outbox parity, broker restart, replay after device-authorization changes, and live provider acceptance remain open. CAP-040 stays prepared, not accepted. Checklist: 683 complete / 24 open; classifications unchanged ([unit tests](../tests/test_mqtt_delivery.py); [disposable checker](../scripts/check-mqtt-delivery-disposable.py); [recovery contract](mqtt-recovery.md); [source evidence](builds/2026-10-19-recovery/mqtt-delivery-state-machine.json); [PostgreSQL/Mosquitto evidence](builds/2026-10-19-recovery/mqtt-delivery-postgresql-mosquitto.json)).


| CAP-041 | Digital soil mapping | services/analytics/ | MAN-CAP-041: SOC features and geographic cross-validation match model fixture | tests/test_dsm_soc_prediction.py | B — baseline code retained; Kernel capability path and model parity remain unassessed. The SDK offers location-filtered reads for stored soil samples and soil-carbon measurements only. A source audit found the legacy extractor omitted plot coordinates even though residual kriging and spatial-block CV require them; it now returns the configured plot center or a point-on-surface fallback from the plot boundary, preserving the location predicate. The focused extractor, deterministic-fold, and spatial-block CV regressions pass within 22 DSM tests (95 across the DSM/geostatistics/spectral selection), and disposable PostgreSQL 16/PostGIS on minimal synthetic relations verifies both geometry paths and location filtering. Geographic field folds now use seeded, deterministic sample-count balancing; regressions prove repeatability, field exclusivity, and equal-fixture balance. The spatial-block test uses the mean-baseline fallback; no XGBoost model is trained and fixture parity remains unvalidated ([existing SDK reads](builds/2026-10-18-recovery/sdk-ecology-read-methods.json); [coordinate regression](builds/2026-10-19-recovery/cap-041-spatial-training-coordinates.json); [fold regression](builds/2026-10-19-recovery/cap-041-geographic-fold-repeatability.json)). |
| CAP-042 | Guild protocol | contracts/; services/guilds/ | MAN-CAP-042: Registry, domains, tasks, evidence and governance projections preserve chain identities | tests/test_guild_services.py; tests/test_guild_registry_projection.py; tests/test_kgp_worker_durability.py; scripts/check-kgp-worker-reconnect-disposable.py | B — baseline code retained; the current-source disposable check replays all 452 ordered schemas and projects ten synthetic registry/domain/task/governance events, including Guild Registry metadata, steward, and status. Repeated log replay is idempotent; a ten-event simulated reorg clears chain-owned registry metadata while preserving the canonical guild row and stable key, then rebuilds from replacement-branch logs. Worker database restart and lease reclaim also pass. Guild-owned values live under the reserved `metadata._kgp_registry` subobject so a reorg does not overwrite canonical name/status/steward fields. Earlier rollout evidence records migration 403 applied to the candidate after checkpoint/restore rehearsal; this check changed neither candidate nor legacy. Candidate app rebuild and populated projection parity remain open. The disposable stack is no-volume and loopback-published; no chain/provider call occurred. Other event types, live-chain behavior, and overall capability parity remain unassessed. [Migration](../schemas/postgres/403_kgp_governance_target_policy_projection.sql); [current disposable evidence](builds/2026-10-19-recovery/cap-042-guild-registry-projection-reorg.json); [prior worker evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json); [candidate rollout evidence](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json) |
| CAP-043 | Credit Token | contracts/; services/credit_class/ | MAN-CAP-043: ERC-20/proxy integration preserves roles, supply, pause and custody | tests/test_credit_balance.py; contracts/test/KokonutCreditToken.t.sol | B — baseline code retained; a source audit found repeat issuance reused serial zero because the counter was read from the per-token issued-amount map and never advanced. An appended UUPS-safe batch/vintage serial counter now allocates repeat issuance distinct token IDs, skips an existing legacy serial-zero record when the new counter is empty, and rejects the zero batch sentinel. The proxy Foundry suite passes 17 tests and a 1,000-run fuzz check; all 67 contract tests pass. Existing storage slots 0–4 are unchanged and the new mapping is appended at slot 5. This fixes issuance identity only; database-ledger parity, deployed proxy compatibility, role custody, pause/retirement policy, and MAN-CAP-043 acceptance remain open ([evidence](builds/2026-10-19-recovery/cap-043-credit-serial-identity.json)). |
| CAP-044 | Price Oracle | contracts/src/KokonutPriceOracle.sol; services/ingestion/ | MAN-CAP-044: Price-feed consensus and updater permissions preserve baseline | contracts/test/KokonutPriceOracle.t.sol; tests/test_oracle_infrastructure.py | B — source repair adds explicit `isFresh`/`getFreshPrice` reads and lets authorized updates replace expired feeds; 13 oracle tests and the complete 73-test Foundry suite pass, including 256 freshness fuzz cases. Existing `getPrice` remains raw for compatibility. Kernel/service consumption, source-timestamp policy, feed consensus, and parity remain unassessed; CAP-044 is not accepted ([evidence](builds/2026-10-19-recovery/cap-044-oracle-freshness.json)). |
| CAP-045 | Selective Disclosure | contracts/src/KokonutSelectiveDisclosure.sol | MAN-CAP-045: Selective disclosure proof verifies while private claims remain hidden | contracts/test/KokonutSelectiveDisclosure.t.sol; tests/test_attestation.py | B — verifier now returns `false` for proof/flag length mismatches and flags outside the supported `0`/`1` direction encoding, preventing calldata panics and arbitrary nonzero direction handling while preserving the boolean API. Ten focused tests pass, including 256 fuzz cases for unsupported flags; the complete 77-test Foundry suite passes. The contract stores only attestation roots and does not receive disclosed claims, but leaf construction and consumer parity remain unassessed; CAP-045 is not accepted ([evidence](builds/2026-10-19-recovery/cap-045-proof-shape.json)). |
| CAP-046 | KokonutResolver | contracts/src/KokonutResolver.sol; services/attestation/ | MAN-CAP-046: Resolver permits approved attesters only with existing schemas and owner | contracts/test/KokonutResolver.t.sol; tests/test_attestation.py | B — constructor now rejects zero-address initial attesters, matching `addAttester`; synthetic EAS-caller tests confirm only the configured EAS address can call resolver callbacks and that current allowlist state gates both attest and revoke. Twelve focused tests pass, including 256 add/remove fuzz cases; the complete 81-test Foundry suite passes. Real EAS/schema integration, deployment state, revocation policy for removed attesters, and MAN-CAP-046 parity remain unassessed ([evidence](builds/2026-10-19-recovery/cap-046-resolver-gates.json)). |
| CAP-047 | Platform integrity | services/migration/; services/gateway/; services/events/; services/scheduler/ | MAN-CAP-047: Migration drift rejection, default-protected routes and lease/retry recovery hold | tests/test_migration.py; tests/test_gateway_auth.py; tests/test_scheduler_durability.py; tests/test_event_bus_durability.py; tests/test_eas_indexer_recovery.py; tests/test_climate_worker.py; tests/test_market_data_worker.py; tests/test_sensor_driver_schedule.py; tests/test_remote_sensing_worker.py; tests/test_remote_sensing_provider_records.py; tests/test_runtime_role_boundary.py; tests/test_data_freshness_notification_outbox.py; tests/test_smtp_transport.py; tests/test_compose_metabase_profile.py| D — Read-only candidate status on 20 October listed schema migrations 510–525 as pending; this batch did not migrate candidate or legacy. Earlier candidate rollout records document encrypted checkpoint/restore rehearsals through migrations 435 ([404–432 rollout](builds/2026-10-17-recovery/candidate-migrations-404-432-rollout.json); [433 rollout](builds/2026-10-17-recovery/candidate-migration-433-rollout.json); [434 rollout](builds/2026-10-18-recovery/candidate-migration-434-rollout.json); [435 rollout](builds/2026-10-18-recovery/candidate-migration-435-rollout.json)). Five owner-approved reference seeds were applied separately; pilot seed files remain held. Fresh network-disabled, seed-free PostgreSQL 16 schema replays apply all 539 repository schemas through migration 548 on native AMD64 and ARM64/QEMU, with zero pending or failed migrations. Migration 541 removes `PUBLIC SELECT` from the two `pg_stat_statements` relations, keeping global query telemetry out of the signed source-reader boundary ([native replay](builds/2026-10-22-recovery/native-current-schema-548.json); [ARM64/QEMU replay](builds/2026-10-22-recovery/arm64-qemu-current-schema-548.json)). A clean linux/arm64 QEMU replay also applied all 423 current schemas through 432 with zero pending; the ARM64 app passed its in-container health check and returned HTTP 200 for `/health` plus HTTP 401 `credentials_required` for an anonymous farm-activity read. Host loopback ingress now passes for the ARM64 app on a normal bridge: host health returned 200 and the protected route returned 401; native AMD64 PostgreSQL was used for that ingress-focused replay ([ingress evidence](builds/2026-10-17-recovery/arm64-loopback-ingress.json); [ARM64 schema evidence](builds/2026-10-17-recovery/arm64-qemu-current-schema-432.json)). Application-table RLS is off and the runtime still uses the database owner credential; worker features remain disabled and no worker database logins/grants or location grants are provisioned; the notification-enqueue secret is staged separately in encrypted `.env.sops`. Drift/auth/retry/recovery and named MAN-CAP acceptance remain pending. [Runtime](portability-runtime.md); scoped empty-workload PostgreSQL restore completed; populated restore exercised; optional consumer role boundaries and Directus startup verified: [Recovery](recovery-preparation.md), [roles](optional-database-roles.md); all attached legacy storage encrypted and retained: [Preservation](legacy-storage-preservation.md); legacy Redis/PG clones retained: [Inventory](provider-clone-inventory.md); four DB logical restores and 13 table fingerprints match: [Restore](legacy-logical-restore.md); synthetic paired restore, scheduler stale-owner/window and event lease/retry/replay/disposal checks passed; selected sensor anomaly handler/receipt recovery passed; same-event timeout/lease takeover and crash-after-effect retry passed for one idempotent CRISP cache handler, with other handlers and broader platform integrity acceptance open: [Fixture](recovery-fixture-setup.md), [sensor evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json), [crash/retry evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json); source-level scheduler ownership/cutover inventory published; live provider and activation state remain unverified [inventory](schedule-ownership-inventory.md). Candidate scheduler status returned zero tasks in the earlier read-only snapshot [evidence](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json); external Prefect state remains unknown. The refreshed JobSpec contract now also requires an explicit location for scheduled weather, matching climate; 86 focused scheduler/dispatch/inventory checks pass. Persisted tasks were not re-read, and no MAN-CAP acceptance is implied ([evidence](builds/2026-10-15-recovery/worker-weather-location-contract.json)).  The two global notification handlers now also have a default-off isolated enqueue path through migration 417; seven network-disabled PostgreSQL 16 checks and the 136-test focused source suite pass. Migrations 417–419 were already present in the candidate pre-433 baseline; the encrypted notification-enqueue DSN/password is staged, but its login/grants remain unprovisioned and the feature is off; no MAN-CAP acceptance is implied ([disposable evidence](builds/2026-10-16-recovery/notification-enqueue-worker-disposable.json)). The scheduler source catalog now validates sensor location/driver-instance inputs and the registry enforces their exact location match; this does not deploy a schedule, establish worker tenant context/RLS, or accept MAN-CAP-047 ([evidence](builds/2026-10-16-recovery/sensor-driver-scheduled-source-contract.json)). Migration 429 also has source and disposable forced-RLS acceptance for the default-off signed climate worker; migration 429 is applied on the candidate, worker credentials/grants are unprovisioned, and no live provider or schedule was exercised ([evidence](builds/2026-10-17-recovery/climate-worker-disposable.json)). Migration 430 also passes disposable forced-RLS replay, bounded-write, direct-access, idempotency, and rollback checks and is applied on the candidate; end-to-end MAN-CAP-047 acceptance remains open ([evidence](builds/2026-10-17-recovery/market-data-worker-disposable.json)). Scheduled sensor imports now reject database-selected module/class/type values before import; this is source-only and does not supply the missing isolated sensor worker identity or signed database functions. A fresh 18 October ARM64/QEMU run replayed all 425 ordered schemas through migration 434 after the clean-bootstrap role prerequisite, then verified ARM64 app/PostGIS architecture, health 200, anonymous protected-route 401, internal network, resource limits, and cleanup. This remains emulation evidence and does not accept MAN-CAP-047 ([evidence](builds/2026-10-18-recovery/arm64-qemu-current-schema-434.json)). A 20 October current-source ARM64 Gateway also ran against a native AMD64 PostgreSQL database with all 515 schemas through migration 524: health returned 200 and an anonymous protected write returned 401. It does not advance ARM64 database replay beyond migration 434 or certify hardware ([integration evidence](builds/2026-10-20-recovery/arm64-gateway-schema-524-runtime.json)). The network-disabled schema-bootstrap profile also passed an isolated runtime smoke with no host ports or project network; two focused Compose contract tests validate its default and ARM64 image override. The smoke ran no migrations and does not change MAN-CAP status ([tests](../../tests/test_schema_bootstrap_profile.py); [evidence](builds/2026-10-20-recovery/schema-bootstrap-networkless-smoke.json)). The 20 October QEMU replay attempt reached migration 068 before interruption; a fresh 21 October network-disabled ARM64/PostGIS replay then applied all 529 current schemas through migration 538 with zero failures, and its scratch resources were removed ([ARM64 replay](builds/2026-10-21-recovery/arm64-qemu-current-schema-538.json)). The latest successful network-disabled ARM64/QEMU replay applies all 588 current schema files through migration 597 with zero failures; temporary resources were removed and no seeds or farm data were used ([ARM64 replay](builds/2026-10-23-recovery/arm64-qemu-current-schema-597-after-bootstrap-retry.json)). A later replay through migration 598 stopped at migration 454 after 444 schema applications; focused migration 454 PostgreSQL 16 acceptance passes, but full replay remains unverified ([attempt](builds/2026-10-23-recovery/arm64-qemu-current-schema-598.json)). A fresh disposable PostgreSQL 16 outage acceptance now runs the event dispatcher and notification sender as separate long-lived processes; both survive a database stop/start, and notification retry plus crash/lease reclaim preserve idempotency. The focused schema fixture replays migrations 116, 165, and 375 and adds the migration-406 notification location column only; no external provider is called ([worker recovery](builds/2026-10-21-recovery/dedicated-event-notification-worker-reconnect.json)). This remains emulation evidence, not Raspberry Pi hardware acceptance; The SMTP path now shares an explicit TLS adapter across outbox, anomaly CLI, and health-check email; 38 focused SMTP/health-check checks and all 19 Compose-profile tests pass; no provider was called. This closes transport implementation only, not live external delivery or on-call ownership ([SMTP evidence](builds/2026-10-23-recovery/smtp-tls-transport.json)). MAN-CAP-047 remains open. Sprint baseline (26 October 2026): the native disposable full schema replay applied all 642 files through 651 and cleaned up; separate minimal-schema runtime/auth-role and signed operator-context checks passed. The full-schema two-tenant probe and live identity remain open ([baseline](builds/2026-10-26-recovery/sprint-workflow-baseline.json); [replay](builds/2026-10-26-recovery/sprint-native-schema-replay.json); [roles](builds/2026-10-26-recovery/sprint-operator-session-role-disposable.json); [context](builds/2026-10-26-recovery/sprint-operator-tenant-context-disposable.json)). |
| CAP-048 | Strategic reserve | services/strategic_reserve/health.py | MAN-CAP-048: Adequacy/trigger/drawdown reports match; release proposals remain drafts | tests/test_strategic_reserve.py; tests/test_good_offense.py | B — corrected preempt advisory behavior: rising `gt`/`gte` metrics can use the documented zero-baseline fraction only for percentages in `(0, 1)`; falling `lt`/`lte` triggers now report `baseline_required` rather than generating a preempt point below the hard threshold. Invalid percentages and unsupported operators fail closed, while hard-trigger behavior remains unchanged. Twenty-two focused strategic-reserve/good-offense tests pass with Ruff and compilation. No release is executed; Kernel and populated parity remain unassessed ([evidence](builds/2026-10-19-recovery/cap-048-preempt-trigger-semantics.json)). |
| CAP-049 | Capital accounting | services/capital/credit.py; services/capital/ | MAN-CAP-049: Eight-capital accounting, deferred ledger, capacity and diversion preserve totals | tests/test_capital_accounting.py | B — draft-credit writes now reject non-finite/non-positive amounts; exact idempotency-key retries return the original credit, while reuse with a different immutable payload raises before it can be misreported as a duplicate. Twelve focused capital-accounting tests pass with Ruff and compilation. The SDK offers read-only location-filtered `value_flow_event` records, but verification, exclusion, and full flow-accounting parity remain unestablished; CAP-049 is not accepted ([credit evidence](builds/2026-10-19-recovery/cap-049-credit-idempotency.json); [SDK read evidence](builds/2026-10-18-recovery/sdk-market-capital-read-methods.json)). |
| CAP-050 | Tactical layer & simulation | services/simulation/resolution.py; services/systems/ | MAN-CAP-050: Tactical models and seeded Monte Carlo outputs match agreed tolerance | tests/test_simulation_resolution.py | B — Monte Carlo output is now stable in draw-index order under parallel execution; sampling, connection-factory, simulator, and non-finite metric failures are isolated per draw and returned in deterministic order. Fourteen focused tests pass with Ruff and compilation. Seeded output parity against the legacy model, agreed tolerance, and broader tactical-model parity remain unassessed; CAP-050 is not accepted ([evidence](builds/2026-10-19-recovery/cap-050-simulation-determinism.json)). |
| CAP-051 | Data governance | services/analytics/ | MAN-CAP-051: Consent, access history, retention and portability preserve audit/privacy | tests/test_data_governance.py; tests/test_consent_append_only.py | P — migration 401 and source implementation prepare nullable runtime policy windows, explicit policy approval, audited record-level holds, and hold-aware generic/event eligibility. New schedules remain drafts and auto-enforcement stays off unless approved; destructive enforcement also has an independent feature gate. Focused source checks and ordered disposable PostgreSQL migration/hold acceptance pass; migrations 401/402 are applied on the candidate after checkpoint/restore rehearsal; no jurisdiction period is configured. Bounded local CLI inventories now expose policy scope/approval state and active or released holds while omitting free-text reasons; local actor fields remain unauthenticated ([inventory checks](builds/2026-10-17-recovery/retention-inventory-cli.json)). Consent/disposition parity, policy ownership, and end-to-end disposition remain open. [Migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql); [database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json); [candidate rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json); [gate](builds/2026-10-15-recovery/data-retention-enforcement-gate.json) |
| CAP-052 | Platform upgrade system | scripts/upgrade.sh; scripts/rollback.sh | MAN-CAP-052: Isolated upgrade/rollback preserves authority, checksum and recovery history | tests/test_upgrade.py; tests/test_upgrade_integration.py | B — upgrade success/failure now updates the exact `platform_upgrade` row created for that run. Previously a failure inserted a separate `failed` row and left the partial unique `started` record active, blocking future upgrades; latest-row success updates could also target another run. First-time migration failure now records a failed run if the migration created the history table before a later step failed. Fourteen focused script tests pass and `bash -n` passes. Live upgrade/rollback, backup restore, and release checksum parity remain unassessed; CAP-052 is not accepted ([evidence](builds/2026-10-19-recovery/cap-052-upgrade-history-transition.json)). |
| CAP-053 | Field data collection | services/mobile/; docs/field-data-collection-guide.md | MAN-CAP-053: Offline capture, enrollment, private media and sync dedupe preserve device/farm scope | tests/test_mobile_api.py; tests/test_mobile_form_validation.py; tests/test_mobile_offline.py; tests/test_mobile_media_storage.py | D — migration 381 provides immutable revisions, reviewer-scoped participant links, consent checks, and downstream eligibility. Sync validates each payload against its exact revision schema; undeclared fields fail with non-echoing errors, and remote `$ref` retrieval is rejected. Focused mobile/schema checks passed (60); four CORS cases passed in the previous slice. A fresh encrypted pre-rollout checkpoint restored into a network-isolated template0 database with matching 372 migration fingerprints, extension versions, and schema inventory; five immutable 1.2.0 forms are active, five 1.1.0 revisions retired, and the app/database/Metabase are healthy. `/api/mobile/app` served five 1.2.0 fallbacks (200); anonymous forms returned an empty list (200), while location query without token and invalid token returned 401 ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)). Legacy rows remain unassessed. Source-level OIDC console routes now issue and revoke location-scoped enrollments/devices with CSRF and no-store code responses; five route/auth tests pass. A synthetic live HTTP enrollment→registration→forms→sync check passed against the restored clone: enrollment 201, derived registration 200, five 1.2.0 forms, and one valid field note accepted (200); all synthetic rows were removed. Eligibility correctly remained false as `transport_pending`. Real-provider OIDC/browser scope acceptance and retired-form browser consent acceptance remain open. A live Gateway ASGI/HTTP check with a synthetic reviewed retired required-consent revision returned 403 after withdrawal despite regrant and wrote no collection or success log; seeded retired `1.1.0` revisions are `not_required` and were not used for that policy branch ([retired Gateway evidence](builds/2026-10-12-recovery/field-collector-retired-form-gateway-http-consent-withdrawal.json)). A temporary process used the encrypted local media adapter: upload 201, AES-GCM ciphertext at mode 0600, wrong-key rejection, authenticated head verification, and attachment during sync passed; synthetic files and rows were removed. The running candidate provider configuration was unchanged and no public download route is defined. A one-object age-encrypted local media checkpoint/restore rehearsal passed with AES-GCM authentication, plaintext digest verification and wrong-key rejection. A second synthetic replay previously verified only the supplied SOPS age identity. Since then, with owner approval, a random 32-byte `MOBILE_MEDIA_LOCAL_KEY` was added to `.env.sops`; targeted readback matched without emitting the value, and a one-object KKM1 checkpoint/restore using that exact SOPS key and age identity passed AES-GCM authentication, plaintext digest, and wrong-key rejection ([current provisioning/recovery evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-provisioning.json); [historical key availability evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-availability.json); [first evidence](builds/2026-10-12-recovery/field-collector-media-backup-restore.json); [age-only evidence](builds/2026-10-12-recovery/field-collector-media-sops-age-restore.json)). The candidate now runs local media through the edge overlay; the source and base Compose profile still default to S3. The isolated edge overlay also passed synthetic SOPS-keyed named-volume recovery across two disposable app containers ([edge volume evidence](builds/2026-10-12-recovery/field-collector-edge-media-volume-recovery.json)). Synthetic PostgreSQL/upload-row parity and actual candidate app recreation/restart are verified; production migration/recovery and live S3/R2 inventory/deletion acceptance remain open. Free-text/photo semantic review and retention/erasure remain open; tenant-aware grant source (migrations 388–389) is implemented and passed focused disposable PostgreSQL authorization and trigger checks; operator-CLI membership/share lifecycle and legacy-grant conversion passed disposable acceptance; clean full-schema replay of all 380 migrations, including the 384–385–389 trigger stack, passed ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)); migration 390 implements two-party audited transfers; 14 disposable PostgreSQL transfer/context checks and eight context unit tests pass ([acceptance](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)); migrations 387–390 are deployed on the candidate after an encrypted checkpoint, with zero pending schemas and 120 seed files pending in the ledger (five mobile-form rows and ten revisions exist without applied seed history); the app-only rollout is healthy and protected routes return 401 ([rollout](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json)); operator-affiliation reconciliation, worker integration, direct-database isolation, and RLS remain open under the target boundary documented in [mobile-tenant-isolation.md](mobile-tenant-isolation.md). The read-only ownership/lineage preflight ran against the empty candidate and a migrated populated archive copy. All 32 pending schemas through migration 385 applied transactionally with zero failures and the final plan has zero pending. The corrected complete-schema inventory found two locations, no active organization-member rows, one direct organization assignment not confirmed by an active owned-primary relationship, and one unassigned location; it counted four mobile devices and five location-scoped dashboard datasets, plus three report snapshots and 38 dashboard datasets without a location. An initial false-reference result exposed UUID-array string decoding; the query now returns text arrays and fails closed on an unexpected shape. No owner was inferred or backfilled. Accountable owner review, unlocated-row lineage, tenant-aware grants, and RLS remain open ([replay evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json)). A secure-origin service worker caches only static app HTML and the vault helper; `/mobile` now redirects to `/mobile/` so relative worker and vault paths remain inside the existing Gateway proxy route (33 mobile API tests and 2 Node offline-shell checks pass); the candidate app-only rebuild returned 308/200 for the redirect/canonical page and 200 JavaScript for the worker, with PostgreSQL and Metabase healthy; local candidate Caddy ingress passes route, worker, health, and security-header checks; an isolated browser stopped at ERR_CERT_AUTHORITY_INVALID and the interstitial was not bypassed; browser-through-proxy and external Traefik/public ingress remain open; a real-browser origin-outage run reopened this shell, retained one encrypted field note across reload, then accepted one mock sync and cleared the queue ([browser evidence](builds/2026-10-12-recovery/field-collector-browser-offline-reconnect.json)). A later online candidate-Gateway browser run enrolled from a one-time synthetic fixture, synced two synthetic 1.2.0 notes, and verified that the pending badge clears automatically without page navigation or manual sync. Aggregate DB evidence recorded two successful uploads; both rows remained `transport_pending` and `eligible_for_use=false`. Candidate location/device/enrollment/collection/log fixture rows were removed. A local-vault reset is now available from the locked-browser gate: after explicit browser confirmation it deletes the encrypted IndexedDB database and known legacy keys, while warning that server enrollment must be revoked separately. Focused adapter deletion, blocked-delete, cross-tab-lock, and reopen checks pass; the candidate browser showed the control, which was not invoked; the repository owner later unlocked the vault. New mocked API regression tests reject retired required-consent photo uploads after withdrawal and reject retired-record sync after withdrawal even when a later grant exists; both assert rollback and no private media or collection write (62 focused mobile tests pass; rollback-only PostgreSQL view acceptance confirms active-grant eligibility and persistent ineligibility after withdrawal/regrant ([source evidence](builds/2026-10-12-recovery/field-collector-withdrawal-source-tests.json), [database evidence](builds/2026-10-12-recovery/field-collector-postgres-consent-eligibility.json)). A live PostgreSQL-backed direct sync-handler call and a separate Gateway ASGI/HTTP request both rejected withdrawal after regrant with 403 and wrote no collection or upload log ([handler evidence](builds/2026-10-12-recovery/field-collector-postgres-sync-withdrawal.json), [Gateway evidence](builds/2026-10-12-recovery/field-collector-gateway-http-consent-withdrawal.json)). Focused rerun of the mobile/API/CORS Python suites passed 83 tests, with 11 Node shell/vault checks also passing ([evidence](builds/2026-10-12-recovery/field-collector-consent-source-regressions.json)). A synthetic retired-required-consent browser client check passed: native minlength blocked a short reference, and one valid-reference record remained encrypted and pending after the mock returned 403. The isolated test vault retains that synthetic record; the mock server is stopped. This does not test candidate Gateway consent withdrawal. The Directus-independent manifest CLI validates/previews offline and supports explicit transactional publication through `mobile_form`; apply requires a distinct operator and expected-version/absence guard. Twenty-nine focused form/schema checks and Ruff pass with a fake transaction adapter. A separate no-volume PostGIS fixture passed snapshot/actor/retirement, stale/reuse/location rejection, rollback, and historical-content checks; it applied the migration 381 publication prefix only ([evidence](builds/2026-10-12-recovery/mobile-form-publication-transaction.json)). The OIDC-scoped queue/detail source and console UI use separate list/detail grants; append-only reviewer notes require both `review` and `read_detail`, and migration 382 enforces eligibility, evidence shape, attribution, and immutability. Twenty-two focused route/query/auth tests pass; migration 382 and the actual Gateway service functions passed isolated PostGIS checks for queue list/detail, append/history, unchanged collection state, cross-location and revoked-grant denial, malformed/missing evidence, unsynced rows, update, and delete behavior ([migration evidence](builds/2026-10-12-recovery/mobile-review-event-migration-isolated.json)). A clean ordered replay of all 373 schema migrations through 382 passed with zero pending; migration 382 is applied to the candidate and the rebuilt app is healthy; real-provider/browser, live disposition, retention/erasure, and tenant/RLS acceptance remain open ([candidate evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json)) ([form contract](mobile-form-operations.md); [console contract](kernel-operations-console.md)). Browser consent withdrawal, offline capture/reconnect from a client whose path to the Gateway is severed, real OIDC, production media backup/retention, live S3/R2 inventory/deletion acceptance, and human disposition remain open. Two disposable full-runtime instances on the candidate network passed health and named-volume recovery while the main services remained untouched ([evidence](builds/2026-10-12-recovery/field-collector-media-runtime-volume-recreation.json)). Isolated migration-358 upload-row/object parity passed with one synthetic object ([evidence](builds/2026-10-12-recovery/field-collector-media-db-object-parity.json)). The dry-run-default cleanup CLI now expires only expired unattached uploads; 44 focused mobile/media/API/CLI tests and disposable PostGIS/provider acceptance passed; standard and security Ruff checks passed. Provider-neutral orphan reconciliation is implemented; 31 focused tests and an isolated local apply check passed, and the local candidate dry-run found zero objects ([candidate evidence](builds/2026-10-12-recovery/field-collector-media-orphan-reconcile.json); [isolated apply evidence](builds/2026-10-12-recovery/field-collector-media-orphan-apply-isolated.json)). Live S3/R2 listing/deletion and production retention remain open. A brief approved Wi-Fi-off probe against localhost kept reporting Online and is not offline acceptance ([probe](builds/2026-10-12-recovery/field-collector-wifi-off-probe.json)). [Live browser evidence](builds/2026-10-12-recovery/field-collector-browser-candidate-gateway.json). [Access contract](mobile-access-contract.md); [policy decisions](mobile-form-classification-review.md); [media](local-private-media.md); [recovery](work-media-recovery.md); [fixture](recovery-media-fixture.md)  Candidate edge media is active on the running local candidate: the app-only recreation and restart preserved a synthetic encrypted object with authenticated SHA-256; the upload table remains empty ([evidence](builds/2026-10-12-recovery/field-collector-candidate-edge-media-activation.json)).  The latest live browser outage retry exposed and fixed blank optional fields serialized as null; with empty fields omitted, the encrypted queue held one note while the candidate app was unavailable, then background retry received HTTP 200 and cleared the queue after recovery. A guarded cleanup revoked/removed the synthetic fixture; the accepted row stayed ineligible as `transport_pending` ([outage/reconnect evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json)). This kept host Wi-Fi online and does not verify `navigator.onLine=false` or OS airplane mode. This slice now prevents generic retention sweeps from mutating protected mobile and governed activity tables; restricted pending disposition is documented, while human erasure execution and jurisdiction-owned periods remain unimplemented. A separate `mobile_collection_retention:inventory` route and console action now expose content-free counts/statuses for known direct collection/media/canonical-activity/review lineage; it requires queue-read plus the separate inventory grant, and does not confer payload access or perform dispositions. Focused dual-grant authorization, query-scope/read-only, and console checks pass (49 focused operator auth/review/console tests; Ruff clean); complete lineage, human disposition, jurisdiction-owned retention, and live R2 listing/deletion remain open; source-level private-prefix validation for upload/head/delete now has 49 focused storage/reconcile/cleanup test passes. The selected production ZITADEL hostname, expected issuer, HTTPS port, and Gateway callback also render in offline Compose acceptance (8 focused tests; [evidence](builds/2026-10-23-recovery/zitadel-selected-host-config.json)); live OIDC remains open. |
| CAP-054 | Silvi tree tracking | services/analytics/tree_tracking.py | MAN-CAP-054: GPS tracking, growth/pest analytics and exports preserve locations and units | tests/test_tree_tracking.py; tests/test_spatial_export.py | B — tree-density reads now use the deployed `plot.area`/`area_unit` columns, normalize hectares/square meters/acres, and return unavailable density for unsupported or zero area; growth calculations retain legitimate zero measurements and average canopy independently of height data. Forward migration 462 applies the same conversion to the public density view without changing applied migration 057. Twenty focused tests pass with Ruff and compilation; disposable PostGIS applied/replayed 462 and verified synthetic area outputs. Candidate rollout, populated legacy parity, Silvi/provider behavior, pest analytics, spatial exports, and MAN-CAP-054 review remain open ([evidence](builds/2026-10-19-recovery/cap-054-tree-area-and-growth.json)). |
| CAP-055 | Oracle infrastructure | services/ingestion/ | MAN-CAP-055: Feed consensus and actuator dispatch retain safety/authorization gates | tests/test_oracle_infrastructure.py | B — median and weighted consensus now reject invalid prices, invalid confidence, naive timestamps, and duplicate normalized source identities; deviation thresholds fail closed, and zero-weight providers are excluded. Thirty-eight focused tests pass with Ruff and compilation. No provider, database, chain, MQTT broker, or actuator was contacted. Physical actuation is still unaccepted: the low-level publisher is not linked to persisted approval state, and operator authorization, delivery idempotency, and device acknowledgment lack a verified contract. Feed freshness, reference-price parity, consensus tolerances, on-chain behavior, and MAN-CAP-055 review remain open ([evidence](builds/2026-10-19-recovery/cap-055-oracle-input-validation.json)). |
| CAP-056 | Revenue model & channels | services/analytics/ | MAN-CAP-056: Revenue, pricing and channel delivery preserve partner scope and approved execution | tests/test_revenue_model.py; tests/test_channel_health.py | B — channel delivery plans scope preferences to the requested segment and location, omit inactive/unconfigured channels, and do not default to all channels when explicit preferences target only inactive channels. Channel config and delivery-plan reads, including defaults, recursively redact credential-shaped fields. Break-even analysis rejects non-finite values and negative costs before database access. Six focused mocked checks pass with Ruff and compilation. The legacy write path may still persist inline provider credentials in JSONB; SOPS-backed secret references, provider delivery, tenant authorization, finance-output parity, populated fixtures, and MAN-CAP-056 remain open. Revenue Multiplier failures return class-only summaries with partial results preserved; SDK accessors expose stored local market/pricing records without provider refresh or recalculation ([channel evidence](builds/2026-10-19-recovery/cap-056-channel-plan-secrets.json); [SDK evidence](builds/2026-10-18-recovery/sdk-market-capital-read-methods.json)). |
| CAP-057 | Environmental scanning | services/analytics/ | MAN-CAP-057: PESTEL, regional readiness and segment results match evidence fixture | tests/test_pestel.py; tests/test_env_scanning.py | B — PESTEL factor inserts now require an existing analysis, bind factor location to that analysis, and reject non-finite/out-of-range impact and likelihood before SQL writes. Environmental scan communication now includes freshly collected findings alongside retained findings from steps without new evidence. Eleven focused mocked checks pass with Ruff and compilation. Regional readiness, segment outputs, reference fixtures, populated parity, tenant authorization, and MAN-CAP-057 remain open ([evidence](builds/2026-10-19-recovery/cap-057-environmental-scan-scope.json)). |
| CAP-058 | Marketplace | services/analytics/marketplace.py | MAN-CAP-058: Listings, orders and cooperative orders preserve lifecycle and account custody | tests/test_marketplace.py; tests/test_marketplace_integration.py | B — listing, price-observation, order, and editable listing numeric inputs now reject non-finite or non-positive values before writes; the API’s `quality_grade` is persisted in price observations. Removed an unused harvest-yield query from listing evaluation. The mocked unit suite passes 42 tests and 17 subtests with Ruff and compilation; no database was used. Order lifecycle/custody, concurrent inventory reservation, cooperative order behavior, populated parity, and MAN-CAP-058 remain open. Read-only SDK accessors expose buyer-demand signals, segments, and production-market matches by location; they do not confirm commitments, fulfill orders, or mutate marketplace lifecycle ([marketplace evidence](builds/2026-10-19-recovery/cap-058-marketplace-inputs.json); [SDK evidence](builds/2026-10-18-recovery/sdk-market-capital-read-methods.json)). |
| CAP-059 | Abundance Protocol | services/abundance/ | MAN-CAP-059: Impact validation/voting/credit adjustment preserves lifecycle and approval | tests/test_abundance_protocol.py | B — validator selection now applies exact case-insensitive domain/category matching and the requested expertise threshold, records expertise separately from trust, and samples with system randomness. Reviews require a selected/revealed validator in an active round under a row lock. Quadratic votes validate finite weight and schema vote type before SQL. Coin issuance validates a positive finite score and locks a validated/finalized periodic-impact row before inserting. The protocol suite passes 66 mocked/schema checks with Ruff and compilation; no database or chain was used. Commit/reveal payload verification, category synonym/fixture parity, chain custody, funding/distribution rules, populated parity, and MAN-CAP-059 remain open ([evidence](builds/2026-10-19-recovery/cap-059-abundance-governance-guards.json)). |
| CAP-060 | Schema.org alignment | services/linkml/ | MAN-CAP-060: Schema mappings, JSON-LD context and graph exports retain URI vocabulary | tests/test_linkml_jsonld.py; tests/test_linked_data.py::TestSchemaOrgAlignment | B — default Schema.org and GeoSPARQL prefixes now exactly match the LinkML YAML namespaces, fixing malformed `schema:name` expansion and GeoSPARQL URI drift. Prefix expansion/compaction round-trips and explicit empty JSON-LD contexts are covered; 14 focused tests pass with Ruff and compilation. Broader schema-derived context generation, graph/export parity, and MAN-CAP-060 review remain open ([evidence](builds/2026-10-19-recovery/cap-060-jsonld-uri-roundtrip.json)). |
| CAP-061 | Regen Network parity | services/credit_class/; services/data_module/; services/linkml/schemas/ | MAN-CAP-061: Regen-compatible enums/project/claim/credit representations remain compatible | tests/test_regen_standards_parity.py; tests/test_linked_data.py::TestSchemaOrgAlignment | B — Project and CreditClass schemas now declare the Regen `rfs:ProjectInfo` and `rfs:CreditClassInfo` class URIs, and JSON-LD document generation preserves an explicit CURIE/IRI type. ImpactClaim now separates the local record kind and governance lifecycle from Regen `ClaimType` and `VerificationStatus`, uses the `rfs:Claim` class and standard field URIs, and its record/category/status/type values match the SQL constraints. Seven source-backed offline tests pass; all five LinkML YAML files parse. Regen credit-batch fields/units, attestation mapping, upstream version pinning, populated/reference fixture parity, chain behavior, and MAN-CAP-061 remain open ([evidence](builds/2026-10-19-recovery/cap-061-regen-schema-crosswalk.json)). |
| CAP-062 | ARKIV parity | services/data_module/; services/data_stream/post.py; services/gateway/data_stream.py; services/credit_class/fees.py; services/credit_class/batch_manager.py; services/grpc/credit_class_service.py; proto/ecocredit/v1/service.proto | MAN-CAP-062: Expiry, transaction origin and fee distribution preserve documented representations | tests/test_credit_fees.py; tests/test_credit_batch_manager.py; tests/test_linked_data.py; tests/test_data_stream.py; tests/test_gateway_data_stream.py; tests/test_grpc_enabled_transport.py | B — marketplace fee collection rejects invalid/non-finite amounts and normalizes to NUMERIC(18,8); zero-fee records settle as a no-op. Distribution locks the fee row, requires matching denominations, rejects exact over-distribution, and marks completion only when fully paid. Batch creation validates paired origin ID/source, stores origin references, and writes the existing unique origin index in the same caller transaction; CLI and gRPC inputs are available. Data Stream post create/update accepts optional timezone-aware expiry values normalized to UTC, and Gateway writes/reads carry the value without inferring a retention period. The focused selection passes 295 tests, one database-dependent skip, and 17 subtests with Ruff and compilation; the 30-test gRPC run used the approved host-access path for local loopback. SDK protobuf generation is pinned to grpcio-tools 1.68.1/protobuf 5.29.1 and checked against all generated modules. Expiry remains metadata-only and is not connected to retention-policy enforcement/cleanup; other expiry-bearing entities remain unintegrated. Origin conflict rollback/concurrency is not proven in PostgreSQL. MAN-CAP-062 remains unaccepted ([evidence](builds/2026-10-19-recovery/cap-062-fee-distribution-settlement.json)). |
| CAP-063 | GeoNode parity | services/csw/__init__.py; services/csw/serializer.py; services/ingestion/gis_import.py; services/ingestion/raster_metadata.py; services/maps/viewer.html; services/geostory/; services/thesaurus/ | MAN-CAP-063: GIS/KML/raster import, metadata, CSW, map and geostory access match fixture | tests/test_csw_catalog.py; tests/test_csw_serializer.py; tests/test_map_viewer_contract.py; tests/test_gis_import.py; tests/test_geospatial_import_error_redaction.py; tests/test_legacy_geo_import_error_redaction.py; tests/test_spatial_import.py; tests/test_security_hardening.py; tests/test_raster_metadata_error_redaction.py | B — `GetRecord` applies the same public-visibility filter as `GetRecords`, and invalid/oversized page sizes fail before SQL. `GetRecords` counts the full filtered public result set before pagination. Retained CSW serializers escape metadata, replace XML 1.0 forbidden controls, and declare `gmd`/`gco` namespaces. The Leaflet viewer constructs farm popups with text nodes and validates finite WGS84 coordinates while retaining zero values. GIS import validates finite/ranged positions, closed rings, and coordinate-count bounds; Polygon/MultiPolygon WKT preserves interior rings and invalid/empty input preflight avoids PostgreSQL. KML Placemark Polygon/MultiGeometry import preserves holes/ExtendedData and uses defusedxml against entity expansion. Raster metadata maps `.tif`/`.tiff` to the schema's `tiff` format and does not fabricate EPSG:4326 when CRS is missing. The focused CSW/GIS/map, spatial KML, security, raster metadata, and import-redaction selection passes 70 tests with Ruff, compilation, and JavaScript syntax. The map still depends on its legacy Directus endpoint; no tenant-scoped Gateway map API, CSW endpoint, or ISO 19115 fixture parity is established. KML style/altitude, raster GroundOverlay/persistence, layer authorization, PostGIS recovery, populated spatial fixtures, geostory, thesaurus, database-backed matched-total fixture/output-schema parity, catalog HTTP routes, and MAN-CAP-063 remain open ([evidence](builds/2026-10-19-recovery/cap-063-csw-xml-safety.json)). |
| CAP-064 | gRPC API | services/grpc/; services/grpc/pagination.py; services/grpc/credit_class_service.py; services/credit_class/page_queries.py; services/credit_class/class_manager.py; services/credit_class/batch_manager.py; services/credit_class/basket.py; services/credit_class/marketplace.py; proto/; sdk/ | MAN-CAP-064: Generated protocol, API-key scope and streaming behavior match REST policy | tests/test_grpc.py; tests/test_grpc_auth_context_lifecycle.py; tests/test_grpc_auth_denial_cardinality.py; tests/test_grpc_enabled_transport.py; tests/test_grpc_error_redaction.py; tests/test_grpc_optional_boundary.py; tests/test_grpc_sdk_method_parity.py; tests/test_grpc_pagination.py; tests/test_credit_class_page_queries.py; tests/test_grpc_health_tls.py; tests/test_grpc_server_tls_preflight.py; tests/test_python_grpc_channel_factory.py; sdk/typescript/src/__tests__/ecocredit-pagination.test.ts; sdk/typescript/src/__tests__/transport.test.ts; sdk/typescript/src/__tests__/sdk.test.ts; tests/test_grpc_data_service_contract.py | P — optional target, scoped auth, pooled DB and bounded shutdown prepared; private-only/insecure-network, API-key, runtime-role and health limits documented. The Python SDK includes optional namespaced generated stubs that passed an isolated wheel import. The TypeScript gRPC SDK's clean build/archive include the five required proto files and exclude tests; both service clients loaded from an extracted package and closed without RPC calls. Authentication denials now preserve unary-unary, unary-stream, stream-unary, and stream-stream handler cardinality; the enabled loopback check confirms a missing-key unary-stream call returns UNAUTHENTICATED before service DB acquisition. The expanded focused gRPC selection passes 48 tests with Ruff and compilation. Live TLS endpoint behavior, real DB/runtime roles, tenant scope, and REST parity remain unassessed. [gRPC contract](grpc-overlay.md); [loopback evidence](builds/2026-10-14-recovery/grpc-enabled-loopback-transport.json); [denial evidence](builds/2026-10-19-recovery/cap-064-grpc-denial-cardinality.json) The TypeScript SDK inventory now covers all 55 protocol RPCs exactly once; source fallback lets clean-checkout Vitest construct clients, while the built package uses its bundled proto set (25 TypeScript tests, 2 inventory tests; [evidence](builds/2026-10-21-recovery/cap-064-grpc-sdk-rpc-coverage.json)). The TypeScript SDK also forwards cursor pagination for all nine paginated EcocreditService list methods, models optional proto pagination metadata, and preserves no-argument calls (25 TypeScript tests; [pagination evidence](builds/2026-10-21-recovery/cap-064-typescript-pagination.json)). All nine paginated EcocreditService list handlers now return bounded pages and totals, with a next cursor encoded as ASCII decimal offset bytes; zero limit selects 100, limits above 500 and malformed cursors fail before service DB acquisition. Cursor forwarding, no-argument compatibility, a two-page enabled-transport round trip, and invalid-input preflight pass; the manager selection passes 272 tests, one skip, and 17 subtests. Paginated manager reads now use deterministic SQL LIMIT/OFFSET and project reads page location IDs before metadata hydration; page-row materialization is bounded, but COUNT and large offsets may scan many records. Count/page statements and subsequent RPCs are independent, so concurrent writes can change totals or shift pages. Runtime auth/tenant/TLS and REST parity remain open. [Bounded-page query evidence](builds/2026-10-21-recovery/cap-064-bounded-page-queries.json). `GRPC_MAX_MESSAGE_BYTES` now caps inbound/outbound gRPC messages at a configurable 1–64 MiB (4 MiB default); invalid configuration fails before pool creation, and enabled loopback proves oversized requests/responses return `RESOURCE_EXHAUSTED` ([message-size evidence](builds/2026-10-21-recovery/cap-064-grpc-message-size-limits.json)). The health CLI now accepts `--tls-ca`/`GRPC_TLS_CA`, selects a secure channel, and fails closed when server TLS settings lack a CA path; mocked trust-file, channel-selection, cleanup, and CLI checks pass (44 focused gRPC tests; [TLS health evidence](builds/2026-10-21-recovery/cap-064-grpc-health-tls.json)). Compose passes path settings without mounting certificate material. Server TLS files and credentials now validate before pool acquisition with redacted failures. A real loopback handshake verifies the supplied self-signed trust root and 127.0.0.1 IP SAN; remote health targets now require CA-verified TLS unless `--insecure` is explicit; plaintext defaults only to recognized loopback. The 50-test unit selection and seven enabled transport checks pass ([plaintext policy evidence](builds/2026-10-21-recovery/cap-064-grpc-health-remote-plaintext-policy.json)). The TypeScript SDK also uses system-trusted TLS for remote targets by default, preserves explicit credentials, and keeps plaintext to recognized loopback; 35 Vitest checks, build, and package dry run pass ([SDK evidence](builds/2026-10-21-recovery/cap-064-typescript-grpc-tls-defaults.json)). The optional Python SDK now exposes a lazy TLS-by-default channel helper with explicit remote plaintext opt-in; 16 focused tests, compilation, and wheel build pass ([Python SDK evidence](builds/2026-10-21-recovery/cap-064-python-grpc-channel-factory.json)). Production DNS certificate, certificate lifecycle, public ingress, authenticated tenant scope, and REST parity remain open ([server preflight evidence](builds/2026-10-21-recovery/cap-064-grpc-server-tls-preflight.json); [TLS loopback evidence](builds/2026-10-21-recovery/cap-064-grpc-health-tls-loopback.json)). Server startup now requires TLS unless `GRPC_ALLOW_INSECURE=true` explicitly opts into trusted private-network plaintext; missing or malformed settings fail before database-pool creation. Local legacy Compose defaults the explicit option for local development, the private Kernel gRPC overlay sets it with no host port, and production forces it off ([server plaintext policy](builds/2026-10-21-recovery/cap-064-grpc-server-plaintext-opt-in.json)). The orphan `agent-summary-worker` environment-only entries have been removed from Kernel standard/runtime-role overlays; the legacy one-shot worker remains outside Kernel until a complete adapter is provided.  The TypeScript DataService now normalizes every unary response and streamed IRI update from protobuf snake_case into its declared camelCase result shape, validates malformed responses and int32 versions, and bounds stream buffering with pause/resume and cancellation-safe cleanup. Proto `IRIInfo.hash_algorithm` now matches the Python handler's content-hash algorithm. Twenty-five focused mock tests pass; this establishes source/client shape only, not live gRPC transport or REST parity ([evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)). The TypeScript Ecocredit client also rejects malformed or out-of-range page limits locally across all nine list methods while preserving cursor bytes; 36 focused tests pass ([evidence](builds/2026-10-29-recovery/kernel-analytics-and-ecocredit-input-contracts.json)). This does not establish live gRPC transport or runtime acceptance. |
| CAP-065 | Business Model Canvas | services/analytics/business_model_canvas.py; services/gateway/business_planning_writes.py; services/gateway/business_planning_routes.py; services/gateway/business_planning_edits.py; services/gateway/business_planning_metadata.py; services/gateway/business_planning_edit_routes.py; services/gateway/business_planning_reads.py; services/gateway/operator_auth.py; schemas/postgres/463_location_scoped_business_canvas_create.sql; schemas/postgres/464_location_scoped_business_canvas_edit.sql; schemas/postgres/465_location_scoped_business_canvas_metadata_edit.sql; services/gateway/comprehensive_status_reads.py; services/gateway/comprehensive_status_routes.py; services/export/reports/core.py; services/export/reports/state.py; services/export/reports/strategy.py; services/export/reports/context.py; services/export/reports/commons/ecological.py; services/export/reports/commons/kokonut.py; services/export/reports/commons/bio_factory.py; services/export/reports/commons/liberation.py; services/export/reports/commons/scaling.py; services/capital/capture.py | MAN-CAP-065: One-click canvas and fourteen-section status retain evidence and scope | tests/test_bmc_oneclick.py; tests/test_comprehensive_status.py; tests/test_gateway_comprehensive_status_reads.py; tests/test_stakeholder_outcomes_scope.py; tests/test_gateway_business_planning_writes.py; tests/test_gateway_business_planning_edits.py; tests/test_gateway_business_planning_metadata.py; tests/test_operator_route_policy_inventory.py; tests/test_migration.py; scripts/check-business-canvas-create-disposable.py; scripts/check-business-canvas-edit-disposable.py | P — protected location canvas creation now supports caller-composed drafts and one-click `/canvases/from-data` generation. Both require exact signed `business_planning:create`, OIDC/CSRF, and migration 463; generated mode establishes context before source reads and uses the same transaction for location-bound suggestions and draft creation. It rejects caller-supplied blocks, returns populated-block/source-category metadata, and records bounded source-category tags. The shared suggestion builder uses current location-bound verified/published records, native-currency expenses, and consented public feedback. The focused Gateway/policy/legacy suggestion selection passes 42 tests; eight legacy DB-backed tests skip because local PostgreSQL is unavailable. Universal ACL/RLS remains open; migration 463 is additive and does not revoke CLI/Directus DML. Location-scoped status now suppresses global stakeholder links and filters published anti-capture policies to the exact location; per-section savepoints recover failed queries. The 28-test source-scope repair and 59-test combined Gateway/status selection pass with Ruff and compilation; inventories were refreshed and no database was used. A separate `GET /operator/api/comprehensive-status/{location_id}` now requires exact `comprehensive_status:read`, OIDC, and same-transaction signed location context; it runs read-only with statement/lock timeouts, rejects invalid dates before opening the report-data connection, and caps responses at 512 KiB. No audience receives automatic access; the read contract and route do not establish populated-output parity. Migration 464 adds `PATCH /canvases/{canvas_id}/blocks/{block_name}` for exact-grant draft-only edits with expected version/timestamp, request idempotency, and append-only prior-state history; a bounded `GET /canvases/{canvas_id}/versions` returns current plus scoped prior snapshots. The 94-test Gateway/read/write/policy/migration selection passes; disposable PostgreSQL 16 applies/replays migration 464 and passes 14 edit, retry, stale-write, lifecycle, allowlisted legacy-history, scope, and privilege assertions, including migration application without optional runtime roles. Ruff, compilation, matrix validation, and refreshed runtime SQL inventory pass; candidate and legacy databases are untouched, and migrations 464 and 465 are not rolled out. CLI/Directus table writers remain compatible and can bypass Kernel history. Populated 14-section report parity, row-level source evidence parity, canvas lifecycle-transition parity, live OIDC/browser, universal ACL/RLS, legacy writer retirement, and MAN-CAP-065 owner review remain open. Migration 465 adds draft-only allowlisted metadata edits for canvas name, description, fiscal year, and tags; they share the request ledger, optimistic version guards, and history snapshots with block edits. The 112-test focused Gateway/read/write/policy/migration selection passes, and disposable PostgreSQL 16 applies/replays migration 465 with 21 grouped authorization, validation, retry, history, lifecycle, and privilege assertions; roleless optional-app migration also passes. Candidate and legacy databases remain untouched. Lifecycle transitions, populated metadata/content parity, live OIDC/browser, universal ACL/RLS, legacy writer retirement, and MAN-CAP-065 owner review remain open ([read contract](comprehensive-status-kernel-read-contract.md); [write contract](business-planning-kernel-write-contract.md); [migration](../schemas/postgres/463_location_scoped_business_canvas_create.sql); [generated-draft evidence](builds/2026-10-19-recovery/cap-065-gateway-generated-draft.json); [create evidence](builds/2026-10-19-recovery/cap-065-business-canvas-create-disposable.json); [edit contract](business-planning-kernel-edit-contract.md); [edit migration](../schemas/postgres/464_location_scoped_business_canvas_edit.sql); [edit tests](../tests/test_gateway_business_planning_edits.py); [edit evidence](builds/2026-10-19-recovery/cap-065-business-canvas-edit-disposable.json)). |
| CAP-066 | State of Kokonut | services/export/; services/export/reports/core.py; services/export/reports/state.py; services/export/reports/strategy.py; schemas/postgres/528_location_scoped_stakeholder_landscape.sql; scripts/report_generator_query_scope_inventory.py; scripts/report_generator_helper_scope_inventory.py; services/capital/diversion.py; services/analytics/value_stream.py; services/planning/budget.py| MAN-CAP-066: Network report, funding rollup and timelines match baseline exports | tests/test_state_of_kokonut.py; tests/test_state_of_kokonut_graphs.py; tests/test_comprehensive_status.py; tests/test_farm_activity_summary_report.py; tests/test_crop_noi_report.py; tests/test_stakeholder_foundation.py; tests/test_data_stream.py; tests/test_report_generator_query_scope_inventory.py; tests/test_report_generator_helper_scope_inventory.py; tests/test_capital_accounting.py; tests/test_value_stream.py; tests/test_report_generator_inventory.py; tests/test_planning_budget.py; tests/test_report_state_cursor_cleanup.py; tests/test_report_snapshot_cursor_cleanup.py; tests/test_report_generator_cli.py; tests/test_unified_cli_success_contract.py| P — exporter ClickHouse construction moved behind an optional adapter; a separate OIDC-scoped read-only console lists location-specific submitted `report_snapshot` records and can read their detail in source. Funding source totals now group by currency, participation totals retain token denomination, and a mixed-currency `total_raised` is null with a separate `total_raised_by_currency` map; 14 State of Kokonut/report-graph tests pass with Ruff and compilation using synthetic USD/USDC rows. Per-location farm summaries and State/comprehensive network rollups now preserve harvest totals by native unit; mixed-unit scalar values are null. The farm-summary harvest source now includes only verified/published lifecycle rows, matching the canonical crop-NOI view; draft, submitted, and rejected events do not enter report aggregates. Verified/published expense-category totals also honor the requested inclusive period via expense_date, alongside financial transaction_date, harvest date, and published activity date filters. The focused CAP-066 report selection passes 24 tests with Ruff and compilation using mocked/synthetic rows. The crop NOI report now reads the shared formula view and returns verified-input revenue/cost components; migration 527 excludes draft/rejected and cross-location source rows without changing the view output schema. The stakeholder cockpit is explicitly network-only because its internal/public aggregate views have no farm dimension: farm-scoped CLI and direct calls fail closed, while auto-generated snapshots remain unassigned. Two focused report tests and disposable PostgreSQL migration/replay checks pass. The same fail-closed, unassigned snapshot policy now covers coordination cockpit, DAO proposal history, governance coordination health, stakeholder ecosystem, representation, trust and value streams, and technology roadmap. Their global views/ledgers do not establish farm lineage; nine-report CLI, direct-call, and auto-scope checks pass (73 passed, five database-dependent skips) ([scope evidence](builds/2026-10-21-recovery/cap-066-network-only-report-scopes.json)).  Three additional public reference reports (regional bio inputs, Green Paper publication status, and open-source impact) are now network-only because their source views have no farm predicate; the expanded CLI/direct-call/auto-snapshot scope selection passes (86 passed, five database-dependent skips) ([evidence](builds/2026-10-21-recovery/cap-066-public-reference-report-scope.json)).  Seven more helper-backed reports (capability assessment/dashboard, federation mutual aid, participatory signal, process health, strategy execution, and formal value streams) are network-only where helpers return global catalogs, intentionally omit location filters, or mix global and farm-filtered measures. The expanded scope suite passes 121 tests with seven database-dependent skips. A source-only regression cross-checks the generated no-scope inventories against the network-only registry and the known multi-location adapters (109 inventory/CLI tests pass) ([evidence](builds/2026-10-21-recovery/cap-066-helper-backed-network-report-scopes.json)).  `scaling_economics` now separates farm-specific launch costs from network targets: farm snapshots omit network target rows/totals, while network runs include both datasets and remain unassigned ([evidence](builds/2026-10-21-recovery/cap-066-scaling-economics-scope.json)).  `strategic_reserve` farm snapshots now omit network-wide reserve balances/counts and fundability, retaining only the selected farm seed-vault summary; network runs keep the aggregate reserve view ([evidence](builds/2026-10-21-recovery/cap-066-strategic-reserve-scope.json)). The stakeholder landscape now keeps canonical party identity network-wide while a location report uses migration 528’s separate location-lineaged aggregate for verified location identifiers, scoped relationships/interests, and scoped salience; the view uses invoker privileges so caller row policies apply; source and disposable PostgreSQL checks pass ([evidence](builds/2026-10-21-recovery/cap-066-stakeholder-landscape-location-scope.json)). No FX or harvest-unit conversion is inferred. This source change does not certify populated report parity. Login, scope denial, payload parity, and broader tenant scope remain unverified; the owner supplied a cross-lifecycle review audience of liquidity providers, DAO members, guild members, and the wider community, which grants no blanket access. AST direct and helper-query scans identify scope review targets, not tenant isolation; the report query-scope analyzer now pairs SQL predicates with binds on matching location branches and has regressions for mismatched and no-location branches ([evidence](builds/2026-10-21-recovery/cap-066-report-scope-branch-correlation.json)). A mocked four-case contract verifies that the Data Stream summary named-bind SQL exactly matches its parameter map with neither, either, or both optional period bounds; this does not expand the positional-only analyzer or prove populated output parity ([evidence](builds/2026-10-21-recovery/cap-066-named-report-bind-contract.json)). The static AST inventory now also follows the optional condition-list appends and matching mapping writes: 175 positional plus one named direct-query contract are checked with zero mismatches. Dynamic/nested mutations and helper SQL/parameter construction remain unresolved; populated report parity remains open ([evidence](builds/2026-10-21-recovery/cap-066-static-named-report-bind-contract.json)). The helper-closure inventory statically checks two named-bind contracts across report-to-helper query memberships with zero mismatches; it resolves unique unshadowed module SQL constants, bounded optional filter-list appends, literal local wrapper callers, and fail-closed `if/elif` branches that pair literal SQL filters with literal positional containers. The latter resolves the business-model-canvas and SWOT location/organization listing variants with matching one-placeholder/one-value arity. Coverage is now 169/169 static helper SQL memberships, zero unresolved, and 149 positional plus eight named contracts, with zero mismatches. The analyzer resolves the three literal return variants from SWOT’s local `_location_filter` helper and both shared-view SQL branches across five literal callers (ten memberships). It now emits a conditional source signal only for a returned location predicate bound to the caller’s `location_id`; organization and empty-result variants remain separately unscoped. These signals do not establish authorization or tenant isolation ([formatted-wrapper evidence](builds/2026-10-21-recovery/cap-066-formatted-query-wrapper-callers.json); [helper-return evidence](builds/2026-10-21-recovery/cap-066-helper-return-filter-bind-contracts.json); [bind evidence](builds/2026-10-21-recovery/cap-066-helper-named-bind-contracts.json); [literal SQL evidence](builds/2026-10-21-recovery/cap-066-literal-module-sql-constants.json); [optional filter bind evidence](builds/2026-10-21-recovery/cap-066-optional-filter-list-bind-contract.json); [literal wrapper callsite evidence](builds/2026-10-21-recovery/cap-066-local-query-wrapper-callsites.json); [tuple-filter evidence](builds/2026-10-21-recovery/cap-066-helper-tuple-filter-bind-contracts.json)). CI #430 identified stale generated source/query/helper line maps; all three were regenerated and their freshness checks pass without changing report parity conclusions ([refresh evidence](builds/2026-10-17-recovery/ci-430-report-inventory-refresh.json)). [Providers](provider-configuration.md); [console contract](kernel-operations-console.md); legacy CH objects inventoried and encrypted, report parity open: [Inventory](analytics-broker-recovery.md); [report/query source map](reporting-parity-inventory.md); [query-scope scan](report-generator-query-scope-inventory.json); [helper-scope scan](report-generator-helper-scope-inventory.json); [archive metadata](builds/2026-10-13-recovery/reporting-archive-inventory.json); [currency evidence](builds/2026-10-19-recovery/cap-066-funding-currency-dimensions.json); [harvest unit evidence](builds/2026-10-19-recovery/cap-066-harvest-unit-rollups.json); [harvest lifecycle evidence](builds/2026-10-21-recovery/cap-066-farm-harvest-lifecycle.json); [period bounds evidence](builds/2026-10-21-recovery/cap-066-farm-summary-period-bounds.json); [network cockpit scope evidence](builds/2026-10-21-recovery/cap-066-stakeholder-cockpit-network-scope.json); [NOI evidence](builds/2026-10-21-recovery/cap-066-crop-noi-view-disposable.json) The capital-accounting diversion helper now uses a fixed six-bind expense query and the schema’s `expense_date` column, fixing the bounded query’s nonexistent `event_date` reference; source/helper inventory checks pass with 169/169 helper SQL memberships static, zero unresolved, and zero bind mismatches across 149 positional plus eight named contracts ([evidence](builds/2026-10-21-recovery/cap-066-capital-diversion-query-contract.json)). This source check does not establish tenant authorization, populated report parity, or owner acceptance. The value-stream WIP, lead-time, and first-time-through queries now use static parameterized SQL; the helper inventory verifies nine report memberships with zero bind mismatches ([evidence](builds/2026-10-21-recovery/cap-066-value-stream-static-query-contracts.json)). SQL source signals do not prove PostgreSQL execution, tenant authorization, RLS, or populated output parity. The business-plan financial-plan list now uses fixed organization/status SQL with a 3/3 bind contract; empty status remains unfiltered, and the query has no location-scope signal ([evidence](builds/2026-10-21-recovery/cap-066-business-plan-list-query-contract.json)). The shared `services/common/database.py:query` adapter is recorded separately from its unchanged SQL caller sites: four calls across three report types are covered by the direct/helper inventories. The helper inventory now accounts for 169/169 SQL memberships with zero unresolved query sites; this is source analysis, not authorization or runtime acceptance ([evidence](builds/2026-10-21-recovery/cap-066-query-forwarder-callsite-inventory.json)). Every direct report cursor across core, state, operations, wellbeing, ecological, Kokonut public-view, bio-factory, liberation, scaling, and snapshot paths is context-managed or closed on failure; snapshot write failures roll back; 287 synthetic execute/fetch failures plus missing-location cleanup pass ([evidence](builds/2026-10-22-recovery/report-generator-cursor-cleanup.json)). Auto-generation now increments its diagnostic empty count for successfully stored reports whose primary sections are empty; the focused report/unified CLI selection passes 172 tests ([evidence](builds/2026-10-22-recovery/report-auto-empty-summary-count.json)). This resource-lifecycle and CLI-diagnostic work does not close populated output parity or MAN-CAP-066. The 29 October source-only projection batch now names the exact columns for technology-roadmap overview, stakeholder engagement summary, and commitment health; a focused mock regression preserves scope, ordering, and payload. This remains source-contract evidence, not populated report parity or MAN-CAP acceptance ([evidence](builds/2026-10-29-recovery/kernel-strategy-roadmap-engagement-projections.json)). The 29 October continuation also replaces six commons report wildcards and additional stakeholder, grievance, trust, value-stream, and governance wildcards with schema-backed projections. Focused fake-cursor tests preserve scope, order, and output rows; populated-data parity and MAN-CAP acceptance remain open ([evidence](builds/2026-10-29-recovery/kernel-public-projections-and-sdk-contracts.json)).|
| CAP-067 | Kokonut Protocol execution bridge | services/protocol_bridge/execution.py; services/protocol_bridge/connector.py; schemas/postgres/600_protocol_execution_bridge.sql; docs/protocol-bridge.md | MAN-CAP-067: An approved location-linked intent reaches the test network idempotently, finalized matching effect evidence is independently reviewed, and KI never signs or publishes source records | tests/test_protocol_bridge.py; tests/test_protocol_connector.py; tests/test_agent_safety.py | P — migration 600 defines the location crosswalk, immutable request snapshot, distinct-human approval quorum, durable handoff and reviewed reconciliation. The 32-test focused source selection passes with nine database-dependent skips; Ruff and compilation pass. A network-disabled native PostgreSQL 16 replay applies all 591 schemas through migration 600 with zero pending or failed entries and cleanup complete; 21 bridge/connector unit tests pass under linux/arm64 QEMU (aarch64). No candidate or legacy rollout, Gateway authorization surface, live chain adapter, external transaction, or MAN-CAP-067 acceptance is established. |

**16 October 2026 Directus relation-expansion guard (CAP-001 / CAP-047 / CAP-053):** tenant-scoped Directus reads now fail closed when a request includes a non-empty `deep` object, dotted relation paths, nested wildcards, or malformed field selectors. Seven focused authorization tests pass, and the Directus hook extension builds with TypeScript checking. This prevents unreviewed related records from crossing the existing grant-filtered root query at the source hook; it does not establish runtime enforcement in the pinned image, field privacy, or a cross-collection grant model. Directus parity and all MAN-CAP statuses remain open ([source evidence](builds/2026-10-15-recovery/directus-relation-expansion-denial.json); [inventory](directus-parity-inventory.md)).

## Progress snapshot — 13 October 2026

**CAP-047 event-effect slice — 14 October 2026:** cache invalidation handlers
require a valid location UUID and fail closed instead of issuing an all-location
cache invalidation when event scope is absent or malformed. Focused cache,
architecture, and durable event-delivery checks pass (59 tests); Ruff and
syntax checks pass. This does not complete the platform-integrity acceptance
row or provide worker DB isolation; see the source audit in
[`mobile-tenant-rls-callsite-audit.md`](mobile-tenant-rls-callsite-audit.md).

**16 October 2026 signed cache-worker slice (CAP-040 / CAP-047):** all four
registered EventBus cache handlers now have an opt-in signed worker path.
Migrations 415–416 limit invalidation to the matching event, signed location,
and analytics/CRISP/metric cache type. Eighty focused Python tests and eight
network-isolated PostgreSQL 16 checks pass, including replay, forced RLS, retry
idempotency, handler registration, and direct-table denial. The feature remains
off by default; no worker credential or active location grant is provisioned,
migration 416 is applied on the candidate; runtime activation and MAN-CAP status do not change
([evidence](builds/2026-10-16-recovery/cache-invalidation-worker-four-handlers-disposable.json);
[migration 416](../schemas/postgres/416_sensor_harvest_cache_invalidation.sql)).

Current focus: **Phase 7, native public API reads**. CAP-053's tenant preflight
now gates counts on schema completeness; the guard passed against a populated
archived restore, reported 11 missing columns, and skipped lineage counts; its
complete-schema path passed against the empty candidate at migration 385. The candidate has since advanced through migration 386 (377 applied schemas, zero pending), with app health 200 and anonymous farm-activity and review routes returning 401.
See the [incomplete](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-gate.json)
and [complete](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-complete.json)
evidence, and [phase progress](progress.md)
for the implementation ledger and the [runtime record](portability-runtime.md) for
exact deployed images. Seven capabilities have a deployed partial/adjacent integration
(D), six have prepared partial integration (P), and 53 retain their baseline code
with their Kernel access path unassessed (B). **0 of 66 capabilities are certified
for end-to-end Kernel parity.** B does not mean removed, migrated, or working in the
minimal image: optional dependencies and full access paths still require assessment.
D/P describe only the named slice, never completion of the whole capability.

The JavaScript SDK package now compiles with TypeScript 5.8.3 after aligning its
Directus adapter calls with the installed SDK command API and matching Python's
pagination presence/precedence behavior. Its ESM package
preflight includes the license and excludes test output; npm's dry-run lists 27
files. The locked Vitest 5.0.3 toolchain now audits with zero vulnerabilities.
The Python SDK's version 0.1.0 wheel and source archive build and contain the
README, Apache license, typed marker, and 16 `.py` files for the optional,
namespaced generated gRPC package. The wheel and optional gRPC runtime imported
successfully in a temporary environment, including both REST clients and all
10 generated modules; no live request was made.
The TypeScript gRPC package's clean build and npm archive include the five-file
service proto import closure in `dist/proto` and exclude test output. Both
service clients loaded from an extracted archive and closed without RPC calls;
server/client API parity remains unassessed. The separate JavaScript REST SDK
artifact also imported from an extracted tarball; both clients instantiated and
the HTTP guard recorded zero calls. An offline fake-adapter parity slice now
covers the five generated v1 reads and Directus pagination across both SDKs,
including route encoding, headers, response values and error handling. This
slice is now locked by persistent Python and TypeScript tests (6 passing in each
suite), including typed response payloads and stable malformed-response errors.
The fake transports make no network calls. This
offline slice now also aligns Python `create_export()` and JavaScript
`createExport()` inputs, including `target_table`, while preserving the existing
JavaScript `create()` method's payload behavior. Four focused Python tests, 13 JavaScript SDK tests,
and the TypeScript build pass with fake client methods only
([evidence](builds/2026-10-17-recovery/sdk-export-method-parity.json)). This
This slice also aligns specialized list-query filters and option forwarding: the
required filter wins over a conflicting caller filter, and Python preserves
offset and meta just as JavaScript does. Five Python SDK tests, 14 Vitest tests,
Ruff, and the TypeScript build pass with mocked clients
([evidence](builds/2026-10-17-recovery/sdk-convenience-query-parity.json)).
These SDK query helpers do not establish authorization or tenant isolation. This
partial evidence applies to CAP-001, CAP-007, CAP-014 and the adjacent CAP-031
public summary slice; live route/auth, tenant scope and broader SDK parity remain
unassessed. The 6 D / 4 P / 56 B / 0 accepted counts do not change.
The 18 October SDK contract work adds PostGIS geometry, recursive JSONB, enum,
organization, and organization-membership record types to the Python/TypeScript
schema guard. It now checks 33 models and 673 canonical columns, including 36
JSONB shapes, 7 PostGIS shapes, 18 enum fields, and 8 auto-discovered SQL
`CHECK`-literal fields. Membership records are descriptive and do not grant
tenant access. `ExpenseCategory` now exposes the shared finance taxonomy,
including its additive schema version. `CapitalSource` types funding metadata
and status but does not authorize financial actions. `FinancialTransaction`
describes recorded financial facts and does not initiate payments or prove
verification. `ValueFlowEvent` carries verification/attestation references
without performing those actions. `ExcludedValueEvent` records exclusion
context without mutating its linked flow. `CropCostAllocation` describes a
stored allocation without recalculating it or transferring funds.
`MetricDefinition` exposes metric governance metadata and validation cases but
does not execute formulas or verify values. `MetricVersion` describes the
formula/change history row but does not grant direct mutation behavior.
`MetricValue` exposes computed values and human-verification attribution
separately; the type does not treat computation as verification. Forecast
types expose scenario assumptions and stored output/confidence fields without
running the engine or verifying the results. This is source-level SDK typing evidence only; it does not close the broader SDK,
authorization, Directus projection, or tenant-isolation gates
([organization evidence](builds/2026-10-18-recovery/sdk-organization-schema-parity.json);
[membership evidence](builds/2026-10-18-recovery/sdk-organization-member-parity.json);
[expense-category evidence](builds/2026-10-18-recovery/sdk-expense-category-parity.json);
[capital-source evidence](builds/2026-10-18-recovery/sdk-capital-source-parity.json);
[financial-transaction evidence](builds/2026-10-18-recovery/sdk-financial-transaction-parity.json);
[value-flow evidence](builds/2026-10-18-recovery/sdk-value-flow-event-parity.json);
[excluded-value evidence](builds/2026-10-18-recovery/sdk-excluded-value-event-parity.json);
[cost-allocation evidence](builds/2026-10-18-recovery/sdk-crop-cost-allocation-parity.json);
[metric-definition evidence](builds/2026-10-18-recovery/sdk-metric-definition-parity.json);
[metric-version evidence](builds/2026-10-18-recovery/sdk-metric-version-parity.json);
[metric-value evidence](builds/2026-10-18-recovery/sdk-metric-value-parity.json);
[forecast-model evidence](builds/2026-10-18-recovery/sdk-forecast-model-parity.json);
[literal evidence](builds/2026-10-18-recovery/sdk-checked-literal-parity.json);
[auto-discovery evidence](builds/2026-10-18-recovery/sdk-check-literal-autodiscovery.json)).
See the [JavaScript ledger](progress.md#phase-7-javascript-sdk-package-preflight--11-october-2026)
and [Python import ledger](progress.md#phase-7-python-sdk-isolated-wheel-import-check--11-october-2026).

An optional OIDC identity/session adapter and a same-origin principal/report
review page are implemented in source. The queue reads only submitted
`report_snapshot` records under an explicit per-location grant; details remain
read-only. OIDC is disabled pending provider settings and migration 380; login,
CSRF, session revocation, scope denials, and audit behavior are unverified. The
Cloudflare preview remains synthetic-only. This infrastructure slice does not
certify any capability or change the totals. See the
[console contract](kernel-operations-console.md).

The active AMD64 Kernel candidate has a private database and healthy app. Its
rebuilt image matches all 1,294 bundled source hashes in the checkout, and its
schema-only migration plan reports zero pending across 370 applied migrations
through 379. The app liveness endpoint returns 200; its scheduler currently has
zero enabled, disabled or running tasks. No numbered seeds or pilot fixture were
loaded. These are operational checks, not proof of a complete
farm/metric/reviewer/mobile workflow. Legacy remains stopped with volumes
retained. The previous app image is preserved under a rollback tag. The active
candidate app still uses its owner login; the verified read-only analytics login is separate. The opt-in Metabase profile is healthy with credential encryption enabled. It retains the H2 demo separately and adds a read-only PostgreSQL source filtered to the three `kokonut_reporting` views, plus three first-party cards and a dashboard. The candidate is empty, so all cards return zero rows; exact exported card SQL passed independent output parity on a copied populated fixture. All MAN-CAP acceptance gates remain open.

Shared infrastructure changes (provider flags, adapters, requirement groups,
scheduler/events/cache ports, images and migrations) support many rows but do not
certify unchanged domains. Test paths remain candidates, not passing results.
Implementation-time lint, static boundary checks and Docker startup must not be
reported as domain parity. No Python/Solidity/extension acceptance suites were run
in the implementation slices recorded here.

**Update rule:** every subsequent Kernel implementation/deployment slice updates
this column for directly affected IDs and the phase ledger, linking its evidence
and remaining acceptance gates. When acceptance is actually performed, retain its
fixture/provider/image identity and result in the evidence record; only then mark
that capability accepted. Preserve the 66 baseline IDs and their original checks.

## Acceptance evidence record

For each ID, attach fixture identity, provider/profile, source commit, selected tests and their results, manual output comparison, authorization/tenant checks, audit evidence and recovery/rollback result. Preserve domain-specific vocabularies; a report or advisory capability does not acquire verification authority simply because the transport changes.

Candidate test mapping is deliberately conservative: missing guessed names are excluded. Expand mappings using the static service-group test references and the domain registry before changing that capability. CLI/API compatibility and frontend workflows require separate assertions; a Python import reference alone cannot establish them.

## Infrastructure gates

- Migration history/checksums remain intact; additive schema revisions only.
- Database/outbox leases, idempotency, retry limits and operator replay remain durable.
- Public views keep verified farm/record eligibility and consent restrictions.
- Existing SDK/protobuf/CLI contracts remain versioned and compatible.
- A capability can use an optional/offloaded adapter, but its supported access path must be documented and tested.
- Profile and ARM64 certification is a separate release gate after relevant parity checks pass.

## Batch execution — 10 October 2026

[Six-batch checklist](batches.md). **Batch 1 complete:** matching AMD64/ARM64
minimal artifacts now bundle source inventories and the public relation readiness
gate. [Build evidence](builds/2026-10-10-batch1/README.md). Running images are unchanged.
No new capability acceptance gates closed; counts remain 6 D / 4 P / 56 B / 0 accepted.
**Next: Batch 2, baseline data ownership and isolated backup/recovery preparation.**

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

### Batch 2 ClickHouse first-read visibility trace — 10 October 2026

Sanitized query-log evidence confirms inserts and 44 immediate reads targeted
`kokonut_analytics` without exceptions. The reads reported zero rows for five
seconds, followed by a later read containing both synthetic sensor-date rows.
Async inserts and query result cache were disabled; neither explains the delay.
Root cause remains unknown and no visibility SLA is claimed. [Evidence and limits](sensor-entrypoint-recovery.md#first-read-visibility).
Batch 2 remains open; CAP-040 stays P and acceptance counts are unchanged.

### Batch 2 CSV and authenticated HTTP sensor paths — 10 October 2026

FastAPI now resolves its nested request annotations, and HTTP publishes the
`sensor_reading` event atomically with source, health and outbox changes. The
isolated run accepted two CSV and three authenticated HTTP readings, rejected an
invalid timestamp and HMAC, delivered five outbox rows, and matched raw and v3
aggregates. Events are still pending for the enabled anomaly handler; network
listener/proxy and handler-effect acceptance remain open. [Evidence](builds/2026-10-10-recovery/sensor-csv-http.json).
CAP-040 remains P; counts and deployment selection are unchanged.

### Batch 2 local limiter process reset — 11 October 2026

Using the promoted image in one disposable container with networking disabled,
the first Python process exhausted its default local bucket (100 allowed, one
denied); a second Python process selected the local provider and admitted the
same identity again. This verifies local state resets across an OS process
boundary. The candidate gateway/container was not restarted, and no PostgreSQL,
audit, or domain state was touched. [Evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json).
CAP-040 remains P; actual service restart, shared/multi-replica limits and other
listed parity gates remain open.

### Batch 2 candidate gateway restart — 11 October 2026

Exhausted a synthetic credential bucket through the active candidate gateway,
then restarted only its app container in place. The container returned healthy;
the same identity received 200 after restart. PostgreSQL kept its container ID
and start time. Exact audit results were 124 allowed and one `rate_limited`
denial; the 125 synthetic records remain retained. [Evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json).
This accepts local limiter reset for the single candidate app. CAP-040 remains
P; shared PostgreSQL/multi-replica behavior, host/public ingress and the other
listed parity gates remain open.

### Batch 2 PostgreSQL shared limiter consumption — 11 October 2026

On the isolated migration-373 portability database, the shared adapter denied
an over-capacity request, returned a 10-second retry estimate, and gave a
different caller an independent bucket. Two backend instances handled 140
concurrent same-caller checks (121 allowed, 19 denied in 2.193 seconds), within
the refill-aware bound. Synthetic rows were deleted and the table returned to
zero rows; the candidate database was untouched. [Evidence](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json).
This is bounded connection-concurrency evidence only; PostgreSQL outage,
multi-process/multi-replica and gateway 503/audit acceptance remain open.

### Batch 2 gateway limiter update — 11 October 2026

CAP-040 remains P. In addition to local-provider and shared-consumption
checks, a network-disabled source ASGI probe explicitly selected
PostgresRateLimiter, simulated an unreachable database, and confirmed the
gateway returned 503 with Retry-After: 30 while attempting one denied audit
callback in memory. It confirmed no fallback to local state.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-outage.json).
The two-second PostgreSQL row-lock timeout has also been exercised: a synthetic
held lock returned SQLSTATE 55P03 after 2.124 seconds and the temporary bucket
was deleted. [Evidence](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json).
Four OS processes also shared one bucket across 160 direct adapter calls:
114 allowed and 46 denied in 1.653 seconds, within the refill-aware bound; the
synthetic row was deleted. [Evidence](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json).
The real GatewayAudit path was also exercised with PostgreSQL unreachable: it
attempted the write, logged OperationalError, and allowed the gateway's 503
response to complete; no durable denial record was possible.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json).
Four gateway ASGI processes also shared PostgreSQL state across 160 requests:
121 returned 200 and 39 returned 429 with Retry-After, within the refill-aware
bound; the synthetic bucket was removed.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json).
Two private-network API containers also shared the PostgreSQL limiter over
160 HTTP requests: 119 returned 200 and 41 returned 429 with Retry-After; the
refill-aware cap was 126 and the synthetic bucket was removed.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json).
Audit replay after database recovery, production ingress, replica failover/scale,
and candidate provider activation remain open.

### CAP-040 gateway audit journal update — 11 October 2026

The earlier stop/restart observation below characterized the original behavior
and is superseded for current source by the bounded local journal. In the later
real-ASGI recovery probe, a PostgreSQL-outage denial returned 503 with
`Retry-After: 30` and queued one event. After replacing the app container on the
same retained volume, the startup replay worker committed exactly one audit
row, preserved its original timestamp and drained the journal. Duplicate event
IDs remained one row; the configured one-event queue limit rejected a second
event; the SQLite file was mode 0600. [Implementation and recovery evidence](gateway-audit-spool.md).

CAP-040 remains partial. Journal saturation/volume loss, installing a restored
copy into a live Compose volume,
candidate provider activation, replica failover/scale, production ingress, and
the other transport and handler parity gates remain open. A new CLI reports
counts/integrity, checkpoints online to a new private file, and restores only
to a new destination. Process exit around a committed/uncommitted SQLite write,
live-source checkpoint consistency, restore identity, 0600 output permissions,
and overwrite rejection passed in a synthetic fixture.
[Checkpoint evidence](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).
The rebuilt image's unified CLI also passed status and temporary-bind
checkpoint/restore invocation without a database or persistent volume.
[Image evidence](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).
The active candidate still uses the local rate limiter. The isolated synthetic
audit row, temporary app containers and temporary journal volume were removed;
the portability database returned to its prior stopped state. No schema
migration, domain data write or pytest suite ran.
[ASGI replay evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).

### CAP-040 local SQLite contention update — 11 October 2026

The first cold-start probe found three `database is locked` failures among eight
simultaneous writers. WAL/schema initialization now retries transient lock
errors. Three later cold starts each committed all 144 events from 12 processes;
10 warm writers also completed. An online checkpoint captured 166 valid events
while all eight writers were active; the source subsequently reached 481 events.
Temporary synthetic files were removed.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json).

CAP-040 remains partial. This closes only local process-level SQLite contention
and checkpoint consistency; volume/device/host loss, power loss, external alert
delivery, approved retention, live-volume restore, candidate-provider activation
and replica failover/scale remain open.

### CAP-040 audit saturation alert and write guard — 11 October 2026

The queue alert threshold defaults to 80% of its configured cap, with an
absolute-count override exposed by both Compose profiles. Unified CLI status
reports pending count, cap, threshold, alert and restriction state without
event payloads. `/health` reports `audit_capture` as `ok`, `degraded` or
`unavailable`. Before a non-read handler, middleware replays the journal and
checks both capacity and local SQLite writeability; unavailable storage or a
queue at/above threshold returns 503 with `Retry-After: 30` before handler
execution. A storage-path failure, injected `ENOSPC`, a missing journal after
in-process observation, threshold rejection, recovery below threshold, and the
no-event status output passed against private synthetic fixtures. The capacity
probe's temporary record was not retained; no physical disk was filled.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json).

CAP-040 remains partial: in-flight operations can finish if storage fails after
preflight; an empty replacement volume after restart requires external volume
monitoring to distinguish it from first use. Physical-device/power failure,
external alert delivery, production retention ownership, live-volume restore,
candidate activation and replica failover/scale remain open.

### Historical CAP-040 audit recovery boundary — 11 October 2026

The initial isolated PostgreSQL stop/restart probe found that the then-current
GatewayAudit writer dropped outage events while new post-recovery writes
succeeded. That result is retained as baseline evidence, not the current
implementation status. [Historical evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).

### CAP-040 audit admission addendum — 11 October 2026

Mutating gateway requests reserve spool threshold headroom in SQLite until
handler completion and audit capture. Sixteen local worker processes sharing
one journal at 3/4 pending yielded one reservation; a forced worker exit left a
reservation that the next preflight safely reaped. ASGI success/error paths
released only after audit capture; a forked worker used a distinct owner lock,
and an injected release failure was reaped on the next preflight. Multi-host
filesystems, independent replica failover and headroom consumed by read/denial
events remain open.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).

### CAP-040 concurrent event-handler effect — 11 October 2026

On a fresh restored PostgreSQL fixture, four independent workers processed 16
synthetic `metric_computed` events. One real cache handler invalidated the 16
target-location entries, preserved three sentinel entries, and recorded 16
single-attempt successful receipts/logs. This narrows the handler/concurrency gap
for one cache effect; other handler types, same-event retry/crash recovery,
runtime-role policy and provider recovery remain open. CAP-040 stays partial and
the capability counts do not change. [Details](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/event-handler-concurrency.json).

### CAP-040 CRISP cache-handler addendum — 11 October 2026

Four independent operator containers processed 16 synthetic `crisp_scored`
events, with four completed events assigned to each worker. The real allowlisted
CRISP handler invalidated all 16 target `crisp` cache entries, preserved three
sentinel entries, and wrote 16 successful one-attempt delivery receipts/logs;
all leases were released. The helper also reverified the earlier metric run.
The in-flight observer failed on an ambiguous joined `status` column, so this
run has no in-flight snapshot; the earlier metric run retains its own. Same-event
retry/crash, other handler types, production runtime-role policy and provider
recovery remain open. CAP-040 remains partial and counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/crisp-handler-concurrency.json).

### CAP-040 same-event active lease addendum — 11 October 2026

While the real CRISP cache handler was held at a synthetic cache write, worker A
owned the event with one processing delivery attempt. A second real worker
processed no event; PostgreSQL still showed worker A as owner and attempt count
one. After releasing the lock, worker A completed the event once, wrote one
successful receipt/log, invalidated only its target cache row and preserved the
sentinel. This confirms an unexpired active lease excludes another claimant for
the same event. Expired-lease takeover while the original handler remains live,
crash after an external side effect, runtime-role policy and provider recovery
remain open. CAP-040 stays partial and capability counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-claim-exclusion.json).

### CAP-040 same-event timeout and retry addendum — 11 October 2026

One synthetic CRISP event timed out while its cache write was blocked, returned
to pending with one retry, then completed successfully on its second delivery
attempt. The timeout and success logs were both retained; the target cache row
was invalidated and its sentinel remained valid. This verifies timeout retry
for one idempotent cache effect. The handler deadline expired before the
planned second worker started, so this timeout/retry probe did not test stale
lease takeover; the later CAP-040 stale-lease addendum covers that case. Crash
after side effect, other handler types, runtime-role policy and provider
recovery remain open. CAP-040 stays partial and capability counts do not
change. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json).

### CAP-040 same-event expired-lease takeover addendum — 11 October 2026

With worker A's synthetic CRISP cache update blocked, the lease was expired and
worker B reclaimed the same event before A's handler returned. PostgreSQL
observed two blocked handler updates, followed by two successful handler logs.
Worker A lost completion ownership; worker B completed the event and performed
the single target invalidation while the sentinel stayed valid. This confirms
reclaim and duplicate invocation for one idempotent cache effect. It does not
prove safety for other handler types or external side effects; crash-after-effect
recovery, runtime-role policy, stale-worker lease-loss reporting semantics and
provider recovery remain open. Worker A's CLI counted one failure although B
completed the event; whether CLI/metrics should label lease loss separately
remains a follow-up. CAP-040 stays partial and capability counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json).

### CAP-040 stale-worker reporting correction — 11 October 2026

The event bus now returns a separate `lease_lost` count, skips stale-owner retry
updates, and preserves `failed` for handler errors/timeouts. The one-shot CLI
returns success when lease loss is the only outcome; persistent workers back off
instead of immediately polling again. The focused lease-loss regression
function passed by direct invocation, and modified Python files compile; the
host has no pytest installation, so the regular test runner did not execute.
The earlier concurrent takeover evidence remains historical evidence of the old
counter output; it was not rewritten. A live rerun is still useful confirmation.
This reporting fix does not expand handler-effect or exactly-once guarantees;
CAP-040 remains partial. [Implementation details](event-handler-concurrency.md).

### CAP-040 crash after handler side effect addendum — 11 October 2026

A synthetic crash worker exited after the allowlisted CRISP cache handler
committed its effect but before the delivery receipt update. The event remained
processing with a processing receipt at attempt one and no handler log. A
guarded lease expiry enabled the real event CLI to reclaim it. The handler ran
again and completed attempt two; the second cache update changed zero rows. The
target remained invalidated once and the sentinel remained valid. This covers
retry after a lost receipt for one idempotent local cache effect, not exactly-once
effects for other handlers. The fixture database is stopped and its volumes are
retained. CAP-040 remains partial. [Machine evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json).

### CAP-047 registered handler replay-risk inventory — 11 October 2026

Inspected all five effective event registrations and their allowlisted callable
implementations. The metric and CRISP cache handlers have isolated concurrent
and crash/retry evidence. The sensor anomaly handler can write alert/claim rows,
emit another platform event, notify email/Directus and dispatch configured
actuator commands; existing cooldown checks are not per-event idempotency
receipts. The stale-data and threshold handlers share best-effort webhook and
Directus sends without durable notification receipts, so they can duplicate a
successful send or mark delivery successful after a caught send failure. No
endpoint or actuator was contacted. Durable notification/idempotency contracts,
anomaly crash recovery, runtime-role policy and remaining provider recovery
remain open. This source audit closes only the handler-inventory checklist item;
CAP-047 and CAP-040 remain partial and capability counts do not change.
[Details](event-handler-concurrency.md).

### CAP-047 notification outbox implementation — 11 October 2026

Added migration `375_notification_outbox.sql` and a PostgreSQL delivery adapter
for the event-driven webhook/Directus notification paths. The handler uses the
platform event UUID with channel and destination identity so event redelivery
does not create another queue row. Delivery attempts have committed leases,
bounded retry/backoff, stable receiver idempotency headers, dead-letter state,
and actor/reason audit for replay or disposal. The event worker now dispatches
the queue; provider-disabled rows remain unclaimed. URLs and credentials stay
in worker environment variables. Source compilation and whitespace checks pass.
The migration was applied twice in a fresh internal-only scratch DB. All nine
fake-transport checks passed, including stable source event-id propagation through
the handler, duplicate-handler enqueue suppression, provider pause, retry/backoff,
crash-after-send reclaim with the same idempotency key, CLI help, and operator
replay/disposal audit. Six fake requests were recorded; no real endpoint was
contacted. The candidate and legacy DBs were not migrated. [Implementation report](event-handler-concurrency.md); [machine evidence](builds/2026-10-11-recovery/notification-outbox-check.json).
Real provider acceptance, outbox retention/capacity, recovery coverage for other
event-handler paths and broader CAP-040 acceptance remain partial; capability
counts do not change.

### CAP-047 notification outbox capacity reporting — 11 October 2026

The read-only notification stats command now includes total/open row counts,
oldest open age, and combined table/index bytes for queue, attempt, and operator
audit relations. Default advisory thresholds are 256 MiB warning and 512 MiB
critical, configurable in Compose or the worker environment. Thresholds do not
block enqueue/delivery and the implementation does not prune rows. The interim
retention rule keeps all rows and evidence until an owner approves temporal
retention and archive semantics; active and undisposed work is never eligible
for deletion. The capacity query and critical-state calculation passed in an
isolated rerun. This closes capacity visibility only; provider acceptance,
retention-period approval and broader recovery remain open. The scoped sensor
anomaly event-worker recovery now has separate evidence below. [Policy](notification-outbox-operations.md); [machine evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json).

### CAP-047 dynamic retention and legal-hold source contract — 15 October 2026

The owner selected runtime-configurable retention windows and legal-hold rules;
no durations are embedded. Migration 401 adds nullable policy windows, draft
and approved states, and an append-only audited record-hold ledger. Event
cleanup now requires one approved active global event policy, checks active
holds and incomplete delivery/disposition state, and remains disabled by
default. Generic cleanup also requires an explicit approval and feature gate.
The candidate has now applied migrations 401 and 402 after a fresh checkpoint and isolated restore rehearsal. No policy is configured. Ninety-four
focused source/unit tests and four subtests
pass, including the legal-hold skip path. Ordered migration 401 and synthetic
PostgreSQL assertions verify policy demotion, audited immutable holds, and
hold-aware generic/event cleanup; acceptance corrected an undersized action
column. Those earlier isolated checks did not access the candidate or legacy database. The later candidate schema rollout changed no policy rows; no MAN-CAP status or count changes. Pruning remains disabled until approved policy data and accountable operators are in place ([migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql);
[database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json);
[source evidence](builds/2026-10-15-recovery/retention-policy-source-checks.json);
[operations](retention-policy-operations.md)).

The general EventBus cleanup path now rejects nonpositive retention windows
and preserves an aged parent event while its dead-letter disposition remains
pending. Sixteen focused durability tests pass. This avoids orphaning an
operator-actionable dead letter; it does not change notification-outbox pruning
(none is implemented) or close owner-approved retention periods. [Evidence](builds/2026-10-14-recovery/event-cleanup-pending-disposition.json).

**15 October 2026 retention scope metadata (CAP-047):** migration 402 adds
optional owner-defined jurisdiction and purpose codes with no defaults or
legal interpretation. Approval cannot enable auto-enforcement for unresolved
scope; the generic sweeper skips scoped policies, rejects overlapping active
scopes, and event cleanup refuses ambiguous global policy state. Sixty-two
focused data-governance/EventBus tests and four subtests pass. The ordered
migration acceptance for 401 and 402 passes on an internal-only synthetic
PostgreSQL fixture. The candidate now has both migrations applied after a fresh
restore-rehearsed checkpoint; no periods, scoped policies, or holds are active,
and named MAN-CAP checks remain unaccepted. The generic sweeper now explicitly
skips the notification outbox, attempts, and operator audit until an
archive/idempotency workflow exists; dry runs do not mark policies as enforced
([source evidence](builds/2026-10-16-recovery/retention-notification-sweeper-guard.json)).
Retention enforcement also rejects missing, oversized, or non-string actors and
non-boolean dry-run modes before opening PostgreSQL. This source guard does not
enable pruning or change capability status
([migration](../../schemas/postgres/402_retention_policy_scope_codes.sql);
[operations](retention-policy-operations.md);
[evidence](builds/2026-10-15-recovery/retention-policy-disposable.json);
[candidate rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json)).

The same pre-database validation now applies to policy creation, approval,
retirement, and legal-hold placement/release. Actor values are trimmed and
bounded to the persisted 200-character columns; blank or non-string reasons
are rejected before a cursor opens. Fifty-two focused tests and 49 subcases pass;
retention periods remain unconfigured and MAN-CAP acceptance is unchanged
([evidence](builds/2026-10-16-recovery/retention-audit-input-validation.json)).

### CAP-047 sensor anomaly crash/replay — 11 October 2026

Migration `376_sensor_anomaly_delivery.sql` adds per-reading/rule effect receipts,
enables the email outbox channel, and permits the existing `requires_approval`
actuation state. The event handler now evaluates only the reading referenced by
its source event; its alert, optional draft claim, ingestion log, webhook/Directus/
email intents keyed to the actual downstream event ID, actuator approval record,
and downstream `sensor_alert` event share the database transaction. In an
internal-only synthetic fixture, the actual EventBus worker exited with code 86
after handler commit and before receipt acknowledgement. A replacement worker
reclaimed the expired source-event lease and completed attempt two; the event
receipt moved from `processing` to `success` with one success log. The retry
preserved one alert, draft claim, effect receipt, three notification intents,
downstream event, ingestion log, and critical actuation record. Critical work
remained unapproved with `human_approval_required=true`. Email formatting used a
fake SMTP transport; no provider endpoint or actuator was contacted. Migration
376 was re-applied twice successfully. The fixture used only the relevant schema
set, no ports or egress, and its volume was retained after shutdown. [Details](sensor-anomaly-delivery.md);
[machine evidence](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json).

This closes one scoped sensor anomaly event-worker crash/retry check. Provider
acceptance, operator approval policy, retention ownership, recovery coverage for
additional handlers/runtime conditions and broader CAP-040 acceptance remain
open. CAP-047 and Batch 2 remain partial; capability counts do not change.

### Batch 2 PostgreSQL runtime-role boundary — 11 October 2026

Added an opt-in bootstrap for a distinct, non-owner application role. The role
has no superuser, role/database creation, replication, RLS bypass, or inherited
membership privileges; it can connect only to its configured database, use the
public schema, and perform table DML plus sequence access. Persistent DDL,
`CREATE ROLE`, `CREATE DATABASE`, admin-role switching, and connections to
unrelated databases were denied in an internal-only synthetic PostgreSQL
fixture. Provisioning passed twice, including default grants for a table created
after provisioning. The scratch container is stopped and its volume retained;
the running candidate and legacy database were not modified. [Policy](runtime-role-policy.md);
[machine evidence](builds/2026-10-11-recovery/runtime-role-isolation.json).

This validates the role primitive on a populated restore as well. A fresh copy
of the populated legacy archive accepted the opt-in role twice. The native
`public_locations()` query returned two governed public rows, a PostGIS function
returned SRID 4326, and an admin-created synthetic table supported runtime DML
and sequence use. Persistent DDL, role/database creation, admin-role switching,
and connections to the other two databases were denied. The public query emitted
only a count, and no restored domain rows were changed. [Populated-restore evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json).

The candidate still uses its owner-backed credential. Legacy Directus and
Metabase still use the `kokonut` superuser in the legacy Compose file and are not
included in the candidate runtime-role overlay; separate service roles and
grants remain open. Full domain workflow acceptance is also open. No capability
count changes; Batch 2 remains partial.

### CAP-007 candidate analytics-source ACL review — 11 October 2026

Before migrations 371–379, the candidate was reviewed in a read-only
database session. `kokonut` was its only login/superuser role; no runtime,
analytics-source, or Metabase metadata role existed, and migration 377's
reporting schema/views were absent. `PUBLIC` could connect to the application
database and create temporary objects. No roles, grants, schemas, source, or
data were changed by that review. Migrations 371–379 have since been applied;
the reporting views and the verified `kokonut_analytics_ro` login now exist.
The candidate-only Metabase metadata database/login are also provisioned, with
real-login metadata CREATE success and application-database denial. Metabase
is healthy under the explicit profile with saved-credential encryption enabled;
the default manifest still lists only `database` and `app`, and PostgreSQL has
no host port. It retains the built-in H2 demo with 39 generic cards and one dashboard, plus
a separate read-only PostgreSQL source filtered to the three approved
`kokonut_reporting` views and three Kokonut cards in a dedicated dashboard.
The Metabase card SQL now passes populated output parity on an isolated copy;
the active candidate remains empty and CAP-007 acceptance remains open. [Card
parity evidence](builds/2026-10-11-recovery/metabase-card-output-parity.json);
[ACL evidence](builds/2026-10-11-recovery/candidate-reporting-acl-review.json);
[migration evidence](builds/2026-10-11-recovery/candidate-migration-apply.json);
[analytics role evidence](builds/2026-10-11-recovery/candidate-analytics-role.json);
[profile evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json);
[profile contract](metabase-kernel-profile.md).

The encrypted metadata backup also passes a full restore in a matching,
network-disabled disposable PostGIS 16 target. Source/card/dashboard/user counts
and all dashboard placements match the live candidate; 14 H2 virtual tiles
remain alongside 25 saved-card placements. The target was removed and live
metadata was unchanged. Card-output parity also passed on an isolated populated
copy. [Restore
manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json).

### CAP-053 source-audit update — 13 October 2026

The repository-owned Field Collector consumer audit found and fixed an
unguarded farm-activity timestamp lookup in
`services/analytics/process_interfaces.py`. Other repository-owned report,
export, metric, analytics, process-trace, Gateway, hook, and seeded dashboard
consumers use the shared eligibility predicate. This source-only update does
not close CAP-053: external/operator-edited dashboard parity, populated output
validation, real OIDC, browser offline/withdrawal acceptance, disposition,
retention, and RLS remain open. Migration 389 adds source-level tenant-aware
grant checks to the database write triggers. The actual 387–389 migrations,
388–389 replay, CLI membership/share lifecycle, and legacy-grant conversion
passed in disposable PostgreSQL. The subsequent clean full-schema replay
applied all 380 ordered migrations with zero pending or failed and registered
all 11 relevant 384–385–389 activity/workflow triggers; candidate rollout and
populated/archive replay remain open
([replay evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
See the [consumer audit](field-collector-downstream-source-audit.md).

### CAP-053 aggregate operator preflight — 13 October 2026

The ownership preflight now reports database-wide counts of enabled and
disabled operator identities and active organization memberships, plus
location-scoped active grants split into legacy, tenant-qualified, currently
authorized, and invalid counts. It evaluates tenant-qualified grants with the
shared `operator_scope_grant_allows` predicate and returns aggregate counts
without operator identity attributes or raw IDs. Five focused checks and Ruff
passed; actual migrations 388 and 391 passed on a schema-targeted disposable
PostgreSQL fixture with exact synthetic counts and verified zero-row cleanup
([evidence](builds/2026-10-13-recovery/tenant-preflight-operator-access-disposable.json)).
This helps quantify the operator affiliation migration but does not map real
operators to organizations or convert legacy grants. CAP-053 remains partial;
worker integration, direct-database isolation, populated production lineage,
retention/disposition, and RLS remain open.

**16 October 2026 tenant-preflight identity boundary (CAP-053 / CAP-047):**
the CLI now requires a separately supplied `KOKONUT_TENANT_PREFLIGHT_DSN`,
pins `search_path` and read-only repeatable-read execution, and refuses to run
inventory SQL unless the session is a direct `kokonut_tenant_preflight` login
with no role memberships, public-table DML/ownership, or database/schema
object-creation rights.
The sanitized report shows the dedicated identity's privilege flags and
checks the configured application role independently. Focused identity,
DSN-error-sanitization, inventory short-circuit, and existing aggregate tests
pass ([source evidence](builds/2026-10-16-recovery/tenant-preflight-identity-source.json)).
A separate PostgreSQL 16 fixture passed with a synthetic RLS-enabled inventory
relation, confirming that the read-only role's `BYPASSRLS` setting must match
the inventory's RLS state ([database evidence](builds/2026-10-16-recovery/tenant-preflight-identity-postgres.json)).
Role provisioning, secret storage, operator authorization, and cross-tenant
read-scope approval remain open. No candidate or legacy database was accessed;
this change does not enable RLS or certify MAN-CAP.

**14 October 2026 signed OIDC operator tenant context (CAP-053):** migration
394 makes PostgreSQL validate the active session, enabled identity,
tenant-qualified grant, active operator membership, and current location owner
or unexpired share before signing context for the current backend/transaction.
Additional scopes must resolve to the same tenant. The shared context accessor
verifies the signature; diagnostic GUC values and tampered payloads do not
grant rows. Disposable PostgreSQL 16 replay and forced-RLS acceptance passed
owner/shared access, denials, context cleanup, share revocation, and concurrent
grant-revocation locking. Twenty focused tenant/OIDC tests passed (one skipped);
Ruff and Python compilation passed. This does not complete CAP-053 or enable
RLS: migration 395 now removes session-table access from the general runtime
role and gives OIDC a separate bounded auth connection. Its isolated forced-RLS
acceptance verifies read/write/mint denial for the runtime role and bounded
session lifecycle for auth ([evidence](builds/2026-10-14-recovery/operator-session-role-disposable.json)).
Gateway API-key context, workers, Directus/views, broad runtime DML on other
public tables, and candidate rollout remain open. Candidate stays at
migration 391 under OFU-18.

**14 October 2026 runtime mobile credential grants (CAP-053):** the app runtime
now receives an explicit column allowlist on `mobile_device` and
`mobile_device_enrollment`. It cannot read device-token, push, or enrollment
hashes, use `SELECT *` across those tables, insert/delete devices, delete
enrollments, or edit enrollment hashes. Safe handler SQL for device reads,
enrollment issue/revoke and last-seen updates passed in a network-isolated
PostgreSQL 16 role check. The runtime login also called the
bounded token resolver and one-time enrollment redemption successfully. The
  focused mobile/auth/migration set passed 148 tests; Ruff and 507-source
migration validation passed. This check did not run the HTTP handlers through
the runtime login and does not close DML on other public tables,
database-verified Gateway capabilities, workers, Directus/views,
candidate rollout, or RLS ([policy](runtime-role-policy.md); [evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json)).

**14 October 2026 bounded device revocation (CAP-053):** migration 398 moves
status/token mutation behind a fixed database function that revalidates the
exact API-key, capability, or OIDC-session scope under forced RLS. Runtime
direct UPDATE is limited to telemetry columns. Migration 399 and the bootstrap
restore narrow security-schema/function access after a DB-only restore. The
exact pre-398 checkpoint restored, migrations 398–399 replayed, and synthetic
forced-RLS checks passed owner success, cross-tenant hiding, denial, token
clearing, and transaction cleanup. At that rollout the candidate had 390 applied schemas
through 399 and health 200, while application RLS remained disabled. It still
runs as the `kokonut` superuser because runtime credentials are not provisioned;
authenticated HTTP under the dedicated role remains open. This does not accept
CAP-053 or any MAN-CAP check ([evidence](builds/2026-10-14-recovery/candidate-migration-398-399-device-revocation.json)).

**14 October 2026 database-only restore owner repair (CAP-053 implementation
follow-up):** migration 400 recreates six bounded NOLOGIN function-owner roles,
restores their exact grants and SECURITY DEFINER ownership, and restores
runtime/operator-auth security-schema lookup after a database-only restore.
The runtime bootstrap now fails closed on unexpected function ownership. A
restored pre-398 clone replayed migrations 398–400; a separate synthetic
owner/ACL-loss fixture passed forced-RLS revocation and operator-auth checks.
The populated-clone bootstrap did not complete, so full restore acceptance is
still open. The local candidate has 391 schemas through 400, health 200, and no
application-table RLS; it still uses the `kokonut` superuser. No MAN-CAP check
is accepted ([evidence](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json)).

### CAP-040/047 worker source inspection addendum — 14 October 2026

The worker review now has a deterministic static import closure over all 12
scheduled modules and five allowlisted event-handler modules, plus a direct SQL
call-site inventory and direct-call graph for the 69 local source files. The
call graph follows 31 entry functions through 281 function memberships and 413
statically resolved call edges across 17 operations; dynamic dispatch,
callbacks and external effects remain open. The SQL inventory records
196 execution sites: 166 literal statement fingerprints, 30 composed or
variable statements, and three unknown statement kinds. The scanner infers
fixed local query prefixes and savepoint-control statements; the remaining
unknowns are generic adapter calls that accept SQL from their callers. The
output omits SQL text and values; regex-derived relation names are review hints
only. This adds source navigation and identifies the remaining function-level effect targets;
the 30 dynamic sites have source-pattern review, and a source regression traces
the generic wrappers currently used by the worker closure. It does not
establish full function reachability, complete effects, worker identity,
grants, or tenant isolation. CAP-040 and CAP-047 remain partial and capability
counts do not change ([source closure](worker-source-closure.json); [SQL inventory](worker-sql-inventory.json); [evidence](builds/2026-10-14-recovery/worker-sql-inventory-check.json)).

### CAP-040/047 worker effect source index — 15 October 2026

A deterministic inventory now scans the current worker function graph for
high-confidence direct effect calls. It records 43 unique source locations
across HTTP, email delivery, process lifecycle, EVM RPC/client setup,
filesystem, and dynamic import boundaries (49 operation/site memberships)
across 20 roots.
The graph overapproximates mutually exclusive CLI branches and can miss
provider callbacks; it does not establish runtime behavior, authorization,
replay safety, or tenant context. The graph follows the EventBus process target
to its local resolver; the callback trace records the validator, dynamic
import, and five allowlisted handlers, but does not verify persisted dispatch
configuration.
Worker identity, role/context, and live recovery gates remain open, so no
MAN-CAP status or count changes ([inventory](worker-effect-inventory.json);
[worker map](worker-operation-map.md)).

### CAP-040/047 worker tenant-context design — 16 October 2026

The worker boundary now has an implementation contract: a database-verified
`system_worker` principal receives exact location/resource/action grants;
global lease and event-queue coordination stays in a separate control-plane
boundary; and the allowlisted sensor-reading handler is the first tenant
execution target. No migration, worker identity, source integration, candidate
change, or RLS policy was added. Runtime worker isolation and all named
MAN-CAP checks remain open; capability statuses and acceptance counts do not
change ([contract](worker-tenant-context-contract.md); [operation map](worker-operation-map.md)).

The worker database factory now requires a named per-worker DSN, verifies the
database login, and rejects autocommit; its sibling credential resolver reads
only the matching worker-specific secret and enforces a 32–4096-byte boundary.
Twenty-one focused unit checks cover the factory and resolver, with Ruff,
compilation, and migration-source validation passing
([evidence](builds/2026-10-16-recovery/worker-credential-resolver-unit.json)).
No real worker secret is provisioned or delivered, and the handler still uses
the shared runtime path. The EventBus now launches handlers through a child
process environment that strips worker-specific DSNs and credentials before
exec; 26 mocked EventBus/runner checks cover environment filtering, request
transport, compatibility, failure handling, and timeout cleanup
([evidence](builds/2026-10-16-recovery/event-handler-child-environment.json)).
The same filter now covers scheduled/manual tasks, known jobs and flow
commands, report generation, migration execution, and SOPS. The supervisor
strips worker secrets from the API child and limits scheduler/event-bus children
to their named worker-key prefixes. Ruff and compilation pass; the EventBus,
scheduler, supervisor, job, migration, SOPS, and environment-policy suites pass
183 focused checks ([evidence](builds/2026-10-16-recovery/worker-subprocess-environment-unit.json)).
No dedicated worker secret is provisioned or used.
This does not deliver an identity-specific secret or establish runtime worker
identity, bounded source/effect integration, direct-database isolation, or RLS
readiness. CAP-040/047 statuses and MAN-CAP acceptance counts remain unchanged.

The first source step now requires the sensor-reading handler to receive a
canonical location UUID and match the source reading to that location before
processing. This prevents a mismatched event payload from selecting a reading
in another location; it does not establish a signed worker identity or tenant
context. Six focused anomaly-handler cases cover missing/malformed location,
canonicalization, validation before DB access, mismatched source location, and
valid matching input. No MAN-CAP acceptance or status changed
([source](../../services/ingestion/anomaly_detector.py); [contract](worker-tenant-context-contract.md); [tests](../../tests/test_anomaly_detector.py)).

CI #342 exposed seed writes that conflicted with migration 404's farm-activity
guard. The pilot seed now inserts lineage with each row, and the Adelphi
alignment seed no longer issues a blanket farm-activity update. Two focused
seed-contract checks pass; the combined focused run passes 16 tests. Hosted CI
must be rerun on the pushed fix before the release gate can close
([evidence](builds/2026-10-16-recovery/ci-342-pilot-seed-guard-fix.json)).

### CAP-047 scheduler template preflight — 15 October 2026

A source-only comparison covers all 15 shared JobSpecs. Thirteen default
argument lists satisfy the current Kernel command contracts; sensor and
climate defaults are rejected for missing source/location inputs. Remote
sensing is optional and runs one due job at a time, with a validated batch
limit of 1–10 (the JobSpec defaults to one). ClickHouse projection remains
limited to one bounded `--run-once` batch; manual list, replay, disposal, and
reconcile actions are rejected. No task or provider was activated. This does
not inspect persisted tasks, Prefect state, provider outcomes, or grant boundaries, so it is inventory
progress and not scheduler acceptance ([JobSpec inventory](worker-job-contract-inventory.json);
[projection evidence](builds/2026-10-15-recovery/projection-job-contract.json);
[remote-sensing evidence](builds/2026-10-15-recovery/remote-sensing-job-contract.json)).

### CAP-047 authenticated backup object transport — 15 October 2026

Local encrypted checkpoint manifests are now authenticated with a
PBKDF2-derived HMAC. The optional S3/R2 transport stages objects under a unique
prefix, verifies remote bytes, and uses a conditional create-only manifest as
the completion marker. Downloads verify the authenticated manifest and
artifact hashes into a new private directory. Twenty-eight focused tests use
fake Compose and object-store adapters; no R2 credentials or objects were
accessed, and no remote delete or lifecycle action is implemented. This is
recovery tooling evidence only; provider backup/restore and MAN-CAP-047 remain
open ([contract](backup-object-storage.md); [tests](../../tests/test_backup_remote.py); [offline evidence](builds/2026-10-15-recovery/backup-object-transport-offline.json)).

### CAP-001/047 operator report-review tenant-context regression — 15 October 2026

Five direct service tests now verify that the report queue and detail readers
establish operator tenant context on the same connection before their scoped
queries, retain location-qualified grant rechecks, stop before querying when
tenant context is denied, and roll back/close on denial or oversized payload.
These use synthetic connections and do not execute PostgreSQL's signed context
functions. Live identity/database-role behavior, populated report parity,
application RLS, and all named MAN-CAP acceptances remain open; capability
status and counts do not change
([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)).

### CAP-001/047 registered report source map — 15 October 2026

The source inventory links all 94 registered report types to their defining
callable, source line, and declared inputs across 15 modules. All declare a
`location_id` parameter and 93 declare a period boundary, but this does not
prove those values constrain every query or that output measures match domain
expectations. The AST-only inventory and freshness checks pass without
executing report code. Populated output parity and owner selection remain open;
capability status and counts do not change
([inventory](report-generator-source-inventory.json); [evidence](builds/2026-10-15-recovery/report-generator-source-inventory.json)).

### Phase 8 optional ARM64 service/profile coverage — 16 October 2026

The profile planner and explicit Compose overlays now cover HTTP sensors,
Directus, and ClickHouse analytics on ARM64 in addition to the previously
verified core, proxy, OIDC/ZITADEL, gRPC, and MQTT selections. A ClickHouse-
enabled Kernel image built under QEMU and passed a no-network ARM64 import of
`clickhouse-connect`; the pinned ClickHouse image reports version 25.8.28.1.
The pinned Directus image's Node runtime reports `arm64` and version 22.23.1.
All selected services in the affected Compose configurations resolve to
`linux/arm64`, and 27 focused planner/Compose tests pass. This verifies code and
image compatibility only. No live ClickHouse profile, projection parity,
Directus bootstrap/hooks/authorization, or physical Raspberry Pi behavior was
tested; capability row statuses and MAN-CAP acceptance counts are unchanged
([evidence](builds/2026-10-16-recovery/kernel-arm64-optional-profiles.json)).

### CAP-040/047 bounded anomaly receipt functions — 16 October 2026

Migration 407 adds signed-location reservation and outcome functions behind a
dedicated non-login owner. Disposable PostgreSQL 16 acceptance passed nine
checks, including event/source/device/rule matching, replay suppression,
outcome and alert-link validation, runtime/auth separation, and no direct
worker table access. The functions are not wired into the handler and no worker
login, candidate rollout, or RLS policy is enabled; no MAN-CAP row is accepted
([migration](../schemas/postgres/407_sensor_anomaly_effect_functions.sql);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-effect-functions-disposable.json)).

### CAP-040/047 bounded sensor-alert event publication — 16 October 2026

Migration 408 adds a canonical event publisher behind a separate non-login
owner. It requires the signed source location and an `alert_created` receipt,
derives the event payload and critical priority from the alert, and inserts the
same pending event shape used by the current handler. Identical retries are
accepted without modifying queue state; conflicting IDs fail closed. Eleven
disposable PostgreSQL 16 checks pass, including ACL and replay checks. The
handler still uses the direct EventBus path; no worker login, candidate
rollout, RLS, or MAN-CAP acceptance is claimed
([migration](../schemas/postgres/408_sensor_alert_event_function.sql);
[evidence](builds/2026-10-16-recovery/sensor-alert-event-function-disposable.json)).

### CAP-040/047 bounded sensor-alert notification intent — 16 October 2026

Migration 409 adds a separate non-login enqueue function for the webhook,
Directus, and email contracts used by the existing notification adapter. The
function requires the signed location, matching sensor-reading receipt and
published alert event, a fixed primary destination, and an allowlisted,
bounded payload. It inserts only a pending outbox intent; exact retries are
no-ops and conflicts fail closed. Twelve disposable PostgreSQL 16 checks pass,
including delivery-state preservation, role boundaries, direct table denial,
and migration replay. The handler is not wired to this function; notification
delivery remains separately owned and no MAN-CAP acceptance is claimed
([migration](../schemas/postgres/409_sensor_alert_notification_intent.sql);
[evidence](builds/2026-10-16-recovery/sensor-alert-notification-intent-disposable.json)).

### CAP-040/047 bounded sensor-alert actuation intent — 16 October 2026

Migration 410 now contains a separate non-login function owner and
`create_sensor_alert_actuation_intent`. The function source validates signed
location, source-event/reading/receipt lineage, the linked alert, its recorded
`sensor_alert` event, and the currently enabled actuator rule. It derives the
command from that rule, requires human approval for critical alerts, and uses a
partial unique key to return the existing intent on retries without resetting
approval or transport state. Sixteen focused disposable PostgreSQL 16 checks
pass for lineage, approval behavior, retry preservation, role boundaries,
direct table denial, and migration replay. No handler integration, worker
credential, candidate rollout, RLS, or MAN-CAP acceptance is claimed
([migration](../schemas/postgres/410_sensor_alert_actuation_intent.sql);
[evidence](builds/2026-10-16-recovery/sensor-alert-actuation-intent-disposable.json)).

### CAP-040/047 bounded sensor-alert draft claim — 16 October 2026

Migration 411 adds `create_sensor_alert_draft_claim` behind a separate
non-login owner. It validates the signed reading event, anomaly receipt,
location, device, rule, and linked alert, then inserts only a `draft` MRV claim
or adopts the exact legacy claim already linked to that alert. Its stable key
uses the source-reading event plus alert. The handler can invoke it after the
`alert_created` receipt and before building notification intent data; the
alert-event publisher remains separate and its payload omits `claim_id`.
The worker receives function EXECUTE only; it has no direct MRV-claim or
sensor-alert access. Fourteen focused disposable PostgreSQL 16 checks pass for
scope and source linkage, draft creation, lifecycle-preserving retries and
legacy adoption, role boundaries, direct table denial, and replay. This is not
a newly accepted capability and no MAN-CAP row is closed
([migration](../schemas/postgres/411_sensor_alert_draft_claim_intent.sql);
[evidence](builds/2026-10-16-recovery/sensor-alert-draft-claim-disposable.json)).

### CAP-040/047 bounded sensor-anomaly reads — 16 October 2026

Migration 412 adds read-only sensor-anomaly operations behind a dedicated
no-login function owner. Source reads and rule evaluation require the signed
`sensor_reading/process` scope and match the event type, source table and ID,
payload location, and sensor selectors to the reading and device. Rule listing
is limited to enabled rules for the scoped device's sensor type. Value,
rate-of-change, gap, minimum, maximum, and cooldown reads are bounded to the
same device and location; metric evaluation also receives and validates the
source event. The worker has no direct read privileges on event, sensor, rule,
location, or alert tables. Explicit owner policies allow bounded functions to
operate when a source table is forced under RLS. Ten disposable PostgreSQL 16
checks pass for replay, unsigned and mismatched-scope denial, synthetic metric
results, cooldown behavior, forced-RLS reads, and role/column boundaries.
These functions are dormant: the anomaly handler does not yet use a dedicated
worker identity, migration 412 is applied on the candidate, and RLS is not
enabled globally. This is implementation evidence only; no MAN-CAP row changes
status ([migration](../schemas/postgres/412_sensor_anomaly_worker_reads.sql);
[runner](../scripts/check-sensor-anomaly-worker-reads-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-reads-disposable.json)).

### CAP-040/047 bounded sensor-anomaly alert write — 16 October 2026

Migration 413 adds a bounded `SECURITY DEFINER` function to create one
source-derived, location-bound alert and its append-only ingestion audit entry
for a signed worker scope and reserved anomaly receipt. The function advances
that receipt only after both writes succeed. Nine disposable PostgreSQL 16
checks pass for replay, source/rule/scope denial, required receipt, duplicate
suppression, forced-RLS execution, direct table denial, role separation, and
atomic rollback when audit insertion fails. No candidate or legacy database
was accessed. The function is dormant, the handler has not been integrated
with a dedicated worker identity, and no MAN-CAP status changes
([migration](../schemas/postgres/413_sensor_anomaly_alert_write.sql);
[runner](../scripts/check-sensor-anomaly-alert-write-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-alert-write-disposable.json)).

### CAP-040/047 signed sensor-anomaly worker integration — 16 October 2026

`handle_sensor_reading` now uses the worker-only database and credential
resolvers, sets transaction-bound `sensor_reading/process` context, and calls
the bounded read, receipt, alert/audit, draft-claim, event, notification, and
approval-intent functions on one connection. EventBus child-process secret
routing is allowlisted for this exact handler. Migration 414 adds canonical
notification context to published alert events, a signed boolean-only check
for configured actuation, and no-login function-owner policies needed when
source tables already enforce RLS. Forty-five focused anomaly/EventBus tests
and eight disposable PostgreSQL 16 end-to-end checks pass, including EventBus
child-process crash recovery with idempotent attempt-two completion. The worker login,
credential and location grant are not provisioned; migration 414 is not on the
candidate, global RLS is not enabled, and live EventBus recovery, provider
delivery and human actuation acceptance remain open. This implementation does
not change MAN-CAP status ([adapter](../services/ingestion/sensor_anomaly_worker.py);
[migration](../schemas/postgres/414_sensor_anomaly_worker_delivery.sql);
[runner](../scripts/check-sensor-anomaly-worker-delivery-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json)).

### CAP-040/047 worker SQL inventory reconciliation — 17 October 2026

The current static inventories cover 29 operation roots, 89 source files, and
313 SQL execution sites. The call graph links 240 unique sites across 307
operation/site memberships and leaves 73 without a static function match.
Source-pattern review covers all 43 composed/variable SQL sites, including the
signed-context cleanup, anomaly worker query wrappers, the fixed NOI
location-filter fragment, and the new bounded sensor worker calls. The weather,
forecast, and sensor worker roots add only literal SQL. The inventory refresh
itself only changed static reports; it did not alter database ACLs or RLS.
Migrations 426, 427, and 429–431's function-owner grants and policies are
documented below. No worker credential was provisioned or candidate rollout
performed, and no MAN-CAP status changed ([source map](worker-operation-map.md);
[SQL inventory](worker-sql-inventory.json);
[reachability](worker-sql-reachability.json);
[refresh evidence](builds/2026-10-16-recovery/runtime-sql-inventory-refresh-latest.json)).

### CAP-040/047 signed weather-forecast worker — 16 October 2026

Native scheduled five-day forecast ingestion now uses a dedicated worker
module, exact scheduler secret routing, and a default-off feature gate. The
child receives only its named DSN/credential pair and the shared PostgreSQL
login settings are stripped. Migration 426 provides signed location lookup
and bounded batch storage; the forecast natural-key upsert, ingestion audit,
and ClickHouse outbox intent commit atomically. A mismatch between the signed
location and requested or row scope is rejected. The no-login function owner
has only required column grants and function-owner-only RLS policies; the
disposable fixture forces RLS on location, forecast, audit, and outbox tables.
The 203 focused forecast, scheduler, worker-boundary, and operation-map checks pass;
Ruff is clean, and nine disposable
PostgreSQL 16 checks pass for replay, RLS, idempotency, scope denial, audit,
context cleanup, and direct-table/function ACLs. No provider, candidate or
legacy database, or persisted schedule was accessed. Migration 426 is applied on the candidate; worker
credentials/grant are not provisioned and the feature remains off, and legacy
persisted forecast tasks remain on the previous shared-identity module until
schedule owners reconcile them. No MAN-CAP check is accepted; broader provider
parity, live schedule state, application-wide RLS, and recovery acceptance
remain open ([worker](../services/ingestion/weather_forecast_worker.py);
[migration](../schemas/postgres/426_signed_weather_forecast_worker.sql);
[runner](../scripts/check-weather-forecast-worker-disposable.py);
[evidence](builds/2026-10-16-recovery/weather-forecast-worker-disposable.json)).

### CAP-040/047 signed current-weather worker — 17 October 2026

Native scheduled current-weather ingestion now uses a dedicated default-off worker with exact `weather` DSN, credential, and OpenWeatherMap key routing; shared PostgreSQL settings are stripped. Migration 427 adds signed location lookup and bounded atomic persistence for the observation, sanitized audit, ClickHouse outbox intent, and idempotency receipt. Forced-RLS disposable PostgreSQL checks cover migration replay, exact legacy outbox-intent reuse, conflicting outbox denial with rollback, scope mismatch, failure auditing, transaction cleanup, and direct-table/function ACLs. The 178 focused tests, nine disposable checks, Ruff, compilation, and regenerated inventories pass. Migration 427 is applied on the candidate; grants are not provisioned, the feature is off, and no provider, persisted schedule, candidate/legacy database, or real credential was used. Legacy task rows remain on the old entrypoint pending owner reconciliation. CAP-040 and CAP-047 remain unaccepted; live-provider parity, schedule state, application-wide RLS, and recovery acceptance remain open ([worker](../services/ingestion/weather_worker.py); [migration](../schemas/postgres/427_signed_weather_observation_worker.sql); [runner](../scripts/check-weather-observation-worker-disposable.py); [evidence](builds/2026-10-17-recovery/weather-observation-worker-disposable.json)).

### CAP-040/047 signed sensor-driver worker — 17 October 2026

Scheduled CSV sensor ingestion now has a dedicated default-off worker, exact
database/credential routing, and no shared-identity fallback. Migration 431
adds signed location-scoped driver and sensor-catalog reads, bounded atomic
reading/event/audit/ClickHouse-outbox persistence, idempotent duplicate
handling, and a location-bound driver status audit. Five disposable PostgreSQL
16 checks pass under forced RLS, including migration replay, cross-location
denial, duplicate suppression, atomic conflict rollback, and worker/runtime
privilege boundaries. The 200 focused sensor-worker, scheduler, job-contract,
and runtime-role tests pass with Ruff, Python compilation, and capability
matrix validation. Migration 431 is applied on the candidate; its worker login/grant is not
provisioned, and the feature is not enabled. No real sensor
file, provider, schedule, credential, candidate database, or legacy database
was used. Existing persisted sensor tasks remain on the legacy entrypoint
pending owner reconciliation; live input/provider parity, application-wide
RLS, Raspberry Pi hardware acceptance, and MAN-CAP-040/047 remain open
([worker](../services/ingestion/sensor_worker.py);
[migration](../schemas/postgres/431_signed_sensor_driver_worker.sql);
[runner](../scripts/check-sensor-ingestion-worker-disposable.py);
[evidence](builds/2026-10-17-recovery/signed-sensor-ingestion-worker-disposable.json)).

### CAP-040/047 isolated global notification enqueue — 16 October 2026

Migration 417 and the default-off handler adapter now support isolated enqueue
for `data_stale` and `threshold_breached` events. The function rechecks the
durable source ID/type and optional location lineage, restricts channels and
destination, caps intent size, and preserves stable idempotency. The distinct
login has no direct table or sequence privileges; notification delivery and
operator disposition remain separate. Seven checks pass on network-isolated
disposable PostgreSQL 16, and the focused migration/event/worker/map/runtime
suite passes 136 tests. Ruff, compilation, generated worker/SQL inventory
checks, and Compose resolution pass. No candidate or legacy database was
accessed, migration 417 has not been rolled out, its credential is not
provisioned, and the feature remains off. The SQL runner promoted only its
synthetic login directly; full runtime-role bootstrap integration acceptance
remains open. This implementation evidence does not change capability status
or MAN-CAP acceptance
([migration](../schemas/postgres/417_isolated_notification_enqueue.sql);
[runner](../scripts/check-notification-enqueue-worker-disposable.py);
[evidence](builds/2026-10-16-recovery/notification-enqueue-worker-disposable.json)).


### CAP-047/053 runtime function ACL closure — 16 October 2026

The migration 417 runtime-bootstrap acceptance exposed inherited `PUBLIC
EXECUTE` on the mobile credential functions from migrations 392–393 and on
the signed worker context helpers from migration 405. Migrations 418–419 now
remove those public grants. The runtime provisioner grants the mobile helper
functions to `kokonut_runtime`, and the worker context functions to
`kokonut_worker_execution` plus the specific bounded function owners. It also
repairs these grants on bootstrap after database-only restore. The disposable
PostgreSQL 16 integration applies/replays migrations 391–396, 398–400, 405,
and 417–419 and invokes the real runtime-role bootstrap. Nineteen database
checks and 49 focused migration/runtime tests pass, including notification
login enqueue under forced RLS and denial of unrelated SECURITY DEFINER and
direct-table access ([migrations](../schemas/postgres/418_mobile_credential_function_acl.sql),
[worker ACL migration](../schemas/postgres/419_private_worker_context_functions.sql);
[runner](../scripts/check-operator-session-role-disposable.py);
[evidence](builds/2026-10-16-recovery/runtime-notification-enqueue-role-disposable.json)).
Migrations 405–419 are not applied to the candidate; no encrypted credential
was provisioned, no provider was contacted, and no application-table RLS or
MAN-CAP acceptance is claimed. CAP-047 and CAP-053 progress classifications
remain unchanged.

### CAP-040/047 scheduler post-effect recovery — 16 October 2026

The disposable SchedulerEngine acceptance now kills the real scheduler parent
after a synthetic `data_stale` handler commits a notification outbox effect but
before task completion is acknowledged. The replacement worker reclaims the
task as attempt two; event delivery remains successful with one attempt and the
outbox retains exactly one row. Five focused handler-runner tests pass. The
acceptance also found and fixed service INFO logs contaminating the handler
runner's JSON stdout protocol. It uses selected scheduler/event/notification
migrations, a synthetic local-only webhook destination, and no delivery worker
or provider network call; candidate and legacy databases were untouched and the
disposable container was removed ([runner](../scripts/check-scheduler-engine-reconnect-disposable.py);
[protocol regression](../tests/test_event_handler_runner.py);
[evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json)).
This strengthens implementation/recovery evidence only; CAP-040 and CAP-047
classifications and MAN-CAP acceptance remain unchanged.

### CAP-040/047 per-location NOI snapshot scheduling — 16 October 2026

Native NOI snapshot jobs now require one location per task. The CLI validates
and canonicalizes scope before opening a database connection, constrains both
the source view and crop-cycle row, and preserves an explicit manual
`--all-locations` reconciliation mode. The curated job dispatcher, disabled
schedule planner, and persisted-command validator enforce the same location
contract. The focused CLI, scheduler, operation-map, and SQL/source inventory
suites pass 158 tests. No database,
provider, candidate, or persisted schedule was accessed; no task was activated.
This earlier query-filter slice did not establish worker identity or signed
context; that integration is recorded in the following section. Broader metrics
worker identity, application RLS, and MAN-CAP classifications remain open
([command](../services/metrics/cli.py); [scheduler contract](../services/security/scheduled_command_contracts.py);
[job inventory](worker-job-contract-inventory.json);
[evidence](builds/2026-10-16-recovery/noi-snapshot-location-scope.json)).

### CAP-040/047 signed NOI snapshot worker — 16 October 2026

Native NOI snapshot reconciliation now has a separate scheduled module and
worker-key route. Its default-off feature gate requires one canonical location;
the scheduler forwards only the NOI worker DSN/credential to that exact module
and strips shared PostgreSQL login settings from the child environment. The
worker establishes the database-signed `noi_snapshot/reconcile` context and
calls migration 425's bounded function. That function upserts only snapshots
for the signed location, refuses a caller-supplied location mismatch, and
leaves a stale conflicting cross-location snapshot untouched. The worker login
and execution role have no direct source or target table privileges; the
application runtime cannot execute the function. The focused source/scheduler/
inventory suite passes 193 tests; seven disposable PostgreSQL 16 checks pass,
including replay, exact grants, mismatch denial, and transaction cleanup.
Migration 425 is applied on the candidate; credentials and grants are not
provisioned, the feature remains off, application RLS remains disabled, and no
MAN-CAP acceptance is claimed ([worker](../services/metrics/noi_snapshot_worker.py);
[migration](../schemas/postgres/425_signed_noi_snapshot_worker.sql);
[runner](../scripts/check-noi-snapshot-worker-disposable.py);
[evidence](builds/2026-10-16-recovery/noi-snapshot-worker-disposable.json)).

### CAP-040/047 isolated global market-data worker — 17 October 2026

Native Market Data JobSpecs use a default-off dedicated World Bank worker; the manual
CLI and legacy persisted-task entrypoint remain available. Migration 430 grants one
bounded batch/audit function to a dedicated principal with no direct login table access.
The 199 focused source/scheduler checks and six disposable forced-RLS PostgreSQL 16
checks pass, including clean replay, direct-access denial, idempotency, malformed-row
rejection, and rollback. Migration 430 is applied on the candidate, and no real
provider or schedule was accessed. No MAN-CAP status changes
([worker](../services/ingestion/market_data_worker.py);
[migration](../schemas/postgres/430_isolated_market_data_worker.sql);
[runner](../scripts/check-market-data-worker-disposable.py);
[evidence](builds/2026-10-17-recovery/market-data-worker-disposable.json)).

### SDK spatial type contract — 18 October 2026

Python and TypeScript SDK models now represent schema-constrained PostGIS
`POINT` and `POLYGON` values with reusable GeoJSON shapes. The offline schema
guard verifies all seven mapped spatial fields alongside the 442 scalar types,
473 SQL columns, and nullable annotations across 20 models. Five source-guard
tests and the 29-test JavaScript suite pass; the TypeScript build, Ruff,
compilation, and guard pass. This improves generated/client-side data contracts
only; it does not establish Directus projection behavior, GIS validity, or
tenant authorization. JSONB semantic contracts remain under separate audit.
Capability classifications and MAN-CAP acceptance do not change
([evidence](builds/2026-10-18-recovery/sdk-postgis-shape-parity.json)).

### SDK JSONB contract types — 18 October 2026

The Python and TypeScript SDKs now expose recursive JSON value/object aliases,
and the source guard records the current semantic shape of all 24 JSONB fields
in the mapped models. Twenty-three fields are typed as JSON objects and
`ReportSnapshot.negative_findings` as an array of JSON objects. Twenty-seven
Python SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff, guard, and
matrix validation pass. These contracts describe the SDK surface; PostgreSQL
JSONB remains unrestricted and no runtime payload validator was added. This
does not establish Directus projection behavior or change capability/MAN-CAP
classifications ([evidence](builds/2026-10-18-recovery/sdk-jsonb-shape-parity.json)).

### SDK enum contract types — 18 October 2026

The static schema guard now discovers enum definitions and `column::enum_type`
checks from the ordered SQL sources. Python and TypeScript use shared literal
aliases for all seven constrained PostgreSQL enum types represented by 16
fields in the mapped SDK models. Twenty-nine Python SDK/guard tests and 29
JavaScript tests pass with the TypeScript build, Ruff, schema guard, and matrix
validation. This is static contract parity; it does not validate existing row
contents, unconstrained string fields, runtime API payloads, or Directus
projection behavior. Capability classifications and MAN-CAP acceptance remain
unchanged ([evidence](builds/2026-10-18-recovery/sdk-enum-schema-parity.json)).

### SDK organization-member schema parity — 18 October 2026

Python and TypeScript now model `organization_member`, including the nullable
`team_id` introduced by migration 174, JSON-object metadata, and the SQL
membership, role, and status literals. The source guard checks 22 models and
505 canonical columns, including 472 scalar types, 26 JSONB shapes, seven
PostGIS shapes, 16 enum fields, and eight discovered SQL CHECK fields. Thirty-
three Python SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff,
compilation, matrix validation, and diff checks pass. This type is descriptive;
it does not represent ownership, authorization, or a tenant grant. Checklist:
551 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-organization-member-parity.json`.

### SDK expense-category parity — 18 October 2026

The Python and TypeScript SDKs now expose the shared `expense_category`
taxonomy, including `schema_version` from migration 017. The offline guard
checks 23 models and 516 canonical columns, with 483 scalar types, 26 JSONB
shapes, seven PostGIS shapes, 16 enum fields, and eight SQL CHECK literal
fields. Thirty-four Python SDK/guard tests and 29 JavaScript tests pass with
the TypeScript build, Ruff, compilation, guard, matrix validation, and diff
check. The type adds no authorization behavior. Checklist: 552 complete / 19
open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-expense-category-parity.json`.

### SDK capital-source parity — 18 October 2026

The Python and TypeScript SDKs now expose `capital_source`, including status,
JSON metadata, and migration 017's `schema_version`. The offline guard checks
24 models and 529 columns, including 495 scalar types, 27 JSONB shapes, seven
PostGIS shapes, 17 enum fields, and eight SQL CHECK-literal fields. Thirty-five
Python SDK/guard tests and 29 JavaScript tests pass with the TypeScript build,
Ruff, compilation, schema guard, matrix validation, and diff check. This type
does not authorize financial actions. Checklist: 553 complete / 19 open.
Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-capital-source-parity.json`.

### SDK financial-transaction parity — 18 October 2026

Python and TypeScript now expose the canonical `financial_transaction` row,
including transaction identifiers and amounts, reconciliation state, evidence,
and import lineage. The source guard checks 25 models and 555 columns, including
520 scalar fields, 28 JSONB shapes, seven PostGIS shapes, 17 enum fields, and
eight SQL CHECK-literal fields. Thirty-six Python SDK/guard tests and 29
JavaScript tests pass with TypeScript build, Ruff, compilation, schema guard,
matrix validation, and diff checks. This type does not initiate payments or
establish verification. Checklist: 554 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-financial-transaction-parity.json`.

### SDK value-flow event parity — 18 October 2026

Python and TypeScript now expose the canonical `value_flow_event` row,
including location, flow details, verification/attestation references,
exclusion state, and chain transaction identifiers. The guard checks 26 models
and 577 columns, including 542 scalar types, 28 JSONB shapes, seven PostGIS
shapes, 17 enum fields, and eight SQL CHECK-literal fields. Thirty-seven Python
SDK/guard tests and 29 JavaScript tests pass with TypeScript build, Ruff,
compilation, schema guard, matrix validation, and diff checks. The type does
not verify records or submit attestations. Checklist: 555 complete / 19 open.
Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-value-flow-event-parity.json`.

### SDK excluded-value event parity — 18 October 2026

Python and TypeScript now expose `excluded_value_event`, including the linked
flow, exclusion type, amount/currency, reason, and reviewer attribution. The
guard checks 27 models and 586 canonical columns, including 551 scalar fields,
28 JSONB shapes, seven PostGIS shapes, 17 enum fields, and eight SQL
CHECK-literal fields. Thirty-eight Python SDK/guard tests and 29 JavaScript
tests pass with TypeScript build, Ruff, compilation, schema guard, matrix
validation, and diff checks. This type records exclusion context and does not
mutate the linked flow. Checklist: 556 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-excluded-value-event-parity.json`.

### SDK crop-cost allocation parity — 18 October 2026

Python and TypeScript now expose `crop_cost_allocation`, including its crop
cycle/expense references, allocation method, amount, and optional ratio. The
guard checks 28 models and 594 columns, including 559 scalar fields, 28 JSONB
shapes, seven PostGIS shapes, 17 enum fields, and eight SQL CHECK-literal
fields. Thirty-nine Python SDK/guard tests and 29 JavaScript tests pass with
TypeScript build, Ruff, compilation, schema guard, matrix validation, and diff
checks. The type describes a stored allocation and does not calculate or
transfer funds. Checklist: 557 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-crop-cost-allocation-parity.json`.

### SDK metric-definition parity — 18 October 2026

Python and TypeScript now expose `metric_definition`, including validation
object arrays, source/report usage, stakeholder fields, and additive category
and state metadata. The guard checks 29 models and 617 columns, including 581
scalar types, 29 JSONB shapes, seven PostGIS shapes, 17 enum fields, and eight
SQL CHECK-literal fields. Forty Python SDK/guard tests and 29 JavaScript tests
pass with TypeScript build, Ruff, compilation, schema guard, matrix validation,
and diff checks. The type does not execute formulas or verify metric values.
Checklist: 558 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-metric-definition-parity.json`.

### SDK metric-version parity — 18 October 2026

Python and TypeScript now expose `metric_version` history with version number,
formula snapshot, changes, reason, and audit fields. The guard checks 30 models
and 625 canonical columns, including 589 scalar types, 29 JSONB shapes, seven
PostGIS shapes, 17 enum fields, and eight SQL CHECK-literal fields. Forty-one
Python SDK/guard tests and 29 JavaScript tests pass with TypeScript build, Ruff,
compilation, schema guard, matrix validation, and diff checks. This type
describes history and does not grant mutation or verification behavior.
Checklist: 559 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-metric-version-parity.json`.

### SDK metric-value parity and additive-column guard correction — 18 October 2026

Python and TypeScript now expose `metric_value`, including source-record IDs,
stored verification state, reviewer attribution, and verification notes. A
schema-guard regression verifies that duplicate `ADD COLUMN IF NOT EXISTS`
statements preserve an existing base column's type and nullability. The guard
checks 31 models and 640 columns, including 602 scalar types, 30 JSONB shapes,
seven PostGIS shapes, 17 enum fields, and eight SQL CHECK-literal fields.
Forty-three Python SDK/guard tests and 29 JavaScript tests pass with TypeScript
build, Ruff, compilation, schema guard, matrix validation, and diff checks.
The SDK keeps computation separate from human verification. Checklist: 560
complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-metric-value-parity.json`.

### SDK forecast model parity — 18 October 2026

Python and TypeScript now expose `forecast_scenario` and `forecast_output`,
including scenario assumptions, lifecycle state, result values, confidence
bounds, and input metadata. The guard checks 33 models and 673 columns,
including 629 scalar types, 36 JSONB shapes, seven PostGIS shapes, 18 enum
fields, and eight SQL CHECK-literal fields. Forty-five Python SDK/guard tests
and 29 JavaScript tests pass with TypeScript build, Ruff, compilation, schema
guard, matrix validation, and diff checks. The types do not execute forecasts
or establish output verification. Checklist: 561 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-forecast-model-parity.json`.

### AI summary SDK model parity — 18 October 2026

Python and TypeScript now model stored AI narratives with subject identity,
source lineage, confidence, lifecycle state, and review attribution. The
schema guard checks 34 models and 687 columns, including 642 scalar types,
seven PostGIS shapes, 36 JSONB shapes, 19 enum fields, and eight standalone
SQL CHECK literals. Forty-six focused Python SDK/guard tests, 29 JavaScript
tests, TypeScript build, Ruff, compilation, guard, matrix validation, and diff
checks pass. This adds a typed data contract only; it does not generate or
publish summaries. No capability status or MAN-CAP acceptance changed.
Checklist: 562 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-ai-summary-parity.json`.

### Dashboard dataset SDK model parity — 18 October 2026

Python and TypeScript now model the stored dashboard dataset definition,
including query text, location scope, refresh state, lifecycle, and metadata.
The schema guard checks 35 models and 700 columns, including 654 scalar types,
seven PostGIS shapes, 37 JSONB shapes, 20 enum fields, and eight standalone
SQL CHECK literals. Forty-seven focused Python SDK/guard tests, 29 JavaScript
tests, TypeScript build, Ruff, compilation, guard, matrix validation, and diff
checks pass. The model does not execute SQL or trigger refresh jobs. No
capability status or MAN-CAP acceptance changed. Checklist: 563 complete / 19
open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-dashboard-dataset-parity.json`.

### Time-series forecast SDK model parity — 18 October 2026

Python and TypeScript now model stored time-series forecasts and accuracy
records, including constrained model/status literals, model inputs, forecast
values and intervals, and observed-versus-predicted measurements. Recursive
`JSONValue[]` typing covers the forecast value array without imposing an
object-only shape. The schema guard checks 37 models and 725 columns,
including 675 scalar types, seven PostGIS shapes, 41 JSONB shapes, 20 enum
fields, and ten standalone SQL CHECK literals. Forty-eight focused Python
SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff, compilation,
guard, matrix validation, and diff checks pass. The types do not calculate
forecasts or accuracy; capability status and MAN-CAP acceptance are unchanged.
Checklist: 564 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-time-series-forecast-parity.json`.

### Demand forecast SDK model parity — 18 October 2026

Python and TypeScript now model stored demand projections with period,
quantity, revenue/confidence, model, input/source lineage, and review fields.
The guard validates the forecast-type and lifecycle literals plus both JSON
object fields. It checks 38 models and 755 columns, including 703 scalar
types, seven PostGIS shapes, 43 JSONB shapes, 20 enum fields, and 12 standalone
SQL CHECK literals. Forty-nine focused Python SDK/guard tests, 29 JavaScript
tests, TypeScript build, Ruff, compilation, guard, matrix validation, and diff
checks pass. The contract does not compute or verify estimates; capability
status and MAN-CAP acceptance are unchanged. Checklist: 565 complete / 19
open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-demand-forecast-parity.json`.

### Demand market-size and trend SDK model parity — 18 October 2026

Python and TypeScript now model stored TAM/SAM/SOM estimates and demand-trend
records, including constrained market/analysis types, lifecycle, source
metadata, and reviewer attribution. The schema guard checks 40 models and 823
columns, including 768 scalar types, seven PostGIS shapes, 46 JSONB shapes, 20
enum fields, and 16 standalone SQL CHECK literals. Fifty focused Python
SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff, compilation,
guard, matrix validation, and diff checks pass. These types do not calculate
market size or rerun trend analysis; capability status and MAN-CAP acceptance
remain unchanged. Checklist: 566 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-demand-market-analysis-parity.json`.

### Buyer signal and production-market match SDK parity — 18 October 2026

Python and TypeScript now model buyer demand signals and period-scoped
production-market matches, including buyer intent, constrained signal and
commitment values, supply/demand measures, provenance, and review fields. The
schema guard checks 42 models and 882 columns, including 824 scalar types,
seven PostGIS shapes, 49 JSONB shapes, 20 enum fields, and 21 standalone SQL
CHECK literals. Fifty-one focused Python SDK/guard tests, 29 JavaScript tests,
TypeScript build, Ruff, compilation, guard, matrix validation, and diff checks
pass. The records do not establish fulfillment or calculate supply gaps;
capability status and MAN-CAP acceptance remain unchanged. Checklist: 567
complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-buyer-market-match-parity.json`.

### Buyer segment SDK model parity — 18 October 2026

Python and TypeScript now model stored buyer segments with constrained segment
type/value fields, criteria, performance measures, assessment periods, and
review attribution. The schema guard checks 43 models and 906 columns,
including 847 scalar types, seven PostGIS shapes, 50 JSONB shapes, 20 enum
fields, and 24 standalone SQL CHECK literals. Fifty-two focused Python
SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff, compilation,
guard, matrix validation, and diff checks pass. The type does not classify
buyers or calculate measures; capability status and MAN-CAP acceptance remain
unchanged. Checklist: 568 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-buyer-segment-parity.json`.

### Trend result SDK model parity — 18 October 2026

Python and TypeScript now model trend estimates, smoothed values, and detected
change points, including constrained confidence/direction, smoothing and
detection methods, status, and evidence fields. The schema guard checks 46
models and 957 columns, including 896 scalar types, seven PostGIS shapes, 52
JSONB shapes, 20 enum fields, and 30 standalone SQL CHECK literals. Fifty-three
focused Python SDK/guard tests, 29 JavaScript tests, TypeScript build, Ruff,
compilation, guard, matrix validation, and diff checks pass. The models do not
compute the represented analyses; capability status and MAN-CAP acceptance
remain unchanged. Checklist: 569 complete / 19 open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-trend-result-parity.json`.

### Seasonal decomposition and trend dashboard SDK parity — 18 October 2026

Python and TypeScript now model saved seasonal/trend/residual components and
trend-dashboard summaries. Recursive JSON arrays preserve the component
values without restricting them to object records. The schema guard checks
48 models and 988 columns, including 923 scalar types, seven PostGIS shapes,
56 JSONB shapes, 20 enum fields, and 31 standalone SQL CHECK literals.
Fifty-four focused Python SDK/guard tests, 29 JavaScript tests, TypeScript
build, Ruff, compilation, guard, matrix validation, and diff checks pass.
The types do not calculate decomposition or dashboard aggregates; capability
status and MAN-CAP acceptance remain unchanged. Checklist: 570 complete / 19
open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-seasonal-trend-dashboard-parity.json`.

### Weather observation SDK model parity — 18 October 2026

Python and TypeScript now represent stored weather observations and their
source lineage. The guard covers 49 models and 1,012 columns, including 945
scalar types, seven PostGIS shapes, 58 JSONB shapes, 20 enum fields, and 31
standalone SQL CHECK literals. This adds data contracts only; it does not
fetch, validate, or verify provider data. Checklist: 571 complete / 19 open.
Capability classifications and MAN-CAP acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-weather-observation-parity.json`.

### Soil sample SDK model parity — 18 October 2026

Python and TypeScript now represent soil sample measurements with source
lineage, governed lifecycle, sampling protocol/custody fields, and typed
location geometry. The guard covers 50 models and 1,060 columns, including
991 scalar types, eight PostGIS shapes, 59 JSONB shapes, 20 enum fields, and
32 standalone SQL CHECK literals. This adds record contracts only; it does not
validate measurements or authorize review. Checklist: 572 complete / 19 open.
Capability classifications and MAN-CAP acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-soil-sample-parity.json`.

### Soil-carbon measurement SDK model parity — 18 October 2026

Python and TypeScript now represent stored soil-carbon measurements with
evidence links, baseline lineage, governed review metadata, and lab protocol
fields. The guard covers 51 models and 1,087 columns, including 1,017 scalar
types, eight PostGIS shapes, 60 JSONB shapes, 20 enum fields, and 33 standalone
SQL CHECK literals. The type does not calculate carbon stocks or perform
verification. Checklist: 573 complete / 19 open. Capability classifications
and MAN-CAP acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-soil-carbon-measurement-parity.json`.

### Environmental baseline SDK model parity — 18 October 2026

Python and TypeScript now represent stored environmental baseline values with
optional plot scope, evidence links, and source lineage. The guard covers 52
models and 1,104 columns, including 1,033 scalar types, eight PostGIS shapes,
61 JSONB shapes, 20 enum fields, and 33 standalone SQL CHECK literals. The
record does not calculate values or establish an authoritative baseline.
Checklist: 574 complete / 19 open. Capability classifications and MAN-CAP
acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-environmental-baseline-parity.json`.

### Species observation SDK model parity — 18 October 2026

Python and TypeScript now represent biodiversity observations with source
lineage, evidence arrays, lifecycle, trophic level, and conservation status.
The guard covers 53 models and 1,133 columns, including 1,061 scalar types,
eight PostGIS shapes, 62 JSONB shapes, 20 enum fields, and 36 standalone SQL
CHECK literals. Its TypeScript literal parser now handles multiline unions.
The model does not verify field observations or ecological classifications.
Checklist: 575 complete / 19 open. Capability classifications and MAN-CAP
acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-species-observation-parity.json`.

### Remote-sensing observation SDK model parity — 18 October 2026

Python and TypeScript now represent remote-sensing observations with evolved
spectral fields, image metadata, source lineage, and typed geometry. The model
reflects migration 432's nullable plot link. The guard covers 54 models and
1,172 columns, including 1,096 scalar types, 10 PostGIS shapes, 64 JSONB
shapes, 20 enum fields, and 36 standalone SQL CHECK literals. It does not
fetch imagery or calculate indices. Checklist: 576 complete / 19 open.
Capability classifications and MAN-CAP acceptance are unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-remote-sensing-observation-parity.json`.

### MRV claim and verification-review SDK model parity — 18 October 2026

Python and TypeScript now represent MRV claims separately from human review
records, preserving lifecycle and attestation fields as stored data. The guard
covers 56 models and 1,209 columns, including 1,133 scalar types, 10 PostGIS
shapes, 66 JSONB shapes, 21 enum fields, and 36 standalone SQL CHECK literals.
It also recognizes UUID arrays as string arrays in both SDKs. These models do
not verify claims, change lifecycle, or submit attestations. Checklist: 577
complete / 19 open. Capability classifications and MAN-CAP acceptance are
unchanged. Evidence:
`docs/refactor/builds/2026-10-18-recovery/sdk-mrv-claim-review-parity.json`.

### Financial ClickHouse outbox source parity — 18 October 2026

PostgreSQL migration 434 replaces the Directus hook's best-effort HTTP insert
with an atomic outbox trigger for `sales_event` and `expense_event` creation.
The optional ClickHouse worker remains the delivery adapter. Disposable
PostgreSQL 16 replay, forced-RLS, transaction rollback, USD/non-USD mapping,
zero-value omission, and narrow owner/source-role ACL checks pass, along with the focused
Directus-hook test and extension build. Candidate rollout is complete; updates/deletes, historical backfill,
populated report parity, and MAN-CAP acceptance remain open. The candidate
rollout followed encrypted checkpoint and restore rehearsal
([rollout evidence](builds/2026-10-18-recovery/candidate-migration-434-rollout.json)). CI #483 exposed that the new NOLOGIN projection owner was absent from the
database-only restore-role prerequisites; it is now listed and the focused
role inventory regression passes 2 tests. No capability classification changes. Checklist: 605 complete / 19
open. Evidence:
`docs/refactor/builds/2026-10-18-recovery/financial-events-outbox-disposable.json`.

Migration 435 adds an after-insert guard for both sources. It verifies the
existing stable outbox key resolves to the exact expected source, target,
columns, rows, and payload digest; a mismatch raises and rolls back the source
insert instead of being silently accepted by migration 434's enqueue. A
network-disabled PostgreSQL 16 replay and forced-RLS check passes exact
duplicate acceptance and conflicting duplicate rejection, along with the
existing currency, zero-value, transaction, and privilege behavior. Migration
435 is not applied to the local candidate and requires its own checkpointed
rollout. Capability classifications are unchanged. Checklist: 606 complete /
19 open ([migration](../schemas/postgres/435_financial_projection_conflict_guard.sql); [disposable evidence](builds/2026-10-18-recovery/financial-events-outbox-disposable.json)).

### Directus farm-activity source-contract update — 18 October 2026

The optional Directus fixture now enforces the owner-selected Gateway boundary: synthetic location grants do not authorize farm-activity API reads or writes, and Field Note reads remain location-scoped. Seven focused source/fixture checks, Ruff, compilation, and the matrix validator pass. Commit `6c53e0fe` is pushed to PR #68; Security #209 passed and CI #485 is in progress. No capability classification changed, and this is not fresh pinned-runtime acceptance or broader Directus parity evidence ([source evidence](builds/2026-10-18-recovery/directus-gateway-only-source-contract.json)).

### Field Collector successful-upload CORS contract — 18 October 2026

The actual Gateway middleware and Field Collector upload handler now have an
in-process successful-response check using a synthetic device-token resolver
and mocked PostgreSQL/media adapters. A successful HTTP 201 carries the exact
allowlisted origin, `Access-Control-Allow-Credentials: true`, and `Vary:
Origin`; the existing preflight test also confirms the custom device/upload
headers. Two focused CORS tests and Ruff pass. No live credentials, database,
provider, or network were used. This closes only the source/in-process response
contract, not browser-through-proxy, live OIDC/device auth, or external ingress.
Capability classifications remain unchanged; checklist: 607 complete / 19
open ([evidence](builds/2026-10-18-recovery/mobile-upload-success-cors.json)).


### Candidate migration 435 rollout — 18 October 2026

The migration-435 checkpoint was restored into a network-disabled, no-volume
PostgreSQL 16 container from a `template0` target. The 431-row ledger
fingerprint, extension versions, and 1,396 public relations matched the
candidate. The ordered runner then applied only migration 435; the candidate
now has 426 applied schemas, six previously applied seeds, and zero pending
schema migrations. The app remains healthy, `/health` returns 200, and
anonymous operator review access returns 401. No seeds, legacy services, app
image, Metabase, or proxy were changed. Financial update/delete reconciliation,
historical projection backfill, populated report parity, and named MAN-CAP
acceptance remain open ([rollout evidence](builds/2026-10-18-recovery/candidate-migration-435-rollout.json)).

Capability classifications are 53 baseline-retained, 7 deployed, and 6 prepared.
Checklist: 632 complete / 19 open; named MAN-CAP acceptance
remains separate.

### CAP-047 isolated RPC wallet-balance snapshot worker — 18 October 2026

Migration 436 and a default-off `rpc_worker` now isolate scheduled wallet
balance snapshots behind a dedicated login and bounded chain-lock, wallet-list,
snapshot/outbox, and completion functions. The login has no direct table access;
the operation is global protocol data and does not claim location tenant
context. Network-disabled PostgreSQL 16 acceptance passed migration replay,
forced-RLS operations, idempotent snapshot/outbox replay, legacy same-block
reuse, malformed/conflicting snapshot rejection, exact eight-decimal numeric
storage, and direct-table denial. The legacy CLI now row-locks and checks
duplicate content instead of using `ON CONFLICT (tx_hash)`, which the base
schema cannot support because its index is non-unique. The focused
worker/legacy boundary suite passes 284 tests with Ruff and compilation. Both
balance paths now use decimal half-up rounding; the legacy ClickHouse row
builder preserves a decimal instead of converting through a binary float. Both
paths anchor each chain run to one block height and timestamp. The isolated
worker hashes the exact numeric JSON sent to PostgreSQL, buffers wallet
observations, and rejects a changed block hash before storing snapshots. The
legacy CLI queries every wallet at the selected height and rolls back the
transaction if the block hash changes before commit. These checks do not pin
RPC reads to a block hash or establish recovery after a later reorganization.
The candidate remains at
migration 435;
no worker credential, provider, schedule, or feature was activated. This only
preserves point-in-time balance snapshots; transaction-history scanning,
confirmation/finality, provider parity, schedule ownership, and reorg recovery
remain open. CAP-047 remains partial and MAN-CAP acceptance is unchanged
([worker](../services/ingestion/rpc_worker.py);
[migration](../schemas/postgres/436_isolated_rpc_indexer.sql);
[runner](../scripts/check-rpc-indexer-worker-disposable.py);
[database evidence](builds/2026-10-18-recovery/rpc-indexer-worker-disposable.json);
[checks](builds/2026-10-18-recovery/rpc-indexer-worker-checks.json)). The
default image from pushed commit `9e02eeff` also built for `linux/arm64`, and
QEMU imported the worker and constructed a synthetic balance snapshot with
networking disabled. No ARM64 database/app stack or migration 436 replay ran;
physical Raspberry Pi acceptance remains open
([ARM64 evidence](builds/2026-10-18-recovery/arm64-rpc-worker-image-smoke.json)).
Wei-to-ETH conversion now uses decimal half-up rounding in both the isolated
and manual RPC paths. Exact numeric JSON, payload hash parity, one-block
snapshot reads, changed-hash rejection in both paths, and decimal ClickHouse
payload preparation are covered by 284 focused tests; disposable PostgreSQL
confirms exact precision. This changes source correctness evidence only, not capability
classification or MAN-CAP status.


**Forecast-accuracy SDK read note — 18 October 2026:** Python and TypeScript
now expose read-only `forecast_accuracy` access scoped to `forecast_id`, the
actual indexed parent relationship in migration 131. There is no `location_id`
column, so the client does not invent location scope; Directus/API policy remains
the authorization boundary. Ninety-eight Python SDK/schema/method tests, 48
JavaScript tests, TypeScript build, Ruff, Python compilation, schema and
capability guards, and diff checks pass offline. This does not calculate or
verify forecast accuracy and changes no capability classification. Checklist:
625 complete / 19 open ([evidence](builds/2026-10-18-recovery/sdk-forecast-accuracy-read-methods.json)).

**Sensor operations SDK read note — 18 October 2026:** Python and TypeScript
now expose location-filtered reads for sensor-device inventory and sensor-alert
history. Sensor alerts follow migration 406's nullable location lineage; legacy
unassigned rows are excluded from the scoped method. No registration, alert
lifecycle mutation, actuation, or authorization boundary is added. The focused
SDK suites, TypeScript build, Ruff, schema/capability guards, and diff checks
pass; classifications remain unchanged. Checklist: 626 complete / 19 open
([evidence](builds/2026-10-18-recovery/sdk-sensor-operations-read-methods.json)).


**Variogram-model SDK read note — 18 October 2026:** Python and TypeScript now
provide a typed read-only `variogram_model` group filtered by the stored
`location_id`. The SDK schema guard verifies the four SQL model-type values,
all fields and scalar families, nullable location/metadata, and JSON object
shape. These reads do not fit, validate, or certify a variogram, and MAN-CAP-008
remains unaccepted. Ninety-eight Python SDK/schema/method tests and 48
JavaScript tests pass with TypeScript build, Ruff, compilation and matrix guards.
Checklist: 627 complete / 19 open
([evidence](builds/2026-10-18-recovery/sdk-variogram-read-methods.json)).

**CAP-024 role nomination note — 18 October 2026:** the exact-grant Gateway
proposal route and migration 438 now allow idempotent role nominations that
remain `proposed`; direct runtime/Directus assignment writes are revoked, and
the request/actor ledger is private and append-only. The 148 focused Gateway, migration,
and route-policy tests plus disposable PostgreSQL 16 apply/replay/ACL checks
pass. The candidate remains at migration 437 and its app connects as administrative `kokonut`, so the runtime-role ACLs do not isolate that deployment. This is prepared source and disposable-database evidence only. No approval action or MAN-CAP acceptance is implied.
Checklist: 647 complete / 19 open; classifications stay 45 baseline-retained,
7 deployed, 14 prepared ([evidence](builds/2026-10-18-recovery/governance-assignment-proposals-disposable.json)).


**CAP-024 definition mutation note — 18 October 2026:** migration 443 adds exact-grant, location-scoped circle/role creation and draft-only descriptive edits through the Gateway. New definitions are drafts; circle parent and role circle references must be in the same location, and hierarchy cycles are rejected. An immutable private ledger records actor, request, reason, and before/after values; runtime and Directus direct writes are revoked and trigger-guarded. The console uses a separate no-store circle-detail read requiring exact location `:read` and `:update` to load draft fields while keeping the aggregate summary free of description and purpose. The focused CAP-024 Gateway, policy, and console suite passes 151 tests (5 skipped), and disposable PostgreSQL 16 replay through 443 verifies write boundaries and retries. Ruff, compilation, JavaScript syntax, matrix validation, and the refreshed SQL inventory (850 service files / 4,111 execution sites) pass. Candidate remains at migration 437 with administrative `kokonut`; no candidate/legacy database was touched and no migration was rolled out. CAP-024 remains prepared, not accepted. Checklist: 654 complete / 19 open; classifications remain 45 baseline-retained, 7 deployed, 14 prepared ([migration](../schemas/postgres/443_governance_definition_mutations.sql); [Gateway tests](../tests/test_gateway_governance_definition_mutations.py); [database evidence](builds/2026-10-18-recovery/governance-definition-mutations-disposable.json)).
**CAP-024 definition lifecycle note — 18 October 2026:** migration 442 adds audited Gateway transitions for location-scoped governance circles and roles. Exact per-action grants, creator/reviewer separation, state preconditions, request-key replay, and immutable actor/reason history are enforced in a bounded security-definer function. Status changes made directly by runtime and Directus roles are blocked even when broad table writes are present. Twelve focused Gateway and route-policy tests pass; disposable PostgreSQL 16 applies/replays migrations 437–442 and verifies full circle/role lifecycle transitions, direct status bypass denial, idempotency, and ACLs. Candidate and legacy databases were not touched; CAP-024 remains prepared, and console lifecycle controls, creation/edit parity, live acceptance, RLS, populated fixtures, and MAN-CAP-024 remain open. Checklist: 652 complete / 19 open; classifications remain 45 baseline-retained, 7 deployed, 14 prepared ([migration](../schemas/postgres/442_governance_definition_lifecycle.sql); [Gateway tests](../tests/test_gateway_governance_definition_actions.py); [database evidence](builds/2026-10-18-recovery/governance-lifecycle-actions-disposable.json)).

**CAP-024 tactical session registry note — 18 October 2026:** the exact-grant
Gateway now lists location-scoped tactical session summaries and aggregate item
counts with a signed read context, read-only transaction, and bounded keyset
pagination. Notes, agenda, outcomes, and party identities are omitted. The
operator console renders the registry as text alongside the open-action queue.
Thirty-eight focused Gateway, route-policy, and console checks pass; Ruff,
compilation, JavaScript syntax, capability validation, and the refreshed runtime
SQL inventory pass. This closes only a code-level read slice: tactical create/edit
parity, populated data, tenant RLS, live OIDC/browser behavior, and MAN-CAP-024
acceptance remain open. See [evidence](builds/2026-10-18-recovery/governance-tactical-session-registry.json).

**CAP-024 tactical session creation note — 19 October 2026:** migration 444 and the Gateway now create planned tactical sessions through exact location `governance_tactical:create`, signed tenant context, and active person binding. The circle must be active and location-owned; optional facilitator/recorder roles must be active in that circle. Unsupported status, notes, outcome, identity, and timestamp fields are rejected. Exact retries replay; changed request-key reuse fails. A private immutable ledger captures actor, reason, and request content, while runtime/Directus direct inserts are revoked and guarded. The console form is hidden without the exact create grant and uses CSRF/no-store requests. Fifteen focused Gateway/route-policy/console checks and disposable PostgreSQL 16 apply/replay acceptance through migration 444 pass. Candidate stays at migration 437; no candidate/legacy database was accessed. Checklist: 656 complete / 19 open; classifications remain 45 baseline-retained, 7 deployed, 14 prepared. CAP-024 remains prepared, not accepted; item edits, populated parity, live OIDC/browser, least-privilege rollout, tenant RLS, and MAN-CAP-024 remain open ([contract](governance-tactical-session-creation-contract.md); [migration](../schemas/postgres/444_governance_tactical_session_creation.sql); [tests](../tests/test_gateway_governance_tactical_session_mutations.py); [database evidence](builds/2026-10-19-recovery/governance-tactical-session-creation-disposable.json)).


**CAP-024 tactical content mutation note — 19 October 2026:** the Gateway now creates open tactical items and edits only open-item content or planned-session content. Exact signed location grants, active operator/person binding, same-location references, bounded fields, lifecycle separation, stable idempotent request IDs, and private immutable before/after history are enforced by migration 445's security-definer function. Runtime and Directus direct writes are blocked; row-lock reference grants are limited to `UPDATE(id)`. The console adds grant-gated CSRF/no-store create and edit forms. The focused mutation slice passes 19 tests and the broader CAP-024 Gateway, route-policy, and console regression set passes 182 tests with five skips; 33 migration metadata tests and the disposable PostgreSQL 16 migration 437–445 apply/replay acceptance, including ACL and lifecycle-boundary cases ([contract](governance-tactical-content-mutation-contract.md); [migration](../../schemas/postgres/445_governance_tactical_content_mutations.sql); [Gateway tests](../../tests/test_gateway_governance_tactical_mutations.py); [database evidence](builds/2026-10-19-recovery/governance-tactical-content-mutations-disposable.json)). Candidate remains at migration 444 and was not changed. This completes the code-level mutation slice, not MAN-CAP-024 acceptance: least-privilege runtime rollout, remaining report/populated-data parity, tenant RLS, live OIDC/browser behavior, and accountable-owner review remain open.


**CAP-027 recommendation review acceptance — 19 October 2026:** migration 450 applies and replays in disposable PostgreSQL 16; seven runtime assertions pass for location and grant scope, self-review denial, diversity/minority approval gates, idempotency and collision handling, append-only decision history, and runtime/Directus direct-table denial. The PostgreSQL row-lock correction grants only `UPDATE(id)` to the non-login function owner. The 119 focused CAP-027 Gateway, route-policy, Delphi, and migration checks pass. No candidate or legacy database was touched; migration 450 remains prepared and unapplied there. CAP-027 remains prepared, not accepted; live OIDC/browser, broader lifecycle and populated parity, universal ACL/RLS, and MAN-CAP-027 owner review remain open. Checklist: 667 complete / 19 open; classifications remain 42 baseline-retained, 7 deployed, and 17 prepared ([contract](delphi-consultation-kernel-contract.md); [migration](../schemas/postgres/450_location_scoped_delphi_recommendation_review.sql); [disposable evidence](builds/2026-10-19-recovery/cap-027-delphi-recommendation-review-disposable.json)).


**CAP-027 reviewer console acceptance — 19 October 2026:** the operator console now exposes a Delphi draft queue only for locations with an exact `delphi:review` session grant. It shows database readiness blockers, hides approval for blocked or self-authored drafts, limits rejection choices to the database reason-code allowlist, and sends CSRF-protected no-store requests with stable request IDs for retries. Five focused console contract tests pass, including inline JavaScript parsing with Node.js; live OIDC/browser acceptance remains open. No capability classification changed. Checklist: 667 complete / 19 open; classifications remain 42 baseline-retained, 7 deployed, and 17 prepared ([contract](delphi-consultation-kernel-contract.md); [console](../../apps/operator-console/index.html)).


**CAP-027 facilitator draft creation acceptance — 19 October 2026:** migration 451 and its Gateway/console path pass the approved focused source and disposable PostgreSQL checks; see [draft evidence](builds/2026-10-19-recovery/cap-027-delphi-recommendation-drafts-disposable.json) and [updated checklist](batches.md). The checklist is 668 complete / 19 open (687 total). Capability classifications remain 42 baseline-retained, 7 deployed, and 17 prepared; CAP-027 remains prepared, not accepted.



**CAP-035 consent-aware experiment observation capture — 20 October 2026:** migration 510 adds a signed exact-location `solution_lifecycle:collect` action and an active-experiment console form. Protocols require either a participant-consent purpose/version or an approved non-personal basis. Participant captures recheck the exact-location participant link and latest consent state; a private receipt and observation commit atomically. Forced RLS hides withdrawn and unassessed legacy rows, and runtime/Directus cannot write observations or read receipts directly. The console uses CSRF/no-store, opaque participant-link IDs, non-identifying evidence guidance, and stable retry IDs. The 177-test experiment/Gateway/console/route-policy/migration selection passes, as do Ruff, Python compilation, inline JavaScript syntax, and disposable PostgreSQL 16 migration 510 apply/replay with eight grouped checks. Candidate and legacy remain untouched; migration 510 is not rolled out. Checklist: 763 complete / 24 open; classifications remain 31 baseline-retained, 7 deployed, and 28 prepared. [Write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/510_location_solution_experiment_observation_capture.sql); [Gateway test](../tests/test_gateway_solution_lifecycle_experiment_observation.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-observation-disposable.json).
**CAP-035 exact-location approved experiment start — 20 October 2026:** migration 509 adds a signed `solution_lifecycle:transition` action that starts only an active exact-origin experiment with independently approved protocol and a matching immutable approval receipt. It writes an immutable retry receipt and changes experiment state only; it does not assert participant consent, collect observations, or advance the solution stage. Migration 509 also removes direct experiment lifecycle updates from the shared runtime and Directus roles. All legacy experiment create, submit, approve, start, observation, analysis, completion, result-review, and replication helpers now fail before database access. Consent-aware observation collection, scoped analysis, and completion remain open Gateway work. The focused Gateway/console/route/legacy/migration selection passes 118 tests; seven disposable PostgreSQL 16 apply/replay and role-boundary groups pass. Candidate and legacy remain untouched; migration 509 is not rolled out. [Write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/509_location_solution_experiment_start.sql); [Gateway tests](../tests/test_gateway_solution_lifecycle_experiment_start.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-start-disposable.json). Checklist: 762 complete / 24 open; classifications remain 31 baseline-retained, 7 deployed, and 28 prepared.

**CAP-035 independent experiment protocol review — 20 October 2026:** migration 508 adds private exact-location submitted-protocol detail and independent approval. Review requires a current signed location grant; details omit party identities and expose only reviewer-conflict booleans. Approval requires an active human distinct from owner and submitter, is retry-safe through private immutable receipts, and changes only protocol status and reviewer attribution. Consent, start, and stage transition remain separate. The legacy approval helper now fails before database access. The focused Gateway/console/route/legacy/migration selection passes 104 tests with one database-backed skip; eight disposable PostgreSQL 16 apply/replay and privilege groups pass. Candidate and legacy databases remain untouched; migration 508 is not rolled out. [Write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/508_location_solution_experiment_protocol_review.sql); [Gateway tests](../tests/test_gateway_solution_lifecycle_experiment_protocol_review.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-protocol-review-disposable.json). Checklist: 760 complete / 24 open; classifications remain 31 baseline-retained, 7 deployed, and 28 prepared.

**CAP-035 experiment protocol submission — 20 October 2026:** migration 507 adds an exact-location owner-only `draft` → `submitted` action with an immutable retry receipt. It requires signed submit scope, an active human owner binding, and a current active exact-origin experiment-ready solution; it does not approve, collect consent/observations, start, analyze, or change solution stage. The legacy submit helper fails before database access, and the console uses exact read/submit grants, acknowledgement, CSRF/no-store, and stable retries. The 98-test focused Gateway/console/route/legacy/migration selection (one database-backed skip) and eight grouped disposable PostgreSQL 16 apply/replay and privilege checks pass. Candidate and legacy remain untouched; migration 507 is not rolled out. [Write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/507_location_solution_experiment_submission.sql); [Gateway tests](../tests/test_gateway_solution_lifecycle_experiment_submission.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-submission-disposable.json). Checklist: 759 complete / 24 open; classifications remain 31 baseline-retained, 7 deployed, and 28 prepared.

**CAP-035 experiment protocol draft — 20 October 2026:** migration 506 adds an exact-origin Gateway draft action and console form. It requires signed location create scope, active human attribution, an active exact-origin solution at `experiment_ready` or `testing`, and bounded allowlisted protocol input. Exact retries are immutable; no submission, approval, consent collection, observation, execution, analysis, or lifecycle transition is exposed. Legacy direct experiment creation fails closed; runtime and Directus cannot insert or edit protocol fields or delete experiments, while runtime lifecycle updates remain narrow. The 137-test focused Gateway/console/runtime/legacy selection (one skip), Ruff, Python/JavaScript syntax, and disposable PostgreSQL 16 apply/replay checks pass; 11 grouped scope, validation, retry, draft-only, immutability, and privilege checks pass. Candidate and legacy remain untouched and migration 506 is not rolled out. [Write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/506_location_solution_experiment_create.sql); [Gateway tests](../tests/test_gateway_solution_lifecycle_experiment_create.py); [evidence](builds/2026-10-20-recovery/cap-035-solution-experiment-create-disposable.json). Checklist: 758 complete / 24 open; classifications remain 31 baseline-retained, 7 deployed, and 28 prepared.

**CAP-035 promotion-gate definition — 20 October 2026:** migration 505 adds exact-origin, location-scoped immutable gate drafts with four supported stage mappings, bounded criteria and thresholds, independent approval, and retry receipts. The existing location gate list and reviewer projection expose criteria only for the solution origin; linked other-origin criteria remain redacted. The 239-test focused Gateway/console/route-policy/migration and runtime-role selection passes, as do Ruff, Python/inline-JavaScript syntax checks, and disposable PostgreSQL 16 migration apply/replay with ten authorization, privacy, lifecycle, idempotency, and privilege checks. Migration 505 revokes table and column grants for runtime/Directus; the runtime-role bootstrap reapplies the revoke after its broad grants ([write contract](solution-lifecycle-kernel-write-contract.md); [migration](../schemas/postgres/505_location_solution_gate_definition.sql); [tests](../tests/test_gateway_solution_lifecycle_gate_create.py); [disposable evidence](builds/2026-10-20-recovery/cap-035-solution-gate-create-disposable.json)). Candidate and legacy remain untouched. Checklist: 757 complete / 24 open; capability classifications remain 31 baseline-retained, 7 deployed, and 28 prepared; CAP-035 remains prepared pending populated parity, live OIDC/browser acceptance, broader ACL/RLS, recovery, and owner review.

**CAP-035 adoption-program revision lineage — 20 October 2026:** migration 519 adds an exact-location list of independently reviewed redesign decisions and an idempotent action that creates one linked replacement draft per predecessor. The original redesign remains immutable; the new draft must pass submission and independent review before it can become enablement-ready. The private revision relation is non-branching and inaccessible to runtime/Directus directly. The console is create-grant-gated, paged, CSRF/no-store, retry-safe, and location-change guarded. The focused Gateway/route-policy/console/migration selection passes 127 tests; Ruff and Python compilation pass. Disposable PostgreSQL 16 applies/replays migrations 513–519 and passes 42 grouped authorization, lineage, retry, lifecycle, and privilege checks. Candidate and legacy remain untouched; migration 519 is not rolled out. CAP-035 remains prepared pending consent-aware participant events, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-035 owner acceptance ([migration](../../schemas/postgres/519_location_solution_adoption_program_revision.sql); [tests](../../tests/test_gateway_solution_lifecycle_adoption_program_revision.py); [evidence](builds/2026-10-20-recovery/cap-035-adoption-program-disposable.json)).

**Directus hook error-safety note — 20 October 2026:** optional extension handlers now log bounded exception class names for role lookup, workflow-history logging, NOI calculation, and scheduled callbacks, without exception messages. The focused extension checks pass four tests and TypeScript type checking passes. This is log-hygiene evidence only; hook output parity, runtime identity, schedule ownership, and capability classification are unchanged ([implementation](../../extensions/kokonut-hooks/src/error-safety.ts); [evidence](builds/2026-10-20-recovery/directus-hook-error-redaction.json)).

**CAP-038 AI-summary CLI lifecycle note — 20 October 2026:** the standalone
summary CLI validates mode and UUID inputs before database setup, avoids a
discarded connection on generation, and closes query resources on list/verify
failures. Seven mocked/offline checks, Ruff, and compilation pass; no database
or provider was contacted. This does not authenticate the CLI operator, establish
tenant isolation or principal authorization, or accept MAN-CAP-038
([evidence](builds/2026-10-20-recovery/cap-038-ai-summary-cli-lifecycle.json)).

**CAP-038 shared-agent draft cursor note — 20 October 2026:** the shared
synthesis-agent persistence helper now closes its cursor after both successful
and failed insert/fetch paths, and performs commit only after closing the cursor.
The 29-test focused selection passes with fake connections. This does not
establish agent identity, least privilege, or MAN-CAP-038 acceptance
([evidence](builds/2026-10-20-recovery/cap-038-agent-draft-cursor-lifecycle.json)).

**CAP-038 AI-summary digest inspection note — 20 October 2026:** the legacy
`--verify` command now clearly reports that it computes a digest without stored
digest comparison and performs no lifecycle review or status update. Eight
offline CLI checks pass; MAN-CAP-038 acceptance is unchanged
([evidence](builds/2026-10-20-recovery/cap-038-ai-summary-verify-readonly.json)).

**CAP-038 AI-summary list scope note — 20 October 2026:** unfiltered summary
inventory now requires explicit `--all-locations` and omits narrative previews;
location-scoped listing retains its preview. Three offline checks cover scope
preflight, global output minimization, and exact location filtering. This is not
a database authorization boundary and MAN-CAP-038 remains open
([evidence](builds/2026-10-20-recovery/cap-038-ai-summary-list-scope.json)).

**CAP-038 shared-agent source metadata note — 20 October 2026:** `SynthesisAgent`
now rejects source-table metadata outside the same one-to-20 lowercase-identifier
shape enforced by the authenticated draft function. Three fake-connection cases
verify rejection before cursor creation. This does not establish linked evidence,
tenant authorization, or MAN-CAP-038 acceptance
([evidence](builds/2026-10-20-recovery/cap-038-agent-source-table-metadata.json)).

**CAP-038 standalone metadata parity note — 20 October 2026:** the standalone
AI-summary writer now uses the shared 1–20 lowercase-identifier validator too.
Three offline malformed-list cases fail before cursor creation or safety-side
effects; the combined agent/summary/Gateway selection passes 85 tests with nine
database-dependent skips. This remains shape validation, not evidence lineage
or MAN-CAP-038 acceptance
([evidence](builds/2026-10-20-recovery/cap-038-ai-summary-source-metadata-preflight.json)).

**CAP-038 standalone draft write-boundary note — 20 October 2026:** standalone
AI-summary writes reject content above the database's 20,000-character limit
before cursor creation and close the cursor when INSERT or fetch fails without
committing. Three fake-connection regressions pass inside an 88-test focused
agent/summary/Gateway selection with nine PostgreSQL-dependent skips. This does
not establish authenticated CLI access or MAN-CAP-038 acceptance
([evidence](builds/2026-10-20-recovery/cap-038-ai-summary-write-boundary.json)).

**CAP-038 shared draft content-bound note — 20 October 2026:** both shared
agent and standalone AI-summary draft writers reject content over the database
review function's 20,000-character limit before cursor creation. The combined
agent/summary/Gateway selection passes 89 tests with nine PostgreSQL-dependent
skips; no database or provider was contacted. This remains input validation,
not identity or least-privilege acceptance
([evidence](builds/2026-10-20-recovery/cap-038-agent-draft-content-bound.json)).

**ARM64 software-only refresh — 20 October 2026:** current source revision
`1e5bf08a` builds for `linux/arm64` and passes a network-disabled, read-only
QEMU import smoke for the Gateway, Python SDK, 18 JobSpecs, and synthetic RPC
snapshot. This does not certify physical hardware, current-schema replay,
resource endurance, power-loss behavior, or 24-hour recovery
([evidence](builds/2026-10-20-recovery/arm64-kernel-current-source-smoke.json)).

**CAP-038 declared-source alignment — 20 October 2026:** two legacy synthesis
agents no longer list tables their query paths do not read. A focused regression
pins the bio-factory and stakeholder-feedback metadata; 91 agent/summary/Gateway
tests pass with nine PostgreSQL-dependent skips. This does not provide row-level
provenance or close MAN-CAP-038
([evidence](builds/2026-10-20-recovery/cap-038-source-metadata-query-alignment.json)).

**CAP-038 wellbeing source alignment — 20 October 2026:** the Wellbeing
Synthesis Agent now declares its directly queried `stakeholder_feedback`
aggregation source. The focused combined agent/summary/Gateway selection passes
92 tests with nine PostgreSQL-dependent skips; Ruff and compilation pass. This
aligns metadata only and does not establish row-level provenance or close
MAN-CAP-038 ([evidence](builds/2026-10-20-recovery/cap-038-wellbeing-source-metadata.json)).

**CAP-047 freshness CLI preflight — 20 October 2026:** standalone and unified
data-freshness help and invalid argument combinations now return before
loading secret-bearing database configuration. The 37-test freshness suite,
Ruff, compilation, and diff checks pass, including a fresh-process import
check. This is an offline
CLI usability boundary only; it does not
change alert routing, retention, runtime recovery, or MAN-CAP-047 acceptance
([evidence](builds/2026-10-20-recovery/freshness-cli-offline-preflight.json)).

**CAP-039 ingestion help isolation — 20 October 2026:** every one of the 19
mounted ingestion modules returns parser help with `KOKONUT_ENV=production`, no
database identity, and an unavailable SOPS age key. The subprocess regression,
Ruff, and compilation pass. This closes only help/import configuration
preflight; non-help CLI parity and MAN-CAP-039 review remain open
([evidence](builds/2026-10-20-recovery/cap-039-ingestion-help-isolation.json)).

**CAP-039 ingestion status read parity — 21 October 2026:** `log`, `indexers`,
and `summary` now have synthetic standalone/unified output parity. Log filters
are bound parameters, persisted diagnostics are redacted, and all three status
reads close fake connections after query failure. Nine focused tests, Ruff,
and compilation pass; no database or provider was contacted. This is a mocked
read-path contract, not populated-data or authorization
acceptance ([evidence](builds/2026-10-21-recovery/cap-039-ingestion-status-cli-parity.json)).

**CAP-039 device manager read CLI parity — 21 October 2026:** standalone and
unified `device_manager --list` and `--health` outputs match using synthetic
query results. Both SQL operations bind the requested location, invalid scope
fails before DB setup, and successful paths close their resources. Ten focused
tests, Ruff, and compilation pass; no database/provider was contacted. Device
registration writes, populated-data parity, and authorization remain open
([evidence](builds/2026-10-21-recovery/cap-039-device-manager-read-cli.json)).

**CAP-039 device registration transaction — 21 October 2026:** device
registration now commits the device and initial health row together, and rolls
back when health initialization fails. Standalone/unified registration
argument and output parity passes; the focused device-manager service/CLI
selection passes 29 tests, Ruff, and compilation with mocked database
interactions. This does not verify live PostgreSQL or authorization
([evidence](builds/2026-10-21-recovery/cap-039-device-manager-registration-atomicity.json)).

**CAP-039 sensor inventory CLI parity — 21 October 2026:** standalone and
unified sensor inventory/calibration reads produce matching synthetic output,
bind the selected location, and close their cursors/connections. Missing or
malformed scope on inventory listing fails before DB setup. Nine focused tests,
Ruff, and compilation pass; no database/provider was contacted. Single-reading,
CSV, and scheduled-driver forwarding are checked with stubbed operations;
ingestion effects/output and scheduled-driver runtime remain open
([evidence](builds/2026-10-21-recovery/cap-039-sensor-inventory-cli-parity.json)).

**CAP-039 climate data CLI dispatch — 21 October 2026:** all six climate
operation selectors preserve standalone/unified JSON receipts and location
forwarding with stubbed operations; conflicting selectors fail before DB
setup. Eight focused tests, Ruff, and compilation pass; no database/provider
was contacted. Provider retrieval and persistence remain open
([evidence](builds/2026-10-21-recovery/cap-039-climate-data-cli-parity.json)).

**CAP-039 remote-sensing CSV parity — 21 October 2026:** single-location and
explicit aggregate CSV modes match across standalone/unified entrypoints with
synthetic plot mapping and stubbed persistence. The location query is scoped,
aggregate mode requires `--all-locations`, and the checks verify logs and
cleanup. Two focused tests pass with Ruff and compilation; no database/provider
was contacted. Live writes and aggregate-operation authorization remain open
([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-csv-cli-parity.json)).

**CAP-039 remote-sensing job-list read — 21 October 2026:** the location-scoped
fetch-job list now has standalone/unified JSON parity with synthetic rows,
bound location SQL, cleanup, and missing/invalid scope preflight. Five focused
tests, Ruff, and compilation pass; no database/provider was contacted. Job
provider execution and worker recovery remain open
([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-job-list-parity.json)).

**CAP-039 remote-sensing job creation — 21 October 2026:** job creation now
validates positive cadence before database setup and keeps the insert in a
rollback-safe transaction with explicit cursor cleanup. Standalone/unified
arguments and JSON receipts match. The combined fetcher/scheduler selection
passes 38 tests with Ruff and Python compilation; all DB behavior is synthetic
and no provider was contacted. Provider execution, lease/retry recovery, live
authorization, and MAN-CAP-039 review remain open. Checklist: 832 complete /
25 open; capability classifications remain 31 baseline-retained, 7 deployed,
and 28 prepared ([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-job-create-contract.json)).

**CAP-039 remote-sensing fetcher cursor cleanup — 21 October 2026:** active-job
queries, exact job lookups, job lists, and stored/plot-derived bbox reads now
close cursors on query and result-fetch failures. Ten synthetic cases pass in
the focused 82-test fetcher/scheduler/automation selection with Ruff and
compilation; no database/provider was contacted. Live authorization, provider
execution, and worker recovery remain open. Checklist: 833 complete / 25 open;
matrix classifications remain 31 baseline-retained, 7 deployed, and 28
prepared ([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-fetcher-cursor-cleanup.json)).

**CAP-039 remote-sensing manual job run — 21 October 2026:** `--job-id` now
validates as a UUID before DB setup. Standalone/unified execution binds the
same location-scoped record and returns matching output with provider
execution stubbed; malformed IDs fail offline. Five manual-path checks pass in
the 87-test fetcher/scheduler/automation selection with Ruff and compilation.
No database/provider was contacted. Live authorization, provider output, and
worker recovery remain open. Checklist: 834 complete / 25 open; matrix remains
31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-manual-run-contract.json)).

**CAP-039 remote-sensing write cursor cleanup — 21 October 2026:** status
updates and provider-attempt inserts now close cursors when SQL execution
fails, without taking transaction control from the caller. Two synthetic
regressions pass in the 89-test fetcher/scheduler/automation selection with
Ruff and compilation; no database/provider was contacted. Live write behavior
and worker recovery remain open. Checklist: 835 complete / 25 open; capability
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-write-cursor-cleanup.json)).

**CAP-039 current-weather query cleanup — 21 October 2026:** current-weather
ingestion closes its database connection if location discovery fails, preserves
the primary query error if close also fails, and logs only the close exception
class. Three synthetic failure cases pass in the 37-test current-weather and
forecast selection with Ruff and compilation; no database/provider was
contacted. Live database and provider behavior remain open. Checklist: 836
complete / 25 open; matrix classifications remain 31 baseline-retained, 7
deployed, and 28 prepared ([evidence](builds/2026-10-21-recovery/cap-039-weather-location-query-cleanup.json)).

**CAP-039 current-weather CLI parity — 21 October 2026:** single-location and
explicit aggregate reads match across standalone/unified entrypoints with
synthetic empty query results. Location UUIDs are canonicalized/bound; malformed
scope fails before DB setup; logs and cleanup match, and no provider is
contacted. Four focused parity/preflight tests pass in the 41-test
weather/forecast selection with Ruff and compilation. Populated parity, live
provider behavior, authorization, and MAN-CAP-039 review remain open. Checklist:
837 complete / 25 open; capability classifications remain 31 baseline-retained,
7 deployed, and 28 prepared ([evidence](builds/2026-10-21-recovery/cap-039-weather-cli-parity.json)).

**CAP-039 weather-forecast CLI parity — 21 October 2026:** canonical
single-location and explicitly selected aggregate reads now match across
standalone/unified entrypoints with synthetic empty results. Bound scope, logs,
and cleanup match; malformed location IDs fail before DB setup. Four focused
forecast parity/preflight tests pass within the 45-test weather/forecast
selection with Ruff and compilation; no database/provider was contacted.
Populated parity, live provider behavior, authorization, and MAN-CAP-039 review
remain open. Checklist: 838 complete / 25 open; capability classifications
remain 31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-weather-forecast-cli-parity.json)).

**CAP-039 data-freshness summary CLI — 21 October 2026:** the global summary
has matching standalone/unified JSON output on synthetic view rows. Query/fetch
failures close both cursor and connection. Five focused cases pass in the 42-test
freshness selection with Ruff and compilation; no database/provider was
contacted. Populated view parity, global operator/privacy boundary, and alert
delivery remain open. Checklist: 839 complete / 25 open; classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-data-freshness-summary-cli.json)).

**CAP-039 data-freshness helper cursor cleanup — 21 October 2026:** helper-owned
configuration, location, ingestion-time, alert-state, alert-history, delivery,
and check-result cursors close on SQL/fetch failure. Seventeen synthetic cases
pass in the 59-test freshness/telemetry selection with Ruff and compilation; no
database/provider was contacted. Transaction orchestration SAVEPOINT cursors,
live authorization, global-summary privacy, and alert delivery remain open.
Checklist: 840 complete / 25 open; classifications remain 31 baseline-retained,
7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-data-freshness-helper-cursor-cleanup.json)).

**CAP-039 data-freshness SAVEPOINT cursor cleanup — 21 October 2026:** the
check orchestration closes SAVEPOINT, rollback-to-savepoint, state/check-update,
and release cursors on failure while retaining the existing rollback behavior.
Five synthetic cases pass in the 64-test freshness/telemetry selection with
Ruff and compilation; no database/provider was contacted. Live database behavior
and authorization remain open. Checklist: 841 complete / 25 open; matrix
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-data-freshness-savepoint-cursor-cleanup.json)).

**CAP-039 data-freshness check CLI dispatch — 21 October 2026:** standalone
and unified `--check --source weather` calls forward matching arguments and
JSON output, with connection cleanup. Invalid source-only use fails before DB
setup. The checker is stubbed, so no query, freshness write, or alert runs. Two
focused cases pass within the 66-test freshness selection with Ruff and
compilation. Actual evaluation, global privacy/authorization, and delivery
remain open. Checklist: 842 complete / 25 open; classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-data-freshness-check-cli.json)).

**CAP-039 anomaly-rule list CLI contract — 21 October 2026:** `--list-rules`
now has standalone/unified output parity on synthetic rows and explicitly
rejects location selectors; its existing query remains global. Five focused
cases pass in the 47-test anomaly selection with Ruff and compilation; no
database/provider was contacted. Populated parity and owner review of global
operator authorization/privacy remain open. Checklist: 843 complete / 25 open;
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared
([evidence](builds/2026-10-21-recovery/cap-039-anomaly-rule-list-cli.json)).

**CAP-039 / CAP-040 market-data CLI entrypoint — 21 October 2026:** the
market-data module now exposes a callable parser used by the unified ingestion
CLI instead of the `runpy` fallback. World Bank and explicit seed arguments and
help output match between entrypoints; dispatcher arguments are restored after
success or failure. Invalid sources and date filters fail before
provider/database access. Thirty-five focused market-data tests and 62
ingestion help/unified CLI checks pass with Ruff and compilation. No provider,
database, schedule, candidate, or legacy service was accessed. This does not
prove populated-data or live-provider parity, close production worker gates, or
accept MAN-CAP-040/047. Checklist: 844 complete / 25 open (869 total); matrix
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_market_data_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-market-data-cli-entrypoint.json)).

**CAP-039 / CAP-040 price-attestation CLI entrypoint — 21 October 2026:**
`price_attestation` now has a callable parser/main path and avoids opening
PostgreSQL when arguments only request help or do not select an operation.
Stubbed manual/daily dispatch closes connections; standalone/unified arguments
and help match. Seven CLI regressions pass within the 50-test price/Oracle
selection and 62 CLI-help/unified checks, with Ruff and compilation. No database
or chain was contacted; populated price lineage and on-chain attestation remain
unverified. Checklist: 845 complete / 25 open (870 total); classifications
remain 31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_price_attestation_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-price-attestation-cli-entrypoint.json)).

**CAP-039 / CAP-040 GIS import CLI entrypoint — 21 October 2026:** the GIS
import module now has a callable parser/main used by unified dispatch.
Standalone/unified file/target arguments and help match; missing file and
invalid-target invocations fail before import. Six CLI cases pass within the
40-test GIS/geospatial selection, with Ruff and compilation. The importer was
stubbed; no file or database was accessed. This confirms parser dispatch only,
not populated spatial-data parity. Checklist: 846 complete / 25 open (871
total); classifications remain 31 baseline-retained, 7 deployed, and 28
prepared ([tests](../tests/test_gis_import_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-gis-import-cli-entrypoint.json)).

**CAP-039 / CAP-040 HTTP sensor-receiver CLI entrypoint — 21 October 2026:**
the HTTP receiver now has a callable parser/main. Standalone/unified host and
port arguments and help match; non-integer ports fail before server startup.
Five CLI cases pass within the 79-test HTTP/IoT/outbox selection with Ruff and
compilation. Server startup was stubbed; no socket or database was accessed.
This does not establish authenticated sensor transport or live listener
recovery. Checklist: 847 complete / 25 open (872 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_http_sensor_receiver_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-http-sensor-receiver-cli-entrypoint.json)).

**CAP-039 / CAP-040 MQTT subscriber CLI entrypoint — 21 October 2026:** the
MQTT subscriber now has a callable parser/main. Standalone/unified broker and
port arguments and help match; non-integer ports fail before startup. Five CLI
cases pass within the 91-test MQTT/IoT/outbox selection with Ruff and
compilation. Subscriber startup was stubbed; no broker or database was
contacted. This is CLI dispatch coverage, not MQTT delivery acceptance.
Checklist: 848 complete / 25 open (873 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_mqtt_subscriber_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-mqtt-subscriber-cli-entrypoint.json)).

**CAP-039 / CAP-040 EAS indexer CLI entrypoint — 21 October 2026:** the EAS
indexer now has a callable parser/main. Standalone/unified chain arguments and
help match; unsupported chains fail before dispatch. Five CLI cases pass in the
41-test recovery/redaction/outbox selection with Ruff and compilation. The
indexer was stubbed; no chain or database was contacted. This is command
dispatch coverage and does not prove live EAS ingestion or cursor recovery.
Checklist: 849 complete / 25 open (874 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_eas_indexer_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-eas-indexer-cli-entrypoint.json)).

**CAP-039 / CAP-040 Gnosis indexer CLI entrypoint — 21 October 2026:** the
Gnosis indexer now has a callable parser/main. Standalone/unified block interval
and help match; invalid values and ranges fail before provider/database setup.
Nine CLI cases pass in the 53-test recovery/redaction/outbox selection with
Ruff and compilation. Provider and database effects were stubbed or rejected.
This does not establish live chain reorg/recovery behavior. Checklist: 850
complete / 25 open (875 total); classifications remain 31 baseline-retained,
7 deployed, and 28 prepared ([tests](../tests/test_gnosis_indexer_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-gnosis-indexer-cli-entrypoint.json)).

**CAP-039 / CAP-040 mock-sensor CLI entrypoint — 21 October 2026:** the demo
sensor generator now has a callable parser/main. Setup/generate/cleanup actions
and help dispatch match; no-action invocation displays help without calling a
demo operation. Nine CLI cases pass in the 81-test mock-sensor/IoT/outbox
selection. Ruff and compilation pass after removing unused imports/assignments.
All demo actions were stubbed; no records or alerts were created/deleted.
Checklist: 851 complete / 25 open (876 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([tests](../tests/test_mock_sensors_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-mock-sensors-cli-entrypoint.json)).

**CAP-039 price-attestation input contract — 21 October 2026:** manual price
attestation now rejects non-positive/non-finite prices, blank commodity/source,
and daily/manual option conflicts before PostgreSQL setup; the shared write
function also validates its inputs before opening a cursor. Daily processing
preserves an explicit zero confidence instead of coercing it to full confidence.
The focused CLI, daily-attestation, and provider-error selection passes 35
tests; Ruff and Python compilation pass. All persistence/provider behavior was
stubbed or guarded, so no database, chain, or external provider was contacted.
This closes invalid-input preflight only; live price lineage, persistence,
authorization, and on-chain attestation remain unverified. Checklist: 855
complete / 25 open (880 total); classifications remain 31 baseline-retained,
7 deployed, and 28 prepared
([implementation](../services/ingestion/price_attestation.py);
[tests](../tests/test_price_attestation_cli.py);
[evidence](builds/2026-10-21-recovery/cap-039-price-attestation-cli-entrypoint.json)).

**CAP-039 listener port preflight — 21 October 2026:** the HTTP sensor
receiver and MQTT subscriber CLIs reject ports outside 1–65535 before starting
their listener/client. The MQTT module also keeps `--help` usable when
`MQTT_BROKER_PORT` is malformed, then reports that configuration error before
subscriber startup. The combined listener CLI selection passes 25 tests (11
HTTP, 14 MQTT) with Ruff and Python compilation. No server socket, broker,
database, or provider was accessed. Live listener/authenticated sensor
transport and broker delivery/recovery remain open. Checklist: 855 complete /
25 open (880 total); classifications remain 31 baseline-retained, 7 deployed,
and 28 prepared ([HTTP test](../tests/test_http_sensor_receiver_cli.py);
[MQTT test](../tests/test_mqtt_subscriber_cli.py);
[HTTP evidence](builds/2026-10-21-recovery/cap-039-http-sensor-receiver-cli-entrypoint.json);
[MQTT evidence](builds/2026-10-21-recovery/cap-039-mqtt-subscriber-cli-entrypoint.json)).

**CAP-039 sensor CSV audit scope — 21 October 2026:** sensor CSV processing
now writes every row audit through its existing farm-scoped connection and
passes the canonical `location_id`, covering missing/short rows, invalid numeric
values, unknown sensors, timestamp/read validation rejection, successful reads,
and caught write failures. Raw values and unknown device identifiers stay out of
error messages. The synthetic selection passes 29 tests with Ruff and Python compilation; temporary CSV
fixtures and database/projection mocks were used, with no live database or
provider access. This verifies call-site scope and cleanup, not live RLS or
populated import parity. Checklist: 856 complete / 25 open (881 total);
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared
([implementation](../services/ingestion/sensor_ingester.py);
[tests](../tests/test_sensor_ingester_csv_audit_scope.py);
[evidence](builds/2026-10-21-recovery/cap-039-sensor-csv-audit-scope.json)).

**CAP-039 ingestion CLI contract inventory — 21 October 2026:** the unified
CLI contract now names a representative successful non-help invocation for all
19 modules registered in `services.ingestion.cli.TOOLS`, including ingestion
status and Baal indexing, and classifies each command's local, database,
provider, or simulated write boundaries and expected output. A registry-to-inventory regression verifies all 19 names are present; focused
parser, forwarding, output, or preflight regressions cover every mounted module.
The inventory does not claim live provider/database parity or authorization.
MAN-CAP-039 owner acceptance and privileged operator boundaries remain open.
Checklist: 857 complete / 25 open (882 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([contract](unified-cli-kernel-contract.md);
[dispatcher](../services/ingestion/cli.py);
[help tests](../tests/test_ingestion_cli_help_isolation.py)).

**CAP-039 GIS import audit scope — 21 October 2026:** GIS boundary writes and
their ingestion audits now share one connection and transaction. Location rows
scope to themselves; farm and plot rows resolve through their owning location.
Unknown targets receive a fixed failure audit with no location scope. Per-row
geometry update failures recover through a savepoint, and batch failures roll
back while closing the connection. The synthetic GIS selection passes 44 tests
with Ruff and Python compilation; no live database or provider was accessed.
This does not establish populated geometry parity or live tenant/RLS behavior.
Checklist: 858 complete / 25 open (883 total); classifications remain
31 baseline-retained, 7 deployed, and 28 prepared
([implementation](../services/ingestion/gis_import.py);
[tests](../tests/test_gis_import_audit_scope.py);
[evidence](builds/2026-10-21-recovery/cap-039-gis-import-audit-scope.json)).

**CAP-039 sensor reading transaction scope — 21 October 2026:** manual and CSV
sensor-reading rows, audits, and outbox writes now share the caller's
location-scoped transaction. Both EventBus publishes leave commit ownership to
the caller; CSV rows use savepoints so an individual failure does not roll back
earlier accepted rows. Rejected manual readings persist their audit without
creating a reading, while outbox failure rolls back both source and success
audit. Seven new mocked cases pass within a 26-test sensor ingestion/CLI
selection, with Ruff and Python compilation. No database, ClickHouse, or
EventBus was contacted. A synthetic successful manual-reading command also
produces identical output and transactional effects through standalone and
unified entrypoints. Live tenant/RLS behavior and populated sensor parity remain
open. Checklist: 860
complete / 25 open (885 total); classifications remain 31 baseline-retained,
7 deployed, and 28 prepared
([implementation](../services/ingestion/sensor_ingester.py);
[test](../tests/test_sensor_ingester_transaction_audit_scope.py);
[evidence](builds/2026-10-21-recovery/cap-039-sensor-single-audit-scope.json)).


**CAP-038 shared synthesis draft boundary — 21 October 2026:** the ten registered shared `SynthesisAgent` draft paths now route through `services.agents.worker_cli` and the signed worker adapter. The task-key registry is explicit; source queries use a bounded read-only transaction, request lookup occurs before those reads, and exact-location drafts use worker identity. The inventory records zero literal direct DML sites in `services/agents`. The broader CAP-038 regression selection passes 153 tests with nine existing PostgreSQL-dependent skips, with Ruff, Python compilation, Compose YAML parsing, and inventory freshness checks. Stored shared-agent CLI output contains only its draft receipt. This is source and fake-connection evidence only: migrations 529/530 and worker credentials are not deployed; generic source manifests remain table-name hints; replay cannot reconstruct every task-specific output field; runtime DB privilege, populated task parity, and MAN-CAP-038 acceptance remain open ([evidence](builds/2026-10-21-recovery/cap-038-shared-synthesis-signed-writer.json)).


**CAP-038 capital-efficiency synthesis provenance — 21 October 2026:** the capital-efficiency shared agent now attaches bounded source IDs for all four location-filtered published views. It collects exact counts and the first 50 IDs in one repeatable-read snapshot; the signed database function revalidates IDs through the same public-safe views before storing the private manifest. Focused worker, adapter, and agent tests pass (41), Ruff and Python compilation pass, and disposable PostgreSQL 16 applies/replays migration 531 and passes 11 grouped acceptance checks, including rejection of unpublished and other-location rows. Candidate and legacy databases remain untouched; migration 531 and worker credentials are not rolled out. The other generic synthesis agents still have table-name hints without row-level manifests, and this does not establish runtime/Directus least privilege, populated-task parity, or MAN-CAP-038 acceptance ([migration](../schemas/postgres/531_capital_efficiency_synthesis_source_references.sql); [agent](../services/agents/capital_efficiency_agent.py); [disposable evidence](builds/2026-10-21-recovery/cap-038-capital-efficiency-source-references-disposable.json); [batch checks](builds/2026-10-21-recovery/cap-038-capital-efficiency-provenance.json)).


**CAP-038 bio-factory synthesis provenance — 21 October 2026:** the signed bio-factory agent now records bounded references to its four location-filtered published views. The network-wide regional-input catalogue is excluded. The shared base collector runs fixed view queries inside the same repeatable-read transaction as synthesis; migration 532 moves source-view authorization into a migration-owned registry and verifies exact counts and sample IDs against those views. The focused worker, adapter, capital-efficiency, and bio-factory selection passes 53 tests, and Ruff, compilation, refreshed SQL/write-boundary inventories, and matrix validation pass. Disposable PostgreSQL 16 applies/replays migrations 529–532 and passes 12 grouped checks, including registry access denial and migration replay. Candidate and legacy remain untouched; migrations 529–532 and worker credentials are not rolled out. Other generic agents still lack row-level manifests; runtime privilege boundaries, populated parity, and MAN-CAP-038 acceptance remain open ([base contract](../services/agents/base.py); [bio-factory agent](../services/agents/bio_factory_agent.py); [migration](../schemas/postgres/532_registered_agent_source_reference_views.sql); [disposable evidence](builds/2026-10-21-recovery/cap-038-bio-factory-source-references-disposable.json); [batch checks](builds/2026-10-21-recovery/cap-038-bio-factory-provenance.json)). Checklist: 904 complete / 24 open (928 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 regenerative synthesis provenance — 21 October 2026:** the Regenerator shared agent now attaches bounded row IDs for its four location-filtered published views: regenerative outcomes, governance mechanisms assigned to that location, replication assessments, and adaptive stewardship reviews. Global or unassigned governance rows are excluded. Migration 533 registers the views and grants the drafter only `id` and `location_id`; the existing security function rechecks the exact IDs through each public view. The focused worker/agent selection passes 62 tests; Ruff, compilation, current SQL and write-boundary inventories, and matrix validation pass. Disposable PostgreSQL 16 applies/replays migrations 529–533 and passes 13 grouped checks, including cross-location rejection with no partial attachment. Candidate and legacy remain untouched; migration 533 and worker credentials are not deployed. Other synthesis agents still lack row manifests; populated parity, wider runtime privilege boundaries, and MAN-CAP-038 acceptance remain open ([agent](../services/agents/regenerator_agent.py); [migration](../schemas/postgres/533_regenerator_synthesis_source_references.sql); [tests](../tests/test_regenerative_outcomes.py); [disposable evidence](builds/2026-10-21-recovery/cap-038-regenerator-source-references-disposable.json); [batch evidence](builds/2026-10-21-recovery/cap-038-regenerator-provenance.json)). Checklist: 905 complete / 24 open (929 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 shared public-view provenance — 21 October 2026:** a validated static view map now builds bounded exact-location reference queries for Commons, GNH, Financial Resilience, and Open Source Capitalist synthesis. Migration 534 registers fifteen published views and grants the source-reference drafter only `id` and `location_id`; global scaling targets, open-source artifacts, and Green Paper publication status are excluded from farm manifests. The focused worker/agent selection passes 272 tests, Ruff and Python compilation pass, and disposable PostgreSQL 16 applies/replays migrations 529–534 with 16 grouped checks, including all four manifest round-trips, exact view-column privileges, and no direct worker access to source tables. No candidate or legacy database was touched; migration 534 and worker credentials are not deployed. Wellbeing, Feedback, Kokonut Commons, other agent paths, populated parity, and owner acceptance remain open ([collector](../services/agents/base.py); [migration](../schemas/postgres/534_public_synthesis_source_reference_views.sql); [tests](../tests/test_synthesis_source_references.py); [disposable evidence](builds/2026-10-21-recovery/cap-038-public-synthesis-source-references-disposable.json); [batch evidence](builds/2026-10-21-recovery/cap-038-public-synthesis-provenance.json)). Checklist: 906 complete / 24 open (930 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 consent-safe Wellbeing and Feedback provenance — 21 October 2026:** both synthesis agents now reference only consented, public, published rows through `v_public_stakeholder_feedback_summary`; Wellbeing also references its cultural, wellbeing-metric, and participatory-action public views. Raw private feedback aggregates remain outside the manifest. Migration 535 registers the four views and grants the drafter only `id` and `location_id`. The focused worker/agent selection passes 76 tests; Ruff and Python compilation pass; disposable PostgreSQL 16 applies/replays migrations 529–535 with 19 grouped checks, including rejection of a no-consent feedback record and absence of partial manifests. No candidate or legacy database was touched; migration 535 and worker credentials are not deployed. Kokonut Commons shared/global records and remaining agent paths still need scoped reference policy, while populated parity and MAN-CAP-038 owner acceptance remain open ([agents](../services/agents/wellbeing_agent.py); [feedback](../services/agents/feedback_agent.py); [migration](../schemas/postgres/535_consent_safe_wellbeing_feedback_source_views.sql); [tests](../tests/test_synthesis_source_references.py); [disposable evidence](builds/2026-10-21-recovery/cap-038-wellbeing-feedback-source-references-disposable.json); [batch evidence](builds/2026-10-21-recovery/cap-038-wellbeing-feedback-provenance.json)). Checklist: 907 complete / 24 open (931 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 farm-assigned Kokonut Commons provenance — 21 October 2026:** the agent now attaches bounded IDs for anti-capture, redistribution, and algorithmic-redistribution policies assigned to the requested location. Migration 536 registers their published views and grants only `id` and `location_id`. Global federation protocols, participatory-signal experiments, and unassigned policy rows are excluded from farm manifests. The focused worker/agent selection passes 78 tests, Ruff and compilation pass, and disposable PostgreSQL 16 applies/replays migrations 529–536 with 22 grouped checks, including direct source-table denial and exact column grants. Candidate and legacy remain untouched; migration 536 and worker credentials are not deployed. The shared-source contract for network-wide governance remains open, as do populated parity and MAN-CAP-038 owner acceptance ([agent](../services/agents/kokonut_commons_agent.py); [migration](../schemas/postgres/536_location_scoped_kokonut_commons_source_views.sql); [tests](../tests/test_synthesis_source_references.py); [disposable evidence](builds/2026-10-21-recovery/cap-038-kokonut-commons-source-references-disposable.json); [batch evidence](builds/2026-10-21-recovery/cap-038-kokonut-commons-provenance.json)). Checklist: 908 complete / 24 open (932 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 consolidated shared-agent source contracts — 21 October 2026:** a regression now covers all ten shared `SynthesisAgent` classes and requires each mapped view to appear in a bounded query with an exact location bind, caps captured IDs at 50, and validates every class manifest through the signed worker adapter. The focused selection passes 84 tests; Ruff, compilation, runtime SQL, worker source, worker SQL, agent write-boundary, and capability-matrix checks pass. This is a source/mock contract check; migrations 529–536 retain their separate disposable PostgreSQL evidence, and no candidate or legacy database was changed. Populated task parity, worker/runtime deployment, Directus least privilege, and MAN-CAP-038 acceptance remain open ([tests](../tests/test_synthesis_source_references.py); [evidence](builds/2026-10-21-recovery/cap-038-all-synthesis-source-map-contracts.json)). Checklist: 909 complete / 24 open (933 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 registered signed-worker summary types — 21 October 2026:** the worker now permits draft creation only for the four built-in deterministic summaries and ten registered synthesis types. Migration 537 uses a `NOT VALID` check so historical receipts remain available while new unsupported types fail atomically. The offline worker, migration, and agent selection passes 137 tests; Ruff and compilation pass; the disposable PostgreSQL 16 chain applies and replays migration 537 with 23 grouped checks. Runtime SQL and agent write-boundary inventories were refreshed, worker source/SQL inventories remain current, and the matrix validates. No candidate or legacy database was modified; migration 537 is not deployed ([adapter](../services/agents/worker_draft.py); [migration](../schemas/postgres/537_registered_worker_summary_types.sql); [disposable evidence](builds/2026-10-21-recovery/cap-038-registered-worker-summary-types-disposable.json); [batch evidence](builds/2026-10-21-recovery/cap-038-registered-worker-summary-types.json)). Checklist: 910 complete / 24 open (934 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 synthesis worker registry enforcement — 21 October 2026:** the worker function now independently resolves each task through its ten-module registry, checks the concrete registered class and class-declared metadata, and rejects broader catalogue-only write tasks before receipt lookup or database access. The focused selection passes 138 tests; Ruff, compilation, SQL and worker inventories, the write-boundary inventory, and matrix validation pass. No database or provider was used. This is code-level dispatch validation, not deployed runtime identity or least-privilege acceptance ([worker](../services/agents/worker_cli.py); [tests](../tests/test_agent_worker_cli.py); [evidence](builds/2026-10-21-recovery/cap-038-worker-enforces-agent-registry.json)). Checklist: 911 complete / 24 open (935 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.


**CAP-038 Delphi recommendation legacy-path retirement — 21 October 2026:** the agent now returns recommendations as in-memory suggestions, and legacy facilitator/CLI draft, list, approve, and reject methods fail before database access. Recommendation persistence and human decisions use the authenticated, location-scoped CAP-027 Gateway paths. The focused Delphi/Gateway/console selection passes 129 tests; Ruff, compilation, runtime SQL inventory, agent write-boundary inventory, matrix validation, and diff checks pass. No migration or candidate/legacy database change was involved. Other legacy Delphi study/panel paths, live OIDC/browser behavior, populated parity, runtime-role boundaries, and MAN-CAP-038 acceptance remain open ([contract](agent-ecosystem-kernel-contract.md); [tests](../tests/test_delphi.py); [evidence](builds/2026-10-21-recovery/cap-038-delphi-legacy-write-retirement.json)).


**CAP-066 location-derived report scope — 21 October 2026:** the source inventory now recognizes the three Statement of Work child queries as scoped through the exact location-bound parent row whose ID they bind. Detection is conservative: direct function-scope `execute`/`fetchone` flow only, and overwritten/unscoped parent values do not count. Across 94 reports and 176 direct query sites, visible location-scope signals increased from 126 to 129 with no bind-arity mismatches; the report changes from mixed to all-direct-query-visible scope. The 42-test analyzer suite, Ruff, compilation, refreshed query/helper inventories, and matrix check pass. This does not establish database authorization, RLS, runtime execution, or populated report parity ([analyzer](../scripts/report_generator_query_scope_inventory.py); [tests](../tests/test_report_generator_query_scope_inventory.py); [inventory](report-generator-query-scope-inventory.json); [evidence](builds/2026-10-21-recovery/cap-066-parent-row-scope-lineage.json)).


**CAP-039 Delphi suggestion CLI parity — 21 October 2026:** the legacy recommendation command now produces the same in-memory suggestion through standalone and unified entrypoints. The subprocess test uses an invalid database URL and unavailable SOPS identity, confirms caller-supplied actor attribution is omitted, and passes without DB setup. This verifies forwarding and offline behavior only; persisted drafts and human decisions remain on the authenticated CAP-027 Gateway routes ([test](../tests/test_unified_cli_success_contract.py); [evidence](builds/2026-10-21-recovery/cap-039-delphi-suggestion-cli-parity.json)).


**CAP-066 report parent-collection scope — 21 October 2026:** the source analyzer follows direct location-scoped parent result collections into child queries by `id`/`*_id` inside a simple row loop. It recognizes EBF pillar reads through a location-filtered scorecard ID and stakeholder commitment-health reads through location-filtered plans; the latter remains conditional for network-wide calls. Unscoped or replaced collections do not propagate. Across 94 reports and 176 direct query sites, visible location-scope signals increased from 129 to 131 with no bind mismatches. The 44-test analyzer suite, Ruff, compilation, refreshed query/helper inventories, and matrix validation pass. Static source evidence does not establish authorization, RLS, or populated report parity ([analyzer](../scripts/report_generator_query_scope_inventory.py); [tests](../tests/test_report_generator_query_scope_inventory.py); [inventory](report-generator-query-scope-inventory.json); [evidence](builds/2026-10-21-recovery/cap-066-parent-collection-scope-lineage.json)).


**CAP-066 explicit network-report guards — 21 October 2026:** the report source inventory now records direct `require_network_scope(report_type, location_id)` calls separately from bound location filters. Eighteen registered reports explicitly reject farm attribution when they read network-wide sources; their queries remain classified by the existing location-scope rules, so this signal cannot inflate farm-filter coverage. The focused analyzer suite passes 46 tests, Ruff passes, and the generated inventory is fresh. This is a source guard inventory only; it does not prove caller authorization, tenant isolation, view lineage, intended stakeholder audience, or populated report parity ([analyzer](../scripts/report_generator_query_scope_inventory.py); [tests](../tests/test_report_generator_query_scope_inventory.py); [inventory](report-generator-query-scope-inventory.json); [evidence](builds/2026-10-21-recovery/cap-066-network-report-scope-guards.json)).


**CAP-039 mock-sensor count preflight — 21 October 2026:** standalone and unified mock-sensor generation now reject zero and negative `--count` values before dispatch, and the generation function rejects non-positive, non-integer, and boolean counts before opening PostgreSQL. The focused CLI, cleanup, insertion-redaction, and dispatch selection passes 23 tests; Ruff and Python compilation pass. Database access was replaced with fail-on-access stubs. This closes an input-validation defect only; provider parity, schedule transfer, and populated data acceptance remain open ([implementation](../services/ingestion/mock_sensors.py); [tests](../tests/test_mock_sensors_cli.py); [evidence](builds/2026-10-21-recovery/cap-039-mock-sensor-count-preflight.json)).


**CAP-039 mock-sensor setup connection lifecycle — 21 October 2026:** setup now rolls back on failure and closes the connection after both successful and failed registration. Synthetic checks verify commit/rollback/close behavior, including a sensor-type query failure; the focused mock-sensor CLI, cleanup, redaction, and unified dispatcher selection passes 26 tests with Ruff and Python compilation. No PostgreSQL or provider was accessed. This closes local connection lifecycle only and does not establish scheduled worker recovery or provider parity ([implementation](../services/ingestion/mock_sensors.py); [test](../tests/test_mock_sensors_cleanup.py); [evidence](builds/2026-10-21-recovery/cap-039-mock-sensor-setup-cleanup.json)).

**CAP-038 signed source boundary for read-only synthesis — 22 October 2026:** all ten registered shared-synthesis agents and deterministic AI-summary generation now use their dedicated reader identities for read-only runs. Each transaction establishes the signed location context before switching to security-barrier wrappers; read-only mode skips draft receipts and writes. The focused agent/summary selection passes 221 tests with nine existing database-dependent skips; Ruff, compilation, and refreshed runtime SQL inventory pass. This closes shared-runtime fallbacks for these generation paths only; summary listing/digest inspection and non-synthesis agents remain separately scoped. No migration or database was changed, and MAN-CAP-038 remains open ([contract](agent-ecosystem-kernel-contract.md); [evidence](builds/2026-10-22-recovery/cap-038-read-only-agent-source-boundary.json)). Checklist: 951 complete / 24 open (975 total); classifications remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-038 EBF evidence-gap source boundary — 22 October 2026:** the EBF
evidence-gap read now uses the dedicated agent source login with its own
`ebf_scorecard/read` grant. Migration 545 filters the view by database-signed
location scope, exposes only the 11 required key/result columns, revokes stale
raw-view and wrapper grants on replay, and denies writes and source-login
wrapper access. The `ebf-evidence-gap-worker` Compose profile receives only
the isolated source DSN and credential. The focused migration/EBF/worker/task/
profile selection passes 106 tests; Ruff and compilation pass. Disposable
PostgreSQL 16 applies and replays migrations
529–545 with 32 grouped assertions, including exact-location and ungranted-
location denial, cross-resource isolation, raw-view denial, and stale-grant
cleanup. Static worker SQL, function, and boundary inventories were refreshed;
the source-closure and capability checks pass. Candidate and legacy databases
remain untouched, and no production credentials/grants were provisioned. This
does not establish operator authorization for the EBF CLI or universal RLS
([migration](../schemas/postgres/545_signed_ebf_evidence_gap_source.sql);
[worker](../services/agents/worker_cli.py);
[Compose profile](../docker-compose.worker.yml);
[native evidence](builds/2026-10-22-recovery/cap-038-ebf-evidence-gap-source-worker-disposable.json)).
**CAP-013 signed CIDS source boundary — 22 October 2026:** the CIDS export CLI
and agent now use the isolated source login, a transaction-bound
`cids_export/read` grant, and six minimal security-barrier projections from
migration 546. Forced-RLS policies scope the shared view owner to the exact
signed CIDS or existing AI-summary location; public feedback content is never
selected by the worker. The focused selection passes 88 tests and the
network-disabled PostgreSQL 16 replay passes 33 grouped assertions. Candidate
and legacy databases remain untouched; migration 546 and production grants are
not deployed. Populated CIDS output parity, live identity/runtime acceptance,
physical Raspberry Pi checks, and MAN-CAP-013 remain open ([migration](../schemas/postgres/546_signed_cids_export_source.sql);
[worker](../services/agents/worker_cli.py); [native evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-arm64-disposable.json)).

Checklist: 953 complete / 24 open (977 total); classifications remain
30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.

**CAP-038 signed Delphi agent summary source — 22 October 2026:** migration 548 adds a signed exact-location `delphi/read` projection for the facilitator agent. It returns aggregate statistics from consented panel members only, suppresses results below the configured privacy floor, and omits participant tokens and free text. The agent's study and location inputs are validated before its isolated read-only worker connection; the in-memory recommendation carries the location scope. The focused worker/preflight/Delphi/profile selection passes 109 tests, Ruff and compilation pass, runtime SQL and worker inventories are current, and capability validation passes. Disposable PostgreSQL 16 applies/replays through migration 548 with 35 grouped assertions on native AMD64 and ARM64/QEMU. Candidate and legacy remain untouched; migration 548 and worker grants are not deployed. The separate legacy Delphi `live-summary` command and other study/panel paths, populated parity, runtime/operator provisioning, Directus parity, and MAN-CAP-038 acceptance remain open ([migration](../schemas/postgres/548_signed_delphi_agent_summary_source.sql); [agent](../services/agents/delphi_facilitator_agent.py); [native evidence](builds/2026-10-22-recovery/cap-038-delphi-agent-source-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-delphi-agent-source-arm64-disposable.json)). Checklist: 964 complete / 24 open (988 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.


**CAP-038 organic-readiness signed source — 22 October 2026:** the existing organic readiness calculations now run as a registered synthesis task through the signed source worker. Migration 549 supplies location-filtered aliases for the legacy analytics queries and seven ID/location-only provenance views; the compliance checklist exposes only IDs and location for its count, never findings or notes. The focused worker/source/organic selection passes 210 tests, and network-disabled PostgreSQL 16 apply/replay passes eight checks on native AMD64 and ARM64/QEMU. This disposable migration test uses a synthetic location-context function; signature behavior is covered by the separate signed worker-context acceptance. Migration 549 is not on the candidate, which remains at 548; no real worker credential was provisioned. Populated parity, runtime identity and grants, candidate rollout, and MAN-CAP-038 acceptance remain open ([agent](../services/agents/organic_readiness_agent.py); [migration](../schemas/postgres/549_signed_organic_readiness_synthesis_source.sql); [tests](../tests/test_synthesis_source_references.py); [native disposable evidence](builds/2026-10-22-recovery/cap-038-organic-readiness-source-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-organic-readiness-source-arm64-disposable.json)).

**CAP-040 legacy current-weather transaction integrity — 22 October 2026:** the compatibility ingestion path now writes its observation and success audit in the same transaction, isolates each location with a savepoint, and rolls back projection failures atomically. A mocked failure/success batch and an outbox-failure rollback are covered by the 48-test weather/worker/JobSpec-inventory/CLI selection; Ruff and Python compilation pass. No provider or live database was accessed. This does not make legacy replays idempotent or enable the default-off signed worker; persisted schedules, provider parity, and MAN-CAP-040 acceptance remain open ([implementation](../services/ingestion/weather.py); [tests](../tests/test_weather_legacy_atomicity.py); [evidence](builds/2026-10-22-recovery/weather-legacy-transaction-atomicity.json)).

**CAP-040 legacy forecast audit atomicity — 22 October 2026:** the legacy five-day runner now places each location’s forecast persistence, success audit, and completion steps inside one outer savepoint. Audit failure rolls that location back, writes a bounded same-connection failure audit, and allows subsequent farms to proceed. The focused forecast/worker/JobSpec-inventory/CLI selection passes 50 tests with Ruff and compilation; no provider or live database was used. Natural-key upsert is unchanged; schedule ownership, live parity, and MAN-CAP-040 remain open ([implementation](../services/ingestion/weather_forecast.py); [tests](../tests/test_weather_forecast_atomicity.py); [evidence](builds/2026-10-22-recovery/weather-forecast-legacy-transaction-atomicity.json)).

### CAP-047 stale-data notification handler retry boundary — 22 October 2026

The registered `data_stale` handler now has focused acceptance showing that it
uses the isolated notification-enqueue identity and commits outbox intents
before returning to EventBus. Enqueue failure rolls back and propagates so the
durable event can be retried. The formatter keeps Directus optional alongside
webhook and email, with no provider credentials in persisted payloads. The
freshness/event/outbox/migration selection passes 204 tests with Ruff,
compilation, inventory checks, and capability validation. Database/provider
calls were mocked; live delivery and destination ownership remain open. This
does not change capability classifications or close MAN-CAP-047 ([tests](../tests/test_data_freshness_notification_outbox.py);
[evidence](builds/2026-10-22-recovery/freshness-alert-outbox-atomicity.json)).


### CAP-037 independent capacity review decision — 22 October 2026

Migration 558 and the Gateway now make the existing review queue actionable through a separate exact-location `operating_pilot:review` decision route. Approval and rejection apply only to submitted self-reported profiles after checking the active Adelphi location and independent reviewer binding. Rejection requires a reason and preserves the audit record when the owner revises the rejected profile. Exact retries replay while payload changes conflict. The console requires acknowledgement, CSRF, and no-store; runtime and Directus cannot mutate lifecycle status or inspect receipts. The 179-test focused selection and 52-group disposable PostgreSQL acceptance pass; runtime SQL inventory is current at 4,534 execution sites; candidate and legacy remain untouched, so migration 558 is not deployed. CAP-037 remains prepared (`P`) pending remaining item workflows, populated parity, live OIDC/browser acceptance, production ACL/RLS and recovery, privacy/audience review, and accountable-owner acceptance. Checklist: 984 complete / 24 open (1,008 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 entries. See the [write contract](operating-pilot-kernel-read-contract.md), [migration](../schemas/postgres/558_location_operating_pilot_capacity_review_decision.sql), [Gateway tests](../tests/test_gateway_operating_pilot_writes.py), and [disposable evidence](builds/2026-10-22-recovery/cap-037-capacity-review-decisions-disposable.json).

**CAP-037 private demand draft submission — 22 October 2026:** migration 559 and the Gateway add a separate exact-location submit-own action for the operator’s own private demand draft. Signed tenant scope, the active human binding, Adelphi location mapping, row ownership, and draft status are checked before the transition and private retry receipt commit atomically. The focused Gateway, policy, console, and migration-metadata selection passes 114 tests; Ruff, compilation, console JavaScript syntax, requirement-group/provider checks, and capability validation pass. Network-disabled PostgreSQL 16 applies/replays migrations 461–559 with all 54 grouped assertions on native AMD64 and ARM64/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-arm64-disposable.json)). Candidate and legacy remain untouched; migration 559 is not rolled out. Raspberry Pi hardware, performance, power-loss, and 24-hour recovery acceptance remain open. Demand review/fulfillment, populated parity, live OIDC/browser, production ACL/RLS, and accountable-owner acceptance also remain open. Checklist: 985 complete / 24 open (1,009 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 entries.

**CAP-037 independent demand review queue — 22 October 2026:** migration 560 adds a bounded read-only queue for receipt-backed Kernel demand submissions, under the existing exact-location review grant. The function requires signed location scope and a unique active reviewer binding, excludes the reviewer’s own party, and returns only structured work and period fields; descriptions, source references, and submitter identity stay private. The focused Gateway, route-policy, console, and migration-metadata selection passes 138 tests. Network-disabled PostgreSQL 16 applies/replays migrations 461–560 with 56 grouped checks on native AMD64 and ARM64/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-arm64-disposable.json)). Candidate and legacy remain untouched; migration 560 is not rolled out. ARM64 emulation is not Raspberry Pi hardware or performance, power-loss, and 24-hour recovery acceptance. Demand decision/fulfillment, populated parity, live OIDC/browser, production ACL/RLS, and accountable-owner acceptance also remain open. Checklist: 986 complete / 24 open (1,010 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 entries.


**CAP-037 location-scoped work opportunities and claim proposals — 22 October 2026:** Migration 564 adds a bounded `GET /operator/api/operating-pilot/{location_id}/work-opportunities` and an idempotent `POST /operator/api/operating-pilot/{location_id}/work-opportunities/{work_item_id}/claims`, both requiring the separate exact location `operating_pilot:claim_own` grant. The queue is limited to the active Adelphi farm mapping, one active human-party binding, non-assigned open/claimed opportunities and bounded pages; it returns fixed work fields and only the caller’s own claim status, never claim IDs, descriptions, evidence, or other claimants. A claim proposal is self-attributed and atomic; it creates only a `proposed` claim plus the existing selection event and allocation marker, with a private append-only request receipt. Exact retries replay, changed request reuse and duplicate-person claims fail closed, and human review/assignment remains separate. Runtime can execute the two bounded functions but cannot directly read/write claim tables, selection events, or receipts; Directus cannot execute the functions. The focused Gateway, route-policy, console, and migration-metadata selection passes 241 tests; Ruff, Python compilation, inline JavaScript syntax, dependency/provider boundaries, capability validation, runtime SQL inventory (4,558 sites), and `git diff --check` pass. Network-disabled PostgreSQL 16 applies/replays migrations 461–564 and passes all 67 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-work-opportunities-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-opportunities-arm64-disposable.json)). QEMU establishes software portability only, not Raspberry Pi hardware, performance, power-loss, or recovery acceptance. Candidate and legacy are untouched; migration 564 is not rolled out. Roll back by disabling the routes, exact policies, and console panel; retain the additive migration and private receipts if applied. CAP-037 remains prepared (`P`): claim review/allocation, other item workflows, populated parity, live OIDC/browser, production ACL/RLS and recovery, privacy/audience review, and owner acceptance remain open. Checklist: 990 complete / 24 open (1,014 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.
**CAP-037 independent work-claim review — 22 October 2026:** Migration 565 adds an identity-blind bounded queue and independent accept/reject action under exact `operating_pilot:review`; self-review is denied, accepted claims remain unassigned pending a separate allocation action, and append-only private receipts support exact retries. The focused Gateway, policy, console, and migration-metadata selection passes 93 tests. Native PostgreSQL 16 and linux/arm64 Docker/QEMU apply/replay migrations 461–565 with 74 grouped assertions ([native evidence](builds/2026-10-22-recovery/cap-037-work-claim-review-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-claim-review-arm64-disposable.json)). QEMU is software portability evidence only, not Raspberry Pi hardware acceptance. Candidate and legacy remain untouched; migration 565 is not rolled out. CAP-037 remains prepared pending other workflows, populated parity, live OIDC/browser, production ACL/RLS and recovery, privacy/audience review, and owner acceptance. Checklist: 991 complete / 24 open (1,015 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 entries.

**CAP-037 explicit work-claim allocation — 22 October 2026:** Migration 566
adds separate allocate-scoped queue and assignment routes. The queue exposes
claimant names only to operators with the exact location `allocate` grant and
omits private evidence/reasons; unresolved competitors and self-claims are
ineligible. Allocation changes only assignment fields after independent claim
acceptance and leaves lifecycle/review state unchanged. Exact request retries
replay through a private append-only receipt. The focused Gateway, route-policy,
and console selection passes 39 tests; Ruff, Python compilation, and inline
JavaScript syntax pass. Native PostgreSQL 16 and ARM64/QEMU apply/replay through
migration 566 pass 82 grouped assertions ([native evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-arm64-disposable.json)).
QEMU establishes software portability only, not Raspberry Pi hardware. Candidate
and legacy remain untouched; migration 566 is not rolled out. CAP-037 remains
prepared pending other workflows, populated parity, live OIDC/browser, broader
ACL/RLS, recovery, privacy/audience review, and owner acceptance. Checklist:
992 complete / 24 open (1,016 total); matrix remains 30 baseline-retained, 7
deployed, and 29 prepared across 66 entries.

## CAP-037 — Independent resource-request review queue (migration 571)

The reviewer console now has a bounded exact-location queue for receipt-backed Kernel resource submissions. It requires `operating_pilot:review`, signed tenant context, an active human reviewer binding, and the active Adelphi farm mapping. It excludes self-review and receiptless legacy requests and returns only reviewer-authorized request details without requester identity. No decision or fulfillment action is exposed. Focused tests pass 146; disposable PostgreSQL 16 replay and 130 grouped assertions pass on native AMD64 and ARM64/QEMU. Candidate and legacy databases are untouched, and CAP-037 remains prepared. QEMU is software portability evidence only. Checklist: 998 complete / 24 open (1,022 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.

## CAP-037 — Independent resource-request review decisions (migration 572)

Migration 572 and the Gateway/console add a one-time, exact-location approve/reject action for receipt-backed Kernel resource submissions. The database requires signed tenant context, exact review grant, a unique active human-party binding, active Adelphi mapping, independent reviewer, and a linked submitted draft. Rejection has a bounded private reason; exact retries replay, while changed retries and second decisions fail closed. Runtime has function execution only, Directus cannot execute the function, and neither role can directly mutate canonical requests or read decision receipts. This action does not partially allocate or fulfill resources.

Focused Gateway/read/route-policy/console checks pass 254 tests. Network-disabled PostgreSQL 16 migration apply/replay through 572 passes 146 grouped assertions on native AMD64 and ARM64/QEMU. QEMU is software portability evidence only. Candidate and legacy databases remain untouched, migration 572 is not rolled out, and CAP-037 remains prepared (`P`). Checklist: 999 complete / 24 open (1,023 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows. Evidence: [native](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-disposable.json), [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-arm64-disposable.json).

## CAP-037 — Independent resource-request fulfillment confirmation (migration 573)

Migration 573 adds a bounded `operating_pilot:fulfill` queue and independent human confirmation for approved, receipt-backed Kernel resource requests. The database rechecks signed location context, exact grant, active farm mapping, and one active human binding. It excludes requester self-confirmation and legacy rows; the read-only queue exposes neither requester identity nor approval reason. A confirmation closes the approved request, records the fulfiller in a private append-only receipt, preserves the reviewer attribution, and replays exact retries. The route cannot record inventory, expense, or payment evidence. Runtime has execute-only access to bounded functions; Directus cannot invoke them or read receipts, and neither runtime role can directly update the canonical request table.

Focused Gateway, route-policy, console, and migration checks pass 308 tests; network-disabled PostgreSQL 16 applies/replays migrations 461–573 and passes 165 grouped assertions natively and under ARM64/QEMU ([native](builds/2026-10-22-recovery/cap-037-resource-request-fulfillment-disposable.json); [ARM64/QEMU](builds/2026-10-22-recovery/cap-037-resource-request-fulfillment-arm64-disposable.json)). The queue is exercised in a read-only transaction. QEMU is software portability evidence only. Candidate and legacy databases remain untouched; migration 573 is not rolled out. CAP-037 remains prepared (`P`), with populated parity, live OIDC/browser behavior, broader ACL/RLS, production recovery, and owner acceptance open. Checklist: 1,000 complete / 24 open (1,024 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.

**CAP-038 per-task agent source identities — 23 October 2026:** Migration 580 gives EBF, CIDS, and Delphi separate worker DSNs/credentials, SET-only login roles, and read-only roles restricted to one, six, and one projections respectively. The migration removes those capability views from the shared synthesis reader and validates role membership and direct public-relation access. Compose profiles expose only the matching task credential; the worker code checks the matching database login and selects the exact reader role. The focused worker/database/profile/Compose selection passes 109 tests, migration integrity passes 36, and the disposable PostgreSQL 16 source chain passes 40 grouped checks natively and under linux/arm64 QEMU ([migration](../schemas/postgres/580_agent_source_worker_identity_split.sql); [native](builds/2026-10-23-recovery/cap-038-agent-source-principal-split-native-disposable.json); [ARM64/QEMU](builds/2026-10-23-recovery/cap-038-agent-source-principal-split-arm64-disposable.json)). QEMU is software portability evidence only. Candidate and legacy are untouched; worker credentials/grants are not deployed. Exact location-grant provisioning, populated parity, live OIDC/provider/browser acceptance, broader ACL/RLS, recovery, physical Raspberry Pi behavior, and MAN-CAP-038 acceptance remain open. Checklist: 1,006 complete / 24 open (1,030 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 named MAN-CAP checks are accepted.

**CAP-038 isolated AI-summary inspection identity — 23 October 2026:** Migration 581 splits listing/digest inspection from deterministic generation with a signed inspection login and exact NOLOGIN reader role. The list projection remains bounded; the digest view returns metadata, SHA-256, and character length without returning summary content to Python. The inspection reader has direct SELECT grants on the list/digest projections and a direct EXECUTE grant on `public.digest`; the inspection login receives no direct digest-function grant and cannot read raw summary content or deterministic operational source views. The deterministic reader retains its 13 generation views but loses both inspection projections. Focused worker/profile/migration tests pass 128; Ruff, compilation, Compose parsing, worker/runtime inventory freshness, and matrix validation pass. Network-disabled disposable PostgreSQL 16 migration apply/replay through 581 passes 42 grouped assertions natively ([evidence](builds/2026-10-23-recovery/cap-038-summary-inspection-identity-native-disposable.json)); the ARM64/QEMU replay also passes 42 grouped assertions ([ARM64/QEMU](builds/2026-10-23-recovery/cap-038-summary-inspection-identity-arm64-disposable.json)). QEMU is software portability evidence only. Candidate and legacy are untouched; migration and credentials are not deployed. CAP-038 remains prepared; exact grants, populated parity, live provider/browser acceptance, broader ACL/RLS, recovery, physical Raspberry Pi acceptance, and MAN-CAP-038 remain open. Checklist: 1,007 complete / 24 open (1,031 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 named MAN-CAP checks are accepted.


**CAP-038 isolated Organic Readiness source identity — 23 October 2026:** Migration 582 gives Organic Readiness synthesis a separate signed login and a NOLOGIN reader limited to fifteen location-filtered projections; shared synthesis loses those projections. The worker selects the task-specific DSN, credential, and reader role, while its optional Compose profile also provides the separate draft-writer identity. The focused worker/database/profile selection passes 95 tests; Ruff and compilation pass. Disposable PostgreSQL 16 apply/replay through 582 passes 45 grouped assertions natively ([native evidence](builds/2026-10-23-recovery/cap-038-organic-readiness-identity-native-disposable.json)) and under ARM64/QEMU ([ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-organic-readiness-identity-arm64-disposable.json)). The synthetic projections test the real signed scope function against own and foreign locations; QEMU is software evidence only. Candidate and legacy are untouched, and migration 582/credentials are not deployed. CAP-038 remains prepared pending credential/grant provisioning, populated parity, live provider/browser acceptance, broader ACL/RLS, production recovery, physical Raspberry Pi acceptance, and human review. Checklist: 1,008 complete / 24 open (1,032 total); matrix classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows; 0/66 MAN-CAP checks are accepted.


**CAP-038 authenticated agent-task draft attribution — 23 October 2026:** Migration 595 gives the thirteen isolated deterministic/synthesis source logins access to a function-only writer role, not broad worker execution. Draft writes first bind the signed worker ID to a task key derived from the authenticated PostgreSQL login, under the exact location `ai_summary:draft` grant. The reviewer queue reads this private attribution mapping instead of querying the forced-RLS `worker_principal` table; unknown worker drafts are blocked from verification while human rejection remains available. The focused worker/Gateway/console/profile/context selection passes 189 tests. Network-disabled PostgreSQL 16 applies/replays through 595 with 82 grouped assertions on native AMD64 and ARM64/QEMU ([migration](../schemas/postgres/595_agent_task_draft_attribution.sql); [native evidence](builds/2026-10-23-recovery/cap-038-task-draft-attribution-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-task-draft-attribution-arm64-disposable.json)). QEMU is software portability evidence only. Candidate and legacy remain untouched; production credentials/grants and candidate rollout are still pending. CAP-038 remains prepared; MAN-CAP acceptance is still 0/66. Checklist: 1,021 complete / 24 open (1,045 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.

**CAP-038 authenticated agent run attribution in review — 23 October 2026:** Migration 596 exposes the opaque worker request UUID next to the registered task in the review queue. Its location-scoped function joins only the authorized summary/request pair; the reviewer role receives column-only request access and runtime, Directus, and task-writer roles cannot read the receipt table or call the function. Gateway context precedes the query; the console renders the identifier as text. Focused Gateway, console, and migration tests pass 70; Ruff, compilation, and diff checks pass. Network-disabled PostgreSQL 16 applies/replays through 596 with 84 grouped assertions on native AMD64 and ARM64/QEMU ([migration](../schemas/postgres/596_agent_task_run_review_attribution.sql); [native evidence](builds/2026-10-23-recovery/cap-038-agent-run-attribution-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-agent-run-attribution-arm64-disposable.json)). QEMU confirms software portability only, not Raspberry Pi hardware. The UUID identifies the worker request, not the initiating human. Candidate and legacy are untouched; migration 596 and production grants are not deployed. CAP-038 remains prepared and 0/66 MAN-CAP checks are accepted. Checklist: 1,022 complete / 24 open (1,046 total); capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows.

**CAP-038 authenticated operator-request attribution in review — 23 October 2026:** Migration 597 adds an exact-location review wrapper that returns operator attribution only when the immutable Gateway request receipt matches the AI-summary row. It exposes only the operator UUID and request UUID; request hashes, payloads, email, and profile data remain private. The focused Gateway/console selection passes 35 tests, and network-disabled PostgreSQL 16 migration apply/replay passes 86 grouped assertions on native AMD64 and ARM64/QEMU ([migration](../schemas/postgres/597_ai_summary_operator_run_review_attribution.sql); [native evidence](builds/2026-10-23-recovery/cap-038-operator-run-attribution-native-disposable.json); [ARM64/QEMU evidence](builds/2026-10-23-recovery/cap-038-operator-run-attribution-arm64-disposable.json)). Candidate and legacy are untouched. CAP-038 remains prepared; operator attribution does not establish the human who initiated agent tasks.

**CAP-038 agent lifecycle guard and hosted-CI repair — 23 October 2026:** Migration 598 distinguishes a PostgreSQL superuser session from a worker by excluding implicit superuser role membership, while explicit worker sessions/`SET ROLE` and the compatibility marker remain restricted. Its isolated PostgreSQL 16.4 apply/replay check passes nine assertions. Hosted CI #772 found seven stale test contracts; the local fix updates the lifecycle SQLSTATE expectation, regenerates the source inventory, aligns the EBF identity assertion, supplies a valid weather fixture, includes the migration-owned role in restore prerequisites, and removes a brittle report line-number expectation. Focused tests pass 67 with 9 database-only cases skipped; disposable migration acceptance, Ruff, and inventory checks pass ([migration](../schemas/postgres/598_agent_safety_superuser_session_guard.sql); [acceptance](builds/2026-10-23-recovery/agent-safety-superuser-ci-regression.json); [CI correction evidence](builds/2026-10-23-recovery/ci-772-correction-checks.json)). Candidate and legacy remain untouched. CAP-038 remains prepared, and no MAN-CAP acceptance is claimed. Checklist: 1,026 complete / 24 open (1,050 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted.

**Optional Prefect runtime compatibility — 23 October 2026:** The real Prefect 3.8.8 local runner passes 28 focused runtime and existing flow tests covering parallel monitoring submission, metrics-before-dependent-work ordering, JobSpec-derived retries, failure propagation, and deployment-to-flow resolution. The test harness uses temporary local Prefect API/SQLite state with all domain handlers mocked ([tests](../tests/test_prefect_runtime_acceptance.py); [evidence](builds/2026-10-23-recovery/prefect-runtime-acceptance.json)). No production Prefect server, provider, Kokonut database, schedule activation, or dispatcher transfer was exercised. This does not close provider ownership, durable scheduler recovery, or schedule-cutover gates. Checklist: 1,027 complete / 24 open (1,051 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted.


**Shared SMTP transport — 23 October 2026:** Production alert delivery is now selected as SMTP. A dependency-free adapter centralizes outbox email, legacy anomaly email, and health-check mail with verified STARTTLS by default, optional implicit TLS, and explicitly unauthenticated plain mode; invalid SMTP settings do not claim email work, and other outbox channels continue. The focused SMTP/health-check selection passes 38 checks, the full Compose-profile suite passes 19 tests, and five Compose configurations plus Ruff, compilation, shell syntax, dependency groups, provider boundaries, and matrix validation pass. No external SMTP server or candidate/legacy database was contacted. The owner selected auth.kokonut.network for ZITADEL on the same date. SMTP endpoint/secrets, recipient/severity/on-call ownership and ZITADEL issuer/client/test-account configuration remain open. No capability classification or MAN-CAP acceptance changes. Checklist: 1,031 complete / 24 open (1,055 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted. Evidence: [SMTP transport](builds/2026-10-23-recovery/smtp-tls-transport.json).

**CAP-038 human-attribution route inventory — 23 October 2026:** the authenticated AI-summary generation route uses the Gateway session operator and an immutable draft/request receipt (migrations 522/597). The Delphi Gateway route stores facilitator output under the submitting operator and an append-only request receipt (migration 451); it does not execute the facilitator, and the standalone CLI draft is in-memory only with its legacy actor option ignored. No generic OIDC agent-task run route is registered. Existing AI-summary/Delphi route and CLI tests pass 94. This closes the current-source entrypoint inventory only; worker identities, human attribution for future run APIs, live OIDC, least-privilege rollout, and MAN-CAP-038 remain open ([inventory](agent-task-attribution-inventory.md); [evidence](builds/2026-10-23-recovery/agent-human-attribution-source-audit.json)). Checklist: 1,031 complete / 24 open (1,055 total); matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted.

**Worker inventory refresh after CI #774 — 23 October 2026:** hosted CI failed seven saved-report freshness/coverage checks while 9,114 tests and 163 subtests passed. Five generated reports had drifted from current worker sources; the refreshed graph covers 32 roots and 96 files, with 682 function memberships, 936 direct-call edges, and 341 SQL sites. Their five focused test modules pass 35 tests locally, and CI #775 passed on pushed commit `237c7c86`, verifying the repair. This remains source-inventory maintenance rather than release/capability acceptance ([CI evidence](builds/2026-10-23-recovery/ci-774-worker-inventory-refresh.json)). Capability classifications remain 30 baseline-retained, 7 deployed, and 29 prepared; the checklist remains 1,031 complete / 24 open, and 0/66 MAN-CAP checks are accepted.


### CAP-066 source-scope inventory update — 23 October 2026

The report query inventory now traces parent-row scope into Statement of Work and EBF child reads across `try`/`if` branches, with branch-local inference and a negative unscoped-replacement regression. The current static inventory covers 176 direct query sites (131 scope signals, six conditional, zero unresolved); 48 focused tests, Ruff, and generated-inventory validation pass ([evidence](builds/2026-10-23-recovery/report-parent-row-scope-inheritance.json)). This improves the source-review map only. It does not establish tenant authorization, RLS, PostgreSQL behavior, populated-output parity, report-owner acceptance, or MAN-CAP-066. CAP-066 remains prepared; the matrix remains 30 baseline-retained, 7 deployed, and 29 prepared across 66 capabilities, with 0/66 MAN-CAP checks accepted.


### ARM64 software portability evidence — 23 October 2026

The current-source ARM64 app builds and its no-network/read-only import smoke passes; a clean isolated PostgreSQL 16 ARM64/QEMU replay applies all 589 current schemas through migration 598 with zero pending/failed files and no seed/farm data ([schema evidence](builds/2026-10-23-recovery/arm64-qemu-current-schema-598-retry.json); [app evidence](builds/2026-10-23-recovery/arm64-kernel-current-source-smoke-ef0bcf60.json)). This is software-portability evidence only. No Raspberry Pi hardware, power-loss, thermal/performance, endurance, or 24-hour recovery acceptance is claimed; those gates remain open. Capability classifications and MAN-CAP acceptance remain unchanged.

**Candidate migration rollout 552–598 — 23 October 2026:** the candidate and an isolated restored clone now match at 589 applied schema migrations through 598, six seed records, zero pending/failed entries, and 1,486 public relations. A fresh age-encrypted checkpoint was restore-rehearsed before the ordered runner applied the 47 pending migrations; no seed or farm data was added. The candidate app alone was rebuilt/recreated, health is 200, and anonymous farm-activity access is denied with 401/no-store. The checkpoint and stopped recovery volume remain available for local rollback; production/off-host recovery, live OIDC, provider credentials, physical Raspberry Pi, and named MAN-CAP acceptance remain open ([rollout evidence](builds/2026-10-23-recovery/candidate-migrations-552-598-rollout.json)). This advances local deployment state without changing capability classification. Checklist: 1,032 complete / 24 open (1,056 total); classifications remain 30 baseline-retained, 7 deployed, and 29 prepared across 66 rows, with 0/66 MAN-CAP checks accepted.


**Latest local batch — CAP-006 aggregate landscape-reference preflight (23 October 2026):** the explicit-target operator command returns global counts only for corridor-source, corridor-target, and buffer-habitat mismatches, in a repeatable-read/read-only transaction with bounded lock/query timeouts. Four unit checks reject unexpected result shapes; disposable PostgreSQL confirms count accuracy without emitting fixture IDs/names, proves the CLI blocks without a selected target, and rejects a write from the preflight transaction. This enables historical reconciliation but does not rewrite rows or validate the composite FKs. See `docs/refactor/landscape-pollinator-kernel-read-contract.md`, `tests/test_landscape_reference_preflight.py`, and `docs/refactor/builds/2026-10-23-recovery/cap-006-landscape-reference-location-disposable.json`. Checklist: 1,060 complete / 25 open (1,085 total); the matrix remains 26 baseline-retained, 7 deployed, and 34 prepared across 67 rows.

**Latest local batch — CAP-006 energy dashboard calculation parity (23 October 2026):** the signed energy read now includes verified/approved 30-day consumption, production, and net totals, legacy-defined renewable-use share, a seven-day trend, and an advisory fixed-factor carbon estimate. The 59-test Gateway/console/domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. Costs remain withheld because the energy schema has no currency field; populated output and registered-renewable parity remain open. Checklist: 1,063 complete / 25 open (1,088 total); classifications remain 26 baseline-retained, 7 deployed, and 34 prepared across 67 rows. [Evidence](builds/2026-10-23-recovery/cap-006-energy-calculation-parity.json).


**Latest local batch — CAP-006 registered renewable metrics (24 October 2026):** the exact-location energy read now reports active registry entries by fixed renewable type, their registered capacity, annual generation, stored offset values, and legacy-capped generation coverage using reviewed annual consumption. The 59-test energy Gateway/console/domain/route-policy selection, Ruff, Python compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. Stored values remain advisory and populated asset parity is open. Checklist: 1,064 complete / 25 open (1,089 total); classifications remain 26 baseline-retained, 7 deployed, and 34 prepared across 67 rows. [Evidence](builds/2026-10-24-recovery/cap-006-registered-renewable-parity.json).


**Latest local batch — CAP-006 reviewed daily efficiency history (24 October 2026):** the exact-location energy summary now includes up to 12 recent daily efficiency-log rows, filtered to verified/approved status and projected without notes, arbitrary metadata, or unclassified cost-per-unit output. The 59-test Gateway/console/domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. Stored intensity remains advisory and populated record/formula parity is open. Checklist: 1,065 complete / 25 open (1,090 total); classifications remain 26 baseline-retained, 7 deployed, and 34 prepared across 67 rows. [Evidence](builds/2026-10-24-recovery/cap-006-reviewed-efficiency-history.json).


**Latest local batch — CAP-006 active energy source breakdown (24 October 2026):** the exact-location energy summary now reports active energy-source counts and rated capacity by fixed source type, separate from renewable registration details. The 59-test Gateway/console/domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. Populated source parity remains open. Checklist: 1,066 complete / 25 open (1,091 total); classifications remain 26 baseline-retained, 7 deployed, and 34 prepared across 67 rows. [Evidence](builds/2026-10-24-recovery/cap-006-active-energy-source-breakdown.json).


**Latest local batch — CAP-006 currency-safe energy costs (24 October 2026):** migration 604 adds an optional currency code without classifying historic amounts; the database requires valid currency on new or changed costs. Legacy analytics and the signed Gateway keep cost totals grouped by code, and the operator console displays reviewed 30-day sums with unclassified-row counts. A combined total is emitted only when the single currency is complete. The 64-test energy Gateway/console/domain/CLI selection, disposable PostgreSQL apply/replay checks, Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. Candidate and legacy databases remain untouched; migration 604 is not rolled out. Populated cost reconciliation, ACL/RLS, live OIDC/browser, and MAN-CAP-006 remain open. [Contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-energy-cost-currency-disposable.json).

**Latest local batch — CAP-005 cooperative management Kernel summary (24 October 2026):** the first private `cooperative_management:read` route returns location-qualified cooperative/type/status counts, active memberships, shared-asset type/status counts, and booking status counts after signed tenant context. The hidden-by-default operator panel renders only fixed aggregate fields as text; member identity, credentials/KYC, booking detail, financial values, GPS, evidence, and free text stay omitted. Twelve focused Gateway/console/route-policy checks pass; Ruff, Python compilation, JavaScript syntax, runtime SQL inventory, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-005 is prepared, not accepted; profile/credential workflows, populated parity, live OIDC/browser, least-privilege ACL/RLS, privacy review, and MAN-CAP-005 remain open. Checklist: 1,070 complete / 25 open (1,095 total); classifications: 25 baseline-retained, 7 deployed, 35 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](cooperative-management-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-005-cooperative-management-kernel-read.json).

**Latest local batch — CAP-008 signed trend forecast generation (24 October 2026):** the exact-location `POST /operator/api/trends/{location_id}/forecast` route requires `trend_analysis:compute`, OIDC operator authentication, and CSRF. It loads at most 365 verified values from the active metric definition at the requested location, bounds horizon/confidence, persists finite advisory values transactionally, reuses an active ARIMA forecast for identical input/configuration, and supersedes it when verified inputs change. The console exposes generation only for the exact compute grant and reloads the fixed saved projection. The focused 43-test Gateway/console/route-policy selection passes with Ruff, Python compilation, JavaScript syntax, refreshed runtime SQL inventory, and matrix validation. No migration, provider, candidate, or legacy database was used. Scientific/populated-data parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,082 complete / 25 open (1,107 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-forecast-generation.json).

**Previous local batch — CAP-008 saved geostatistical realization summaries (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/realization-summaries` route selects a bounded location-owned run page before aggregating realization point values. It returns method, realization number, counts, mean, standard deviation, min/max, grid resolution, and run time, omitting point values, geometries, seeds, model IDs, and metadata; non-finite values become `null`. The grant-gated console validates method and scope, discards stale responses, and renders text only with advisory labeling. The combined 60-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Per-point values, scientific/populated parity, other geostatistics paths, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,081 complete / 25 open (1,106 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-realization-kernel-summaries.json).

**Previous local batch — CAP-008 saved kriging Kernel summaries (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/kriging-summaries` route selects a bounded page of location-authorized kriging runs before aggregating point predictions and uncertainty. It returns per-run counts and summary statistics only; point records, coordinates, model IDs, metadata, and thresholds are omitted, and non-finite values become `null`. The grant-gated console validates scope, method, page, and numeric fields, suppresses stale requests, and renders text only. The combined 56-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Per-point outputs, numerical/populated parity, other geostatistics paths, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,080 complete / 25 open (1,105 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-kriging-kernel-summaries.json).

**Previous local batch — CAP-008 saved sensor-network design Kernel read (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/sensor-network-designs` route uses exact `geostatistics:read` plus signed tenant context. It returns bounded saved spacing, coverage, sensor-count, gap, and confidence values for the exact location, while omitting notes, IDs, model references, and metadata. The shared console validates scope and finite numeric fields, suppresses stale requests, and renders the fixed projection as text with advisory labeling. The combined 52-test CAP-008 Gateway/console/route-policy selection passes with Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Calculation/populated parity, remaining geostatistics outputs, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,079 complete / 25 open (1,104 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-sensor-network-design-kernel-read.json).

**Previous local batch — CAP-008 saved variogram-model Kernel read (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/variogram-models` route uses exact `geostatistics:read` and signed tenant context. It returns bounded spherical, exponential, Gaussian, and Matérn fit summaries for the requested location, omitting model IDs and metadata; non-finite fields become `null`. The shared console validates the model enum and location/page correlation, suppresses stale requests, renders fixed fields as text, and labels fits advisory. The combined 48-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Numerical/populated parity, remaining geostatistics outputs, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,078 complete / 25 open (1,103 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-variogram-kernel-read.json).

**Latest local batch — CAP-008 cross-validation property mapping (24 October 2026):** only the three explicit soil properties and `ndvi` are accepted; unsupported values fail before database connection and no unknown soil key can fall back to organic carbon. The full 62-test geostatistics module passes with Ruff and compilation; runtime SQL inventory and diff checks pass. No migration or database was used. Checklist: 1,086 complete / 25 open (1,111 total) ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-cross-validation-property-map.json)).

**Latest local batch — CAP-008 leave-one-out metric pairing (24 October 2026):** aggregate cross-validation errors and R-squared now use only successful prediction/observation pairs, even when a middle fold fails. The full 59-test geostatistics module passes with Ruff and compilation; runtime SQL inventory and diff checks pass. No migration or database was used. Checklist: 1,085 complete / 25 open (1,110 total); CAP-008 remains prepared ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-loo-success-pairing.json)).

**Latest local batch — CAP-008 cross-validation variogram scope (24 October 2026):** the legacy runner now binds explicit variogram selection to both requested location and property before loading source points; mismatches return a generic not-found response, and source-point queries remain location-filtered. The full 58-test geostatistics module passes with Ruff and compilation; runtime SQL inventory and diff checks pass. No migration or database was used. This closes source-level cross-location model reuse, not database-role/RLS acceptance. Checklist: 1,084 complete / 25 open (1,109 total); matrix remains 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-cross-validation-model-scope.json)).

**Latest local batch — CAP-008 bounded spatial-block fold diagnostics (24 October 2026):** the exact-location cross-validation response now includes fixed aggregate diagnostics only for spatial-block folds where every block has at least five held-out samples. Source is capped at ten folds and 16 KiB; block IDs, coordinates, point-level actual/predicted values, failure details, and model references remain private. The text-only console validates the bounded response. The 42-test Gateway/console/route-policy selection passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks. No migration, provider, candidate, or legacy database was used. Other geostatistics paths, populated/numerical parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,083 complete / 25 open (1,108 total); matrix classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-spatial-fold-diagnostics.json)).

**Previous local batch — CAP-008 saved spatial cross-validation Kernel read (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/cross-validation` route uses exact `geostatistics:read` plus signed tenant context. It returns bounded spatial-block, leave-one-out, and k-fold error summaries for the exact location, omitting fold-level results, model identifiers, and metadata; non-finite numeric fields become `null`. The grant-gated console validates scope, page, strategy, and fixed numeric fields and renders text only. The combined 44-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Fold diagnostics, other geostatistics outputs, populated/numerical parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,077 complete / 25 open (1,102 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-spatial-cross-validation-kernel-read.json).

**Previous local batch — CAP-008 saved spatial-autocorrelation Kernel read (24 October 2026):** the private `/operator/api/geostatistics/{location_id}/autocorrelation` route uses a separate exact `geostatistics:read` grant and signed tenant context. It returns the newest saved Moran's I, Geary's C, or join-count result per property, with bounded paging and finite numeric fields; narrative interpretation, metadata, IDs, and coordinates are omitted. The separate console panel renders fixed text and labels stored statistics advisory. Thirty-nine focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Other geostatistics outputs, populated/numerical parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,076 complete / 25 open (1,101 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](geostatistics-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-spatial-autocorrelation-kernel-read.json).

**Latest local batch — CAP-008 saved forecast Kernel read (24 October 2026):** a private exact-location `trend_analysis:read` route selects the newest stored forecast for the requested metric. It returns at most 100 forecast values and interval entries, filters intervals to fixed numeric fields, omits model parameters/metadata/IDs/accuracy rows, and preserves status as recorded. The hidden-by-default console validates the response, renders fixed values as text, and labels them advisory. Thirty-two focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Repository tracing found no writer to `time_series_forecast`; forecast generation/persistence, geostatistics paths, populated parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,075 complete / 25 open (1,100 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-saved-forecast-kernel-read.json).

**Latest local batch — CAP-008 saved seasonal decomposition Kernel read (24 October 2026):** a private exact-location `trend_analysis:read` route reads the newest stored decomposition for a selected metric. SQL limits each component array to 200 values before returning it; malformed arrays and non-finite numbers become safe empty/null values, and the response marks truncation. The hidden-by-default console validates the scope and component shape, renders fixed values as text, and labels partial output and advisory status. Twenty-seven focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Forecast/geostatistics paths, populated parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,074 complete / 25 open (1,099 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-seasonal-decomposition-kernel-read.json).

**Latest local batch — CAP-008 stored change-point Kernel read (24 October 2026):** a private exact-location route returns at most 100 saved detections for a metric selected from the authorized estimate list. Signed tenant context precedes the read; IDs, classification text, metadata, and actor details are omitted, and non-finite magnitude/confidence values become `null`. The console validates location/metric correlation, renders fixed values as text, and displays stored status without lifecycle actions. Twenty-two focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Decomposition, forecast/geostatistics paths, populated parity, live OIDC/browser, least-privilege ACL/RLS, audience review, and MAN-CAP-008 remain open. Checklist: 1,073 complete / 25 open (1,098 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-change-points-kernel-read.json).
**Latest local batch — CAP-008 stored trend smoothing Kernel read (24 October 2026):** a private location-scoped route returns at most 100 saved smoothing points for a metric selected from the authorized estimate list. The signed read omits estimator parameters/metadata, converts non-finite values to `null`, and the console validates location and metric correlation before rendering fixed values as text. Seventeen focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks. No migration, provider, candidate, or legacy database was used. Decomposition, change-point/forecast and geostatistics routes, populated parity, live OIDC/browser, least-privilege ACL/RLS, and MAN-CAP-008 remain open. Checklist: 1,072 complete / 25 open (1,097 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-trend-smoothing-kernel-read.json).
**Latest local batch — CAP-008 saved trend estimate Kernel read (24 October 2026):** the first private `trend_analysis:read` endpoint returns the latest stored trend estimate per metric for the exact location, with bounded pagination and signed tenant context. Non-finite numeric values are withheld as `null`; the console validates location/page correlation, renders fixed fields as text, and labels stored outputs advisory. Twelve focused Gateway/console/route-policy checks pass; Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-008 remains prepared pending populated calculation parity, remaining forecast/geostatistics paths, live OIDC/browser, least-privilege ACL/RLS, and MAN-CAP-008. Checklist: 1,071 complete / 25 open (1,096 total); classifications: 24 baseline-retained, 7 deployed, 36 prepared across 67 rows, with 0/67 MAN-CAP checks accepted. See [contract](trend-analysis-kernel-read-contract.md) and [evidence](builds/2026-10-24-recovery/cap-008-trend-estimate-kernel-read.json).

**CAP-027 authenticated study lifecycle transitions — 25 October 2026:** migration 631 adds separate exact-location `delphi:open` and `delphi:close` Gateway actions with signed context and immutable retry receipts. Opening requires at least one question and the configured minimum of consented panel members; closing is one-way and preserves its opening timestamp. The 47-test selected API/route-policy/draft suite passes, and migrations 449–451, 630, and 631 apply/replay on disposable PostgreSQL 16 with six grouped assertions. No candidate or legacy database was touched. Console lifecycle controls, panel/item authoring, contributions, stopping checks, live OIDC/browser, populated parity, universal ACL/RLS, and MAN-CAP-027 acceptance remain open. CAP-027 is still prepared; capability classifications do not change. Checklist: 1,169 complete / 25 open (1,194 total); matrix: 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([contract](delphi-consultation-kernel-contract.md); [migration](../schemas/postgres/631_location_scoped_delphi_study_lifecycle.sql); [evidence](builds/2026-10-25-recovery/cap-027-delphi-study-lifecycle-disposable.json)).

**CAP-027 operator-console study lifecycle controls — 25 October 2026:** the console lists studies only when the same location has `delphi:read` plus `delphi:open` or `delphi:close`, then shows each action only for its corresponding status and grant. It requires explicit confirmation, CSRF/no-store, retry-stable request IDs, and validates the location, study, and resulting status. Six focused lifecycle-console checks pass; the four Delphi study/recommendation console suites pass 19 tests with Node.js syntax validation. No database/provider or live OIDC/browser was used. Questionnaire/panel authoring, contributions, stopping evaluation, live OIDC/browser, populated parity, least-privilege ACL/RLS, and MAN-CAP-027 remain open. CAP-027 stays prepared; classifications do not change. Checklist: 1,170 complete / 25 open (1,195 total); matrix: 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([contract](delphi-consultation-kernel-contract.md); [console](../apps/operator-console/index.html); [tests](../tests/test_operator_console_delphi_study_lifecycle.py); [evidence](builds/2026-10-25-recovery/cap-027-delphi-study-lifecycle-console.json)).

**Latest local batch — C2 SDK path-segment parity (27 October 2026):** both SDKs encode caller-controlled collection and item IDs as single path segments and reject empty/dot-only values before transport. The pinned Directus helper descriptors were verified to interpolate route segments directly. All 98 Python SDK tests and 56 JavaScript SDK tests pass; TypeScript build and static checks pass. No runtime, database, or provider was contacted. This is a transport-correctness subgate and does not change capability classifications or close the broader C2 route/auth/scope, pagination/error, live OIDC, or populated acceptance gates. Checklist: 1,283 complete / 25 open (1,308 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([evidence](builds/2026-10-27-recovery/sdk-path-segment-parity.json)).

**Latest local batch — C2 SDK pagination parity (27 October 2026):** the Python SDK now applies the same merged-option rules as TypeScript: offset is honored only with a limit, valid offset takes precedence over page, and zero-limit offset fails before a request. Full SDK suites (99 Python, 57 JavaScript), TypeScript build, Ruff, compilation, and the 109-model schema-parity checker pass using mocked/no-network checks. This does not change capability classifications or close route/auth, error/runtime, live OIDC, or populated acceptance. Checklist: 1,284 complete / 25 open (1,309 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([evidence](builds/2026-10-27-recovery/sdk-pagination-contract.json)).

**Latest local batch — Currency reference catalog runtime boundary (27 October 2026):** migration 672 keeps `dfs_currency` readable while denying runtime mutation. Native and ARM64/QEMU PostgreSQL checks pass migration replay, table/column denial, provisioner reapplication, and Directus-role preservation. The native full-schema replay through migration 672 passes 28 two-tenant checks, including reading the USD row installed by the finance migration. The refreshed source/ACL report covers 119 policies with zero mismatches and records 1,001 relations with effective DML while RLS is disabled; broad runtime grants and RLS coverage remain open. Three focused regression modules pass 103 tests. No capability classifications or MAN-CAP acceptance changed; physical-device, populated operational data, and production acceptance remain open. Checklist: 1,286 complete / 25 open (1,311 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([migration](../schemas/postgres/672_runtime_dfs_currency_read_only.sql); [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-672-native-disposable.json); [native ACL](builds/2026-10-27-recovery/dfs-currency-runtime-read-only-disposable.json); [ARM64 ACL](builds/2026-10-27-recovery/dfs-currency-runtime-read-only-arm64-disposable.json)).

**Latest local batch — Crop GDD configuration runtime boundary (27 October 2026):** migration 673 keeps `crop_gdd_config` readable to analytics while denying direct runtime mutation. Native and ARM64/QEMU PostgreSQL checks pass apply/replay, table and column denial, provisioner reapplication, and preservation of Directus grants. The native full-schema replay through 673 passes 29 two-tenant checks and proves the runtime can query the relation; no seed files were loaded, so populated GDD values were not tested. The refreshed source/ACL report covers 120 policies with zero mismatches and records 1,000 relations with effective DML while RLS is disabled; C1 remains open. The three focused regression modules pass 104 tests. No capability classifications or MAN-CAP acceptance changed; populated-data, physical-device, and production acceptance remain open. Checklist: 1,287 complete / 25 open (1,312 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([migration](../schemas/postgres/673_runtime_crop_gdd_config_read_only.sql); [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-673-native-disposable.json); [native ACL](builds/2026-10-27-recovery/crop-gdd-config-runtime-read-only-disposable.json); [ARM64 ACL](builds/2026-10-27-recovery/crop-gdd-config-runtime-read-only-arm64-disposable.json)).

**Latest local batch — Pest degree-day configuration runtime boundary (27 October 2026):** migration 674 keeps the schema-defined pest degree-day thresholds readable to analytics while denying direct runtime mutation. Source review confirms `record_degree_day` writes only operational `degree_day_record`; the available pest reference writer targets the separate `pest_biology_reference`, and no service/extension SQL targets the config table. Native and ARM64/QEMU disposable PostgreSQL checks pass migration replay, table/column write denial, provisioner reapplication, and preservation of Directus grants. The native replay applies all 665 schemas through migration 674 and passes 30 two-tenant checks, including reading the `fall_armyworm` default defined in schema migration 149. The source/ACL report covers 121 policies with zero mismatches and 999 relations retaining effective DML while RLS is disabled; broad C1 isolation remains open. The three focused regression modules pass 105 tests. No capability classifications or MAN-CAP acceptance changed; candidate/legacy, physical-device, populated operational, and production acceptance remain open. Checklist: 1,288 complete / 25 open (1,313 total); 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([migration](../schemas/postgres/674_runtime_pest_degree_day_config_read_only.sql); [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-674-native-disposable.json); [native ACL](builds/2026-10-27-recovery/pest-degree-day-config-runtime-read-only-disposable.json); [ARM64/QEMU ACL](builds/2026-10-27-recovery/pest-degree-day-config-runtime-read-only-arm64-disposable.json)).

**Latest local batch — Revenue-multiplier configuration runtime boundary (27 October 2026):** migration 675 keeps the shared `revenue_multiplier_config` readable to the runtime while denying its broad DML privileges. Schema 016 defines the table; seed files 015 and 069 supply its configurable business parameters. The revenue-multiplier service only reads the table and falls back to code defaults; no service or extension writer exists. The migration affects only `kokonut_runtime`, leaving the distinct Directus/admin grant path available. Native and ARM64/QEMU disposable PostgreSQL checks pass table and column mutation denial, provisioner reapplication, and Directus grant preservation. The native full-schema replay applies all 666 schemas and passes 31 two-tenant checks, including a query against the table; optional seeds were not applied, so configured parameter values were absent. The source/ACL report covers 122 policies with zero mismatches and 998 relations still retaining effective DML while RLS is disabled; C1 remains open. The service test module passes 14 tests; the three runtime-role/report/schema-replay modules pass 106 tests. No capability classifications changed; candidate/legacy and production remain untouched, and physical Raspberry Pi acceptance is not claimed. Checklist: 1,289 complete / 25 open (1,314 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([migration](../schemas/postgres/675_runtime_revenue_multiplier_config_read_only.sql); [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-675-native-disposable.json); [native ACL](builds/2026-10-27-recovery/revenue-multiplier-config-runtime-read-only-disposable.json); [ARM64/QEMU ACL](builds/2026-10-27-recovery/revenue-multiplier-config-runtime-read-only-arm64-disposable.json)).

**Latest local batch — Governed reference-class runtime boundary (27 October 2026):** migration 676 keeps `reference_class` readable but denies mutation by `kokonut_runtime`. Prediction comparison only consumes verified/published classes; source review found no service or extension writer. Native and ARM64/QEMU PostgreSQL checks pass migration replay, table/column write denial, provisioner reapplication, and preservation of synthetic Directus grants. The corrected native full-schema replay applies all 667 schemas through 676 and passes 31 two-tenant checks under verified 1.5 GiB/two-CPU limits. The refreshed report covers 123 declared controls with zero policy mismatches and records 997 relations retaining effective DML while RLS is disabled; broad C1 isolation remains open. The combined runtime-role/report/migration/ARM64-parser/SQL-inventory/reference-class/prediction-calibration selection reports 173 passed and one skipped. No seeds or farm data were loaded. Candidate/legacy, live Directus, populated reference-class data, physical-device, and production acceptance remain open. Checklist: 1,290 complete / 25 open (1,315 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows ([migration](../schemas/postgres/676_runtime_reference_class_read_only.sql); [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-676-native-disposable.json); [native ACL](builds/2026-10-27-recovery/reference-class-runtime-read-only-disposable.json); [ARM64 ACL](builds/2026-10-27-recovery/reference-class-runtime-read-only-arm64-disposable.json); [source/ACL report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).

**Latest local batch — SDK export-create lifecycle contract (27 October 2026):** Python and TypeScript `exports.create` now share the public `ExportCreateInput` shape, project only the six request fields, and set `status=pending` and `requested_by=sdk`; runtime-injected lifecycle and server-result fields are discarded. The focused Python SDK and method-parity selection passes 105 tests, JavaScript passes 57 tests, and TypeScript build, Ruff, and Python compilation pass. Mocked clients made no HTTP calls; no database, provider, candidate, or legacy service was used. This closes one static SDK gap only; route authorization and broader runtime parity remain open. No capability classification or MAN-CAP acceptance changed ([evidence](builds/2026-10-27-recovery/sdk-export-create-lifecycle-contract.json)). Checklist: 1,291 complete / 25 open (1,316 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest local batch — Canonical export-log SDK contract (27 October 2026):** the earlier pending-create API was removed after source review found its payload included four columns absent from the canonical table and no worker consumes pending rows. Python and TypeScript now expose read-only `list`/`get` methods and model the ten actual `export_log` columns; file generation remains available through the exporter CLI. The focused Python SDK/method-parity selection passes 100 tests, JavaScript passes 53 tests, and the TypeScript build, 109-model/2,150-column schema guard, Ruff, Python compilation, and diff check pass with mocked clients. An authenticated Gateway request flow, attribution, and durable asynchronous processing remain open. No capability classifications or MAN-CAP acceptance changed ([evidence](builds/2026-10-27-recovery/sdk-export-audit-read-only-contract.json)). Checklist: 1,293 complete / 25 open (1,318 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest local batch — Report snapshot SDK lifecycle boundary (27 October 2026):** Python and TypeScript no longer expose generic create, bulk-create, update, or delete operations for generated report snapshots. The exporter remains the generation path, and the helper provides list/detail/type-filtered reads while snapshot review stays behind its governed lifecycle. The focused Python SDK/method-parity/report-governance selection passes 107 tests; JavaScript passes 53; TypeScript builds; Ruff, compilation, and the 109-model/2,150-column schema guard pass. No database or provider was contacted. Gateway report generation and reviewer transitions remain open, with no capability classification or MAN-CAP acceptance change ([evidence](builds/2026-10-27-recovery/sdk-report-snapshot-read-only-contract.json)). Checklist: 1,294 complete / 25 open (1,319 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest local batch — Kernel release-input lock repair (28 October 2026):** PR #71 CI failed because the OIDC Dockerfile dependency change did not update its locked input hash. The lock now includes the current `Dockerfile.kernel` and both `requirements/oidc.txt` and `requirements/http-client.txt` hashes. The local release-input check and 36 focused Kernel profile/release-gate tests pass; hosted Security passed on the failed head. The repair still needs a fresh hosted CI run, and no OCI build was performed. Capability and MAN-CAP statuses are unchanged ([evidence](builds/2026-10-28-recovery/ci-kernel-release-lock-repair.json)). Checklist: 1,297 complete / 25 open (1,322 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest local batch — Calculated NOI snapshot SDK boundary (27 October 2026):** Python and TypeScript no longer expose generic create, bulk-create, update, or delete operations for `noi_snapshot`. The table stores calculated outputs, source inputs, calculation version, and timestamp; repository search found no SDK mutation callsites. Both SDKs preserve list/detail/crop-cycle reads; existing CLI, signed-worker, and Directus-extension writer paths were not changed or runtime-validated here. Focused Python SDK/parity/report-governance checks pass 111 tests; JavaScript passes 55; TypeScript build, Ruff, and Python compilation pass. No database/provider was contacted. This does not establish tenant isolation or change capability/MAN-CAP status ([evidence](builds/2026-10-27-recovery/sdk-noi-snapshot-read-only-contract.json)). Checklist: 1,296 complete / 25 open (1,321 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

**Latest local batch — Attestation record SDK lifecycle boundary (27 October 2026):** Python and TypeScript no longer expose generic create, bulk-create, update, or delete operations for `attestation_record`. The table stores governed workflow rows and chain-indexer projections; direct insertion cannot publish or independently verify an EAS attestation. Both SDKs retain list/detail, pending-state, and subject-filtered reads, while publishing and revoking remain in the dedicated EAS service and governed signing workflow. The workflow examples now read indexed records. Focused Python SDK/parity/report-governance checks pass 109 tests; JavaScript passes 54; TypeScript build, Ruff, and Python compilation pass. No database/provider was contacted. This does not add a Gateway attestation-request workflow or change capability/MAN-CAP status ([evidence](builds/2026-10-27-recovery/sdk-attestation-read-only-contract.json)). Checklist: 1,295 complete / 25 open (1,320 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


**Latest local batch — Market reference data runtime ACL (28 October 2026):** Migration 678 and runtime provisioning keep `market_reference_data` readable but immutable to `kokonut_runtime`, preserving the separate Directus administration grants. Native and ARM64/QEMU disposable PostgreSQL checks pass migration replay, SELECT, mutation/column denial, provisioner reapplication, and synthetic Directus grant preservation. A fresh native schema replay through 678 passes all 33 two-tenant checks and 125 declared runtime controls; the source/ACL report has zero mismatches. Of 1,511 relations, 995 retain effective DML while RLS is disabled, so C1 remains open. Candidate/legacy databases remain untouched, and QEMU is not physical Raspberry Pi evidence. No capability classification or MAN-CAP acceptance changed ([migration](../schemas/postgres/678_runtime_market_reference_data_read_only.sql); [native replay](builds/2026-10-28-recovery/runtime-role-full-schema-678-native-disposable.json); [focused ACL checks](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-disposable.json)). Checklist: 1,298 complete / 25 open (1,323 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


**Latest local batch — Quantity unit catalog runtime ACL (28 October 2026):** Migration 679 and runtime provisioning keep the schema-seeded `quantity_unit` table readable but immutable to `kokonut_runtime`, preserving Directus administration. Focused native and ARM64/QEMU PostgreSQL checks pass migration replay, SELECT, table/column write denial, provisioner reapplication, and synthetic Directus grant preservation. A fresh native schema replay through 679 passes 34 two-tenant checks and 126 runtime controls; the refreshed source/ACL report has zero mismatches. Of 1,511 relations, 994 retain effective DML while RLS is disabled, so C1 remains open. Candidate/legacy databases are untouched, and QEMU is not physical Raspberry Pi evidence. Capability classifications and MAN-CAP acceptance are unchanged ([migration](../schemas/postgres/679_runtime_quantity_unit_read_only.sql); [native replay](builds/2026-10-28-recovery/runtime-role-full-schema-679-native-disposable.json); [focused ACL checks](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-disposable.json)). Checklist: 1,299 complete / 25 open (1,324 total); classifications remain 24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


**Latest continuation — geostatistics and pollinator detail contracts (28 October 2026):** Seven remaining private geostatistics GET routes now publish strict schemas for cross-validation, variograms, sensor-network designs, kriging summaries/points, and realization summaries/points; together with the earlier autocorrelation route, all eight saved geostatistics GET routes now validate fixed projections and request identity. Pollinator review queue, habitat, and hive details now expose strict response contracts, including a record-type-discriminated review-detail union. These contracts preserve existing location grants and no-store error behavior. Geostatistics summary and point readers, plus pollinator detail/review readers, stop advertising pages beyond offset 10,000. The combined focused selection passes 158 tests. Two conservative SQL-inventory `WITH` candidates were source-reviewed as SELECT-only; their fingerprints were moved to the explicit reviewed ledger without approving ACLs or changing grants, and the total remains 37. Ruff, Python compilation, capability validation, inventory checks on Python 3.11/3.12, and diff checks pass. No live database/provider, candidate, or legacy service was used. Populated-data parity, live OIDC/browser behavior, and broader tenant isolation remain open ([evidence](builds/2026-10-28-recovery/gateway-geostatistics-pollinator-response-contracts.json)). The matrix now records 38 strict private Gateway response endpoints across 67 rows: 24 baseline-retained, 7 deployed, and 36 prepared; capability classifications and MAN-CAP acceptance are unchanged.

**Latest local batch — public projections and read-only SDK/CLI guardrails (29 October 2026):** The public governance cockpit now selects migration 249's six explicit aggregate/privacy columns. Python and JavaScript REST SDK generic CRUD rejects writes to report, NOI, attestation, and export audit projections while preserving their reads and writes to unrelated collections. Report snapshot verification rejects malformed UUID/hash inputs before opening PostgreSQL and uses separate UUID and SHA-256 query predicates. Focused mock checks pass for all three source contracts, including snapshot cursor cleanup; no database, provider, or live service was contacted. This does not establish populated report parity, tenant isolation, or capability/MAN-CAP acceptance ([evidence](builds/2026-10-29-recovery/kernel-public-read-and-verify-preflight.json)).

**Latest source continuation — Data Stream signer CLI batch bound (29 October 2026):** `data-stream process --limit` now accepts 1–100 only and rejects invalid values before handler/database access; valid boundary values pass through unchanged. Nineteen focused mock checks pass with Ruff and Python compilation. No chain/provider/database is contacted. This is CLI guardrail evidence only and does not establish signing-provider behavior or capability/MAN-CAP acceptance ([evidence](builds/2026-10-29-recovery/datastream-signer-cli-batch-bound.json)).
