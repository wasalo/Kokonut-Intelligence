-- ============================================================
-- 299_sequential_decision_integrity.sql
-- Fail closed for malformed and mutable sequential-decision evidence.
-- ============================================================

ALTER TABLE decision_evidence_event
    ADD CONSTRAINT decision_evidence_likelihood_pair_check
        CHECK ((likelihood_hypothesis IS NULL) = (likelihood_alternative IS NULL)),
    ADD CONSTRAINT decision_evidence_likelihood_range_check
        CHECK ((likelihood_hypothesis IS NULL OR likelihood_hypothesis <= 1)
           AND (likelihood_alternative IS NULL OR likelihood_alternative <= 1)),
    ADD CONSTRAINT decision_evidence_source_check
        CHECK (NULLIF(BTRIM(source_ref), '') IS NOT NULL OR source_id IS NOT NULL);

ALTER TABLE decision_posterior_update
    ADD CONSTRAINT decision_posterior_count_check CHECK (effective_evidence_count > 0);

CREATE OR REPLACE FUNCTION prevent_sequential_ledger_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'sequential evidence and posterior records are immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_decision_evidence_immutable ON decision_evidence_event;
CREATE TRIGGER trg_decision_evidence_immutable
    BEFORE UPDATE ON decision_evidence_event
    FOR EACH ROW EXECUTE FUNCTION prevent_sequential_ledger_mutation();

DROP TRIGGER IF EXISTS trg_decision_posterior_immutable ON decision_posterior_update;
CREATE TRIGGER trg_decision_posterior_immutable
    BEFORE UPDATE ON decision_posterior_update
    FOR EACH ROW EXECUTE FUNCTION prevent_sequential_ledger_mutation();
