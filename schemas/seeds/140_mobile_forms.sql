-- ============================================================
-- Kokonut Field Collector v1 forms
-- ============================================================

INSERT INTO mobile_form
    (form_id, name, description, form_schema, ui_schema, version, collection_type, status)
VALUES
    (
        'farm_activity_v1',
        'Farm Activity',
        'Record work completed in the field.',
        '{"type":"object","required":["activity_type","activity_date"],"properties":{"activity_type":{"type":"string","title":"Activity","enum":["planting","weeding","irrigation","pruning","spraying","harvesting","transport","storage","other"]},"activity_date":{"type":"string","title":"Date","format":"date"},"description":{"type":"string","title":"Description"},"labor_hours":{"type":"number","title":"Labor hours","minimum":0},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["activity_type","activity_date","description","labor_hours","notes"]}',
        '1.0.0', 'farm_activity', 'active'
    ),
    (
        'harvest_v1',
        'Harvest Event',
        'Record harvested quantity and quality.',
        '{"type":"object","required":["harvest_date","quantity","unit"],"properties":{"harvest_date":{"type":"string","title":"Date","format":"date"},"crop":{"type":"string","title":"Crop"},"plot":{"type":"string","title":"Plot"},"quantity":{"type":"number","title":"Quantity","minimum":0},"unit":{"type":"string","title":"Unit","enum":["kg","tonnes","bags","bunches","liters","units"]},"quality_grade":{"type":"string","title":"Quality grade","enum":["A","B","C","premium","standard","rejected"]},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["harvest_date","crop","plot","quantity","unit","quality_grade","notes"]}',
        '1.0.0', 'harvest_event', 'active'
    ),
    (
        'expense_v1',
        'Expense',
        'Record a farm expense and optional receipt photo.',
        '{"type":"object","required":["expense_date","category","amount"],"properties":{"expense_date":{"type":"string","title":"Date","format":"date"},"category":{"type":"string","title":"Category","enum":["seeds","fertilizer","pesticide","labor","equipment","transport","irrigation","processing","packaging","marketing","utilities","rent","other"]},"amount":{"type":"number","title":"Amount","minimum":0},"description":{"type":"string","title":"Description"},"vendor":{"type":"string","title":"Vendor"},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["expense_date","category","amount","description","vendor","notes"]}',
        '1.0.0', 'expense_event', 'active'
    ),
    (
        'field_note_v1',
        'Field Note',
        'Capture an observation, issue, or recommendation.',
        '{"type":"object","required":["note_date","content"],"properties":{"note_date":{"type":"string","title":"Date","format":"date"},"note_type":{"type":"string","title":"Note type","enum":["observation","issue","recommendation","weather","pest","general"]},"title":{"type":"string","title":"Title"},"content":{"type":"string","title":"What did you observe?","format":"textarea"},"tags":{"type":"string","title":"Tags"}}}',
        '{"order":["note_date","note_type","title","content","tags"]}',
        '1.0.0', 'field_note', 'active'
    ),
    (
        'soil_sample_v1',
        'Soil Sample',
        'Record a field soil sample and its measurements.',
        '{"type":"object","required":["sample_date"],"properties":{"sample_date":{"type":"string","title":"Date","format":"date"},"depth_cm":{"type":"number","title":"Depth (cm)","minimum":0},"depth_layer":{"type":"string","title":"Depth layer","enum":["topsoil","subsoil","root_zone"]},"ph":{"type":"number","title":"pH","minimum":0,"maximum":14},"organic_matter_pct":{"type":"number","title":"Organic matter (%)","minimum":0,"maximum":100},"texture":{"type":"string","title":"Texture","enum":["sandy","loamy","clay","silty"]},"moisture_pct":{"type":"number","title":"Moisture (%)","minimum":0,"maximum":100},"notes":{"type":"string","title":"Notes","format":"textarea"}}}',
        '{"order":["sample_date","depth_cm","depth_layer","ph","organic_matter_pct","texture","moisture_pct","notes"]}',
        '1.0.0', 'soil_sample', 'active'
    )
ON CONFLICT (form_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    form_schema = EXCLUDED.form_schema,
    ui_schema = EXCLUDED.ui_schema,
    version = EXCLUDED.version,
    collection_type = EXCLUDED.collection_type,
    status = EXCLUDED.status,
    updated_at = NOW();
