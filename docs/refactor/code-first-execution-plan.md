**Latest local batch — CAP-008 empirical lag search contract (24 October 2026):** empirical variograms now use fixed-width `lag_distance` bins, centered `lag_tolerance` selection, and `bandwidth` as a maximum pair-separation cap, while retaining the legacy half-of-maximum-observed-distance cap. Each bin reports mean selected-pair distance and Matheron semivariance with matching pair counts; empty bins are omitted. The CLI exposes all three parameters and rejects invalid values before database access. Hand-calculated synthetic cases cover exact bins, tolerance, bandwidth, and pair counts. The 84-test geostatistics module passes with Ruff, compilation, dependency-group alignment, regenerated/current SQL inventory, and matrix validation. SciPy is explicit in the analytics group for the direct import and was already required transitively by GSTools. No migration or database was used. CAP-008 remains prepared pending scientific/populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-empirical-lag-contract.json)).

**Latest local batch — CAP-008 variogram fitting optimization (24 October 2026):** variogram fitting now uses GSTools' robust nonlinear optimizer instead of returning initial estimates. Invalid/non-finite empirical bins are filtered, and fitted parameters/R-squared must be finite. Synthetic curves recover known sill, range, and nugget values for spherical, exponential, Gaussian, and Matérn models; Matérn smoothness stays at its GSTools default because the schema does not persist it. The 78-test geostatistics module passes; Ruff, compilation, runtime SQL inventory check, and matrix validation pass. No migration or database was used. CAP-008 remains prepared pending scientific/populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-variogram-fit-optimization.json)).

**Latest local batch — CAP-008 shared geostatistics source queries (24 October 2026):** variogram fitting, autocorrelation, kriging, simulation, and cross-validation now share fixed location/property queries. Only `soil_carbon`, `soil_moisture`, `soil_ph`, and `ndvi` are accepted; soil keys map to fixed columns, unsupported input fails before database connection, and explicit kriging/simulation variogram IDs must match location and property. The full geostatistics module passes 73 tests; changed-file Ruff, compilation, refreshed runtime SQL inventory/check, and matrix validation pass. No migration or database was used. CAP-008 remains prepared pending scientific/populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-geostat-source-scope.json)).

**Latest local batch — CAP-008 cross-validation property mapping (24 October 2026):** the runner now accepts only `soil_carbon`, `soil_moisture`, `soil_ph`, or `ndvi`. Soil properties map to explicit columns rather than falling back to organic carbon for unknown `soil_*` keys, and unsupported input fails before database access. The full geostatistics test module passes 62 tests; Ruff, compilation, runtime SQL inventory, and diff checks pass. No migration or database was used ([evidence](builds/2026-10-24-recovery/cap-008-cross-validation-property-map.json)).

**Latest local batch — CAP-008 leave-one-out metric pairing (24 October 2026):** leave-one-out cross-validation now accumulates actual values only alongside successful predictions, so a failed middle fold no longer shifts subsequent prediction/observation pairs. All summary errors and R-squared use the same successful observations. The full geostatistics test module passes 59 tests with Ruff, compilation, refreshed runtime SQL inventory, and diff checks; no database or migration was used ([evidence](builds/2026-10-24-recovery/cap-008-loo-success-pairing.json)).

**Latest local batch — CAP-008 cross-validation variogram scope (24 October 2026):** the legacy cross-validation runner now requires an explicitly selected variogram's ID, location, and property to match the requested analysis before it reads sample points. Mismatches return a generic not-found response, while soil and remote-sensing points retain exact-location filters. The full geostatistics module passes 58 tests; Ruff, Python compilation, refreshed runtime SQL inventory, and diff checks pass. No migration or database was used. This fixes model reuse across location scopes but does not establish least-privilege database access or RLS; populated parity, live OIDC/browser, audience review, and MAN-CAP-008 remain open ([evidence](builds/2026-10-24-recovery/cap-008-cross-validation-model-scope.json)).

**Latest local batch — CAP-008 bounded spatial-block fold diagnostics (24 October 2026):** the exact-location cross-validation response now returns fixed aggregate diagnostics only for spatial-block folds with at least five test samples each. It caps source data at ten folds and 16 KiB and omits block IDs, coordinates, point-level values, failure strings, and model references; leave-one-out details remain private. The text-only grant-gated console validates and displays the projection. Forty-two focused Gateway, console, and route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks. No migration, provider, candidate, or legacy database was used. Other geostatistics paths, populated/numerical parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-spatial-fold-diagnostics.json)).

**Latest local batch — CAP-008 saved geostatistical realization summaries (24 October 2026):** a private exact-location `geostatistics:read` route selects bounded saved runs before aggregating their point values. The fixed summary includes method, realization number, counts, mean, standard deviation, minimum, maximum, grid resolution, and time; point values, geometries, seeds, model IDs, and metadata are omitted. Non-finite values become `null`; the shared console renders text and labels output advisory. The combined 60-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Per-point output, scientific/populated parity, other geostatistics paths, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-realization-kernel-summaries.json)).

**Previous local batch — CAP-008 saved kriging Kernel summaries (24 October 2026):** the private exact-location `geostatistics:read` route selects bounded saved runs before aggregating per-point predictions and uncertainty into fixed run summaries. It omits individual point records and coordinates, model IDs, metadata, and thresholds; non-finite values become `null`. The shared console validates the response, renders text only, and labels output advisory. The combined 56-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Numerical/populated parity, per-point output, other geostatistics paths, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-kriging-kernel-summaries.json)).

**Previous local batch — CAP-008 saved sensor-network design Kernel read (24 October 2026):** a private exact-location `geostatistics:read` route returns bounded saved spacing and coverage estimates with sensor counts, gap percentage, confidence, and computation time. Notes, model references, IDs, and metadata are omitted; non-finite numbers become `null`. The shared panel validates scope and numeric values, renders fixed fields as text, and labels outputs advisory. The combined 52-test CAP-008 Gateway/console/route-policy selection passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Calculation/populated parity, other geostatistics outputs, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-sensor-network-design-kernel-read.json)).

**Previous local batch — CAP-008 saved variogram-model Kernel read (24 October 2026):** the private exact-location `geostatistics:read` route returns bounded saved spherical, exponential, Gaussian, and Matérn fit summaries, omitting model IDs and metadata; non-finite numeric values become `null`. The shared console validates location/page and model type, discards stale responses, and renders the fixed projection as text while labeling fits advisory. The combined 48-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Numerical/populated parity, other geostatistics paths, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-variogram-kernel-read.json)).

**Previous local batch — CAP-008 saved spatial cross-validation Kernel read (24 October 2026):** a private exact-location `geostatistics:read` route returns bounded spatial CV error summaries, excluding fold-level results, model identifiers, and metadata; non-finite numbers become `null`. The shared grant-gated console validates strategy and scope and renders fixed fields as text. The combined 44-test CAP-008 Gateway/console/route-policy suite passes with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Fold diagnostics, other geostatistics outputs, populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-spatial-cross-validation-kernel-read.json)).

**Previous local batch — CAP-008 saved spatial-autocorrelation Kernel read (24 October 2026):** a private exact-location `geostatistics:read` route selects the latest saved autocorrelation result per property/metric, with bounded paging, finite numeric values, and no interpretation text, metadata, IDs, or point coordinates. The separate grant-gated console panel renders fixed fields as text and labels results advisory. Thirty-nine focused Gateway/console/route-policy tests pass with Ruff, compilation, JavaScript syntax, runtime SQL inventory, matrix validation, and diff checks. No migration, provider, candidate, or legacy database was used. Other geostatistics outputs, populated parity, live OIDC/browser, ACL/RLS, audience review, and MAN-CAP-008 remain open ([contract](geostatistics-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-008-spatial-autocorrelation-kernel-read.json)).

**Latest local batch — CAP-005 cooperative management Kernel summary (24 October 2026):** the first private `cooperative_management:read` route returns exact-location cooperative/type/status, active membership, asset type/status, and booking status counts after signed tenant context. Its operator panel is grant-gated and text-only; personal identity, credential/KYC, booking detail, financial values, GPS, and free text are omitted. Twelve focused Gateway, console, and route-policy checks pass; Ruff, compilation, JavaScript syntax, runtime SQL inventory, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-005 remains prepared pending profile/credential workflows, populated parity, live OIDC/browser, least-privilege ACL/RLS, audience/privacy review, and MAN-CAP-005 ([contract](cooperative-management-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-005-cooperative-management-kernel-read.json)).

**Latest local batch — CAP-006 monthly carbon-offset compatibility (24 October 2026):** the location-scoped energy summary restores the legacy monthly offset estimate (active registered offset declarations divided by 12) and net monthly emissions (30-day fixed-factor estimate minus that offset). The console validates both and labels them advisory; negative values remain visible. Thirteen focused Gateway/console tests pass with Ruff, compilation, and JavaScript syntax. No migration, database, provider, candidate, or legacy data was used; populated output parity and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-carbon-offset-monthly-compatibility.json)).

**Latest ARM64 application portability check — 24 October 2026:** the default Kernel image built from `8f5fd1eb` for `linux/arm64`; a network-disabled QEMU smoke reported `aarch64` and passed Gateway app creation, both Python SDK imports, all 18 job specs, migration CLI help without database credentials, and synthetic RPC snapshot construction. The temporary image/container were removed, with no database, provider, credential, candidate, legacy stack, or persistent volume access. This updates code-only portability evidence; physical Raspberry Pi, power, thermal/performance, and long-duration recovery acceptance remain open ([evidence](builds/2026-10-24-recovery/arm64-kernel-current-source-smoke-8f5fd1eb.json)).

**Latest local batch — CAP-006 currency-safe energy costs (24 October 2026):** migration 604 adds an optional currency code without assigning currencies to historic cost rows. New and changed energy costs require a valid code; legacy analytics keep currencies separate, and the exact-location signed Gateway plus console expose reviewed 30-day totals by code and unclassified counts without unsafe mixed totals. The 64-test energy Gateway/console/domain/CLI selection and disposable PostgreSQL apply/replay checks pass, as do Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks. Candidate and legacy databases remain untouched; migration 604 has not been rolled out. Populated cost reconciliation, ACL/RLS, live OIDC/browser acceptance, and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-energy-cost-currency-disposable.json)).

**Previous local batch — CAP-006 active energy source breakdown (24 October 2026):** the private energy summary now includes a location-scoped aggregate of active source counts and rated capacity by fixed source type, distinct from renewable registrations. The console validates the enum projection and renders fixed fields as text. The 59-test Gateway/console/energy-domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks pass. No migration/database/provider was used. Populated source parity, ACL/RLS, live OIDC/browser, and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-active-energy-source-breakdown.json)).

**Previous local batch — CAP-006 reviewed daily efficiency history (24 October 2026):** the exact-location summary restores the latest 12 verified/approved daily efficiency-log rows with a fixed projection that omits notes, metadata, and unclassified cost-per-unit output. The console validates the bounded history and labels persisted intensity and efficiency values as advisory. The 59-test Gateway/console/energy-domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks pass. No migration/database/provider was used. Populated record/formula parity, ACL/RLS, live OIDC/browser, and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-reviewed-efficiency-history.json)).

**Previous local batch — CAP-006 registered renewable metrics (24 October 2026):** the signed exact-location energy summary now aggregates active registered renewable entries by fixed type, including count, rated capacity, annual generation, and stored offset values. The legacy generation-coverage formula remains capped at 100%, with a 365-day verified/approved-consumption denominator; unreviewed `recorded` rows are excluded. The console labels offsets advisory and coverage indicative. The 59-test Gateway/console/energy-domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. Populated asset parity, review of registered values, ACL/RLS, live OIDC/browser acceptance, and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-24-recovery/cap-006-registered-renewable-parity.json)).

**Previous local batch — CAP-006 energy dashboard calculations (23 October 2026):** the exact-location `energy_monitoring:read` projection adds verified/approved 30-day consumption, production, and net totals; legacy-defined renewable-use share; a seven-day trend; and a fixed-factor carbon estimate explicitly labeled advisory. Costs stay withheld because readings have no currency classification. The 59-test Gateway/console/energy-domain/route-policy selection, Ruff, compilation, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. Populated parity, ACL/RLS, live OIDC/browser acceptance, and MAN-CAP-006 remain open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-006-energy-calculation-parity.json)).

**Previous local batch — CAP-006 verified waste and incident-count reads (23 October 2026):** the private `GET /operator/api/waste/{location_id}/summary` requires exact `waste_management:read`, sets signed tenant context before four location-qualified queries, and returns verified waste/compost/recycling aggregates plus descriptive incident counts. Units stay separate; incident narratives and identities are omitted. The hidden-by-default console validates grant, response scope, categories, and stale state, and renders fixed fields as text. The combined energy/waste Gateway, console, and route-policy selection passes 25 tests, with Ruff, JavaScript syntax, runtime SQL inventory, capability validation, and diff checks passing. No migration, provider, candidate, or legacy database was used. CAP-006 remains prepared ([contract](waste-management-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-006-waste-kernel-read.json)).

**Previous local batch — CAP-006 farm-energy Kernel read path (23 October 2026):** the private `GET /operator/api/energy/{location_id}/summary` route requires exact `energy_monitoring:read`, sets signed tenant context before location-qualified SQL, and returns only grouped verified/approved kWh aggregates. The hidden-by-default console validates grant, response scope/unit, fixed categories, and stale state; it renders fixed fields as text. Fourteen focused Gateway/console/route-policy tests, Ruff, JavaScript syntax, SQL inventory, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-006 is prepared, with energy calculation parity, waste/habitat/pollinator coverage, populated data, ACL/RLS, live OIDC/browser acceptance, and MAN-CAP-006 still open ([contract](energy-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-006-energy-kernel-read.json)).

# Code-first refactor execution plan

**Updated:** 24 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68

**Latest software portability check — 24 October 2026:** a network-disabled
ARM64/QEMU PostgreSQL 16 replay applied all 595 current schema files through
migration 604 with zero pending or failed migrations, no seeds/farm data, no
published host ports, `aarch64` confirmed, and cleanup complete. This validates
schema portability under emulation; physical Raspberry Pi, power, performance,
and production recovery acceptance remain open ([evidence](builds/2026-10-24-recovery/arm64-qemu-current-schema-604.json)).

**Latest local batch — CAP-002 nutrient operations operator-console reads (23 October 2026):** an exact `nutrient_budget:read` grant gates allowlisted balance, soil-test, input, and removal views. Same-origin/no-store pages validate location, offset, and event type, and stale views are discarded. Fixed scalar fields render as text; IDs, notes, and arbitrary metadata are omitted. Classified costs preserve currency and historic unclassified amounts are withheld. The 191-test CAP-002 console/Gateway/domain/route-policy selection, Ruff, inline JavaScript syntax, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-002 remains prepared pending historic currency reconciliation, model/populated parity, live OIDC/browser, ACL/RLS, and MAN-CAP-002 ([contract](nutrient-operations-console-contract.md); [evidence](builds/2026-10-23-recovery/cap-002-nutrient-console.json)).

**Latest local batch — CAP-002 crop-simulation operator-console reads (23 October 2026):** the exact `digital_twin:read` grant gates a completed-run list and bounded persisted daily-state detail. Same-origin/no-store pages validate location, offset, and selected-run correlation; stale results are discarded after location/run changes. Fixed run/state fields render as text, IDs stay internal, and no model is executed. The 106-test CAP-002 console/Gateway/domain/route-policy selection, Ruff, inline JavaScript syntax, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-002 remains prepared pending model/frozen/populated parity, live OIDC/browser acceptance, ACL/RLS, and MAN-CAP-002 ([contract](crop-simulation-runs-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-002-crop-simulation-console.json)).

**Latest local batch — CAP-002 irrigation-zone operator-console status (23 October 2026):** a separate exact `precision_irrigation:read` grant gates a read-only status table. Same-origin/no-store pages are capped at 25 zones and validate location/offset before rendering; stale pages are ignored after a location switch. Fixed zone, soil, area, moisture, target, and schedule values render as text with no device controls or IDs. The 53-test CAP-002 console/Gateway/domain/route-policy selection, Ruff, inline JavaScript syntax, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-002 remains prepared pending frozen/populated parity, live OIDC/browser, ACL/RLS, and MAN-CAP-002 ([contract](irrigation-status-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-002-irrigation-console.json)).

**Latest local batch — CAP-002 harvest-yield operator-console surface (23 October 2026):** the hidden-by-default console summary requires the exact `yield_monitoring:read` grant for a valid location. Same-origin/no-store requests verify response location and discard stale location results. Fixed fields show verified/published aggregate, crop, and recent-harvest values as text while preserving stored units. The 13-test console/Gateway/route-policy selection, Ruff, inline JavaScript syntax, capability validation, and diff checks pass. No migration, provider, candidate, or legacy database was used. CAP-002 remains prepared pending frozen/populated parity, live OIDC/browser acceptance, database ACL/RLS, and MAN-CAP-002 ([contract](yield-monitoring-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-002-yield-monitoring-console.json)).

