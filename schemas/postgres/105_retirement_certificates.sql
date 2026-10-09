-- Retirement Certificates: PDF-verified documents for retired carbon credits

-- ============================================================
-- retirement_certificate
-- ============================================================
CREATE TABLE IF NOT EXISTS retirement_certificate (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    retirement_id UUID NOT NULL REFERENCES credit_retirement(id) ON DELETE RESTRICT,
    credit_id UUID NOT NULL REFERENCES carbon_credit(id) ON DELETE RESTRICT,
    credit_class_id UUID REFERENCES credit_class(id),
    credit_batch_id UUID REFERENCES credit_batch(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    certificate_number VARCHAR(50) NOT NULL UNIQUE,
    retired_tonnes NUMERIC(14,4) NOT NULL,
    retirement_reason VARCHAR(100) NOT NULL,
    beneficiary_name VARCHAR(255),
    beneficiary_wallet VARCHAR(42),
    retirement_statement TEXT,
    vintage_year INTEGER,
    methodology VARCHAR(255),
    certificate_html TEXT,
    certificate_cid TEXT,
    certificate_hash VARCHAR(128),
    verification_url TEXT,
    qr_code_data TEXT,
    attestation_uid VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'issued',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    CONSTRAINT chk_cert_status CHECK (status IN ('issued', 'revoked'))
);

CREATE INDEX IF NOT EXISTS idx_rc_retirement ON retirement_certificate(retirement_id);
CREATE INDEX IF NOT EXISTS idx_rc_credit ON retirement_certificate(credit_id);
CREATE INDEX IF NOT EXISTS idx_rc_location ON retirement_certificate(location_id);
CREATE INDEX IF NOT EXISTS idx_rc_number ON retirement_certificate(certificate_number);
CREATE INDEX IF NOT EXISTS idx_rc_status ON retirement_certificate(status);
