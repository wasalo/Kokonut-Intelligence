"""Provision Directus' optional DML-only PostgreSQL identity.

Run this one-shot command with the database administrator credentials against a
dedicated Kernel PostgreSQL instance, after the application schema has been
created and before Directus starts. The long-running Directus process must use
the separate runtime credential.
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql

from .runtime_role import _ensure_login_role, _role_identifier, _verify_role_attributes

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_PLACEHOLDER_SECRET = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE)
_APP_SCHEMAS = ("public", "kokonut")
_DIRECTUS_RELATION_POLICY = "kokonut_security.directus_relation_privilege_policy"
_DIRECTUS_POLICY_MODES = frozenset({"read_only", "no_access"})


def _apply_migration_declared_relation_policies(cur, directus_ident: sql.Identifier) -> dict[str, int]:
    """Reapply ordered-migration Directus denials after compatibility grants.

    The provisioner intentionally grants broad collection access for the
    optional Directus adapter. Ordered migrations can narrow that access for
    Kernel-owned workflows. Because this command is idempotent and may run
    again after migrations, the migration-owned policy registry is the source
    of truth for those exceptions.
    """
    cur.execute(
        f"SELECT schema_name, relation_name, access_mode "
        f"FROM {_DIRECTUS_RELATION_POLICY} ORDER BY schema_name, relation_name"
    )
    policies = cur.fetchall()
    seen: set[tuple[str, str]] = set()
    counts = {"read_only": 0, "no_access": 0}
    for schema_name, relation_name, access_mode in policies:
        if (
            schema_name not in _APP_SCHEMAS
            or not isinstance(relation_name, str)
            or not _ROLE_NAME.fullmatch(relation_name)
            or access_mode not in _DIRECTUS_POLICY_MODES
        ):
            raise RuntimeError("Directus relation privilege policy contains an invalid entry")
        key = (schema_name, relation_name)
        if key in seen:
            raise RuntimeError("Directus relation privilege policy contains a duplicate entry")
        seen.add(key)

        relation = sql.Identifier(schema_name, relation_name)
        qualified_name = f"{schema_name}.{relation_name}"
        cur.execute("SELECT pg_catalog.to_regclass(%s)", (qualified_name,))
        relation_oid = cur.fetchone()[0]
        if relation_oid is None:
            raise RuntimeError("Directus relation privilege policy refers to a missing relation")
        cur.execute(
            "SELECT relation.relkind FROM pg_catalog.pg_class AS relation "
            "WHERE relation.oid = pg_catalog.to_regclass(%s)",
            (qualified_name,),
        )
        relation_kind = cur.fetchone()[0]
        is_view = relation_kind in {"v", "m"}

        if access_mode == "no_access":
            cur.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                    relation, directus_ident
                )
            )
            column_privileges = (
                ("SELECT", "INSERT", "UPDATE")
                if is_view
                else ("SELECT", "INSERT", "UPDATE", "REFERENCES")
            )
        else:
            if is_view:
                cur.execute(
                    sql.SQL("REVOKE INSERT, UPDATE, DELETE ON TABLE {} FROM {}").format(
                        relation, directus_ident
                    )
                )
                column_privileges = ("INSERT", "UPDATE")
            else:
                cur.execute(
                    sql.SQL(
                        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                        "ON TABLE {} FROM {}"
                    ).format(relation, directus_ident)
                )
                column_privileges = ("INSERT", "UPDATE", "REFERENCES")

        cur.execute(
            "SELECT attribute.attname "
            "FROM pg_catalog.pg_attribute AS attribute "
            "WHERE attribute.attrelid = pg_catalog.to_regclass(%s) "
            "AND attribute.attnum > 0 AND NOT attribute.attisdropped "
            "ORDER BY attribute.attnum",
            (qualified_name,),
        )
        columns = [row[0] for row in cur.fetchall()]
        for column_name in columns:
            for privilege in column_privileges:
                cur.execute(
                    sql.SQL("REVOKE {} ({}) ON TABLE {} FROM {}").format(
                        sql.SQL(privilege),
                        sql.Identifier(column_name),
                        relation,
                        directus_ident,
                    )
                )

        cur.execute(
            "SELECT sequence_namespace.nspname, sequence.relname "
            "FROM pg_catalog.pg_class AS relation "
            "JOIN pg_catalog.pg_depend AS dependency "
            "  ON dependency.refobjid = relation.oid "
            " AND dependency.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass "
            " AND dependency.classid = 'pg_catalog.pg_class'::pg_catalog.regclass "
            " AND dependency.deptype IN ('a', 'i') "
            "JOIN pg_catalog.pg_class AS sequence "
            "  ON sequence.oid = dependency.objid AND sequence.relkind = 'S' "
            "JOIN pg_catalog.pg_namespace AS sequence_namespace "
            "  ON sequence_namespace.oid = sequence.relnamespace "
            "WHERE relation.oid = pg_catalog.to_regclass(%s) "
            "ORDER BY sequence_namespace.nspname, sequence.relname",
            (qualified_name,),
        )
        for sequence_schema, sequence_name in cur.fetchall():
            cur.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM {}").format(
                    sql.Identifier(sequence_schema, sequence_name),
                    directus_ident,
                )
            )

        cur.execute(
            "SELECT "
            "has_table_privilege(%s, %s, 'SELECT'), "
            "has_table_privilege(%s, %s, 'INSERT'), "
            "has_table_privilege(%s, %s, 'UPDATE'), "
            "has_table_privilege(%s, %s, 'DELETE'), "
            "has_table_privilege(%s, %s, 'TRUNCATE'), "
            "has_table_privilege(%s, %s, 'REFERENCES'), "
            "has_table_privilege(%s, %s, 'TRIGGER'), "
            "has_any_column_privilege(%s, %s, 'SELECT'), "
            "has_any_column_privilege(%s, %s, 'INSERT'), "
            "has_any_column_privilege(%s, %s, 'UPDATE'), "
            "has_any_column_privilege(%s, %s, 'REFERENCES')",
            tuple(value for _ in range(11) for value in (directus_ident.string, qualified_name)),
        )
        effective = cur.fetchone()
        expected = (
            (True, False, False, False, False, False, False, True, False, False, False)
            if access_mode == "read_only"
            else (False,) * 11
        )
        if effective != expected:
            raise RuntimeError(
                "Directus relation privilege policy did not produce the expected effective ACL"
            )
        counts[access_mode] += 1
    return counts


def provision_directus_role(
    conn,
    *,
    database: str,
    admin_user: str,
    directus_user: str,
    directus_password: str,
) -> dict[str, object]:
    """Create a non-owner Directus role with DML on application schemas only.

    This intentionally revokes PUBLIC database CONNECT grants across the
    dedicated Kernel PostgreSQL instance before granting the new identity
    access to its one application database. Existing service identities need
    explicit database grants, as provisioned by their own role bootstrappers.
    """
    for label, value in (("admin_user", admin_user), ("directus_user", directus_user)):
        if not _ROLE_NAME.fullmatch(value):
            raise ValueError(f"{label} must be a lowercase PostgreSQL role name")
    admin_ident = _role_identifier(admin_user, "admin_user")
    directus_ident = _role_identifier(directus_user, "directus_user")
    if admin_user == directus_user:
        raise ValueError("admin and Directus runtime roles must be distinct")
    if not database or "\x00" in database:
        raise ValueError("database name is required")
    if len(directus_password) < 24 or _PLACEHOLDER_SECRET.match(directus_password):
        raise ValueError("directus_password must be a non-placeholder secret of at least 24 characters")

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, rolsuper FROM pg_roles WHERE rolname = current_user")
            current_database, current_user, is_superuser = cur.fetchone()
            if current_database != database:
                raise RuntimeError("connected database does not match the requested Kernel database")
            if current_user != admin_user or not is_superuser:
                raise RuntimeError("connection must use the configured PostgreSQL superuser")
            cur.execute(
                "SELECT pg_catalog.to_regclass(%s)",
                (_DIRECTUS_RELATION_POLICY,),
            )
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "ordered migrations must create the Directus relation privilege policy before provisioning"
                )

            directus_oid = _ensure_login_role(
                cur,
                name=directus_user,
                identifier=directus_ident,
                password=directus_password,
            )

            # Reset this role's old database access, then make only the app DB
            # connectable by it. Revoking PUBLIC is necessary because PostgreSQL
            # has no per-role DENY privilege that can override PUBLIC grants.
            cur.execute("SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1' ORDER BY datname")
            database_names = [row[0] for row in cur.fetchall()]
            for database_name in database_names:
                database_ident = sql.Identifier(database_name)
                cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(database_ident))
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(database_ident, directus_ident)
                )
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), directus_ident))

            # Reconcile old explicit schema/object ACLs before applying the
            # narrow supported scope. System schemas are managed by PostgreSQL.
            cur.execute(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname !~ '^pg_' "
                "AND nspname <> 'information_schema' ORDER BY nspname"
            )
            schemas = [row[0] for row in cur.fetchall()]
            app_schemas: list[str] = []
            for schema_name in schemas:
                schema_ident = sql.Identifier(schema_name)
                cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {}").format(schema_ident, directus_ident))
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}").format(
                        schema_ident, directus_ident
                    )
                )
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} FROM {}").format(
                        schema_ident, directus_ident
                    )
                )
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        schema_ident, directus_ident
                    )
                )
                if schema_name in _APP_SCHEMAS:
                    app_schemas.append(schema_name)

            if "public" not in app_schemas:
                raise RuntimeError("required public application schema is missing")

            for schema_name in app_schemas:
                schema_ident = sql.Identifier(schema_name)
                # The new-database PUBLIC CREATE grant must be removed for a
                # DML-only role to remain unable to create schema objects.
                cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA {} FROM PUBLIC").format(schema_ident))
                cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema_ident, directus_ident))
                cur.execute(
                    sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                        schema_ident, directus_ident
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                        schema_ident, directus_ident
                    )
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                    ).format(admin_ident, schema_ident, directus_ident)
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
                    ).format(admin_ident, schema_ident, directus_ident)
                )

            directus_policy_counts = _apply_migration_declared_relation_policies(
                cur, directus_ident
            )

            _verify_role_attributes(cur, directus_user)
            cur.execute(
                "SELECT datname, has_database_privilege(%s, oid, 'CONNECT') "
                "FROM pg_database WHERE datallowconn OR datname = 'template1' ORDER BY datname",
                (directus_user,),
            )
            access = {name: allowed for name, allowed in cur.fetchall()}
            if access.get(database) is not True or any(allowed for name, allowed in access.items() if name != database):
                raise RuntimeError("Directus role must connect only to its configured application database")

            cur.execute(
                "SELECT has_schema_privilege(%s, 'public', 'USAGE'), has_schema_privilege(%s, 'public', 'CREATE')",
                (directus_user, directus_user),
            )
            if cur.fetchone() != (True, False):
                raise RuntimeError("Directus role must have public USAGE and no CREATE privilege")

            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = %s) "
                "OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = %s) "
                "OR EXISTS (SELECT 1 FROM pg_database WHERE datdba = %s)",
                (directus_oid, directus_oid, directus_oid),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("Directus runtime role must not own database objects")

        conn.commit()
    except BaseException:
        conn.rollback()
        raise

    return {
        "status": "provisioned",
        "database": database,
        "runtime_user": directus_user,
        "schemas": app_schemas,
        "privileges": ["SELECT", "INSERT", "UPDATE", "DELETE", "sequence USAGE/SELECT/UPDATE"],
        "privilege_exceptions": {
            "migration_declared_relation_policies": directus_policy_counts,
        },
        "ddl": False,
        "owns_relations": False,
        "connect_scope": [database],
        "public_connect_revoked_from": sorted(database_names),
    }


def main() -> int:
    database = os.environ.get("PG_DB", "kokonut_intelligence")
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    directus_user = os.environ.get("KOKONUT_DIRECTUS_RUNTIME_USER", "kokonut_directus_runtime")
    directus_password = os.environ.get("KOKONUT_DIRECTUS_RUNTIME_PASSWORD", "")
    if not admin_password or not directus_password:
        raise SystemExit("admin and Directus runtime credentials must be supplied through the environment")

    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "database"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=database,
        user=admin_user,
        password=admin_password,
        connect_timeout=10,
    )
    try:
        result = provision_directus_role(
            conn,
            database=database,
            admin_user=admin_user,
            directus_user=directus_user,
            directus_password=directus_password,
        )
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
