# Field Collector form policy decisions

**Status:** Owner-delegated source policy decisions recorded; deployment pending.
**Decision date:** 12 October 2026.
**Decision authority:** The repository owner explicitly delegated the form-policy
judgment to the implementation agent.
**Source:** `schemas/seeds/140_mobile_forms.sql`; revised definitions publish as
version `1.1.0` after migration 381 is applied.

## Decision rule

The five built-in forms capture location-scoped farm operations, production,
business finance, ecological observations, and soil measurements. Their intended
subjects are farm activities and environmental conditions, not identifiable
people. They are classified `not_required` because they do not require a
participant-linked consent grant for that limited operational purpose. The
collector remains the operator, not the data subject.

`not_required` is a Kokonut form-policy classification. It is not a legal
determination, does not select a legal basis for unrelated processing, does not
make data public, and does not waive lifecycle review. It means the mobile
consent gate will not require a participant link or a `stakeholder_consent`
grant for records submitted against these exact revisions. The source code
continues to require sync and the governed downstream eligibility check.

## Decisions by form

| Form ID | Version | Classification | Category | Purpose | Scope / intended recipient | Participant reference |
| --- | --- | --- | --- | --- | --- | --- |
| `farm_activity_v1` | `1.1.0` | `not_required` | `farm_operations` | Location-scoped operational activity tracking and aggregate labor planning. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `harvest_v1` | `1.1.0` | `not_required` | `farm_production` | Location-scoped crop harvest quantity and quality tracking. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `expense_v1` | `1.1.0` | `not_required` | `farm_finance` | Location-scoped farm operating expense and business receipt accounting. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `field_note_v1` | `1.1.0` | `not_required` | `field_observation` | Location-scoped ecological and operational observations, excluding person-centered records. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `soil_sample_v1` | `1.1.0` | `not_required` | `soil_quality_measurement` | Location-scoped soil sampling and ecological monitoring. | Dynamic enrolled location; authorized operators of that farm location. | No |

All five policies use `consent_scope_type='location'` with a null `scope_id`;
the mobile service derives the actual location from the device enrollment.
`consent_recipient_party_id` and `consent_version` are null because these
operational policies have no participant consent instrument or canonical
recipient party. `consent_recipient_type` is `location_operator`.

Each revision carries reviewer metadata and non-empty JSON evidence naming its
source form, relevant field-data governance guidance, and the owner delegation.
The reviewer field transparently identifies this as an agent-authored decision
under owner delegation; it does not claim a separate human review occurred.

## Per-form collection boundaries

- **Farm Activity:** labor hours are aggregate activity data. Do not enter
  worker names, person-level hours, or performance evaluations.
- **Harvest Event:** keep notes about crops, plots, quality, and operations. Do
  not put personal details in notes.
- **Expense:** use farm business expenses and business receipts only. Do not
  upload personal receipts or include private payment/account information.
- **Field Note:** use for ecological or operational observations. Person-
  centered notes, health/contact/disciplinary details, and other sensitive
  personal records require a separate consent-reviewed workflow.
- **Soil Sample:** notes describe the sample or site conditions, not people.

The API validates form ID, version, collection type, location, and consent
metadata, but it does not validate submitted text or photo content against the
form schema. These collection boundaries are visible instructions, not
server-enforced content filters. A future participant-focused form must use a
separate revision classified `required`, a reviewer-created participant link,
and the exact consent checks in migration 381. Do not broaden these forms to
person-centered use without revisiting their policy.

## Revision and rollout behavior

The source definitions and browser fallback now describe version `1.1.0` and
carry the same categories and purposes. `scripts/seed.sh` includes
`140_mobile_forms.sql` after its ordered migration step, so migration 381 adds
the policy columns and revision triggers before the seed runs.

On a database where migration 381 has already backfilled version `1.0.0`, the
seed's version update creates immutable `1.1.0` snapshots and retires the old
revisions. Pending records that cite a known retired revision remain private and
review-required under the migration contract. This source change has not
applied migration 381, run the seed, changed the candidate database, or altered
any container. Existing version `1.0.0` snapshots remain unclassified until
that migration and seed are applied in order.

## Separate open decisions and gates

These classifications do not settle the human retention/erasure disposition,
organization-wide tenant/RLS policy, or media cleanup/expiry policy. Those
remain release gates. Migration 381 must be applied only by the checksummed
migration runner, then the separately authorized mobile acceptance must verify
active and retired form behavior, no participant-reference requirement for
these five `1.1.0` forms, and ineligibility of legacy unassessed rows. The
existing governed verification/publication boundary remains required after
collection eligibility.
