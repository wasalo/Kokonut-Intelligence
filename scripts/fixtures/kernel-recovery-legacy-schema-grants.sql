-- Reviewed legacy compatibility grants; isolated recovery rehearsal only.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='10s';
DO $$ BEGIN
 IF current_database() <> 'kokonut_intelligence' OR current_user <> 'kokonut' THEN
  RAISE EXCEPTION 'Unexpected recovery database or operator';
 END IF;
END $$;
GRANT ALL ON SCHEMA kokonut TO kokonut;
GRANT ALL ON SCHEMA public TO kokonut;
COMMIT;
