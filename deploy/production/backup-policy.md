# Production backup policy

**Principle: no irreplaceable data exists until a backup has been taken
AND a restore from that backup has been verified.**

## Schedule

| What | When | Tool | Retention |
|---|---|---|---|
| Full checkpoint (pg_dump + ClickHouse + volumes) | nightly 03:30 host time | `scripts/backup.sh` | 30 days |
| Off-host copy | after each checkpoint | rsync/rclone to object storage | 30 days |
| Restore rehearsal | first Monday monthly, manual | `scripts/restore.sh` + `verify-backup.sh` | evidence logged |

## Storage targets

1. **Local**: `/opt/ki-prod/backups` (fast restore, dies with the host)
2. **Off-host (required)**: Hostinger Object Storage or Backblaze B2.
   Configure rclone remote `ki-backups`; the nightly cron pushes each new
   checkpoint directory after `verify-backup.sh` passes.

## Nightly flow (cron on prod host)

```
03:30  scripts/backup.sh                    # encrypted checkpoint
04:00  verify-backup.sh <checkpoint>        # integrity + decrypt test
04:15  rclone copy /opt/ki-prod/backups/<id> remote:ki-prod-backups/<id>
```

Alert channels (`ALERT_WEBHOOK_URL` / `ALERT_SMTP_*`) fire on any step
failing — see `config/worker/crontab` and `scripts/health-alert.sh`.

## Restore rehearsal (monthly, documented procedure)

```bash
# 1. Pick the newest checkpoint
CHECKPOINT=$(ls -1d /opt/ki-prod/backups/checkpoint-* | sort | tail -1)

# 2. Verify integrity
./scripts/verify-backup.sh "$CHECKPOINT"

# 3. Restore into a THROWAWAY project (never over production)
COMPOSE_PROJECT_NAME=ki-restore-test ./scripts/restore.sh \
    --checkpoint "$CHECKPOINT" --confirm

# 4. Spot-check data
docker compose -p ki-restore-test exec database psql -U kokonut \
  -d kokonut_intelligence -c "SELECT count(*) FROM location;"

# 5. Tear down the rehearsal project
docker compose -p ki-restore-test down -v
```

Log each rehearsal (date, checkpoint id, result) in this file's
[Rehearsal log](#rehearsal-log).

## Rehearsal log

| Date | Checkpoint | Result | Notes |
|---|---|---|---|
| — | — | — | no rehearsals yet (production not deployed) |

## Encryption

Checkpoints are encrypted with `BACKUP_ENCRYPTION_KEY`. The key is stored
in the SOPS-encrypted env — it rotates with the environment secrets.
Losing it means losing every backup: the key must exist in at least two
independent places (prod env + Wasabi's password manager).
