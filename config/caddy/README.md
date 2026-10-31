# Caddy Reverse Proxy Configuration

Caddy is an optional reverse-proxy adapter. The repository has separate Caddy
files for the legacy integration stack and the Kernel candidate; the Kernel
Gateway owns route authorization and CORS.

## Files

| File | Purpose |
|---|---|
| `Caddyfile` | Legacy local config — uses externally provisioned `/etc/caddy/certs/cert.pem` and `key.pem` |
| `Caddyfile.production` | Production config — automatic HTTPS via Let's Encrypt |
| `Caddyfile.kernel` | Optional Kernel ingress — redirects HTTP to HTTPS and proxies the host to `app:8099` |
| `Caddyfile.kernel.zitadel` | Kernel ingress when the self-hosted ZITADEL overlay is selected |

## Dev vs Production

These instructions apply to the **legacy** root Compose stack. Its production
overlay (`docker-compose.prod.yml`) swaps the mount:

```yaml
# docker-compose.prod.yml
caddy:
  volumes:
    - ./config/caddy/Caddyfile.production:/etc/caddy/Caddyfile:ro
```

Keep the two legacy route files aligned when modifying legacy routing. Kernel
files deliberately have a different topology and should not copy these routes.

For Kernel ingress, select `--proxy` with `scripts/kernel-profile.py` (and
`--zitadel` if needed). `Caddyfile.kernel` proxies the HTTPS host to the native
Gateway at `app:8099`; the ZITADEL variant also routes the configured identity
host. Kernel profile Caddy is opt-in and binds to loopback by default.

## Current Routes

| Route | Target | Behavior |
|---|---|---|
| `/directus/*` | `directus:8055` | Strip prefix, reverse proxy |
| `/admin/*` | `directus:8055` | Strip prefix, reverse proxy |
| `/maps/*` | Static files | Serve from `/app/services/maps` |
| `/field/*` | Static files | Field collector HTML from `/app/services/mobile` |
| `/mobile*` | `gateway:8099` | Field collector app via gateway; `/mobile` redirects to `/mobile/` for relative shell assets |
| `/api/mobile/*` | `gateway:8099` | Mobile register/forms/sync API |
| `/grpc/*` | `grpc:50051` | gRPC-Web proxy (h2c transport) |
| **catch-all** | `directus:8055` | All other paths go to Directus |

In the legacy stack, the Field Collector is routed at `/mobile/`. The Kernel
Gateway serves its own selected app routes; do not use the legacy path table as
a statement of Kernel feature parity.

Metabase is not routed through either default Caddy file. The legacy Traefik
overlay and Kernel Metabase profile are separate optional configurations.

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

## CORS Headers (Legacy files only)

The legacy `Caddyfile` and `Caddyfile.production` set these headers for their
routes. Kernel Caddy does not set CORS headers; its Gateway applies the
configured origin policy:

```caddy
header {
    Access-Control-Allow-Origin *
    Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
    Access-Control-Allow-Headers "Content-Type, Authorization, x-api-key, x-capability-token, x-device-token"
    Access-Control-Max-Age 86400
}
```

For route-specific CORS, use `@matcher` blocks.

## Security Headers

The two legacy Caddy files apply all four headers to their responses. Kernel
Caddy sets the first three; HSTS is not configured there because it is a
separate ingress profile and requires an explicit HTTPS deployment decision.

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CADDY_DOMAIN` | `localhost` | Legacy production hostname for automatic TLS |
| `CADDY_HTTP_PORT` | `80` | Legacy Compose HTTP listener port |
| `CADDY_HTTPS_PORT` | `443` | Legacy Compose HTTPS listener port |
| `KOKONUT_KERNEL_DOMAIN` | `localhost` | Kernel proxy hostname |
| `KOKONUT_KERNEL_HTTPS_PORT` | `8448` | Kernel HTTPS redirect port; Kernel proxy defaults bind to loopback |

## Troubleshooting

- **Legacy Caddy won't start**: Check that `CADDY_DOMAIN` is set in `.env` for the production file. The legacy local file expects its externally provisioned certificate and key files; it does not generate an internal certificate itself.
- **Kernel Caddy won't start**: Check the selected Kernel profile's domain and certificate storage settings; these differ from legacy `CADDY_DOMAIN` settings.
- **Routes not matching**: Caddy uses longest-match. More specific routes (like `/directus/*`) take precedence over the catch-all.
- **TLS errors in legacy production**: Caddy auto-obtains certs. Ensure port 80 is reachable from the internet for ACME HTTP-01 challenges.
