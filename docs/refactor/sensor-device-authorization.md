# Active-device authorization across HTTP and MQTT

The standalone HTTP receiver now selects secrets only for devices whose registry
status is `active`, matching MQTT's existing policy. Unknown, inactive,
maintenance, decommissioned, or secret-less devices cannot authenticate through
that lookup. No device is registered or reactivated by ingestion.

Both receivers select the active device under `FOR SHARE OF sd` in the reading
transaction. Ordinary updates of that device row, including status, location,
sensor identity, and secret changes, wait until the reading transaction ends.
Both set a five-second transaction-local lock timeout before lookup. Lock
failure follows their existing retryable processing path. This bounds lock
waits, not total query execution or transaction duration.

HTTP signature verification initially reads the secret in a separate connection.
The reading transaction now compares that authenticated secret against the
locked current row before writing. A rotation between authentication and write
rejects the reading without source, health, or outbox writes. The secret is not
added to responses or evidence. Batch readings each repeat this check; a status
or secret change between items can reject later items while earlier items remain
committed. MQTT verifies its signed payload using the locked row's secret.

Revocation is serialized at the reading transaction boundary. A reading already
holding the lock can commit before a waiting operator status update; this does
not retroactively revoke committed evidence. Operator commands and direct SQL
can still reactivate devices according to their existing authority. Domain
registration policy, scoped gateway authorization, and HTTP/MQTT signature
format differences remain separate concerns.

Static lint and diff checks passed. No tests, devices, secret changes, requests,
replays, images, or containers were modified by this slice. Pending runtime
acceptance: inactive-device denial, secret rotation between authentication/write,
concurrent revocation, lock timeout and retry, batch revocation between items,
rollback/release, MQTT operator replay under changed authorization, and absence
of secrets in output. Rebuild both receiver roles before adoption.

Rollback preserves device registry, sensor readings, and outbox history. A prior
HTTP image permits inactive-device lookup again; keep its ingress stopped until
a validated policy is available. Never reactivate devices or weaken signatures
to work around a rejected reading.
