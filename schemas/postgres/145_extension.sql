-- ============================================================
-- 145_extension.sql — Digital Extension Services
-- Content delivery, peer learning, skill assessment, and
-- advisory integration for farmer training and education.
-- ============================================================

-- ============================================================
-- 1. Extension Content Module (topic-organized training)
-- ============================================================
CREATE TABLE IF NOT EXISTS extension_module (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_name     VARCHAR(255) NOT NULL,
    description     TEXT,
    category        VARCHAR(100) NOT NULL,
    difficulty      VARCHAR(50) DEFAULT 'beginner',
    content_type    VARCHAR(50) NOT NULL,
    content_url     TEXT,
    duration_minutes INTEGER,
    language        VARCHAR(50) DEFAULT 'en',
    tags            TEXT[],
    prerequisites   UUID[],
    is_public       BOOLEAN DEFAULT TRUE,
    status          VARCHAR(50) DEFAULT 'draft',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ext_module_category ON extension_module(category);
CREATE INDEX IF NOT EXISTS idx_ext_module_difficulty ON extension_module(difficulty);
CREATE INDEX IF NOT EXISTS idx_ext_module_content_type ON extension_module(content_type);
CREATE INDEX IF NOT EXISTS idx_ext_module_status ON extension_module(status);

ALTER TABLE extension_module DROP CONSTRAINT IF EXISTS chk_ext_module_category;
ALTER TABLE extension_module ADD CONSTRAINT chk_ext_module_category CHECK (category IN (
    'soil_health', 'water_management', 'pest_control', 'post_harvest',
    'financial_literacy', 'agroforestry', 'climate_adaptation',
    'organic_practices', 'record_keeping', 'cooperative_management', 'other'
));

ALTER TABLE extension_module DROP CONSTRAINT IF EXISTS chk_ext_module_difficulty;
ALTER TABLE extension_module ADD CONSTRAINT chk_ext_module_difficulty CHECK (difficulty IN (
    'beginner', 'intermediate', 'advanced'
));

ALTER TABLE extension_module DROP CONSTRAINT IF EXISTS chk_ext_module_content_type;
ALTER TABLE extension_module ADD CONSTRAINT chk_ext_module_content_type CHECK (content_type IN (
    'video', 'guide', 'quiz', 'interactive', 'audio', 'field_practice'
));

ALTER TABLE extension_module DROP CONSTRAINT IF EXISTS chk_ext_module_status;
ALTER TABLE extension_module ADD CONSTRAINT chk_ext_module_status CHECK (status IN (
    'draft', 'active', 'archived'
));

-- ============================================================
-- 2. Farmer Learning Progress
-- ============================================================
CREATE TABLE IF NOT EXISTS learning_progress (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    module_id       UUID NOT NULL REFERENCES extension_module(id) ON DELETE CASCADE,
    farmer_name     VARCHAR(255) NOT NULL,
    progress_pct    NUMERIC(5,2) DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
    score           NUMERIC(5,2) CHECK (score >= 0 AND score <= 100),
    time_spent_min  INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    attempts        INTEGER DEFAULT 1,
    status          VARCHAR(50) DEFAULT 'in_progress',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lp_location ON learning_progress(location_id);
CREATE INDEX IF NOT EXISTS idx_lp_module ON learning_progress(module_id);
CREATE INDEX IF NOT EXISTS idx_lp_status ON learning_progress(status);
CREATE INDEX IF NOT EXISTS idx_lp_farmer ON learning_progress(farmer_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_unique_farmer_module ON learning_progress(location_id, module_id, farmer_name);

ALTER TABLE learning_progress DROP CONSTRAINT IF EXISTS chk_lp_status;
ALTER TABLE learning_progress ADD CONSTRAINT chk_lp_status CHECK (status IN (
    'not_started', 'in_progress', 'completed', 'failed', 'expired'
));

-- ============================================================
-- 3. Peer Learning Network
-- ============================================================
CREATE TABLE IF NOT EXISTS peer_network (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    network_name    VARCHAR(255) NOT NULL,
    description     TEXT,
    network_type    VARCHAR(100) NOT NULL,
    location_id     UUID REFERENCES location(id) ON DELETE SET NULL,
    max_members     INTEGER,
    meeting_cadence VARCHAR(100),
    language        VARCHAR(50) DEFAULT 'en',
    status          VARCHAR(50) DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_peer_type ON peer_network(network_type);
CREATE INDEX IF NOT EXISTS idx_peer_location ON peer_network(location_id);
CREATE INDEX IF NOT EXISTS idx_peer_status ON peer_network(status);

ALTER TABLE peer_network DROP CONSTRAINT IF EXISTS chk_peer_type;
ALTER TABLE peer_network ADD CONSTRAINT chk_peer_type CHECK (network_type IN (
    'learning_group', 'mentorship', 'community_of_practice',
    'farmer_field_school', 'cooperative', 'other'
));

ALTER TABLE peer_network DROP CONSTRAINT IF EXISTS chk_peer_status;
ALTER TABLE peer_network ADD CONSTRAINT chk_peer_status CHECK (status IN (
    'active', 'inactive', 'archived'
));

-- Peer network membership
CREATE TABLE IF NOT EXISTS peer_network_member (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    network_id      UUID NOT NULL REFERENCES peer_network(id) ON DELETE CASCADE,
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farmer_name     VARCHAR(255) NOT NULL,
    role            VARCHAR(100) DEFAULT 'member',
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    left_at         TIMESTAMPTZ,
    status          VARCHAR(50) DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_peer_member_network ON peer_network_member(network_id);
CREATE INDEX IF NOT EXISTS idx_peer_member_location ON peer_network_member(location_id);
CREATE INDEX IF NOT EXISTS idx_peer_member_farmer ON peer_network_member(farmer_name);

ALTER TABLE peer_network_member DROP CONSTRAINT IF EXISTS chk_pnm_role;
ALTER TABLE peer_network_member ADD CONSTRAINT chk_pnm_role CHECK (role IN (
    'member', 'mentor', 'moderator', 'facilitator'
));

ALTER TABLE peer_network_member DROP CONSTRAINT IF EXISTS chk_pnm_status;
ALTER TABLE peer_network_member ADD CONSTRAINT chk_pnm_status CHECK (status IN (
    'active', 'inactive', 'removed'
));

-- ============================================================
-- 4. Content Delivery Tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS content_delivery (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_id       UUID NOT NULL REFERENCES extension_module(id) ON DELETE CASCADE,
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farmer_name     VARCHAR(255) NOT NULL,
    delivery_channel VARCHAR(100) NOT NULL,
    delivery_status VARCHAR(50) NOT NULL DEFAULT 'sent',
    delivered_at    TIMESTAMPTZ,
    viewed_at       TIMESTAMPTZ,
    clicked_at      TIMESTAMPTZ,
    device_type     VARCHAR(100),
    network_type    VARCHAR(50),
    bandwidth_kbps  INTEGER,
    retry_count     INTEGER DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cd_module ON content_delivery(module_id);
CREATE INDEX IF NOT EXISTS idx_cd_location ON content_delivery(location_id);
CREATE INDEX IF NOT EXISTS idx_cd_channel ON content_delivery(delivery_channel);
CREATE INDEX IF NOT EXISTS idx_cd_status ON content_delivery(delivery_status);
CREATE INDEX IF NOT EXISTS idx_cd_farmer ON content_delivery(farmer_name);
CREATE INDEX IF NOT EXISTS idx_cd_delivered ON content_delivery(delivered_at);

ALTER TABLE content_delivery DROP CONSTRAINT IF EXISTS chk_cd_channel;
ALTER TABLE content_delivery ADD CONSTRAINT chk_cd_channel CHECK (delivery_channel IN (
    'sms', 'whatsapp', 'mobile_app', 'video_link', 'audio_broadcast',
    'community_screening', 'print', 'in_person'
));

ALTER TABLE content_delivery DROP CONSTRAINT IF EXISTS chk_cd_status;
ALTER TABLE content_delivery ADD CONSTRAINT chk_cd_status CHECK (delivery_status IN (
    'pending', 'sent', 'delivered', 'viewed', 'clicked', 'failed'
));

-- ============================================================
-- 5. Extension Advisory (linked to training recommendations)
-- ============================================================
CREATE TABLE IF NOT EXISTS extension_advisory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farmer_name     VARCHAR(255) NOT NULL,
    advisory_type   VARCHAR(100) NOT NULL,
    topic           VARCHAR(100) NOT NULL,
    title           VARCHAR(300) NOT NULL,
    message         TEXT NOT NULL,
    recommended_modules UUID[],
    priority        INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    source_context  JSONB DEFAULT '{}',
    status          VARCHAR(50) DEFAULT 'draft',
    read_at         TIMESTAMPTZ,
    acted_at        TIMESTAMPTZ,
    feedback        TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ea_location ON extension_advisory(location_id);
CREATE INDEX IF NOT EXISTS idx_ea_topic ON extension_advisory(topic);
CREATE INDEX IF NOT EXISTS idx_ea_status ON extension_advisory(status);
CREATE INDEX IF NOT EXISTS idx_ea_farmer ON extension_advisory(farmer_name);
CREATE INDEX IF NOT EXISTS idx_ea_priority ON extension_advisory(priority DESC);
CREATE INDEX IF NOT EXISTS idx_ea_type ON extension_advisory(advisory_type);

ALTER TABLE extension_advisory DROP CONSTRAINT IF EXISTS chk_ea_type;
ALTER TABLE extension_advisory ADD CONSTRAINT chk_ea_type CHECK (advisory_type IN (
    'seasonal_alert', 'practice_recommendation', 'training_prompt',
    'pest_warning', 'market_signal', 'water_advisory', 'general'
));

ALTER TABLE extension_advisory DROP CONSTRAINT IF EXISTS chk_ea_topic;
ALTER TABLE extension_advisory ADD CONSTRAINT chk_ea_topic CHECK (topic IN (
    'soil_health', 'water_management', 'pest_control', 'post_harvest',
    'financial_literacy', 'agroforestry', 'climate_adaptation',
    'organic_practices', 'market_access', 'general'
));

ALTER TABLE extension_advisory DROP CONSTRAINT IF EXISTS chk_ea_status;
ALTER TABLE extension_advisory ADD CONSTRAINT chk_ea_status CHECK (status IN (
    'draft', 'sent', 'delivered', 'read', 'acted', 'expired', 'cancelled'
));

-- ============================================================
-- 6. Skill Assessment (pre/post training effectiveness)
-- ============================================================
CREATE TABLE IF NOT EXISTS skill_assessment (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    module_id       UUID NOT NULL REFERENCES extension_module(id) ON DELETE CASCADE,
    farmer_name     VARCHAR(255) NOT NULL,
    assessment_type VARCHAR(50) NOT NULL,
    score           NUMERIC(5,2) CHECK (score >= 0 AND score <= 100),
    max_score       NUMERIC(5,2) DEFAULT 100,
    questions_total INTEGER,
    questions_correct INTEGER,
    time_spent_min  INTEGER,
    assessment_date TIMESTAMPTZ DEFAULT NOW(),
    assessor_name   VARCHAR(255),
    notes           TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sa_location ON skill_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_sa_module ON skill_assessment(module_id);
CREATE INDEX IF NOT EXISTS idx_sa_type ON skill_assessment(assessment_type);
CREATE INDEX IF NOT EXISTS idx_sa_farmer ON skill_assessment(farmer_name);
CREATE INDEX IF NOT EXISTS idx_sa_date ON skill_assessment(assessment_date);

ALTER TABLE skill_assessment DROP CONSTRAINT IF EXISTS chk_sa_type;
ALTER TABLE skill_assessment ADD CONSTRAINT chk_sa_type CHECK (assessment_type IN (
    'pre_test', 'post_test', 'diagnostic', 'self_assessment', 'field_observation'
));

-- ============================================================
-- 7. Public Views
-- ============================================================

-- Available modules with completion rates
CREATE OR REPLACE VIEW v_training_catalog AS
SELECT
    em.id AS module_id,
    em.module_name,
    em.description,
    em.category,
    em.difficulty,
    em.content_type,
    em.duration_minutes,
    em.language,
    em.tags,
    em.status,
    (SELECT COUNT(*) FROM learning_progress lp WHERE lp.module_id = em.id) AS total_enrolled,
    (SELECT COUNT(*) FROM learning_progress lp WHERE lp.module_id = em.id AND lp.status = 'completed') AS total_completed,
    CASE
        WHEN (SELECT COUNT(*) FROM learning_progress lp WHERE lp.module_id = em.id) > 0
        THEN ROUND(
            (SELECT COUNT(*)::NUMERIC FROM learning_progress lp WHERE lp.module_id = em.id AND lp.status = 'completed')
            / (SELECT COUNT(*)::NUMERIC FROM learning_progress lp WHERE lp.module_id = em.id) * 100, 1
        )
        ELSE 0
    END AS completion_rate_pct,
    (SELECT ROUND(AVG(lp.score), 1) FROM learning_progress lp WHERE lp.module_id = em.id AND lp.score IS NOT NULL) AS avg_score
FROM extension_module em
WHERE em.status = 'active';

-- Individual farmer progress and skills
CREATE OR REPLACE VIEW v_farmer_progress AS
SELECT
    lp.id AS progress_id,
    lp.location_id,
    l.name AS location_name,
    lp.farmer_name,
    lp.module_id,
    em.module_name,
    em.category,
    em.difficulty,
    lp.progress_pct,
    lp.score,
    lp.time_spent_min,
    lp.attempts,
    lp.started_at,
    lp.completed_at,
    lp.status,
    (SELECT sa.score FROM skill_assessment sa
     WHERE sa.location_id = lp.location_id AND sa.module_id = lp.module_id
       AND sa.farmer_name = lp.farmer_name AND sa.assessment_type = 'pre_test'
     ORDER BY sa.assessment_date DESC LIMIT 1) AS pre_test_score,
    (SELECT sa.score FROM skill_assessment sa
     WHERE sa.location_id = lp.location_id AND sa.module_id = lp.module_id
       AND sa.farmer_name = lp.farmer_name AND sa.assessment_type = 'post_test'
     ORDER BY sa.assessment_date DESC LIMIT 1) AS post_test_score
FROM learning_progress lp
JOIN extension_module em ON em.id = lp.module_id
LEFT JOIN location l ON l.id = lp.location_id;

-- Training completion and skill improvement metrics
CREATE OR REPLACE VIEW v_extension_effectiveness AS
SELECT
    em.category,
    em.module_name,
    COUNT(DISTINCT lp.id) AS total_enrollments,
    COUNT(DISTINCT CASE WHEN lp.status = 'completed' THEN lp.id END) AS completions,
    ROUND(
        COUNT(DISTINCT CASE WHEN lp.status = 'completed' THEN lp.id END)::NUMERIC
        / NULLIF(COUNT(DISTINCT lp.id), 0) * 100, 1
    ) AS completion_rate_pct,
    ROUND(AVG(CASE WHEN lp.status = 'completed' THEN lp.score END), 1) AS avg_completion_score,
    ROUND(AVG(CASE WHEN lp.status = 'completed' THEN lp.time_spent_min END), 0) AS avg_time_min,
    (SELECT ROUND(AVG(pre.score), 1) FROM skill_assessment pre
     WHERE pre.module_id = em.id AND pre.assessment_type = 'pre_test') AS avg_pre_score,
    (SELECT ROUND(AVG(post.score), 1) FROM skill_assessment post
     WHERE post.module_id = em.id AND post.assessment_type = 'post_test') AS avg_post_score,
    (SELECT ROUND(AVG(post.score) - AVG(pre.score), 1)
     FROM skill_assessment post
     JOIN skill_assessment pre ON pre.location_id = post.location_id
       AND pre.module_id = post.module_id AND pre.farmer_name = post.farmer_name
     WHERE post.module_id = em.id
       AND post.assessment_type = 'post_test' AND pre.assessment_type = 'pre_test') AS avg_skill_improvement
FROM extension_module em
LEFT JOIN learning_progress lp ON lp.module_id = em.id
WHERE em.status = 'active'
GROUP BY em.id, em.category, em.module_name;

-- ============================================================
-- 8. Seed Data — Training Categories
-- ============================================================
INSERT INTO extension_module (module_name, description, category, difficulty, content_type, status) VALUES
    ('Soil Testing Basics', 'How to collect and interpret soil samples for nutrient management', 'soil_health', 'beginner', 'guide', 'active'),
    ('Composting Techniques', 'On-farm composting methods for organic matter improvement', 'soil_health', 'beginner', 'video', 'active'),
    ('Cover Cropping Guide', 'Selecting and managing cover crops for soil restoration', 'soil_health', 'intermediate', 'guide', 'active'),
    ('Irrigation Scheduling', 'Efficient water use through scheduling and monitoring', 'water_management', 'beginner', 'guide', 'active'),
    ('Rainwater Harvesting', 'Designing and maintaining rainwater collection systems', 'water_management', 'beginner', 'video', 'active'),
    ('Drip Irrigation Setup', 'Installing and maintaining low-cost drip irrigation', 'water_management', 'intermediate', 'interactive', 'active'),
    ('Integrated Pest Management', 'Reducing chemical use through biological controls', 'pest_control', 'beginner', 'guide', 'active'),
    ('Organic Pest Solutions', 'Natural remedies and biopesticides for common pests', 'pest_control', 'intermediate', 'video', 'active'),
    ('Scouting & Monitoring', 'Field scouting techniques for early pest detection', 'pest_control', 'beginner', 'guide', 'active'),
    ('Post-Harvest Handling', 'Proper harvesting, cleaning, and storage to reduce loss', 'post_harvest', 'beginner', 'guide', 'active'),
    ('Cold Chain Basics', 'Managing temperature-sensitive crops from field to market', 'post_harvest', 'intermediate', 'video', 'active'),
    ('Value Addition Processing', 'Simple processing techniques to increase product value', 'post_harvest', 'intermediate', 'interactive', 'active'),
    ('Farm Bookkeeping', 'Simple record-keeping methods for smallholder farms', 'financial_literacy', 'beginner', 'guide', 'active'),
    ('Cost-Benefit Analysis', 'Calculating true cost of production per crop cycle', 'financial_literacy', 'intermediate', 'guide', 'active'),
    ('Accessing Credit', 'Understanding loan options and building creditworthiness', 'financial_literacy', 'beginner', 'audio', 'active')
ON CONFLICT DO NOTHING;
