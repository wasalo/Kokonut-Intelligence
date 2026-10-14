"""Provision least-privilege application and operator-auth roles.

Run this module with migration/operator credentials before starting app or
worker roles. It changes instance/database access policy, so it remains
separate from ordered schema migrations.
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_PLACEHOLDER_SECRET = re.compile(
    r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE
)
_SESSION_FUNCTIONS = (
    "kokonut_security.create_operator_session(text,text,text,text,text,text,timestamptz)",
    "kokonut_security.authenticate_operator_session(text)",
    "kokonut_security.revoke_operator_session(uuid)",
)
_GATEWAY_CONTEXT_FUNCTION = (
    "kokonut_security.set_gateway_tenant_context(text,text,uuid,text,text)"
)
_MOBILE_DEVICE_READ_COLUMNS = (
    "id",
    "device_id",
    "device_name",
    "device_type",
    "os",
    "os_version",
    "app_version",
    "location_id",
    "user_id",
    "has_camera",
    "has_gps",
    "has_offline",
    "status",
    "last_sync_at",
    "last_seen_at",
    "metadata",
    "created_at",
    "updated_at",
    "revoked_at",
    "tenant_organization_id",
)
_MOBILE_DEVICE_UPDATE_COLUMNS = (
    "status",
    "device_token_hash",
    "revoked_at",
    "updated_at",
    "last_seen_at",
    "last_sync_at",
)
_MOBILE_ENROLLMENT_READ_COLUMNS = (
    "id",
    "user_id",
    "location_id",
    "created_by",
    "expires_at",
    "used_at",
    "consumed_device_id",
    "revoked_at",
    "created_at",
    "tenant_organization_id",
)
_MOBILE_ENROLLMENT_INSERT_COLUMNS = (
    "code_hash",
    "user_id",
    "location_id",
    "tenant_organization_id",
    "created_by",
    "expires_at",
)
_MOBILE_ENROLLMENT_UPDATE_COLUMNS = ("revoked_at",)
_MOBILE_CREDENTIAL_COLUMNS = {
    "mobile_device": ("device_token_hash", "push_token"),
    "mobile_device_enrollment": ("code_hash",),
}
_API_KEY_COLUMNS = (
    "id",
    "key_hash",
    "key_prefix",
    "role_id",
    "scopes",
    "expires_at",
    "is_active",
)


def _role_identifier(value: str, label: str) -> sql.Identifier:
    if not _ROLE_NAME.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase PostgreSQL role name")
    return sql.Identifier(value)


def _ensure_login_role(cur, *, name: str, identifier: sql.Identifier, password: str) -> int:
    cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (name,))
    existing = cur.fetchone()
    if existing:
        role_oid = existing[0]
        cur.execute(
            """
            SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = %s)
                OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = %s
                           AND nspname NOT LIKE 'pg_%%'
                           AND nspname <> 'information_schema')
                OR EXISTS (SELECT 1 FROM pg_database WHERE datdba = %s)
            """,
            (role_oid, role_oid, role_oid),
        )
        if cur.fetchone()[0]:
            raise RuntimeError(f"{name} role owns database objects; review and transfer them first")

        cur.execute(
            """
            SELECT granted.rolname
            FROM pg_auth_members membership
            JOIN pg_roles granted ON granted.oid = membership.roleid
            WHERE membership.member = %s
            """,
            (role_oid,),
        )
        for (granted_role,) in cur.fetchall():
            cur.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    _role_identifier(granted_role, "granted role"), identifier
                )
            )
        cur.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
            ).format(identifier),
            (password,),
        )
    else:
        cur.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
            ).format(identifier),
            (password,),
        )
        cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (name,))
        role_oid = cur.fetchone()[0]
    return role_oid


def _verify_role_attributes(cur, role_name: str) -> None:
    cur.execute(
        """
        SELECT role.rolsuper, role.rolcreatedb, role.rolcreaterole,
               role.rolreplication, role.rolbypassrls, role.rolinherit,
               has_schema_privilege(role.oid, 'public', 'CREATE'),
               EXISTS (SELECT 1 FROM pg_auth_members membership
                        WHERE membership.member = role.oid)
          FROM pg_roles AS role
         WHERE role.rolname = %s
        """,
        (role_name,),
    )
    if cur.fetchone() != (False, False, False, False, False, False, False, False):
        raise RuntimeError(f"{role_name} retains a privileged attribute, membership, or schema CREATE access")
    cur.execute(
        """SELECT EXISTS (
               SELECT 1 FROM pg_class
                WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = %s)
           )""",
        (role_name,),
    )
    if cur.fetchone()[0]:
        raise RuntimeError(f"{role_name} must not own database relations")


def _revoke_runtime_default_privileges(
    cur, admin_ident: sql.Identifier, runtime_ident: sql.Identifier
) -> None:
    """Require explicit provisioning before the runtime can use new objects."""
    for scope in (None, "public"):
        for object_kind in ("TABLES", "SEQUENCES"):
            statement = sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} ").format(admin_ident)
            if scope is not None:
                statement += sql.SQL("IN SCHEMA {} ").format(sql.Identifier(scope))
            statement += sql.SQL("REVOKE ALL PRIVILEGES ON {} FROM {}").format(
                sql.SQL(object_kind), runtime_ident
            )
            cur.execute(statement)


def _verify_no_runtime_default_privileges(
    cur, *, admin_user: str, runtime_user: str
) -> None:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM pg_default_acl AS defaults
              CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS privilege
             WHERE defaults.defaclrole = (SELECT oid FROM pg_roles WHERE rolname = %s)
               AND defaults.defaclobjtype IN ('r', 'S')
               AND (defaults.defaclnamespace = 0 OR defaults.defaclnamespace =
                    (SELECT oid FROM pg_namespace WHERE nspname = 'public'))
               AND privilege.grantee = (SELECT oid FROM pg_roles WHERE rolname = %s)
        )
        """,
        (admin_user, runtime_user),
    )
    if cur.fetchone()[0]:
        raise RuntimeError(
            "runtime role retains default privileges on future public tables or sequences"
        )


