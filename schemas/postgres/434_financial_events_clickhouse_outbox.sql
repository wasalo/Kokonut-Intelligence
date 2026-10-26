-- Replace the Directus-only best-effort financial ClickHouse write with a
-- transactionally coupled PostgreSQL outbox projection. Preserve its create-
-- time event semantics; financial edits/deletions require a separate reviewed
-- correction contract and are not silently converted into duplicate totals.

BEGIN;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_financial_projection_owner'
    ) THEN
        CREATE ROLE kokonut_financial_projection_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_financial_projection_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'financial projection owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_financial_projection_owner'
            OR member_role.rolname = 'kokonut_financial_projection_owner'
    ) THEN
        RAISE EXCEPTION 'financial projection owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_financial_projection_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_financial_projection_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_financial_projection_owner;
GRANT EXECUTE ON FUNCTION public.uuid_generate_v4()
    TO kokonut_financial_projection_owner;
GRANT INSERT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_financial_projection_owner;
GRANT SELECT (event_key) ON public.clickhouse_outbox
    TO kokonut_financial_projection_owner;

-- Keep the bounded owner usable if a later hardening migration enables RLS on
-- the shared outbox. This policy does not grant the login/application roles.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'financial_projection_owner_outbox_insert'
    ) THEN
        EXECUTE 'CREATE POLICY financial_projection_owner_outbox_insert '
             || 'ON public.clickhouse_outbox FOR INSERT '
             || 'TO kokonut_financial_projection_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'financial_projection_owner_outbox_key_read'
    ) THEN
        EXECUTE 'CREATE POLICY financial_projection_owner_outbox_key_read '
             || 'ON public.clickhouse_outbox FOR SELECT '
             || 'TO kokonut_financial_projection_owner USING (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_financial_event_projection()
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
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'financial projection trigger only accepts inserts';
    END IF;

    IF TG_TABLE_NAME = 'sales_event' THEN
        projection_type := 'sales';
        -- The former Directus hook used the transaction type as the sales
        -- category because sales_event has no category column.
        projection_category := 'sales';
        projection_amount := NEW.total_amount;
    ELSIF TG_TABLE_NAME = 'expense_event' THEN
        projection_type := 'expense';
        projection_category := NULLIF(BTRIM(NEW.category), '');
        projection_amount := NEW.amount;
    ELSE
        RAISE EXCEPTION 'unsupported financial projection source';
    END IF;

    -- Match the legacy hook's omission of zero-value rows without inventing a
    -- location UUID or treating non-USD amounts as USD.
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

    INSERT INTO public.clickhouse_outbox (
        event_key, source_table, source_id, target_table,
        columns, rows, payload_hash
    ) VALUES (
        'financial:' || TG_TABLE_NAME || ':' || NEW.id::TEXT,
        TG_TABLE_NAME,
        NEW.id::TEXT,
        'financial_events',
        projection_columns,
        projection_rows,
        projection_hash
    ) ON CONFLICT (event_key) DO NOTHING;

    RETURN NEW;
END;
$$;

ALTER FUNCTION kokonut_security.enqueue_financial_event_projection()
    OWNER TO kokonut_financial_projection_owner;
REVOKE ALL ON FUNCTION kokonut_security.enqueue_financial_event_projection()
    FROM PUBLIC;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_financial_projection_owner;

DROP TRIGGER IF EXISTS trg_sales_event_financial_clickhouse_outbox
    ON public.sales_event;
CREATE TRIGGER trg_sales_event_financial_clickhouse_outbox
    AFTER INSERT ON public.sales_event
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.enqueue_financial_event_projection();

DROP TRIGGER IF EXISTS trg_expense_event_financial_clickhouse_outbox
    ON public.expense_event;
CREATE TRIGGER trg_expense_event_financial_clickhouse_outbox
    AFTER INSERT ON public.expense_event
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.enqueue_financial_event_projection();

COMMENT ON FUNCTION kokonut_security.enqueue_financial_event_projection() IS
    'Atomically enqueues one create-time financial_events mirror row from sales_event or expense_event; ClickHouse delivery remains optional and retryable.';

COMMIT;
