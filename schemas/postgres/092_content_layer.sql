-- ============================================================
-- 092_content_layer.sql — Content/Sensemaking Layer
-- ============================================================

-- 1. Content piece
CREATE TABLE IF NOT EXISTS content_piece (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    author_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    content_type VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    summary TEXT,
    audience VARCHAR(100) DEFAULT 'public',
    evidence_ids UUID[],
    source_references TEXT[],
    sensemaking_score NUMERIC(5,2),
    status VARCHAR(50) DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cp_location ON content_piece(location_id);
CREATE INDEX IF NOT EXISTS cp_author ON content_piece(author_id);
CREATE INDEX IF NOT EXISTS cp_type ON content_piece(content_type);
CREATE INDEX IF NOT EXISTS cp_status ON content_piece(status);

ALTER TABLE content_piece DROP CONSTRAINT IF EXISTS chk_cp_type;
ALTER TABLE content_piece ADD CONSTRAINT chk_cp_type CHECK (content_type IN (
    'narrative', 'report', 'analysis', 'news', 'investigation', 'education', 'other'
));

ALTER TABLE content_piece DROP CONSTRAINT IF EXISTS chk_cp_status;
ALTER TABLE content_piece ADD CONSTRAINT chk_cp_status CHECK (status IN (
    'draft', 'reviewing', 'published', 'archived', 'rejected'
));

-- 2. Content distribution
CREATE TABLE IF NOT EXISTS content_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES content_piece(id) ON DELETE CASCADE,
    channel VARCHAR(100) NOT NULL,
    audience_segment VARCHAR(100),
    reach_count INTEGER DEFAULT 0,
    engagement_count INTEGER DEFAULT 0,
    distributed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS cd_content ON content_distribution(content_id);
CREATE INDEX IF NOT EXISTS cd_channel ON content_distribution(channel);

-- 3. Sensemaking score
CREATE TABLE IF NOT EXISTS sensemaking_score (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES content_piece(id) ON DELETE CASCADE,
    evidence_diversity_score NUMERIC(5,2),
    source_credibility_score NUMERIC(5,2),
    validation_count INTEGER DEFAULT 0,
    challenge_count INTEGER DEFAULT 0,
    composite_score NUMERIC(5,2),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS sms_content ON sensemaking_score(content_id);