def _apply_mobile_credential_boundary(cur, runtime_ident: sql.Identifier) -> dict[str, object]:
    """Replace broad runtime grants on mobile credentials with call-site grants."""
    policies = {
        "mobile_device": {
            "select": _MOBILE_DEVICE_READ_COLUMNS,
            "insert": (),
            "update": _MOBILE_DEVICE_UPDATE_COLUMNS,
        },
        "mobile_device_enrollment": {
            "select": _MOBILE_ENROLLMENT_READ_COLUMNS,
            "insert": _MOBILE_ENROLLMENT_INSERT_COLUMNS,
            "update": _MOBILE_ENROLLMENT_UPDATE_COLUMNS,
        },
    }
    for table_name, grants in policies.items():
        table_ident = sql.Identifier("public", table_name)
        cur.execute(
            "SELECT attname FROM pg_attribute "
            "WHERE attrelid = to_regclass(%s) AND attnum > 0 AND NOT attisdropped",
            (f"public.{table_name}",),
        )
        actual_columns = {row[0] for row in cur.fetchall()}
        required_columns = set(_MOBILE_CREDENTIAL_COLUMNS[table_name])
        for columns in grants.values():
            required_columns.update(columns)
        missing_columns = sorted(required_columns - actual_columns)
        if not actual_columns or missing_columns:
            raise RuntimeError(
                f"{table_name} is missing columns required for the mobile credential boundary"
            )

        cur.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                table_ident, runtime_ident
            )
        )
        # Column grants survive a table-level REVOKE, so explicitly clear any
        # grants left by an earlier provisioner version before applying the
        # allowlist. Unknown future columns remain inaccessible until reviewed.
        for column_name in sorted(actual_columns):
            for privilege in ("SELECT", "INSERT", "UPDATE"):
                cur.execute(
                    sql.SQL("REVOKE {} ({}) ON TABLE {} FROM {}").format(
                        sql.SQL(privilege),
                        sql.Identifier(column_name),
                        table_ident,
                        runtime_ident,
                    )
                )
        for privilege, columns in grants.items():
            if not columns:
                continue
            cur.execute(
                sql.SQL("GRANT {} ({}) ON TABLE {} TO {}").format(
                    sql.SQL(privilege),
                    sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                    table_ident,
                    runtime_ident,
                )
            )

    return {
        "mobile_device": {
            "select": list(_MOBILE_DEVICE_READ_COLUMNS),
            "update": list(_MOBILE_DEVICE_UPDATE_COLUMNS),
            "denied_select": list(_MOBILE_CREDENTIAL_COLUMNS["mobile_device"]),
            "insert": [],
            "delete": False,
        },
        "mobile_device_enrollment": {
            "select": list(_MOBILE_ENROLLMENT_READ_COLUMNS),
            "insert": list(_MOBILE_ENROLLMENT_INSERT_COLUMNS),
            "update": list(_MOBILE_ENROLLMENT_UPDATE_COLUMNS),
            "denied_select": list(
                _MOBILE_CREDENTIAL_COLUMNS["mobile_device_enrollment"]
            ),
            "delete": False,
        },
    }


