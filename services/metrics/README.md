# metrics

`services.metrics` — Metric computation engine — governed metric calculators and storage.

## CLI Usage

```bash
python3 -m services.metrics
```
```bash
python3 -m services.metrics.cli --help
```

Reconcile crop-cycle NOI snapshots for one location (requires migration 379):

```bash
python3 -m services.metrics --reconcile-noi-snapshots --location-id UUID
```

For an explicitly requested manual aggregate reconciliation, use
`--reconcile-noi-snapshots --all-locations`. The native scheduler requires one
location per `noi_snapshots` task; its daily plan remains disabled until the
schedule owner approves activation.

## Modules

- `cli` — Metric Computation Engine
- `engine` — Metric Computation Engine
- `calculators/` — sub-package

## Files

3 Python modules
