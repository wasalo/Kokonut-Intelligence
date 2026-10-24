-- Classify energy costs without guessing historic currencies or aggregating
-- unlike currencies in the legacy reporting surface.

BEGIN;

ALTER TABLE public.energy_reading
    ADD COLUMN IF NOT EXISTS cost_currency_code VARCHAR(3);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.energy_reading'::pg_catalog.regclass
           AND conname = 'chk_energy_reading_cost_currency_code'
    ) THEN
        ALTER TABLE public.energy_reading
            ADD CONSTRAINT chk_energy_reading_cost_currency_code
            CHECK (
                cost_currency_code IS NULL
                OR (
                    cost_currency_code ~ '^[A-Z]{3}$'
                    AND (total_cost IS NOT NULL OR cost_per_kwh IS NOT NULL)
                )
            );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_energy_reading_cost_currency()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (NEW.total_cost IS NOT NULL OR NEW.cost_per_kwh IS NOT NULL)
           AND NEW.cost_currency_code IS NULL THEN
            RAISE EXCEPTION 'cost_currency_code is required when recording or changing an energy cost'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    IF (NEW.total_cost IS NOT NULL OR NEW.cost_per_kwh IS NOT NULL)
       AND NEW.cost_currency_code IS NULL
       AND (NEW.total_cost IS DISTINCT FROM OLD.total_cost
            OR NEW.cost_per_kwh IS DISTINCT FROM OLD.cost_per_kwh
            OR NEW.cost_currency_code IS DISTINCT FROM OLD.cost_currency_code) THEN
        RAISE EXCEPTION 'cost_currency_code is required when recording or changing an energy cost'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_energy_reading_cost_currency
    ON public.energy_reading;
CREATE TRIGGER trg_energy_reading_cost_currency
    BEFORE INSERT OR UPDATE OF total_cost, cost_per_kwh, cost_currency_code
    ON public.energy_reading
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_energy_reading_cost_currency();

COMMENT ON COLUMN public.energy_reading.cost_currency_code IS
    'Uppercase three-letter currency code for energy cost; NULL means no currency was recorded and historical amounts are not comparable.';

-- CREATE OR REPLACE VIEW may append columns, so preserve the established
-- v_energy_consumption column order and add the currency at the end.
CREATE OR REPLACE VIEW public.v_energy_consumption AS
SELECT
    er.location_id,
    l.name AS location_name,
    es.source_name,
    es.source_type,
    er.activity_type,
    er.reading_date,
    er.reading_type,
    er.kwh,
    er.cost_per_kwh,
    er.total_cost,
    er.status,
    er.cost_currency_code
FROM public.energy_reading AS er
JOIN public.location AS l ON l.id = er.location_id
JOIN public.energy_source AS es ON es.id = er.source_id
WHERE er.reading_type = 'consumption';

COMMIT;
