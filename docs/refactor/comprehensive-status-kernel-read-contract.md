# Comprehensive Status Kernel read contract

## Route and permission

`GET /operator/api/comprehensive-status/{location_id}` generates the existing
14-section Comprehensive Status report for exactly one location. The operator
must have an active, tenant-qualified `comprehensive_status:read` grant for
that location and an active membership in the grant's organization. The
Gateway validates that grant through the database-signed operator context
before invoking any report generator. No stakeholder class or audience gets
automatic access; each reader must receive an explicit location grant.

Optional `period_start` and `period_end` query parameters accept canonical
`YYYY-MM-DD` dates. The report-read service rejects invalid identifiers, dates,
and reversed ranges before opening its report-data connection. Gateway OIDC
session and route-grant authorization runs separately and may use the operator
authentication database before the service is invoked. There is no network-wide
mode on this route.

## Response behavior

The report retains the existing per-location sections and network rollup
shape, with the rollup containing only the selected location. It does not
create, verify, publish, or snapshot a report. The response is `no-store`, has
a 512 KiB encoded-size limit, and runs in a read-only PostgreSQL transaction
with an eight-second statement timeout and a two-second lock timeout. A failed
section rolls back to its savepoint and returns a bounded section error; other
sections continue when the transaction remains usable.

The 14 section keys are `farm_summary`, `crop_noi`, `environmental`,
`climate_impact`, `financial_sustainability`, `capital_efficiency`,
`holistic_wellbeing`, `community_governance`, `gnh_alignment`,
`training_impact`, `regenerative_outcomes`, `foundational_wellbeing`,
`stakeholder_outcomes`, and `capital_accounting`.

## Source scope

- Location rows and farm, plot, crop, climate, finance, wellbeing, training,
  environmental, and regenerative source reads are called with the exact
  granted location.
- Crop cost allocations are reached only through crop-cycle IDs selected for
  that location.
- Location stakeholder outcomes include only verified or published rows for
  that location. Capability/value-stream relationships from the global view
  are omitted because that view has no location lineage.
- Anti-capture policy counts include only published policies assigned to the
  exact location.
- Active operations protocols are shared reference metadata; the report
  returns only their title, section, and version. Community governance may
  include location-null rows only through its public view, which requires
  published status, evidence maturity at least three, and a non-empty public
  summary.

The location report source has mocked scope regressions and refreshed static
query inventories. Those checks do not prove populated-output parity or
universal database RLS. The route's explicit grant and source predicates are
the current access boundary; broader least-privilege database roles and RLS
remain separate gates.

## HTTP errors

- `400`: malformed location or period input.
- `403`: tenant-qualified grant/session denial or PostgreSQL permission denial.
- `404`: operator OIDC is disabled.
- `413`: generated report exceeds the response bound.
- `503`: bounded report read failure; logs include only the exception class.

The route does not grant public, DAO-wide, guild-wide, or community-wide
access. Owners can grant this resource per location to the operators who need
the report.
