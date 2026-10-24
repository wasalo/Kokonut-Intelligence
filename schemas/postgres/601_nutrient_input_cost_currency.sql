-- Make nutrient input costs currency-qualified without guessing historical currencies.

BEGIN;

ALTER TABLE public.nutrient_input
    ADD COLUMN IF NOT EXISTS cost_currency_code VARCHAR(3);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.nutrient_input'::pg_catalog.regclass
           AND conname = 'chk_nutrient_input_cost_currency_code'
    ) THEN
        ALTER TABLE public.nutrient_input
            ADD CONSTRAINT chk_nutrient_input_cost_currency_code
            CHECK (
                cost_currency_code IS NULL
                OR (cost IS NOT NULL AND cost_currency_code ~ '^[A-Z]{3}$')
            );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_nutrient_input_cost_currency()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.cost IS NOT NULL AND NEW.cost_currency_code IS NULL THEN
            RAISE EXCEPTION 'cost_currency_code is required when recording or changing a nutrient input cost'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.cost IS NOT NULL
       AND NEW.cost_currency_code IS NULL
       AND (NEW.cost IS DISTINCT FROM OLD.cost
            OR NEW.cost_currency_code IS DISTINCT FROM OLD.cost_currency_code) THEN
        RAISE EXCEPTION 'cost_currency_code is required when recording or changing a nutrient input cost'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_nutrient_input_cost_currency
    ON public.nutrient_input;
CREATE TRIGGER trg_nutrient_input_cost_currency
    BEFORE INSERT OR UPDATE OF cost, cost_currency_code
    ON public.nutrient_input
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_nutrient_input_cost_currency();

COMMENT ON COLUMN public.nutrient_input.cost_currency_code IS
    'Uppercase three-letter currency code for cost; NULL means no currency was recorded and historical amounts are not comparable.';

CREATE OR REPLACE VIEW public.v_nutrient_input_summary AS
SELECT
    ni.budget_id,
    nb.location_id,
    nb.season,
    nb.crop_name,
    ni.input_type,
    COUNT(*) AS event_count,
    SUM(ni.nitrogen_kg) AS total_nitrogen_kg,
    SUM(ni.phosphorus_kg) AS total_phosphorus_kg,
    SUM(ni.potassium_kg) AS total_potassium_kg,
    SUM(ni.cost) FILTER (WHERE ni.cost_currency_code IS NOT NULL) AS total_cost,
    AVG(ni.application_rate) AS avg_application_rate,
    ni.rate_unit,
    ni.cost_currency_code,
    COUNT(ni.cost) FILTER (WHERE ni.cost_currency_code IS NULL)
        AS unclassified_cost_count
FROM public.nutrient_input AS ni
JOIN public.nutrient_budget AS nb ON nb.id = ni.budget_id
WHERE ni.status IN ('recorded', 'verified')
GROUP BY ni.budget_id, nb.location_id, nb.season, nb.crop_name,
         ni.input_type, ni.rate_unit, ni.cost_currency_code
ORDER BY nb.season, ni.input_type, ni.cost_currency_code;

COMMIT;
