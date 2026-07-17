-- ============================================================
-- 308_er_integrity_foundations.sql
-- Enforce consistency across operational parent relationships.
-- ============================================================

CREATE OR REPLACE FUNCTION validate_operational_context()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_location UUID;
    cycle_plot UUID;
    cycle_location UUID;
    harvest_cycle UUID;
    harvest_location UUID;
BEGIN
    IF TG_TABLE_NAME = 'farm' THEN
        IF EXISTS (
            SELECT 1
            FROM crop_cycle cc
            JOIN plot p ON p.id = cc.plot_id
            WHERE p.farm_id = NEW.id
              AND cc.location_id <> NEW.location_id
        ) OR EXISTS (
            SELECT 1
            FROM farm_activity fa
            JOIN plot p ON p.id = fa.plot_id
            WHERE p.farm_id = NEW.id
              AND fa.location_id <> NEW.location_id
        ) THEN
            RAISE EXCEPTION 'farm % location change would invalidate operational ownership', NEW.id;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'plot' THEN
        SELECT f.location_id INTO expected_location
        FROM farm f
        WHERE f.id = NEW.farm_id;
        IF expected_location IS NULL THEN
            RAISE EXCEPTION 'plot % references farm % without a location', NEW.id, NEW.farm_id;
        END IF;
        IF EXISTS (
            SELECT 1 FROM crop_cycle cc
            WHERE cc.plot_id = NEW.id AND cc.location_id <> expected_location
        ) OR EXISTS (
            SELECT 1
            FROM farm_activity fa
            WHERE fa.plot_id = NEW.id AND fa.location_id <> expected_location
        ) THEN
            RAISE EXCEPTION 'plot % change would invalidate operational ownership', NEW.id;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'crop_cycle' THEN
        SELECT p.farm_id, f.location_id INTO cycle_plot, expected_location
        FROM plot p
        JOIN farm f ON f.id = p.farm_id
        WHERE p.id = NEW.plot_id;
        IF cycle_plot IS NULL OR expected_location IS NULL THEN
            RAISE EXCEPTION 'crop cycle % references an invalid plot', NEW.id;
        END IF;
        IF NEW.location_id <> expected_location THEN
            RAISE EXCEPTION 'crop cycle % location does not match its plot', NEW.id;
        END IF;
        IF EXISTS (
            SELECT 1
            FROM harvest_event h
            WHERE h.crop_cycle_id = NEW.id
              AND (h.location_id <> NEW.location_id OR h.plot_id <> NEW.plot_id)
        ) THEN
            RAISE EXCEPTION 'crop cycle % change would invalidate harvest ownership', NEW.id;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME IN ('farm_activity', 'harvest_event', 'expense_event') THEN
        IF NEW.plot_id IS NOT NULL THEN
            SELECT f.location_id INTO expected_location
            FROM plot p
            JOIN farm f ON f.id = p.farm_id
            WHERE p.id = NEW.plot_id;
            IF expected_location IS NULL OR expected_location <> NEW.location_id THEN
                RAISE EXCEPTION '% % location does not match its plot', TG_TABLE_NAME, NEW.id;
            END IF;
        END IF;
        IF NEW.crop_cycle_id IS NOT NULL THEN
            SELECT cc.plot_id, cc.location_id INTO cycle_plot, cycle_location
            FROM crop_cycle cc
            WHERE cc.id = NEW.crop_cycle_id;
            IF cycle_location IS NULL OR cycle_location <> NEW.location_id THEN
                RAISE EXCEPTION '% % location does not match its crop cycle', TG_TABLE_NAME, NEW.id;
            END IF;
            IF NEW.plot_id IS NOT NULL AND cycle_plot <> NEW.plot_id THEN
                RAISE EXCEPTION '% % plot does not match its crop cycle', TG_TABLE_NAME, NEW.id;
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'sales_event' THEN
        IF NEW.crop_cycle_id IS NOT NULL THEN
            SELECT cc.plot_id, cc.location_id INTO cycle_plot, cycle_location
            FROM crop_cycle cc
            WHERE cc.id = NEW.crop_cycle_id;
            IF cycle_location IS NULL OR cycle_location <> NEW.location_id THEN
                RAISE EXCEPTION 'sales event % location does not match its crop cycle', NEW.id;
            END IF;
        END IF;
        IF NEW.harvest_id IS NOT NULL THEN
            SELECT h.crop_cycle_id, h.location_id INTO harvest_cycle, harvest_location
            FROM harvest_event h
            WHERE h.id = NEW.harvest_id;
            IF harvest_location IS NULL OR harvest_location <> NEW.location_id THEN
                RAISE EXCEPTION 'sales event % location does not match its harvest', NEW.id;
            END IF;
            IF NEW.crop_cycle_id IS NOT NULL AND harvest_cycle <> NEW.crop_cycle_id THEN
                RAISE EXCEPTION 'sales event % crop cycle does not match its harvest', NEW.id;
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_farm_operational_context ON farm;
CREATE CONSTRAINT TRIGGER trg_farm_operational_context
AFTER UPDATE OF location_id ON farm
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_plot_operational_context ON plot;
CREATE CONSTRAINT TRIGGER trg_plot_operational_context
AFTER INSERT OR UPDATE OF farm_id ON plot
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_crop_cycle_operational_context ON crop_cycle;
CREATE CONSTRAINT TRIGGER trg_crop_cycle_operational_context
AFTER INSERT OR UPDATE OF plot_id, location_id ON crop_cycle
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_farm_activity_operational_context ON farm_activity;
CREATE CONSTRAINT TRIGGER trg_farm_activity_operational_context
AFTER INSERT OR UPDATE OF plot_id, crop_cycle_id, location_id ON farm_activity
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_harvest_event_operational_context ON harvest_event;
CREATE CONSTRAINT TRIGGER trg_harvest_event_operational_context
AFTER INSERT OR UPDATE OF plot_id, crop_cycle_id, location_id ON harvest_event
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_sales_event_operational_context ON sales_event;
CREATE CONSTRAINT TRIGGER trg_sales_event_operational_context
AFTER INSERT OR UPDATE OF harvest_id, crop_cycle_id, location_id ON sales_event
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

DROP TRIGGER IF EXISTS trg_expense_event_operational_context ON expense_event;
CREATE CONSTRAINT TRIGGER trg_expense_event_operational_context
AFTER INSERT OR UPDATE OF plot_id, crop_cycle_id, location_id ON expense_event
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_operational_context();

-- Validate existing rows before the new triggers can protect future writes.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM crop_cycle cc
        JOIN plot p ON p.id = cc.plot_id
        JOIN farm f ON f.id = p.farm_id
        WHERE cc.location_id <> f.location_id
    ) THEN
        RAISE EXCEPTION 'existing crop_cycle rows contain inconsistent location ownership';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM harvest_event h
        JOIN crop_cycle cc ON cc.id = h.crop_cycle_id
        WHERE h.location_id <> cc.location_id OR h.plot_id <> cc.plot_id
    ) THEN
        RAISE EXCEPTION 'existing harvest_event rows contain inconsistent ownership';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM sales_event s
        JOIN harvest_event h ON h.id = s.harvest_id
        WHERE s.location_id <> h.location_id
           OR (s.crop_cycle_id IS NOT NULL AND s.crop_cycle_id <> h.crop_cycle_id)
    ) THEN
        RAISE EXCEPTION 'existing sales_event rows contain inconsistent harvest ownership';
    END IF;
END;
$$;

COMMENT ON FUNCTION validate_operational_context() IS
    'Rejects operational records whose location, plot, crop cycle, farm, and harvest relationships disagree';
