-- Immutable Field Collector form revisions and reviewed participant links.
-- Existing collections remain unassessed; this migration does not infer consent.

ALTER TABLE mobile_form
    ADD COLUMN IF NOT EXISTS consent_policy_status TEXT NOT NULL DEFAULT 'unclassified'
        CHECK (consent_policy_status IN ('unclassified', 'required', 'not_required')),
    ADD COLUMN IF NOT EXISTS consent_data_category TEXT,
    ADD COLUMN IF NOT EXISTS consent_purpose TEXT,
    ADD COLUMN IF NOT EXISTS consent_scope_type TEXT,
    ADD COLUMN IF NOT EXISTS consent_scope_id UUID,
    ADD COLUMN IF NOT EXISTS consent_recipient_type TEXT,
    ADD COLUMN IF NOT EXISTS consent_recipient_party_id UUID REFERENCES party(id),
    ADD COLUMN IF NOT EXISTS consent_recipient_name TEXT,
    ADD COLUMN IF NOT EXISTS consent_version TEXT,
    ADD COLUMN IF NOT EXISTS consent_policy_reviewed_by TEXT,
    ADD COLUMN IF NOT EXISTS consent_policy_reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS consent_policy_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE mobile_form
    ADD CONSTRAINT chk_mobile_form_consent_policy_complete CHECK (
        consent_policy_status = 'unclassified'
        OR (
            NULLIF(BTRIM(consent_policy_reviewed_by), '') IS NOT NULL
            AND consent_policy_reviewed_at IS NOT NULL
            AND CASE WHEN jsonb_typeof(consent_policy_evidence) = 'array'
                     THEN jsonb_array_length(consent_policy_evidence) > 0 ELSE FALSE END
        )
    ),
    ADD CONSTRAINT chk_mobile_form_required_consent_policy CHECK (
        consent_policy_status <> 'required'
        OR (
            NULLIF(BTRIM(consent_data_category), '') IS NOT NULL
            AND NULLIF(BTRIM(consent_purpose), '') IS NOT NULL
            AND consent_scope_type IN (
                'network', 'organization', 'location', 'farm', 'cooperative',
                'value_stream', 'initiative', 'decision'
            )
            AND NULLIF(BTRIM(consent_recipient_type), '') IS NOT NULL
            AND NULLIF(BTRIM(consent_version), '') IS NOT NULL
            AND (
                (consent_scope_type IN ('network', 'location') AND consent_scope_id IS NULL)
                OR (consent_scope_type NOT IN ('network', 'location') AND consent_scope_id IS NOT NULL)
            )
        )
    );

CREATE TABLE mobile_form_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id VARCHAR(200) NOT NULL REFERENCES mobile_form(form_id) ON DELETE RESTRICT,
    version VARCHAR(50) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT,
    form_schema JSONB NOT NULL,
    ui_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    collection_type VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id),
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    min_app_version VARCHAR(50),
    consent_policy_status TEXT NOT NULL
        CHECK (consent_policy_status IN ('unclassified', 'required', 'not_required')),
    consent_data_category TEXT,
    consent_purpose TEXT,
    consent_scope_type TEXT,
    consent_scope_id UUID,
    consent_recipient_type TEXT,
    consent_recipient_party_id UUID REFERENCES party(id),
    consent_recipient_name TEXT,
    consent_version TEXT,
    consent_policy_reviewed_by TEXT,
    consent_policy_reviewed_at TIMESTAMPTZ,
    consent_policy_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('active', 'retired', 'inactive')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (form_id, version),
    CONSTRAINT chk_mobile_form_version_required_policy CHECK (
        consent_policy_status <> 'required'
        OR (
            NULLIF(BTRIM(consent_policy_reviewed_by), '') IS NOT NULL
            AND consent_policy_reviewed_at IS NOT NULL
            AND CASE WHEN jsonb_typeof(consent_policy_evidence) = 'array'
                     THEN jsonb_array_length(consent_policy_evidence) > 0 ELSE FALSE END
            AND NULLIF(BTRIM(consent_data_category), '') IS NOT NULL
            AND NULLIF(BTRIM(consent_purpose), '') IS NOT NULL
            AND consent_scope_type IN (
                'network', 'organization', 'location', 'farm', 'cooperative',
                'value_stream', 'initiative', 'decision'
            )
            AND NULLIF(BTRIM(consent_recipient_type), '') IS NOT NULL
            AND NULLIF(BTRIM(consent_version), '') IS NOT NULL
            AND (
                (consent_scope_type IN ('network', 'location') AND consent_scope_id IS NULL)
                OR (consent_scope_type NOT IN ('network', 'location') AND consent_scope_id IS NOT NULL)
            )
        )
    ),
    CONSTRAINT chk_mobile_form_version_reviewed_policy CHECK (
        consent_policy_status = 'unclassified'
        OR (
            NULLIF(BTRIM(consent_policy_reviewed_by), '') IS NOT NULL
            AND consent_policy_reviewed_at IS NOT NULL
            AND CASE WHEN jsonb_typeof(consent_policy_evidence) = 'array'
                     THEN jsonb_array_length(consent_policy_evidence) > 0 ELSE FALSE END
        )
    )
);

