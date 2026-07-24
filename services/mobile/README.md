# Kokonut Field Collector

The Field Collector is a dependency-free HTML companion tool for field workers.
It saves records to browser `localStorage` first, then uploads them to the
mobile API when the browser is online.

## Entry points

- Gateway: `/mobile` or `/api/mobile/app`
- Caddy static route: `/field/field-collector.html`
- Directus endpoint: `/field-collector/` (redirects to the Caddy route)
- Direct file: open `field-collector.html` directly in a browser

When opened directly as a file, configure the Gateway or Caddy API origin in
Settings before syncing. The app does not require a connection to record data.

## API

- `POST /api/mobile/register` issues a browser/device token.
- `GET /api/mobile/forms` returns active cached form definitions.
- `POST /api/mobile/sync` accepts up to 50 idempotent records per request.
- `GET /api/mobile/sync/status` returns device queue status.

Device tokens are sent in `X-Device-Token` and are stored hashed in
`mobile_device.device_token_hash`. Raw field payloads remain in the governed
`offline_collection` queue; this v1 companion does not automatically promote
them into canonical domain tables.
