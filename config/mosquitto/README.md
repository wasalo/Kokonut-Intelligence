# Mosquitto MQTT Broker Configuration

Configuration for the Eclipse Mosquitto MQTT broker used for IoT sensor ingestion.

## Files

| File | Purpose |
|---|---|
| `mosquitto.conf` | Broker settings (port, TLS, auth, persistence, logging) |
| `acl` | Topic access control list |
| `certs/` | TLS certificates (gitignored except README) |

## Quick Start

1. Provision TLS certificates (see `certs/README.md`)
2. Start the broker: `docker compose up -d mosquitto`
3. Verify health: `mosquitto_sub -h localhost -p 8883 --cafile certs/ca.crt --cert certs/healthcheck.crt --key certs/healthcheck.key -t '$SYS/#'`

## Broker Settings

| Setting | Value | Description |
|---|---|---|
| Port | 8883 | TLS-only (no plaintext) |
| Auth | Client certificates | `require_certificate true`, `use_identity_as_username true` |
| ACL | `acl` file | Topic-based read permissions |
| Persistence | Enabled | Data at `/mosquitto/data/` |
| Message limit | 10,240 bytes | Maximum payload size |
| Queue limit | 1,000 messages | Maximum queued messages |

## ACL Topics

| User | Access | Topics |
|---|---|---|
| `sensor-ingestion` | Read | `sensors/+/+/readings` |
| `healthcheck` | Read | `$SYS/#` |

Device certificate identities are added by the provisioning workflow with exact topic permissions.

## TLS PKI

The broker uses mutual TLS (mTLS) — both server and client certificates are required. See `certs/README.md` for the full certificate list and provisioning instructions.

## Docker Mounts

```yaml
mosquitto:
  volumes:
    - ./config/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
    - ./config/mosquitto/acl:/mosquitto/config/acl:ro
    - ./config/mosquitto/certs:/mosquitto/certs:ro
```

## Modifying ACL

1. Edit `config/mosquitto/acl`
2. Restart Mosquitto: `docker compose restart mosquitto`
3. No rebuild required — the file is mounted read-only but Mosquitto reads it at runtime

## Troubleshooting

- **Broker won't start**: Missing TLS certificates. Provision them first (see `certs/README.md`).
- **Connection refused**: Client certificate not signed by the CA, or identity not in the ACL.
- **Healthcheck failing**: Ensure `healthcheck.crt` and `healthcheck.key` exist and are valid.
