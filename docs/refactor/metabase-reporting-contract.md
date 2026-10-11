# Metabase reporting source contract

**Status (11 October 2026):** after source alignment, a fresh scratch database
in a second-generation recovery-volume copy applied all 369 schema migrations
through 378 and reported zero pending. The expanded actual-view role fixture
passed, including lifecycle, scope, aggregation, and denial probes; synthetic
reporting rows were rolled back. A third-generation scratch replay through the
transactional runner also verified all 369 source checksums and zero pending;
an injected duplicate-table failure left neither its table nor ledger row
(`0|0`). The prior 368-migration scratch is retained as historical evidence
only. The archived application clone's read-only plan found zero checksum drift
and 25 pending migrations; none were applied to that retained clone. A separate
network-isolated clone applied the 25 reviewed migrations with unchanged
pre-existing row fingerprints for 16 populated tables; the detailed review is
in [pending migration compatibility](pending-migration-compatibility-review.md).
Populated farm-summary and Celo-attestation view outputs subsequently matched
independent base-table queries in both directions on a disposable populated
copy, with zero differences. The metric view matched an independent query but
returned zero rows because that population has no published metric policies;
the separate transaction-rolled-back role fixture passed the nonempty published
metric period/method/review-field probe. The analytics role read only the
three named views and was denied on application tables, the private policy
table, and DDL on that copy. See [populated parity evidence](builds/2026-10-11-recovery/populated-report-view-parity.json).
No Metabase source is configured and no Kokonut report cards have been built.
Metabase remains optional and belongs only in the analytics profile. See the
[source-aligned evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json),
[transactional replay evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json),
and [migration source/recovery record](migration-checksum-drift.md).

Before migrations 371–379 were applied, a read-only ACL inventory found that
`kokonut` was the candidate's only login/superuser role and that PUBLIC had
`CONNECT` and `TEMPORARY` privileges. The nine reviewed migrations are now
applied and the three reporting views exist. The dedicated candidate now has a
verified `kokonut_analytics_ro` login, with `PUBLIC CONNECT` revoked on its four
databases and `PUBLIC TEMPORARY` revoked on the application database. Its login
reads the views and is denied on application data, the private policy table,
DDL, temporary tables, and other databases. Eight extension metadata relations
and 1,165 extension functions remain accessible through inherited grants; none
of those functions is SECURITY DEFINER. The optional Metabase profile is
healthy on its loopback-only port with saved-credential encryption enabled. A
sanitized inventory found one built-in sample H2 source and generic demo
content, but no Kokonut PostgreSQL source or cards. [Pre-migration ACL evidence](builds/2026-10-11-recovery/candidate-reporting-acl-review.json); [migration result](builds/2026-10-11-recovery/candidate-migration-apply.json); [active role evidence](builds/2026-10-11-recovery/candidate-analytics-role.json); [profile evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json); [profile contract](metabase-kernel-profile.md).

## Purpose and source of truth

PostgreSQL remains canonical for operational and governed records. Metabase is
an optional consumer of a small, reviewed reporting surface; it does not define
Kokonut metrics, lifecycle state, or authorization. The native API remains the
reference for user-scoped and tenant-scoped reads. The first Metabase connection
is limited to data already intentionally visible through reviewed public
aggregate policy. Do not use a shared BI login for partner, tenant, reviewer, or
internal data that needs caller-specific access.

The existing starting points are the public views in
[`schemas/postgres/018_public_views.sql`](../../schemas/postgres/018_public_views.sql),
native query code in `services/core/adapters/postgres_analytics.py`, and the
location response in [`public-summary-contracts.md`](public-summary-contracts.md).
Those objects are evidence of current behavior, not an approved BI contract.
The proposed stable interface is a dedicated `kokonut_reporting` schema with
versioned, explicitly granted views. Metabase should see that schema only.

## Proposed v1 reporting surface

| View | Grain and required columns | Eligibility and exclusions | Current-source disposition |
| --- | --- | --- | --- |
| `kokonut_reporting.v_farm_summary` | One row per eligible location: `location_id`, `location_name`, `country`, `region`, `farm_count`, `plot_count`, `total_area_ha`, `area_data_complete`, `status` | Active location with a verified or published registry record. Count active farms only when they have a matching farm-specific registry record or a location-wide registry record (`farm_id IS NULL`); count active plots on those farms. Publish aggregate values only; no names of people, exact geometry, private evidence, or financial data. | Migration 377 pre-aggregates farms and plots separately, fixes equal-area undercounting, normalizes hectares/square meters/acres, and returns a NULL area with `area_data_complete = FALSE` if any included active farm has missing or unsupported area units. |
| `kokonut_reporting.v_verified_metric_values` | One row per governed value: `location_id`, `location_name`, `metric_key`, `display_name`, `unit`, `value`, `period_start`, `period_end`, `computation_method`, `computed_at`, `verified_at` | `metric_value.verified = TRUE`; active eligible location; metric definition explicitly approved for public reporting. Include the full period and method so clients can distinguish separate values. No draft/submitted/rejected values, reviewer notes, raw evidence, or private inputs. | Migration 377 adds `kokonut_reporting.metric_publication_policy`, using the standard governed lifecycle and starting empty. Only `published` policy rows appear. The view preserves all qualifying periods/methods; it has no ambiguous latest-row selection. |
| `kokonut_reporting.v_attestation_summary` | One row per eligible location, claim type, and chain: `location_id`, `location_name`, `claim_type`, `chain`, `total_attestations`, `published_count`, `first_attestation`, `latest_attestation` | Active eligible location; verified or published attestations; Celo only for v1. Exclude attestation payloads, private evidence, attester identity, and transaction details. | Existing `v_public_attestation_summary` is the behavioral starting point. The output must continue to label Celo scope and must not imply all-chain coverage or independent ecological/financial certification. |

