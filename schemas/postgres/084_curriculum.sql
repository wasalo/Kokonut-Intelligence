-- ============================================================
-- 084_curriculum.sql — Structured Curriculum
-- ============================================================

-- 1. Training program (top-level curriculum)
CREATE TABLE IF NOT EXISTS training_program (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    program_name VARCHAR(255) NOT NULL,
    description TEXT,
    program_type VARCHAR(100) NOT NULL,
    target_audience TEXT[],
    estimated_duration_hours NUMERIC(8,2),
    prerequisites TEXT[],
    learning_objectives TEXT[],
    certification_available BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_program_type ON training_program(program_type);
CREATE INDEX IF NOT EXISTS idx_program_status ON training_program(status);

ALTER TABLE training_program DROP CONSTRAINT IF EXISTS chk_program_type;
ALTER TABLE training_program ADD CONSTRAINT chk_program_type CHECK (program_type IN (
    'soil_management', 'pest_management', 'harvest_post_harvest',
    'financial_management', 'organic_inputs', 'water_management',
    'agroforestry', 'record_keeping', 'climate_adaptation',
    'cooperative_management', 'digital_literacy', 'other'
));

ALTER TABLE training_program DROP CONSTRAINT IF EXISTS chk_program_status;
ALTER TABLE training_program ADD CONSTRAINT chk_program_status CHECK (status IN ('draft', 'active', 'archived'));

-- 2. Training module (within a program)
CREATE TABLE IF NOT EXISTS training_module (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    program_id UUID NOT NULL REFERENCES training_program(id) ON DELETE CASCADE,
    module_name VARCHAR(255) NOT NULL,
    description TEXT,
    sequence_order INTEGER NOT NULL,
    learning_objectives TEXT[],
    duration_hours NUMERIC(6,2),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_module_program ON training_module(program_id);
CREATE INDEX IF NOT EXISTS idx_module_sequence ON training_module(program_id, sequence_order);

ALTER TABLE training_module DROP CONSTRAINT IF EXISTS chk_module_status;
ALTER TABLE training_module ADD CONSTRAINT chk_module_status CHECK (status IN ('draft', 'active', 'archived'));

-- 3. Training lesson (within a module)
CREATE TABLE IF NOT EXISTS training_lesson (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_id UUID NOT NULL REFERENCES training_module(id) ON DELETE CASCADE,
    lesson_name VARCHAR(255) NOT NULL,
    description TEXT,
    sequence_order INTEGER NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    content_url TEXT,
    duration_minutes INTEGER,
    learning_objectives TEXT[],
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lesson_module ON training_lesson(module_id);
CREATE INDEX IF NOT EXISTS idx_lesson_sequence ON training_lesson(module_id, sequence_order);

ALTER TABLE training_lesson DROP CONSTRAINT IF EXISTS chk_lesson_content_type;
ALTER TABLE training_lesson ADD CONSTRAINT chk_lesson_content_type CHECK (content_type IN (
    'text', 'video', 'audio', 'field_practice', 'quiz', 'demonstration', 'discussion', 'assessment'
));

ALTER TABLE training_lesson DROP CONSTRAINT IF EXISTS chk_lesson_status;
ALTER TABLE training_lesson ADD CONSTRAINT chk_lesson_status CHECK (status IN ('draft', 'active', 'archived'));

-- 4. Training enrollment
CREATE TABLE IF NOT EXISTS training_enrollment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    program_id UUID NOT NULL REFERENCES training_program(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    participant_name VARCHAR(255) NOT NULL,
    participant_role VARCHAR(100),
    staff_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    enrollment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_completion DATE,
    actual_completion DATE,
    status VARCHAR(50) DEFAULT 'enrolled',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrollment_program ON training_enrollment(program_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_location ON training_enrollment(location_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_status ON training_enrollment(status);

ALTER TABLE training_enrollment DROP CONSTRAINT IF EXISTS chk_enrollment_status;
ALTER TABLE training_enrollment ADD CONSTRAINT chk_enrollment_status CHECK (status IN (
    'enrolled', 'in_progress', 'completed', 'dropped', 'suspended'
));

-- 5. Training progress (lesson/module completion)
CREATE TABLE IF NOT EXISTS training_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    enrollment_id UUID NOT NULL REFERENCES training_enrollment(id) ON DELETE CASCADE,
    lesson_id UUID REFERENCES training_lesson(id) ON DELETE SET NULL,
    module_id UUID REFERENCES training_module(id) ON DELETE SET NULL,
    completion_date DATE,
    score NUMERIC(5,2) CHECK (score >= 0 AND score <= 100),
    competency_level VARCHAR(50),
    time_spent_minutes INTEGER,
    training_session_id UUID REFERENCES training_session(id) ON DELETE SET NULL,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_progress_enrollment ON training_progress(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_progress_lesson ON training_progress(lesson_id);
CREATE INDEX IF NOT EXISTS idx_progress_module ON training_progress(module_id);

ALTER TABLE training_progress DROP CONSTRAINT IF EXISTS chk_progress_competency;
ALTER TABLE training_progress ADD CONSTRAINT chk_progress_competency CHECK (competency_level IS NULL OR competency_level IN (
    'not_started', 'beginner', 'intermediate', 'advanced', 'mastered'
));

-- 6. Competency framework
CREATE TABLE IF NOT EXISTS competency_framework (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_id UUID NOT NULL REFERENCES training_module(id) ON DELETE CASCADE,
    competency_name VARCHAR(255) NOT NULL,
    description TEXT,
    assessment_criteria TEXT[],
    passing_score NUMERIC(5,2) DEFAULT 70.0 CHECK (passing_score >= 0 AND passing_score <= 100),
    weight NUMERIC(3,2) DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_competency_module ON competency_framework(module_id);

ALTER TABLE competency_framework DROP CONSTRAINT IF EXISTS chk_competency_status;
ALTER TABLE competency_framework ADD CONSTRAINT chk_competency_status CHECK (status IN ('active', 'archived'));

-- 7. Credential
CREATE TABLE IF NOT EXISTS credential (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    enrollment_id UUID NOT NULL REFERENCES training_enrollment(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES training_program(id) ON DELETE RESTRICT,
    credential_name VARCHAR(255) NOT NULL,
    credential_type VARCHAR(50) NOT NULL,
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date DATE,
    credential_number VARCHAR(100) UNIQUE,
    skills_demonstrated TEXT[],
    verification_url TEXT,
    status VARCHAR(50) DEFAULT 'issued',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credential_enrollment ON credential(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_credential_program ON credential(program_id);
CREATE INDEX IF NOT EXISTS idx_credential_status ON credential(status);

ALTER TABLE credential DROP CONSTRAINT IF EXISTS chk_credential_type;
ALTER TABLE credential ADD CONSTRAINT chk_credential_type CHECK (credential_type IN (
    'program_completion', 'module_completion', 'competency', 'certification', 'attendance'
));

ALTER TABLE credential DROP CONSTRAINT IF EXISTS chk_credential_status;
ALTER TABLE credential ADD CONSTRAINT chk_credential_status CHECK (status IN ('issued', 'revoked', 'expired'));

-- 8. Public views
CREATE OR REPLACE VIEW v_public_training_program_summary AS
SELECT
    tp.id AS program_id,
    tp.program_name,
    tp.program_type,
    tp.description,
    tp.estimated_duration_hours,
    tp.target_audience,
    tp.certification_available,
    (SELECT COUNT(*) FROM training_module tm WHERE tm.program_id = tp.id) AS module_count,
    (SELECT COUNT(*) FROM training_enrollment te WHERE te.program_id = tp.id) AS enrollment_count,
    (SELECT COUNT(*) FROM training_enrollment te WHERE te.program_id = tp.id AND te.status = 'completed') AS completion_count,
    tp.status
FROM training_program tp
WHERE tp.status = 'active';

CREATE OR REPLACE VIEW v_training_progress_summary AS
SELECT
    te.id AS enrollment_id,
    te.participant_name,
    te.participant_role,
    tp.program_name,
    tp.program_type,
    te.enrollment_date,
    te.expected_completion,
    te.status AS enrollment_status,
    COUNT(DISTINCT tp2.lesson_id) AS lessons_completed,
    (SELECT COUNT(*) FROM training_lesson tl JOIN training_module tm ON tl.module_id = tm.id WHERE tm.program_id = tp.id) AS total_lessons,
    CASE
        WHEN (SELECT COUNT(*) FROM training_lesson tl JOIN training_module tm ON tl.module_id = tm.id WHERE tm.program_id = tp.id) > 0
        THEN ROUND(COUNT(DISTINCT tp2.lesson_id)::NUMERIC / (SELECT COUNT(*) FROM training_lesson tl JOIN training_module tm ON tl.module_id = tm.id WHERE tm.program_id = tp.id) * 100, 1)
        ELSE 0
    END AS completion_pct,
    AVG(tp2.score) AS avg_score,
    l.name AS location_name
FROM training_enrollment te
JOIN training_program tp ON tp.id = te.program_id
LEFT JOIN training_progress tp2 ON tp2.enrollment_id = te.id
LEFT JOIN location l ON l.id = te.location_id
GROUP BY te.id, te.participant_name, te.participant_role, tp.program_name, tp.program_type,
         te.enrollment_date, te.expected_completion, te.status, tp.id, l.name;