CREATE INDEX idx_mobile_form_version_visible
    ON mobile_form_version (status, location_id, name);

INSERT INTO mobile_form_version (
    form_id, version, name, description, form_schema, ui_schema,
    collection_type, location_id, is_public, min_app_version,
    consent_policy_status, consent_data_category, consent_purpose,
    consent_scope_type, consent_scope_id, consent_recipient_type,
    consent_recipient_party_id, consent_recipient_name, consent_version,
    consent_policy_reviewed_by, consent_policy_reviewed_at,
    consent_policy_evidence, status, created_by, created_at
)
SELECT
    form_id, version, name, description, form_schema, COALESCE(ui_schema, '{}'::jsonb),
    collection_type, location_id, COALESCE(is_public, FALSE), min_app_version,
    consent_policy_status, consent_data_category, consent_purpose,
    consent_scope_type, consent_scope_id, consent_recipient_type,
    consent_recipient_party_id, consent_recipient_name, consent_version,
    consent_policy_reviewed_by, consent_policy_reviewed_at,
    consent_policy_evidence,
    CASE
        WHEN status = 'active' THEN 'active'
        WHEN status = 'retired' THEN 'retired'
        ELSE 'inactive'
    END,
    'schema:381-backfill',
    created_at
FROM mobile_form;

CREATE FUNCTION protect_mobile_form_version_content()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'mobile form revisions cannot be deleted';
    END IF;
    IF ROW(
        NEW.id, NEW.form_id, NEW.version, NEW.name, NEW.description,
        NEW.form_schema, NEW.ui_schema, NEW.collection_type, NEW.location_id,
        NEW.is_public, NEW.min_app_version, NEW.consent_policy_status,
        NEW.consent_data_category, NEW.consent_purpose, NEW.consent_scope_type,
        NEW.consent_scope_id, NEW.consent_recipient_type,
        NEW.consent_recipient_party_id, NEW.consent_recipient_name,
        NEW.consent_version, NEW.consent_policy_reviewed_by,
        NEW.consent_policy_reviewed_at, NEW.consent_policy_evidence,
        NEW.created_by, NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.form_id, OLD.version, OLD.name, OLD.description,
        OLD.form_schema, OLD.ui_schema, OLD.collection_type, OLD.location_id,
        OLD.is_public, OLD.min_app_version, OLD.consent_policy_status,
        OLD.consent_data_category, OLD.consent_purpose, OLD.consent_scope_type,
        OLD.consent_scope_id, OLD.consent_recipient_type,
        OLD.consent_recipient_party_id, OLD.consent_recipient_name,
        OLD.consent_version, OLD.consent_policy_reviewed_by,
        OLD.consent_policy_reviewed_at, OLD.consent_policy_evidence,
        OLD.created_by, OLD.created_at
    ) THEN
        RAISE EXCEPTION 'mobile form revision content is immutable; publish a new version';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
        (OLD.status = 'active' AND NEW.status IN ('retired', 'inactive'))
        OR (OLD.status = 'inactive' AND NEW.status = 'active')
    ) THEN
        RAISE EXCEPTION 'mobile form revision status transition is not allowed';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_mobile_form_version_content