def _verify_mobile_credential_boundary(cur, role_name: str) -> None:
    checks = (
        ("public.mobile_device", "device_id", "SELECT", True),
        ("public.mobile_device", "device_token_hash", "SELECT", False),
        ("public.mobile_device", "push_token", "SELECT", False),
        ("public.mobile_device", "device_token_hash", "UPDATE", True),
        ("public.mobile_device", "device_token_hash", "INSERT", False),
        ("public.mobile_device_enrollment", "id", "SELECT", True),
        ("public.mobile_device_enrollment", "code_hash", "SELECT", False),
        ("public.mobile_device_enrollment", "code_hash", "INSERT", True),
        ("public.mobile_device_enrollment", "code_hash", "UPDATE", False),
        ("public.mobile_device_enrollment", "revoked_at", "UPDATE", True),
    )
    for table_name, column_name, privilege, expected in checks:
        cur.execute(
            "SELECT has_column_privilege(%s, %s, %s, %s)",
            (role_name, table_name, column_name, privilege),
        )
        if cur.fetchone()[0] is not expected:
            raise RuntimeError(
                f"{role_name} has an unexpected {privilege} grant on "
                f"{table_name}.{column_name}"
            )
    for table_name, privilege in (
        ("public.mobile_device", "INSERT"),
        ("public.mobile_device", "UPDATE"),
        ("public.mobile_device", "DELETE"),
        ("public.mobile_device_enrollment", "UPDATE"),
        ("public.mobile_device_enrollment", "DELETE"),
    ):
        cur.execute(
            "SELECT has_table_privilege(%s, %s, %s)",
            (role_name, table_name, privilege),
        )
        if cur.fetchone()[0]:
            raise RuntimeError(f"{role_name} retains table-wide {privilege} on {table_name}")


def _apply_api_key_boundary(cur, runtime_ident: sql.Identifier) -> dict[str, object]:
    """Keep API-key authentication read-only for the general runtime role."""
    table_ident = sql.Identifier("public", "api_key")
    cur.execute(
        "SELECT attname FROM pg_attribute "
        "WHERE attrelid = to_regclass('public.api_key') AND attnum > 0 AND NOT attisdropped"
    )
    actual_columns = {row[0] for row in cur.fetchall()}
    missing_columns = sorted(set(_API_KEY_COLUMNS) - actual_columns)
    if not actual_columns or missing_columns:
        raise RuntimeError("api_key is missing columns required for the runtime boundary")

    cur.execute(
        sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
            table_ident, runtime_ident
        )
    )
    for column_name in sorted(actual_columns):
        for privilege in ("SELECT", "INSERT", "UPDATE"):
            cur.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE {} FROM {}").format(
                    sql.SQL(privilege),
                    sql.Identifier(column_name),
                    table_ident,
                    runtime_ident,
                )
            )
    cur.execute(
        sql.SQL("GRANT SELECT ({}) ON TABLE {} TO {}").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in _API_KEY_COLUMNS),
            table_ident,
            runtime_ident,
        )
    )
    return {
        "select": list(_API_KEY_COLUMNS),
        "insert": [],
        "update": [],
        "delete": False,
    }


