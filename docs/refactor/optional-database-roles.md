# Optional database consumer roles

**Status (11 October 2026):** role boundaries passed on fresh isolated copies of
the populated application and Metabase metadata databases. The expanded
reporting-view check also passed against a current-schema scratch database in a
copied recovery volume; it did not migrate the restored application database,
whose historical checksum drift remains unresolved. The pinned Directus
owner bootstrap completed and its DML-only runtime became healthy. Metabase
initialized a separate empty metadata database as a non-superuser and became
healthy. A separate sanitized review classified the restored board as generic
e-commerce demo content over the sample H2 source; retain it only as an
explicitly labeled demo fixture. The populated farm-summary and Celo-attestation
views also matched independent base-table queries on a separate disposable
copy; the metric view returned zero rows because that data has no published
policy. On that copy, the analytics role could read only the three curated
reporting views among reporting relations and was denied on application tables,
the private policy table, and DDL. Those role checks did not change the
candidate or legacy databases. The recovery-only Compose manifest is not a
deployable Kernel profile.
See [populated parity evidence](builds/2026-10-11-recovery/populated-report-view-parity.json).

Before migration 377 was applied, the candidate had only the `kokonut`
superuser login and inherited `PUBLIC CONNECT`/`TEMPORARY` grants. The reporting
schema is now applied and the separate `kokonut_analytics_ro` login is
provisioned on the dedicated candidate. It can connect only to the application
database and read only the three approved reporting views; its real-login
checks denied application tables, the private policy table, DDL, temp tables,
and other databases. The reviewed ACL change revoked `PUBLIC CONNECT` across
the four candidate databases and `PUBLIC TEMPORARY` on the application
database. Eight extension metadata relations and 1,165 extension functions
remain accessible through inherited extension grants; none is SECURITY
DEFINER. The Metabase metadata role/profile is implemented separately but has
now been provisioned on `kokonut_metabase`; its real login can create metadata
objects and is denied on the application database. The pinned Metabase profile
is healthy at a loopback-only port with credential encryption enabled. The
candidate now has a separate `Kokonut Reporting Views` source using
`kokonut_analytics_ro` and an inclusion filter for `kokonut_reporting`; schema
sync lists only its three approved views. Three Kokonut cards and a dashboard
are saved. Their queries complete but return zero rows on the empty candidate;
populated report-output parity remains open.
[Pre-migration ACL inventory](builds/2026-10-11-recovery/candidate-reporting-acl-review.json); [migration result](builds/2026-10-11-recovery/candidate-migration-apply.json); [active analytics-role evidence](builds/2026-10-11-recovery/candidate-analytics-role.json); [candidate Metabase profile](metabase-kernel-profile.md).

## Why these are separate identities

The legacy `docker-compose.yml` connects both Directus and Metabase as the
`kokonut` PostgreSQL superuser. Directus uses the application database with
`DB_SEARCH_PATH=public,kokonut`; Metabase keeps its own application metadata in
the `metabase` database. The repository does not configure Metabase's
operational data source, so its source permissions cannot be inferred from
Compose. Neither optional product is enabled in the Kernel candidate or
standard profile.

| Identity | Database scope | Required access | Explicit boundary |
| --- | --- | --- | --- |
| `kokonut_directus_runtime` | Kernel application database | `CONNECT`; `USAGE`; `SELECT`, `INSERT`, `UPDATE`, `DELETE` on Directus-managed relations; sequence `USAGE`, `SELECT`, `UPDATE` | No ownership, schema `CREATE`, role/database administration, or access to the metadata database. Directus CRUD permissions remain a separate API authorization layer. |
| `kokonut_metabase_app` | One dedicated Metabase metadata database | Owns that database's application relations so Metabase can create and migrate its metadata schema | No superuser, `CREATEDB`, `CREATEROLE`, or connection to the Kernel application database. Do not reuse it as an analytics-source account. |
| `kokonut_analytics_ro` | One explicitly configured source database | `CONNECT`, `USAGE` on a reviewed reporting schema, and `SELECT` on individually approved views | No application-table access, writes, schema creation, metadata-database access, or public sharing of private evidence. The local candidate role is provisioned; production provisioning remains separate, and no operational Metabase source connection is configured. |

