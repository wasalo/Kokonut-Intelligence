-- ============================================================
-- 320_consent_lifecycle_public_gates.sql
-- Correct effective consent resolution and public registry gates.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_effective_lookup
    ON stakeholder_consent(
        party_id, data_category, purpose, scope_type, scope_id,
        recipient_party_id, recipient_type, effective_at DESC, created_at DESC
    );

CREATE OR REPLACE VIEW v_effective_stakeholder_consent AS
SELECT DISTINCT ON (
    sc.party_id, sc.data_category, sc.purpose, sc.scope_type, sc.scope_id,
    sc.recipient_party_id, sc.recipient_type
)
    sc.id AS consent_event_id,
    sc.party_id,
    p.display_name AS party_name,
    sc.event_type,
    sc.data_category,
    sc.purpose,
    sc.scope_type,
    sc.scope_id,
    sc.recipient_party_id,
    rp.display_name AS recipient_party_name,
    sc.recipient_type,
    sc.recipient_name,
    sc.consent_method,
    sc.legal_basis,
    sc.consent_version,
    sc.effective_at,
    sc.expires_at,
    CASE
        WHEN sc.event_type = 'grant' AND sc.expires_at IS NOT NULL AND sc.expires_at <= NOW() THEN 'expired'
        WHEN sc.event_type = 'grant' THEN 'granted'
        WHEN sc.event_type = 'withdraw' THEN 'withdrawn'
        WHEN sc.event_type = 'deny' THEN 'denied'
        ELSE 'expired'
    END AS effective_status,
    (sc.event_type = 'grant' AND (sc.expires_at IS NULL OR sc.expires_at > NOW())) AS consented,
    sc.reason, sc.evidence, sc.source_system, sc.source_record_id, sc.created_at
FROM stakeholder_consent sc
JOIN party p ON p.id = sc.party_id
LEFT JOIN party rp ON rp.id = sc.recipient_party_id
WHERE sc.effective_at <= NOW()
ORDER BY sc.party_id, sc.data_category, sc.purpose, sc.scope_type, sc.scope_id,
         sc.recipient_party_id, sc.recipient_type, sc.effective_at DESC, sc.created_at DESC;

CREATE OR REPLACE VIEW v_public_statement_of_work AS
SELECT s.id, s.location_id, l.name AS location_name, s.sow_name, s.sow_version,
       s.effective_date, s.expiration_date, s.total_contract_value, s.currency, s.status,
       (SELECT COUNT(*)::int FROM sow_deliverable sd WHERE sd.sow_id = s.id) AS total_deliverables,
       (SELECT COUNT(*)::int FROM sow_deliverable sd WHERE sd.sow_id = s.id AND sd.status = 'accepted') AS accepted_deliverables,
       (SELECT COUNT(*)::int FROM sow_payment_schedule sp WHERE sp.sow_id = s.id) AS total_payments,
       (SELECT COALESCE(SUM(sp.amount), 0) FROM sow_payment_schedule sp WHERE sp.sow_id = s.id AND sp.payment_status = 'paid') AS total_paid,
       (SELECT COUNT(*)::int FROM sow_change_request sc WHERE sc.sow_id = s.id) AS total_change_requests,
       s.created_at
FROM statement_of_work s
JOIN location l ON s.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND EXISTS (SELECT 1 FROM farm_registry_record fr
              WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published'));

CREATE OR REPLACE VIEW v_public_sow_deliverables AS
SELECT sd.id, sd.sow_id, s.sow_name, s.location_id, l.name AS location_name,
       sd.deliverable_name, sd.description, sd.acceptance_criteria, sd.due_date,
       sd.delivered_at, sd.status,
       CASE WHEN sd.due_date IS NOT NULL AND sd.delivered_at IS NOT NULL
            THEN sd.delivered_at <= sd.due_date ELSE NULL END AS on_time,
       sd.created_at
FROM sow_deliverable sd
JOIN statement_of_work s ON sd.sow_id = s.id
JOIN location l ON s.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND EXISTS (SELECT 1 FROM farm_registry_record fr
              WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published'));

CREATE OR REPLACE VIEW v_public_sow_payment_schedule AS
SELECT sp.id, sp.sow_id, s.sow_name, s.location_id, l.name AS location_name,
       sp.milestone_name, sp.amount, s.currency, sp.due_date, sp.payment_status,
       CASE WHEN sp.payment_status = 'paid' AND sp.paid_at IS NOT NULL AND sp.due_date IS NOT NULL
            THEN sp.paid_at::date <= sp.due_date ELSE NULL END AS on_time,
       sp.created_at
FROM sow_payment_schedule sp
JOIN statement_of_work s ON sp.sow_id = s.id
JOIN location l ON s.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND s.status IN ('active', 'completed')
  AND EXISTS (SELECT 1 FROM farm_registry_record fr
              WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published'));

CREATE OR REPLACE VIEW v_public_cross_farm_portfolio AS
SELECT cfp.*,
       (SELECT COUNT(*) FROM farm f WHERE f.status = 'active') AS active_farms,
       (SELECT COALESCE(SUM(re.amount), 0) FROM revenue_event re) AS total_network_revenue
FROM cross_farm_portfolio cfp
WHERE EXISTS (SELECT 1 FROM farm_registry_record fr
              WHERE fr.status IN ('verified', 'published'))
ORDER BY cfp.last_computed_at DESC
LIMIT 1;
