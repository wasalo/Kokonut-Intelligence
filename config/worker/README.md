# Worker Cron Schedule

Crontab installed in the legacy `kokonut-worker` image. The current active
crontab runs only the health-check/alert script; scheduled ingestion and
computation examples below it are commented out and are managed by the legacy
database scheduler when enabled. The Kernel candidate uses its native worker
runtime and does not depend on this crontab.

## Files

| File | Purpose |
|---|---|
| `crontab` | Legacy cron definitions installed in the worker image |

## How It's Installed

`Dockerfile.worker` copies and installs the `appuser` crontab:

```dockerfile
COPY config/worker/crontab /tmp/kokonut-crontab
RUN crontab -u appuser /tmp/kokonut-crontab
```

Changes require rebuilding the legacy worker image:

```bash
docker compose -f docker-compose.yml -f docker-compose.worker.yml build kokonut-worker
docker compose -f docker-compose.yml -f docker-compose.worker.yml --profile worker up -d kokonut-worker
```

## Cron Jobs

| Job | Schedule | Command |
|---|---|---|
| Health check + alerting | Every 5 minutes | `bash scripts/health-alert.sh` |

The other ingestion/computation examples in `crontab` are commented out and
marked deprecated. They are not active jobs. Enable or configure work through
the selected scheduler, with the appropriate feature, source, and review gates.

Sensor ingestion is source-driven and is not a recurring cron job. Use the
explicit CSV or single-reading CLI, or configure the HTTP/MQTT receiver for a
real device source. The no-argument `sensor_ingester` command is invalid.

## Adding New Jobs

1. Edit `config/worker/crontab`
2. Follow the cron format: `minute hour day-of-month month day-of-week command`
3. All commands run from `/app` with the Kokonut Python environment
4. Logs go to `/var/log/cron.log`
5. Rebuild: `docker compose -f docker-compose.yml -f docker-compose.worker.yml build kokonut-worker`

Backups are operator-owned and must run from the host or a dedicated backup
service. The worker intentionally does not include the Docker CLI or Docker
socket required by `scripts/backup.sh`.

Worker health checks validate service endpoints and system resources. Docker
container checks are disabled because the worker has no Docker CLI or socket.

## Timing Adjustments

For the active legacy health-alert cron, edit the crontab directly. Its
contents are baked into the image and are not hot-reloaded. Kernel schedule
cadence is defined by the native scheduler configuration and database state,
not by this file.
