# Kokonut Field Collector

The Field Collector is a dependency-free HTML companion tool for field workers.
It saves records to browser `localStorage` first, then uploads them to the
mobile API when the browser is online.

## Entry points

- Gateway (preferred): `/mobile` or `/api/mobile/app`
- Caddy static route: `/field/field-collector.html`
- Directus endpoint: `/field-collector/` (redirects to the Caddy route)
- Direct file: open `field-collector.html` directly in a browser

Base Compose runs the gateway service and Caddy proxies `/mobile*` and
`/api/mobile/*` to it, so phones on the LAN can use same-origin sync without
manual Settings.

## Local network access

Replace `<lan-ip>` with the host machine's LAN address (for example
`192.168.1.42`). Dev Caddy uses an internal CA, so phones may need to accept a
self-signed certificate warning for HTTPS.

| Path | URL | Notes |
|------|-----|-------|
| Preferred (gateway via Caddy) | `https://<lan-ip>/mobile` | HTML + `/api/mobile` same origin |
| Static HTML via Caddy | `https://<lan-ip>/field/field-collector.html` | API also same-origin via `/api/mobile/*` proxy |
| Loopback gateway | `http://127.0.0.1:8099/mobile` | Host-only; not reachable from phones |
| Direct file | `file://.../field-collector.html` | Set Settings → API URL to `https://<lan-ip>` or `http://<lan-ip>:8099` |

Start the stack with `docker compose up -d` (includes `gateway`). Host-only
fallback: `python3 -m services.gateway.cli --serve --port 8099`.

When opened directly as a file, configure the API origin in Settings before
syncing. The app does not require a connection to record data.

## API

- `POST /api/mobile/register` issues a browser/device token.
- `GET /api/mobile/forms` returns active cached form definitions.
- `POST /api/mobile/sync` accepts up to 50 idempotent records per request.
- `GET /api/mobile/sync/status` returns device queue status.

Device tokens are sent in `X-Device-Token` and are stored hashed in
`mobile_device.device_token_hash`. Raw field payloads remain in the governed
`offline_collection` queue; this v1 companion does not automatically promote
them into canonical domain tables.
