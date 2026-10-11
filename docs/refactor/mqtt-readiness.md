# MQTT subscriber readiness

The optional subscriber writes a local readiness snapshot when MQTT_STATE_FILE
is selected. The candidate overlay chooses /tmp/kokonut-mqtt-state.json and
replaces the previously disabled image healthcheck with a local state check.
Legacy callers without this setting perform no state-file writes.

Startup clears state before configuration/client setup. Successful CONNACK marks
connected but not subscribed. Only the expected subscription message ID and
granted SUBACK establish subscribed state. Disconnect clears both flags and
the expected message ID; reconnect requests and confirms subscription again.
Shutdown clears state before disconnecting. Operator replay constructs a
subscriber without starting its transport, so its cleanup does not overwrite
the live subscriber's readiness file.

`services/core/mqtt_state.py` writes via a private temporary file, flush/fsync,
and atomic replacement. The snapshot contains only version, PID, connected,
and subscribed flags. No topic, client identifier, credentials, or payload is
included. The check rejects symlinks, nonregular files, foreign ownership,
nonprivate permissions, oversized snapshots, invalid process identity, dead
processes, and either false connection flag. It runs as the image's non-root
user and uses shared CLI JSON/error helpers.

## Meaning and limits

Readiness means the process is present and its most recently observed broker
connection/subscription state is positive. It does not establish receipt schema
availability, successful ingestion, fresh sensor data, or network-loop progress.
No timed heartbeat is claimed. A hung process can retain positive flags until
disconnect is observed; a future watchdog must account for that. Docker marking
the service unhealthy does not itself restart it. Failed callbacks/process exits
continue to use the selected restart policy.

The readiness command does not contact the broker, load Paho, or run a database
query. Its shared CLI infrastructure still loads application configuration and
the database library. Do not treat it as a standalone dependency-free command.

## Pending acceptance and rollout

Validate startup clearing, expected versus unknown SUBACK IDs, granted/denied
QoS, connect/disconnect/reconnect, stopped/dead process checks, concurrent file
reads during replacement, permissions and symlink rejection, operator replay
isolation, and real container health transitions. Runtime tests and subscriber
starts were not performed. Static lint, provider/dependency gates, Compose
configuration, and diff checks passed.

The [updated MQTT image](mqtt-overlay.md#updated-subscriber-build) includes this
source and has not been deployed. Migration 372 remains required for
the updated QoS 1 receipt path and is still unapplied. No broker or device state
changed. Rollback removes MQTT_STATE_FILE and restores the disabled subscriber
healthcheck while retaining transport/data recovery state.
