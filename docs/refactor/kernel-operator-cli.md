# Kernel operator CLI overview

The local operator entry point is the unified CLI:

```bash
python3 -m services.cli kernel overview
python3 -m services.cli kernel schema-readiness
```

`kernel overview` reports the platform version, build SHA, and configured
provider selections. It reads feature settings only: it does not connect to
PostgreSQL, probe optional services, start workers, or print credential values.
Its JSON explicitly reports `health_checked: false` and
`database_checked: false`; enabled providers are configuration, not evidence of
runtime availability.

`kernel schema-readiness` is a separate read-only database gate. It checks the
bundled migration checksums, required extensions, and selected application
relations/columns without applying migrations. It requires the configured
PostgreSQL connection and reports bounded categories/counts on failure.

The existing `GET /api/health/services` Gateway route is public and probes
configured services. It is not the authenticated operator console and is not
used by `kernel overview`. A browser-based operations console remains pending an
explicit operator identity/scope, audit, CORS, and action policy. Future console
write actions must use the governed service APIs and preserve human approval;
the overview command is intentionally local and read-only.
