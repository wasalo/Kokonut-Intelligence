# metrics

`services.metrics` — Metric computation engine — governed metric calculators and storage.

## CLI Usage

```bash
python3 -m services.metrics
```
```bash
python3 -m services.metrics.cli --help
```

Reconcile the current crop-cycle NOI snapshots from PostgreSQL's shared view
(requires migration 379):

```bash
python3 -m services.metrics --reconcile-noi-snapshots
```

The corresponding `noi_snapshots` scheduler job is planned as a daily task and
remains disabled until its schedule owner approves activation.

## Modules

- `cli` — Metric Computation Engine
- `engine` — Metric Computation Engine
- `calculators/` — sub-package

## Files

3 Python modules
