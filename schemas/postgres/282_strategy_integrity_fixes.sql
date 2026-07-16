-- ============================================================
-- 282_strategy_integrity_fixes.sql
-- Close strategy orchestration integrity gaps before foresight expansion.
-- ============================================================

ALTER TABLE strategy_review_task
    DROP CONSTRAINT IF EXISTS strategy_review_task_review_type_check;
ALTER TABLE strategy_review_task
    ADD CONSTRAINT strategy_review_task_review_type_check CHECK (
        review_type IN ('scheduled', 'kpi_breach', 'risk_change', 'assumption_failure',
                        'coherence_breach', 'portfolio_variance', 'competitive_change')
    );

CREATE OR REPLACE FUNCTION validate_strategy_plan_cascade()
RETURNS TRIGGER AS $$
DECLARE
    parent_scope_type VARCHAR(20);
    parent_scope_id UUID;
    location_organization_id UUID;
BEGIN
    IF NEW.parent_strategy_plan_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.parent_strategy_plan_id = NEW.id THEN
        RAISE EXCEPTION 'strategy plan cannot parent itself';
    END IF;
    SELECT scope_type, scope_id INTO parent_scope_type, parent_scope_id
    FROM strategy_plan WHERE id = NEW.parent_strategy_plan_id;
    IF parent_scope_type IS NULL THEN
        RAISE EXCEPTION 'parent strategy plan does not exist';
    END IF;
    IF NEW.scope_type <> 'location' OR parent_scope_type <> 'organization' THEN
        RAISE EXCEPTION 'only location strategy plans may cascade from organization plans';
    END IF;
    SELECT organization_id INTO location_organization_id
    FROM location WHERE id = NEW.scope_id;
    IF location_organization_id IS NULL OR location_organization_id <> parent_scope_id THEN
        RAISE EXCEPTION 'location strategy must cascade from its owning organization';
    END IF;
    IF NEW.cascade_mode = 'independent' THEN
        RAISE EXCEPTION 'cascaded strategy plans must be inherited or adapted';
    END IF;
    IF EXISTS (
        WITH RECURSIVE ancestors(id) AS (
            SELECT NEW.parent_strategy_plan_id
            UNION ALL
            SELECT sp.parent_strategy_plan_id
            FROM strategy_plan sp
            JOIN ancestors a ON a.id = sp.id
            WHERE sp.parent_strategy_plan_id IS NOT NULL
        )
        SELECT 1 FROM ancestors WHERE id = NEW.id
    ) THEN
        RAISE EXCEPTION 'strategy plan cascade would create an ancestry cycle';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
