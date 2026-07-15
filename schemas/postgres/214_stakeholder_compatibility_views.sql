-- Compatibility projections for existing stakeholder-like domain records.
-- These are source candidates, not automatic identity merges.

CREATE OR REPLACE VIEW v_stakeholder_source_candidates AS
SELECT
    'farmer_profile'::VARCHAR(50) AS source_type,
    fp.id AS source_id,
    NULLIF(TRIM(CONCAT_WS(' ', fp.first_name, fp.last_name)), '') AS display_name,
    'person'::VARCHAR(30) AS suggested_party_type,
    fp.location_id,
    fp.status,
    jsonb_build_object('phone_verified', fp.phone_verified, 'email_verified', fp.email_verified, 'kyc_status', fp.kyc_status) AS source_metadata
FROM farmer_profile fp
UNION ALL
SELECT
    'buyer_profile', bp.id, bp.name, 'organization', NULL, bp.status,
    jsonb_build_object('buyer_type', bp.buyer_type, 'verified', bp.verified)
FROM buyer_profile bp
UNION ALL
SELECT
    'partner', p.id, p.name, 'organization', NULL, p.status,
    jsonb_build_object('partner_type', p.partner_type, 'slug', p.slug)
FROM partner p
UNION ALL
SELECT
    'cooperative', c.id, c.name, 'cooperative', c.location_id, c.status,
    jsonb_build_object('governance_model', c.governance_model, 'membership_count', c.membership_count)
FROM cooperative c
UNION ALL
SELECT
    'stakeholder_public', sp.id, sp.name, 'organization', sp.location_id, sp.status,
    jsonb_build_object('public_type', sp.public_type, 'influence_score', sp.influence_score, 'interest_score', sp.interest_score)
FROM stakeholder_public sp;

COMMENT ON VIEW v_stakeholder_source_candidates IS 'Existing identity-like records available for reviewable party linking';
