-- ============================================================
-- LLM Chat / Natural Language Interface
-- Chat sessions, messages, intent classification, and
-- structured query generation from natural language.
-- ============================================================

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID REFERENCES location(id),
    user_id         VARCHAR(200),

    -- Session metadata
    title           VARCHAR(300),
    language        VARCHAR(10) DEFAULT 'en',
    context         JSONB DEFAULT '{}',

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    message_count   INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_session_user ON chat_session (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_session_location ON chat_session (location_id);
CREATE INDEX IF NOT EXISTS idx_chat_session_status ON chat_session (status);

-- Chat messages
CREATE TABLE IF NOT EXISTS chat_message (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,

    -- Intent / classification
    intent          VARCHAR(100),
    intent_confidence NUMERIC(3,2),
    entities        JSONB DEFAULT '{}',

    -- Response metadata
    response_time_ms    INTEGER,
    tokens_used         INTEGER,
    model_name          VARCHAR(100),

    -- Sources / citations
    sources         JSONB DEFAULT '[]',
    query_results   JSONB DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_message (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_role ON chat_message (role);
CREATE INDEX IF NOT EXISTS idx_chat_message_intent ON chat_message (intent);

-- Intent definitions
CREATE TABLE IF NOT EXISTS chat_intent (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    examples        JSONB DEFAULT '[]',
    handler         VARCHAR(200),
    required_params JSONB DEFAULT '[]',
    optional_params JSONB DEFAULT '[]',
    risk_level      VARCHAR(20) DEFAULT 'low',
    requires_auth   BOOLEAN DEFAULT FALSE,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE chat_intent
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Query cache (avoid re-running identical queries)
CREATE TABLE IF NOT EXISTS chat_query_cache (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash      VARCHAR(64) NOT NULL UNIQUE,
    intent          VARCHAR(100),
    query_text      TEXT,
    result          JSONB NOT NULL,
    result_summary  TEXT,
    hit_count       INTEGER DEFAULT 1,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_hit_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_query_cache_hash ON chat_query_cache (query_hash);
CREATE INDEX IF NOT EXISTS idx_chat_query_cache_intent ON chat_query_cache (intent);

-- Feedback on responses
CREATE TABLE IF NOT EXISTS chat_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    rating          INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_type   VARCHAR(50) DEFAULT 'thumbs',
    comment         TEXT,
    user_id         VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_feedback_message ON chat_feedback (message_id);

-- ============================================================
-- Default Intent Definitions
-- ============================================================

DO $$
BEGIN
    INSERT INTO chat_intent (name, description, examples, handler, required_params, optional_params, risk_level) VALUES
        ('get_yield', 'Get yield data for a crop or location', '["What was the maize yield last season?", "How much did we harvest?"]', 'handle_yield_query', '["location_id"]', '["crop_name", "date_range"]', 'low'),
        ('get_weather', 'Get current or forecast weather', '["What is the weather forecast?", "Will it rain tomorrow?"]', 'handle_weather_query', '["location_id"]', '["forecast_days"]', 'low'),
        ('get_soil', 'Get soil health data', '["What is the soil moisture?", "How is the soil nitrogen?"]', 'handle_soil_query', '["location_id"]', '["metric", "date_range"]', 'low'),
        ('get_crisp', 'Get CRISP risk scores', '["What is our CRISP score?", "How is our climate risk?"]', 'handle_crisp_query', '["location_id"]', '["dimension"]', 'low'),
        ('get_advisory', 'Get pending advisory recommendations', '["What should I do today?", "Any alerts?"]', 'handle_advisory_query', '["location_id"]', '[]', 'low'),
        ('compare_seasons', 'Compare yield or metrics across seasons', '["How does this season compare to last?", "Show yield trends"]', 'handle_comparison_query', '["location_id"]', '["crop_name", "metric"]', 'low'),
        ('estimate_cost', 'Estimate input or operation costs', '["How much will fertilizer cost?", "Estimate irrigation cost"]', 'handle_cost_query', '["location_id"]', '["input_type", "area_ha"]', 'low'),
        ('digital_twin', 'Run or query digital twin simulation', '["Simulate with more irrigation", "What if we increase nitrogen?"]', 'handle_twin_query', '["location_id"]', '["scenario_params"]', 'medium')
    ON CONFLICT (name) DO UPDATE SET
        description = EXCLUDED.description,
        examples = EXCLUDED.examples,
        updated_at = NOW();
END $$;

-- ============================================================
-- Public Views
-- ============================================================

CREATE OR REPLACE VIEW v_chat_session_summary AS
SELECT
    cs.id,
    cs.user_id,
    cs.location_id,
    cs.title,
    cs.message_count,
    cs.started_at,
    cs.last_message_at,
    (SELECT COUNT(*) FROM chat_message cm WHERE cm.session_id = cs.id AND cm.role = 'user') AS user_messages,
    (SELECT AVG(cm.response_time_ms) FROM chat_message cm WHERE cm.session_id = cs.id AND cm.role = 'assistant') AS avg_response_ms,
    cs.status
FROM chat_session cs
ORDER BY cs.last_message_at DESC NULLS LAST;

CREATE OR REPLACE VIEW v_chat_intent_usage AS
SELECT
    cm.intent,
    COUNT(*) AS usage_count,
    AVG(cm.intent_confidence) AS avg_confidence,
    AVG(cm.response_time_ms) AS avg_response_ms,
    MAX(cm.created_at) AS last_used
FROM chat_message cm
WHERE cm.intent IS NOT NULL
GROUP BY cm.intent
ORDER BY usage_count DESC;

CREATE OR REPLACE VIEW v_chat_feedback_summary AS
SELECT
    cf.feedback_type,
    AVG(cf.rating) AS avg_rating,
    COUNT(*) AS total_feedback,
    SUM(CASE WHEN cf.rating >= 4 THEN 1 ELSE 0 END) AS positive,
    SUM(CASE WHEN cf.rating <= 2 THEN 1 ELSE 0 END) AS negative
FROM chat_feedback cf
GROUP BY cf.feedback_type;
