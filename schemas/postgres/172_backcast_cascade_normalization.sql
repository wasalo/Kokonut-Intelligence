BEGIN;

CREATE TABLE IF NOT EXISTS backcast_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plan_name VARCHAR(200) NOT NULL CHECK (btrim(plan_name) <> ''),
    future_state_description TEXT NOT NULL CHECK (btrim(future_state_description) <> ''),
    current_gap_analysis TEXT NOT NULL CHECK (btrim(current_gap_analysis) <> ''),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backcast_plan_narrative ON backcast_plan(narrative_id);
CREATE INDEX IF NOT EXISTS idx_backcast_plan_location ON backcast_plan(location_id);

ALTER TABLE threat_backcast_plan ADD COLUMN IF NOT EXISTS plan_id UUID;

-- Existing code grouped milestones by narrative. Preserve that behavior for
-- unambiguous legacy rows while separating groups whose repeated headers differ.
WITH assigned AS (
    SELECT id AS milestone_id,
           md5('backcast-plan-v1|' || narrative_id::text || '|' || location_id::text || '|' ||
               btrim(plan_name) || '|' || future_state_description || '|' || current_gap_analysis)::uuid AS inferred_plan_id
    FROM threat_backcast_plan
)
UPDATE threat_backcast_plan milestone
SET plan_id = assigned.inferred_plan_id
FROM assigned
WHERE milestone.id = assigned.milestone_id AND milestone.plan_id IS NULL;

INSERT INTO backcast_plan (
    id, narrative_id, location_id, plan_name, future_state_description,
    current_gap_analysis, metadata, created_at, updated_at
)
SELECT plan_id, (ARRAY_AGG(narrative_id ORDER BY id))[1],
       (ARRAY_AGG(location_id ORDER BY id))[1], MIN(btrim(plan_name)),
       MIN(future_state_description), MIN(current_gap_analysis),
       jsonb_build_object('backfilled_from', 'threat_backcast_plan', 'backfill_version', '172'),
       MIN(created_at), MAX(updated_at)
FROM threat_backcast_plan
WHERE plan_id IS NOT NULL
GROUP BY plan_id
ON CONFLICT (id) DO NOTHING;

ALTER TABLE threat_backcast_plan ALTER COLUMN plan_id SET NOT NULL;
ALTER TABLE threat_backcast_plan DROP CONSTRAINT IF EXISTS fk_threat_backcast_milestone_plan;
ALTER TABLE threat_backcast_plan ADD CONSTRAINT fk_threat_backcast_milestone_plan
    FOREIGN KEY (plan_id) REFERENCES backcast_plan(id) ON DELETE CASCADE;
ALTER TABLE threat_backcast_plan DROP CONSTRAINT IF EXISTS chk_backcast_milestone_order_positive;
ALTER TABLE threat_backcast_plan ADD CONSTRAINT chk_backcast_milestone_order_positive
    CHECK (milestone_order > 0);
CREATE UNIQUE INDEX IF NOT EXISTS uq_backcast_milestone_plan_order
    ON threat_backcast_plan(plan_id, milestone_order);
CREATE INDEX IF NOT EXISTS idx_backcast_milestone_plan ON threat_backcast_plan(plan_id);

CREATE OR REPLACE FUNCTION enforce_backcast_plan_location()
RETURNS TRIGGER AS $$
DECLARE narrative_location UUID;
BEGIN
    SELECT threat.location_id INTO narrative_location
    FROM threat_narrative narrative
    JOIN threat ON threat.id = narrative.threat_id
    WHERE narrative.id = NEW.narrative_id;
    IF narrative_location IS NULL OR narrative_location IS DISTINCT FROM NEW.location_id THEN
        RAISE EXCEPTION 'backcast plan location must match narrative threat location';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_backcast_plan_location ON backcast_plan;
CREATE TRIGGER trg_backcast_plan_location
BEFORE INSERT OR UPDATE OF narrative_id, location_id ON backcast_plan
FOR EACH ROW EXECUTE FUNCTION enforce_backcast_plan_location();

CREATE OR REPLACE FUNCTION enforce_backcast_milestone_header()
RETURNS TRIGGER AS $$
DECLARE parent backcast_plan%ROWTYPE;
BEGIN
    SELECT * INTO parent FROM backcast_plan WHERE id = NEW.plan_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'backcast plan % does not exist', NEW.plan_id; END IF;
    NEW.narrative_id := parent.narrative_id;
    NEW.location_id := parent.location_id;
    NEW.plan_name := parent.plan_name;
    NEW.future_state_description := parent.future_state_description;
    NEW.current_gap_analysis := parent.current_gap_analysis;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_backcast_milestone_header ON threat_backcast_plan;
