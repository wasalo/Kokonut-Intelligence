# Spreadsheet Guide

The spreadsheet bridge supports CSV exchange for farm activity records. It is intended for operators and partners who work offline or in simple spreadsheets.

## Create Template

```bash
python3 -m services.export.spreadsheet_bridge --template exports/farm_activity_template.csv
```

## Validate Import

```bash
python3 -m services.export.spreadsheet_bridge --import-file data/farm_activity.csv --dry-run
```

## Import Farm Activity

```bash
python3 -m services.export.spreadsheet_bridge --import-file data/farm_activity.csv
```

Imported rows start as `draft` and keep source metadata in `source_raw`.

## Export Farm Activity

```bash
python3 -m services.export.spreadsheet_bridge --export-file exports/farm_activity.csv --location-id UUID
```

Exports include only `verified` and `published` farm activity rows.

## Required Fields

- `location_id`
- `activity_type`
- `activity_date`
- `description`

Manual spreadsheet data can introduce quality issues. Operators should submit imported drafts for review before using them in public reports.
