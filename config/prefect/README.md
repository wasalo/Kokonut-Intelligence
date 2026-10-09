# Prefect Workflow Deployments

Deployment configuration for Prefect workflow orchestration.

## Files

| File | Purpose |
|---|---|
| `deployment.yaml` | Flow deployment definitions with schedules and tags |

## Deployments

| Name | Flow | Schedule | Tags |
|---|---|---|---|
| `scheduled-hourly` | `scheduled_hourly` | Every hour | `scheduled`, `hourly` |
| `scheduled-every-6h` | `scheduled_every_6h` | Every 6 hours | `scheduled`, `every-6h` |
| `scheduled-daily` | `scheduled_daily` | Daily at 06:00 UTC | `scheduled`, `daily` |
| `scheduled-weekly` | `scheduled_weekly` | Sundays at 03:00 UTC | `scheduled`, `weekly` |
| `full-pipeline` | `full_pipeline` | Manual only | `manual`, `full` |

All flows are defined in `services/flows/pipelines.py`.

## Usage

```bash
# Apply all deployments
prefect deployment apply deployment.yaml

# Run a specific deployment
prefect deployment run "scheduled-daily"

# Run manually (without deployment)
python3 -m services.flows.pipelines full_pipeline
```

## Adding New Deployments

1. Create the flow in `services/flows/pipelines.py`
2. Add a deployment entry to `deployment.yaml`
3. Apply: `prefect deployment apply deployment.yaml`

## Cron Expressions

All schedules use UTC. Reference:

- `0 * * * *` — every hour
- `0 */6 * * *` — every 6 hours
- `0 6 * * *` — daily at 06:00
- `0 3 * * 0` — weekly on Sundays at 03:00
