# Explicit native public response models

`services/gateway/public_models.py` defines the three native read responses:
PublicMetricSummary, PublicCrispAssessment and PublicLocationSummary. Nested models
define location, metric, metric-count and attestation-count fields. PublicError
documents the existing route-level error envelope. The three route decorators now
declare these response schemas for generated FastAPI OpenAPI documentation.
No route or public-access policy was added.

All models forbid extra fields, so an accidental query expansion cannot silently
add public metadata. Validation errors hide input values in their rendered
messages. Non-finite numeric values are rejected. CRISP status must be published;
location status must be active. Rating/confidence values follow the existing
schema constraints and remain nullable. Computed scores/timestamps can remain
null where canonical published rows permit that. Counts must be nonnegative.

The router explicitly validates successful payloads before constructing
JSONResponse. Merely declaring response_model would not validate a directly
returned Response. The model output then passes through FastAPI's JSON encoder.
Failed response validation follows the existing generic 500 path; it does not
silently remove additional fields or mutate source records. Route-level 400,
404 where applicable, and 500 errors are documented separately; middleware
authorization/rate-limit responses are not fully described by these models.

## Presentation details

UUID fields use the UUID type and serialize in canonical lowercase hyphenated
form. This can normalize alternate valid UUID input spelling previously echoed
by metric/location summary routes. Dates and timestamps retain ISO presentation.
Metric values and CRISP composite scores are JSON numbers normalized through
float fields; aggregate counts are integers, including PostgreSQL numeric SUM
results. These are reporting response types, not exact-decimal financial exports.
Existing keys, public projections, ordering and lifecycle visibility are retained.
The legacy double-encoded location list/detail responses are outside this slice.

## Current status and acceptance

Source changes passed lint/static checks and were subsequently rebuilt/deployed to
the running AMD64 portability API. Its schema gate and HTTP healthcheck passed;
see [the runtime record](portability-runtime.md) for image/rollback identities.
Generated OpenAPI has not been inspected at runtime. No tests or live route requests ran.
Existing deployed summary visibility/selection rules remain
described by [their contract map](public-summary-contracts.md).

Pending acceptance includes nullable published data, numeric conversion,
UUID normalization, unexpected-field rejection, protected lifecycle fields,
generated OpenAPI, error compatibility and SDK/client consumption. No SDK was
regenerated from an unvalidated schema. Cross-field invariants such as count
consistency, period ordering and matching nested IDs still come from the owned
query/database constraints rather than new response-model business rules.

Rollback selects the previous API image with its unchanged schema inventory.
No data migration or lifecycle transition occurs. API model validation does not
replace row/field authorization or evidence review.
