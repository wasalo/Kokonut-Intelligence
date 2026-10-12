# Field Collector form classification review

**Status:** decision worksheet; no form classifications have been approved.
**Source:** `schemas/seeds/140_mobile_forms.sql`, current form version `1.0.0`.
**Runtime status:** migration 381 has not been applied. This worksheet does not
change form policy, seed data, migration source, or database state.

## How to complete this review

An authorized reviewer must complete one decision record for each exact form
revision. Do not infer consent requirements from the field names or from a
collector's enrollment. Keep the revision `unclassified` until the completed
decision is approved and published as a new immutable form revision under
migration 381.

For each revision, record:

- `consent_classification`: `required` or `not_required`, with reviewer, review
  timestamp, and non-empty evidence. `unclassified` is the current state, not
  an approval choice.
- data category, collection purpose, recipient type and recipient name;
- exact consent version and scope type/identifier when consent is required;
- whether the workflow needs an opaque participant reference (never a canonical
  party ID in a mobile request);
- retention period/rule and the human disposition for withdrawal, correction,
  erasure requests, and expired evidence;
- whether the form's free-text fields or attachments need additional handling.

If a field cannot be decided, record the open question and leave the revision
unclassified. “Not required” still needs reviewer metadata and evidence. The
review decision is about the exact form version; a later content or policy
change requires a new version.

## Current form inventory

These are source descriptions, not consent determinations. Free-text fields
can contain information beyond their labels; reviewers should consider that
possibility without treating it as a preselected data category.

| Form ID | Name / collection type | Required fields in source schema | Other source fields | Current decision |
| --- | --- | --- | --- | --- |
| `farm_activity_v1` | Farm Activity / `farm_activity` | `activity_type`, `activity_date` | `description`, `labor_hours`, `notes` | Pending; version `1.0.0`, active in seed |
| `harvest_v1` | Harvest Event / `harvest_event` | `harvest_date`, `quantity`, `unit` | `crop`, `plot`, `quality_grade`, `notes` | Pending; version `1.0.0`, active in seed |
| `expense_v1` | Expense / `expense_event` | `expense_date`, `category`, `amount` | `description`, `vendor`, `notes`; form description allows an optional receipt photo | Pending; version `1.0.0`, active in seed |
| `field_note_v1` | Field Note / `field_note` | `note_date`, `content` | `note_type`, `title`, `tags` | Pending; version `1.0.0`, active in seed |
| `soil_sample_v1` | Soil Sample / `soil_sample` | `sample_date` | `depth_cm`, `depth_layer`, `ph`, `organic_matter_pct`, `texture`, `moisture_pct`, `notes` | Pending; version `1.0.0`, active in seed |

## Reviewer decision records

Copy and complete this record separately for each form ID/version above. Use
`TBD` only to document an unresolved field; it does not authorize a policy
change. Keep supporting evidence in the approved review location and reference
it here without adding sensitive evidence to this repository.

### Decision record — `farm_activity_v1` version `1.0.0`

- Consent classification (`required` / `not_required`): **Pending**
- Data category:
- Collection purpose:
- Recipient type and name:
- Scope type and identifier (if required):
- Consent version (if required):
- Participant reference required (`yes` / `no`):
- Retention rule and withdrawal/erasure disposition:
- Free-text/photo handling notes:
- Reviewer identity and review timestamp:
- Evidence reference:
- Approved by / approval timestamp:
- New immutable version to publish:
- Unresolved questions:

### Decision record — `harvest_v1` version `1.0.0`

- Consent classification (`required` / `not_required`): **Pending**
- Data category:
- Collection purpose:
- Recipient type and name:
- Scope type and identifier (if required):
- Consent version (if required):
- Participant reference required (`yes` / `no`):
- Retention rule and withdrawal/erasure disposition:
- Free-text/photo handling notes:
- Reviewer identity and review timestamp:
- Evidence reference:
- Approved by / approval timestamp:
- New immutable version to publish:
- Unresolved questions:

### Decision record — `expense_v1` version `1.0.0`

- Consent classification (`required` / `not_required`): **Pending**
- Data category:
- Collection purpose:
- Recipient type and name:
- Scope type and identifier (if required):
- Consent version (if required):
- Participant reference required (`yes` / `no`):
- Retention rule and withdrawal/erasure disposition:
- Receipt-photo handling and retention:
- Reviewer identity and review timestamp:
- Evidence reference:
- Approved by / approval timestamp:
- New immutable version to publish:
- Unresolved questions:

### Decision record — `field_note_v1` version `1.0.0`

- Consent classification (`required` / `not_required`): **Pending**
- Data category:
- Collection purpose:
- Recipient type and name:
- Scope type and identifier (if required):
- Consent version (if required):
- Participant reference required (`yes` / `no`):
- Retention rule and withdrawal/erasure disposition:
- Free-text/photo handling notes:
- Reviewer identity and review timestamp:
- Evidence reference:
- Approved by / approval timestamp:
- New immutable version to publish:
- Unresolved questions:

### Decision record — `soil_sample_v1` version `1.0.0`

- Consent classification (`required` / `not_required`): **Pending**
- Data category:
- Collection purpose:
- Recipient type and name:
- Scope type and identifier (if required):
- Consent version (if required):
- Participant reference required (`yes` / `no`):
- Retention rule and withdrawal/erasure disposition:
- Free-text/photo handling notes:
- Reviewer identity and review timestamp:
- Evidence reference:
- Approved by / approval timestamp:
- New immutable version to publish:
- Unresolved questions:

## Gates after review

1. Resolve each record with an authorized reviewer and preserve the decision
   evidence.
2. Add reviewed policy to a new immutable form version; do not update an
   existing published revision in place.
3. Keep organization-wide tenant/RLS policy and human retention/erasure
   disposition as separate open decisions; this worksheet does not settle them.
4. Apply migration 381 only with the ordered, checksummed migration runner and
   complete the separately authorized live mobile acceptance gate.

Until these gates pass, all five current revisions remain unclassified and
ineligible for downstream reporting or publication under the documented
eligibility contract.
