# Worker Cron Schedule

Crontab for the `kokonut-worker` container, running periodic ingestion, computation, and maintenance tasks.

## Files

| File | Purpose |
|---|---|
| `crontab` | Cron job definitions for the worker container |

## How It's Installed

`Dockerfile.worker` copies and installs the `appuser` crontab:

```dockerfile
COPY config/worker/crontab /tmp/kokonut-crontab
RUN crontab -u appuser /tmp/kokonut-crontab
```

Changes require rebuilding the worker image:

```bash
docker compose -f docker-compose.yml -f docker-compose.worker.yml build kokonut-worker
docker compose -f docker-compose.yml -f docker-compose.worker.yml --profile worker up -d kokonut-worker
```

## Cron Jobs

| Job | Schedule | Command |
|---|---|---|
| Weather ingestion | Every 6 hours | `python3 -m services.ingestion.weather` |
| Market data | Daily 06:00 UTC | `python3 -m services.ingestion.market_data --source world_bank` |
| EAS indexer | Every 15 minutes | `python3 -m services.ingestion.eas_indexer` |
| RPC wallet indexer | Every 30 minutes | `python3 -m services.ingestion.rpc_indexer` |
| Sensor ingester | Every 5 minutes | `python3 -m services.ingestion.sensor_ingester` |
| Gnosis Chain indexer | Every 2 hours | `python3 -m services.ingestion.gnosis_indexer` |
| Anomaly detection | Every hour | `python3 -m services.ingestion.anomaly_detector` |
| Metrics computation | Every 4 hours | `python3 -m services.metrics --compute --all-locations` |
| Health check + alerting | Every 5 minutes | `bash scripts/health-alert.sh` |
| Dashboard dataset refresh | Every 6 hours | `python3 -m services.export.dataset_refresh --all` |
| Data freshness check | Every hour | `python3 -m services.ingestion.data_freshness --check` |
| Climate data refresh | Sundays 03:00 UTC | `python3 -m services.ingestion.climate_data --all --location-id ...` |

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

Adjust timing via environment variables in `docker-compose.worker.yml` if needed, or edit the crontab directly. The crontab is baked into the image — changes are not hot-reloaded.
