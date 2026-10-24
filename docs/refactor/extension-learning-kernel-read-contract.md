# Extension-learning Kernel read contract

## Scope

The initial Kernel surface consists of these private operator routes:

- `GET /operator/api/extension-learning/{location_id}/modules`
- `GET /operator/api/extension-learning/{location_id}/summary`

It requires an authenticated OIDC operator with an exact
`extension_learning:read` grant for the requested location. The Gateway sets
signed tenant context on the same PostgreSQL connection before the data
queries. The transaction is repeatable-read and read-only, with bounded
statement and lock timeouts; it ends with rollback and connection cleanup.

## Projection

The active, public module catalog is paginated (1–50 rows, offset 0–10,000)
and can be filtered by the source schema's category, difficulty, and content
type values. It returns only the stable module ID, title, category, difficulty,
content type, duration, and language. URLs, descriptions, tags, prerequisites,
and arbitrary metadata remain withheld until content ownership and delivery
behavior are reviewed.

The summary groups location-owned records into four bounded summaries:

- learning enrollments by module category and progress status;
- content deliveries by channel and delivery status;
- assessments by type, with total and scored-record counts;
- peer networks by network type and status, including active membership count.

Every operational query filters the requested location. Peer membership is
counted only when both the network and membership row match that location and
the member is active and has not left. No learner or member names, individual
progress, assessment scores, notes, contact details, delivery errors, device
information, arbitrary metadata, or network descriptions are selected. Counts
remain private to the exact location grant; they are not a public or
cross-location community report.

The route is read-only. It does not enroll participants, deliver content,
record or grade an assessment, manage a peer network, or issue an advisory.

## Verification and rollback

Source tests verify UUID and filter preflight before connection, read-only
transaction setup, context before queries, exact location predicates, peer
membership scope, aggregate-only output, catalog pagination, cleanup, route
policy, no-store headers, and denial when tenant context is unavailable. No
migration is required. Runtime SQL inventory captures the direct SQL sites.

Rollback by removing the route registration and its exact route policy. No
database state is changed. CAP-004 remains prepared until populated parity,
audience/privacy review, live OIDC/browser behavior, database ACL/RLS review,
and MAN-CAP-004 acceptance are complete.
