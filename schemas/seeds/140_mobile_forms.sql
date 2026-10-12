-- ============================================================
-- Kokonut Field Collector v1 forms
-- ============================================================

INSERT INTO mobile_form
    (form_id, name, description, form_schema, ui_schema, version, collection_type, status,
     consent_policy_status, consent_data_category, consent_purpose, consent_scope_type,
     consent_scope_id, consent_recipient_type, consent_recipient_party_id,
     consent_recipient_name, consent_version, consent_policy_reviewed_by,
     consent_policy_reviewed_at, consent_policy_evidence)
VALUES
    (
        'farm_activity_v1',
        'Farm Activity',
        'Record location-scoped field work and aggregate labor hours. Do not include worker names or person-specific evaluations.',
        '{"type":"object","required":["activity_type","activity_date"],"properties":{"activity_type":{"type":"string","title":"Activity","enum":["planting","weeding","irrigation","pruning","spraying","harvesting","transport","storage","other"]},"activity_date":{"type":"string","title":"Date","format":"date"},"description":{"type":"string","title":"Description"},"labor_hours":{"type":"number","title":"Labor hours","minimum":0},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["activity_type","activity_date","description","labor_hours","notes"]}',
        '1.1.0', 'farm_activity', 'active',
        'not_required', 'farm_operations',
        'Location-scoped operational activity tracking and aggregate labor planning.',
        'location', NULL, 'location_operator', NULL,
        'Authorized operators of the enrolled farm location', NULL,
        'Codex agent (classification delegated by repository owner)',
        TIMESTAMPTZ '2026-10-12 00:11:55-04:00',
        $farm_activity_evidence$[
          {"source":"schemas/seeds/140_mobile_forms.sql#farm_activity_v1","basis":"The fields describe location-scoped farm work and aggregate labor hours; no participant identity is collected."},
          {"source":"docs/field-data-collection-guide.md","basis":"Mobile rows remain private until governed downstream eligibility and review."},
          {"source":"repository-owner delegation, 2026-10-12","basis":"The repository owner explicitly delegated the form-policy judgment to the implementation agent."}
        ]$farm_activity_evidence$::jsonb
    ),
    (
        'harvest_v1',
        'Harvest Event',
        'Record harvested quantity and quality for this location. Keep notes operational and do not include personal details.',
        '{"type":"object","required":["harvest_date","quantity","unit"],"properties":{"harvest_date":{"type":"string","title":"Date","format":"date"},"crop":{"type":"string","title":"Crop"},"plot":{"type":"string","title":"Plot"},"quantity":{"type":"number","title":"Quantity","minimum":0},"unit":{"type":"string","title":"Unit","enum":["kg","tonnes","bags","bunches","liters","units"]},"quality_grade":{"type":"string","title":"Quality grade","enum":["A","B","C","premium","standard","rejected"]},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["harvest_date","crop","plot","quantity","unit","quality_grade","notes"]}',
        '1.1.0', 'harvest_event', 'active',
        'not_required', 'farm_production',
        'Location-scoped crop harvest quantity and quality tracking.',
        'location', NULL, 'location_operator', NULL,
        'Authorized operators of the enrolled farm location', NULL,
        'Codex agent (classification delegated by repository owner)',
        TIMESTAMPTZ '2026-10-12 00:11:55-04:00',
        $harvest_evidence$[
          {"source":"schemas/seeds/140_mobile_forms.sql#harvest_v1","basis":"The fields describe crop, plot, harvested quantity, unit, and quality; no participant identity is collected."},
          {"source":"docs/field-data-collection-guide.md","basis":"Mobile rows remain private until governed downstream eligibility and review."},
          {"source":"repository-owner delegation, 2026-10-12","basis":"The repository owner explicitly delegated the form-policy judgment to the implementation agent."}
        ]$harvest_evidence$::jsonb
    ),
    (
        'expense_v1',
        'Expense',
        'Record a farm business expense and related receipt. Do not upload personal receipts or include private payment or account data.',
        '{"type":"object","required":["expense_date","category","amount"],"properties":{"expense_date":{"type":"string","title":"Date","format":"date"},"category":{"type":"string","title":"Category","enum":["seeds","fertilizer","pesticide","labor","equipment","transport","irrigation","processing","packaging","marketing","utilities","rent","other"]},"amount":{"type":"number","title":"Amount","minimum":0},"description":{"type":"string","title":"Description"},"vendor":{"type":"string","title":"Vendor"},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["expense_date","category","amount","description","vendor","notes"]}',
        '1.1.0', 'expense_event', 'active',
        'not_required', 'farm_finance',
        'Location-scoped farm operating expense and business receipt accounting.',
        'location', NULL, 'location_operator', NULL,
        'Authorized operators of the enrolled farm location', NULL,
        'Codex agent (classification delegated by repository owner)',
        TIMESTAMPTZ '2026-10-12 00:11:55-04:00',
        $expense_evidence$[
          {"source":"schemas/seeds/140_mobile_forms.sql#expense_v1","basis":"The fields describe farm business expense categories, amounts, vendors, and optional business receipts; no participant identity is collected."},
          {"source":"docs/field-data-collection-guide.md","basis":"Mobile rows remain private until governed downstream eligibility and review."},
          {"source":"repository-owner delegation, 2026-10-12","basis":"The repository owner explicitly delegated the form-policy judgment to the implementation agent."}
        ]$expense_evidence$::jsonb
    ),
    (
        'field_note_v1',
        'Field Note',
        'Capture an operational or ecological observation for this location. Do not record person-centered, health, contact, disciplinary, or other sensitive personal details; use a separately consent-reviewed workflow for those records.',
        '{"type":"object","required":["note_date","content"],"properties":{"note_date":{"type":"string","title":"Date","format":"date"},"note_type":{"type":"string","title":"Note type","enum":["observation","issue","recommendation","weather","pest","general"]},"title":{"type":"string","title":"Title"},"content":{"type":"string","title":"What did you observe?","format":"textarea"},"tags":{"type":"string","title":"Tags"}}}',
        '{"order":["note_date","note_type","title","content","tags"]}',
        '1.1.0', 'field_note', 'active',
        'not_required', 'field_observation',
        'Location-scoped ecological and operational observations, excluding person-centered records.',
        'location', NULL, 'location_operator', NULL,
        'Authorized operators of the enrolled farm location', NULL,
        'Codex agent (classification delegated by repository owner)',
        TIMESTAMPTZ '2026-10-12 00:11:55-04:00',
        $field_note_evidence$[
          {"source":"schemas/seeds/140_mobile_forms.sql#field_note_v1","basis":"The form is intended for operational/ecological observations; person-centered records are excluded from this collection purpose."},
          {"source":"docs/field-data-collection-guide.md","basis":"Community and mobile records remain governed and are not inherently cleared for reporting or publication."},
          {"source":"repository-owner delegation, 2026-10-12","basis":"The repository owner explicitly delegated the form-policy judgment to the implementation agent."}
        ]$field_note_evidence$::jsonb
    ),
    (
        'soil_sample_v1',
        'Soil Sample',
        'Record soil measurements for this location. Notes should describe the sample and site conditions only, not people.',
        '{"type":"object","required":["sample_date"],"properties":{"sample_date":{"type":"string","title":"Date","format":"date"},"depth_cm":{"type":"number","title":"Depth (cm)","minimum":0},"depth_layer":{"type":"string","title":"Depth layer","enum":["topsoil","subsoil","root_zone"]},"ph":{"type":"number","title":"pH","minimum":0,"maximum":14},"organic_matter_pct":{"type":"number","title":"Organic matter (%)","minimum":0,"maximum":100},"texture":{"type":"string","title":"Texture","enum":["sandy","loamy","clay","silty"]},"moisture_pct":{"type":"number","title":"Moisture (%)","minimum":0,"maximum":100},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["sample_date","depth_cm","depth_layer","ph","organic_matter_pct","texture","moisture_pct","notes"]}',
        '1.1.0', 'soil_sample', 'active',
        'not_required', 'soil_quality_measurement',
        'Location-scoped soil sampling and ecological monitoring.',
        'location', NULL, 'location_operator', NULL,
        'Authorized operators of the enrolled farm location', NULL,
        'Codex agent (classification delegated by repository owner)',
        TIMESTAMPTZ '2026-10-12 00:11:55-04:00',
        $soil_sample_evidence$[
          {"source":"schemas/seeds/140_mobile_forms.sql#soil_sample_v1","basis":"The fields describe soil sample depth and environmental measurements; no participant identity is collected."},
          {"source":"docs/field-data-collection-guide.md","basis":"Mobile rows remain private until governed downstream eligibility and review."},
          {"source":"repository-owner delegation, 2026-10-12","basis":"The repository owner explicitly delegated the form-policy judgment to the implementation agent."}
        ]$soil_sample_evidence$::jsonb
    )
ON CONFLICT (form_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    form_schema = EXCLUDED.form_schema,
    ui_schema = EXCLUDED.ui_schema,
    version = EXCLUDED.version,
    collection_type = EXCLUDED.collection_type,
    status = EXCLUDED.status,
    consent_policy_status = EXCLUDED.consent_policy_status,
    consent_data_category = EXCLUDED.consent_data_category,
    consent_purpose = EXCLUDED.consent_purpose,
    consent_scope_type = EXCLUDED.consent_scope_type,
    consent_scope_id = EXCLUDED.consent_scope_id,
    consent_recipient_type = EXCLUDED.consent_recipient_type,
    consent_recipient_party_id = EXCLUDED.consent_recipient_party_id,
    consent_recipient_name = EXCLUDED.consent_recipient_name,
    consent_version = EXCLUDED.consent_version,
    consent_policy_reviewed_by = EXCLUDED.consent_policy_reviewed_by,
    consent_policy_reviewed_at = EXCLUDED.consent_policy_reviewed_at,
    consent_policy_evidence = EXCLUDED.consent_policy_evidence,
    updated_at = NOW();
