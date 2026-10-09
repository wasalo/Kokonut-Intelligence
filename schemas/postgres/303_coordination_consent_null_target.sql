-- 303_coordination_consent_null_target.sql
-- Preserve exact recipient matching while allowing an explicitly broadcast
-- exchange (NULL target) to match a network consent with NULL recipient.

CREATE OR REPLACE FUNCTION enforce_coordination_exchange_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    alliance_scope_type VARCHAR(30);
    alliance_scope_id UUID;
BEGIN
    IF NEW.status = 'completed' THEN
        SELECT scope_type, scope_id INTO alliance_scope_type, alliance_scope_id
        FROM coordination_alliance WHERE id = NEW.alliance_id;
        IF NEW.consent_event_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM v_effective_stakeholder_consent c
            WHERE c.consent_event_id = NEW.consent_event_id
              AND c.party_id = NEW.from_party_id
              AND c.event_type = 'grant'
              AND c.consented = TRUE
              AND c.data_category = 'coordination_knowledge_exchange'
              AND c.purpose = 'knowledge_exchange'
              AND c.recipient_party_id IS NOT DISTINCT FROM NEW.to_party_id
              AND (NEW.consent_scope IS NULL OR c.scope_type = NEW.consent_scope)
              AND (
                  c.scope_type = 'network'
                  OR (c.scope_type = alliance_scope_type AND c.scope_id IS NOT DISTINCT FROM alliance_scope_id)
              )
        ) THEN
            RAISE EXCEPTION 'effective sender consent for this knowledge exchange is required';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