def _verify_api_key_boundary(cur, role_name: str) -> None:
    for column_name in _API_KEY_COLUMNS:
        cur.execute(
            "SELECT has_column_privilege(%s, 'public.api_key', %s, 'SELECT')",
            (role_name, column_name),
        )
        if cur.fetchone()[0] is not True:
            raise RuntimeError(f"{role_name} cannot read api_key.{column_name}")
    for table_name, privilege in (
        ("public.api_key", "INSERT"),
        ("public.api_key", "UPDATE"),
        ("public.api_key", "DELETE"),
    ):
        cur.execute(
            "SELECT has_table_privilege(%s, %s, %s)",
            (role_name, table_name, privilege),
        )
        if cur.fetchone()[0]:
            raise RuntimeError(f"{role_name} retains table-wide {privilege} on api_key")
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_attribute "
        "WHERE attrelid = 'public.api_key'::regclass AND attnum > 0 AND NOT attisdropped "
        "AND attname <> ALL(%s) AND has_column_privilege(%s, 'public.api_key', attname, 'SELECT'))",
        (list(_API_KEY_COLUMNS), role_name),
    )
    if cur.fetchone()[0]:
        raise RuntimeError(f"{role_name} can read an unreviewed api_key column")
    cur.execute(
        """SELECT EXISTS (
               SELECT 1 FROM pg_attribute
                WHERE attrelid = 'public.api_key'::regclass
                  AND attnum > 0 AND NOT attisdropped
                  AND (
                    has_column_privilege(%s, 'public.api_key', attname, 'INSERT')
                    OR has_column_privilege(%s, 'public.api_key', attname, 'UPDATE')
                  )
           )""",
        (role_name, role_name),
    )
    if cur.fetchone()[0]:
        raise RuntimeError(f"{role_name} retains column-level API-key write privileges")


