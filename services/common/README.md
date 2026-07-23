# common

`services.common` — Shared infrastructure used across all Kokonut services.

## Modules

- `cli` — Shared CLI helpers: `run()` (clean error + exit code), `print_json()` (canonical JSON), `get_connection()` (context-managed DB), `mount_argparse()` (adapter for legacy argparse CLIs)
- `database` — `DatabaseConnection` class wrapping psycopg2 with SQLAlchemy-like `:param` style, context-managed commit/rollback/close
- `db` — PostgreSQL and ClickHouse connection config constants (`PG_HOST`, `PG_PORT`, etc.) loaded from environment
- `env` — Idempotent `.env.sops` / `.env` loader via SOPS decryption
- `logging` — Structured logging: `get_logger(name)` under `kokonut.*` namespace

## Usage

```python
from services.common.cli import run, print_json, get_connection
from services.common.database import get_connection, DatabaseConnection
from services.common.logging import get_logger

logger = get_logger("my_service")

with get_connection() as conn:
    rows = conn.execute("SELECT * FROM location").all()
    print_json(rows)
```
