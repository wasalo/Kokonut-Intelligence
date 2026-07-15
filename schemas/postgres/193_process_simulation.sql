-- ============================================================
-- 193_process_simulation.sql — Process Simulation + Optimization
-- ============================================================
-- Enables what-if process simulation, stores simulation results,
-- and persists process capability indices (Cp, Cpk, Pp, Ppk).

-- Process simulation scenarios
CREATE TABLE IF NOT EXISTS process_simulation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    process_key VARCHAR(100) REFERENCES process_map(process_key) ON DELETE SET NULL,
    scenario_params JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'completed', 'cancelled')),
    results JSONB,
    created_by UUID,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ps_process ON process_simulation(process_key);
CREATE INDEX IF NOT EXISTS idx_ps_status ON process_simulation(status);

-- Simulation results (per-metric comparison)
CREATE TABLE IF NOT EXISTS process_simulation_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id UUID NOT NULL REFERENCES process_simulation(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    baseline_value DOUBLE PRECISION,
    simulated_value DOUBLE PRECISION,
    improvement_pct DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_psr_simulation ON process_simulation_result(simulation_id);

-- Process capability indices (enhanced SPC)
CREATE TABLE IF NOT EXISTS process_capability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    cp DOUBLE PRECISION,
    cpk DOUBLE PRECISION,
    pp DOUBLE PRECISION,
    ppk DOUBLE PRECISION,
    sigma_level DOUBLE PRECISION,
    period VARCHAR(40),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pcap_entity ON process_capability(entity_type, metric);
CREATE INDEX IF NOT EXISTS idx_pcap_computed ON process_capability(computed_at DESC);

COMMENT ON TABLE process_simulation IS 'What-if process simulation scenarios with parameter overrides';
COMMENT ON TABLE process_simulation_result IS 'Per-metric simulation results: baseline vs simulated';
COMMENT ON TABLE process_capability IS 'Process capability indices: Cp, Cpk, Pp, Ppk, sigma level';
