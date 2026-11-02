-- Keep global controlled-vocabulary reads available while routing application
-- mutations through a small, reviewed SECURITY DEFINER contract.
BEGIN;

DO $$
BEGIN
    IF pg_catalog.to_regnamespace('kokonut_security') IS NULL THEN
        RAISE EXCEPTION 'required schema kokonut_security is missing';
    END IF;
    IF pg_catalog.to_regclass('public.thesaurus') IS NULL
       OR pg_catalog.to_regclass('public.thesaurus_keyword') IS NULL
       OR pg_catalog.to_regclass('public.thesaurus_keyword_label') IS NULL THEN
        RAISE EXCEPTION 'required thesaurus relations from migration 114 are missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_thesaurus_owner'
    ) THEN
        CREATE ROLE kokonut_thesaurus_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_thesaurus_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_thesaurus_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_thesaurus_owner'
            OR member_role.rolname = 'kokonut_thesaurus_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_thesaurus_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_thesaurus_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_thesaurus_owner;

-- The owner can perform only the column operations used below. DELETE on the
-- label table is needed only for the existing keyword ON DELETE CASCADE.
GRANT SELECT (id, identifier), INSERT (id, identifier, title, description, language),
      UPDATE (title, description)
    ON public.thesaurus TO kokonut_thesaurus_owner;
GRANT SELECT (id, thesaurus_id),
      INSERT (id, thesaurus_id, keyword_about, alt_label, parent_keyword_id),
      DELETE
    ON public.thesaurus_keyword TO kokonut_thesaurus_owner;
GRANT SELECT (id, keyword_id, language),
      INSERT (id, keyword_id, label, language), UPDATE (label), DELETE
    ON public.thesaurus_keyword_label TO kokonut_thesaurus_owner;

