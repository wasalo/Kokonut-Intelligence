# Optional Kernel MQTT ingestion

`docker-compose.kernel-mqtt.yml` adds a digest-pinned Mosquitto broker and an
independent subscriber. The default app still disables MQTT; selecting the
overlay does not enable actuator publication. HTTP/CSV ingestion remains
available independently. Broker persistence uses the separate
`kernel-mqtt-data` volume, with no legacy volume reuse or host port publication.

The Dockerfile's optional `mqtt` target adds requirements/mqtt.txt (Paho) to the
Kernel base and runs the existing subscriber as UID 10001. The default image
still excludes Paho. The transport retains TLS client validation, topic ACLs,
payload HMAC validation, registered-device lookup, PostgreSQL writes, and the
existing ClickHouse projection enqueue path. ClickHouse is disabled in this
subscriber image; projections can remain pending for later delivery.

## Provisioning and profile selection

Provision settings through the existing encrypted secret workflow:

- `KOKONUT_MQTT_CERTS_DIR`: broker-readable directory containing ca.crt,
  server.crt/server.key, and healthcheck.crt/healthcheck.key.
- `KOKONUT_MQTT_SUBSCRIBER_CERTS_DIR`: separate app-readable directory containing
  only ca.crt and subscriber.crt/subscriber.key. Do not expose broker private
  keys to the subscriber.
- `KOKONUT_MQTT_PASSWORD_FILE`: existing Mosquitto-format password file, mounted
  read-only at the configured /mosquitto/data/passwd path.
- `MQTT_USERNAME` and `MQTT_PASSWORD`: subscriber credentials required by the
  existing client. Review their relationship with certificate identity and the
  configured broker authentication mode during acceptance.
- `MQTT_CLIENT_ID`: stable unique subscriber identity for the overlay's opt-in
  [QoS 1 delivery mode](mqtt-delivery.md); avoid simultaneous consumer ID reuse.

Bind mounts reject nonexistent host paths rather than creating empty
directories. Provision private-key read permissions for the container users;
do not make them broadly readable to work around a mount error. Server
certificate hostname validation must cover mosquitto for subscriber access and
localhost for the broker health probe. The existing ACL recognizes subscriber
certificate identity sensor-ingestion and healthcheck identity healthcheck;
devices still need individually provisioned exact topic permissions.

After provisioning, combine the standalone candidate with this overlay:

```sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-mqtt.yml config --quiet
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-mqtt.yml build mqtt-subscriber
```

Configuration was validated with placeholder settings without printing resolved
secrets. A subscriber image was subsequently built as recorded below. No
certificates, password files, devices, or broker volumes were created, and no
broker/subscriber was started. External field devices
cannot reach this private overlay until an explicit ingress arrangement is
reviewed. No plaintext listener or host publishing override is introduced here.

## Startup, health, and pending acceptance

Missing subscriber credentials or TLS initialization failures now raise instead
of returning successfully. The command always calls stop in finally; database
cleanup runs even if disconnect fails. Disabled-provider startup remains a
deliberate no-op. Connection-rejection callbacks currently log failures; robust
connection/subscription readiness remains an acceptance gate.

The broker health probe waits for one authenticated $SYS/broker/uptime message,
with twelve-second client and fifteen-second Docker timeouts. The subscriber
explicitly disables the inherited API image healthcheck. This is not a sensor
readiness assertion; durable heartbeat/subscription reporting is not yet added.

The subsequent [readiness change](mqtt-readiness.md) adds a private local
connection/subscription snapshot and overlay healthcheck in source. A timed
network-loop watchdog remains outside that readiness contract. The rebuilt image
below includes this change; the Compose overlay supplies its readiness probe.

### First subscriber build

The mqtt target built successfully on 10 October 2026 as
`kokonut-kernel-candidate-mqtt:local`. Local image inspection reports identity
`sha256:8ba88a32c66fbd0f0b07653a595f52b56a91a8c8ca8a86cc874ec5d0cae9dbcd`,
linux/amd64, 475,916,450 bytes (approximately 454 MiB), configured user appuser.
Paho 2.1.0 installed within the inherited requirement range. The image captures
uncommitted source at build time and has not been deployed or release-tagged.
Build success does not prove subscriber import/startup, broker connection,
authorization, ingestion durability, or ARM64 compatibility.

Source review identified a durability gap before adoption: `_insert_ch` catches
projection enqueue exceptions even when called within the source-row database
transaction, while `_on_message` only logs processing errors. Correct failure
propagation and transaction rollback/reuse before certifying live ingestion.
An ingestion success log is not sufficient evidence of an atomic source/outbox
commit on that path. The subsequent [transaction correction](mqtt-transactions.md)
propagates enqueue errors and resets message transactions in source. The first
subscriber image predates it; the rebuilt image below includes the correction.
Validate failure paths before adoption.

### Updated subscriber build

On 10 October 2026 the same local tag was rebuilt with transaction cleanup,
QoS 1 delivery, durable receipts/operator recovery, and subscription readiness.
Docker image inspection reports identity
`sha256:ae2f8fe07d873018065177b5d9dc706130d179180f70641b37888263b6d9a14e`,
linux/amd64, 475,967,232 bytes (approximately 454 MiB), user appuser.
The build installed Paho 2.1.0. This replaces the first image under the mutable
local tag and captures uncommitted source; it is not a release artifact.
The active local Kernel candidate database now includes migrations through 379,
including migration 372 for the QoS 1 receipt path; migration 371 is also applied
there. This is separate from legacy/production and does not mean the MQTT broker
or subscriber was deployed. No containers were started or replaced for this
build, and transport, ingestion, recovery, and ARM64 checks remain pending.

Pending checks: target build on ARM64, mTLS identity/hostname validation,
ACL denials, accepted and bad-HMAC payloads, device/location authorization,
duplicate delivery, PostgreSQL and deferred projection behavior, reconnect,
credential/certificate failures, signal cleanup, and broker persistence/recovery.
Preserve actuator human approval and HMAC rules when adding command publication
later. Runtime tests were not added or run. Static lint, provider/dependency
gates, Compose parsing, and diff checks passed.

The image digests above are historical local builds and predate subsequent
source changes; rebuild from the reviewed checkout before enabling the overlay.
The active candidate schema is current, but the broker/subscriber and MQTT
profile have not been started. The legacy stack remains separately preserved.

## Rollback

Stop/remove only mqtt-subscriber and mosquitto, then omit this overlay. Omitting
the overlay alone does not stop already-running orphan containers. Retain broker
data and externally provisioned certificates/passwords for recovery; do not
delete the named volume. No migrations, scheduler ownership, or device records
changed during this implementation.
