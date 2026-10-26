# Directus RBAC Permissions

SQL seed file that creates the complete Directus role-based access control system.

## Extension Build Prerequisite

The base Compose service mounts the hook package at
`/directus/extensions/directus-extension-kokonut-hooks`. Directus loads its
compiled entry point from the ignored `extensions/kokonut-hooks/dist/`
directory, so a fresh checkout must build it before starting Compose:

```bash
make hooks-build
docker compose up -d directus
```

`make hooks-build` installs the exact lockfile dependencies with `npm ci` when
they are missing or stale, then runs the Directus extension bundler plus
TypeScript validation. The Field Collector endpoint is plain JavaScript and
does not require a build step.

## Files

| File | Purpose |
|---|---|
| `permissions.sql` | Roles, policies, access rules, and per-collection CRUD permissions |

## How It's Applied

`scripts/seed.sh` pipes this file to PostgreSQL:

```bash
cat config/directus/permissions.sql | docker exec -i kokonut-database psql -U kokonut -d kokonut_intelligence
```

The SQL uses `ON CONFLICT` / `IF NOT EXISTS` guards — safe to re-run.

## Roles

| Role | Description | Access Level |
|---|---|---|
| Field Worker | Field data entry staff | Create/read/update own location records (draft only) |
| Supervisor | Field supervisors | Read all, submit for approval |
| Manager | Farm/location managers | Full status transitions including rejection |
| Finance | Finance/accounting staff | Expense, sales, revenue focus |
| Analyst | Data analysts | Read-only verified/published data |
| Auditor | Compliance/audit | Read-only all statuses for forensic review |
| Agent Read-Only | Automated agents | Read-only access to governed collections |
| Agent Write | Automated agents | Create draft records, cannot publish |
| Agent Full | Trusted agents | Broader write access, still cannot verify/publish |

## Protected Collections

Agent roles are restricted from `verified`/`published` status on all governed collections. This is enforced by:

1. **`permissions.sql`** — role grants exclude status transitions to `verified`/`published`
2. **`services/agents/safety.py`** — runtime guard rejects agent writes to governed collections
3. **Directus hooks** — `extensions/kokonut-hooks/` enforces lifecycle rules

## Adding New Collection Permissions

1. Add the collection to the relevant role's permission block in `permissions.sql`
2. Follow the existing pattern: `INSERT INTO directus_permissions (collection, action, fields, permissions, presets, ...)` with appropriate `role_id` and `policy_id`
3. Re-apply via `./scripts/seed.sh`
4. Test with `python3 -m tests.test_directus_metadata`

`farm_activity` is intentionally excluded from Directus role permissions. The
Kokonut Gateway owns Field Collector and operator farm-activity operations,
including tenant-qualified grants, lifecycle validation, and the append-only
actor ledger. Reapplying `permissions.sql` removes stale farm-activity rules
from the repository-managed policies. Do not re-add these permissions to make
the unlicensed Directus API expose that collection.

The Auditor's `dashboard_dataset` read permission uses an explicit metadata
field allowlist and excludes archived `query_sql`. Reapplying the seed repairs
the wildcard rule and preserves non-wildcard operator-edited field lists. The
hook also rejects query operators that reference the archived SQL and redacts
it from responses; custom permission policies still need review.