**Latest local batch — CAP-003 traceability operator-console surface (23 October 2026):** the console now provides a hidden-by-default, exact-location `traceability:read` batch list/detail panel. Its fixed status filter and bounded pages use same-origin/no-store requests; location changes clear prior detail state, stale requests are discarded, and batch, custody, quality, certification, food-safety, and provenance fields render as text. Five console contracts plus Gateway and route-policy tests pass (18 total), including inline JavaScript syntax; Ruff and capability validation pass. No migration, candidate/legacy database, provider, or chain was used. CAP-003 remains prepared pending populated parity, audience review, live OIDC/browser behavior, database ACL/RLS, recovery, and MAN-CAP-003 acceptance ([contract](traceability-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-003-traceability-console.json)).

**Previous CAP-004 batch — active public learning-module catalog (23 October 2026):** `GET /operator/api/extension-learning/{location_id}/modules` lists only active public modules with exact location `extension_learning:read`, allowlisted filters, and 1–50 item pagination. The projection omits URLs and free-text content pending review. The combined CAP-004 service/HTTP/route-policy selection passes 10 tests; Ruff, compilation, runtime SQL inventory, and capability checks pass. No migration, candidate/legacy database, or provider was used. See the [Kernel read contract](extension-learning-kernel-read-contract.md) and [evidence](builds/2026-10-23-recovery/cap-004-extension-learning-summary.json).

**Latest local batch — CAP-002 currency-qualified nutrient input costs (23 October 2026):** ordered migration 601 adds an optional currency code while preserving historical unclassified amounts. New or changed cost values require a three-letter code; Gateway projections withhold legacy amounts lacking currency, and nutrient summaries split totals by currency without conversion. The 182-test nutrient/Gateway/operator-auth/migration selection and six network-disabled PostgreSQL 16 migration/replay/data-integrity assertions pass. Ruff, compilation, runtime SQL inventory, capability validation, and diff checks pass. No candidate/legacy database, provider, or chain was used. Historic cost reconciliation, populated parity, live OIDC/browser, RLS, and MAN-CAP-002 remain open ([contract](nutrient-events-kernel-read-contract.md); [migration](../schemas/postgres/601_nutrient_input_cost_currency.sql); [evidence](builds/2026-10-23-recovery/nutrient-input-cost-currency-disposable.json)).

**Previous local batch — CAP-002 deterministic crop-simulation baseline (23 October 2026):** the legacy simulator now derives daily weather variation from stable SHA-256 buckets keyed by `weather_seed` (default 0) and persists/returns the selected seed. A synthetic 30-day maize fixture covers seeds 0 and 42; it passes under `PYTHONHASHSEED=1` and `98765`. The focused Gateway/digital-twin/operator-auth selection passes 114 tests, with Ruff, compilation, runtime SQL inventory, capability validation, and diff checks. This pins repeatability only; legacy/populated output parity, agronomic correctness, live OIDC/browser, RLS, and MAN-CAP-002 remain open. No migration, candidate/legacy database, or provider was used ([fixture](../tests/fixtures/crop_simulation_reference_v1.json); [contract](crop-simulation-runs-kernel-read-contract.md)).

**Latest pulled batch — Protocol execution bridge (23 October 2026):** branch head `7679b3ea` adds a governed KI-to-Protocol intent/outbox/reconciliation path and migration 600. The focused bridge/connector/safety selection passes 32 tests with 9 database-dependent skips; Ruff and Python compilation pass. A network-disabled disposable native PostgreSQL 16 replay applies all 591 schema files through migration 600 with zero pending/failed migrations, no seeds, and successful cleanup. The bridge and connector modules also pass 21 unit tests under linux/arm64 QEMU (`aarch64`) with the repository mounted read-only. The capability is tracked as prepared CAP-067; there is no live NEAR/EVM adapter, Gateway authorization surface, candidate rollout, external transaction, or named manual acceptance. Physical Raspberry Pi behavior remains unverified.

**Previous local batch — CAP-003 traceability Kernel read path (23 October 2026):** the OIDC operator Gateway now has exact-location read-only batch list and detail endpoints. Signed tenant context is set before SQL, each child collection query repeats the requested-location constraint, and page/related-result limits are enforced. The response covers bounded custody, quality, certifications, food-safety, and provenance records while omitting actor names, free text, GPS, evidence URLs, and arbitrary metadata. The 76-test traceability/operator-auth selection passes, as do Ruff, compilation, and the regenerated runtime SQL inventory. No migration, candidate or legacy database, provider, or chain was used. Populated output parity, live ZITADEL/browser, direct-database RLS, report audience review, and MAN-CAP-003 remain open ([contract](traceability-kernel-read-contract.md); [evidence](builds/2026-10-23-recovery/cap-003-traceability-kernel-read.json)).

**Previous local batch — signed credit-adjustment checks and SMTP secret setup (23 October 2026):** migration 599 adds a default-off signed, location-scoped credit-adjustment worker; the Prefect compatibility path remains on the existing read-only command until worker identity/grants are provisioned. The 256-test focused suite, Ruff, six native disposable PostgreSQL 16 checks, and all 19 Compose-profile tests pass. The disposable runner supports explicit ARM64/QEMU selection; its 12-test runner/Compose contracts and six migration-599 checks pass on ARM64/QEMU (`aarch64`) and native PostGIS (`x86_64`). A separate full ARM64 schema replay through 599 failed at `000_extensions.sql` before applying any schema and captured no PostgreSQL diagnostic; the previous full replay through 598 remains the latest complete bootstrap evidence. Maileroo SMTP host/account and both supplied keys are configured/encrypted through SOPS; email stays disabled because the alert recipient and severity/on-call routing are not yet selected. The intended ZITADEL test operator is `hello@kokonut.network`; client ID and live identity setup remain open. No candidate or legacy database, live provider, or schedule was touched.

**Latest candidate rollout — migrations 552–598 (23 October 2026):** source revision `ac1a84cd16499e9c644f0a1de6d16e8b3d1948bf` now has all 47 pending schemas applied to the local candidate after a fresh encrypted checkpoint and isolated restore rehearsal. Candidate and clone match at 589 schemas through 598, six unchanged seed rows, zero pending/failed entries, and 1,486 public relations. Only the app was rebuilt/recreated; health is 200 and an anonymous protected farm-activity request returns 401/no-store. No seed SQL or farm data was added; the legacy stack was untouched. Rollback image, encrypted checkpoint, and stopped recovery volume are retained ([rollout evidence](builds/2026-10-23-recovery/candidate-migrations-552-598-rollout.json)). The checkpoint is same-host/database-only, so it does not close off-host or production recovery.

**PR #68 status at the start of the 23 October production-host config batch:** commit `1d343a2327308ea30e7b2d2a7348f58dcc033bda` was pushed. Security #501 passed; CI #777 was in progress on that exact SHA. Physical Raspberry Pi acceptance remains open.


**Previous pushed batch — SMTP transport and worker-inventory repair (23 October 2026):** commit `237c7c86874ee454902cff807bda39a58887b7a8` is pushed to PR #68. The earlier SMTP batch added a dependency-free adapter with verified STARTTLS by default, optional implicit TLS, and opt-in unauthenticated plain transport; its focused SMTP/health-check selection passed 38 checks and all 19 Compose-profile tests passed. CI #774 exposed seven stale generated worker-inventory freshness/coverage checks; the five reports were regenerated and their focused test set passed 35. Security #499 and CI #775 both passed on pushed commit `237c7c86`. The local CAP-066 source-scope analyzer follow-up passes 48 focused tests with Ruff and current generated-inventory checks: it now traces location scope from parent rows into child queries inside `try` and `if` blocks, including Statement of Work and EBF. It is source-analysis evidence only, not report output, runtime authorization, or RLS acceptance ([worker repair](builds/2026-10-23-recovery/ci-774-worker-inventory-refresh.json); [scope inheritance](builds/2026-10-23-recovery/report-parent-row-scope-inheritance.json)). The clean network-disabled ARM64/QEMU replay applied all 589 schema files through migration 598 with zero pending or failed files; the latest ARM64 app build and read-only/no-network smoke also passed. These are software portability checks, not physical Raspberry Pi acceptance ([schema evidence](builds/2026-10-23-recovery/arm64-qemu-current-schema-598-retry.json); [app smoke](builds/2026-10-23-recovery/arm64-kernel-current-source-smoke-ef0bcf60.json)). Candidate and legacy databases remain untouched ([SMTP evidence](builds/2026-10-23-recovery/smtp-tls-transport.json); [prior failed migration-598 attempt](builds/2026-10-23-recovery/arm64-qemu-current-schema-598.json)).

**Previous batch — current-source ARM64 replay and CI #771 correction:** the clean bootstrap now creates a locked historical `directus` placeholder only when absent, and the corrected network-disabled ARM64/QEMU PostgreSQL 16 run applied all 588 schema files through migration 597 with zero pending or failed files and successful cleanup. CI #771 then found that a PostgreSQL superuser seed session was classified as a worker because superusers have implicit membership in every role. New migration 598 excludes that implicit membership while retaining denial for explicit worker roles and non-superuser worker logins. Focused migration/agent-safety checks pass 49 tests with nine existing DB-dependent skips; Ruff, compilation, and network-disabled PostgreSQL 16.4/16.15 replay/role checks pass. The repeatable role test is integrated into the CI runner, replays migration 598 twice, and verifies admin/operator publication, worker terminal-state denial, and marker restrictions. The prior full-schema evidence records source `ba11ae3b` with the dirty working tree later committed as `c0eb4837`; it predates migration 598, which is separately verified. Candidate and legacy databases remain untouched; CI #772 later completed with failure and subsequent CI #773 passed on `b69b824c`. The repeatable role check is included in the current pushed batch. The Directus permission API boundary and owner parity gate remain open. Evidence: [full ARM64 replay](builds/2026-10-23-recovery/arm64-qemu-current-schema-597-after-bootstrap-retry.json), [repeatable lifecycle check](builds/2026-10-23-recovery/agent-safety-superuser-ci-regression.json), [PostgreSQL 16.15 role check](builds/2026-10-23-recovery/agent-safety-superuser-session-disposable.json), [Directus permission probe](builds/2026-10-23-recovery/directus-effective-permissions.json). This correction builds on the preceding pushed clean-bootstrap batch.

Refactor status: docs/refactor/batches.md has 1,073 complete / 25 open checkboxes (1,098 total); 97.7% is checkbox completion, not capability acceptance. The 67-row capability matrix has 24 baseline-retained, 7 deployed, and 36 prepared capabilities; all 67 named MAN-CAP acceptance checks remain open. Human/runtime gates are tracked separately in docs/refactor/open-follow-ups.md.

**CAP-066 helper-return location scope correlation — 21 October 2026:** the
report query analyzer follows literal same-module filter/bind pairs returned
by a helper and reports a conditional location signal only when the filter is
bound to the caller's `location_id` argument. Joined `alias.id = %s` requires
a matching `location` join. Three SWOT suggestion queries now expose their
location-specific variant separately from organization/no-filter variants;
wrong-argument and unjoined-alias regressions stay unscoped. The focused query,
helper, and source-inventory selection passes 57 tests with Ruff, compilation,
all report/runtime inventory freshness checks, matrix validation, and diff
checks. The helper inventory remains 169/169 static SQL memberships with zero
unresolved sites and bind mismatches; 81 memberships have a location-scope
source signal. This does not establish authorization, RLS, database execution,
populated report parity, or audience access ([evidence](builds/2026-10-21-recovery/cap-066-helper-return-location-scope-correlation.json)).
Checklist: 894 complete / 24 open; matrix: 31 baseline-retained, 7 deployed,
28 prepared. No database, migration, candidate, legacy stack, or provider was
used.


**Updated:** 21 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68

**CAP-064 explicit gRPC server plaintext policy — 21 October 2026:** server
startup now requires TLS unless `GRPC_ALLOW_INSECURE=true` opts into trusted
private-network plaintext. Compose keeps the local legacy and private Kernel
development paths explicit while production forces TLS. Profile tests also
found and removed orphan `agent-summary-worker` environment stanzas from the
Kernel standard/runtime-role overlays. The combined gRPC/profile/Compose suite
passes 128 tests with Ruff, compilation, and whitespace checks. No services,
database, or provider were started; production certificate/ingress, tenant
authorization, and REST parity remain open ([evidence](builds/2026-10-21-recovery/cap-064-grpc-server-plaintext-opt-in.json)).
Checklist: 935 complete / 24 open (959 total); capability classifications
remain 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows.

**CAP-066 literal formatted SQL in shared-view callers — 21 October 2026:**
the analyzer resolves helper SQL f-strings only when every direct local caller
supplies literal strings for interpolated names. Both `_fetch_public_view`
queries now resolve across five report callers, for ten report-to-helper
memberships; bind arity is one/one for location-filtered SQL and zero/zero for
unfiltered SQL. No location-scope signal is inferred. Helper coverage is
157/175 static SQL sites, 18 unresolved, and 143 positional plus two named
contracts with zero mismatches. The focused query/helper/source selection
passes 51 tests with Ruff, compilation, all three inventory checks, matrix
validation, and diff checks. External/dynamic callers, database execution, and
populated parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-formatted-query-wrapper-callers.json)).

**CAP-066 local helper-return filter and bind variants — 21 October 2026:**
the analyzer follows only same-module helpers whose normal paths explicitly
return literal filter/positional-container pairs or raise. It resolves three
SWOT suggestion reads across location, empty-organization, and organization
results, with matching arity and no tenant-scope signal. Helper coverage is
147/175 static SQL sites, 28 unresolved, and 133 positional plus two named
contracts with zero mismatches. The focused query/helper/source selection
passes 48 tests with Ruff, compilation, all three inventory checks, matrix
validation, and diff checks. Dynamic returns, unsupported flow, authorization,
and populated report parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-helper-return-filter-bind-contracts.json)).

**CAP-066 helper branch-paired SQL and bind variants — 21 October 2026:** the
helper analyzer resolves literal SQL and positional parameter containers
assigned together on successful branches of a fail-closed `if/elif` chain. It
adds the business-model-canvas and SWOT listing queries, both with matching
location/organization variant arity, without assigning a tenant-scope signal.
Coverage is 144/175 static SQL sites, 31 unresolved, and 130 positional plus
two named contracts with zero mismatches. The focused query/helper/source
selection passes 44 tests with Ruff, compilation, all three inventory checks,
matrix validation, and diff checks. Runtime SQL, authorization context,
external callers, and populated report parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-helper-tuple-filter-bind-contracts.json)).

**CAP-066 literal query-wrapper call sites — 21 October 2026:** the helper
analyzer resolves a wrapper only when every direct local call supplies
a string literal and a positional tuple/list. The business-plan report's
`services/planning/sandop.py:_rows` query now records all three `cockpit` call
sites, each with matching one-placeholder/one-value arity; it receives no
location-scope signal. Helper coverage is 142/175 static SQL sites, 33
unresolved, and 128 positional plus two named contracts with zero mismatches.
The focused query/helper/source selection passes 40 tests with Ruff,
compilation, all three inventory checks, matrix validation, and diff checks.
Dynamic/indirect callers, runtime SQL, and populated report parity remain open
([evidence](builds/2026-10-21-recovery/cap-066-local-query-wrapper-callsites.json)).

**CAP-066 optional helper filter-list SQL and bind contracts — 21 October 2026:**
the static helper analyzer now enumerates simple paired clause-list and
parameter-list appends across all guard combinations, bounded to six guards.
It resolves five report-to-helper memberships, bringing coverage to 141/175
static SQL sites and 127 positional plus two named bind contracts, with zero
mismatches. Thirty-four SQL sites remain unresolved. The 37-test focused
query/helper/source suite passes with Ruff, compilation, all three inventory
freshness checks, matrix validation, and diff checks. The resolver does not
certify tenant-scope correlation; nested/dynamic mutations, PostgreSQL
execution, and populated output parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-optional-filter-list-bind-contract.json)).

**CAP-066 literal module SQL constants in helper closure — 21 October 2026:**
the query analyzer resolves a unique literal module-level SQL string only when
it precedes the function and no local binding shadows it. Five helper query
memberships are now statically resolved; helper coverage is 136/175 static SQL
sites, 39 unresolved sites, 122 positional contracts, and two named contracts,
with zero bind mismatches. The focused query/helper/source selection passes 32
tests; Ruff, compilation, all three inventories, matrix validation, and diff
checks pass. Computed/reassigned globals, dynamic SQL, runtime execution, and
populated report parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-literal-module-sql-constants.json)).

**CAP-066 helper named-bind contracts — 21 October 2026:** the helper-scope
inventory now carries named-bind analysis for reachable helper queries. Across
175 report-to-helper query memberships, 117 positional and two named contracts
are statically checked with zero mismatches. The 30-test helper/query/source
selection, Ruff, compilation, all three generated inventory checks, matrix
validation, and diff checks pass. Dynamic SQL/parameter construction and
populated report parity remain open; this scan is not database execution or
tenant authorization ([evidence](builds/2026-10-21-recovery/cap-066-helper-named-bind-contracts.json)).