PostgreSQL's `PUBLIC CONNECT` and extension relation grants are inherited by all
roles unless revoked. The recovery fixture revokes `PUBLIC CONNECT` on every
database in its dedicated test instance, then grants only the named target
databases. The analytics login still sees five built-in PostGIS and
`pg_stat_statements` metadata relations through existing `PUBLIC SELECT`
grants. It has no access to application relations in `public`, including
`schema_migration`. A production grant plan must explicitly review extension
ACLs and all database ACLs before applying the same instance-wide hardening.

## Directus bootstrap and runtime split

The pinned Directus image's default command runs `cli.js bootstrap` before
starting the server. Bootstrap can install or migrate the database, which is
outside the DML-only runtime role. For Kernel use, keep a one-shot
owner-backed bootstrap/upgrade operation and start the long-running service
with the image's native `cli.js start` command after bootstrap succeeds. This
command split was exercised with the pinned `12.1.1` image on the isolated
populated restore; the runtime role had no ownership or DDL privileges and the
server became healthy.

Directus runtime DML is intentionally broad within the managed `public` and
`kokonut` schemas. The populated restore exposed DML on 1,386 public relations
to that internal service identity. It is not an analytics connection and must
not be shared with Metabase. Keep Directus user/policy/field permissions and
the existing authorization tests as the user-facing access boundary.

Directus remains a separate future profile. Likely touchpoints are:

- `docker-compose.yml`: remove `DB_USER=kokonut` from the legacy Directus
  service and use explicit Directus admin/runtime credentials.
- New `docker-compose.kernel-directus.yml`: optional service plus a separately
  invoked bootstrap profile; its app command must not run bootstrap as the
  runtime user.
- `services/migration/runtime_role.py`: keep the native Kernel DML role
  separate; do not extend it to Directus or Metabase.
- `tests/test_directus_metadata.py`, `tests/test_gateway_auth.py`, and the
  Directus permission SQL in `config/directus/permissions.sql`: preserve the
  independent API permission boundary and verify access after changing DB
  identities.

## Metabase metadata and source access

Metabase's metadata database contains saved questions, dashboards, collections,
and users. Its application role must be able to run Metabase's schema
migrations in that one database. The populated restore test transferred
ownership of 290 application relations and the database to the non-superuser
`kokonut_metabase_app` role. A synthetic create/alter/drop and DML check passed;
the role could not connect to the Kernel application database or `postgres`.
The check did not alter saved rows or inspect question contents. Avoid a broad
`REASSIGN OWNED` for this transfer: it also targeted system-required objects in
the restore. Transfer reviewed application relations and sequences in the
metadata schema, confirm their owners, then set the dedicated metadata database
owner. The fixture used the same synthetic role for the populated metadata copy
and a separate empty startup database; a production instance should point the
role at exactly one metadata database.

Metabase's operational data source is a different credential. The source
should use a read-only login against a future curated PostgreSQL reporting
schema, for example `kokonut_reporting`, with explicit per-view grants. Do not
grant `SELECT` across all of `public`: that would expose private and
unpublished application data. The source role should receive no writes or DDL.
If model persistence, uploads, or actions are later required, add a separate
writable connection and schema for that specific feature.

The view contract is specified in
[`metabase-reporting-contract.md`](metabase-reporting-contract.md), and
[`schemas/postgres/377_kokonut_reporting_contract.sql`](../../schemas/postgres/377_kokonut_reporting_contract.sql)
now implements the curated views and an empty, lifecycle-governed metric
allowlist. The role fixture grants only those three views and exercises their
behavior with transaction-rolled-back synthetic rows. Migration 377 was applied
through the tracked runner to `kokonut_reporting_scratch`; the post-run plan
reported zero pending schema migrations. Exact view grants, base-table and
policy-table denials, and farm/metric/Celo-attestation behavior passed. The
active candidate now has the same curated schema plus the verified
`kokonut_analytics_ro` login; Metabase has no source connection yet. The
archived application database's checksum drift at `schema:000_extensions.sql`
was not repaired or bypassed. See the
[reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract.json)
and [read-only drift triage](migration-checksum-drift.md).

The legacy metadata contains 39 saved cards and one dashboard. Structural
review found a generic **E-commerce Insights** board over the sample H2 source;
preserve it only for demo/compatibility use, not as Kokonut reporting. A
populated legacy metadata startup, source registration, and Kokonut-specific
card/output parity remain open. The candidate-only Metabase overlay and
metadata bootstrap are prepared in
[`metabase-kernel-profile.md`](metabase-kernel-profile.md). The first-start
check uses a separate empty database and does not connect to any saved source.
Startup evidence is
[here](builds/2026-10-11-recovery/optional-consumer-startup.json).

