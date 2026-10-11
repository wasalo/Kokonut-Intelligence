# Bounded standalone HTTP sensor requests

`http_sensor_limits.SensorBodyLimit` is an ASGI middleware installed before
standalone receiver routes parse JSON. POST requests accept at most 10,240
received body bytes, or 262,144 bytes for paths ending in `/readings/batch`.
Actual bytes are counted regardless of Content-Length or chunked delivery.
A bounded byte buffer avoids accumulating a Python object per received chunk.
Oversize input returns 413; exceeding the ten-second total receive budget
returns 408. Disconnect stops processing without credential/database lookup.

The middleware replays the exact received bytes to the downstream app. HMAC
verification continues to sign the original request body; no JSON normalization
or evidence rewriting is introduced. Non-HTTP and non-POST requests pass through.
The byte limit bounds accepted body memory, not total server/process concurrency,
headers, or an individual oversized chunk allocated by the server before receipt.
The timeout covers receiving the body, not SQL execution or complete responses.

Pydantic input bounds now require 1–100 batch readings, a 1–255 character device
ID, units up to 64 characters, timestamps up to 128, and quality up to 32.
Model violations use FastAPI's validation response. These are explicit changes
to the standalone receiver's accepted input contract; review device clients
before rollout. Per-item batch commits and retry outcomes remain unchanged.
No gateway sensor route, proxy exposure, broker dependency, or device bypass
was added.

Static lint and diff checks passed. No tests, HTTP requests, image builds,
services, or persisted readings were created. Runtime acceptance remains:
boundary-sized single/batch requests, oversized and chunked requests, slow
upload/disconnect, exact-body HMAC preservation, invalid model dimensions,
empty/oversized batches, missing/incorrect Content-Length, and concurrent load.
The running image predates this middleware and requires rebuilding before use.

Rollback restores the previous receiver input contract using a reviewed image
while retaining readings and outbox evidence. Keep the standalone receiver
private until its ingress, authentication, device policy, and transport parity
gates pass. Limits do not certify public deployment readiness.