CREATE TRIGGER trg_backcast_milestone_header
BEFORE INSERT OR UPDATE OF plan_id, narrative_id, location_id, plan_name,
    future_state_description, current_gap_analysis ON threat_backcast_plan
FOR EACH ROW EXECUTE FUNCTION enforce_backcast_milestone_header();

CREATE TABLE IF NOT EXISTS backcast_milestone_dependency (
    plan_id UUID NOT NULL REFERENCES backcast_plan(id) ON DELETE CASCADE,
    milestone_id UUID NOT NULL REFERENCES threat_backcast_plan(id) ON DELETE CASCADE,
    depends_on_milestone_id UUID NOT NULL REFERENCES threat_backcast_plan(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (milestone_id, depends_on_milestone_id),
    CHECK (milestone_id <> depends_on_milestone_id)
);
CREATE INDEX IF NOT EXISTS idx_backcast_dependency_plan ON backcast_milestone_dependency(plan_id);
CREATE INDEX IF NOT EXISTS idx_backcast_dependency_target ON backcast_milestone_dependency(depends_on_milestone_id);

INSERT INTO backcast_milestone_dependency(plan_id, milestone_id, depends_on_milestone_id)
SELECT source.plan_id, source.id, target.id
FROM threat_backcast_plan source
CROSS JOIN LATERAL unnest(COALESCE(source.dependencies, '{}'::uuid[])) dependency_id
JOIN threat_backcast_plan target ON target.id = dependency_id AND target.plan_id = source.plan_id
WHERE source.id <> target.id
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION enforce_backcast_dependency_integrity()
RETURNS TRIGGER AS $$
DECLARE source_plan UUID; target_plan UUID; has_cycle BOOLEAN;
BEGIN
    SELECT plan_id INTO source_plan FROM threat_backcast_plan WHERE id = NEW.milestone_id;
    SELECT plan_id INTO target_plan FROM threat_backcast_plan WHERE id = NEW.depends_on_milestone_id;
    IF source_plan IS NULL OR target_plan IS NULL OR source_plan <> target_plan OR NEW.plan_id <> source_plan THEN
        RAISE EXCEPTION 'backcast dependencies must remain within one plan';
    END IF;
    WITH RECURSIVE reachable(id) AS (
        SELECT NEW.depends_on_milestone_id
        UNION
        SELECT dependency.depends_on_milestone_id
        FROM backcast_milestone_dependency dependency
        JOIN reachable ON dependency.milestone_id = reachable.id
    )
    SELECT EXISTS(SELECT 1 FROM reachable WHERE id = NEW.milestone_id) INTO has_cycle;
    IF has_cycle THEN RAISE EXCEPTION 'backcast milestone dependency cycle detected'; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_backcast_dependency_integrity ON backcast_milestone_dependency;
CREATE TRIGGER trg_backcast_dependency_integrity
BEFORE INSERT OR UPDATE ON backcast_milestone_dependency
FOR EACH ROW EXECUTE FUNCTION enforce_backcast_dependency_integrity();

CREATE OR REPLACE FUNCTION sync_backcast_dependency_array()
RETURNS TRIGGER AS $$
DECLARE affected UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN affected := OLD.milestone_id;
    ELSE affected := NEW.milestone_id;
    END IF;
    UPDATE threat_backcast_plan milestone
    SET dependencies = COALESCE((
        SELECT array_agg(dependency.depends_on_milestone_id ORDER BY target.milestone_order, dependency.depends_on_milestone_id)
        FROM backcast_milestone_dependency dependency
        JOIN threat_backcast_plan target ON target.id = dependency.depends_on_milestone_id
        WHERE dependency.milestone_id = affected
    ), '{}'::uuid[]), updated_at = NOW()
    WHERE milestone.id = affected;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_backcast_dependency_array ON backcast_milestone_dependency;
CREATE TRIGGER trg_sync_backcast_dependency_array
AFTER INSERT OR UPDATE OR DELETE ON backcast_milestone_dependency
FOR EACH ROW EXECUTE FUNCTION sync_backcast_dependency_array();

ALTER TABLE backcast_assumption_challenge
    ADD COLUMN IF NOT EXISTS backcast_plan_id UUID REFERENCES backcast_plan(id) ON DELETE CASCADE;
UPDATE backcast_assumption_challenge challenge
SET backcast_plan_id = milestone.plan_id
FROM threat_backcast_plan milestone
WHERE milestone.id = challenge.plan_id AND challenge.backcast_plan_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_bac_backcast_plan ON backcast_assumption_challenge(backcast_plan_id);

CREATE TABLE IF NOT EXISTS threat_cascade_step (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cascade_id UUID NOT NULL REFERENCES threat_cascade(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL CHECK (step_order > 0),
    threat_id UUID NOT NULL REFERENCES threat(id) ON DELETE RESTRICT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(cascade_id, step_order),
    UNIQUE(cascade_id, threat_id)
);
CREATE INDEX IF NOT EXISTS idx_threat_cascade_step_threat ON threat_cascade_step(threat_id);

INSERT INTO threat_cascade_step(cascade_id, step_order, threat_id, metadata)
SELECT cascade.id, chain.ordinality::integer, chain.threat_id,
       jsonb_build_object('backfilled_from', 'threat_cascade.failure_chain', 'backfill_version', '172')
FROM threat_cascade cascade
CROSS JOIN LATERAL unnest(cascade.failure_chain) WITH ORDINALITY chain(threat_id, ordinality)
JOIN threat step_threat ON step_threat.id = chain.threat_id
JOIN threat trigger_threat ON trigger_threat.id = cascade.trigger_threat_id
WHERE chain.threat_id <> cascade.trigger_threat_id
  AND step_threat.location_id = trigger_threat.location_id
  AND NOT EXISTS (
      SELECT 1 FROM unnest(cascade.failure_chain) WITH ORDINALITY prior(prior_id, prior_order)
      WHERE prior.prior_id = chain.threat_id AND prior.prior_order < chain.ordinality
  )
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION enforce_cascade_step_location()
RETURNS TRIGGER AS $$
DECLARE trigger_id UUID; trigger_location UUID; step_location UUID;
BEGIN
    SELECT cascade.trigger_threat_id, threat.location_id INTO trigger_id, trigger_location
    FROM threat_cascade cascade JOIN threat ON threat.id = cascade.trigger_threat_id
    WHERE cascade.id = NEW.cascade_id;
    SELECT location_id INTO step_location FROM threat WHERE id = NEW.threat_id;
    IF trigger_id IS NULL OR NEW.threat_id = trigger_id OR step_location IS DISTINCT FROM trigger_location THEN
        RAISE EXCEPTION 'cascade steps must be distinct downstream threats in the trigger location';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cascade_step_location ON threat_cascade_step;
CREATE TRIGGER trg_cascade_step_location
BEFORE INSERT OR UPDATE ON threat_cascade_step
FOR EACH ROW EXECUTE FUNCTION enforce_cascade_step_location();

CREATE OR REPLACE FUNCTION sync_cascade_failure_chain()
RETURNS TRIGGER AS $$
DECLARE affected UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN affected := OLD.cascade_id;
    ELSE affected := NEW.cascade_id;
    END IF;
    UPDATE threat_cascade cascade
    SET failure_chain = COALESCE((
        SELECT array_agg(step.threat_id ORDER BY step.step_order)
        FROM threat_cascade_step step WHERE step.cascade_id = affected
    ), '{}'::uuid[]), updated_at = NOW()
    WHERE cascade.id = affected;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_cascade_failure_chain ON threat_cascade_step;
CREATE TRIGGER trg_sync_cascade_failure_chain
AFTER INSERT OR UPDATE OR DELETE ON threat_cascade_step
FOR EACH ROW EXECUTE FUNCTION sync_cascade_failure_chain();

CREATE OR REPLACE VIEW v_backcast_plan_summary AS
SELECT plan.id AS plan_id, plan.narrative_id, plan.location_id, plan.plan_name,
       COUNT(milestone.id) AS milestone_count,
       COUNT(milestone.id) FILTER (WHERE milestone.milestone_status = 'completed') AS completed_count,
       COUNT(milestone.id) FILTER (WHERE milestone.milestone_status = 'blocked') AS blocked_count,
       MIN(milestone.milestone_target_date) FILTER (WHERE milestone.milestone_status NOT IN ('completed', 'skipped')) AS next_target_date,
       plan.created_at, plan.updated_at
FROM backcast_plan plan
LEFT JOIN threat_backcast_plan milestone ON milestone.plan_id = plan.id
GROUP BY plan.id;

COMMIT;
