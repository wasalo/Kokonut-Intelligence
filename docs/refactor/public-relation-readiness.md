# Public relation readiness contract

The optional Kernel schema gate now checks catalog presence and required columns
for the four relations used by the migrated public read slice:

| Relation in public schema | Required object kind | Contract fields |
| --- | --- | --- |
| v_public_farm_summary | view | location ID/name, country, region, status |
| v_public_metric_summary | view | location ID, metric key/name/unit/value/timestamp |
| v_public_attestation_summary | view | location ID, total/published counts, latest timestamp |
| crisp_risk_assessment | table or partitioned table | assessment/location IDs, periods, methodology, composite score/rating/confidence/maturity, timestamp, status |

`services/core/schema_readiness.py:PUBLIC_READ_RELATIONS` is the deliberately
bounded application contract. It is not a generated replacement for migrations
or a complete inventory of every platform table. Catalog inspection uses
pg_class/pg_namespace/pg_attribute in the same read-only repeatable-read
transaction as migration/extension checks. Relation names are query parameters;
there is no dynamic SQL identifier construction or database object mutation.

A missing relation, wrong object kind, or absent required column blocks startup
with `public_relations_mismatch`. Reports include relations_expected,
relations_invalid and columns_missing counts, without names or row contents.
A missing relation contributes all of its required columns to columns_missing;
those counts overlap. Earlier inventory/tracking/schema/extension failures take
precedence, so zero relation counters on those failures do not mean the relation
stage passed. The successful readiness report records four checked relations.

The check does not validate column types, view definitions, visibility predicates,
grants, row-level security, indexes, seed completeness, query plans or response
behavior. A manually changed view can still satisfy this structural check.
Authorization and capability acceptance remain separate required gates. Additional
domain migrations must define their own read contracts rather than treating this
small catalog check as whole-platform certification.

## Execution and rollback

Lint, static provider/dependency checks and diff checks passed. The new catalog
check was subsequently rebuilt into the AMD64 portability image and deployed to
both API and idle worker. Both passed the gate against the existing database;
see [the runtime record](portability-runtime.md) for current/rollback identities.
No tests, schema changes, task activation or fixture writes ran. Missing-object
rejection paths, grants, query behavior and ARM64 runtime remain unvalidated.

When adopted, repair missing objects through reviewed additive migrations or a
compatible image/database release. Do not update tracking checksums to bypass
the gate. Rollback selects the previous API/worker image; that earlier gate lacks
this structural protection. Preserve database state and reviewed public view
definitions during diagnosis.
