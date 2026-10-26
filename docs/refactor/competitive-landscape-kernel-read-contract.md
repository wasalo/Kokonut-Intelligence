# Competitive landscape Kernel read contract

CAP-029's first native Kernel slice is a bounded location summary at
`GET /operator/api/competitive-landscape/{location_id}/summaries`. It requires
an authenticated operator, a current `competitive_landscape:read` grant for the
requested location, and signed transaction-bound tenant context. PostgreSQL
rechecks the grant and requested location before returning data.

The projection includes landscape metadata and aggregate counts for actors,
high/critical threats, Five Forces observations, worsening pressure, signals,
unreviewed critical signals, verified advantages, and verified outcomes. It
includes the average force pressure and verified defensibility, but not
individual values or records. Organization landscapes, landscapes whose linked
strategy plan belongs to another scope, and other locations are excluded.

The response omits canonical party identity, actor names and descriptions,
signal content/source references, evidence, rationales, advantage statements,
individual outcome measurements/comparators, and party attribution. A
dedicated non-login database role owns the bounded security-definer function;
runtime and Directus receive no direct competitive table reads, and Directus
cannot execute the function. The role's table reads are limited to the
projection dependencies and tenant grant validation tables.

This surface is a first-party summary, not CAP-029 parity. It does not create or
edit landscapes, track changes over time, expose the report/dashboard surface,
or replace the existing competitive analytics and advantage workflows. Full
behavior parity, populated fixture comparison, live OIDC/browser behavior,
universal tenant ACL/RLS, and MAN-CAP-029 owner acceptance remain open.

Migration 453 has only been applied and replayed against disposable PostgreSQL
16 by `scripts/check-competitive-landscape-disposable.py`. Candidate and
legacy databases are not included in this acceptance and require a separate
rollout gate.
