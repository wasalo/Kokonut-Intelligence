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

## Request and failure contract

- `POST /api/v1/sensors/{device_id}/readings` accepts one signed JSON reading.
  `POST /api/v1/sensors/{device_id}/readings/batch` accepts 1–100 readings.
- `X-Signature` is HMAC-SHA256 over the exact request bytes. The receiver looks
  up the active device slug and shared secret in PostgreSQL; an optional
  `sha256=` prefix is accepted. The JSON device ID must match the URL.
- The ASGI body limiter caps single requests at 10,240 bytes and batch requests
  at 262,144 bytes, and stops waiting for a body after ten seconds. Oversize
  requests return 413; body timeout returns 408; missing/invalid signatures
  return 401; URL/payload identity mismatch returns 400.
- Each accepted reading commits the canonical PostgreSQL reading, device-health
  update, analytical outbox row, and durable platform event on one connection.
  A single-reading retryable storage failure returns 503 with
  `Retry-After: 30`; retry the identical timestamp and payload so the existing
  dedupe identity can resolve uncertain commit outcomes.
- Batch processing is sequential and each item has its own transaction. The
  response can therefore contain a mix of successes, duplicates, and
  retryable failures; it is not all-or-nothing. A retryable batch result is
  reported in the JSON body (`retryable` and `retry_after_seconds`), so clients
  must retry only failed items with their original timestamps.
- The receiver has no built-in per-device rate limit or public TLS listener.
  Keep it private; a private network does not replace HMAC or active-device
  authorization. The health endpoint is liveness only.

## Evidence and remaining gates

Earlier isolated recovery checks exercised the receiver over TCP from a second
container, including HMAC rejection, authenticated single/batch writes, URL/
payload mismatch, duplicate timestamp behavior, and delivery of selected
outbox projections to ClickHouse. [Listener evidence](builds/2026-10-10-recovery/sensor-http-listener.json),
[CSV/HTTP evidence](builds/2026-10-10-recovery/sensor-csv-http.json), and
[outbox evidence](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json).
Those checks used the isolated recovery fixture and did not enable this Compose
overlay. They do not certify its merged runtime identity, database grants,
startup/health, optional-profile independence, or shutdown behavior.

Compose parsing used placeholder credentials; no secret values were printed.
The optional `http-sensors` Compose service has not been built or started. No
test suite was run for this contract update. Remaining gates include overlay
image import/startup, runtime-role grants, timestamp-mode selection and UTC
identity, batch retry behavior, body-limit boundary/timeout, shutdown, service
liveness, disabled ClickHouse behavior, and public-ingress policy. This is a
prepared deployment option, not certified transport parity.

Rollback stops/removes only candidate `http-sensors` and omits its overlay.
Omitting a manifest alone leaves an orphan service running. Preserve database,
outbox, ingestion logs, and device configuration; no volume removal is needed.
Keep the legacy stack stopped and avoid overlapping ingress during cutover.