**CAP-066 static named report bind contract — 21 October 2026:** the direct
report inventory now compares SQLAlchemy `:name` and psycopg `%(name)s` binds
with literal mapping keys, including simple condition-list and mapping updates
under matching `if` branches. It covers all 176 direct query sites using 175
positional contracts and one named contract, with zero mismatches. The 84-test
Data Stream/query/helper/source selection passes with Ruff, compilation, three
inventory freshness checks, capability validation, and diff checks. Dynamic or
nested mutations, dynamic helper binds, runtime PostgreSQL behavior, and
populated report parity remain open ([evidence](builds/2026-10-21-recovery/cap-066-static-named-report-bind-contract.json)).

**CAP-066 named report bind filters — 21 October 2026:** a mocked connection
regression now checks the remaining direct named-bind report query across all
four optional date-bound combinations. Its SQL bind names exactly match the
supplied parameter map, and the location bind is always present. The combined
Data Stream/query/helper/source-inventory selection passes 79 tests; Ruff,
compilation, and diff checks pass. The static inventory remains positional-only
at 175 of 176 direct queries; this does not establish PostgreSQL execution,
dynamic helper coverage, or populated report parity ([evidence](builds/2026-10-21-recovery/cap-066-named-report-bind-contract.json)).

**CAP-066 conditional report query bind arity — 21 October 2026:** the static
query analyzer now correlates SQL placeholders with parameters across simple
location branches and a common static suffix. It checks 175/176 direct report
queries and 117/175 report-to-helper query memberships with no mismatches.
Regressions cover matching branches, opposite-branch parameter errors, and
unresolved nested SQL/parameter mutations. The combined focused query/helper/source inventory
selection passes 24 tests; Ruff, compilation, three inventory checks, and matrix
validation pass. No database or provider was used. Helper-query named binds,
complex helper queries, runtime SQL, and populated report parity remain open
([evidence](builds/2026-10-21-recovery/cap-066-conditional-query-bind-arity.json)).

**CAP-066 report helper SQL bind arity — 21 October 2026:** the helper-scope
inventory now records positional bind counts for statically resolved helper
queries. Across 94 report types and 175 report-to-helper query memberships,
116 sites are statically checkable and none mismatch; named and dynamic
parameters remain unresolved. The six-test helper/source inventory selection,
Ruff, compilation, three report inventory checks, and capability-matrix
validation pass. No database or provider was used. This is source evidence,
not runtime SQL acceptance ([evidence](builds/2026-10-21-recovery/cap-066-helper-query-bind-arity.json)).

**CAP-066 report SQL bind arity inventory — 21 October 2026:** the query-scope
inventory now compares positional `%s` placeholder counts with simple statically
known parameter containers for unbranched static SQL. SQL string literals and
comments do not count as binds; named, dynamic, and conditional parameter
construction stays unresolved. 170 of 176 direct report query sites are
statically checkable, with zero mismatches. Extra-bind, SQL-literal/comment,
and named-bind regressions pass in a 15-test focused climate-report/inventory
selection. Ruff, compilation, four inventory checks, runtime SQL inventory, and
matrix validation pass. No database or provider was used ([evidence](builds/2026-10-21-recovery/cap-066-report-query-bind-arity.json)).

**CAP-066 climate-impact report query fix — 21 October 2026:** the climate
report's shared active-protocol query no longer receives an unused location
parameter despite having no SQL placeholder. A focused regression checks every
query's placeholder/parameter arity and confirms the shared protocol projection
is preserved. The report and query-inventory selection passes 12 tests; Ruff,
Python compilation, runtime SQL and three report inventory checks, and matrix
validation pass. No database, migration, candidate, legacy stack, or provider
was used. Populated report parity and MAN-CAP-066 owner acceptance remain open
([evidence](builds/2026-10-21-recovery/cap-066-climate-impact-query-parameters.json)).

**Network-disabled bootstrap profile — 20 October 2026:** the schema-only
PostgreSQL Compose profile passed a local runtime smoke with `network_mode:
none`, no host ports, a healthy database, and successful `psql` through
`docker compose exec`; temporary container and volume were removed. No schema
migrations ran during this smoke. The full 516-migration replay has separate
evidence and used a private Compose bridge ([smoke evidence](builds/2026-10-20-recovery/schema-bootstrap-networkless-smoke.json); [profile](../../docker-compose.schema-bootstrap.yml)).

**Current-source clean schema replay — 21 October 2026:** a fresh native AMD64
PostgreSQL 16 target using the network-disabled bootstrap profile applied all
519 current schema migrations through migration 528 with zero failures. No
seeds or farm data were loaded, no host port was published, and the temporary
container and volume were removed. The 36-test migration unit suite and
519-file source validation pass; the 66-row capability matrix remains valid.
The candidate and legacy stacks were not targeted. Full ARM64 schema replay,
physical Raspberry Pi/power behavior, and candidate rollout remain open
([replay evidence](builds/2026-10-21-recovery/clean-bootstrap-current-schema-528.json)).
The explicit Compose-only path now skips workstation dotenv loading because it
uses `psql` inside the selected database container and only needs its routing
database/user; the bypass is development-only and production rejects it. Twenty
focused environment/Compose tests pass ([configuration evidence](builds/2026-10-21-recovery/schema-bootstrap-secretless-config.json)).

**ARM64 full-schema replay attempt — 20 October 2026:** the locked ARM64 PostGIS
image reached healthy and reported `aarch64` under QEMU, with no network or host
ports. The 516-file replay was stopped while migration 068 was in progress after
approximately 9.5 minutes because emulated database throughput was impractical
for a complete local run. Cleanup removed the temporary database, container, and
volume. This partial attempt is not migration acceptance; the latest completed
ARM64 replay remains through migration 434 ([evidence](builds/2026-10-20-recovery/arm64-schema-replay-attempt.json)).

**CAP-039 CLI syntax compatibility — 20 October 2026:** the documented
`framework list` invocation now works through the standalone and unified DAO
CLIs while retaining the no-argument compatibility form. Three fake-connection
checks pass for output parity, cleanup, and invalid-action preflight; Ruff and
Python compilation pass. No live database or DAO provider was contacted
([evidence](builds/2026-10-20-recovery/cap-039-governance-framework-list-cli.json)).

**Current-schema clean replay — 20 October 2026:** A fresh isolated native
AMD64 PostgreSQL 16 database applied all 516 repository schema migrations
through 525 with zero failures and no seeds or farm data. The focused migration,
operator lifecycle, and unified-CLI selection passes 105 tests; Ruff, Python
compilation, matrix validation, and migration-source validation pass. Docker's
address pool was exhausted by 20 empty networks from prior Kokonut test
projects; only those unattached test networks were removed. Candidate and legacy
networks and services remained untouched. The candidate still needs its own
ordered migration rollout after a fresh encrypted checkpoint and restore
rehearsal. ARM64 database replay remains through 434; the separate ARM64 Gateway
runtime check remains against schema 524. [Replay evidence](builds/2026-10-20-recovery/clean-bootstrap-current-schema-525.json).

**CAP-038 source metadata correction — 20 October 2026:** the Wellbeing
Synthesis Agent's direct location-scoped `stakeholder_feedback` aggregation is
now represented in its source-table declaration. Its regression pins the query
and declaration; combined agent/summary/Gateway tests pass 92 cases with nine
PostgreSQL-dependent skips. No database or provider was contacted. This aligns
the source hint but does not add row-level provenance or authenticated agent
identity ([evidence](builds/2026-10-20-recovery/cap-038-wellbeing-source-metadata.json)).

**Bootstrap and ARM64 software acceptance — 20 October 2026:** A clean schema
replay exposed migration 475's dependency on an optional Directus role in fresh
installations. Bootstrap now provisions a restricted `NOLOGIN` placeholder
when absent, and the migration CLI performs the same preflight before pending
schema work without mutating dry-run/no-op plans. Focused migration, upgrade,
and role tests pass (56); Ruff and Python compilation pass. An isolated native
AMD64 PostgreSQL 16 clean bootstrap applied all 515 current schema files through
migration 524. The current ARM64 Kernel image also passed a no-network,
read-only QEMU import/help smoke. Candidate and legacy stacks were untouched;
full schema replay was not ARM64, whose database acceptance remains through
migration 434, and QEMU does not certify Raspberry Pi hardware. See the
[bootstrap replay](builds/2026-10-20-recovery/clean-bootstrap-current-schema-524.json)
and [ARM64 smoke](builds/2026-10-20-recovery/arm64-kernel-current-source-smoke-c6aab4ea.json).
The ARM64 Gateway was also run against a fresh schema-524 PostgreSQL database
on the internal disposable network: it reported `aarch64`, health returned
200, and an anonymous protected write returned 401. The temporary containers,
volume, network, and image were removed, and the candidate remained healthy.
This verifies the QEMU app against the current schema but not ARM64 PostgreSQL
or physical Pi behavior ([integration evidence](builds/2026-10-20-recovery/arm64-gateway-schema-524-runtime.json)).

**Latest CAP-038 implementation slice — 20 October 2026:** Migrations 521–524
provide location-scoped AI-summary review, authenticated draft creation, and
private bounded source-record manifests. Draft requests bind to signed
`ai_summary:draft` location scope, persist the requester, and return their
saved result before regeneration on retry. Source manifests record exact
location-owned row counts and up to 50 ordered IDs per table, and PostgreSQL
checks every ID against the requested location. Sensor and expense references
match the summary’s top-three sensor types and top-five configured expense
categories, with deterministic tie ordering. The review queue exposes these
references under the exact review grant. Draft generation uses `REPEATABLE READ`
so summary values and source references share one database snapshot. Review
blocks self-approval/rejection and marks legacy unattributed drafts as
unapprovable; independent verification
sets `verified` only and publication remains separate. The focused
Gateway/route-policy/console/source-reference/safety selection passes 64 tests
with nine PostgreSQL-dependent skips;
disposable PostgreSQL 16 applies/replays 521–524 with 12 grouped checks. Ruff,
Python compilation, and inline JavaScript syntax checks pass. Candidate and
legacy remain untouched; migration 524 is not rolled out. Legacy agent
identity, other global-reference and background-agent lineage, full source
snapshots, populated parity, live OIDC/browser, runtime recovery, and MAN-CAP-038
remain open ([agent contract](agent-ecosystem-kernel-contract.md); [disposable
evidence](builds/2026-10-20-recovery/cap-038-ai-summary-global-source-references-disposable.json)).

**Latest implementation slice — 20 October 2026:** The optional Directus
weekly callback now identifies its real effect: a grouped read of verified,
source-eligible farm activity that returns location-week rows and persists no
snapshots. Its log no longer reports snapshots as created. The daily NOI batch
reports succeeded/failed crop-cycle totals and flags partial failure instead of
logging an apparently complete success count. The 72-test extension suite and
Directus extension build pass. Directus hook and schedule ownership/output
parity remain open; the daily NOI callback still runs through the Directus
database connection and needs reconciliation with the default-off signed
per-location NOI worker. See the [parity inventory](directus-parity-inventory.md),
[weekly evidence](builds/2026-10-20-recovery/directus-weekly-schedule-effect.json),
and [NOI evidence](builds/2026-10-20-recovery/directus-noi-partial-failures.json).

**Latest CAP-038 implementation slice — 20 October 2026:** The shared
`SynthesisAgent` and standalone AI-summary runners now validate declared
top-level output presence, types, and UUID formats before draft persistence,
so invalid output cannot be committed as an agent-created draft. Eighty-six
focused agent-module, task-schema, and persistence-boundary checks pass,
including no insert or commit on invalid output and guaranteed connection
close; no database or model provider was contacted. Nested content validation,
authenticated agent identities, least-privilege table access, populated parity,
live provider behavior, and a separate human approval workflow remain open. See the
[agent contract](agent-ecosystem-kernel-contract.md) and
[evidence](builds/2026-10-20-recovery/cap-038-agent-draft-validation.json).

Agent task entry points now also validate declared required inputs, primitive
types, UUIDs, and exact `YYYY-MM-DD` dates before database access or Delphi
facilitator initialization. The 19-file focused run passes 172 tests with nine
database-dependent skips; mocked preflight checks, Ruff, Python compilation,
and capability-matrix validation pass. This is shape validation only; caller
identity, tenant authorization, runtime database least privilege, populated
task/provider parity, and recovery remain open ([input evidence](builds/2026-10-20-recovery/cap-038-agent-input-preflight.json)).

Draft persistence helpers now repeat validation at the write boundary, so direct
calls cannot bypass the shared/standalone runner checks. The two-file fake-
connection regression passes 15 tests and confirms malformed input/content is
rejected before a cursor or commit; the broader 19-file agent selection passes
182 tests with nine PostgreSQL-trigger checks skipped for lack of a configured
database. This still creates drafts only and does not establish agent identity
or tenant authorization ([write-boundary evidence](builds/2026-10-20-recovery/cap-038-agent-draft-write-boundary.json)).

The task catalogue now validates its own supported top-level input/output schema
declarations whenever a task is listed or invoked. Unsupported types, formats,
required flags, or schema keywords fail closed, even for omitted optional
fields. The focused catalogue/input/shared-runner selection passes 35 tests;
nested object/array schemas remain undefined ([catalogue evidence](builds/2026-10-20-recovery/cap-038-agent-schema-catalog.json)).

**Latest code-first audit slice — 20 October 2026:** The optional Directus parity inventory now includes a deterministic source report for literal permission declarations. It counts 175 declared rule rows, of which 125 use wildcard fields and 50 use explicit field lists; it identifies 28 wildcard Auditor declarations, confirms zero literal `farm_activity` permission insertions, and records four permission updates plus one deletion. The generated JSON is freshness-checked in CI, and parser regressions cover quoted delimiters and SQL comments. This is not effective deployed permission state and does not alter role access; conditional seed logic, later mutations, custom policies, relation parity, hook effects, and runtime acceptance remain open. See the [parity inventory](directus-parity-inventory.md), [checker](../scripts/directus_permission_inventory.py), [tests](../tests/test_directus_permission_inventory.py), and [source report](builds/2026-10-20-recovery/directus-permission-source-inventory.json).

**CAP-047 offline CLI preflight — 20 October 2026:** standalone and unified
data-freshness help and invalid argument combinations now return before
secret-bearing database configuration is imported. The 37-test freshness
suite, Ruff, Python compilation, and diff checks pass, including a fresh-
process entrypoint parity check. This
closes only avoidable secret loading and connection attempts from help/invalid
CLI invocations; it does not establish runtime recovery,
provider delivery, retention, or MAN-CAP-047 acceptance
([evidence](builds/2026-10-20-recovery/freshness-cli-offline-preflight.json)).

**CAP-039 ingestion CLI help isolation — 20 October 2026:** actual parser help
for all 19 mounted ingestion modules passes in a production-like environment
without database credentials or a decryptable SOPS identity. The test verifies
zero exit status and nonempty help per module. Non-help CLI output contracts and
MAN-CAP-039 owner acceptance remain open ([test](../tests/test_ingestion_cli_help_isolation.py);
[evidence](builds/2026-10-20-recovery/cap-039-ingestion-help-isolation.json)).

**Latest implementation slice — 20 October 2026:** CAP-035 now requires an immutable exact-purpose/version participant-consent policy on every submitted adoption program and provides consent-aware event capture through migration 520. The creator configures the policy before submission, and the independent review queue displays its terms. `solution_lifecycle:collect` hashes the opaque participant reference before database access; PostgreSQL requires an active exact-location participant link plus the latest matching consent grant, stores only link/consent IDs, and makes exact retries immutable. Withdrawal and link revocation remove participants from current projections; phase breakdowns below five are suppressed. The legacy direct writer remains fail-closed. Focused Gateway/console checks pass 113 tests; the expanded migration-metadata and exact route-policy selection passes 149 tests. Disposable PostgreSQL 16 applies/replays migrations 513–520 with 51 grouped consent, authorization, retry, privacy, lifecycle, and privilege checks. Ruff, Python compilation, capability-matrix validation, runtime SQL inventory, repository inventory, and diff checks pass. Candidate and legacy databases are untouched; migration 520 is not rolled out. Checklist: 782 complete / 24 open; matrix: 31 baseline-retained, 7 deployed, and 28 prepared. See the [write contract](solution-lifecycle-kernel-write-contract.md), [source audit](solution-lifecycle-source-route-audit.md), and [disposable evidence](builds/2026-10-20-recovery/cap-035-adoption-program-disposable.json).

**Latest code-first audit slice — 20 October 2026:** CAP-036 repository source-lineage inventory is complete. A source checker confirms that one generic helper is the only SQL writer and has no production callers, and that migrations 460/478 use the same three exact location lineages. Unknown subjects remain excluded. This check did not inspect any database; populated/archived corpus mapping and output parity remain open, along with live ZITADEL/browser, broader ACL/RLS, recovery, and MAN-CAP-036 acceptance. See the [lineage inventory](sequential-evidence-subject-lineage-inventory.md), [checker](../scripts/check-sequential-subject-lineage.py), and [evidence](builds/2026-10-20-recovery/cap-036-subject-lineage-source-audit.json). The checklist is 756 complete / 24 open; the capability matrix remains 31 baseline-retained, 7 deployed, and 28 prepared.

