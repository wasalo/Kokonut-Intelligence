-- Fail the source transaction if a stable financial outbox key is already
-- occupied by a different projection. Migration 434's enqueue trigger remains
-- create-time only; edits and deletions require a separate reviewed contract.

BEGIN;

GRANT SELECT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_financial_projection_owner;

CREATE OR REPLACE FUNCTION kokonut_security.assert_financial_event_projection()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    projection_type TEXT;
    projection_category TEXT;
    projection_currency TEXT;
    projection_amount NUMERIC(15, 2);
    projection_created_at TIMESTAMPTZ;
    projection_columns JSONB;
    projection_rows JSONB;
    projection_payload JSONB;
    projection_hash TEXT;
    projection_key TEXT;
    existing_source_table TEXT;
    existing_source_id TEXT;
    existing_target_table TEXT;
    existing_columns JSONB;
    existing_rows JSONB;
    existing_payload_hash TEXT;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'financial projection guard only accepts inserts';
    END IF;

    IF TG_TABLE_NAME = 'sales_event' THEN
        projection_type := 'sales';
        projection_category := 'sales';
        projection_amount := NEW.total_amount;
    ELSIF TG_TABLE_NAME = 'expense_event' THEN
        projection_type := 'expense';
        projection_category := NULLIF(BTRIM(NEW.category), '');
        projection_amount := NEW.amount;
    ELSE
        RAISE EXCEPTION 'unsupported financial projection source';
    END IF;

    IF projection_amount IS NULL OR projection_amount = 0 THEN
        RETURN NEW;
    END IF;

    projection_currency := COALESCE(NULLIF(UPPER(BTRIM(NEW.currency)), ''), 'USD');
    projection_created_at := COALESCE(NEW.created_at, statement_timestamp());
    projection_columns := jsonb_build_array(
        'timestamp', 'transaction_id', 'location_id', 'transaction_type',
        'category', 'amount', 'currency', 'amount_usd', 'chain', 'token', 'metadata'
    );
    projection_rows := jsonb_build_array(jsonb_build_array(
        TO_CHAR(
            projection_created_at AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        ),
        NEW.id::TEXT,
        NEW.location_id::TEXT,
        projection_type,
        projection_category,
        projection_amount::TEXT,
        projection_currency,
        CASE WHEN projection_currency = 'USD' THEN projection_amount::TEXT ELSE NULL END,
        NULL,
        NULL,
        jsonb_build_object(
            'source_system', 'postgresql',
            'source_table', TG_TABLE_NAME,
            'projection_version', '1'
        )
    ));
    projection_payload := jsonb_build_object(
        'columns', projection_columns,
        'rows', projection_rows
    );
    projection_hash := ENCODE(
        public.digest(CONVERT_TO(projection_payload::TEXT, 'UTF8'), 'sha256'),
        'hex'
    );
    projection_key := 'financial:' || TG_TABLE_NAME || ':' || NEW.id::TEXT;

    SELECT
        outbox.source_table,
        outbox.source_id,
        outbox.target_table,
        outbox.columns,
        outbox.rows,
        outbox.payload_hash
      INTO
        existing_source_table,
        existing_source_id,
        existing_target_table,
        existing_columns,
        existing_rows,
        existing_payload_hash
      FROM public.clickhouse_outbox AS outbox
     WHERE outbox.event_key = projection_key;

    IF NOT FOUND
       OR existing_source_table IS DISTINCT FROM TG_TABLE_NAME
       OR existing_source_id IS DISTINCT FROM NEW.id::TEXT
       OR existing_target_table IS DISTINCT FROM 'financial_events'
       OR existing_columns IS DISTINCT FROM projection_columns
       OR existing_rows IS DISTINCT FROM projection_rows
       OR existing_payload_hash IS DISTINCT FROM projection_hash THEN
        RAISE EXCEPTION 'financial projection conflicts with an existing outbox event'
            USING ERRCODE = '23505';
    END IF;

    RETURN NEW;
END;
$$;

ALTER FUNCTION kokonut_security.assert_financial_event_projection()
    OWNER TO kokonut_financial_projection_owner;
REVOKE ALL ON FUNCTION kokonut_security.assert_financial_event_projection()
    FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_sales_event_financial_projection_conflict_guard
    ON public.sales_event;
CREATE TRIGGER trg_sales_event_financial_projection_conflict_guard
    AFTER INSERT ON public.sales_event
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.assert_financial_event_projection();

DROP TRIGGER IF EXISTS trg_expense_event_financial_projection_conflict_guard
    ON public.expense_event;
CREATE TRIGGER trg_expense_event_financial_projection_conflict_guard
    AFTER INSERT ON public.expense_event
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.assert_financial_event_projection();

COMMENT ON FUNCTION kokonut_security.assert_financial_event_projection() IS
    'Verifies the same-transaction financial outbox projection is an exact match for its source insert and aborts on missing or conflicting event keys.';

COMMIT;
