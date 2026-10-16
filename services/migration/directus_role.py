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

            cur.execute("SELECT to_regclass('public.farm_activity_operator_event')")
            if cur.fetchone()[0] is not None:
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                        sql.Identifier("public", "farm_activity_operator_event"),
                        directus_ident,
                    )
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

            cur.execute("SELECT to_regclass('public.farm_activity_operator_event')")
            if cur.fetchone()[0] is not None:
                cur.execute(
                    """SELECT has_table_privilege(%s, 'public.farm_activity_operator_event', 'SELECT')
                           OR has_table_privilege(%s, 'public.farm_activity_operator_event', 'INSERT')
                           OR has_table_privilege(%s, 'public.farm_activity_operator_event', 'UPDATE')
                           OR has_table_privilege(%s, 'public.farm_activity_operator_event', 'DELETE')""",
                    (directus_user, directus_user, directus_user, directus_user),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError("Directus runtime role must not access the farm activity operator ledger")
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
            "farm_activity_operator_event": "no direct access; Gateway trigger owner appends the ledger",
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
