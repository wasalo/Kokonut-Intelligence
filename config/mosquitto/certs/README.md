# MQTT Certificates

Provision these files outside Git before starting Mosquitto:

- `ca.crt`
- `server.crt`
- `server.key`
- `healthcheck.crt`
- `healthcheck.key`
- `subscriber.crt`
- `subscriber.key`
- `actuator.crt`
- `actuator.key`

The broker intentionally fails to start when the certificate bundle is absent.
Never commit private keys to this directory.