BEFORE UPDATE OR DELETE ON mobile_form_version
FOR EACH ROW EXECUTE FUNCTION protect_mobile_form_version_content();

CREATE FUNCTION guard_mobile_form_revision_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.form_id IS DISTINCT FROM OLD.form_id THEN
            RAISE EXCEPTION 'mobile form IDs are immutable';
        END IF;
        IF NEW.version = OLD.version AND ROW(
            NEW.name, NEW.description, NEW.form_schema, NEW.ui_schema,
            NEW.collection_type, NEW.location_id, NEW.is_public, NEW.min_app_version,
            NEW.consent_policy_status, NEW.consent_data_category, NEW.consent_purpose,
            NEW.consent_scope_type, NEW.consent_scope_id, NEW.consent_recipient_type,
            NEW.consent_recipient_party_id, NEW.consent_recipient_name,
            NEW.consent_version, NEW.consent_policy_reviewed_by,
            NEW.consent_policy_reviewed_at, NEW.consent_policy_evidence
        ) IS DISTINCT FROM ROW(
            OLD.name, OLD.description, OLD.form_schema, OLD.ui_schema,
            OLD.collection_type, OLD.location_id, OLD.is_public, OLD.min_app_version,
            OLD.consent_policy_status, OLD.consent_data_category, OLD.consent_purpose,
            OLD.consent_scope_type, OLD.consent_scope_id, OLD.consent_recipient_type,
            OLD.consent_recipient_party_id, OLD.consent_recipient_name,
            OLD.consent_version, OLD.consent_policy_reviewed_by,
            OLD.consent_policy_reviewed_at, OLD.consent_policy_evidence
        ) THEN
            RAISE EXCEPTION 'mobile form content or consent policy changed without a new version';
        END IF;
        IF NEW.version IS DISTINCT FROM OLD.version AND EXISTS (
            SELECT 1 FROM mobile_form_version
             WHERE form_id = NEW.form_id AND version = NEW.version
        ) THEN
            RAISE EXCEPTION 'mobile form revision version already exists';
        END IF;
    END IF;
    IF TG_OP = 'INSERT' AND EXISTS (
        SELECT 1 FROM mobile_form_version
         WHERE form_id = NEW.form_id AND version = NEW.version
    ) THEN
        RAISE EXCEPTION 'mobile form revision version already exists';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_mobile_form_revision_update
BEFORE INSERT OR UPDATE ON mobile_form
FOR EACH ROW EXECUTE FUNCTION guard_mobile_form_revision_update();

CREATE FUNCTION snapshot_mobile_form_revision()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    revision_status TEXT;
    actor TEXT;
