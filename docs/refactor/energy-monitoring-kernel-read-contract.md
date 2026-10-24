# Farm energy Kernel read contract

**Status:** prepared source capability; populated-data and manual acceptance are open.

## Route and authorization

`GET /operator/api/energy/{location_id}/summary` is private and requires the
exact OIDC location grant `energy_monitoring:read`. The Gateway verifies the
operator and location grant in PostgreSQL through signed tenant context before
the query. Unknown paths, wrong methods, disabled OIDC, and missing grants fail
closed. The HTTP response is `no-store` and varies on the session cookie.

## Projection

The service opens one read-only, repeatable-read PostgreSQL transaction, sets
statement and lock timeouts, then groups `energy_reading` by reading type,
energy source type, and activity type. Both reading and source rows must match
the requested location. Only `verified` and `approved` readings are included.
The bounded response reports reading count, total kWh, and first/last reading
date per fixed schema grouping.

The response also includes fixed dashboard calculations from verified/approved
readings in the last 30 calendar days, using the same location-bound source
join:

- Consumption, production, and net energy (`production - consumption`).
- Renewable consumption and share. Renewable source types are the legacy set
  `solar`, `wind`, `biogas`, and `biomass`; share is renewable consumption
  divided by total consumption, or zero when total consumption is zero.
- A carbon estimate using the legacy source-type factors (kg CO2e/kWh): grid
  0.45, diesel generator 0.70, solar 0, wind 0, biogas 0.05, biomass 0.10,
  and battery 0. The response names this model
  `legacy_source_type_factors_v1`. This fixed-factor estimate is advisory; it
  is not verified emissions, a lifecycle assessment, or a compliance result.
- A seven-day daily consumption/production trend from the same
  verified/approved source rows.
- A separate 365-day registered-renewables summary for active
  `renewable_energy_source` rows. It aggregates row count, rated capacity,
  annual generation, and recorded carbon-offset fields by the fixed renewable
  type enum. Both registration and related energy-source rows must match the
  requested location. These are stored asset declarations, not independently
  verified production or offsets.
- Active `energy_source` counts and summed rated capacity, grouped by the fixed
  source-type enum. This retains the legacy dashboard's source breakdown,
  includes only rows with `status = 'active'`, and omits source names, IDs, and
  arbitrary metadata. This asset inventory is separate from the renewable
  registration summary above.
- Indicative generation coverage, using the legacy formula
  `min(annual_generation / annual_consumption * 100, 100)`. Its denominator is
  consumption from verified/approved readings during the same 365-day window;
  the legacy implementation also counted `recorded` readings, which the Kernel
  intentionally excludes pending review.
- The latest 12 daily `energy_efficiency_log` rows, filtered to `verified` or
  `approved`. The fixed projection preserves date, period, consumption,
  production, net energy, renewable percentage, and stored carbon intensity.
  Notes, arbitrary metadata, and `cost_per_unit_output` are omitted. These
  historical values were entered or computed by the legacy system; reviewed
  status does not independently validate their formulas or reference data, so
  stored carbon intensity remains advisory.

These calculations restore source-defined formulas under the Kernel's
reviewed-evidence boundary; they do not establish populated-output parity.
The registered-asset summary includes capacity, annual generation, and
recorded offset values, but these stored inputs are not independently verified;
the daily efficiency history preserves reviewed rows without certifying their
calculations. Populated data/reference parity remains open. Cost totals remain withheld
because `energy_reading.total_cost` has no
currency field, so values cannot safely be combined or labeled. The projection
omits source names, equipment/device IDs, notes, and arbitrary metadata. Source
rows are not changed and no schedule/device control is exposed. The console
shows the aggregate only when the session provides the exact location grant;
fields are allowlisted and rendered with `textContent`, with response
location/unit checks, stale request suppression, and explicit advisory labels
for fixed-factor emissions, registered offsets, and generation coverage.

## Verification and rollback

Focused fake-connection and Gateway tests cover exact authorization, denied
route preflight, signed context ordering, location join/filter, verified-state
selection, the 30-day formulas, fixed-factor estimate, seven-day trend,
registered renewable metrics and location joins, bounded latest-12 reviewed
efficiency history with sensitive columns excluded, empty denominators,
response projection, connection cleanup, console grant gating, history
validation, no-store behavior, and inline JavaScript syntax. The 59-test Gateway,
console, energy-domain, and route-policy selection passes; Ruff, Python
compilation, runtime SQL inventory, capability validation, and diff checks
pass. No schema migration is required. Rollback is a source rollback: remove
the calculation queries/fields and their console renderers, then regenerate the
runtime SQL inventory and capability records. No data rollback is necessary.

## Remaining acceptance

This closes code-defined energy calculation and registered-renewables slices
only. Populated farm output and asset-register parity, historical data review,
currency classification, waste management, habitat/pollinator parity, runtime
database ACL/RLS, live ZITADEL/browser behavior, and MAN-CAP-006 remain open.
Do not infer those capabilities from this route.
