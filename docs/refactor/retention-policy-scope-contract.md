# Dynamic retention policy scope contract

Updated: 26 October 2026

Retention windows and scope codes remain operator-owned policy data. The
platform does not choose statutory periods, infer a legal basis, activate a
draft, or enable destructive enforcement by default.

## Generic sweeper scope

The generic retention sweep can enforce a configured policy only when the
target table has the standard UUID `id` and `created_at` fields, plus a direct
row column for every non-null scope on the policy:

| Policy scope | Required target column | Predicate |
| --- | --- | --- |
| Location | `location_id` | Exact UUID equality |
| Jurisdiction | `jurisdiction_code` | Exact normalized owner-defined code equality |
| Purpose | `purpose_code` | Exact normalized owner-defined code equality |

The values are passed as SQL parameters. Column names come from this fixed
mapping, never from policy input. If a scope column is absent, the policy is
recorded as skipped before the sweep counts or updates target rows. The
implementation does not infer a jurisdiction from a country name, join an
unconfigured relationship, or interpret free-text purpose labels. Tables that
derive scope through a parent or domain-specific relation need a separately
reviewed resolver before their scoped policies can be enforced.

An active overlapping policy with the same category and entity remains
ambiguous and is skipped. The generic sweep still checks exact entity legal
holds and the feature gate, requires explicit approval metadata and a positive
configured window, and does not execute archive, anonymization, or hard-delete
methods. Notification records and participant-linked governed records remain
on their dedicated archive/disposition paths.

## Acceptance boundary

Focused mocked tests verify that exact configured location/jurisdiction/purpose
codes reach the target query as bound values, and that a missing scope column
skips before candidate counting. They do not connect to PostgreSQL or apply a
retention policy. Actual periods, owner approvals, jurisdiction-to-record
mapping, legal-hold operations, archive workflows, and production enforcement
remain separate gates.
