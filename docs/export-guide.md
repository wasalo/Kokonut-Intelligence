# Data Export And Report Guide

Kokonut Intelligence has several separate export paths:

1. The generic tabular exporter reads allowlisted PostgreSQL or ClickHouse
   collections and writes local CSV, JSON, or conditional Parquet output.
2. The report generator computes registered report payloads and stores governed
   `report_snapshot` rows.
3. The spreadsheet bridge validates/imports CSV templates.
4. Spatial export/import handles GeoJSON, KML, XML, and spatial import logs.
5. CIDS export produces a compatibility JSON-LD mapping.
6. Dataset refresh executes stored dashboard SQL; it is not a file export.

These paths have different filtering, lifecycle, hash, and persistence behavior.

## Generic Exporter

Implementation: `services/export/exporter.py`.

### CLI

```bash
python3 -m services.export.exporter \
  --collection harvest_event \
  --format csv \
  --output exports/

python3 -m services.export.exporter \
  --collection harvest_event \
  --format json \
  --filter '{"location_id": "LOCATION_UUID"}' \
  --output exports/

python3 -m services.export.exporter \
  --collection expense_event \
  --format parquet \
  --filter '{"expense_date": {"$gte": "2026-01-01", "$lte": "2026-06-30"}}' \
  --output exports/

python3 -m services.export.exporter \
  --collection sensor_reading \
  --format csv \
  --source clickhouse \
  --filter '{"sensor_id": "SENSOR_UUID"}' \
  --output exports/
```

The exact flags should be checked with:

```bash
python3 -m services.export.exporter --help
```

### Python API

The parameter is `fmt`, not `format`:

```python
from services.export.exporter import Exporter

exporter = Exporter()
result = exporter.export(
    collection="harvest_event",
    fmt="csv",
    output_dir="exports/",
    filters={"status": "verified"},
)
print(result.row_count, result.file_path, result.file_size)
```

The signature is:

```python
export(
    collection,
    fmt="csv",
    output_dir="exports/",
    filters=None,
    user_id=None,
    include_drafts=False,
)
```

`ExportResult` contains `collection`, `format`, `file_path`, `row_count`,
`file_size`, and `duration_ms`.

### Collection Allowlist

The exporter rejects collections that are not in its hard-coded
`ALLOWED_COLLECTIONS` list. Examples in this guide must use an allowlisted
collection. Arbitrary PostgreSQL tables and ClickHouse views are not accepted.
The ClickHouse example should not use `daily_event_counts` unless that name is
added to the allowlist.

### Formats

| Format | Behavior |
|--------|----------|
| `csv` | Direct CSV output |
| `json` | JSON output |
| `parquet` | Requires `pyarrow`; otherwise falls back to JSON under a `.json` path |

Parquet fallback is imperfect: the requested export/log format can still say
`parquet` while the generated file is JSON. Confirm `pyarrow` is installed when
Parquet interoperability is required. Parquet type detection is conservative;
numeric samples may become `float64`, booleans are handled after numeric
detection, and other values are converted to strings.

### Output Paths

The exporter creates the output directory and writes timestamped local files,
for example:

```text
exports/harvest_event_20260721T120000Z.csv
```

It sanitizes the collection name. It does not upload files to Directus, create a
Directus file record, or provide a signed HTTP download URL.

## Source And Filter Semantics

### PostgreSQL

PostgreSQL exports execute a `SELECT *` from the allowlisted collection, apply
filters, order by `created_at DESC NULLS LAST`, and load all matching rows into
memory. There is no pagination or continuation token.

Supported filter operators include:

- `$gte`
- `$lte`
- `$gt`
- `$lt`
- `$ne`
- `$in`
- `$like`

Lists are treated as `IN` filters. Unsupported operators are silently ignored;
callers should validate filter input before export. Empty `$in` lists can produce
invalid SQL and should be avoided.

For governed collections, the default filter is:

```json
{"status": {"$in": ["verified", "published"]}}
```

This default is replaced when the caller supplies a status filter. The
`include_drafts=True` API option disables the default governed filter. Export
does not itself verify records; it reads the selected rows.

### ClickHouse

ClickHouse exports use equality filters only:

```sql
SELECT *
FROM <allowlisted_collection>
WHERE key = {key}
ORDER BY timestamp DESC
LIMIT 100000
```

ClickHouse does not support the PostgreSQL operator dictionaries in this path.
Results are capped at 100,000 rows, with no pagination. The target table is
assumed to expose a `timestamp` column and `clickhouse-connect` must be
available. A missing client raises an error.

