# Opt-in MQTT QoS 1 delivery

The subscriber supports `MQTT_DELIVERY_MODE=legacy|qos1`. Legacy remains the
default for existing callers. The candidate overlay explicitly selects qos1 and
requires `MQTT_CLIENT_ID`, a stable unique identity for this logical consumer.
Only one running instance may use that identity. Certificate identity and client
ID serve different purposes; the existing certificate/ACL policy remains.

The lazy MQTT factory accepts explicit client_id, clean_session, and manual_ack
options while preserving actuator defaults. The selected subscriber uses MQTT
3.1.1, clean_session=False, manual_ack=True, and requests subscription QoS 1.
Connection rejection, a failed subscription request, or SUBACK without the
requested QoS fail startup/processing instead of appearing subscribed. These
settings use the documented
[Paho client and manual acknowledgement API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html).

## Processing outcomes

- Publishers must send at QoS 1 or higher; QoS 0 deliveries are rejected and
  logged. A QoS 1 subscription caps delivered QoS at 1.
- A successful reading is acknowledged after source/outbox commit and message
  transaction cleanup. Duplicate readings retain the existing duplicate key
  path and can be acknowledged after processing.
- Processing/database/acknowledgement exceptions propagate out of the callback
  without successful acknowledgement. The command exits through its cleanup
  path; the candidate restart policy can reconnect the same broker session.
- Normal-return rejections are deliberately acknowledged to avoid repeatedly
  processing terminal invalid input. Invalid UTF-8/JSON, nonobject payloads,
  unsupported topics, invalid signatures, and malformed timestamps now follow
  rejection paths. QoS 1 readings require a timestamp so redelivery does not
  generate a fresh acquisition time and defeat the existing duplicate key.

No device auto-registration, anonymous broker access, or actuator permission is
introduced. Disabled MQTT exits before delivery-setting validation or Paho
loading. Legacy client creation and automatic acknowledgement defaults remain.

## Recovery limits and remaining gates

This is not an exactly-once or fully certified delivery guarantee. Broker
persistence, queue limits, stable client identity, TLS/ACL setup, publisher QoS,
and session recovery all affect redelivery. Device timestamps still need the
existing validation/canonicalization contract. Terminal rejection logs are not
a durable dead-letter inbox. There is no bounded subscriber retry/disposition
policy yet; repeated database failures can trigger repeated container restarts.
The subsequent [durable recovery contract](mqtt-recovery.md) adds recorded
outcomes, five processing attempts, and explicit replay/disposal in source.
Migration and runtime checks remain prerequisites for certification; failures
that prevent evidence persistence still need an infrastructure recovery policy.
Subscription health reporting is implemented in [source](mqtt-readiness.md);
runtime validation and a timed network-loop watchdog remain pending.

Rehearse crash before commit, after commit before ACK, failed ACK, duplicate
redelivery, broker/subscriber restart, persistent-session reconnection, denied
SUBACK, invalid payload disposal, QoS 0 publishers, ID collisions, timestamp
validation, and disabled-provider behavior. Check current Paho session limits
against the selected version. No runtime tests, subscriptions, broker starts,
or device messages were performed. Static lint, provider/dependency gates,
Compose configuration, and diff checks passed.

The [updated subscriber image](mqtt-overlay.md#updated-subscriber-build) includes
these changes and has not been deployed. Rollback
the opt-in delivery mode only while ingestion is stopped; inspect queued broker
messages before changing clean-session behavior or client ID, since that can
discard recoverable deliveries. Retain broker state and device credentials.