**Latest implementation slice — 20 October 2026:** CAP-035 now has an exact-
location Gateway path for non-promotion lifecycle stage transitions. Migration
503 returns bounded exact-origin targets and atomically records the stage,
canonical lifecycle event, and immutable retry receipt under signed read and
transition grants. The write requires an active human binding, explicit
acknowledgement, bounded rationale/evidence, and expected-stage compare-and-set.
Promotion targets remain behind migration 486; retirement and supersession
remain behind the reviewed retirement/replacement workflow; `adopting` keeps
approved location readiness/configuration checks. The console uses fixed
non-promotion choices, CSRF/no-store, stale-location guards, and stable request
IDs. The focused Gateway, route-policy, console-contract, and gate-transition
selection passes 38 tests; Ruff and Python compilation pass. Disposable
PostgreSQL 16 applies/replays migration 503 and passes 14 grouped checks.
Candidate and legacy remain untouched and migration 503 is not rolled out.
CAP-035 remains prepared pending populated parity, live OIDC/browser, broader
ACL/RLS, recovery, and owner acceptance. Checklist: 755 complete / 24 open;
matrix: 31 baseline-retained, 7 deployed, and 28 prepared across 66 rows. See
the [write contract](solution-lifecycle-kernel-write-contract.md), [source
audit](solution-lifecycle-source-route-audit.md), and [evidence](builds/2026-10-20-recovery/cap-035-nonpromotion-stage-transition-disposable.json).
legacy direct learning insert in `solution_scale.record_learning`; proposals
must use the exact-location Gateway flow, independent review, and accepted-only
application. The focused fail-before-cursor regression passes. A source-to-route
audit inventories remaining direct solution, experiment, adoption, and funding
effects and leaves them open, including current-consent verification for
adoption events and a separately governed disbursement path. No candidate or
legacy database was inspected or changed. CAP-035 remains prepared pending
remaining parity, populated fixtures, live ZITADEL/browser acceptance, broader
ACL/RLS, recovery, and owner acceptance. Checklist: 751 complete / 24 open;
matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence:
[source-to-route audit](solution-lifecycle-source-route-audit.md).

**Latest implementation slice — 20 October 2026:** CAP-035 retirement is now
implemented through migration start, effective sunset, and independent
post-retirement review. Migration 502 requires exact signed location transition
or review scope, an independently approved plan, distinct active humans, and an
operator-selected timezone-aware effective time. Migration leaves the solution
active; sunset waits until the approved time, then atomically retires the
solution and records its lifecycle event; a separate human completes the review.
Immutable receipts preserve exact retry behavior, and runtime/Directus cannot
access them directly. The console provides grant-gated acknowledged forms with
CSRF/no-store and stable request IDs. No records are deleted or pruned, and
retention/legal-hold periods remain configurable. The focused selection passes
134 tests with one database-backed skip; Ruff, compilation, inline JavaScript,
capability-matrix validation, and runtime SQL inventory checks pass. Disposable
PostgreSQL 16 applies/replays migration 502 after the CAP-035 chain and passes
nine acceptance groups. Candidate and legacy remain untouched; migration 502 is
not rolled out. CAP-035 remains prepared pending populated parity, live
ZITADEL OIDC/browser, broader ACL/RLS, recovery, and owner acceptance. Checklist:
749 complete / 24 open; matrix: 31 baseline-retained, 7 deployed, 28 prepared.
See the [write contract](solution-lifecycle-kernel-write-contract.md),
[migration](../schemas/postgres/502_location_solution_retirement_execution.sql),
[tests](../tests/test_gateway_solution_retirement_execution.py), and
[disposable evidence](builds/2026-10-20-recovery/cap-035-retirement-execution-disposable.json).

**Previous implementation slice — 20 October 2026:** CAP-035 now has a
separate exact-location funding tranche review and approval. Migration 492
requires an approved funding case, a proposed tranche, explicit acknowledgement,
signed `solution_lifecycle:review`, and an active reviewer distinct from the
case submitter and case approver. It records only the tranche decision and
reviewer attribution with an immutable retry receipt; no funds are released and
the solution stage does not change. The console provides a text-only review of
bounded milestone terms and CSRF-protected approval with a stable retry ID. The
focused Gateway, route-policy, console, and migration selection passes 117
tests; Ruff, Python compilation, inline JavaScript syntax, capability-matrix
validation, and runtime SQL inventory checks pass. Disposable PostgreSQL 16
applies/replays migration 492 and verifies reviewer independence, scope, retries,
role boundaries, unchanged release state, and unchanged stage. Candidate and
legacy databases remain untouched; migration 492 is not rolled out. CAP-035
remains prepared pending populated parity, live OIDC/browser, broader ACL/RLS,
recovery, and owner review. Checklist: 737 complete / 24 open; matrix: 31
baseline-retained, 7 deployed, 28 prepared. See the [write
contract](solution-lifecycle-kernel-write-contract.md),
[migration](../schemas/postgres/492_location_solution_funding_tranche_review.sql),
[focused tests](../tests/test_gateway_solution_lifecycle_funding_proposals.py), and
[disposable evidence](builds/2026-10-20-recovery/cap-035-solution-funding-tranche-approval-disposable.json).

**Previous implementation slice — 20 October 2026:** CAP-025 now has a
location-scoped reviewer console under the exact `stakeholder_identity:review`
grant. It uses the consent-aware pending queue, withholds source identifiers and
raw feedback, disables decisions when names are unavailable, and submits fixed
reason-code decisions with confirmation, CSRF, and retry-stable request IDs;
independent review remains database-enforced. CAP-035 now exposes bounded gate
and experiment status pages in the lifecycle console. The gate page shows
structural thresholds and latest evaluation state without evidence or reviewer
identity; the experiment page shows fixed lifecycle metadata and only the latest
explicitly reviewed outcome, without protocol narratives, metrics/values,
observations, adverse-event details, or evidence. The funding page exposes only
case/tranche lifecycle labels, currency, and timestamps, never amounts, terms,
rationale, evidence, or participant identities. Five additional paged status
views cover adoption programs, scale gates, replications, learning, and
retirements under the same exact location grant; fixed fields omit IDs,
narratives, evidence, and person-level details, and adoption cohort counts
remain hidden below the database threshold. The console also allows operators
with both exact read and create grants to propose learning from a completed,
reviewed replication. It uses the existing bounded action, explicit confirmation,
CSRF/no-store requests, and retry-stable request IDs; new records remain proposed
for independent review, with no decision or application controls. The combined
CAP-025/CAP-035 console, Gateway, action, and route-policy selection passes 166
tests; Ruff, inline JavaScript parsing, capability validation, inventory refresh,
and diff checks pass. No database, migration, candidate, or legacy system was
used.
CAP-025 and CAP-035 remain prepared pending their remaining source/workflow
parity, populated fixtures, live OIDC/browser, broader ACL/RLS, recovery, and
owner acceptance. Checklist: 725 complete / 24 open; matrix: 31
baseline-retained, 7 deployed, 28 prepared across 66 rows. Evidence:
[CAP-025 contract](stakeholder-identity-kernel-contract.md),
[CAP-035 contract](solution-lifecycle-kernel-read-contract.md), [console](../apps/operator-console/index.html), and
[CAP-035 console tests](../tests/test_operator_console_solution_lifecycle.py).

**Previous implementation slice — 20 October 2026:** CAP-035 now has a
read-only operator-console overview for its location-scoped lifecycle summary,
visible only with exact `solution_lifecycle:read`. It displays the solution
total and fixed aggregate status groups in collapsed sections; it exposes no
row detail and adds no mutation controls. The focused console/Gateway/route-
policy selection passes 89 tests, including JavaScript syntax validation; Ruff
and capability checks pass. No database was used. CAP-035 remains prepared
pending detail/workflow parity, populated fixtures, live OIDC/browser, broader
ACL/RLS, recovery, and owner acceptance. Checklist: 711 complete / 24 open;
capability matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence:
[contract](solution-lifecycle-kernel-read-contract.md),
[console](../apps/operator-console/index.html), and
[console checks](../tests/test_operator_console_solution_lifecycle.py).

**Previous implementation slice — 19 October 2026:** the operator console now
surfaces CAP-037's existing summary, demand, and capacity-period GET routes for
locations with an exact `operating_pilot:read` session grant. It uses
same-origin/no-store requests, discards stale location responses, displays only
fixed aggregate summary keys, and hides capacity totals for suppressed cohorts.
The focused console/Gateway/route-policy selection passes 37 tests, including
inline JavaScript syntax validation; Ruff and capability-matrix validation
pass. No database was used and migration 480 remains unrolled on the candidate.
CAP-037 remains prepared pending item-level workflows, populated scope and
legacy parity, audience review, live OIDC/browser behavior, broader ACL/RLS,
recovery, and owner acceptance. Checklist: 709 complete / 24 open; capability
matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence: [read
contract](operating-pilot-kernel-read-contract.md), [console](../apps/operator-console/index.html), and
[console checks](../tests/test_operator_console_operating_pilot.py).

**Previous implementation slice — 19 October 2026:** CAP-036 now has an
operator-console panel for the existing sequential evidence summary and ordered
event timeline, gated by exact `sequential_evidence:read` location grants. It
uses fixed summary/row allowlists, same-origin no-store reads, stale-location
response guards, and 25-item pages. The view exposes no statements, source
references, evidence values, probabilities, or identities and does not perform
threshold actions. The focused console/Gateway/route-policy selection passes
28 tests, including inline JavaScript syntax validation; Ruff and capability
validation pass. No database or provider was used. CAP-036 remains prepared pending full source lineage, populated parity,
live OIDC/browser acceptance, broader ACL/RLS, recovery, and owner review.
Checklist: 710 complete / 24 open; matrix: 31 baseline-retained, 7 deployed,
28 prepared. Evidence: [contract](sequential-decision-kernel-read-contract.md),
[console](../apps/operator-console/index.html), and
[console checks](../tests/test_operator_console_sequential_evidence.py).

**Previous implementation slice — 19 October 2026:** CAP-037 now has a
bounded aggregate capacity-period page at
`GET /operator/api/operating-pilot/{location_id}/capacity-periods`. Migration
480 groups submitted/approved profiles by period under an active Adelphi farm
mapped to the exact location, and hides all hours when fewer than three people
contribute. The 64-test Gateway/route-policy/migration selection passes;
disposable PostgreSQL 16 apply/replay for migrations 461, 479, and 480 passes
13 grouped authorization, paging, privacy, and privilege checks. Candidate and
legacy databases remain untouched; migration 480 is not rolled out. CAP-037
remains prepared pending item-level capacity and other workflow parity,
populated mapping, audience review, live OIDC/browser, broader ACL/RLS,
recovery, and owner acceptance. Checklist: 708 complete / 24 open; capability
matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence: [contract](operating-pilot-kernel-read-contract.md), [migration](../schemas/postgres/480_location_operating_pilot_capacity_periods.sql), and [disposable acceptance](builds/2026-10-19-recovery/cap-037-operating-pilot-capacity-disposable.json).

**Previous implementation slice — 19 October 2026:** CAP-036 now has a redacted location-scoped event timeline at `GET /operator/api/sequential-evidence/{location_id}/events`. Migration 478 pages stable evidence and posterior sequence metadata for the three known location-bound subject lineages; private narratives, source identifiers, evidence values, likelihoods, probabilities, and identities stay inside PostgreSQL. The focused Gateway/route-policy selection passes 23 tests, Ruff and compilation pass, and disposable PostgreSQL 16 migration apply/replay passes eight acceptance groups. Candidate and legacy databases remain untouched; migration 478 is not rolled out. CAP-036 remains prepared pending complete source-type lineage, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and owner review. Checklist: 706 complete / 24 open; capability matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence: [read contract](sequential-decision-kernel-read-contract.md), [migration](../schemas/postgres/478_location_sequential_evidence_timeline.sql), and [disposable acceptance](builds/2026-10-19-recovery/cap-036-sequential-evidence-timeline-disposable.json).

**Latest implementation slice — 19 October 2026:** CAP-035 now has a location-scoped learning proposal action at `POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning`. Migration 477 validates a completed, actively reviewed replication, exact location and solution lineage, a signed create grant, active proposer attribution, bounded lesson fields, and an idempotency receipt. Proposals remain `proposed`; runtime has no direct table access and Directus cannot execute the function. The focused Gateway/route-policy selection passes 16 tests; Ruff, compilation, and disposable PostgreSQL 16 apply/replay checks pass, including nine acceptance groups. Candidate and legacy databases remain untouched; migration 477 is not rolled out. CAP-035 remains prepared pending remaining lifecycle workflows, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and owner review. Checklist: 705 complete / 24 open; capability matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence: [learning proposal contract](solution-lifecycle-kernel-read-contract.md), [migration](../schemas/postgres/477_location_solution_learning_proposal.sql), and [disposable acceptance](builds/2026-10-19-recovery/cap-035-solution-learning-proposal-disposable.json).