BEGIN
    actor := COALESCE(NULLIF(current_setting('kokonut.actor', TRUE), ''), 'mobile_form_maintenance');
    revision_status := CASE
        WHEN NEW.status = 'active' THEN 'active'
        WHEN NEW.status = 'retired' THEN 'retired'
        ELSE 'inactive'
    END;
    IF TG_OP = 'UPDATE' AND NEW.version = OLD.version THEN
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            UPDATE mobile_form_version
               SET status = revision_status
             WHERE form_id = NEW.form_id AND version = NEW.version;
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        UPDATE mobile_form_version
           SET status = 'retired'
         WHERE form_id = OLD.form_id AND version = OLD.version AND status = 'active';
    END IF;
    INSERT INTO mobile_form_version (
        form_id, version, name, description, form_schema, ui_schema,
        collection_type, location_id, is_public, min_app_version,
        consent_policy_status, consent_data_category, consent_purpose,
        consent_scope_type, consent_scope_id, consent_recipient_type,
        consent_recipient_party_id, consent_recipient_name, consent_version,
        consent_policy_reviewed_by, consent_policy_reviewed_at,
        consent_policy_evidence, status, created_by
    ) VALUES (
        NEW.form_id, NEW.version, NEW.name, NEW.description, NEW.form_schema,
        COALESCE(NEW.ui_schema, '{}'::jsonb), NEW.collection_type,
        NEW.location_id, COALESCE(NEW.is_public, FALSE), NEW.min_app_version,
        NEW.consent_policy_status, NEW.consent_data_category, NEW.consent_purpose,
        NEW.consent_scope_type, NEW.consent_scope_id, NEW.consent_recipient_type,
        NEW.consent_recipient_party_id, NEW.consent_recipient_name,
        NEW.consent_version, NEW.consent_policy_reviewed_by,
        NEW.consent_policy_reviewed_at, NEW.consent_policy_evidence,
        revision_status, actor
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_snapshot_mobile_form_revision
AFTER INSERT OR UPDATE ON mobile_form
FOR EACH ROW EXECUTE FUNCTION snapshot_mobile_form_revision();

CREATE TABLE mobile_participant_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_ref_hash CHAR(64) NOT NULL UNIQUE
        CHECK (participant_ref_hash ~ '^[0-9a-f]{64}$'),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence JSONB NOT NULL CHECK (
        jsonb_typeof(evidence) = 'object' AND evidence <> '{}'::jsonb
    ),
    revoked_by TEXT,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT chk_mobile_participant_link_revocation CHECK (
        (revoked_at IS NULL) = (revoked_by IS NULL)
    )
);

CREATE UNIQUE INDEX uq_mobile_participant_link_active_party_location
    ON mobile_participant_link (party_id, location_id)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_mobile_participant_link_location_active
    ON mobile_participant_link (location_id, created_at DESC)
    WHERE revoked_at IS NULL;

CREATE FUNCTION protect_mobile_participant_link()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'mobile participant links cannot be deleted';
    END IF;
    IF ROW(
        NEW.id, NEW.participant_ref_hash, NEW.party_id, NEW.location_id,
        NEW.created_by, NEW.created_at, NEW.evidence
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.participant_ref_hash, OLD.party_id, OLD.location_id,
        OLD.created_by, OLD.created_at, OLD.evidence
    ) THEN
        RAISE EXCEPTION 'mobile participant link identity is immutable';
    END IF;
    IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL OR NEW.revoked_by IS NULL THEN
        RAISE EXCEPTION 'mobile participant link may only be revoked once';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_mobile_participant_link
BEFORE UPDATE OR DELETE ON mobile_participant_link
FOR EACH ROW EXECUTE FUNCTION protect_mobile_participant_link();

ALTER TABLE offline_collection
    ADD COLUMN form_revision_id UUID REFERENCES mobile_form_version(id) ON DELETE RESTRICT,
    ADD COLUMN participant_link_id UUID REFERENCES mobile_participant_link(id) ON DELETE RESTRICT,
    ADD COLUMN consent_event_id_at_collection UUID REFERENCES stakeholder_consent(id) ON DELETE RESTRICT,
    ADD COLUMN consent_event_id_at_sync UUID REFERENCES stakeholder_consent(id) ON DELETE RESTRICT,
    ADD COLUMN form_validation_status TEXT NOT NULL DEFAULT 'unassessed'
        CHECK (form_validation_status IN ('unassessed', 'active', 'retired_review')),
    ADD COLUMN consent_validation_status TEXT NOT NULL DEFAULT 'unassessed'
        CHECK (consent_validation_status IN ('unassessed', 'not_required', 'granted')),
    ADD COLUMN form_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN consent_validated_at TIMESTAMPTZ;

CREATE INDEX idx_offline_collection_form_revision
    ON offline_collection (form_revision_id, collected_at DESC);
CREATE INDEX idx_offline_collection_participant_link
    ON offline_collection (participant_link_id, collected_at DESC)
    WHERE participant_link_id IS NOT NULL;

