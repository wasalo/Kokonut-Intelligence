# Field Collector form policy decisions

**Status:** Owner-delegated policy decisions recorded; source payload validation
is implemented and deployed in revision `1.2.0` on the local candidate.
**Decision date:** 12 October 2026.
**Decision authority:** The repository owner explicitly delegated the form-policy
judgment to the implementation agent.
**Source:** `schemas/seeds/140_mobile_forms.sql`; revised definitions publish as
version `1.2.0`. The local candidate now serves these revisions after a
checkpointed seed and app rollout; the earlier immutable `1.1.0` revisions are
retired.

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
| `farm_activity_v1` | `1.2.0` | `not_required` | `farm_operations` | Location-scoped operational activity tracking and aggregate labor planning. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `harvest_v1` | `1.2.0` | `not_required` | `farm_production` | Location-scoped crop harvest quantity and quality tracking. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `expense_v1` | `1.2.0` | `not_required` | `farm_finance` | Location-scoped farm operating expense and business receipt accounting. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `field_note_v1` | `1.2.0` | `not_required` | `field_observation` | Location-scoped ecological and operational observations, excluding person-centered records. | Dynamic enrolled location; authorized operators of that farm location. | No |
| `soil_sample_v1` | `1.2.0` | `not_required` | `soil_quality_measurement` | Location-scoped soil sampling and ecological monitoring. | Dynamic enrolled location; authorized operators of that farm location. | No |

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

The API validates each submitted payload against the JSON Schema in its exact
immutable form revision. Built-in `1.2.0` schemas reject undeclared fields and
enforce required fields, primitive types, enums, numeric bounds, and date
formats. Validation errors do not echo submitted values. This structural
allowlist cannot determine whether a free-text value contains a person's name
or sensitive information, and it does not inspect photo contents; collection
guidance and governed human review still apply. A future participant-focused
form must use a separate revision classified `required`, a reviewer-created
participant link, and the exact consent checks in migration 381. Do not broaden
these forms to person-centered use without revisiting their policy.

## Revision and rollout behavior

The source definitions, browser fallback, and candidate database now describe
version `1.2.0` and carry the same categories and purposes as the earlier
`1.1.0` policy revisions. The schema validator and
`additionalProperties: false` allowlists are deployed to the local candidate.
`scripts/seed.sh` includes `140_mobile_forms.sql` after its ordered migration step, so migration 381 adds
the policy columns and revision triggers before the seed runs.

On a database where migration 381 has already backfilled version `1.0.0`, the
seed's version update first created immutable `1.1.0` snapshots on the local
candidate. The checkpointed candidate seed created immutable `1.2.0` snapshots
and retired `1.1.0`; known retired records remain private and review-required
under the migration contract. The seed was first exercised on an isolated
restored clone, which retained the old snapshots and produced five active
closed-schema revisions. Populated databases retain their own unassessed legacy
rows until migration and seed are applied in order.

## Separate open decisions and gates

These classifications do not settle the human retention/erasure disposition,
organization-wide tenant/RLS policy, or media cleanup/expiry policy. Those
remain release gates. An isolated live HTTP check verified active `1.2.0`
unknown-field rejection and a valid sync without a participant reference.
Separately authorized mobile acceptance must still verify the trusted
enrollment-created device path, retired-form behavior, and ineligibility of
legacy unassessed rows.
The existing governed verification/publication boundary remains required after
collection eligibility.
