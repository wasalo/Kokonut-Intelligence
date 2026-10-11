# Optional private HTTP sensor role

`docker-compose.kernel-http-sensors.yml` adds `http-sensors` using the default
Kernel Dockerfile, existing standalone receiver, and private candidate network.
It requires only the PostgreSQL credential and explicitly disables every vendor
provider. Canonical readings and outbox entries remain PostgreSQL writes;
ClickHouse delivery is deferred. Neither MQTT nor its SDK is required.

The service listens on container port 8056 without publishing a host port.
The Kernel Caddy overlay continues to route only to the gateway; it does not
expose this receiver. Network peers can reach the receiver, so its existing
device HMAC/identity checks still apply. Do not treat a private network as device
authorization. Field-device ingress, TLS, rate limits, device status policy,
and gateway policy parity remain prerequisites for public adoption.

Command planning now supports:

```sh
python3 scripts/kernel-profile.py minimal --http-sensors
```

This prints a configuration command without running Docker or loading secrets.
Load encrypted secrets and review the standalone receiver's transaction,
timestamp, retry, and body-limit records before executing a deployment command.
The shared timestamp mode is passed explicitly with a legacy default. If HTTP
and MQTT are selected together, they receive the same exported setting, but
cross-transport historical deduplication still requires reconciliation.

The healthcheck probes `/api/v1/health` at port 8056 instead of the inherited
gateway port. This is process liveness, not database readiness, device validation,
or evidence of successful ingestion. Startup raises errors when FastAPI/Uvicorn
are unavailable or the port is invalid. Forwarded client headers are explicitly
ignored. Init, restart policy, and a 40-second grace period apply to this role;
request drain and committed-write uncertainty require runtime acceptance.

Static lint, placeholder-only Compose parsing, and diff checks passed. No image
build, receiver start, tests, HTTP messages, migrations, or sensor writes were
performed. Pending gates include image import/startup, HMAC and device checks,
transaction failure recovery, UTC identity, retry headers, bounded requests,
shutdown, liveness, and disabled ClickHouse behavior. This is a prepared
deployment option, not certified transport parity.

Rollback stops/removes only candidate `http-sensors` and omits its overlay.
Omitting a manifest alone leaves an orphan service running. Preserve database,
outbox, ingestion logs, and device configuration; no volume removal is needed.
Keep the legacy stack stopped and avoid overlapping ingress during cutover.
