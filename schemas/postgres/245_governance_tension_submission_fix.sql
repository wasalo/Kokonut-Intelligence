-- A submitted tension may await triage ownership; ownership is required once
-- triage or active work begins.

ALTER TABLE governance_tension DROP CONSTRAINT IF EXISTS governance_tension_check2;
ALTER TABLE governance_tension ADD CONSTRAINT governance_tension_owner_check CHECK (
    owner_role_id IS NOT NULL OR owner_party_id IS NOT NULL
    OR status IN ('draft', 'submitted', 'rejected')
);
