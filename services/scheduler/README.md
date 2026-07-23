# scheduler

`services.scheduler` — Task scheduler — database-driven replacement for crontab.

## CLI Usage

```bash
python3 -m services.scheduler.cli --help
```

## Modules

- `cli` — CLI for the task scheduler.
- `engine` — Task scheduler engine.
- `parser` — Cron expression parser for the task scheduler.
- `resources` — Resource pool manager for the task scheduler.
- `worker` — Scheduler worker loop.

## Files

5 Python modules
