"""Shared context and serialization helpers for report generators."""

import hashlib
from typing import Optional

import psycopg2
import psycopg2.extras

from ...common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_pg():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)


# ---------------------------------------------------------------------------
# Shared serialization + context helpers
# ---------------------------------------------------------------------------


def _serialize_value(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (bytes, memoryview)):
        return hashlib.sha256(bytes(obj)).hexdigest()[:16]
    return obj


def _serialize_rows(rows: list[dict]) -> list[dict]:
    return [{k: _serialize_value(v) for k, v in row.items()} for row in rows]


def _looks_like_uuid(value: str) -> bool:
    """Best-effort check that a value is a single UUID (not 'all' or a list)."""
    if not value or not isinstance(value, str):
        return False
    if "," in value:
        return False
    try:
        import uuid

        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def build_negative_findings(context: dict) -> list[dict]:
    """Normalize adverse and unresolved signals without claiming causation."""
    findings = []
    for gap in context.get("evidence_gaps", []):
        if gap.get("public_claims_below_threshold", 0):
            findings.append(
                {
                    "code": "CLAIM_BELOW_PUBLICATION_THRESHOLD",
                    "system": "impact_claim",
                    "severity": "warning",
                    "summary": "Public claims lack the required evidence maturity.",
                    "basis": {"affected_count": gap["public_claims_below_threshold"]},
                    "review_prompt": "Review claim maturity and evidence before publication.",
                }
            )
        if gap.get("carbon_publication_gaps", 0):
            findings.append(
                {
                    "code": "CARBON_VERIFICATION_GAP",
                    "system": "impact_claim",
                    "severity": "high",
                    "summary": "Carbon claims lack publication requirements.",
                    "basis": {"affected_count": gap["carbon_publication_gaps"]},
                    "review_prompt": "Confirm Level 6 evidence, methodology, and external verifier.",
                }
            )
        if gap.get("missing_evidence_links", 0):
            findings.append(
                {
                    "code": "MISSING_EVIDENCE_POINTER",
                    "system": "impact_claim",
                    "severity": "warning",
                    "summary": "Claims are missing evidence pointers.",
                    "basis": {"affected_count": gap["missing_evidence_links"]},
                    "review_prompt": "Attach a governed CID, hash, or attestation reference.",
                }
            )

    forecast = context.get("forecast_performance") or {}
    if forecast.get("overprediction_count", 0):
        findings.append(
            {
                "code": "FORECAST_OVERPREDICTION",
                "system": "forecast_validation",
                "severity": "warning",
                "summary": "Verified outcomes were below forecasts for some evaluated records.",
                "basis": forecast,
                "review_prompt": "Review assumptions and calibration before reusing these projections.",
            }
        )
    milestones = context.get("backcast_milestone_health") or {}
    if milestones.get("blocked_count", 0):
        findings.append(
            {
                "code": "BACKCAST_BLOCKED_MILESTONES",
                "system": "backcasting",
                "severity": "warning",
                "summary": "Backcast milestones are blocked.",
                "basis": milestones,
                "review_prompt": "Review dependencies, resources, and accountable owners.",
            }
        )
    if milestones.get("overdue_count", 0):
        findings.append(
            {
                "code": "BACKCAST_OVERDUE_MILESTONES",
                "system": "backcasting",
                "severity": "warning",
                "summary": "Backcast milestones are past their target dates.",
                "basis": milestones,
                "review_prompt": "Confirm whether target dates and plans remain authoritative.",
            }
        )
    assumptions = context.get("unresolved_assumption_challenges") or {}
    if assumptions.get("pending_count", 0):
        findings.append(
            {
                "code": "BACKCAST_PENDING_ASSUMPTIONS",
                "system": "backcasting",
                "severity": "warning",
                "summary": "Assumption challenges remain unresolved.",
                "basis": assumptions,
                "review_prompt": "Resolve challenged assumptions before adopting dependent milestones.",
            }
        )
    delphi = context.get("delphi_dissent") or {}
    if delphi.get("non_consensus_count", 0):
        findings.append(
            {
                "code": "DELPHI_NON_CONSENSUS",
                "system": "delphi",
                "severity": "notice",
                "summary": "Consensus criteria were not met for some reviewed items.",
                "basis": delphi,
                "review_prompt": "Preserve anonymized minority views and disclose non-consensus.",
            }
        )
    crisp = context.get("crisp_risk") or {}
    if crisp.get("composite_score") is not None and float(crisp["composite_score"]) >= 69:
        findings.append(
            {
                "code": "CRISP_HIGH_RISK",
                "system": "crisp",
                "severity": "high",
                "summary": "The latest published assessment indicates elevated modeled risk.",
                "basis": crisp,
                "review_prompt": "Review the highest-risk dimensions and active mitigations.",
            }
        )
    if crisp and crisp.get("confidence_level") in {"low", "insufficient_evidence"}:
        findings.append(
            {
                "code": "CRISP_INSUFFICIENT_EVIDENCE",
                "system": "crisp",
                "severity": "warning",
                "summary": "The latest published risk assessment has limited evidence confidence.",
                "basis": crisp,
                "review_prompt": "Treat risk severity and evidence uncertainty as separate concerns.",
            }
        )
    calibration = context.get("prediction_calibration") or {}
    if calibration.get("failed_scope_count", 0):
        findings.append(
            {
                "code": "PREDICTION_CALIBRATION_FAILED",
                "system": "prediction_ledger",
                "severity": "high",
                "summary": "One or more model scopes materially failed calibration policy.",
                "basis": calibration,
                "review_prompt": "Do not publish affected forecasts without recalibration and independent review.",
            }
        )
    if calibration.get("insufficient_scope_count", 0):
        findings.append(
            {
                "code": "PREDICTION_CALIBRATION_INSUFFICIENT",
                "system": "prediction_ledger",
                "severity": "warning",
                "summary": "Some model scopes lack enough resolved outcomes for calibration.",
                "basis": calibration,
                "review_prompt": "Disclose limited calibration evidence and continue outcome collection.",
            }
        )
    return findings


