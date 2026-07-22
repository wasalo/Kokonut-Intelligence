"""Implementation parity metadata for generated workflow documentation."""

from .model import WorkflowMetadata


_COMMON_AUDIT = (
    "Lifecycle transitions are recorded with actor and timestamp.",
    "Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.",
)


def _metadata(
    data_sources: tuple[str, ...],
    governance: tuple[str, ...],
    tests: tuple[str, ...],
    audit: tuple[str, ...] = _COMMON_AUDIT,
) -> WorkflowMetadata:
    return WorkflowMetadata(
        governance_controls=governance,
        data_sources=data_sources,
        audit_controls=audit,
        test_refs=tests,
    )


METADATA = {
    "ai_summary": _metadata(
        ("operations | harvest_event, sales_event, crop_cycle, sensor_reading",
         "financial | sales_event, expense_event, noi_snapshot, crop_cycle, crop",
         "environmental | soil_carbon_measurement, species_observation, remote_sensing_observation, weather_observation",
         "combined | operations + financial + environmental sources"),
        ("Agents may create only draft summaries; human roles verify and publish.",
         "Generation requires a verified or published farm registry record.",
         "Eleven catalogue tasks write only ai_summary:draft."),
        ("tests/test_process_architecture.py", "tests/test_agent_tasks.py", "tests/test_workflow_spec_conformance.py"),
        ("Database, Python safety, Directus Zod, and workflow hooks enforce agent draft-only behavior.",
         "The lifecycle transition trigger records every status change."),
    ),
    "budget": _metadata(("budget | budget_line, expense_event, revenue_event",), ("Human approval is required before activation or closure.", "Agents cannot approve or close budgets."), ("tests/test_planning_budget.py", "tests/test_sandop.py")),
    "carbon_retirement": _metadata(("credit_retirement | credit balance, reservation, retirement certificate",), ("Independent human confirmation is required before final retirement or certificate use.", "Reservation and balance mutations must be atomic and idempotent."), ("tests/test_carbon_credits.py", "tests/test_bpm_state_models.py"), ("Idempotency keys and reviewer identity are retained with the retirement ledger.", "Certificate linkage follows confirmed retirement only.")),
    "coordination_alliance": _metadata(("coordination_alliance | participants, reviews, objectives, obligations",), ("Consent, accessibility, minority views, and separation of duties are required for governed coordination.", "No workflow step creates an implicit community commitment."), ("tests/test_coordination.py", "tests/test_coordination_governance.py", "tests/test_coordination_accounting.py", "tests/test_coordination_market_cycles.py")),
    "cooperative_order": _metadata(("cooperative_order | cooperative order and participant commitments",), ("A coordinator verifies member commitments before publication.",), ("tests/test_cooperative.py",)),
    "data_stream_post": _metadata(("data_stream_post | comments, files, EAS anchor metadata",), ("Public visibility requires a verified or published farm registry record.", "Agents cannot verify or publish posts; consent and redaction boundaries remain explicit."), ("tests/test_data_stream.py", "tests/test_workflow_spec_conformance.py"), ("Public publication retains reviewer, consent, redaction, and anchor evidence.",)),
    "emergency_incident": _metadata(("emergency_incident | response actions and remediation evidence",), ("Human verification is required before compliance publication.",), ("tests/test_emergency_response.py",)),
    "event_bus_delivery": _metadata(("event_handler_delivery | leases, attempts, handler results, dead letters",), ("Lease ownership prevents concurrent claims.", "Retries are bounded; replay and disposal require an operator."), ("tests/test_event_bus_durability.py",), ("Lease owner, expiry, attempt number, retry reason, and dead-letter disposition are durable.",)),
    "extension_enrollment": _metadata(("extension_enrollment | module, farmer, progress, assessment",), ("A trainer verifies completion and score before publication.",), ("tests/test_extension.py",)),
    "farm_activity": _metadata(("farm_activity | location, plot, crop cycle, source lineage",), ("Human verification is required before publication or metric use.", "Operational parent context must agree with location, plot, and crop cycle constraints."), ("tests/test_metrics.py", "tests/test_relational_integrity.py"), ("source_system, source_id, and source_raw preserve ingestion provenance.",)),
    "governance_circle": _metadata(("governance_circle | purpose, scope, memberships",), ("Purpose and scope are required before human activation.", "Suspension and retirement require explicit governance rationale."), ("tests/test_governance_links.py", "tests/test_process_architecture.py")),
    "governance_role": _metadata(("governance_role | role definition, accountabilities, circle",), ("A role is independent of its assignee.", "Activation requires an active governance circle and human approval."), ("tests/test_governance_links.py",)),
    "governance_role_assignment": _metadata(("governance_role_assignment | party, role, term, recusal",), ("Assignment requires human approval and a non-recused party.", "Suspension and end states require explicit authority disposition."), ("tests/test_governance_links.py", "tests/test_governance_role_authority.py")),
    "governance_tension": _metadata(("governance_tension | triage owner, resolution, deferral",), ("A triaged or active tension requires an owner.", "Resolution or deferral requires a rationale and evidence."), ("tests/test_governance_tensions.py",)),
    "governance_proposal": _metadata(("governance_proposal | evidence, objections, work item",), ("Human approval requires material harm and consent objections to be resolved.", "Implementation requires a linked work item."), ("tests/test_governance_proposals.py",)),
    "governance_tactical_session": _metadata(("governance_tactical_session | participants and outcomes",), ("Completion requires recorded outcomes; cancellation requires a reason.",), ("tests/test_governance_tactical.py",)),
    "governance_tactical_item": _metadata(("governance_tactical_item | owner, disposition, outcome",), ("An owner and explicit disposition are required before closure.",), ("tests/test_governance_tactical.py",)),
    "governance_circle_link": _metadata(("governance_circle_link | source circle, target circle, mandate",), ("Active links require active circles, an active assignment, a mandate, and human approval.",), ("tests/test_governance_links.py",)),
    "harvest_event": _metadata(("harvest_event | plot, crop cycle, crop, source lineage",), ("Human verification is required before analytics or carbon use.", "Harvest context must agree with the crop cycle ownership path."), ("tests/test_metrics.py", "tests/test_relational_integrity.py")),
    "impact_claim": _metadata(("impact_claim | evidence links, maturity, verifier, methodology",), ("Human verification is required for publication.", "Public claims require evidence maturity; public carbon claims require maturity 6, third-party verification, and methodology."), ("tests/test_ebf_carbon_gates.py", "tests/test_ebf_p0.py", "tests/test_ebf_schema.py")),
    "insurance_claim": _metadata(("insurance_claim | policy, claimant, evidence, adjustment",), ("Human validity review is required before payout processing.",), ("tests/test_digital_finance.py",)),
    "market_order": _metadata(("market_order | buyer, seller, payment, carrier, delivery",), ("Seller confirmation and shipment evidence are required for later states.", "Cancellation remains an explicit governed path."), ("tests/test_marketplace.py", "tests/test_bpm_state_models.py")),
    "metric_value": _metadata(("metric_value | metric definition, period, source records, verification",), ("Computation creates draft values; a human verifies values before public exposure.", "Agents cannot verify or publish metric values."), ("tests/test_metrics.py", "tests/test_bpm_state_models.py", "tests/test_evidence_lineage_integrity.py"), ("Formula version, source lineage, reviewer, and verification notes are retained.",)),
    "objective": _metadata(("objective | KPI targets, reviews, corrective work items",), ("Human review determines objective health.", "Off-track objectives require a corrective work item; reopening requires a new review."), ("tests/test_objective_performance.py",)),
    "pest_intervention": _metadata(("pest_intervention | scouting, IPM method, pesticide and resistance records",), ("Human IPM-compliance verification is required before publication.", "Published intervention data feeds resistance and compliance tracking."), ("tests/test_pest_management.py",)),
    "project": _metadata(("project | program, manager, milestones, completion evidence",), ("Managers control start, hold, resume, completion, and cancellation.", "Hold and cancellation reasons are explicit."), ("tests/test_program_portfolio.py",)),
    "report_snapshot": _metadata(("report_snapshot | report generator inputs, evidence, uncertainty context",), ("Human verification is required before publication.", "Public-interest context, uncertainty, and negative findings remain attached to the snapshot."), ("tests/test_report_governance.py", "tests/test_process_architecture.py")),
    "stakeholder_feedback": _metadata(("stakeholder_feedback | consent, review, public summary, outcomes",), ("Feedback is private by default.", "Public feedback requires explicit consent, a non-empty public summary, published status, and the minimum review period."), ("tests/test_stakeholder_dod_closure.py", "tests/test_cids_export.py", "tests/test_stakeholder_consent.py"), ("Consent scope, review period, redaction, reviewer, and publication decision are retained.",)),
    "traceability_batch": _metadata(("produce_batch | custody, quality, certification, provenance, food safety",), ("Human custody-chain verification is required before provenance publication.",), ("tests/test_traceability.py",)),
    "work_item": _metadata(("work_item | assignment, claims, events, responsibilities, SLA",), ("A work item requires an assignee and exactly one accountable responsibility before start.", "Claims, leases, escalation, and completion are durable."), ("tests/test_management_workflow.py", "tests/test_responsibility_assignment.py"), ("Assignment, blocker, completion, cancellation, and SLA timestamps are recorded.",)),
}


def metadata_for(spec_id: str) -> WorkflowMetadata:
    """Return parity metadata for a registered workflow, if documented."""

    return METADATA.get(spec_id, WorkflowMetadata())
