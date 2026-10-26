-- Retention policy scope is configurable data. These opaque identifiers do
-- not encode a legal rule or select a retention period.
ALTER TABLE data_retention_policy
    ADD COLUMN jurisdiction_code VARCHAR(100),
    ADD COLUMN purpose_code VARCHAR(100),
    ADD CONSTRAINT data_retention_policy_jurisdiction_code_format
        CHECK (
            jurisdiction_code IS NULL
            OR (
                jurisdiction_code = lower(btrim(jurisdiction_code))
                AND jurisdiction_code ~ '^[a-z0-9][a-z0-9._:-]{0,99}$'
            )
        ),
    ADD CONSTRAINT data_retention_policy_purpose_code_format
        CHECK (
            purpose_code IS NULL
            OR (
                purpose_code = lower(btrim(purpose_code))
                AND purpose_code ~ '^[a-z0-9][a-z0-9._:-]{0,99}$'
            )
        );

COMMENT ON COLUMN data_retention_policy.jurisdiction_code IS
    'Owner-defined jurisdiction scope code; no legal duration is implied.';
COMMENT ON COLUMN data_retention_policy.purpose_code IS
    'Owner-defined processing-purpose scope code; no legal duration is implied.';