### Error Behavior

Database and file-generation failures generally propagate. Successful file
generation is logged after the file is written. Export-log failures are printed
as warnings rather than replacing the export result. The exporter does not
reliably create failed export-log rows for every failure path.

## Export Log

`export_log` is defined in `schemas/postgres/008_governance.sql`.

| Column | Meaning |
|--------|---------|
| `id` | Export UUID |
| `user_id` | Optional requesting user |
| `export_type` | Requested format, such as `csv`, `json`, or `parquet` |
| `target_table` | Exported collection |
| `filters` | JSONB filter object |
| `row_count` | Rows written |
| `file_size_bytes` | Output size |
| `file_url` | Local path in the current exporter, not necessarily a URL |
| `status` | Schema-supported export lifecycle |
| `created_at` | Log timestamp |

Schema status values are `pending`, `generating`, `completed`, and `failed`.
The current exporter primarily writes `completed`; it does not consistently
persist intermediate or failed states. There is no export hash, MIME type,
duration, error message, or completion timestamp in this table.

```sql
SELECT export_type, target_table, row_count, file_size_bytes,
       file_url, status, created_at
FROM export_log
ORDER BY created_at DESC
LIMIT 20;
```

## Report Generator

Implementation: `services/export/report_generator.py`.

The current registry contains **94 report types**. The registry is the source of
truth; report descriptions and scopes vary by generator. Report types include
farm, crop, environmental, climate, financial, governance, EBF, CRISP,
ecological, organic, stakeholder, process, business architecture, data stream,
capital, strategic reserve, tactical, simulation, and State of Kokonut reports.

Examples of current types include:

```text
farm_summary, crop_noi, environmental, climate_impact, ebf_scorecard,
ecological_modeling, trophic_pyramid, pest_management, resource_efficiency,
training_impact, revenue_streams, model_validation, data_stream_summary,
business_plan, pitch_deck, process_health, stakeholder_cockpit,
comprehensive_status, strategic_reserve, tactical_layer, simulation_wargame,
capital_accounting, state_of_kokonut
```

This is an abbreviated list, not a complete registry. Inspect
`REPORT_GENERATORS` before relying on a report type.

## Report CLI

```bash
# Generate one location report
python3 -m services.export.report_generator \
  --type farm_summary --location-id LOCATION_UUID

# Repeat --location-id for selected locations
python3 -m services.export.report_generator \
  --type environmental \
  --location-id LOCATION_UUID_1 \
  --location-id LOCATION_UUID_2

# Generate all registered report types for a supported scope
python3 -m services.export.report_generator \
  --auto --location-id LOCATION_UUID

# List existing snapshots
python3 -m services.export.report_generator --list

# Verify an existing snapshot by UUID or exact hash
python3 -m services.export.report_generator --verify SNAPSHOT_UUID_OR_HASH
```

Supported flags are `--type`, repeatable `--location-id`, `--all`,
`--period-start`, `--period-end`, `--list`, `--verify`, and `--auto`.

There is no report-generator `--force`, `--org-id`, `--output`, or generic
`--format` flag. The troubleshooting command using `--force` is invalid.

### `--auto`

`--auto` attempts all 94 registered report generators for the selected scope.
Each report is handled independently; successful reports are persisted even if
others fail. The command exits nonzero when one or more generators fail. There
is no all-or-nothing transaction across the report set.

### Scope And Periods

`--all` passes the literal scope value `all`; it does not centrally iterate every
location. Only network-aware generators interpret that value correctly. Many
location generators require a UUID and may fail with `all` or multiple IDs.

Network-aware report types include State of Kokonut, DAO proposal history,
State of Kokonut graphs, comprehensive status, and strategic reserve.

Period arguments are forwarded to each generator. Some generators apply dates,
some use them to select a reporting year, and some ignore them. There is no
generic report-level date filtering contract.

`--list` returns at most 20 snapshots and provides limited metadata. It does not
offer generic report-type, period, status, or hash-prefix filters.

## Report Snapshots

`report_snapshot` stores report payloads and governance metadata. A newly stored
snapshot is:

```text
status = 'draft'
frozen_at = NULL
```

Snapshot storage does not immediately make a report frozen, verified, or public.
Later migrations add:

- `frozen`
- `frozen_at`
- `frozen_by`
- `expires_at`
- `public_interest_summary`
- `uncertainty_notes`
- `negative_findings`
- `affected_community_voice`

