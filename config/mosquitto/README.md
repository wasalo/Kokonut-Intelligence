# Mosquitto MQTT Broker Configuration

Configuration for the optional Eclipse Mosquitto MQTT broker used by sensor
ingestion adapters. The root `docker-compose.yml` service belongs to the
legacy integration stack; Kernel MQTT is selected with the dedicated overlay.

## Files

| File | Purpose |
|---|---|
| `mosquitto.conf` | Broker settings (port, TLS, auth, persistence, logging) |
| `acl` | Topic access control list |
| `certs/` | TLS certificates (gitignored except README) |

## Quick Start

1. Provision TLS certificates (see `certs/README.md`) and a Mosquitto-format
   password file at `/mosquitto/data/passwd`. The Kernel overlay requires the
   existing host password-file path explicitly; it does not generate it.
2. Start the legacy broker with `docker compose up -d mosquitto`, or have the
   Kernel profile planner print an MQTT-enabled command, for example
   `python3 scripts/kernel-profile.py edge --mqtt`. Review the command before
   running it. The Kernel overlay requires explicit certificate and
   password-file paths.
3. For the legacy stack, verify the loopback-published broker with
   `mosquitto_sub -h localhost -p 8883 --cafile certs/ca.crt --cert certs/healthcheck.crt --key certs/healthcheck.key -t '$SYS/#'`.
   The Kernel overlay publishes no broker host port; its authenticated
   container healthcheck is the local probe.

## Broker Settings

| Setting | Value | Description |
|---|---|---|
| Port | 8883 | TLS-only (no plaintext) |
| Auth | Mutual TLS plus a Mosquitto password file | `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false` |
| ACL | `acl` file | Topic-based read permissions |
| Persistence | Enabled | Data at `/mosquitto/data/` |
| Message limit | 10,240 bytes | Maximum payload size |
| Queue limit | 1,000 messages | Maximum queued messages |

## ACL Topics

| User | Access | Topics |
|---|---|---|
| `sensor-ingestion` | Read | `sensors/+/+/readings` |
| `healthcheck` | Read | `$SYS/#` |

Device certificate identities and their exact topic permissions must be
provisioned separately; no repository workflow automatically creates them.

## TLS PKI

The broker uses mutual TLS (mTLS) — both server and client certificates are required. See `certs/README.md` for the full certificate list and provisioning instructions.

## Legacy Docker Mounts

```yaml
mosquitto:
  volumes:
    - ./config/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
    - ./config/mosquitto/acl:/mosquitto/config/acl:ro
    - ./config/mosquitto/certs:/mosquitto/certs:ro
```

## Modifying ACL

1. Edit `config/mosquitto/acl`
2. Restart the selected broker. For the legacy stack: `docker compose restart mosquitto`.
3. No rebuild required — the file is mounted read-only but Mosquitto reads it at runtime

## Troubleshooting

- **Broker won't start**: Missing TLS certificates. Provision them first (see `certs/README.md`).
- **Connection refused**: Client certificate not signed by the CA, or identity not in the ACL.
- **Healthcheck failing**: Ensure `healthcheck.crt` and `healthcheck.key` exist and are valid.
