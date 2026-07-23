# Spreadsheet Guide

The spreadsheet bridge provides low-barrier CSV exchange for farm activity and selected EBF metadata. It is intended for operators and partners who work offline or in simple spreadsheets. The bridge connects directly to PostgreSQL; it does not bypass the governed lifecycle or replace human review.

## CLI Modes

The CLI executes one mode at a time: template generation, import/validation, or farm-activity export. `--template-type` selects the CSV contract for template and import operations.

## Farm Activity Template

```bash
python3 -m services.export.spreadsheet_bridge --template exports/templates/farm_activity_template.csv
```

The generated `farm_activity` header contains:

| Field | Required | Description |
|---|---|---|
| `location_id` | Yes | Location UUID |
| `plot_id` | No | Plot UUID |
| `crop_cycle_id` | No | Crop-cycle UUID |
| `activity_type` | Yes | Activity category |
| `activity_date` | Yes | Activity date |
| `description` | Yes | Human-readable activity description |
| `labor_hours` | No | Non-negative numeric labor hours |
| `labor_cost` | No | Non-negative numeric labor cost |
| `materials_used` | No | JSON-compatible materials value when populated |
| `notes` | No | Additional notes |
| `source_system` | No | Source system label |
| `source_id` | No | Upstream source identifier |

## Farm Activity Validation And Import

```bash
python3 -m services.export.spreadsheet_bridge --import-file data/farm_activity.csv --dry-run
python3 -m services.export.spreadsheet_bridge --import-file data/farm_activity.csv
```

Validation checks each CSV data row, starting at row 2, for the four required fields. `labor_hours` and `labor_cost`, when supplied, must be numeric and non-negative. Dates, UUIDs, and JSON structure are not prevalidated; database casts and constraints may still reject invalid values.

`--dry-run` returns the number of validated rows and errors without writing. A normal import inserts rows into `farm_activity` with `status = 'draft'`, defaults `source_system` to `spreadsheet_bridge` when absent, preserves an optional `source_id`, and stores the complete source row in `source_raw`. The bridge commits the import through PostgreSQL; imported drafts still require governed review before verification or publication.

Farm activity lifecycle values are `draft`, `submitted`, `verified`, `published`, and `rejected`. Directus permissions prevent normal field workers from setting lifecycle status during creation; the bridge also always inserts draft rows.

## Export Farm Activity

```bash
python3 -m services.export.spreadsheet_bridge --export-file exports/farm_activity.csv --location-id UUID
```

Exports include only `verified` and `published` farm activity rows.

The export requires `--location-id`, writes the standard farm-activity fields to the requested CSV path, creates missing parent directories, and orders rows by `activity_date DESC` and then `created_at DESC`. It does not export draft, submitted, or rejected rows, audit fields, evidence arrays, or the full `source_raw` payload.

## EBF Scorecard Template And Import

Generate an EBF scorecard-period template:

```bash
python3 -m services.export.spreadsheet_bridge \
  --template exports/ebf_scorecard_template.csv \
  --template-type ebf_scorecard
```

The fields are:

- Required: `location_id`, `period_start`, `period_end`, `rubric_version`.
- Optional: `farm_id`, `calibration_method`, `calibration_report_url`.

Allowed `calibration_method` values are `third_party`, `team_with_report`, and `mixed_panel`.

Validate without writing:

```bash
python3 -m services.export.spreadsheet_bridge \
  --import-file data/ebf_scorecard.csv \
  --template-type ebf_scorecard \
  --dry-run
```

Importing without `--dry-run` creates or updates `ebf_scorecard` records as `draft`, with evidence maturity `1` and `public_claim_allowed = FALSE`. Existing rows upsert on `(location_id, period_start, period_end, rubric_version)`; optional farm and calibration values update when supplied, and source-row metadata is merged into the record metadata. The bridge does not verify or publish scorecards.

## EBF Evidence Validation

Generate an EBF evidence-link template:

```bash
python3 -m services.export.spreadsheet_bridge \
  --template exports/ebf_evidence_template.csv \
  --template-type ebf_evidence
```

Required fields are `scorecard_id`, `pillar_key`, `evidence_type`, and `evidence_id`. Optional fields include `evidence_maturity_level` and `evidence_summary`. Supported evidence types are:

- `metric_value`
- `soil_sample`
- `species_observation`
- `water_analysis`
- `remote_sensing_observation`
- `stakeholder_feedback`
- `stakeholder_outcome`
- `impact_claim`
- `attestation_record`
- `report_snapshot`
- `file_upload`

Validate evidence CSV rows with:

```bash
python3 -m services.export.spreadsheet_bridge \
  --import-file data/ebf_evidence.csv \
  --template-type ebf_evidence
```

Evidence maturity must be an integer from 0 through 6. The current CLI validates EBF evidence CSV but does not persist `ebf_score_evidence` rows; persistence remains a separate governed workflow.

## Governance And Quality

Spreadsheet input is not evidence verification. Operators should inspect identifiers, dates, units, numeric values, JSON-compatible fields, and source lineage before submitting drafts for review. Do not use imported drafts in public reports or public EBF scorecards until the owning workflow verifies and publishes them.

## Implementation References

- Bridge implementation: `services/export/spreadsheet_bridge.py`
- Farm activity schema: `schemas/postgres/003_operations.sql`
- Farm activity permissions: `config/directus/permissions.sql`
- Focused tests: `tests/test_spreadsheet_bridge.py`