CREATE VIEW v_mobile_collection_use_eligibility AS
SELECT
    oc.id AS collection_id,
    oc.location_id,
    oc.form_id,
    oc.form_version,
    oc.form_validation_status,
    oc.consent_validation_status,
    oc.form_review_required,
    CASE
        WHEN oc.sync_status <> 'synced' THEN FALSE
        WHEN oc.form_validation_status <> 'active' OR oc.form_review_required THEN FALSE
        WHEN oc.participant_link_id IS NOT NULL AND participant.revoked_at IS NOT NULL THEN FALSE
        WHEN oc.consent_validation_status = 'not_required' THEN TRUE
        WHEN oc.consent_validation_status <> 'granted'
             OR oc.form_revision_id IS NULL OR oc.participant_link_id IS NULL
             OR oc.consent_event_id_at_collection IS NULL THEN FALSE
        WHEN collection_decision.event_type IS DISTINCT FROM 'grant'
             OR collection_decision.party_id IS DISTINCT FROM participant.party_id
             OR collection_decision.data_category IS DISTINCT FROM revision.consent_data_category
             OR collection_decision.purpose IS DISTINCT FROM revision.consent_purpose
             OR collection_decision.scope_type IS DISTINCT FROM revision.consent_scope_type
             OR collection_decision.scope_id IS DISTINCT FROM CASE
                 WHEN revision.consent_scope_type = 'location' THEN oc.location_id
                 ELSE revision.consent_scope_id
             END
             OR collection_decision.recipient_party_id IS DISTINCT FROM revision.consent_recipient_party_id
             OR collection_decision.recipient_type IS DISTINCT FROM revision.consent_recipient_type
             OR collection_decision.consent_version IS DISTINCT FROM revision.consent_version
             OR collection_decision.effective_at > oc.collected_at
             OR (collection_decision.expires_at IS NOT NULL
                 AND collection_decision.expires_at <= oc.collected_at) THEN FALSE
        WHEN collection_decision.expires_at IS NOT NULL
             AND collection_decision.expires_at <= NOW() THEN FALSE
        WHEN current_decision.event_type IS DISTINCT FROM 'grant' THEN FALSE
        WHEN current_decision.expires_at IS NOT NULL AND current_decision.expires_at <= NOW() THEN FALSE
        WHEN EXISTS (
            SELECT 1
              FROM stakeholder_consent revoked
             WHERE revoked.party_id = participant.party_id
               AND revoked.data_category = revision.consent_data_category
               AND revoked.purpose = revision.consent_purpose
               AND revoked.scope_type = revision.consent_scope_type
               AND revoked.scope_id IS NOT DISTINCT FROM CASE
                   WHEN revision.consent_scope_type = 'location' THEN oc.location_id
                   ELSE revision.consent_scope_id
               END
               AND revoked.recipient_party_id IS NOT DISTINCT FROM revision.consent_recipient_party_id
               AND revoked.recipient_type = revision.consent_recipient_type
               AND revoked.consent_version = revision.consent_version
               AND revoked.event_type IN ('withdraw', 'deny', 'expire')
               AND revoked.effective_at > oc.collected_at
               AND revoked.effective_at <= NOW()
        ) THEN FALSE
        ELSE
            TRUE
    END AS eligible_for_use,
    CASE
        WHEN oc.sync_status <> 'synced' THEN 'transport_pending'
        WHEN oc.form_validation_status <> 'active' OR oc.form_review_required THEN 'review_required'
        WHEN oc.participant_link_id IS NOT NULL AND participant.revoked_at IS NOT NULL THEN 'participant_link_revoked'
        WHEN oc.consent_validation_status = 'unassessed' THEN 'consent_unassessed'
        WHEN oc.consent_validation_status = 'not_required' THEN 'eligible'
        WHEN collection_decision.event_type IS DISTINCT FROM 'grant'
             OR collection_decision.party_id IS DISTINCT FROM participant.party_id
             OR collection_decision.data_category IS DISTINCT FROM revision.consent_data_category
             OR collection_decision.purpose IS DISTINCT FROM revision.consent_purpose
             OR collection_decision.scope_type IS DISTINCT FROM revision.consent_scope_type
             OR collection_decision.scope_id IS DISTINCT FROM CASE
                 WHEN revision.consent_scope_type = 'location' THEN oc.location_id
                 ELSE revision.consent_scope_id
             END
             OR collection_decision.recipient_party_id IS DISTINCT FROM revision.consent_recipient_party_id
             OR collection_decision.recipient_type IS DISTINCT FROM revision.consent_recipient_type
             OR collection_decision.consent_version IS DISTINCT FROM revision.consent_version
             OR collection_decision.effective_at > oc.collected_at
             OR (collection_decision.expires_at IS NOT NULL
                 AND collection_decision.expires_at <= oc.collected_at) THEN 'consent_not_effective_at_collection'
        WHEN collection_decision.expires_at IS NOT NULL
             AND collection_decision.expires_at <= NOW() THEN 'consent_expired_after_collection'
        WHEN current_decision.event_type IS DISTINCT FROM 'grant' THEN 'consent_no_longer_active'
        WHEN current_decision.expires_at IS NOT NULL AND current_decision.expires_at <= NOW() THEN 'consent_expired'
        WHEN EXISTS (
            SELECT 1
              FROM stakeholder_consent revoked
             WHERE revoked.party_id = participant.party_id
               AND revoked.data_category = revision.consent_data_category
               AND revoked.purpose = revision.consent_purpose
               AND revoked.scope_type = revision.consent_scope_type
               AND revoked.scope_id IS NOT DISTINCT FROM CASE
                   WHEN revision.consent_scope_type = 'location' THEN oc.location_id
                   ELSE revision.consent_scope_id
               END
               AND revoked.recipient_party_id IS NOT DISTINCT FROM revision.consent_recipient_party_id
               AND revoked.recipient_type = revision.consent_recipient_type
               AND revoked.consent_version = revision.consent_version
               AND revoked.event_type IN ('withdraw', 'deny', 'expire')
               AND revoked.effective_at > oc.collected_at
               AND revoked.effective_at <= NOW()
        ) THEN 'withdrawn_after_collection'
        ELSE 'eligible'
    END AS eligibility_reason
