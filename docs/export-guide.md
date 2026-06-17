# Data Export & Report Guide

Kokonut Intelligence provides structured data exports and report snapshots for partners, compliance, and analysis.

## Export Types

| Format | Extension | Use Case |
|--------|-----------|----------|
| CSV | `.csv` | Spreadsheet analysis, partner delivery |
| JSON | `.json` | API integration, programmatic use |
| Parquet | `.parquet` | Analytical workloads, ClickHouse import |

## Using the Export Service

### CLI

```bash
# Export harvest events to CSV
python3 -m services.export.exporter \
  --collection harvest_event \
  --format csv \
  --output exports/

# Export with filters
python3 -m services.export.exporter \
  --collection harvest_event \
  --format json \
  --filter '{"location_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"}' \
  --output exports/

# Export with date range
python3 -m services.export.exporter \
  --collection expense_event \
  --format parquet \
  --filter '{"expense_date": {"$gte": "2026-01-01", "$lte": "2026-06-30"}}' \
  --output exports/

# Export from ClickHouse
python3 -m services.export.exporter \
  --collection daily_event_counts \
  --format csv \
  --source clickhouse \
  --output exports/
```

### Python API

```python
from services.export.exporter import Exporter

exporter = Exporter()

# Export to CSV
result = exporter.export(
    collection="harvest_event",
    format="csv",
    output_dir="exports/",
    filters={"status": "verified"},
)
print(f"Exported {result.row_count} rows to {result.file_path}")

# Export to JSON
result = exporter.export(
    collection="crop_cycle",
    format="json",
    output_dir="exports/",
    filters={"location_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"},
)
```

## Export Log

Every export is logged to the `export_log` table:

```sql
SELECT
    el.export_type,
    el.target_table,
    el.row_count,
    el.file_size_bytes,
    el.status,
    el.created_at
FROM export_log el
ORDER BY el.created_at DESC
LIMIT 20;
```

| Column | Description |
|--------|-------------|
| `export_type` | `csv`, `json`, `parquet` |
| `target_table` | Collection that was exported |
| `filters` | JSONB of applied filters |
| `row_count` | Number of rows exported |
| `file_size_bytes` | Output file size |
| `status` | `pending`, `generating`, `completed`, `failed` |

## Report Snapshots

Report snapshots are frozen, reproducible outputs stored in `report_snapshot`. Each snapshot includes a hash for verification.

### Report Types

| Type | Description |
|------|-------------|
| `farm_summary` | Location-level operational and financial summary |
| `crop_noi` | Crop cycle net operating income |
| `environmental` | Soil carbon, biodiversity, water usage |
| `impact` | Partner impact metrics and outcomes |
| `partner` | Custom partner-facing reports |
| `public` | Public-facing transparency reports |

### Using the Report Generator

```bash
# Generate a farm summary for a location
python3 -m services.export.report_generator \
  --type farm_summary \
  --location-id a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11

# Generate a crop NOI report
python3 -m services.export.report_generator \
  --type crop_noi \
  --location-id a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11

# Generate an environmental impact report
python3 -m services.export.report_generator \
  --type environmental \
  --location-id a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11

# List existing snapshots
python3 -m services.export.report_generator --list
```

### Snapshot Hash Verification

Each snapshot includes a SHA-256 hash of its data for reproducibility:

```sql
SELECT
    rs.report_name,
    rs.report_type,
    rs.snapshot_hash,
    rs.period_start,
    rs.period_end,
    rs.status,
    rs.created_at
FROM report_snapshot rs
WHERE rs.location_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
ORDER BY rs.created_at DESC;
```

Verify a snapshot:

```python
import hashlib
import json

def verify_snapshot(snapshot_data, expected_hash):
    """Verify snapshot data integrity."""
    computed = hashlib.sha256(
        json.dumps(snapshot_data, sort_keys=True, default=str).encode()
    ).hexdigest()
    return computed == expected_hash
```

## API Examples

### Trigger Export via Directus REST

```bash
# Trigger a CSV export via Directus Flow (if configured)
DIRECTUS_URL=${DIRECTUS_URL:-https://localhost/directus}
curl -k -X POST "$DIRECTUS_URL/flows/trigger/EXPORT_FLOW_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "harvest_event",
    "format": "csv",
    "filters": {"status": "verified"}
  }'
```

### Download Exported File

```bash
# Get the latest export file URL
curl -k -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/export_log?sort[]=-created_at&limit=1&fields[]=file_url"

# Download
curl -k -H "Authorization: Bearer $TOKEN" \
  "$(curl -sk -H "Authorization: Bearer $TOKEN" \
    "$DIRECTUS_URL/items/export_log?sort[]=-created_at&limit=1&fields[]=file_url" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['file_url'])")" \
  -o export.csv
```

## Scheduled Exports

### Via Directus Flows

Configure a Directus Flow with a cron trigger:

1. Go to **Flows** → **Create Flow**
2. Add **Cron Trigger**: `0 0 1 * *` (monthly)
3. Add **Webhook** operation calling the export service
4. Add **Notification** operation to alert when complete

### Via System Cron

```bash
# Monthly export of all verified data
0 0 1 * * cd /path/to/Kokonut-Intelligence && \
  python3 -m services.export.exporter \
    --collection harvest_event --format parquet --output /data/exports/ && \
  python3 -m services.export.exporter \
    --collection expense_event --format parquet --output /data/exports/
```

## Troubleshooting

### "Permission denied" on export

The export user lacks read access to the collection. Check Directus permissions for the export role.

### Export file is empty

The filter returned no results. Verify filter syntax and check the collection has data:

```sql
SELECT COUNT(*) FROM harvest_event WHERE status = 'verified';
```

### ClickHouse export fails

Ensure ClickHouse is running and accessible:

```bash
docker compose exec clickhouse wget --spider -q http://localhost:8123/ping
```

### Snapshot hash doesn't match

The data changed between generation and verification. Regenerate the snapshot:

```bash
python3 -m services.export.report_generator --type farm_summary --location-id UUID --force
```
