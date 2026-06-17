-- ============================================================
-- 024_metric_governance_enforcement.sql — metric definition versioning
-- ============================================================

CREATE OR REPLACE FUNCTION record_metric_definition_version()
RETURNS TRIGGER AS $$
BEGIN
    IF (
        OLD.formula IS DISTINCT FROM NEW.formula OR
        OLD.source_tables IS DISTINCT FROM NEW.source_tables OR
        OLD.inclusion_rules IS DISTINCT FROM NEW.inclusion_rules OR
        OLD.exclusion_rules IS DISTINCT FROM NEW.exclusion_rules OR
        OLD.unit IS DISTINCT FROM NEW.unit OR
        OLD.data_type IS DISTINCT FROM NEW.data_type
    ) THEN
        IF NEW.version <= OLD.version THEN
            NEW.version := OLD.version + 1;
        END IF;

        INSERT INTO metric_version (metric_id, version, formula, changes, change_reason)
        VALUES (
            NEW.id,
            NEW.version,
            NEW.formula,
            'Metric definition changed',
            'Automatic version record from metric_definition update'
        )
        ON CONFLICT (metric_id, version) DO NOTHING;
    END IF;

    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_metric_definition_version ON metric_definition;
CREATE TRIGGER trg_metric_definition_version
BEFORE UPDATE ON metric_definition
FOR EACH ROW
EXECUTE FUNCTION record_metric_definition_version();
