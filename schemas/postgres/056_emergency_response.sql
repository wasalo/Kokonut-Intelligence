-- 056_emergency_response.sql
-- Emergency Incident Tracking & Response

BEGIN;

-- ============================================================================
-- EMERGENCY INCIDENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS emergency_incident (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    incident_type VARCHAR(100) NOT NULL
        CHECK (incident_type IN (
            'drought', 'flood', 'pest_outbreak', 'extreme_heat',
            'frost', 'fire', 'disease_epidemic', 'soil_degradation',
            'water_crisis', 'other'
        )),
    severity VARCHAR(50) NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    detection_date DATE NOT NULL DEFAULT CURRENT_DATE,
    detection_method VARCHAR(100) NOT NULL DEFAULT 'field_observation'
        CHECK (detection_method IN (
            'sensor_alert', 'field_observation', 'remote_sensing',
            'weather_forecast', 'community_report', 'other'
        )),
    description TEXT NOT NULL,
    affected_area_pct NUMERIC(5,2) DEFAULT 0
        CHECK (affected_area_pct >= 0 AND affected_area_pct <= 100),
    affected_plant_count INT DEFAULT 0
        CHECK (affected_plant_count >= 0),
    response_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    emergency_support_provided TEXT,
    response_deadline DATE,
    recovery_date DATE,
    recovery_actions JSONB DEFAULT '[]'::jsonb,
    financial_impact_usd NUMERIC(10,2) DEFAULT 0,
    ecological_impact_notes TEXT,
    lessons_learned TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'detected'
        CHECK (status IN ('detected', 'responding', 'recovering', 'resolved', 'escalated')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_emergency_location ON emergency_incident(location_id);
CREATE INDEX IF NOT EXISTS idx_emergency_type ON emergency_incident(incident_type);
CREATE INDEX IF NOT EXISTS idx_emergency_severity ON emergency_incident(severity);
CREATE INDEX IF NOT EXISTS idx_emergency_status ON emergency_incident(status);
CREATE INDEX IF NOT EXISTS idx_emergency_detection ON emergency_incident(detection_date);

CREATE TRIGGER trg_emergency_updated_at
    BEFORE UPDATE ON emergency_incident
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE emergency_incident IS 'Tracks emergency incidents (drought, flood, pest outbreak, etc.) with response actions, recovery, and lessons learned';

-- ============================================================================
-- VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_public_emergency_incidents AS
SELECT
    e.id,
    e.location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    e.incident_type,
    e.severity,
    e.detection_date,
    e.detection_method,
    e.description,
    e.affected_area_pct,
    e.affected_plant_count,
    e.response_actions,
    e.emergency_support_provided,
    e.response_deadline,
    e.recovery_date,
    CASE
        WHEN e.recovery_date IS NOT NULL AND e.detection_date IS NOT NULL
        THEN (e.recovery_date - e.detection_date)
        ELSE NULL
    END AS response_time_days,
    CASE
        WHEN e.response_deadline IS NOT NULL AND e.recovery_date IS NOT NULL
        THEN e.recovery_date <= e.response_deadline
        ELSE NULL
    END AS met_deadline,
    e.recovery_actions,
    e.financial_impact_usd,
    e.ecological_impact_notes,
    e.lessons_learned,
    e.status,
    e.created_at
FROM emergency_incident e
JOIN location l ON e.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

COMMIT;
