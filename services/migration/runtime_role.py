"""Provision the bounded application role for a dedicated Kernel database.

Run this module with migration/operator credentials before starting app or worker
roles. It is intentionally separate from ordered schema migrations because it
changes instance/database access policy rather than application schema.
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql


_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_PLACEHOLDER_SECRET = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE)


def _role_identifier(value: str, label: str) -> sql.Identifier:
    if not _ROLE_NAME.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase PostgreSQL role name")
    return sql.Identifier(value)


def provision_runtime_role(
    conn,
    *,
    database: str,
    admin_user: str,
    admin_password: str,
    runtime_user: str,
    runtime_password: str,
) -> dict[str, object]:
    """Create/update a non-owner DML role and constrain its database access.

    This operation is intended only for a dedicated Kernel PostgreSQL instance.
    It removes inherited PUBLIC database CONNECT and public-schema CREATE grants;
    any other application role must receive explicit access after review.
    """
    admin_ident = _role_identifier(admin_user, "admin_user")
    runtime_ident = _role_identifier(runtime_user, "runtime_user")
    if admin_user == runtime_user:
        raise ValueError("runtime_user must differ from admin_user")
    if not admin_password:
        raise ValueError("admin password must be provided")
    if (len(runtime_password) < 24 or _PLACEHOLDER_SECRET.match(runtime_password)):
        raise ValueError("runtime password must be a non-placeholder secret of at least 24 characters")
    if runtime_password == admin_password:
        raise ValueError("runtime password must differ from the admin password")
    if not database or "\x00" in database:
        raise ValueError("database name is required")

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), rolsuper FROM pg_roles WHERE rolname = %s", (admin_user,))
        current_database, admin_is_superuser = cur.fetchone()
        if current_database != database:
            raise RuntimeError("connected database does not match the requested Kernel database")
        if not admin_is_superuser:
            raise RuntimeError("admin user must be a PostgreSQL superuser for instance access hardening")

        cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (runtime_user,))
        existing = cur.fetchone()
        if existing:
            runtime_oid = existing[0]
            cur.execute(
                """
                SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = %s)
                    OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = %s
                               AND nspname NOT LIKE 'pg_%%'
                               AND nspname <> 'information_schema')
                    OR EXISTS (SELECT 1 FROM pg_database WHERE datdba = %s)
                """,
                (runtime_oid, runtime_oid, runtime_oid),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role owns database objects; review and transfer them before provisioning")

            cur.execute(
                """
                SELECT granted.rolname
                FROM pg_auth_members membership
                JOIN pg_roles granted ON granted.oid = membership.roleid
                WHERE membership.member = %s
                """,
                (runtime_oid,),
            )
            for (granted_role,) in cur.fetchall():
                cur.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        _role_identifier(granted_role, "granted role"), runtime_ident
                    )
                )

            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(runtime_ident),
                (runtime_password,),
            )
        else:
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(runtime_ident),
                (runtime_password,),
            )

        cur.execute("SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1'")
        database_names = [row[0] for row in cur.fetchall()]
        for name in database_names:
            db_ident = sql.Identifier(name)
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(db_ident))
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(db_ident, runtime_ident))

        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(runtime_ident))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), runtime_ident))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime_ident))
        cur.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
                runtime_ident
            )
        )
        cur.execute(
            sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                runtime_ident
            )
        )
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(admin_ident, runtime_ident)
        )
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
            ).format(admin_ident, runtime_ident)
        )

        cur.execute(
            """
            SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication,
                   r.rolbypassrls, r.rolinherit,
                   has_schema_privilege(r.oid, 'public', 'CREATE'),
                   EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid)
            FROM pg_roles r WHERE r.rolname = %s
            """,
            (runtime_user,),
        )
        role_state = cur.fetchone()
        if role_state != (False, False, False, False, False, False, False, False):
            raise RuntimeError("runtime role retains a privileged attribute, membership, or schema CREATE access")

        cur.execute(
            """
            SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
            FROM pg_database WHERE datallowconn OR datname = 'template1'
            ORDER BY datname
            """,
            (runtime_user,),
        )
        database_access = {name: can_connect for name, can_connect in cur.fetchall()}
        if database_access.get(database) is not True or any(
            access for name, access in database_access.items() if name != database
        ):
            raise RuntimeError("runtime role must have CONNECT only to its configured database")

        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = %s))",
            (runtime_user,),
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime role must not own database relations")

    return {
        "status": "provisioned",
        "database": database,
        "runtime_user": runtime_user,
        "role_attributes": {
            "superuser": False,
            "createdb": False,
            "createrole": False,
            "replication": False,
            "bypassrls": False,
            "inherit": False,
        },
        "public_connect_revoked_from": sorted(database_names),
        "runtime_connect_grants": database_access,
        "table_privileges": ["SELECT", "INSERT", "UPDATE", "DELETE"],
        "sequence_privileges": ["USAGE", "SELECT", "UPDATE"],
        "owns_relations": False,
    }


def main() -> int:
    database = os.environ.get("PG_DB", "kokonut_intelligence")
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    runtime_user = os.environ.get("KOKONUT_RUNTIME_USER", "kokonut_runtime")
    runtime_password = os.environ.get("KOKONUT_RUNTIME_PASSWORD", "")
    if not admin_password or not runtime_password:
        raise SystemExit("admin and runtime credentials must be provided through the environment")

    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "database"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=database,
        user=admin_user,
        password=admin_password,
        connect_timeout=10,
    )
    try:
        result = provision_runtime_role(
            conn,
            database=database,
            admin_user=admin_user,
            admin_password=admin_password,
            runtime_user=runtime_user,
            runtime_password=runtime_password,
        )
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
