# export

`services.export`

## CLI Usage

```bash
python3 -m services.export
```
```bash
python3 -m services.export.cli --help
```

## Modules

- `business_plan` — Business-plan assembler (composes existing EPS / VSM / analytics).
- `cli` — Export CLI — delegates to report_generator for report generation and exports.
- `dataset_refresh` — Dataset Refresh Engine — Execute stored dashboard_dataset queries
- `exporter` — Export Service — CSV, JSON, Parquet
- `kokonut_graphs` — Visual graph descriptors for the State of Kokonut report.
- `report_generator` — Report Generator — Farm Summary, Crop NOI, Environmental Impact
- `spatial_export` — Spatial export: GeoJSON, KML, XML export for zones, trees, and boundaries.
- `spatial_import` — Spatial import: KML/GeoJSON file parsing into farm_zone geometry.
- `spreadsheet_bridge` — CSV spreadsheet bridge for low-barrier farm activity exchange.

## Files

10 Python modules
