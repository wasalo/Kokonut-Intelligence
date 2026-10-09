# security

`services.security` — Zero-trust capability-based access control.

## CLI Usage

```bash
python3 -m services.security.cli --help
```

## Modules

- `audit` — Audit logger — logs all access attempts to access_audit_log.
- `capabilities` — Capability manager — zero-trust capability tokens for fine-grained authorization.
- `cli` — CLI for capability-based security.
- `execution_allowlist` — Allowlisted Python entry points for database-driven workers.
- `interceptor` — gRPC interceptor for capability-based authorization.

## Files

5 Python modules