The existing public location summary is not itself a Metabase source contract. It
is a compact API response with a distinct metric-key count and aggregate
attestation count, not a historical dataset. Metabase reports must use the
curated views above and named measures with documented units and date semantics.

## Authorization and database boundary

- Use a dedicated analytics-source login, `kokonut_analytics_ro`, separate from
  `kokonut_metabase_app` (which owns Metabase's metadata database) and from
  Directus or application runtime identities.
- Grant `CONNECT` only to the application database, `USAGE` on
  `kokonut_reporting`, and `SELECT` on each approved view by name. Grant no
  access to base tables, `public` as a whole, write operations, DDL, role
  management, or the Metabase metadata database.
- Keep view ownership with the controlled migration/operator identity, never
  the analytics login. Review view definitions, called functions, and inherited
  extension/database ACLs before provisioning. Do not weaken database-wide
  `PUBLIC` grants without an ACL inventory.
- Keep the Metabase service and PostgreSQL source on a private Compose network.
  Do not publish the database port for this connection. Do not put Metabase in
  minimal, edge, or standard profiles; enable it only as an optional analytics
  consumer.
- A single database role is suitable only for the reviewed public aggregates
  above. Caller-specific or confidential reporting must go through the native
  API or a separately scoped design; Metabase row filters are not the database
  authorization boundary.

The isolated reporting check exercises the actual curated views as
`kokonut_analytics_ro`. It demonstrates the proposed database boundary and
view behavior on synthetic data, but does not establish parity on populated
Kokonut application rows or authorize a Metabase source connection.

## Implementation sequence

1. Migration 377 defines the farm/plot population rule: active records tied to
   matching farm-specific approval or a location-wide registry record. It
   normalizes supported area units and marks totals incomplete instead of
   silently omitting missing or unsupported areas.
2. Migration 377 creates an empty, lifecycle-governed metric publication
   allowlist. A human must publish the metric policy independently of verifying
   metric values; no key is reportable by default.
3. Apply the forward-only migration through the checksum-tracked migration
   runner. Do not edit migration 018 or any applied migration. Keep the schema
   additive so older app versions remain compatible.
4. Run the updated isolated consumer-role fixture. It grants only the three
   reviewed views and checks equal-area farm aggregation, unsupported units,
   farm-specific eligibility, metric publication, Celo attestation lifecycle,
   and denials for base relations, the private policy table, writes, DDL, and
   other databases. The current run used a new-schema scratch database in a
   copied recovery volume; populated application-row parity remains open.
5. Configure the optional Metabase source only against the application database
   and `kokonut_reporting`. Add Kokonut-owned cards from approved views; retain
   the archived E-commerce Insights board solely as a labeled demo fixture.
6. Compare each card's result with an independent SQL/reference fixture and the
   native governed source for the same dataset before enabling the profile for
   users.

Likely implementation owners are `schemas/postgres/` (new additive migration),
`scripts/fixtures/kernel-optional-db-roles-check.py` (actual-view privilege
checks), `docker-compose.kernel-analytics.yml` plus the Metabase overlay (source
configuration and private networking), `docs/refactor/optional-database-roles.md`,
and a new Kokonut-specific Metabase export/card fixture under
`docs/refactor/builds/` or the repository's chosen dashboard-assets directory.
Do not add credentials to checked-in card exports.

## Acceptance and rollback

The analytics source is ready for promotion only when all of these hold:

- The farm-area result counts distinct farm records correctly, including two
  farms with the same area; eligibility and units have reviewed fixtures.
- Only approved metric keys and human-verified values appear. Periods and
  computation methods are present, and the view has no ambiguous “latest” row
  selection.
- Attestations are limited to the declared Celo scope and approved lifecycle
  states. No private payload or evidence columns are available.
- The source role can select exactly the approved views and cannot access base
  tables, other schemas, unapproved views, writes, DDL, the metadata database,
  or another database.
- Kokonut-specific Metabase cards match independent reference outputs for
  counts, totals, date ranges, empty results, and eligibility filters. API and
  database failure behavior is understood; dashboard startup alone is not
  parity evidence.
- Metabase is absent from minimal/edge/standard and starts only when the
  analytics profile is explicitly selected.

All schema work is additive. Rollback disables the Metabase source/profile and
revokes the analytics view grants; it does not require restoring operational
tables or deleting report history. Keep the old images, encrypted metadata
archive, and original volumes until the rollback window closes. Do not drop the
reporting schema or alter canonical data as part of a consumer rollback.

## Current decision

Migration 377 and the expanded fixture now pass on the source-aligned scratch
target through migration 378; transactional migration replay and rollback also
pass on a third-generation clone. See [reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json)
and [transactional evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json).
The active candidate has the verified analytics login and a healthy, opt-in
Metabase profile with a separate metadata database/login and credential
encryption. Its only registered source is Metabase's sample H2 demo source; no
Kokonut source connection or cards exist. Next, register the PostgreSQL source
with the read-only analytics login and build cards from the reviewed views. Use
a populated isolated fixture for output parity because the active candidate is
empty. The archived clone still has 25 pending migrations; a separate clone
accepted all 25 without changing fingerprints for 16 populated tables. Source
checksum correction and migration ordering are recorded in
[migration-checksum-drift.md](migration-checksum-drift.md).
