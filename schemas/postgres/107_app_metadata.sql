-- Application-level Metadata: Additional off-chain project info for Regen App-style views

-- ============================================================
-- app_project_metadata
-- ============================================================
CREATE TABLE IF NOT EXISTS app_project_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    tagline VARCHAR(500),
    description_short TEXT,
    description_long TEXT,
    cover_image_url TEXT,
    gallery_image_urls TEXT[],
    video_urls TEXT[],
    website_url TEXT,
    twitter_url TEXT,
    instagram_url TEXT,
    facebook_url TEXT,
    linkedin_url TEXT,
    github_url TEXT,
    partner_name VARCHAR(255),
    partner_logo_url TEXT,
    partner_website TEXT,
    categories TEXT[],
    tags TEXT[],
    highlights TEXT[],
    language VARCHAR(10) DEFAULT 'en',
    last_updated_by VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id)
);
