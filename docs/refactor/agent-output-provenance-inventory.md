# Agent output provenance inventory

Updated: 25 October 2026

This source inventory records what the current signed agent workers disclose
about the database views and keys used to produce their outputs. It is not a
runtime execution log, populated-data parity result, or complete provenance
snapshot. Every worker-backed database read is expected to use a
repeatable-read, read-only transaction after installing the corresponding
signed tenant context and selecting its restricted reader role.

| Output path | Output provenance | Scope and privacy boundary | Evidence |
| --- | --- | --- | --- |
| Registered synthesis workers (12 tasks) | `source_tables` and `source_references` identify the registered view, bounded row count, sampled record IDs, and truncation state. Empty views remain present with zero rows and no IDs. | Exact location scope is captured in the same source transaction as synthesis. Network-wide inputs and sensitive or subject-level sources are explicitly mapped as exclusions rather than being treated as farm rows. | [source exclusions](builds/2026-10-25-recovery/cap-038-source-reference-exclusions.json), [deterministic coverage](builds/2026-10-25-recovery/cap-038-deterministic-source-coverage.json), [empty views](builds/2026-10-25-recovery/cap-038-empty-synthesis-source-references.json) |
| Deterministic AI summaries | Fixed `source_tables` and one matching `source_references` entry per source. | Operations, financial, environmental, and combined outputs share a repeatable-read location snapshot; missing and extra source mappings fail closed. | [deterministic coverage](builds/2026-10-25-recovery/cap-038-deterministic-source-coverage.json) |
| AI-summary review list | Every row names `kokonut_agent_source.ai_summary_list` and the normalized location; the structured result repeats that query scope beside `items`, including for an empty list. | Up to twenty location-scoped rows; preview remains as before. The legacy list-returning helper remains available. | [inspection scope](builds/2026-10-25-recovery/cap-038-summary-inspection-source-scope.json), [empty-result scope](builds/2026-10-25-recovery/cap-038-summary-list-empty-source-scope.json) |
| AI-summary digest | Metadata names `kokonut_agent_source.ai_summary_digest`, the normalized summary ID, and location ID; a structured not-found result retains the same query scope beside a null `item`. | Returns summary type/status, model version, content hash, and content length for a match; never returns summary content. The legacy helper still returns `None` for no match. | [inspection scope](builds/2026-10-25-recovery/cap-038-summary-inspection-source-scope.json), [empty-result scope](builds/2026-10-25-recovery/cap-038-summary-list-empty-source-scope.json) |
| EBF evidence-gap analysis | Names `kokonut_agent_source.v_ebf_evidence_gap_summary` and normalized scorecard/location query scope. | The view returns aggregate evidence-gap data. The output does not claim identities or snapshots of underlying evidence records. | [EBF scope](builds/2026-10-25-recovery/cap-038-ebf-output-source-scope.json) |
| CIDS Essential export | The shared profile contract pins CIDS v3.2.0 Essential. The result names six signed input views and normalized location. Every JSON-LD node carries a sorted `kokonut:sourceViews` union and complete `kokonut:propertySourceViews` map. The signed worker adds a separate `source_scope.property_source_records` sidecar that maps each node property to sampled projection-row IDs, with a 50-row per-property cap, count, and truncation flag. The task validator rejects incomplete node/property maps, wrong-view references, malformed IDs, inconsistent counts, and noncanonical ordering. A canonical SHA-256 digest binds the returned JSON-LD document to that sidecar. | Row identifiers remain outside the JSON-LD graph and carry no source values. The sidecar and digest are returned only with the exact-location read-only worker result; the digest is neither a signature nor a retained content snapshot or populated-output parity result. Worker views still enforce publication, verification, and consent filters. | [CIDS scope](builds/2026-10-25-recovery/cap-038-cids-output-source-scope.json), [node attribution](builds/2026-10-25-recovery/cap-038-cids-node-source-attribution.json), [property attribution](builds/2026-10-25-recovery/cap-038-cids-property-source-attribution.json), [property-row lineage](builds/2026-10-25-recovery/cap-038-cids-property-row-lineage.json), [artifact digest](builds/2026-10-25-recovery/cap-038-cids-artifact-digest.json), [pinned profile](builds/2026-10-25-recovery/cap-038-cids-profile-contract.json), [output contract](builds/2026-10-25-recovery/cap-038-cids-provenance-output-contract.json) |
| Delphi facilitation summary | Names `kokonut_agent_source.delphi_live_summary` and normalized study/location scope. | The signed summary projection applies consent and minimum-panel privacy thresholds. It does not expose participant identity, free text, or participant-level source rows. | [Delphi scope](builds/2026-10-25-recovery/cap-038-delphi-output-source-scope.json) |

## Remaining limits

- This inventory covers the current database-backed agent worker paths; it
  does not prove that every legacy command, provider task, or background job
  outside these workers has an equivalent source contract.
- View/query scope does not mean content snapshot, complete lineage from each
  output field to an input row, or populated legacy-output parity.
- Aggregate EBF and Delphi privacy projections intentionally do not disclose
  participant/evidence row identifiers. CIDS now maps each output property to
  contributing source views, but does not map values to exact input rows or
  capture a source-content snapshot.
- The source contracts and tests do not prove production credential/grant
  provisioning, live OIDC, worker-process recovery, or MAN-CAP-038 acceptance.

The [agent attribution inventory](agent-task-attribution-inventory.md) tracks
operator identity and execution boundaries separately from data provenance.
