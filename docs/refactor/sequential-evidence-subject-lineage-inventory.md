# CAP-036 sequential-evidence subject-lineage inventory

**Updated:** 20 October 2026  
**Status:** Repository-source inventory complete; populated/archived corpus
inventory remains open.

## Repository source audit

The ordered evidence projection currently recognizes three exact location
lineages in both migrations 460 and 478:

| Subject type | Source relation | Location proof |
| --- | --- | --- |
| `strategy_plan` | `strategy_plan` | `scope_type = 'location'` and exact `scope_id` |
| `threat` | `threat` | exact `location_id` |
| `solution` | `solution`, optionally `solution_link` | exact location origin or explicit location link |

The repository source audit found one sequential-ledger SQL writer at
`services/decision/sequential_evidence.py`. Its API accepts any subject type
and UUID, but no production service calls it. Existing tests exercise
`strategy_plan`, `threat`, and an intentionally unknown `test` subject type.
`services/analytics/customer_value.py` has a similarly named helper, but it
writes to `strategy_customer_value_hypothesis`, not the sequential ledger.
`services/decision/sequential_integration.py` consumes existing hypotheses and
creates a strategy review task only for a `strategy_plan`; it is not another
hypothesis source.

The machine-readable source evidence is
[`cap-036-subject-lineage-source-audit.json`](builds/2026-10-20-recovery/cap-036-subject-lineage-source-audit.json),
generated and checked by
[`check-sequential-subject-lineage.py`](../../scripts/check-sequential-subject-lineage.py).
The checker parses Python callers, inventories direct service SQL inserts, and
keeps the two SQL projection allowlists and their location predicates aligned.
It has no database connection and makes no claims about populated data.

## Populated and archived data gate

Because the generic writer permits arbitrary subject types, the source audit
cannot establish which types exist in the candidate, legacy archive, or another
populated environment. Keep unrecognized types excluded from both projections.
Do not infer tenant ownership from a UUID match or a familiar subject label.

When a populated corpus is available for this gate, run a read-only aggregate
inventory of distinct `decision_hypothesis.subject_type` values and counts.
Do not export hypothesis IDs, statements, evidence, actors, or source IDs. For
each observed type, prove a unique source relation and an exact location scope
path, including whether organization-owned records can be linked to multiple
locations. Only then add a reviewed migration that extends both summary and
timeline projections, with disposable PostgreSQL cases for exact owner scope,
shared links, foreign-location denial, unknown types, ordering, and output
privacy.

## Acceptance state

The repository-source audit closes only code ownership and allowlist drift. CAP-
036 remains prepared while the populated/archived source inventory, reference
output comparison, live ZITADEL browser acceptance, wider runtime ACL/RLS,
recovery, and MAN-CAP-036 owner acceptance remain open.
