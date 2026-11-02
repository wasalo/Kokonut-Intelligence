-- Bind task/framework-step associations to the shared location of both ends.
-- Existing mismatched historical edges remain NULL for explicit disposition;
-- this migration neither chooses an owner nor deletes association data.
BEGIN;

ALTER TABLE public.farm_task_framework_step
    ADD COLUMN IF NOT EXISTS location_id UUID;

UPDATE public.farm_task_framework_step AS association
   SET location_id = task.location_id
  FROM public.farm_task AS task,
       public.framework_step AS framework_step
 WHERE association.task_id = task.id
   AND association.framework_step_id = framework_step.id
   AND task.location_id = framework_step.location_id
   AND association.location_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conname = 'uq_farm_task_id_location_scope'
           AND conrelid = 'public.farm_task'::regclass
    ) THEN
        ALTER TABLE public.farm_task
            ADD CONSTRAINT uq_farm_task_id_location_scope
            UNIQUE (id, location_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conname = 'uq_framework_step_id_location_scope'
           AND conrelid = 'public.framework_step'::regclass
    ) THEN
        ALTER TABLE public.framework_step
            ADD CONSTRAINT uq_framework_step_id_location_scope
            UNIQUE (id, location_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conname = 'fk_farm_task_framework_step_task_location'
           AND conrelid = 'public.farm_task_framework_step'::regclass
    ) THEN
        ALTER TABLE public.farm_task_framework_step
            ADD CONSTRAINT fk_farm_task_framework_step_task_location
            FOREIGN KEY (task_id, location_id)
            REFERENCES public.farm_task (id, location_id)
            DEFERRABLE INITIALLY DEFERRED NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conname = 'fk_farm_task_framework_step_step_location'
           AND conrelid = 'public.farm_task_framework_step'::regclass
    ) THEN
        ALTER TABLE public.farm_task_framework_step
            ADD CONSTRAINT fk_farm_task_framework_step_step_location
            FOREIGN KEY (framework_step_id, location_id)
            REFERENCES public.framework_step (id, location_id)
            DEFERRABLE INITIALLY DEFERRED NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conname = 'ck_farm_task_framework_step_location_required'
           AND conrelid = 'public.farm_task_framework_step'::regclass
    ) THEN
        ALTER TABLE public.farm_task_framework_step
            ADD CONSTRAINT ck_farm_task_framework_step_location_required
            CHECK (location_id IS NOT NULL) NOT VALID;
    END IF;
END;
$$;

ALTER TABLE public.farm_task_framework_step
    VALIDATE CONSTRAINT fk_farm_task_framework_step_task_location;
ALTER TABLE public.farm_task_framework_step
    VALIDATE CONSTRAINT fk_farm_task_framework_step_step_location;

CREATE OR REPLACE FUNCTION public.enforce_farm_task_framework_step_location()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    task_location_id UUID;
    framework_step_location_id UUID;
BEGIN
    SELECT task.location_id
      INTO task_location_id
      FROM public.farm_task AS task
     WHERE task.id = NEW.task_id;
    IF NOT FOUND OR task_location_id IS NULL THEN
        RAISE EXCEPTION 'farm task association endpoint has no location'
            USING ERRCODE = '23514';
    END IF;

    SELECT framework_step.location_id
      INTO framework_step_location_id
      FROM public.framework_step AS framework_step
     WHERE framework_step.id = NEW.framework_step_id;
    IF NOT FOUND OR framework_step_location_id IS NULL THEN
        RAISE EXCEPTION 'framework step association endpoint has no location'
            USING ERRCODE = '23514';
    END IF;

    IF task_location_id IS DISTINCT FROM framework_step_location_id THEN
        RAISE EXCEPTION 'farm task and framework step must belong to the same location'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.location_id IS NULL THEN
        NEW.location_id := task_location_id;
    ELSIF NEW.location_id IS DISTINCT FROM task_location_id THEN
        RAISE EXCEPTION 'association location must match both endpoints'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.prevent_unresolved_farm_task_framework_step_move()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.location_id IS NOT DISTINCT FROM OLD.location_id THEN
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'farm_task' AND EXISTS (
        SELECT 1
          FROM public.farm_task_framework_step AS association
         WHERE association.task_id = OLD.id
           AND association.location_id IS NULL
    ) THEN
        RAISE EXCEPTION 'resolve or remove unscoped framework-step links before moving a farm task'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'framework_step' AND EXISTS (
        SELECT 1
          FROM public.farm_task_framework_step AS association
         WHERE association.framework_step_id = OLD.id
           AND association.location_id IS NULL
    ) THEN
        RAISE EXCEPTION 'resolve or remove unscoped farm-task links before moving a framework step'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_farm_task_framework_step_location_scope
    ON public.farm_task_framework_step;
CREATE TRIGGER trg_farm_task_framework_step_location_scope
    BEFORE INSERT OR UPDATE OF task_id, framework_step_id, location_id
    ON public.farm_task_framework_step
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_farm_task_framework_step_location();

DROP TRIGGER IF EXISTS trg_farm_task_unresolved_framework_step_move
    ON public.farm_task;
CREATE TRIGGER trg_farm_task_unresolved_framework_step_move
    BEFORE UPDATE OF location_id ON public.farm_task
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_unresolved_farm_task_framework_step_move();

DROP TRIGGER IF EXISTS trg_framework_step_unresolved_farm_task_move
    ON public.framework_step;
CREATE TRIGGER trg_framework_step_unresolved_farm_task_move
    BEFORE UPDATE OF location_id ON public.framework_step
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_unresolved_farm_task_framework_step_move();

COMMENT ON COLUMN public.farm_task_framework_step.location_id IS
    'Shared location of the linked farm_task and framework_step. Existing unresolved legacy links remain NULL until an operator reviews them; new links derive this value when both endpoints agree.';

COMMENT ON TABLE public.farm_task_framework_step IS
    'Location-scoped task-to-framework-step associations. Composite foreign keys enforce matching endpoint locations; unresolved legacy links remain NULL and cannot be edited until reconciled or removed.';

COMMIT;