CREATE OR REPLACE FUNCTION kokonut_security.create_thesaurus(
    requested_identifier TEXT,
    requested_title TEXT,
    requested_description TEXT,
    requested_language TEXT
)
RETURNS TABLE(id UUID)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF requested_identifier IS NULL
       OR pg_catalog.length(requested_identifier) > 100
       OR requested_title IS NULL
       OR pg_catalog.length(requested_title) > 255
       OR (requested_language IS NOT NULL
           AND pg_catalog.length(requested_language) > 10) THEN
        RAISE EXCEPTION 'thesaurus fields exceed their schema bounds'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    INSERT INTO public.thesaurus AS target (
        id, identifier, title, description, language
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_identifier, requested_title,
        requested_description, requested_language
    )
    ON CONFLICT (identifier) DO UPDATE
       SET title = EXCLUDED.title,
           description = EXCLUDED.description
    RETURNING target.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.add_thesaurus_keyword(
    requested_thesaurus_id UUID,
    requested_keyword_about TEXT,
    requested_alt_label TEXT,
    requested_parent_keyword_id UUID
)
RETURNS TABLE(id UUID)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF requested_thesaurus_id IS NULL
       OR requested_keyword_about IS NULL
       OR pg_catalog.length(requested_keyword_about) > 255
       OR (requested_alt_label IS NOT NULL
           AND pg_catalog.length(requested_alt_label) > 255) THEN
        RAISE EXCEPTION 'thesaurus keyword fields exceed their schema bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_parent_keyword_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
             FROM public.thesaurus_keyword AS parent
            WHERE parent.id = requested_parent_keyword_id
              AND parent.thesaurus_id = requested_thesaurus_id
       ) THEN
        RAISE EXCEPTION 'parent keyword must belong to the requested thesaurus'
            USING ERRCODE = '23514';
    END IF;

    RETURN QUERY
    INSERT INTO public.thesaurus_keyword AS target (
        id, thesaurus_id, keyword_about, alt_label, parent_keyword_id
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_thesaurus_id,
        requested_keyword_about, requested_alt_label,
        requested_parent_keyword_id
    )
    RETURNING target.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.upsert_thesaurus_keyword_label(
    requested_keyword_id UUID,
    requested_label TEXT,
    requested_language TEXT
)
RETURNS TABLE(id UUID)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF requested_keyword_id IS NULL
       OR requested_label IS NULL
       OR pg_catalog.length(requested_label) > 255
       OR requested_language IS NULL
       OR pg_catalog.length(requested_language) > 10 THEN
        RAISE EXCEPTION 'thesaurus label fields exceed their schema bounds'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    INSERT INTO public.thesaurus_keyword_label AS target (
        id, keyword_id, label, language
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_keyword_id,
        requested_label, requested_language
    )
    ON CONFLICT (keyword_id, language) DO UPDATE
       SET label = EXCLUDED.label
    RETURNING target.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.delete_thesaurus_keyword(
    requested_keyword_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF requested_keyword_id IS NULL THEN
        RETURN FALSE;
    END IF;

    DELETE FROM public.thesaurus_keyword AS target
     WHERE target.id = requested_keyword_id;
    RETURN FOUND;
END;
$$;

ALTER FUNCTION kokonut_security.create_thesaurus(TEXT, TEXT, TEXT, TEXT)
    OWNER TO kokonut_thesaurus_owner;
ALTER FUNCTION kokonut_security.add_thesaurus_keyword(UUID, TEXT, TEXT, UUID)
    OWNER TO kokonut_thesaurus_owner;
ALTER FUNCTION kokonut_security.upsert_thesaurus_keyword_label(UUID, TEXT, TEXT)
    OWNER TO kokonut_thesaurus_owner;
ALTER FUNCTION kokonut_security.delete_thesaurus_keyword(UUID)
    OWNER TO kokonut_thesaurus_owner;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_thesaurus_owner;

REVOKE EXECUTE ON FUNCTION kokonut_security.create_thesaurus(TEXT, TEXT, TEXT, TEXT)
    FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION kokonut_security.add_thesaurus_keyword(UUID, TEXT, TEXT, UUID)
    FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION kokonut_security.upsert_thesaurus_keyword_label(UUID, TEXT, TEXT)
    FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION kokonut_security.delete_thesaurus_keyword(UUID)
    FROM PUBLIC;

-- A Standard fresh install applies schema migrations before creating the
-- runtime login. If that role is not present yet, runtime-role provisioning
-- grants these same four functions after validating the owner boundary.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        GRANT EXECUTE ON FUNCTION
            kokonut_security.create_thesaurus(TEXT, TEXT, TEXT, TEXT)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.add_thesaurus_keyword(UUID, TEXT, TEXT, UUID)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.upsert_thesaurus_keyword_label(UUID, TEXT, TEXT)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.delete_thesaurus_keyword(UUID)
            TO kokonut_runtime;
    END IF;
END;
$$;

DO $$
DECLARE
    target_table TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    runtime_role_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) INTO runtime_role_exists;

    FOREACH target_table IN ARRAY ARRAY[
        'thesaurus', 'thesaurus_keyword', 'thesaurus_keyword_label'
    ] LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', target_table)
        );

        EXECUTE pg_catalog.format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
            'ON TABLE public.%I FROM PUBLIC',
            target_table
        );
        IF runtime_role_exists THEN
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE public.%I FROM kokonut_runtime',
                target_table
            );
        END IF;

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.%2$I FROM PUBLIC',
                column_name,
                target_table
            );
            IF runtime_role_exists THEN
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    target_table
                );
            END IF;
        END LOOP;

        IF runtime_role_exists THEN
            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.thesaurus IS
    'Global controlled vocabulary. kokonut_runtime retains SELECT and may mutate only through bounded kokonut_security functions; tenant isolation is not implied.';
COMMENT ON TABLE public.thesaurus_keyword IS
    'Global controlled vocabulary terms. kokonut_runtime retains SELECT and may mutate only through bounded kokonut_security functions.';
COMMENT ON TABLE public.thesaurus_keyword_label IS
    'Global controlled vocabulary labels. kokonut_runtime retains SELECT and may mutate only through bounded kokonut_security functions.';

COMMIT;