def fetch_public_interest_context(conn, location_id: str) -> dict:
    """Fetch public-interest context attached to every Green Paper report."""
    # Network-level reports (e.g. state_of_kokonut with --all, dao_proposal_history)
    # pass a non-UUID scope. Skip the location-scoped queries in that case.
    if not location_id or not _looks_like_uuid(location_id):
        return {}

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_stakeholder_feedback_summary
        WHERE location_id = %s
        ORDER BY feedback_date DESC, id
        LIMIT 10
        """,
        (location_id,),
    )
    public_feedback = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT claim_category, claim_type, claim_text, claim_value, claim_unit,
               evidence_maturity, evidence_maturity_label, confidence_level,
               methodology_ref, external_verifier, attestation_uid
        FROM v_public_impact_claim_summary
        WHERE location_id = %s
        ORDER BY claim_date DESC, id
        LIMIT 10
        """,
        (location_id,),
    )
    public_claims = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT claim_category, claim_type, status, public_claim,
               evidence_maturity, COUNT(*) AS claim_count,
               COUNT(*) FILTER (
                   WHERE public_claim = TRUE AND evidence_maturity < 4
               ) AS public_claims_below_threshold,
               COUNT(*) FILTER (
                   WHERE public_claim = TRUE
                     AND claim_category = 'carbon'
                     AND (
                       evidence_maturity < 6
                       OR external_verifier IS NULL
                       OR methodology_ref IS NULL
                     )
               ) AS carbon_publication_gaps,
               COUNT(*) FILTER (
                   WHERE evidence_cid IS NULL
                     AND evidence_hash IS NULL
                     AND attestation_uid IS NULL
               ) AS missing_evidence_links
        FROM impact_claim
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY claim_category, claim_type, status, public_claim, evidence_maturity
        ORDER BY carbon_publication_gaps DESC, public_claims_below_threshold DESC,
                 missing_evidence_links DESC, claim_count DESC
        """,
        (location_id,),
    )
    evidence_gaps = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, status,
               consent_given, consent_scope, is_public, evidence_maturity,
               COUNT(*) AS feedback_count,
               COUNT(*) FILTER (WHERE consent_given = FALSE) AS private_or_no_consent_count,
               COUNT(*) FILTER (WHERE harms_or_unintended_consequences IS NOT NULL) AS harm_or_unintended_consequence_count
        FROM stakeholder_feedback
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY stakeholder_group, feedback_type, sentiment, status,
                 consent_given, consent_scope, is_public, evidence_maturity
        ORDER BY feedback_count DESC, stakeholder_group
        """,
        (location_id,),
    )
    feedback_summary = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT practice_name, practice_type, stakeholder_group, language,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_cultural_context_summary
        WHERE location_id = %s
        ORDER BY practice_type, practice_name
        LIMIT 10
        """,
        (location_id,),
    )
    cultural_context = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT metric_key, metric_name, stakeholder_group, language,
               score_value, count_value, public_summary, evidence_maturity,
               evidence_maturity_label
        FROM v_public_wellbeing_metric_summary
        WHERE location_id = %s
        ORDER BY observation_date DESC, metric_key
        LIMIT 10
        """,
        (location_id,),
    )
    wellbeing_metrics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT action_type, action_date, stakeholder_group, metric_name,
               decision_status, public_summary, evidence_maturity,
               evidence_maturity_label
        FROM v_public_participatory_governance_summary
        WHERE location_id = %s
        ORDER BY action_date DESC, action_type
        LIMIT 10
        """,
        (location_id,),
    )
    participatory_actions = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT plan_name, farm_model, sustainability_status, grant_dependency_pct,
               reinvestment_pct, public_goods_allocation_pct, runway_months,
               projected_annual_revenue_usd, projected_annual_noi_usd,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_financial_sustainability_summary
        WHERE location_id = %s
        ORDER BY plan_period_start DESC, plan_name
        LIMIT 5
        """,
        (location_id,),
    )
    financial_sustainability = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT risk_category, likelihood, impact_level, residual_risk_level,
               owner_role, review_cadence, next_review_date, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_risk_mitigation_summary
        WHERE location_id = %s
        ORDER BY next_review_date NULLS LAST, risk_category
        LIMIT 10
        """,
        (location_id,),
    )
    risk_mitigation = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) AS evaluated_count,
               COUNT(*) FILTER (WHERE predicted_value > actual_value) AS overprediction_count,
               COUNT(*) FILTER (WHERE predicted_value < actual_value) AS underprediction_count,
               AVG(predicted_value - actual_value) AS mean_signed_error
        FROM v_public_prediction_accuracy
        WHERE location_id = %s AND actual_value IS NOT NULL
        """,
        (location_id,),
    )
    forecast_performance = dict(cur.fetchone() or {})

    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE milestone_status = 'blocked') AS blocked_count,
               COUNT(*) FILTER (
                   WHERE milestone_target_date < CURRENT_DATE
                     AND milestone_status NOT IN ('completed', 'skipped')
               ) AS overdue_count,
               MIN(milestone_target_date) FILTER (
                   WHERE milestone_target_date < CURRENT_DATE
                     AND milestone_status NOT IN ('completed', 'skipped')
               ) AS oldest_overdue_date
        FROM threat_backcast_plan WHERE location_id = %s
        """,
        (location_id,),
    )
    backcast_milestone_health = dict(cur.fetchone() or {})

    cur.execute(
        """
        SELECT COUNT(*) AS pending_count, MIN(bac.created_at) AS oldest_pending_at
        FROM backcast_assumption_challenge bac
        JOIN backcast_plan bp ON bp.id = bac.backcast_plan_id
        WHERE bp.location_id = %s AND bac.outcome = 'pending'
        """,
        (location_id,),
    )
    unresolved_assumption_challenges = dict(cur.fetchone() or {})

    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE v.consensus_reached = FALSE) AS non_consensus_count,
               MAX(v.iqr) AS maximum_iqr
        FROM v_delphi_consensus_public v
        JOIN delphi_study ds ON ds.id = v.study_id
        WHERE ds.location_id = %s
        """,
        (location_id,),
    )
    delphi_dissent = dict(cur.fetchone() or {})

    cur.execute(
        """
        SELECT composite_score, rating, confidence_level, evidence_maturity_level,
               period_start, period_end
        FROM v_crisp_composite_rating
        WHERE location_id = %s
        ORDER BY period_end DESC, score_computed_at DESC
        LIMIT 1
        """,
        (location_id,),
    )
    crisp_risk = dict(cur.fetchone() or {})

    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE gate_result='fail') AS failed_scope_count,
               COUNT(*) FILTER (WHERE gate_result='insufficient_data') AS insufficient_scope_count,
               COUNT(*) FILTER (WHERE gate_result='pass') AS passed_scope_count
        FROM v_prediction_calibration_summary
        WHERE location_id=%s OR location_id IS NULL
        """,
        (location_id,),
    )
    prediction_calibration = dict(cur.fetchone() or {})
    cur.close()

    has_private_feedback = any(row.get("private_or_no_consent_count", 0) for row in feedback_summary)
    has_carbon_gaps = any(row.get("carbon_publication_gaps", 0) for row in evidence_gaps)
    has_missing_evidence = any(row.get("missing_evidence_links", 0) for row in evidence_gaps)

    limitations = []
    if has_private_feedback:
        limitations.append(
            "Some stakeholder feedback is private or lacks public consent and is summarized only in aggregate."
        )
    if has_carbon_gaps:
        limitations.append(
            "Some public carbon claims are not publication-ready until Level 6 verifier and methodology requirements are satisfied."
        )
    if has_missing_evidence:
        limitations.append(
            "Some claims are missing CIDs, hashes, or attestation UIDs and should be treated as lower-confidence evidence."
        )
    if not limitations:
        limitations.append(
            "No findings were detected by the configured checks in the available governed data. This is not evidence that adverse outcomes or evidence gaps are absent."
        )

    return {
        "principles": [
            "Publish only governed records that are verified, published, consented, or explicitly public-safe.",
            "Keep private stakeholder evidence off public reports unless consent scope allows publication.",
            "Separate public carbon-balance claims from credit issuance claims unless external verification supports issuance.",
            "Show limitations and evidence gaps beside positive impact claims.",
        ],
        "public_feedback": _serialize_rows(public_feedback),
        "public_claims": _serialize_rows(public_claims),
        "evidence_gaps": _serialize_rows(evidence_gaps),
        "stakeholder_feedback_summary": _serialize_rows(feedback_summary),
        "cultural_context": _serialize_rows(cultural_context),
        "wellbeing_metrics": _serialize_rows(wellbeing_metrics),
        "participatory_actions": _serialize_rows(participatory_actions),
        "financial_sustainability": _serialize_rows(financial_sustainability),
        "risk_mitigation": _serialize_rows(risk_mitigation),
        "forecast_performance": {k: _serialize_value(v) for k, v in forecast_performance.items()},
        "backcast_milestone_health": {k: _serialize_value(v) for k, v in backcast_milestone_health.items()},
        "unresolved_assumption_challenges": {
            k: _serialize_value(v) for k, v in unresolved_assumption_challenges.items()
        },
        "delphi_dissent": {k: _serialize_value(v) for k, v in delphi_dissent.items()},
        "crisp_risk": {k: _serialize_value(v) for k, v in crisp_risk.items()},
        "prediction_calibration": {k: _serialize_value(v) for k, v in prediction_calibration.items()},
        "signed_error_convention": "predicted_minus_actual; positive values indicate overprediction",
        "limitations": limitations,
    }


def attach_public_interest_context(conn, report_data: dict, location_id: Optional[str]) -> dict:
    """Attach public-interest context without changing report-specific payloads."""
    if location_id:
        report_data["public_interest"] = fetch_public_interest_context(conn, location_id)
    return report_data
