-- ============================================================
-- 084_structural_assumptions.sql — Default structural assumptions
-- ============================================================

INSERT INTO structural_assumption (assumption_text, domain, status, original_source) VALUES
('Higher input use leads to higher yields', 'ecological', 'active', 'conventional_agriculture'),
('Soil carbon can be depleted without long-term consequences', 'ecological', 'active', 'conventional_agriculture'),
('Market prices will remain within historical ranges', 'financial', 'active', 'financial_planning'),
('Water availability will remain consistent', 'ecological', 'active', 'infrastructure_planning'),
('Certification always leads to price premiums', 'financial', 'active', 'market_assumptions'),
('Training leads to practice adoption within 6 months', 'social', 'active', 'program_design'),
('Single-crop specialization is more efficient', 'financial', 'active', 'economic_theory'),
('Technology adoption solves all operational problems', 'operational', 'active', 'technology_optimism'),
('Community engagement is optional for farm success', 'social', 'active', 'individualism'),
('Short-term profitability indicates long-term viability', 'financial', 'active', 'financial_metrics')
ON CONFLICT DO NOTHING;
