"""Provision an isolated PostgreSQL metadata database for optional Metabase."""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_PLACEHOLDER_SECRET = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE)


def _identifier(value: str, label: str) -> sql.Identifier:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase PostgreSQL identifier")
    return sql.Identifier(value)


def _validate_secret(value: str, *, admin_password: str) -> None:
    if len(value) < 24 or _PLACEHOLDER_SECRET.match(value):
        raise ValueError("Metabase metadata password must be a non-placeholder secret of at least 24 characters")
    if value == admin_password:
        raise ValueError("Metabase metadata password must differ from the database administrator credential")


def provision_metabase_metadata(
    conn,
    *,
    host: str,
    port: int,
    application_database: str,
    metadata_database: str,
    admin_user: str,
    admin_password: str,
    metadata_user: str,
    metadata_password: str,
    dedicated_instance: bool,
) -> dict[str, object]:
    """Create a metadata-only login and database; never grant application access."""
    metadata_role = _identifier(metadata_user, "metadata_user")
    metadata_db = _identifier(metadata_database, "metadata_database")
    _identifier(application_database, "application_database")
    if metadata_user == admin_user:
        raise ValueError("metadata_user must differ from admin_user")
    if metadata_database in {application_database, "postgres", "template0", "template1"}:
        raise ValueError("metadata_database must be a new, dedicated database name")
    if not dedicated_instance:
        raise ValueError("Metabase metadata provisioning requires a dedicated Kernel PostgreSQL instance")
    if not admin_password:
        raise ValueError("database administrator credential must be provided")
    _validate_secret(metadata_password, admin_password=admin_password)

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_database(), r.rolsuper FROM pg_roles r WHERE r.rolname = %s",
            (admin_user,),
        )
        admin_state = cur.fetchone()
        if not admin_state or admin_state != ("postgres", True):
            raise RuntimeError("connect to the postgres maintenance database as its PostgreSQL superuser")

        cur.execute("SELECT datname FROM pg_database WHERE datallowconn")
        database_names = sorted(row[0] for row in cur.fetchall())
        if application_database not in database_names:
            raise RuntimeError("configured application database is unavailable")

        cur.execute(
            """
            SELECT d.datname
            FROM pg_database d
            CROSS JOIN LATERAL aclexplode(coalesce(d.datacl, acldefault('d', d.datdba))) a
            WHERE d.datallowconn AND d.datname <> %s
              AND a.grantee = 0 AND a.privilege_type = 'CONNECT'
            ORDER BY d.datname
            """,
            (metadata_database,),
        )
        public_connect_databases = [row[0] for row in cur.fetchall()]
        if public_connect_databases:
            raise RuntimeError(
                "review inherited PUBLIC CONNECT before adding a metadata login; "
                f"accessible databases: {', '.join(public_connect_databases)}"
            )

        cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (metadata_user,))
        role_row = cur.fetchone()
        if role_row:
            role_oid = role_row[0]
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = %s OR roleid = %s)",
                (role_oid, role_oid),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("Metabase metadata role has memberships; review them before provisioning")
            cur.execute(
                "SELECT datname FROM pg_database WHERE datdba = %s AND datname <> %s",
                (role_oid, metadata_database),
            )
            if cur.fetchone():
                raise RuntimeError("Metabase metadata role owns another database; review it before provisioning")
            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(metadata_role),
                (metadata_password,),
            )
        else:
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(metadata_role),
                (metadata_password,),
            )

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (metadata_database,))
        exists = cur.fetchone() is not None
        if exists:
            cur.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (metadata_database,),
            )
            if cur.fetchone()[0] != metadata_user:
                raise RuntimeError("existing Metabase metadata database has an unexpected owner")
        else:
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(metadata_db, metadata_role))

        cur.execute("SELECT datname FROM pg_database WHERE datallowconn")
        database_names = sorted(row[0] for row in cur.fetchall())
        for name in database_names:
            cur.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(
                    sql.Identifier(name), metadata_role
                )
            )
        cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(metadata_db))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(metadata_db, metadata_role))
        cur.execute(sql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(metadata_db, metadata_role))

        cur.execute(
            """
            SELECT datname,
                   has_database_privilege(%s, oid, 'CONNECT'),
                   has_database_privilege(%s, oid, 'CREATE')
            FROM pg_database WHERE datallowconn ORDER BY datname
            """,
            (metadata_user, metadata_user),
        )
        database_privileges = {name: (can_connect, can_create) for name, can_connect, can_create in cur.fetchall()}
        if database_privileges.get(metadata_database) != (True, True) or any(
            can_connect or can_create
            for name, (can_connect, can_create) in database_privileges.items()
            if name != metadata_database
        ):
            raise RuntimeError(
                "Metabase metadata role can connect outside its database; review inherited PUBLIC database ACLs"
            )

    metadata_conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=metadata_database,
        user=admin_user,
        password=admin_password,
        connect_timeout=10,
    )
    try:
        metadata_conn.autocommit = False
        with metadata_conn.cursor() as cur:
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        metadata_conn.commit()
    finally:
        metadata_conn.close()

    return {
        "status": "provisioned",
        "metadata_database": metadata_database,
        "metadata_user": metadata_user,
        "application_database": application_database,
        "metadata_database_owner": metadata_user,
        "database_privileges": database_privileges,
    }


