-- ============================================================
-- 350_agent_safety_triggers.sql — DB-level agent safety enforcement
-- ============================================================
-- Adds a trigger function and BEFORE UPDATE triggers on governed
-- tables so that direct SQL (bypassing the Python safety layer)
-- still enforces that agents cannot escalate status to verified/published.
-- ============================================================

-- 1. Trigger function: reads app.agent_id from the transaction.
--    If set and non-empty, blocks status escalation to 'verified' or 'published'.
--    If unset (human operation), allows everything.
CREATE OR REPLACE FUNCTION assert_agent_safety()
RETURNS TRIGGER AS $$
DECLARE
    agent_id TEXT;
BEGIN
    agent_id := current_setting('app.agent_id', TRUE);
    -- If no agent context, this is a human operation — allow everything
    IF agent_id IS NULL OR agent_id = '' THEN
        RETURN NEW;
    END IF;
    -- Block status escalation to verified/published for governed collections
    IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status IN ('verified', 'published') THEN
        RAISE EXCEPTION 'Agent % cannot set status to % on %', agent_id, NEW.status, TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper: apply the trigger to a table if it has a status column.
-- Uses DROP TRIGGER IF EXISTS + CREATE TRIGGER for idempotent re-application.

-- 2. Apply triggers to high-risk governed tables with a status column.

-- impact_claim
DROP TRIGGER IF EXISTS trg_agent_safety ON impact_claim;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON impact_claim
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- carbon_credit
DROP TRIGGER IF EXISTS trg_agent_safety ON carbon_credit;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON carbon_credit
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- stakeholder_feedback
DROP TRIGGER IF EXISTS trg_agent_safety ON stakeholder_feedback;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON stakeholder_feedback
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- data_stream_post
DROP TRIGGER IF EXISTS trg_agent_safety ON data_stream_post;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON data_stream_post
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- data_stream_post_comment
DROP TRIGGER IF EXISTS trg_agent_safety ON data_stream_post_comment;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON data_stream_post_comment
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- crisp_risk_assessment
DROP TRIGGER IF EXISTS trg_agent_safety ON crisp_risk_assessment;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON crisp_risk_assessment
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- threat
DROP TRIGGER IF EXISTS trg_agent_safety ON threat;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON threat
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- threat_flag
DROP TRIGGER IF EXISTS trg_agent_safety ON threat_flag;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON threat_flag
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- threat_horizon
DROP TRIGGER IF EXISTS trg_agent_safety ON threat_horizon;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON threat_horizon
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- delphi_recommendation
DROP TRIGGER IF EXISTS trg_agent_safety ON delphi_recommendation;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON delphi_recommendation
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- delphi_study
DROP TRIGGER IF EXISTS trg_agent_safety ON delphi_study;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON delphi_study
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- metric_proposal
DROP TRIGGER IF EXISTS trg_agent_safety ON metric_proposal;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON metric_proposal
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- stakeholder_outcome
DROP TRIGGER IF EXISTS trg_agent_safety ON stakeholder_outcome;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON stakeholder_outcome
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- stakeholder_grievance_case
DROP TRIGGER IF EXISTS trg_agent_safety ON stakeholder_grievance_case;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON stakeholder_grievance_case
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- stakeholder_decision
DROP TRIGGER IF EXISTS trg_agent_safety ON stakeholder_decision;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON stakeholder_decision
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- report_snapshot
DROP TRIGGER IF EXISTS trg_agent_safety ON report_snapshot;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON report_snapshot
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- forecast_scenario
DROP TRIGGER IF EXISTS trg_agent_safety ON forecast_scenario;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON forecast_scenario
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- prediction_ledger
DROP TRIGGER IF EXISTS trg_agent_safety ON prediction_ledger;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON prediction_ledger
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- prediction_outcome
DROP TRIGGER IF EXISTS trg_agent_safety ON prediction_outcome;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON prediction_outcome
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- reference_class
DROP TRIGGER IF EXISTS trg_agent_safety ON reference_class;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON reference_class
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- outside_view_comparison
DROP TRIGGER IF EXISTS trg_agent_safety ON outside_view_comparison;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON outside_view_comparison
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- delphi_diversity_assessment
DROP TRIGGER IF EXISTS trg_agent_safety ON delphi_diversity_assessment;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON delphi_diversity_assessment
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- delphi_stopping_evaluation
DROP TRIGGER IF EXISTS trg_agent_safety ON delphi_stopping_evaluation;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON delphi_stopping_evaluation
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- delphi_minority_report
DROP TRIGGER IF EXISTS trg_agent_safety ON delphi_minority_report;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON delphi_minority_report
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- credit_retirement
DROP TRIGGER IF EXISTS trg_agent_safety ON credit_retirement;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON credit_retirement
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- credit_class
DROP TRIGGER IF EXISTS trg_agent_safety ON credit_class;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON credit_class
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- credit_batch
DROP TRIGGER IF EXISTS trg_agent_safety ON credit_batch;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON credit_batch
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- credit_adjustment
DROP TRIGGER IF EXISTS trg_agent_safety ON credit_adjustment;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON credit_adjustment
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- credit_transfer
DROP TRIGGER IF EXISTS trg_agent_safety ON credit_transfer;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON credit_transfer
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- retirement_certificate
DROP TRIGGER IF EXISTS trg_agent_safety ON retirement_certificate;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON retirement_certificate
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- governance_circle
DROP TRIGGER IF EXISTS trg_agent_safety ON governance_circle;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON governance_circle
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- governance_proposal
DROP TRIGGER IF EXISTS trg_agent_safety ON governance_proposal;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON governance_proposal
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- governance_tactical_item
DROP TRIGGER IF EXISTS trg_agent_safety ON governance_tactical_item;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON governance_tactical_item
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- governance_tension
DROP TRIGGER IF EXISTS trg_agent_safety ON governance_tension;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON governance_tension
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_alliance
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_alliance;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_alliance
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_participant
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_participant;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_participant
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_objective
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_objective;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_objective
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_contribution
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_contribution;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_contribution
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_benefit
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_benefit;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_benefit
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_risk
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_risk;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_risk
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_knowledge_exchange
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_knowledge_exchange;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_knowledge_exchange
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_review
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_review;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_review
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_learning_link
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_learning_link;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_learning_link
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_metric_observation
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_metric_observation;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_metric_observation
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_conflict_declaration
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_conflict_declaration;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_conflict_declaration
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_benefit_harm_analysis
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_benefit_harm_analysis;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_benefit_harm_analysis
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_minority_view
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_minority_view;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_minority_view
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_appeal
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_appeal;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_appeal
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_remedy
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_remedy;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_remedy
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_approval
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_approval;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_approval
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_partner_event
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_partner_event;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_partner_event
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- coordination_market_observation
DROP TRIGGER IF EXISTS trg_agent_safety ON coordination_market_observation;
CREATE TRIGGER trg_agent_safety
    BEFORE UPDATE ON coordination_market_observation
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION assert_agent_safety('status');

-- 3. Record schema version
INSERT INTO schema_version (version, description, applied_by)
VALUES ('agent-safety-triggers-v1', 'DB-level agent safety triggers for 51 governed tables with status columns', 'schema 350')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
