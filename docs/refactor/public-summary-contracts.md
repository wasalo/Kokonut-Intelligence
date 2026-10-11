# Governed public CRISP and location summaries

Repository inspection found that the existing gateway imported `CRISPEngine`
from `services.crisp` and `PortfolioSummary` from `services.analytics.portfolio`.
Neither class exists in those modules. This slice replaces those unresolved
calls with explicit read services; it does not claim response parity with a
working former implementation or replace internal portfolio/scoring capabilities.

| Route | Native read | Visibility | Missing/excluded result |
| --- | --- | --- | --- |
| GET /api/crisp/{location_id} | latest persisted published CRISP assessment | published assessment joined to v_public_farm_summary | 404 |
| GET /api/analytics/{location_id}/summary | location projection plus aggregate metrics/attestations | existing governed public views | 404 |

Both existing route policies remain explicitly public/read. Malformed UUIDs return
400 before querying. Reads run in the thread pool with a 3-second connection timeout,
5-second statement timeout and 2-second lock timeout. Shared connection contexts
own cursor/transaction cleanup. Both transactions are read-only; the location
roll-up uses repeatable-read for a consistent snapshot across its queries.
These operation bounds are not an end-to-end request deadline.

## CRISP response

The flat response contains assessment_id, location_id, period_start, period_end,
methodology_version, composite_score, rating, confidence_level,
evidence_maturity_level, score_computed_at and status. Selection orders period_end
descending, then score_computed_at descending with nulls last, then assessment ID,
and returns at most one row. Draft, submitted, verified-only and rejected
assessments are excluded. Active/public location visibility still requires a
verified/published farm registry record through the existing view.

Private dimension details, reviewer notes, metadata, source_raw, author identities,
and financial inputs are not selected. No scorer runs and no rating is persisted,
verified, or published by GET. Existing CRISP CLI computation/review capabilities
remain independent. Publication/field policy and client compatibility still need
acceptance before this is treated as a production public reporting contract.

## Location roll-up response

The response contains summary_type=public_location_summary, location_id, location,
metrics and attestations. Location fields are id/name/country/region/status.
Metrics contains the distinct visible metric-key count and latest computed
timestamp. Attestations contains total_attestations, published_count and the
latest attestation timestamp from v_public_attestation_summary. Total includes
verified and published records; that view currently includes Celo attestations
only. It is not an all-chain verification statement or a financial/impact total.
Empty eligible metric/attestation sets yield zero counts and null timestamps.

No private financial aggregates, raw evidence, attestation payloads, or precise
geometry are exposed. FastAPI's JSON encoder handles UUID/date/datetime/Decimal
values. Numeric presentation follows the framework's number conversion rather
than an exact-decimal export contract. Domain counts do not certify evidence
quality, attestation validity, or ecological outcomes.

## Status, acceptance and rollback

Source changes passed lint, provider boundaries, dependency alignment and diff
checks. The subsequent AMD64 portability API build/deployment completed and Docker
reported it healthy; see [the runtime record](portability-runtime.md) for exact
image identities. The database and worker instances were preserved. No test suites,
live summary requests, fixture writes, scoring or lifecycle transitions ran.
Acceptance still needs response/client contracts, active/public visibility,
published-only CRISP selection, ordering, empty results, UUID errors, database
failure cleanup, concurrent reads, and authorization regression coverage.

Internal portfolio_theme_summary and ebf_portfolio_summary remain available in
their original module. Mapping additional portfolio capabilities into the API
requires explicit field/row/consent contracts. No generic raw-table endpoint was
introduced. Rollback selects the prior API image with the same schema; note that
these two prior routes contain the unresolved imports described above. No schema
or data rollback is required, and existing Directus metadata remains retained.