## Isolated fixture and repeatable commands

The fixture uses the encrypted application and Metabase archives, a fresh
PostGIS/PostgreSQL volume, synthetic passwords, and an internal-only Docker
network. Decryption streamed into `pg_restore`; no plaintext archive was
written to disk. It creates no host port or external route. All DML probes use
synthetic tables/views, which the fixture removes. Metabase application
ownership changes are confined to the copied `metabase` database.

The sanitized role-boundary evidence is
[optional consumer database roles](builds/2026-10-11-recovery/optional-consumer-db-roles.json).
The fixture is
[`scripts/fixtures/kernel-optional-db-roles-check.py`](../../scripts/fixtures/kernel-optional-db-roles-check.py),
run through
[`docker-compose.kernel-recovery-consumer-roles.yml`](../../docker-compose.kernel-recovery-consumer-roles.yml).
It checks repeatable role attributes, Directus DML/default privileges and DDL
denials, Metabase metadata relation ownership and a synthetic metadata
migration, exact grants on the actual Kokonut reporting views, equal-area farm
and plot aggregation, unsupported-unit handling, farm-specific registration,
metric publication filtering, Celo-only attestation lifecycle aggregation, and
cross-database connection denials. The app-side reporting behavior uses only
synthetic rows rolled back in the scratch database. No saved Metabase SQL, user
records, or credential values are logged.

When repeating this check, use a new project name and volume. Do not attach the
fixture network or roles to the candidate, standard, portability, or legacy
deployment. After the current check, stop the fixture containers and retain the
volume as evidence.

## Promotion and rollback gates

Before enabling optional consumers in a real Kernel profile:

1. Take a checksum-verified logical checkpoint of the application DB,
   Metabase metadata DB, Directus uploads/extensions, and any Redis-backed
   Directus rate-limit/collaboration state.
2. Provision separate passwords in encrypted secrets. Keep the PostgreSQL
   owner credential out of long-running application environments.
3. Run Directus bootstrap as the owner using the exact pinned image; run the
   server with its runtime identity and confirm `server/ping`, API permissions,
   extension hooks, and protected routes.
4. Assign the Metabase application role only to the metadata database. Start
   the pinned app and restore a copied metadata database. Preserve the reviewed
   sample dashboard only as an explicitly labeled demo/compatibility fixture;
   do not carry it forward as Kokonut analytics.
5. The restored metadata inventory found one sample H2 source: all 39 saved
   cards and 22 dashboard placements refer to it, with no configured
   PostgreSQL/ClickHouse source. Structural review classified the board as
   generic e-commerce demo content. See the [source and disposition report](metabase-source-inventory.md)
   and [sanitized content evidence](builds/2026-10-11-recovery/metabase-content-inventory.json).
   Define Kokonut's measures and published/consented views, grant the source
   login only those views, build first-party cards, and compare results with
   agreed reference outputs before enabling the analytics profile.
6. Update the Kernel overlays and secrets examples only after these checks
   pass. Keep the baseline profile free of Directus and Metabase.

If a Directus or Metabase upgrade fails, stop that service and restore the
matching pre-change database and file checkpoint. Directus migrations may not
be safely reversible; do not rely on automatic downgrade alone. Keep the role
boundary in place during rollback, and restore the prior service image and
credentials from the same checkpoint. Do not make a cluster superuser the
long-running service identity as a recovery shortcut.