**Current local slice — 19 October 2026:** CAP-040 has durable MQTT receipts and a disposable Mosquitto/Paho crash-redelivery check; its commits through `834187e8` are pushed to PR #68. CAP-041 restores SOC training coordinates, adds deterministic sample-balanced field folds, and exercises synthetic spatial-block CV; 22 focused DSM tests, 95 DSM/geostatistics/spectral tests, and disposable PostgreSQL/PostGIS checks pass. CAP-042 projects Guild Registry metadata, steward, and status into a reorg-cleared chain-owned metadata subobject; its disposable run replayed all 452 schemas and checked ten synthetic events, duplicate replay, reorg rebuild, database restart, and lease reclaim, with 14 focused tests passing. CAP-043 fixes repeat credit issuance serial collisions with an appended UUPS-safe counter and legacy serial-zero fallback; its proxy suite passes 17 tests, the issuance fuzz case passes 1,000 runs, and all 67 Foundry tests pass. CAP-041/042/043 were pushed together to PR #68 at `d947b77f`. CAP-044 lets authorized updaters refresh expired oracle feeds and adds explicit freshness-checked reads; its 13-test suite and a 256-case freshness fuzz test pass. CAP-045 makes malformed proof shapes and unsupported direction flags return false; its 10-test suite and a 256-case invalid-flag fuzz test pass. CAP-046 rejects zero-address initial resolver attesters and verifies EAS-only callback gates with synthetic calls; its 12-test suite passes. The complete Foundry suite passes 81 tests across seven suites. CAP-048 suppresses misleading preempt proposals for falling metrics until a normal baseline exists, and reports invalid percentage/operator configuration; 22 focused tests pass with Ruff and compilation. CAP-049 rejects non-finite/non-positive draft credits and conflicting idempotency-key reuse while returning the original row for exact retries; 12 focused capital-accounting tests pass with Ruff and compilation. CAP-050 stabilizes parallel Monte Carlo result ordering and isolates per-draw setup/simulator/metric failures; 14 focused tests pass with Ruff and compilation. CAP-044–046, CAP-048, and CAP-049 are pushed to PR #68 at `bc3a3cdd`. CAP-050 (`70875dc6`) stabilizes seeded parallel simulation results; CAP-052 repairs exact-row upgrade history transitions and health-timeout failure recording. CAP-050 and CAP-052 were pushed together to PR #68 at `765d0769` after focused simulation and upgrade checks, shell syntax, Ruff/compilation, and capability-matrix validation passed. CAP-054 repairs tree density's invalid plot-area query, normalizes supported units in service calculations and public view migration 462, and preserves zero-valued measurements; 20 focused tests and a disposable PostGIS apply/replay pass. CAP-054 (`280bfc46`) and CAP-055 (`3876b299`) were pushed together to PR #68. CAP-055 hardens price consensus against invalid measurements and duplicate providers; its 38 focused oracle tests pass with Ruff and compilation. CAP-056 scopes channel plans by segment, redacts credential-shaped values on preferred and default plans, filters inactive channels, and rejects invalid break-even math before DB access; six mocked tests pass with Ruff and compilation. CAP-057 fixes same-run environmental scan communication and binds PESTEL factors to their analysis location with bounded finite scores; 11 focused mocked tests pass with Ruff and compilation. CAP-056 and CAP-057 were pushed together to PR #68 at `a15e8776`; CAP-058 was pushed at `b1ed227f`; CAP-059 was pushed at `5a6bc596` after 66 mocked/schema checks; CAP-060 was pushed at `662b8c90` after 14 JSON-LD alignment tests. CAP-061 aligns Regen Claim fields/enums with migration constraints, declares Regen Project/CreditClass/Claim class URIs, and preserves explicit CURIE types; 142 linked-data/schema tests pass with Ruff, compilation, and YAML parsing. CAP-061 was pushed to PR #68 at `5effda82`. CAP-062 hardens marketplace fee collection/distribution and wires paired origin transaction references into batch creation and the unique origin index; CLI inputs are available. The focused credit/marketplace/linked-data/Data Stream/Gateway/gRPC selection passes 295 tests, one database-dependent skip, and 17 subtests with Ruff, compilation, CLI help, and generated-protobuf freshness. Data Stream stores caller-supplied timezone-aware expiry as UTC metadata without applying a retention period. The gRPC CreateBatch request now forwards origin references. CAP-062 remains partial: expiry-policy enforcement/cleanup and other expiry-bearing entities, PostgreSQL duplicate-origin rollback and concurrency, and populated settlement parity remain open. CAP-063 hardens retained CSW serializers against markup injection, uses safe popup text and bounded coordinates in the Leaflet viewer, validates boundary rings, preserves Polygon/MultiPolygon holes, and adds hardened KML Polygon/MultiGeometry parsing; 70 CSW/GIS/map, spatial-KML, security, raster-metadata, CSW catalog, and import-redaction tests pass. The tenant-scoped map API, KML style/altitude and raster support, endpoint/catalog, and GeoNode fixture parity remain open. Candidate and legacy databases and deployed contracts are untouched. CAP-064 now preserves registered gRPC streaming cardinality when authentication fails; all four RPC shapes have denial regressions, and enabled loopback confirms missing credentials on a server-streaming method return UNAUTHENTICATED before service database access. The focused six-suite gRPC selection passes 44 tests with Ruff and compilation; TLS, runtime-role/tenant scope, and REST parity remain open ([evidence](builds/2026-10-19-recovery/cap-064-grpc-denial-cardinality.json)). CAP-065 continues to validate exactly one organization or location scope before suggestion reads or writes. In addition to the first Gateway draft-create route, `POST /operator/api/business-planning/{location_id}/canvases/from-data` now establishes signed context before scoped suggestion reads and creates the draft within that same transaction; it rejects caller-supplied blocks and returns source categories plus populated blocks. The focused Gateway/policy/legacy suggestion selection passes 42 tests, with eight database-backed legacy checks skipped because local PostgreSQL is unavailable. Ruff, compilation, matrix validation, and diff checks pass. The earlier 105-test Gateway/auth/policy/migration/report selection and disposable PostgreSQL 16 apply/replay acceptance for migrations 457/463 remain recorded; candidate and legacy databases were not touched and migration 463 is not rolled out. Thirteen-section status, edit/version parity, populated output and row-level source evidence parity, live OIDC/browser, universal ACL/RLS, and MAN-CAP-065 remain open ([generated-draft evidence](builds/2026-10-19-recovery/cap-065-gateway-generated-draft.json); [draft acceptance](builds/2026-10-19-recovery/cap-065-business-canvas-create-disposable.json); [scope evidence](builds/2026-10-19-recovery/cap-065-bmc-scope-preflight.json)). CAP-066 now keeps State of Kokonut funding source and participation rollups currency-aware; the mixed-currency scalar is suppressed, with per-currency totals returned instead. Fourteen report/graph tests pass with Ruff and compilation on synthetic USD/USDC rows; no FX conversion or populated parity is claimed ([evidence](builds/2026-10-19-recovery/cap-066-funding-currency-dimensions.json)). CAP-065 legacy BMC suggestions now use current location-bound schema fields, verified/published records, native-currency costs, and consented public-feedback cohorts; five focused tests pass, while eight PostgreSQL-backed service tests remain skipped because local PostgreSQL is unavailable. Gateway-native generation is now implemented; populated parity remains open ([evidence](builds/2026-10-19-recovery/cap-065-bmc-suggestion-sources.json)). CAP-066 farm summaries and State/comprehensive network rollups now preserve harvest quantity units, suppressing mixed-unit scalars; 17 focused tests pass with Ruff and compilation on synthetic rows ([evidence](builds/2026-10-19-recovery/cap-066-harvest-unit-rollups.json)). CAP-040/041/042/043/044/045/046/048/049/050/052/054/055/056/057/058/059/060/061/062/063/064/065 remain unaccepted; sensor/outbox and model fixture parity, production MQTT security/provider behavior, fitted-model geographic metrics, live-chain behavior, credit ledger/custody parity, oracle freshness/reference-price parity/consensus tolerance, disclosure leaf/consumer parity, live EAS/schema behavior, strategic-reserve populated parity, capital-ledger/custody parity, simulation fixture/tolerance parity, live upgrade/rollback and backup restore, tree/pest/export parity, channel credential migration to SOPS references, tenant authorization, external delivery, break-even/reference pricing parity, actuator authorization/delivery/acknowledgment, owner decisions, and named MAN-CAP acceptance remain open. Checklist: 689 complete / 24 open; matrix: 31 baseline-retained, 7 deployed, 28 prepared. Evidence: [MQTT recovery](builds/2026-10-19-recovery/mqtt-delivery-postgresql-mosquitto.json), [CAP-041 coordinates](builds/2026-10-19-recovery/cap-041-spatial-training-coordinates.json), [CAP-041 folds](builds/2026-10-19-recovery/cap-041-geographic-fold-repeatability.json), [CAP-042 registry projection](builds/2026-10-19-recovery/cap-042-guild-registry-projection-reorg.json), [CAP-043 serial identity](builds/2026-10-19-recovery/cap-043-credit-serial-identity.json), [CAP-044 oracle freshness](builds/2026-10-19-recovery/cap-044-oracle-freshness.json), [CAP-045 proof shape](builds/2026-10-19-recovery/cap-045-proof-shape.json), [CAP-046 resolver gates](builds/2026-10-19-recovery/cap-046-resolver-gates.json), [CAP-048 trigger semantics](builds/2026-10-19-recovery/cap-048-preempt-trigger-semantics.json), [CAP-049 credit idempotency](builds/2026-10-19-recovery/cap-049-credit-idempotency.json), [CAP-050 simulation determinism](builds/2026-10-19-recovery/cap-050-simulation-determinism.json), [CAP-052 upgrade history](builds/2026-10-19-recovery/cap-052-upgrade-history-transition.json), [CAP-054 tree tracking](builds/2026-10-19-recovery/cap-054-tree-area-and-growth.json), [CAP-055 Oracle input validation](builds/2026-10-19-recovery/cap-055-oracle-input-validation.json), [CAP-056 channel redaction](builds/2026-10-19-recovery/cap-056-channel-plan-secrets.json), and [CAP-057 environmental scanning](builds/2026-10-19-recovery/cap-057-environmental-scan-scope.json), and [CAP-058 marketplace inputs](builds/2026-10-19-recovery/cap-058-marketplace-inputs.json), and [CAP-059 Abundance guards](builds/2026-10-19-recovery/cap-059-abundance-governance-guards.json), and [CAP-060 JSON-LD namespaces](builds/2026-10-19-recovery/cap-060-jsonld-uri-roundtrip.json), and [CAP-061 Regen schema crosswalk](builds/2026-10-19-recovery/cap-061-regen-schema-crosswalk.json), [CAP-062 fee settlement](builds/2026-10-19-recovery/cap-062-fee-distribution-settlement.json), [CAP-063 CSW/GIS/map](builds/2026-10-19-recovery/cap-063-csw-xml-safety.json).

**Previous local slice — 19 October 2026:** CAP-036 adds `GET /operator/api/sequential-evidence/{location_id}/summary` under exact `sequential_evidence:read` and signed tenant context. Migration 460 returns aggregate hypothesis lifecycle, evidence-quality, posterior-update, applied-event, and latest threshold-action counts only for exact location-scoped strategy plans, threats, and explicitly location-linked solutions. It excludes statements, event IDs, source references, values, likelihoods, probabilities, and identities; ledger writes and calculations are unchanged. The focused Gateway, route-policy, migration-metadata, and legacy decision selection passes 53 tests with two database-dependent skips; disposable PostgreSQL 16 applies/replays migration 460 and passes six scope, lineage, privacy, and privilege assertions. Candidate and legacy databases are untouched; CAP-036 remains prepared pending ordered item-level reads, remaining source lineage, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-036 owner review. Checklist at that checkpoint: 677 complete / 21 open; matrix: 34 baseline-retained, 7 deployed, 25 prepared. Evidence: [CAP-036 contract](sequential-decision-kernel-read-contract.md) and [CAP-036 acceptance](builds/2026-10-19-recovery/cap-036-sequential-decision-disposable.json).

**Previous local slice — 19 October 2026:** CAP-035 adds `GET /operator/api/solution-lifecycle/{location_id}/summary` under exact `solution_lifecycle:read` and signed tenant context. Migration 459 supports explicit location links and returns aggregate lifecycle, gate/evaluation, experiment/outcome, funding-decision, adoption/configuration/readiness/scale, learning, and retirement state without identities, narratives, evidence, amounts, or raw payloads. The focused Gateway, route-policy, and migration-metadata selection passes 44 tests; disposable PostgreSQL 16 applies/replays migration 459 and passes six scope, aggregate, privacy, and privilege assertions. Candidate and legacy databases are untouched; CAP-035 remains prepared pending item-level workflows, populated parity, live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-035 owner review. Checklist: 676 complete / 20 open; matrix: 35 baseline-retained, 7 deployed, 24 prepared. Evidence: [CAP-035 contract](solution-lifecycle-kernel-read-contract.md) and [CAP-035 acceptance](builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json).

**Previous local slices — 19 October 2026:** CAP-031 has an internal location budget read at `GET /operator/api/planning/{location_id}/budgets`. Migration 455 rechecks exact `planning_budget:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. It includes only plans owned by the location's current organization with budget lines assigned to that location. Results contain plan status/currency/period, planned amount, verified same-currency expenses and variance, foreign-currency expense count, and scenario count; plan labels, categories, objective identity, assumptions, and transaction details are excluded. The focused Gateway, exact route-policy, and migration-metadata selection passes 49 tests. Disposable PostgreSQL 16 applies/replays migration 455 and passes seven lineage, currency, scope, privacy, and ACL assertions. CAP-032 adds `GET /operator/api/business-architecture/{location_id}/summary`, protected by exact `business_architecture:read` and signed tenant context; focused selection passes 48 tests and migration 456 replay passes seven scope/approval/privacy/privilege assertions. CAP-033 adds `GET /operator/api/business-planning/{location_id}/canvases` under exact `business_planning:read`; migration 457 returns location-only canvases with governed lifecycle, nine content blocks, and source references while excluding raw imports, metadata, actors, and organization canvases; 48 focused tests and seven disposable assertions pass. CAP-034 adds `GET /operator/api/coordination/{location_id}/summary` under exact `coordination:read`; migration 458 returns aggregate governance indicators only for exact location alliances and does not alter approval, consent, activation, or publication; 42 focused tests and six disposable assertions pass. Candidate and legacy databases are untouched; migrations 455–458 are not rolled out. CAP-031 remains partial; CAP-032–034 are prepared. Generated pitch/business-plan parity, populated-data parity, live OIDC/browser, trigger/worker recovery, universal ACL/RLS, and owner acceptance remain open. Checklist: 675 complete / 19 open; matrix: 36 baseline-retained, 7 deployed, 23 prepared. Evidence: [CAP-031 contract](planning-budget-kernel-read-contract.md), [CAP-031 acceptance](builds/2026-10-19-recovery/cap-031-budget-summary-disposable.json), [CAP-032 contract](business-architecture-kernel-read-contract.md), [CAP-032 acceptance](builds/2026-10-19-recovery/cap-032-business-architecture-disposable.json), [CAP-033 contract](business-planning-kernel-read-contract.md), [CAP-033 acceptance](builds/2026-10-19-recovery/cap-033-business-canvas-disposable.json), [CAP-034 contract](coordination-kernel-read-contract.md), and [CAP-034 acceptance](builds/2026-10-19-recovery/cap-034-coordination-summary-disposable.json).

**Previous local slice — 19 October 2026:** CAP-030 now has a location-scoped management summary at `GET /operator/api/management/{location_id}/summary`. Migration 454 rechecks exact `management_workflow:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. The response aggregates work lifecycle/open-priority counts, overdue/SLA totals, claim/escalation totals, and latest event time for exact location matches; task content, personal identities, estimated effort, notes, and escalation reasons are excluded. The focused Gateway, route-policy, and migration-metadata selection passes 42 tests. Disposable PostgreSQL 16 applies/replays migration 454 and passes seven scope, aggregate, privacy, and ACL assertions. Candidate and legacy databases are untouched; migration 454 is not rolled out. CAP-030 remains prepared, not accepted: assignment/transition, claim review, dynamic SLA policy, escalation mutation/audit parity, unscoped work-item review, populated fixtures, live OIDC/browser behavior, universal ACL/RLS, and MAN-CAP-030 owner review remain open. Checklist: 671 complete / 19 open; matrix: 39 baseline-retained, 7 deployed, 20 prepared. Evidence: [CAP-030 contract](management-work-kernel-read-contract.md) and [disposable acceptance](builds/2026-10-19-recovery/cap-030-management-work-summary-disposable.json).

**Previous local slice — 19 October 2026:** CAP-029 now has a location-scoped Kernel read at `GET /operator/api/competitive-landscape/{location_id}/summaries`. Migration 453 rechecks exact `competitive_landscape:read` and signed tenant context inside PostgreSQL, using a dedicated non-login reader role. The bounded response contains landscape metadata and aggregate actor/threat, Five Forces, signal, verified advantage, and outcome signals; identity, narrative, evidence, source references, statements, and individual outcome values are excluded. The focused Gateway and exact route-policy selection passes 16 tests; the combined Gateway, policy, migration-metadata, and legacy parity selection passes 56 tests with two skips. Disposable PostgreSQL 16 applies/replays migration 453 and passes seven aggregate, scope, grant, pagination, output-contract, and ACL assertions. Candidate and legacy databases are untouched; migration 453 is not rolled out. CAP-029 remains prepared, not accepted: workflow/report/dashboard parity, populated fixture comparison, live OIDC/browser behavior, universal runtime ACL/RLS, and MAN-CAP-029 owner review remain open. Checklist: 670 complete / 19 open; matrix: 40 baseline-retained, 7 deployed, 19 prepared. Evidence: [CAP-029 contract](competitive-landscape-kernel-read-contract.md) and [disposable acceptance](builds/2026-10-19-recovery/cap-029-competitive-landscape-disposable.json).

**Previous local slice — 19 October 2026:** CAP-024's tactical content implementation is ready for owner review. Migration 445 adds Gateway creation of open tactical items and exact-grant edits for open items/planned sessions, with signed tenant context, active person binding, same-location reference validation, lifecycle separation, stable idempotent retries, and private immutable before/after history. Runtime and Directus direct writes are denied; the function owner has only column-scoped writes and the narrow `UPDATE(id)` row-lock privileges. The operator console now has grant-gated CSRF/no-store forms. The focused mutation slice passes 19 tests; the broader CAP-024 Gateway, route-policy, and console suites pass 182 tests with five skips; migration metadata passes 42 tests, and disposable PostgreSQL 16 applies/replays migrations 437–445 and verifies scope, bindings, lifecycle boundaries, retries/collisions, audit, and ACLs. Ruff, compilation, JavaScript syntax, capability validation, SQL inventory, and diff checks pass. Candidate remains at migration 444; no candidate/legacy DB was changed. Checklist: 658 complete / 19 open (677 total); matrix remains 45 baseline-retained, 7 deployed, 14 prepared. CAP-024 remains prepared rather than MAN-CAP accepted; least-privilege rollout, remaining report/populated-fixture parity, tenant RLS, live OIDC/browser, and accountable-owner review remain open. Evidence: [contract](governance-tactical-content-mutation-contract.md); [database acceptance](builds/2026-10-19-recovery/governance-tactical-content-mutations-disposable.json).

**Previous local slice — 18 October 2026:** CAP-024 now includes audited Gateway creation and draft editing for circles and roles. Migration 443 creates location-scoped definitions only as drafts; draft edits are restricted to descriptive fields and protected by signed tenant context, exact create/update grants, active person binding, same-location circle hierarchy checks, idempotent request history, and an immutable private before/after ledger. Runtime and Directus direct writes are revoked and trigger-guarded. The console exposes CSRF-protected create/edit controls and loads circle edit fields from a separate no-store detail route requiring exact location `:read` and `:update` grants; the aggregate summary keeps free text excluded. The focused CAP-024 Gateway, route-policy, and console suite passes 151 tests (5 skipped), and the ordered migration metadata suite passes 42 tests; disposable PostgreSQL 16 applies/replays migrations 437–443 and verifies authorization, scope, retry/collision behavior, draft-only updates, ledger privacy, and direct-write denial. Ruff, compilation, JavaScript syntax, capability validation, and runtime SQL inventory (850 source files / 4,111 execution sites) pass. Candidate remains at migration 437 and uses administrative `PG_USER=kokonut`; migrations 438–443 are not rolled out and the candidate runtime does not yet enforce their ACL boundary. Candidate and legacy databases were not changed. Work is local and uncommitted on `feat/mobile-offline-acceptance`. Checklist: 654 complete / 19 open (673 total); matrix: 45 baseline-retained, 7 deployed, 14 prepared. CAP-024 remains prepared, not accepted: least-privilege candidate rollout, broader parity, populated parity, domain RLS, live OIDC/browser behavior, and named MAN-CAP review remain open ([contract](governance-definition-lifecycle-contract.md); [migration](../../schemas/postgres/443_governance_definition_mutations.sql); [database evidence](builds/2026-10-18-recovery/governance-definition-mutations-disposable.json)).
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

