# ClickHouse Configuration

XML configuration files for the optional ClickHouse analytical database. The
legacy Compose stack and the Kernel analytics overlay mount `config.d/`
read-only; ClickHouse is not part of the Kernel base or standard profile.

## Files

| File | Purpose |
|---|---|
| `config.d/network.xml` | Binds ClickHouse to `0.0.0.0` (all interfaces) |
| `config.d/profiles.xml` | Query profile tuning (thread limits, memory caps, timeouts) |
| `config.d/experimental.xml` | Enables `allow_experimental_database_materialized_postgresql` |

## Query Profiles

| Profile | Threads | Max Memory | Max Execution Time |
|---|---|---|---|
| `default` | 4 | 4 GB | 60s |
| `analytics` | 8 | 8 GB | 300s |

Use the `analytics` profile for heavy analytical queries:

```sql
SET profile = 'analytics';
SELECT ... FROM ...;
```

## Adding New Config Files

Drop any `.xml` file into `config/clickhouse/config.d/`. ClickHouse reads all files in this directory on startup. Example:

```xml
<clickhouse>
    <max_concurrent_queries>100</max_concurrent_queries>
</clickhouse>
```

Restart the selected ClickHouse service to apply. For the legacy Compose stack,
use `docker compose restart clickhouse`; Kernel analytics uses its separate
Compose project and service.

## Docker Volume Mount

```yaml
clickhouse:
  volumes:
    - ./config/clickhouse/config.d:/etc/clickhouse-server/config.d:ro
```

The `:ro` mount means config files cannot be modified from inside the container.
The example is the legacy Compose service shape; the optional Kernel analytics
overlay mounts the same directory without making ClickHouse a base dependency.