FROM offline_collection oc
LEFT JOIN mobile_form_version revision ON revision.id = oc.form_revision_id
LEFT JOIN mobile_participant_link participant ON participant.id = oc.participant_link_id
LEFT JOIN stakeholder_consent collection_decision
       ON collection_decision.id = oc.consent_event_id_at_collection
LEFT JOIN LATERAL (
    SELECT sc.event_type, sc.expires_at
      FROM stakeholder_consent sc
     WHERE sc.party_id = participant.party_id
       AND sc.data_category = revision.consent_data_category
       AND sc.purpose = revision.consent_purpose
       AND sc.scope_type = revision.consent_scope_type
       AND sc.scope_id IS NOT DISTINCT FROM CASE
           WHEN revision.consent_scope_type = 'location' THEN oc.location_id
           ELSE revision.consent_scope_id
       END
       AND sc.recipient_party_id IS NOT DISTINCT FROM revision.consent_recipient_party_id
       AND sc.recipient_type = revision.consent_recipient_type
       AND sc.consent_version = revision.consent_version
       AND sc.effective_at <= NOW()
     ORDER BY sc.effective_at DESC, sc.created_at DESC, sc.id DESC
     LIMIT 1
) current_decision ON TRUE;

COMMENT ON VIEW v_mobile_collection_use_eligibility IS
    'Consent-aware prerequisite gate for Field Collector rows; pending transport, legacy/unclassified, and retired revisions are ineligible, and post-collection withdrawal cannot be silently undone. This is not a substitute for governed review/publication.';
COMMENT ON TABLE mobile_participant_link IS
    'Reviewer-created, location-scoped opaque participant references; only SHA-256 digests are stored and revoked mappings remain auditable.';

INSERT INTO schema_version (version, description, applied_by)
VALUES (
    'mobile-consent-form-revisions-v1',
    'Immutable Field Collector revisions, reviewer participant links, and consent validation fields (schema 381)',
    'schema 381'
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