Official references: [Directus upgrades and database migrations](https://docs.directus.io/self-hosted/upgrades-migrations),
[Metabase application database](https://www.metabase.com/docs/latest/installation-and-operation/migrating-from-h2),
[Metabase self-hosted security guidance](https://www.metabase.com/docs/latest/installation-and-operation/security-best-practices-self-hosting).

## Metabase source inventory — 11 October 2026

The encrypted legacy metadata archive restored successfully into a fresh,
internal-only recovery database. The sole registered source is marked as
Metabase's sample H2 source; host and database name are unset, and no nonempty
password value is present.
All 39 saved cards use that source, and the one dashboard has 22 placements
using the same source. No PostgreSQL or ClickHouse source appears in the
metadata. The inventory did not inspect card names or definitions, print
connection values, execute queries, or start Metabase against the populated
copy. [Report](metabase-source-inventory.md) ·
[machine evidence](builds/2026-10-11-recovery/metabase-source-inventory.json).

The initial source inventory did not inspect card names; the later structural
review classifies this as generic e-commerce demo content and recommends
keeping it only as an explicitly labeled demo/compatibility fixture. The open
decision is which governed Kokonut views and first-party cards should power
optional Metabase. Do not connect Metabase or claim dashboard parity until that
source contract and output comparison are complete. See the
[source and disposition report](metabase-source-inventory.md) and
[content evidence](builds/2026-10-11-recovery/metabase-content-inventory.json).

### Populated metadata startup — 11 October 2026

On a separate fresh restore, the pinned Metabase image started with
`kokonut_metabase_app`, the non-superuser owner of the isolated metadata DB.
The health endpoint returned 200 and Docker reported `healthy`. Post-startup
counts matched the earlier inventory of the same encrypted metadata archive:
39 cards, one dashboard, 22 dashboard placements, and one user. The source
remained the sample H2 database; no query definition
was read or executed. The role fixture again confirmed cross-database
connection denials and that the curated analytics login could read its
synthetic view while application/base relations remained denied. The
containers/network were removed and the fresh volume retained. [Evidence](builds/2026-10-11-recovery/metabase-populated-startup.json).

## Active candidate analytics-source role — 11 October 2026

The exact candidate now has a separate `kokonut_analytics_ro` login. The
repeatable bootstrap is [services/migration/analytics_role.py](../../services/migration/analytics_role.py)
and its isolated deployment entry point is
[`docker-compose.kernel-analytics-role.yml`](../../docker-compose.kernel-analytics-role.yml).
The one-shot profile revoked PUBLIC database CONNECT across the four existing
candidate databases and PUBLIC TEMPORARY on `kokonut_intelligence`, then granted
the role CONNECT only to the application database and SELECT only on
`v_farm_summary`, `v_verified_metric_values`, and `v_attestation_summary`.
The credential is stored in `.env.sops` under `KOKONUT_ANALYTICS_PASSWORD`;
the application continues to use its existing credential. No Metabase source
or cards were configured.

An actual login read the three views (all currently return zero rows because
this candidate has no pilot data or published metric policies) and was denied
on `public.schema_migration`, the private policy table, schema DDL, temporary
tables, and all other candidate databases. No unreviewed public application
relation was readable. Existing extension ACLs remain inherited: 16 extension
relations have PUBLIC SELECT, of which eight are visible to this login; 1,165
extension functions remain executable and none of the public-executable
extension functions is SECURITY DEFINER. These extension privileges should be
reassessed if the PostgreSQL image or profile changes. Full machine output is in
[candidate analytics-role evidence](builds/2026-10-11-recovery/candidate-analytics-role.json).

The bootstrap changes PUBLIC CONNECT on every existing database, so use it only
with a dedicated Kernel PostgreSQL instance. Its exact ACL rollback should be
reviewed per database; the pre-change candidate ACL inventory listed the app,
`postgres`, and `template1` but not `template_postgis`. To disable only the
source login, set `kokonut_analytics_ro` to `NOLOGIN` and revoke its three view
grants. The retained candidate access hardening can remain in place.

## Active candidate Metabase metadata identity — 11 October 2026

The opt-in profile is defined in
[`docker-compose.kernel-metabase.yml`](../../docker-compose.kernel-metabase.yml)
and documented in [`metabase-kernel-profile.md`](metabase-kernel-profile.md).
Its one-shot bootstrap created `kokonut_metabase`, owned by
`kokonut_metabase_app`, and granted that role only CONNECT and CREATE on the
metadata database. A real login created a temporary metadata table and rolled
it back; the same credential was denied CONNECT to `kokonut_intelligence`.
Metabase's source connection must continue to use the distinct read-only
`kokonut_analytics_ro` identity.

The Metabase image is pinned at 0.62.4. The profile supplies a separate
SOPS-managed `MB_ENCRYPTION_SECRET_KEY`; its startup log confirmed saved
credential encryption is enabled before source registration. Metabase is
healthy with the corrected metadata grants; its sanitized inventory found one
sample H2 source, 39 generic demo cards, one demo dashboard with 22 placements,
and one user record. No Kokonut source or card has been configured. Keep the
encryption key with encrypted metadata backups; losing it makes saved
connection details unrecoverable. See [profile evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json).