def verify_metabase_login(
    *,
    host: str,
    port: int,
    application_database: str,
    metadata_database: str,
    metadata_user: str,
    metadata_password: str,
) -> dict[str, object]:
    """Verify actual metadata login ownership and application DB denial."""
    metadata_conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=metadata_database,
        user=metadata_user,
        password=metadata_password,
        connect_timeout=10,
    )
    try:
        with metadata_conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user")
            if cur.fetchone() != (metadata_user, metadata_user):
                raise RuntimeError("Metabase metadata login has an unexpected identity")
            cur.execute("CREATE TABLE public.kernel_metabase_role_probe (id integer)")
        metadata_conn.rollback()
    finally:
        metadata_conn.close()

    try:
        application_conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=application_database,
            user=metadata_user,
            password=metadata_password,
            connect_timeout=5,
        )
    except psycopg2.Error as exc:
        message = str(exc).lower()
        expected_denial = (
            getattr(exc, "pgcode", None) == "42501"
            or (
                "permission denied for database" in message
                and "connect privilege" in message
            )
        )
        if not expected_denial:
            raise
    else:
        application_conn.close()
        raise RuntimeError("Metabase metadata login unexpectedly connected to the application database")

    return {
        "status": "verified",
        "metadata_user": metadata_user,
        "metadata_database": metadata_database,
        "metadata_create_table_probe_rolled_back": True,
        "application_database_connect_denied": True,
    }


def main() -> int:
    application_database = os.environ.get("PG_APP_DB", "kokonut_intelligence")
    metadata_database = os.environ.get("MB_DB_DBNAME", "kokonut_metabase")
    host = os.environ.get("PG_HOST", "database")
    port = int(os.environ.get("PG_PORT", "5432"))
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    metadata_user = os.environ.get("MB_DB_USER", "kokonut_metabase_app")
    metadata_password = os.environ.get("MB_DB_PASS", "")
    analytics_password = os.environ.get("KOKONUT_ANALYTICS_PASSWORD", "")
    dedicated_instance = os.environ.get("KOKONUT_METABASE_ROLE_DEDICATED_INSTANCE") == "true"
    if not admin_password or not metadata_password:
        raise SystemExit("administrator and metadata credentials must be provided through the environment")
    if analytics_password and metadata_password == analytics_password:
        raise SystemExit("Metabase metadata and analytics source credentials must be distinct")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname="postgres",
        user=admin_user,
        password=admin_password,
        connect_timeout=10,
    )
    try:
        result = provision_metabase_metadata(
            conn,
            host=host,
            port=port,
            application_database=application_database,
            metadata_database=metadata_database,
            admin_user=admin_user,
            admin_password=admin_password,
            metadata_user=metadata_user,
            metadata_password=metadata_password,
            dedicated_instance=dedicated_instance,
        )
    finally:
        conn.close()
    result["login_verification"] = verify_metabase_login(
        host=host,
        port=port,
        application_database=application_database,
        metadata_database=metadata_database,
        metadata_user=metadata_user,
        metadata_password=metadata_password,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
