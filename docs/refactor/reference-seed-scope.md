# Reference seed scope

**Owner decision:** 15 October 2026 — apply reference catalogs only and hold
pilot rows. The owner separately approved the local candidate rollout on 15
October; no production database write was authorized.

## Explicit catalog-only allowlist

`./scripts/seed.sh --catalog-only` applies only these five existing seed
migrations, in this order:

| Seed | Contents | Boundary |
| --- | --- | --- |
| `000_expense_categories.sql` | Expense category lookup values | Catalog values only. |
| `000_metric_definitions.sql` | Canonical metric definitions | Definitions, not computed or verified measurements. |
| `022_metric_governance.sql` | Validation, report-use, and deprecation metadata for the metric catalog | Updates metric definitions only. |
| `103_flow_metrics.sql` | Value-stream metric definitions | Definitions, not measured farm performance. |
| `027_carbon_framework_seeds.sql` | Emission factors, carbon benchmarks, and protocol reference text | Includes estimates; these remain model defaults, not Kokonut farm observations or externally verified outcomes. |

The command is seed-only: it skips schema, ClickHouse, and Directus setup. It
still requires the configured PostgreSQL service and applies the five selected
files through the checksummed migration runner. The default `seed.sh` behavior
is unchanged. The existing `--reference-only` option is retained for
compatibility and still applies the full curated seed list; it is not the
owner-selected catalog scope.

## Local candidate rollout — 15 October 2026

The exact five files above were applied to the migration-400 local candidate
after an explicit owner approval. The runner applied five checksummed
migrations with zero failures. The resulting counts are 19 expense categories,
20 metric definitions, 19 emission factors, 8 carbon benchmarks, and 5
operations protocols. Existing mobile forms (5), form versions (10), and
service registry rows (63) remained at their preflight counts. The candidate
health endpoint returned 200 and the unauthenticated mobile review queue
returned 401. The candidate app, database, Metabase, and proxy were not
recreated; the legacy stack was not touched.

The other 25 curated seed files, `064-068_impact_network.sql`, the already
applied `140_mobile_forms.sql`, and 90 unselected source seeds remain untouched.
No farm measurements or pilot rows were added. See the
[candidate rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json).

## Held curated files

These 25 files remain outside `--catalog-only`:

| Seed(s) | Why held |
| --- | --- |
| `015_revenue_multiplier_config.sql` | Contains model and business assumptions, including prices and operating targets. |
| `023_impact_frameworks.sql` | Mixes useful reference tables with destructive cleanup and Kokonut DAO/Colony instances. Split its safe reference subset before reconsidering. |
| `032_ebf_rubric.sql` | Depends on the EBF framework and dimensions from `023`; include only after a safe standalone framework catalog is prepared. |
| `033_ebf_dashboard_datasets.sql`, `034_ebf_p2_dashboard_datasets.sql`, `035_holistic_wellbeing.sql`, `036_financial_resilience_and_scaling.sql`, `037_capital_efficiency_and_utility.sql`, `038_commons_liberation_and_stewardship.sql`, `039_gnh_alignment_and_inclusion.sql`, `040_regenerative_outcomes_and_stewardship.sql`, `041_open_source_capitalist_scaling.sql`, `042_kokonut_commons_governance.sql` | Mix metric definitions with dashboard records already marked `published` or `verified`. Port and review the report definitions separately before seeding public-facing registry state. |
| `044_bio_factory_operations.sql` | Mixes definitions with regional input-availability estimates and dashboard records. |
| `090_pitch_templates.sql` | Contains active marketing copy with unverified claims about live, funded, and verified farm operations. |
| `091_business_architecture.sql`, `092_technology_roadmap.sql` | Encode active organizational strategy, ownership, and roadmap state. |
| `105_stakeholder_vocabulary.sql` | Contains proxy stakeholder records and a consent row attributed to `system_migration`. |
| `106_stakeholder_engagement.sql`, `107_stakeholder_cockpit.sql`, `108_coordination_example.sql` | Contain Adelphi-specific engagement, published dashboard state, or pilot coordination examples. |
| `109_adelphi_governance_roles.sql`, `110_adelphi_governance_circles.sql` | Create active Adelphi pilot roles and governance circles. |
| `114_state_of_kokonut_funding.sql`, `115_strategic_reserve.sql` | Assert closed/executed historical funding and active reserve balances that have not been owner-verified. |

`140_mobile_forms.sql` is already recorded in the candidate seed ledger and is
not part of the five-file allowlist. `064-068_impact_network.sql` remains
excluded because it includes pilot upserts and location-owner updates. The
other 90 unselected seed sources remain untouched.

## Candidate checkpoint and rollback reference

The current migration-400 candidate was checkpointed and that exact
age-encrypted archive was restore-rehearsed in an isolated PostgreSQL 16.4
`template0` database on 15 October. Its SHA-256 is
`56a08bdf48bce987deffc9a2075e7a4393246d02bfa12bc5f6897d8910e740f1`; restore
parity evidence is recorded in
[the candidate seed checkpoint preflight](builds/2026-10-15-recovery/candidate-reference-seed-checkpoint-preflight.json).
The checkpoint and isolated restore rehearsal preceded the approved candidate
write. The encrypted checkpoint remains the rollback reference; if rollback is
needed, restore into a separately reviewed replacement database and validate
it before cutover. Do not overwrite the candidate in place or rerun a partially
applied batch. The checkpoint is on the same local disk and is not an
independent or production backup.