Lifecycle and publication gates remain separate from hash computation.

### Snapshot Hash

The generator computes SHA-256 over a sorted JSON representation:

```python
payload = json.dumps(data, sort_keys=True, default=str)
snapshot_hash = hashlib.sha256(payload.encode()).hexdigest()
```

The payload includes the generated report and attached public-interest context.
Regenerating a report can produce a different hash when fields such as
`generated_at` change. No report file is generated by snapshot storage.

### Verification

```bash
python3 -m services.export.report_generator \
  --verify SNAPSHOT_UUID_OR_EXACT_HASH
```

The command recomputes and prints PASS/FAIL. It does not update snapshot status,
freeze the snapshot, publish it, or return a dedicated verification record.

There is no deduplication or idempotency key for report generation. Re-running a
generator creates another snapshot row.

## Other Export Tools

### Spreadsheet Bridge

```bash
python3 -m services.export.spreadsheet_bridge \
  --template exports/templates/ebf_scorecard_template.csv

python3 -m services.export.spreadsheet_bridge \
  --import-file data.csv --dry-run
```

The bridge supports farm activity and EBF templates, draft farm-activity
imports, scorecard metadata imports, and evidence validation. EBF evidence rows
are validation-only and are not written to canonical evidence records. It does
not verify or publish scorecards.

### Spatial Export And Import

`services/export/spatial_export.py` provides library APIs for zone, tree,
location, combined-project GeoJSON, KML, and XML. It is not a generic exporter
CLI path. `services/export/spatial_import.py` handles GeoJSON/KML imports with
content hashing and import logging; it uses separate spatial logs rather than
`export_log`.

### Dataset Refresh

`services/export/dataset_refresh.py` executes stored `dashboard_dataset.query_sql`
statements and updates dataset metadata. It is not a file export and does not
create `export_log` rows.

```bash
python3 -m services.export.dataset_refresh --all
```

### Business Plan And CIDS

Business-plan generation supports location or organization scope internally:

```bash
python3 -m services.export.business_plan --location-id LOCATION_UUID
python3 -m services.export.business_plan --org-id ORG_UUID
```

It writes JSON to stdout and does not itself persist a report snapshot.

`services/registry/cids_export.py` separately produces CIDS v3.2.0 Essential Tier
JSON-LD. It is a governed compatibility export, not a CSV/JSON/Parquet
collection export.

## Scheduling And Directus

The repository schedules dashboard dataset refresh and operational ingestion,
metrics, indexing, health, and freshness tasks. It does not configure a generic
exporter cron job or report-generator cron job in the worker crontab or scheduled
task seed.

There is no repository-configured Directus export Flow or `EXPORT_FLOW_ID`.
Directus may expose `export_log` through ordinary REST if permissions are
configured, but the exporter does not upload files to Directus or create a
download endpoint. `file_url` should be treated as a local path unless an
external deployment layer changes that behavior.

## Operational Limitations

- PostgreSQL exports load all matching rows into memory.
- ClickHouse exports are capped at 100,000 rows with no continuation token.
- Parquet requires `pyarrow` and has a JSON fallback.
- Generic filter behavior differs between PostgreSQL and ClickHouse.
- Unsupported PostgreSQL operators may be silently ignored.
- Export-log failures may be warnings rather than durable failed records.
- Report generation is not transactionally atomic across 94 report types.
- Snapshot creation starts as draft/unfrozen.
- Hash verification does not change governance state.
- Period and scope behavior is generator-specific.
- A local output path is not a public download URL.

## Tests And Source References

Relevant tests include:

- `tests/test_report_governance.py`
- `tests/test_cids_export.py`
- `tests/test_spreadsheet_bridge.py`
- `tests/test_spatial_export.py`
- `tests/test_smoke.py`
- `tests/test_cli.py`
- report-specific tests importing `REPORT_GENERATORS`

Primary implementation references:

- `services/export/exporter.py`
- `services/export/report_generator.py`
- `services/export/spreadsheet_bridge.py`
- `services/export/spatial_export.py`
- `services/export/spatial_import.py`
- `services/export/dataset_refresh.py`
- `services/export/business_plan.py`
- `services/registry/cids_export.py`
- `schemas/postgres/008_governance.sql`
- `schemas/postgres/007_modeled_outputs.sql`
- `schemas/postgres/113_arkiv_parity.sql`
- `schemas/postgres/179_lifecycle_transition.sql`
- `config/worker/crontab`
- `schemas/seeds/050_scheduled_tasks.sql`