def provision_runtime_role(
    conn,
    *,
    database: str,
    admin_user: str,
    admin_password: str,
    runtime_user: str,
    runtime_password: str,
    operator_auth_user: str,
    operator_auth_password: str,
) -> dict[str, object]:
    """Provision a general runtime role plus a session-only auth principal.

    The runtime role keeps DML compatibility for existing public tables,
    except ``operator_session``, mobile credentials, and ``api_key``, which use
    explicit least-privilege grants. New public tables and sequences receive no
    automatic runtime privileges. The dedicated auth role can only execute
    the three bounded functions from migration 395. This is scoped to a
    dedicated Kernel PostgreSQL instance.
    """
    admin_ident = _role_identifier(admin_user, "admin_user")
    runtime_ident = _role_identifier(runtime_user, "runtime_user")
    auth_ident = _role_identifier(operator_auth_user, "operator_auth_user")
    if len({admin_user, runtime_user, operator_auth_user}) != 3:
        raise ValueError("admin, runtime, and operator-auth roles must be distinct")
    if not admin_password:
        raise ValueError("admin password must be provided")
    for label, secret in (
        ("runtime_password", runtime_password),
        ("operator_auth_password", operator_auth_password),
    ):
        if len(secret) < 24 or _PLACEHOLDER_SECRET.match(secret):
            raise ValueError(f"{label} must be a non-placeholder secret of at least 24 characters")
    if len({admin_password, runtime_password, operator_auth_password}) != 3:
        raise ValueError("admin, runtime, and operator-auth passwords must be distinct")
    if not database or "\x00" in database:
        raise ValueError("database name is required")

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_database(), rolsuper FROM pg_roles WHERE rolname = %s",
            (admin_user,),
        )
        current_database, admin_is_superuser = cur.fetchone()
        if current_database != database:
            raise RuntimeError("connected database does not match the requested Kernel database")
        if not admin_is_superuser:
            raise RuntimeError("admin user must be a PostgreSQL superuser for instance access hardening")

        cur.execute(
            "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _SESSION_FUNCTIONS),
            _SESSION_FUNCTIONS,
        )
        if any(procedure is None for procedure in cur.fetchone()):
            raise RuntimeError("migration 395 operator-session functions must be applied before role provisioning")
        cur.execute("SELECT to_regprocedure(%s)", (_GATEWAY_CONTEXT_FUNCTION,))
        if cur.fetchone()[0] is None:
            raise RuntimeError("migration 396 Gateway tenant-context function must be applied before role provisioning")

        _ensure_login_role(cur, name=runtime_user, identifier=runtime_ident, password=runtime_password)
        _ensure_login_role(
            cur,
            name=operator_auth_user,
            identifier=auth_ident,
            password=operator_auth_password,
        )
        cur.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                sql.SQL(_GATEWAY_CONTEXT_FUNCTION), runtime_ident
            )
        )
        cur.execute(
            "SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1'"
        )
        database_names = [row[0] for row in cur.fetchall()]
        for name in database_names:
            database_ident = sql.Identifier(name)
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(database_ident))
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(database_ident, runtime_ident))
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(database_ident, auth_ident))

        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        for identifier in (runtime_ident, auth_ident):
            cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(identifier))
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), identifier
                )
            )
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime_ident))

        _revoke_runtime_default_privileges(cur, admin_ident, runtime_ident)

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
        mobile_credential_grants = _apply_mobile_credential_boundary(cur, runtime_ident)
        api_key_grants = _apply_api_key_boundary(cur, runtime_ident)
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(auth_ident)
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(auth_ident)
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM {}").format(
                auth_ident
            )
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {}").format(auth_ident)
        )

        cur.execute("REVOKE ALL ON TABLE public.operator_session FROM PUBLIC")
        cur.execute(
            sql.SQL("REVOKE ALL ON TABLE public.operator_session FROM {}").format(runtime_ident)
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON TABLE public.operator_session FROM {}").format(auth_ident)
        )
        columns = (
            "id, operator_id, session_token_hash, csrf_token_hash, created_at, "
            "last_seen_at, expires_at, revoked_at"
        )
        for privilege in ("SELECT", "INSERT", "UPDATE"):
            for role_ident in (runtime_ident, auth_ident):
                cur.execute(
                    sql.SQL("REVOKE {} ({}) ON TABLE public.operator_session FROM {}").format(
                        sql.SQL(privilege), sql.SQL(columns), role_ident
                    )
                )
        for function in _SESSION_FUNCTIONS:
            cur.execute(
                sql.SQL("REVOKE ALL ON FUNCTION {} FROM {}").format(
                    sql.SQL(function), runtime_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(function), auth_ident
                )
            )

        _verify_role_attributes(cur, runtime_user)
        _verify_role_attributes(cur, operator_auth_user)
        for role_name in (runtime_user, operator_auth_user):
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (role_name,),
            )
            access = {name: allowed for name, allowed in cur.fetchall()}
            if access.get(database) is not True or any(
                allowed for name, allowed in access.items() if name != database
            ):
                raise RuntimeError(f"{role_name} must connect only to its configured database")

        for role_name in (runtime_user, operator_auth_user):
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM pg_attribute AS attribute
                        WHERE attribute.attrelid = 'public.operator_session'::regclass
                          AND attribute.attnum > 0 AND NOT attribute.attisdropped
                          AND (
                            has_column_privilege(%s, 'public.operator_session', attribute.attname, 'SELECT')
                            OR has_column_privilege(%s, 'public.operator_session', attribute.attname, 'INSERT')
                            OR has_column_privilege(%s, 'public.operator_session', attribute.attname, 'UPDATE')
                          )
                   )""",
                (role_name, role_name, role_name),
            )
            if cur.fetchone()[0]:
                raise RuntimeError(f"{role_name} retains direct operator-session column privileges")

        cur.execute(
            """SELECT has_function_privilege(%s, %s, 'EXECUTE')
                     OR has_function_privilege(%s, %s, 'EXECUTE')
                     OR has_function_privilege(%s, %s, 'EXECUTE')""",
            (
                runtime_user, _SESSION_FUNCTIONS[0],
                runtime_user, _SESSION_FUNCTIONS[1],
                runtime_user, _SESSION_FUNCTIONS[2],
            ),
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime role can execute operator-auth functions")
        cur.execute(
            """SELECT has_function_privilege(%s, %s, 'EXECUTE')
                       AND has_function_privilege(%s, %s, 'EXECUTE')
                       AND has_function_privilege(%s, %s, 'EXECUTE')""",
            (
                operator_auth_user, _SESSION_FUNCTIONS[0],
                operator_auth_user, _SESSION_FUNCTIONS[1],
                operator_auth_user, _SESSION_FUNCTIONS[2],
            ),
        )
        if cur.fetchone()[0] is not True:
            raise RuntimeError("operator-auth role is missing a bounded session function grant")

        _verify_mobile_credential_boundary(cur, runtime_user)
        _verify_api_key_boundary(cur, runtime_user)
        _verify_no_runtime_default_privileges(
            cur, admin_user=admin_user, runtime_user=runtime_user
        )
        cur.execute(
            "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
            (runtime_user, _GATEWAY_CONTEXT_FUNCTION),
        )
        if cur.fetchone()[0] is not True:
            raise RuntimeError("runtime role is missing the bounded Gateway context function")

        cur.execute(
            """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                 FROM pg_database
                WHERE datallowconn OR datname = 'template1'
                ORDER BY datname""",
            (runtime_user,),
        )
        runtime_database_access = {name: allowed for name, allowed in cur.fetchall()}
        cur.execute(
            """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                 FROM pg_database
                WHERE datallowconn OR datname = 'template1'
                ORDER BY datname""",
            (operator_auth_user,),
        )
        auth_database_access = {name: allowed for name, allowed in cur.fetchall()}

    return {
        "status": "provisioned",
        "database": database,
        "runtime_user": runtime_user,
        "operator_auth_user": operator_auth_user,
        "public_connect_revoked_from": sorted(database_names),
        "runtime_connect_grants": runtime_database_access,
        "operator_auth_connect_grants": auth_database_access,
        "runtime_table_privileges": ["SELECT", "INSERT", "UPDATE", "DELETE"],
        "runtime_table_privilege_scope": "existing_public_tables_only",
        "runtime_future_object_privileges": [],
        "runtime_table_privilege_exceptions": {
            "api_key": "explicit read-only column allowlist; no insert, update, or delete",
            "mobile_device": "explicit column allowlist; no table-wide INSERT, UPDATE, or DELETE",
            "mobile_device_enrollment": "explicit column allowlist; no table-wide UPDATE or DELETE",
            "operator_session": "bounded functions only",
        },
        "runtime_mobile_credential_privileges": mobile_credential_grants,
        "runtime_api_key_privileges": api_key_grants,
        "operator_session_access": "bounded functions only",
        "operator_auth_functions": ["create", "authenticate", "revoke"],
        "runtime_gateway_function": "set_gateway_tenant_context",
        "runtime_owns_relations": False,
        "operator_auth_owns_relations": False,
    }


def main() -> int:
    database = os.environ.get("PG_DB", "kokonut_intelligence")
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    runtime_user = os.environ.get("KOKONUT_RUNTIME_USER", "kokonut_runtime")
    runtime_password = os.environ.get("KOKONUT_RUNTIME_PASSWORD", "")
    operator_auth_user = os.environ.get("KOKONUT_OPERATOR_AUTH_USER", "kokonut_operator_auth")
    operator_auth_password = os.environ.get("KOKONUT_OPERATOR_AUTH_PASSWORD", "")
    if not admin_password or not runtime_password or not operator_auth_password:
        raise SystemExit(
            "admin, runtime, and operator-auth credentials must be provided through the environment"
        )

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
            operator_auth_user=operator_auth_user,
            operator_auth_password=operator_auth_password,
        )
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