**Current CAP-039 operator-audit slice — 20 October 2026:** Identity disable
now requires a bounded actor label and reason and atomically writes a private
append-only audit record with the PostgreSQL login principal. Focused mocked
checks cover argument validation, CLI output parity, and rollback on session
or audit failure; a disposable PostgreSQL check covers constraints, ACLs,
principal capture, and update/delete/truncate rejection. These records do not
authenticate the actor or close local principal separation. Candidate and
legacy databases remain untouched.

**Current CAP-039 report CLI slice — 20 October 2026:** Standalone and unified
`export --verify`, single-report generation, and automatic batch generation now
compare output. Synthetic auto coverage checks run/item success transitions,
exact location forwarding, read-only calculation, snapshot ordering, and
connection cleanup; an injected report failure is redacted while the next item
continues and the batch is marked partial. Close failures are redacted too.
The full focused selection passes 157 tests, with no database/provider calls.
The checklist is 820 complete / 25 open (845 total); the matrix remains 66 rows
(31 baseline-retained, 7 deployed, 28 prepared). Candidate and
legacy databases were not touched. MAN-CAP-039 owner acceptance, remaining
operator authorization, and live report behavior remain open.

Earlier refactor work recorded a security-hardening batch pushed as `efdd05b5`;
that run and its CI references below are historical checkpoints.
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
current session/scope/tenant layer. The owner selected auth.kokonut.network as the ZITADEL identity hostname on 23 October. Issuer/client
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
| Field Collector | 11, 13 | Expand isolated browser/API checks for retired forms, consent, queue behavior, and cleanup; no-network OIDC checks now cover login/session/logout, invalid claims before DB access, discovery metadata URL, requested scopes, and configured S256 PKCE. | Configure selected ZITADEL after issuer/client settings, test identity, and secrets are provisioned; trusted HTTPS browser origin and human disposition/retention decisions remain open. |
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

CAP-002 now has tenant-scoped, read-only Gateway projections for
verified/published yield summaries, active irrigation-zone status, completed
crop-simulation run summaries and paginated run/daily-state detail, grouped N/P/K balances from the
verified/published latest-budget view, recorded/verified soil-test observations
with advisory nutrient rates, and paginated input/removal records with explicit
lifecycle status. Soil-test and event reads omit notes/metadata; the simulation
endpoints read stored outputs only and do not run the model. The legacy model's
weather jitter now uses a stable integer `weather_seed` (default 0) rather than
process-salted Python hashing. A synthetic two-seed, 30-day fixture passes
under two distinct `PYTHONHASHSEED` values; it is a model regression oracle,
not legacy/populated output parity or agronomic validation. Migration 601 adds
currency-qualified nutrient input capture and aggregation, without mixed-
currency totals or inferred conversion; historic amounts remain unclassified
until reviewed. Continue with owner/populated reference-output parity before
requesting MAN-CAP-002 acceptance.
The endpoints and their limits are recorded in the [yield read
contract](yield-monitoring-kernel-read-contract.md), [irrigation status
contract](irrigation-status-kernel-read-contract.md), [crop-simulation run
contract](crop-simulation-runs-kernel-read-contract.md), [nutrient-balance
contract](nutrient-balances-kernel-read-contract.md), [soil-test
contract](nutrient-soil-tests-kernel-read-contract.md), and [nutrient-events
contract](nutrient-events-kernel-read-contract.md).

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
operators (OFU-16), SMTP endpoint/routing/on-call owner (OFU-05), report retention
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
- **Production operations:** SMTP is the selected alert channel, but its
  production endpoint/credentials, recipient routing/severity, and accountable
  on-call owner remain open (OFU-05); public
  ingress, trusted proxy hops, TLS, and production recovery topology (OFU-06),
  active scheduler inventory/operators (OFU-16), and scheduling the
  owner-selected 24-hour recovery window (OFU-13). Replica/failover checks are
  deferred to production.
- **Provider setup:** `auth.kokonut.network` is the selected identity hostname
  for self-hosted ZITADEL; the exact issuer URL, client ID, callback/redirect,
  test operator identity, and provisioning owner remain open (OFU-07); R2
  credentials and lifecycle policy (OFU-08); browser vault and trusted local
  HTTPS certificate when browser acceptance is scheduled (OFU-10/11).
- **Candidate-only writes:** the five selected reference catalogs (OFU-17) were
  applied to the local candidate after separate approval. The earlier 30-file
  proposal is superseded; pilot rows remain held. The latest recorded local
  candidate rollout is migration 551: 542 schema entries applied, zero
  pending at that source point, and only the app service recreated. Current
  source is through migration 598, so 47 later schema entries require a fresh
  checkpoint, restore rehearsal, ordered rollout, and candidate health checks
  before the candidate is current ([rollout evidence](builds/2026-10-22-recovery/candidate-migration-551-rollout.json)).
  Runtime credential provisioning remains tracked under OFU-19. The candidate
  has six recorded seed entries; 115 unselected seed sources remain pending.

There is no active Raspberry Pi request: OFU-12 records the completed code-only
scope and lack of hardware. If the owner later supplies a Pi, add a separate
physical acceptance record rather than revising emulation evidence.

## Push and release cadence

Keep related changes in local commits and push reviewable batches, as
requested. The latest pushed head is
`d200c72cee37819a2d01948d9bf48072b955d7b6` on PR #68. Security #282 passed;
CI #558 is pending on this head. Review both required hosted checks for the
current head before release decisions.
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

### CAP-043 repeat credit issuance identity — 19 October 2026

Use a dedicated batch/vintage serial counter rather than reading a counter from
the token-amount map. Append storage after the existing proxy layout, and when
the counter is zero check for the original serial-zero token before allocating
the next serial. Reject the zero batch sentinel because it also represents an
uninitialized credit record. Verify repeated direct and batch issuance through
the ERC-1967 proxy, old-proxy counter initialization behavior, per-token amount
preservation, full Foundry regression, and 1,000 fuzz runs. Keep this source
repair separate from deployment: the existing proxy, ledger parity, issuer and
burner custody, pause/retirement policy, and MAN-CAP-043 review need separate
acceptance.

Status: implemented locally and verified; CAP-043 remains baseline-retained,
not accepted. See [serial identity evidence](builds/2026-10-19-recovery/cap-043-credit-serial-identity.json).

### CAP-044 oracle freshness and stale-feed recovery — 19 October 2026

The update path rejected an authorized refresh when the previously stored
price had exceeded `maxAge`, while the contract accepts no source timestamp
that could be independently checked at update time. Age enforcement now lives
on explicit `isFresh` and `getFreshPrice` reads: a missing or expired value
fails closed, the exact `maxAge` boundary remains fresh, and zero `maxAge`
continues to disable expiry. Existing `getPrice` remains available for
backward-compatible raw reads. An authorized updater can refresh a stale feed,
after which the new block timestamp makes it fresh again.

The oracle suite passes 13 tests, including 256 fuzz cases, and the complete
Foundry suite passes all 73 tests. No service consumes the new freshness API
yet, so this contract repair does not establish source timestamp validation,
feed consensus, service parity, or MAN-CAP-044 acceptance. No deployed contract
or chain was touched. See [oracle freshness evidence](builds/2026-10-19-recovery/cap-044-oracle-freshness.json).

### CAP-045 selective disclosure proof shape — 19 October 2026

The verifier indexed `proofFlags` once per proof element without checking the
array lengths, allowing malformed input to panic. It also treated every
nonzero flag as the same direction. Verification now returns `false` unless
proof and flag lengths match and every direction is exactly `0` or `1`, while
keeping the existing boolean API and root-only storage behavior.

The focused suite passes 10 tests, including 256 fuzz cases for unsupported
flags; all 77 Foundry tests pass across seven suites. The contract retains
attestation roots, not disclosed claim data. Leaf construction, consuming-app
integration, and MAN-CAP-045 review remain open. No deployed contract or chain
was touched. See [proof-shape evidence](builds/2026-10-19-recovery/cap-045-proof-shape.json).

### CAP-046 resolver attester configuration and EAS gates — 19 October 2026

The constructor accepted a zero address in `initialAttesters`, unlike the
runtime `addAttester` method. It now rejects that invalid configuration. The
resolver tests also exercise inherited EAS-only callbacks through a synthetic
caller: configured attesters pass both attestation and revocation, unapproved
attesters fail, direct non-EAS calls revert, and removal immediately blocks
both operations under the current allowlist policy.

The resolver suite passes 12 tests, including its 256-run attester fuzz case;
the complete Foundry suite passes 81 tests across seven suites. This does not
verify a real EAS deployment, schema registration, or whether removed
attesters should retain revocation rights. CAP-046 remains unaccepted. No live
chain was contacted. See [resolver evidence](builds/2026-10-19-recovery/cap-046-resolver-gates.json).

### CAP-048 strategic reserve preempt semantics — 19 October 2026

For a falling-is-bad `lt`/`lte` trigger, multiplying the hard threshold by a
fraction below one produced a preempt point that was already beyond the hard
breach. The current schema contains no normal baseline for interpolating a
falling metric, so the health evaluator now reports `baseline_required` and
suppresses that advisory proposal. Rising `gt`/`gte` triggers retain the
zero-baseline calculation for positive hard thresholds and validate the
fraction range `(0, 1)`. Invalid percentages and unsupported triggers do not
produce preempt proposals. Hard-trigger and release behavior is unchanged.

Twenty-two focused reserve/advisory tests pass with Ruff and compilation. No
release execution or database write occurs; populated report parity and
MAN-CAP-048 remain open. See [preempt semantics evidence](builds/2026-10-19-recovery/cap-048-preempt-trigger-semantics.json).

### CAP-049 regenerative credit idempotency — 19 October 2026

Draft credit creation now rejects non-finite and non-positive amounts before
opening a database cursor. When an idempotency key already exists, the service
compares the immutable request fields: an exact retry returns the original
credit, while a changed location, contributor, source, amount, unit, use, or
creator raises a conflict instead of silently looking like a duplicate.
Writes remain draft-only and transaction ownership remains with the caller.

The focused capital-accounting suite passes 12 tests with Ruff and compilation,
including exact retry, payload collision, and invalid amount cases. Database
ledger parity, custody/settlement workflows, and MAN-CAP-049 review remain
open. No database was contacted. See [credit idempotency evidence](builds/2026-10-19-recovery/cap-049-credit-idempotency.json).

### CAP-050 simulation draw ordering and failure isolation — 19 October 2026

The Monte Carlo runner appended values in worker completion order, so a seeded
parallel run could return a different sample sequence. Draw setup also happened
outside the per-draw exception boundary, allowing sampler or DB connection
factory failures to abort the batch. Results now occupy draw-index slots;
sampling, connection setup, simulator calls, and finite-metric validation are
isolated per draw. Failures remain redacted and ordered by draw index.

Fourteen focused simulation tests pass, including sequential/parallel sample
parity, a concurrent connection-factory failure, and non-finite metric
rejection. Ruff and compilation pass. Seeded model fixture parity, agreed
tolerance, and broader tactical coverage remain open; no DB or governed state
was touched. See [simulation evidence](builds/2026-10-19-recovery/cap-050-simulation-determinism.json).

### CAP-052 platform upgrade history — 19 October 2026

Upgrade runs now retain the UUID returned when their `started` history row is
created. Success and failure transition that exact row, so a failed run no
longer inserts a separate `failed` row while leaving the partial unique
`started` row behind, and concurrent history cannot make completion target a
different run. The post-upgrade health-timeout path invokes the failure handler
explicitly because an `exit` builtin does not reliably trigger Bash's `ERR`
trap.

Fourteen focused upgrade-script tests pass, including exact-row transition,
health-timeout handling, backup-manifest tamper detection, and rollback
confirmation. `bash -n scripts/upgrade.sh` passes. No candidate or legacy
database was contacted; live upgrade, rollback, backup restore, and release
checksum parity remain open. See [upgrade-history evidence](builds/2026-10-19-recovery/cap-052-upgrade-history-transition.json).

### CAP-054 tree tracking area units and zero measurements — 19 October 2026

Tree-density code queried and grouped by `plot.area_ha`, which does not exist
in the deployed plot schema; the schema stores `area` plus `area_unit`. The
service now reads those real columns and normalizes hectares, square meters,
and acres. Unsupported, missing, or zero area no longer produces a fabricated
density, and an incomplete plot-area set leaves portfolio density unavailable.
Growth deltas preserve zero-valued measurements, while average canopy growth is
calculated independently from height growth. Forward migration 462 updates the
public tree-density view with matching unit rules; applied migration 057 was
left unchanged.

Twenty focused tree-tracking tests pass with Ruff and compilation. Migration
462 applied twice to a network-isolated disposable PostGIS instance and
synthetic assertions confirmed acre, square-meter, unknown-unit, and zero-area
results. The local candidate was not altered. Silvi/provider behavior, legacy
output fixtures, pest analytics, spatial exports, and MAN-CAP-054 acceptance
remain open. See [tree-tracking evidence](builds/2026-10-19-recovery/cap-054-tree-area-and-growth.json).

### CAP-055 oracle consensus input validation — 19 October 2026

Oracle consensus now rejects non-finite or non-positive prices, invalid
confidence values, missing source identities, and timezone-naive timestamps.
Provider source names are normalized for comparison, so duplicate readings
from one source cannot inflate consensus or source-count confidence. Median
deviation thresholds must be finite and non-negative. Weighted aggregation
ignores zero-weight providers and reports them as excluded.

The focused oracle-infrastructure suite passes 38 tests with Ruff and
compilation. No provider, database, chain, broker, or actuator was contacted.
The raw MQTT publisher still is not bound to the persisted approval row, and
operator authorization, dispatch idempotency, and device acknowledgment are
not established; those actuator gates, provider/reference parity, and
MAN-CAP-055 remain open. See [oracle evidence](builds/2026-10-19-recovery/cap-055-oracle-input-validation.json).

### CAP-056 channel plan scope and secret redaction — 19 October 2026

Channel delivery plans now use the requested location-wide and exact
segment-specific preferences, and include only channels with an active config.
When configured preferences point only at inactive channels, the result stays
empty instead of silently defaulting to every active channel. Configuration
reads recursively redact credential-like fields from both channel listings
and delivery plans.

Six mocked tests pass with Ruff and compilation, including default-plan secret
redaction and break-even rejection of non-finite values and negative costs
before database access.
Inline credentials can still be written to the legacy JSONB config table, so
secret references and SOPS integration remain open, along with external
delivery, tenant authorization, finance parity, populated fixtures, and
MAN-CAP-056. No database or external provider was contacted. See [channel
evidence](builds/2026-10-19-recovery/cap-056-channel-plan-secrets.json).

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

### CAP-057 environmental scan and PESTEL source repairs — 19 October 2026

Environmental scan communication now includes findings collected in the same
auto-populate run, as well as retained findings for earlier steps where the
current source queries returned no replacement evidence. PESTEL factor writes
require an existing analysis and bind the factor to its location; a conflicting
location is rejected. Impact and likelihood inputs are checked for finite
values and schema-supported ranges before SQL access.

Eleven focused mocked checks pass with Ruff and compilation. No database or
external provider was contacted. Regional readiness, segment results,
reference fixtures, populated parity, tenant authorization, and MAN-CAP-057
remain open. Checklist: 685 complete / 24 open; matrix classifications
unchanged. [Evidence](builds/2026-10-19-recovery/cap-057-environmental-scan-scope.json).

### CAP-058 marketplace numeric and price-grade contract — 19 October 2026

Marketplace listing creation now requires positive finite quantity and price;
listing edits and order requests validate positive finite quantities/prices
before writes. Price observations persist `quality_grade`, matching the value
already exposed by the public API. Listing evaluation no longer runs an unused
historical-yield query whose values were not used in its score or response.

The mocked marketplace unit suite passes 42 tests and 17 subtests with Ruff and
compilation. No database or provider was contacted. Order lifecycle and custody,
concurrent inventory reservation, cooperative order behavior, populated parity,
tenant authorization, and MAN-CAP-058 remain open. Checklist: 685 complete /
24 open; matrix classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-058-marketplace-inputs.json).

### CAP-059 Abundance validator and issuance guards — 19 October 2026

Validator selection now filters by exact, case-insensitive category expertise
and the requested weighted threshold, records expertise separately from trust,
and uses system randomness. Reviews require a selected, revealed validator in
an active round and lock the selection row. Quadratic vote weights/types are
checked before SQL. Coin issuance requires a positive finite score and a
validated or finalized periodic-impact record locked in the same transaction.

The protocol suite passes 66 mocked/schema checks with Ruff and compilation.
No database or chain was used. Commit/reveal payload verification, category
synonyms/reference fixtures, chain custody, funding and distribution policy,
populated parity, and MAN-CAP-059 remain open. Checklist: 685 complete / 24
open; matrix classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-059-abundance-governance-guards.json).

