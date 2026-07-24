# Caddy Reverse Proxy Configuration

Caddy handles TLS termination, request routing, security headers, and gzip encoding for the platform.

## Files

| File | Purpose |
|---|---|
| `Caddyfile` | Development config — self-signed TLS (`tls internal`) |
| `Caddyfile.production` | Production config — automatic HTTPS via Let's Encrypt |

## Dev vs Production

The production overlay (`docker-compose.prod.yml`) swaps the mount:

```yaml
# docker-compose.prod.yml
caddy:
  volumes:
    - ./config/caddy/Caddyfile.production:/etc/caddy/Caddyfile:ro
```

Both files must define the same routes. When adding a new route, edit both files.

## Current Routes

| Route | Target | Behavior |
|---|---|---|
| `/directus/*` | `directus:8055` | Strip prefix, reverse proxy |
| `/admin/*` | `directus:8055` | Strip prefix, reverse proxy |
| `/maps/*` | Static files | Serve from `/app/services/maps` |
| `/field/*` | Static files | Field collector HTML from `/app/services/mobile` |
| `/mobile*` | `gateway:8099` | Field collector app via gateway |
| `/api/mobile/*` | `gateway:8099` | Mobile register/forms/sync API |
| `/metabase/*` | `metabase:3000` | Strip prefix, reverse proxy |
| `/grpc/*` | `grpc:50051` | gRPC-Web proxy (h2c transport) |
| **catch-all** | `directus:8055` | All other paths go to Directus |

Field collector LAN URL (after `docker compose up -d`): `https://<host-lan-ip>/mobile`.

## Adding a Route

Add a `handle` block before the catch-all:

```caddy
handle /new-path/* {
    uri strip_prefix /new-path
    reverse_proxy service-name:port
}
```

For gRPC services, use h2c transport:

```caddy
handle /grpc-new/* {
    reverse_proxy grpc-service:port {
        transport http {
            protocols h2c
        }
    }
}
```

## CORS Headers

Global CORS headers are applied to all responses:

```caddy
header {
    Access-Control-Allow-Origin *
    Access-Control-Allow-Methods "GET, POST, OPTIONS"
    Access-Control-Allow-Headers "Content-Type, Authorization, x-api-key, x-capability-token, x-device-token"
}
```

For route-specific CORS, use `@matcher` blocks.

## Security Headers

Applied globally:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CADDY_DOMAIN` | `localhost` | Domain for TLS certificate |
| `CADDY_HTTP_PORT` | `80` | HTTP listener port |
| `CADDY_HTTPS_PORT` | `443` | HTTPS listener port |

## Troubleshooting

- **Caddy won't start**: Check that `CADDY_DOMAIN` is set in `.env` for production. Dev mode defaults to `localhost`.
- **Routes not matching**: Caddy uses longest-match. More specific routes (like `/directus/*`) take precedence over the catch-all.
- **TLS errors in production**: Caddy auto-obtains certs. Ensure port 80 is reachable from the internet for ACME HTTP-01 challenges.