### CAP-060 Schema.org and GeoSPARQL JSON-LD namespace repair — 19 October 2026

The default `schema` and `geo` prefixes now match the exact namespaces in the
LinkML source YAML. This fixes the missing slash that corrupted `schema:name`
expansion and removes the GeoSPARQL hash-versus-slash mismatch. Explicit empty
contexts remain empty when constructing documents or graphs. Fourteen focused
alignment and JSON-LD tests pass with Ruff and compilation. No network or
external JSON-LD processor was used. Schema-derived context generation, class
URI declarations, populated graph/export parity, and MAN-CAP-060 remain open.
Checklist: 685 complete / 24 open; matrix classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-060-jsonld-uri-roundtrip.json).

### CAP-061 Regen claim and entity schema crosswalk — 19 October 2026

Project and CreditClass now declare `rfs:ProjectInfo` and
`rfs:CreditClassInfo`; ImpactClaim declares `rfs:Claim`. JSON-LD document
generation preserves a supplied CURIE/IRI type. ImpactClaim separates Regen
`ClaimType` and `VerificationStatus` from Kokonut record kind and governance
status, and its value sets match the SQL checks. Schema versions increased for
the three changed models. The previous enum-count-only tests were replaced by
SQL/schema crosswalk assertions. The linked-data/schema suites pass 142 tests;
Ruff, compilation, YAML parsing, and matrix validation pass. No database or
chain was used. CreditBatch units/market mapping, attestation parity, upstream
version pinning, populated fixtures, and MAN-CAP-061 remain open. Checklist:
685 complete / 24 open; matrix classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-061-regen-schema-crosswalk.json).

### CAP-062 marketplace fee settlement, origin tracking, and expiry metadata — 19 October 2026

Fee collection validates finite non-negative values and normalizes them to the
NUMERIC(18,8) storage scale. Zero-fee transactions settle as a no-op.
Distribution takes a row lock, enforces the fee denomination, uses exact
decimal totals, and leaves partial payments pending; only exact completion
sets `distributed_at`. Batch creation validates paired origin transaction
ID/source, stores the fields, and writes the unique class/transaction/source
index in the caller-owned transaction; CLI and gRPC inputs are available. Data
Stream create/update accepts caller-supplied timezone-aware expiry timestamps,
stores them in UTC, and passes them through the tenant-scoped Gateway. No
retention window or deletion behavior is inferred.

The combined credit, marketplace, linked-data, Data Stream, Gateway, and gRPC
selection passes 295 tests, one database-dependent skip, and 17 subtests with
Ruff, compilation, CLI help, and generated-protobuf freshness. SDK protobuf
generation is pinned to grpcio-tools 1.68.1/protobuf 5.29.1; incompatible
ambient generator versions fail with an actionable message. The loopback
gRPC tests required host access for ephemeral localhost binding. No database
or chain was used. Expiry-policy enforcement/cleanup and other expiry-bearing
entities, PostgreSQL conflict rollback/concurrency, populated parity, and
MAN-CAP-062 review remain open. Checklist: 685 complete / 24 open; matrix
classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-062-fee-distribution-settlement.json).

### CAP-063 CSW XML integrity — 19 October 2026

ISO 19115 and CSW record serialization escapes metadata as XML text, replaces
XML 1.0 forbidden controls, and declares the `gmd`/`gco` namespaces. The
Leaflet viewer uses text nodes for popup metadata and validates finite WGS84
coordinates while accepting zero values. GIS import validates ring closure and
coordinate bounds, limits coordinate count, preserves holes in Polygon and
MultiPolygon WKT, and preflights source input before opening PostgreSQL. KML
Placemark Polygon and MultiGeometry import uses defusedxml and preserves holes
and ExtendedData. Raster metadata now maps TIFF suffixes to the schema vocabulary and leaves missing CRS unknown. CSW `GetRecord` enforces public visibility, catalog pages are bounded, and `GetRecords` counts the complete filtered match set before pagination. The CSW/GIS/map, spatial-KML, security, raster-metadata, and import-redaction selection passes 70 tests with Ruff, compilation, and JavaScript syntax. The map still depends on the
legacy Directus endpoint. No database, network, or external service was used.
The tenant-scoped map API, CSW endpoint, database-backed matched-total and
output-schema fixture parity, KML
style/altitude, raster GroundOverlay, PostGIS recovery and populated spatial
fixtures, geostory access, thesaurus integration, and MAN-CAP-063 remain open.
Checklist: 685 complete / 24 open;
matrix classifications unchanged. [Evidence](builds/2026-10-19-recovery/cap-063-csw-xml-safety.json).

### CAP-025 location-scoped identity reviewer console — 20 October 2026

Added a reviewer panel to `apps/operator-console/index.html`, shown only for
locations in the signed session's exact `stakeholder_identity:review` grants.
The bounded queue displays source and candidate names only when the database
projection supplies them under current consent/privacy rules; it withholds
source profile IDs and raw feedback and disables decisions when required names
are absent. Approve uses `match_confirmed`; reject offers only the three
Gateway reason codes. Each decision has an explicit confirmation and a
same-origin, no-store, CSRF-protected POST. Request IDs remain stable when a
response is interrupted, and the database still rejects proposer self-review.

Six focused console contract tests and the related CAP-025 Gateway, trust,
resolver, and route-policy selection pass 36 tests. Ruff, inline JavaScript
syntax, and `git diff --check` pass. No database or migration was required, and
candidate/legacy state was untouched. The console completes this code-owned
review surface, but CAP-025 remains prepared pending other identity sources,
non-identity trust evidence, live OIDC/browser acceptance, populated parity,
RLS, post-review consent disposition, and owner acceptance. Checklist: 720
complete / 24 open; the matrix remains 66 rows (31 baseline-retained, 7
deployed, 28 prepared). [Contract](stakeholder-identity-kernel-contract.md);
[tests](../tests/test_operator_console_stakeholder_identity.py).

### CAP-035 location-linked stage-gate console read — 20 October 2026

Extended the existing CAP-035 console with a paged read of the already
protected `/operator/api/solution-lifecycle/{location_id}/gates` route. The
view uses the exact location `solution_lifecycle:read` scope, same-origin
no-store requests, bounded 25-row pages, stale-response rejection on location
change, and text-only DOM rendering. It shows solution labels, stage transition,
structural evidence/experiment thresholds, gate status, and the latest
structural evaluation result/time. It omits row IDs, evidence payloads, and
reviewer identities; it cannot evaluate, approve, or mutate a gate.

The focused CAP-035 console, Gateway read/action, and route-policy selection
passes 99 tests with Ruff and inline JavaScript syntax checks. No database or
migration was needed, and candidate/legacy state was untouched. CAP-035 stays
prepared pending remaining item-level workflows and write/review parity,
populated fixtures, live OIDC/browser, broader ACL/RLS, recovery, and owner
acceptance. Checklist: 721 complete / 24 open; matrix remains 66 rows (31
baseline-retained, 7 deployed, 28 prepared). [Contract](solution-lifecycle-kernel-read-contract.md);
[tests](../tests/test_operator_console_solution_lifecycle.py).

### CAP-035 supplemental lifecycle status console — 20 October 2026

Added fixed, paged views for adoption programs, scale gates, replications,
learning records, and retirements using the existing exact-grant Gateway reads.
All requests are same-origin and no-store, use 25-row pages, and discard stale
responses when the location or selected view changes. Rendering uses fixed
fields and text-only DOM updates; identifiers, narratives, evidence, and
person-level details remain hidden. The adoption count is shown only when the
database projection provides it above the five-reference suppression
threshold. No mutation controls, migrations, or database access were added.

The combined CAP-025/CAP-035 console, Gateway, action, and route-policy
selection passes 139 tests; Ruff and inline JavaScript parsing pass. CAP-035
remains prepared pending remaining workflow and populated-fixture parity, live
OIDC/browser acceptance, broader ACL/RLS, recovery, and owner acceptance.
Checklist: 724 complete / 24 open; matrix: 66 rows (31 baseline-retained, 7
deployed, 28 prepared). [Contract](solution-lifecycle-kernel-read-contract.md);
[tests](../tests/test_operator_console_solution_lifecycle.py).

### CAP-035 learning-proposal operator form — 20 October 2026

The CAP-035 console now supports proposing a learning record from a completed,
actively reviewed replication. The form is available only where the operator has
both exact location `solution_lifecycle:read` and `solution_lifecycle:create`
grants, and it uses the existing Gateway read and write routes. It enforces the
route's fixed lesson, confidence, transferability, and reference bounds; requires
nonempty evidence and an explicit acknowledgement; and submits same-origin,
no-store, CSRF-protected requests. An unchanged retry reuses its request ID if
the prior response was uncertain. The operation creates a `proposed` record
requiring independent review. The form has no approve, reject, or apply controls.

The combined CAP-025/CAP-035 console, Gateway, action, and route-policy selection
passes 166 tests; Ruff and inline JavaScript parsing pass. No migration or
database was needed, and candidate/legacy state remains untouched. CAP-035 stays
prepared pending remaining lifecycle parity, populated fixtures, live OIDC/browser,
broader ACL/RLS, recovery, and owner acceptance. Checklist: 725 complete / 24
open; the matrix remains 66 rows (31 baseline-retained, 7 deployed, 28 prepared).
[Contract](solution-lifecycle-kernel-read-contract.md); [console](../apps/operator-console/index.html);
[tests](../tests/test_operator_console_solution_lifecycle.py).

### CAP-035 experiment status console read — 20 October 2026

Added a bounded experiment-status list to the existing location-scoped
solution-lifecycle console. It uses the existing exact-grant
`/operator/api/solution-lifecycle/{location_id}/experiments` route, same-origin
no-store requests, 25-row offset pages, and location stale-response guards.
Cards show solution labels, protocol version, experiment status/duration,
metric-key counts, lifecycle timestamps, and only an explicitly reviewed
outcome. They do not display IDs, protocol narratives, metric names/values,
observations, adverse-event details, evidence, or reviewer identities. No
approval, review, or mutation controls are present.

The combined CAP-025/CAP-035 console, Gateway read/action, and route-policy
selection passes 134 tests; Ruff and inline JavaScript parsing pass. No
migration or database was used; candidate and legacy state remain untouched.
CAP-035 remains prepared pending experiment evidence/review and other item-level
read/write workflows, populated fixture parity, live OIDC/browser, broader
ACL/RLS, recovery, and owner acceptance. Checklist: 722 complete / 24 open;
matrix: 66 rows (31 baseline-retained, 7 deployed, 28 prepared). [Contract](solution-lifecycle-kernel-read-contract.md);
[tests](../tests/test_operator_console_solution_lifecycle.py).

### CAP-035 funding and tranche status console — 20 October 2026

Added a bounded funding/tranche list to the location-scoped lifecycle console,
using the existing exact-grant `/funding` route. It displays solution labels,
capital stage, instrument, currency, case/tranche state, and approval/release
timestamps. It intentionally omits IDs, all amounts, milestone terms,
rationale, evidence, and submitter/approver/releaser identities. Requests are
same-origin, no-store, paginated in 25-row groups, and guarded against stale
location responses. No approval or tranche-release action is present.

The combined CAP-025/CAP-035 console, Gateway read/action, and exact route-policy
selection passes 136 tests; Ruff and inline JavaScript parsing pass. No
migration or database was used; candidate and legacy remain untouched. CAP-035
stays prepared pending remaining lifecycle detail/write parity, populated
fixtures, live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance.
Checklist: 723 complete / 24 open; matrix: 66 rows (31 baseline-retained, 7
deployed, 28 prepared). [Contract](solution-lifecycle-kernel-read-contract.md);
[tests](../tests/test_operator_console_solution_lifecycle.py).
**Latest implementation slice — 20 October 2026:** CAP-035 now retires the
legacy direct gate approval and evaluation writers. They fail before database
access; exact-location Gateway evaluation and independent review/approval
remain available through migrations 483–485. The legacy transition helper is
still direct and remains open for consumer migration. No migration or database
was used. Checklist: 753 complete / 24 open; matrix: 31 baseline-retained,
7 deployed, 28 prepared. Evidence: [source-to-route audit](solution-lifecycle-source-route-audit.md).

**Latest implementation slice — 20 October 2026:** CAP-035 now disables the
legacy adoption-event writer because `consent_checked` was caller-controlled,
with no program consent policy or canonical participant-party link to validate
against. Both boolean inputs fail before database access. A policy-backed,
exact-location Gateway write remains open, so this is a security boundary, not
feature-parity completion. No database or migration was used. Checklist: 752
complete / 24 open; matrix: 31 baseline-retained, 7 deployed, 28 prepared.
Evidence: [source-to-route audit](solution-lifecycle-source-route-audit.md).

### CAP-039 ingestion status CLI parity — 21 October 2026

The `ingestion status log`, `indexers`, and `summary` paths now compare
standalone and unified output with synthetic connections. The log checks bound
filters; error-bearing reads verify redaction; and all three paths verify
connection cleanup after query failures. Nine focused tests pass with Ruff and
Python compilation. No database or provider was contacted. This closes
mocked output/cleanup paths only;
populated-data behavior and authorization remain open. Checklist: 825 complete
/ 25 open (850 total); capability classifications remain 66 rows: 31
baseline-retained, 7 deployed, and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-ingestion-status-cli-parity.json`.


### CAP-039 location-scoped device read CLI parity — 21 October 2026

Standalone and unified `device_manager --list` and `--health` now match on
synthetic result rows. Both operations bind the exact location; missing or
malformed location scope fails before database setup; successful reads close
resources. Ten focused tests, Ruff, and compilation pass. No database or
provider was contacted. Registration writes, populated-data parity, and
authorization remain open. Checklist: 826 complete / 25 open (851 total);
capability classifications remain 66 rows: 31 baseline-retained, 7 deployed,
and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-device-manager-read-cli.json`.


### CAP-039 device registration transaction boundary — 21 October 2026

`device_manager --register` now returns identical output and receives
identical arguments through standalone and unified entrypoints. Device insert
and initial health-row creation share one transaction; an injected health-row
failure rolls back the insert and closes the cursor. The 29-test
device-manager service/CLI selection, Ruff, and Python compilation pass using
mocked database interactions. Live PostgreSQL and operator authorization are
not verified. Checklist: 827 complete / 25 open (852 total); capability
classifications remain 66 rows: 31 baseline-retained, 7 deployed, and 28
prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-device-manager-registration-atomicity.json`.


### CAP-039 sensor inventory CLI parity — 21 October 2026

Standalone and unified `sensor_ingester --list` and `--calibration` now match
on synthetic output, bind exact location scope, and close resources. Missing
or malformed scope on inventory listing fails before DB setup in both CLIs.
Nine focused tests pass with Ruff and Python compilation. No database or
provider was contacted. Single-reading, CSV, and scheduled-driver argument
forwarding also matches with stubbed operations; sensor effects/output and
scheduled-driver runtime remain open.
Checklist: 828 complete / 25 open (853 total); capability classifications
remain 66 rows: 31 baseline-retained, 7 deployed, and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-sensor-inventory-cli-parity.json`.


### CAP-039 climate data CLI dispatch parity — 21 October 2026

The six climate selectors (five datasets plus `--all`) now preserve JSON
output and canonical location forwarding through standalone and unified CLIs
with stubbed operation functions. Conflicting selectors fail before database
setup. Eight focused tests pass with Ruff and Python compilation. No database
or provider was contacted. Provider retrieval and persistence remain open.
Checklist: 829 complete / 25 open (854 total); capability classifications
remain 66 rows: 31 baseline-retained, 7 deployed, and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-climate-data-cli-parity.json`.


### CAP-039 remote-sensing CSV CLI parity — 21 October 2026

Standalone and unified remote-sensing CSV imports now match in location-scoped
and explicit `--all-locations` modes using a temporary CSV and synthetic plot
mapping. Canonical/ClickHouse writes are stubbed; logs, commit, and cleanup
match. Two focused tests, Ruff, and Python compilation pass. No database or
provider was contacted. Live storage and aggregate authorization remain open.
Checklist: 830 complete / 25 open (855 total); capability classifications
remain 66 rows: 31 baseline-retained, 7 deployed, and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-remote-sensing-csv-cli-parity.json`.


### CAP-039 remote-sensing job list CLI parity — 21 October 2026

The location-scoped fetcher job list now matches through both CLIs with
synthetic query rows; it binds the location and closes its cursor/connection.
Missing or malformed scope fails before database setup. Five focused tests,
Ruff, and Python compilation pass; no database/provider was contacted. Job
provider execution and worker recovery remain open. Checklist: 831
complete / 25 open (856 total); capability classifications remain 66 rows:
31 baseline-retained, 7 deployed, and 28 prepared. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-039-remote-sensing-job-list-parity.json`.


### CAP-039 remote-sensing job creation contract — 21 October 2026

The fetcher rejects non-positive cadence before database setup, matching the
existing schema constraint, and commits job creation as one rollback-safe
transaction with explicit cursor cleanup. Standalone/unified insert arguments
and JSON receipts match. The focused fetcher and scheduler selection passes 38
tests; Ruff and compilation pass. Only synthetic database objects were used;
no provider was contacted. Provider execution, persisted job recovery, and
operator authorization remain open. The checklist is 832 complete / 25 open
(857 total); the 66-row matrix remains 31 baseline-retained, 7 deployed, and 28
prepared. See [evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-job-create-contract.json).


### CAP-039 remote-sensing fetcher read cursor cleanup — 21 October 2026

Active-job query, exact job lookup, location job listing, and both bbox lookup
paths now close cursors when SQL execution or fetching fails. Ten synthetic
failure cases pass in the focused 82-test fetcher/scheduler/automation
selection; Ruff and compilation pass. No database or provider was contacted.
Live database authorization, provider execution, and worker recovery remain
open. Checklist: 833 complete / 25 open (858 total); matrix classifications
remain 31 baseline-retained, 7 deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-fetcher-cursor-cleanup.json).

### CAP-039 remote-sensing manual job-run contract — 21 October 2026

The fetcher preflights `--job-id` UUID syntax against the job table's UUID
primary key, before database access. Standalone and unified commands use the
same bound job/location scope and output with a stubbed provider adapter. Five
manual-path tests pass within the 87-test fetcher/scheduler/automation
selection; Ruff and compilation pass. No database/provider was contacted. Live
authorization, real provider parity, and worker recovery remain open. Checklist:
834 complete / 25 open (859 total); the matrix remains 31 baseline-retained,
7 deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-manual-run-contract.json).

### CAP-039 remote-sensing write cursor cleanup — 21 October 2026

The status update and provider-attempt insert close their cursor after SQL
execution errors while preserving caller transaction ownership. Two synthetic
failure cases pass in the 89-test fetcher/scheduler/automation selection; Ruff
and compilation pass. No database or provider was contacted. Live writes and
worker recovery remain open. Checklist: 835 complete / 25 open (860 total);
capability classifications remain 31 baseline-retained, 7 deployed, and 28
prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-remote-sensing-write-cursor-cleanup.json).

### CAP-039 current-weather query cleanup — 21 October 2026

The current-weather location SELECT and result fetch now close PostgreSQL on
error. A close failure does not mask the query error and is logged by class
only. Three failure-path tests pass within the 37-test weather/forecast
selection with Ruff and compilation. No database/provider was contacted. Live
PostgreSQL/provider behavior remain open. Checklist: 836 complete / 25 open
(861 total); matrix classifications remain 31 baseline-retained, 7 deployed,
and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-weather-location-query-cleanup.json).

### CAP-039 current-weather CLI parity — 21 October 2026

Standalone/unified current-weather reads match for canonical single-location
and explicitly selected aggregate scope using synthetic empty query results.
Malformed IDs fail before DB setup; logs, bound scope, and cleanup match. Four
parity/preflight checks pass in a 41-test weather/forecast selection with Ruff
and compilation; no database/provider was contacted. Populated-data parity,
provider delivery, and live authorization remain open. Checklist: 837 complete /
25 open (862 total); matrix classifications remain 31 baseline-retained, 7
deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-weather-cli-parity.json).

### CAP-039 weather-forecast CLI parity — 21 October 2026

Standalone/unified weather-forecast reads now match for canonical location and
explicit aggregate scope on synthetic empty query results. Invalid IDs fail
before DB setup; the query scope, logs, and cleanup match. Four focused
forecast parity/preflight checks pass in the 45-test weather/forecast selection
with Ruff and compilation. No database/provider was contacted. Populated-data
parity, live provider, and authorization remain open. Checklist: 838 complete /
25 open (863 total); matrix classifications remain 31 baseline-retained, 7
deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-weather-forecast-cli-parity.json).

### CAP-039 data-freshness summary CLI — 21 October 2026

Standalone/unified global summary output matches for synthetic rows, and query
or fetch failure closes cursor and connection. Five focused cases pass in the
42-test freshness/telemetry selection with Ruff and compilation. No
database/provider was contacted. Live view parity, operator/privacy boundaries,
and alert delivery remain open. Checklist: 839 complete / 25 open (864 total);
matrix classifications remain 31 baseline-retained, 7 deployed, and 28
prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-data-freshness-summary-cli.json).

### CAP-039 data-freshness helper cursor cleanup — 21 October 2026

Freshness data-access helpers now close cursors after query and fetch errors for
configuration, location, ingestion-time, alert-state, alert-history, delivery,
and check-result operations. Seventeen synthetic cases pass in the 59-test
freshness/telemetry selection with Ruff and compilation. No database/provider
was contacted. SAVEPOINT orchestration cleanup, authorization, summary privacy,
and delivery remain open. Checklist: 840 complete / 25 open (865 total); matrix
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-data-freshness-helper-cursor-cleanup.json).

### CAP-039 data-freshness SAVEPOINT cursor cleanup — 21 October 2026

Freshness orchestration closes its SAVEPOINT, rollback-to-savepoint, status/check
update, and release cursors on SQL errors. Existing transaction rollback is
preserved and partial results are not committed. Five synthetic cases pass in
the 64-test freshness/telemetry selection with Ruff and compilation. No live
database/provider was used. Checklist: 841 complete / 25 open (866 total);
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-data-freshness-savepoint-cursor-cleanup.json).

### CAP-039 data-freshness check CLI dispatch — 21 October 2026

Standalone/unified `--check --source weather` calls pass the same scope and
produce matching JSON with the checker stubbed; connections close and invalid
source-only input fails before database setup. Two focused tests pass in the
66-test freshness selection with Ruff and compilation. No evaluation, query,
write, or alert was run. Checklist: 842 complete / 25 open (867 total); matrix
classifications remain 31 baseline-retained, 7 deployed, and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-data-freshness-check-cli.json).

### CAP-039 anomaly-rule list CLI contract — 21 October 2026

Standalone/unified global rule listing now matches on a synthetic row. The query
is intentionally global and location/aggregate selectors fail before database
setup. Five focused tests pass in the 47-test anomaly selection with Ruff and
compilation; no database/provider was contacted. This does not set the operator
privacy boundary or prove populated parity. Checklist: 843 complete / 25 open
(868 total); matrix classifications remain 31 baseline-retained, 7 deployed,
and 28 prepared. See
[evidence](builds/2026-10-21-recovery/cap-039-anomaly-rule-list-cli.json).

### CAP-039 / CAP-040 market-data CLI entrypoint — 21 October 2026

The market-data module now provides a reusable parser and callable `main()`, so
the unified ingestion CLI invokes its imported implementation rather than using
the `runpy` fallback. Standalone and unified argument forwarding matches for
World Bank and explicit seed modes, including matching help output. Dispatcher
arguments are restored after success or failure. Invalid sources and World
Bank date filters are rejected before work begins. The focused market-data
tests pass (35), as do 62 ingestion-help/unified-CLI checks, Ruff, compilation,
matrix validation, and diff checks. No provider, database, schedule, candidate,
or legacy service was accessed. Populated price parity, live provider behavior,
and MAN-CAP-040/047 remain open
([evidence](builds/2026-10-21-recovery/cap-039-market-data-cli-entrypoint.json)).

### CAP-039 / CAP-040 price-attestation CLI entrypoint — 21 October 2026

`price_attestation` now exposes a callable parser and `main()`. Incomplete
commands print help before PostgreSQL is opened; stubbed manual and daily paths
preserve arguments and close connections. Standalone and unified CLI output and
argument dispatch match. Seven focused cases pass within the 50-test
price/Oracle selection, with 62 ingestion-help/unified CLI checks, Ruff, and
compilation. Database writes and EAS access were stubbed; no database or chain
was contacted. Populated source parity and on-chain attestation remain open
([evidence](builds/2026-10-21-recovery/cap-039-price-attestation-cli-entrypoint.json)).

### CAP-039 / CAP-040 GIS import CLI entrypoint — 21 October 2026

`gis_import` now exposes a callable parser and `main()`. Standalone/unified
argument forwarding and help match; missing file and invalid target inputs fail
before the import function runs. Six CLI cases pass within the 40-test
GIS/geospatial selection with Ruff and compilation. The importer was stubbed;
no file, database, or provider was accessed. Actual GIS fixture parsing and
import semantics remain covered separately
([evidence](builds/2026-10-21-recovery/cap-039-gis-import-cli-entrypoint.json)).

### CAP-039 / CAP-040 HTTP sensor-receiver CLI entrypoint — 21 October 2026

The HTTP sensor receiver now exposes a callable parser and `main()`.
Standalone/unified host/port forwarding and help match; non-integer ports fail
before startup. Five CLI cases pass in the 79-test HTTP/IoT/outbox selection
with Ruff and compilation. Server startup was stubbed, so no listener, database,
or provider was touched ([evidence](builds/2026-10-21-recovery/cap-039-http-sensor-receiver-cli-entrypoint.json)).

### CAP-039 / CAP-040 MQTT subscriber CLI entrypoint — 21 October 2026

The MQTT subscriber now exposes a callable parser and `main()`. Standalone and
unified broker/port forwarding and help match; invalid non-integer ports fail
before subscriber startup. Five CLI cases pass in the 91-test MQTT/IoT/outbox
selection with Ruff and compilation. Subscriber startup was stubbed, so no
broker or database was contacted
([evidence](builds/2026-10-21-recovery/cap-039-mqtt-subscriber-cli-entrypoint.json)).

### CAP-039 / CAP-040 EAS indexer CLI entrypoint — 21 October 2026

The EAS indexer now exposes a callable parser and `main()`. Standalone/unified
chain arguments and help match; unsupported chain choices fail before indexer
execution. Five CLI cases pass in the 41-test EAS recovery/redaction/outbox
selection with Ruff and compilation. The indexer was stubbed; no chain or
database was contacted ([evidence](builds/2026-10-21-recovery/cap-039-eas-indexer-cli-entrypoint.json)).

### CAP-039 / CAP-040 Gnosis indexer CLI entrypoint — 21 October 2026

The Gnosis indexer now exposes a callable parser and `main()`. Standalone/unified
block interval and help output match; malformed, negative, and reversed ranges
fail before provider/DB access. Nine CLI cases pass in the 53-test Gnosis
recovery/redaction/outbox selection with Ruff and compilation. No provider or
database was contacted ([evidence](builds/2026-10-21-recovery/cap-039-gnosis-indexer-cli-entrypoint.json)).

### CAP-039 / CAP-040 mock-sensor CLI entrypoint — 21 October 2026

The mock-sensor module now exposes a callable parser and `main()`. Setup,
generation, cleanup, and help dispatch match between standalone/unified entry
points; no-action invocation only displays help. Nine CLI cases pass within the
81-test mock-sensor/IoT/outbox selection. Ruff and compilation pass after
removing dead imports/assignments. All demo operations were stubbed; no data was
created or deleted ([evidence](builds/2026-10-21-recovery/cap-039-mock-sensors-cli-entrypoint.json)).

### CAP-039 / CAP-040 Baal indexer CLI range contract — 21 October 2026

The Baal indexer now has a reusable parser and standalone/unified argument
parity. Negative and reversed block intervals fail before provider/database
initialization; explicit block zero is preserved as the requested endpoint.
Twelve focused CLI cases cover dispatch, invalid inputs, help parity, and zero
endpoint behavior, including the actual `run()` range call. The combined Baal
recovery, ingestion dispatch, and all-tool help selection passes 19 tests; Ruff
and compilation pass. No chain or database was contacted. Checklist: 854
complete / 25 open (879 total); matrix remains 66 rows: 31 baseline-retained,
7 deployed, and 28 prepared. See
[the test](../tests/test_baal_indexer_cli.py) and
[evidence](builds/2026-10-21-recovery/cap-039-baal-indexer-cli-contract.json).

### CAP-064 explicit gRPC message-size limits — 21 October 2026

The gRPC server now caps both inbound and outbound messages through
`GRPC_MAX_MESSAGE_BYTES`, default 4 MiB and range 1 KiB–64 MiB. Invalid values
fail before the database pool opens. Base and Kernel Compose expose the
setting. The 36-test server suite and six enabled-transport checks pass,
including oversized request and response rejection; Ruff, compilation,
Compose validation, and diff checks pass. No live database or provider was
used. TLS and authenticated tenant parity remain open ([evidence](builds/2026-10-21-recovery/cap-064-grpc-message-size-limits.json)).


### 21 October 2026 — CAP-064 TLS-aware gRPC health client

The optional health CLI now accepts a CA bundle with `--tls-ca` or
`GRPC_TLS_CA`, uses a secure channel when configured, and fails closed if the
server certificate/key settings are present without a CA. Fixed error messages
redact trust-file paths, and the health channel closes after the request. The
focused gRPC tests pass (44); Ruff, Python compilation, base and Kernel gRPC
Compose validation, and diff checks pass. These checks mock transport and do
not verify a real certificate chain, hostname, public ingress, database, or
provider. Evidence: `docs/refactor/builds/2026-10-21-recovery/cap-064-grpc-health-tls.json`.


### 21 October 2026 — CAP-064 gRPC server TLS startup preflight

The gRPC server now reads the certificate/key and constructs its TLS credentials
before opening the PostgreSQL pool. An incomplete pair, missing file, or
credential error stops startup with redacted diagnostics. Forty-five focused
gRPC tests pass; Ruff, compilation, and diff checks pass. The DB pool and
transport were mocked; no endpoint, database, or provider was contacted.
Evidence: `docs/refactor/builds/2026-10-21-recovery/cap-064-grpc-server-tls-preflight.json`.


### 21 October 2026 — CAP-064 certificate-verified gRPC TLS loopback

The gRPC health client completed a real local TLS handshake against an
in-process server with a temporary self-signed certificate trusted through the
CA option; the test validates the 127.0.0.1 IP SAN. The enabled transport file
passes all seven tests; Ruff, compilation, and diff checks pass. Only loopback
and temporary test files were used. Production DNS certificates, rotation,
public ingress, tenant authorization, and REST parity remain open. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-064-grpc-health-tls-loopback.json`.


### 21 October 2026 — CAP-064 remote health targets require TLS

Plaintext is implicit only for loopback health targets. Remote targets require
a trusted CA or an explicit `--insecure` opt-in for a trusted private network;
server TLS settings cannot be bypassed without their CA. The focused unit suite
passes 50 tests and enabled transport passes seven, including the real TLS
loopback. Ruff, compilation, Compose, matrix, and diff checks pass. No remote
endpoint or database was used. Production DNS/certificate, lifecycle, ingress,
tenant, and REST acceptance remain open. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-064-grpc-health-remote-plaintext-policy.json`.


### 21 October 2026 — CAP-064 TypeScript SDK secure transport defaults

The TypeScript gRPC SDK now chooses system-trusted TLS for remote targets,
plaintext only for recognized loopback, and preserves custom credentials.
Thirty-five Vitest checks pass; `tsc` build and package dry run pass, including
`dist/transport.js`. No RPC or external endpoint was contacted. Python generated
stubs remain caller-managed and document the secure channel path. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-064-typescript-grpc-tls-defaults.json`.


### 21 October 2026 — CAP-064 Python SDK channel security

The optional Python SDK now has a lazy `create_channel()` helper: remote targets
use system-trusted TLS, loopback uses plaintext, private CA bytes select TLS,
and remote plaintext needs `allow_insecure=True`. Importing the package does not
load grpcio. Sixteen tests pass; Ruff, compilation, and wheel build pass, with
the helper included. No RPC or external endpoint was contacted. Evidence:
`docs/refactor/builds/2026-10-21-recovery/cap-064-python-grpc-channel-factory.json`.


### 22 October 2026 — CAP-038 signed worker source search path

The remaining five source-reader transactions now use only the scoped
`kokonut_agent_source` schema and `pg_catalog` for unqualified names. This
removes accidental resolution through `public` while preserving scoped wrapper
queries used by deterministic summaries, summary inspection, EBF, CIDS, and
Delphi. The focused worker/EBF selection passes 56 tests; Ruff, Python
compilation, and capability-matrix validation pass. No database or provider
was used. Evidence: `docs/refactor/builds/2026-10-22-recovery/cap-038-agent-source-search-path.json`.

### 23 October 2026 — CAP-038 task-specific source identities

Migration 580 and the worker profiles isolate EBF, CIDS, and Delphi source reads behind separate credentials and reader roles, each with an explicit projection allowlist. Migration 581 adds a distinct AI-summary inspection login and digest-only view, so inspection cannot read the deterministic worker's operational projections or return summary content to Python. The focused worker/database/profile/migration selection passes 128 tests; Ruff, compilation, Compose parsing, and refreshed inventories pass. Migration 581's disposable PostgreSQL 16 chain passes 42 grouped assertions natively and under ARM64/QEMU. Candidate and legacy are untouched; no credentials or location grants have been provisioned. Exact location grants, populated parity, live OIDC/provider checks, wider ACL/RLS, production recovery, Raspberry Pi hardware, and MAN-CAP-038 acceptance remain open.
