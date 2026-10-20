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
_OPERATOR_CONTEXT_FUNCTION = (
    "kokonut_security.set_operator_tenant_context(text,uuid,uuid,text,text,jsonb)"
)
_MOBILE_DEVICE_REVOKE_FUNCTION = (
    "kokonut_security.revoke_mobile_device(uuid,text,text,text,uuid,text)"
)
_WORKER_CONTEXT_FUNCTION = (
    "kokonut_security.set_worker_tenant_context(text,uuid,text,text)"
)
_WORKER_SCOPE_FUNCTION = "kokonut_security.current_worker_scope(text,text)"
_MOBILE_CREDENTIAL_FUNCTIONS = (
    "kokonut_security.resolve_mobile_device_token(text)",
    "kokonut_security.redeem_mobile_enrollment(text,text,text,text,text,text,text,text)",
    "kokonut_security.set_mobile_device_context(text,text,uuid)",
    "kokonut_security.current_tenant_context()",
)
_FARM_ACTIVITY_EVENT_OWNER = "kokonut_farm_activity_event_owner"
_NOTIFICATION_ENQUEUE_FUNCTION = (
    "kokonut_security.enqueue_notification_intents(uuid,text,uuid,jsonb)"
)
_MARKET_DATA_FUNCTION = (
    "kokonut_security.store_world_bank_market_data(jsonb,text,text,integer)"
)
_EAS_INDEXER_FUNCTIONS = (
    "kokonut_security.acquire_eas_indexer_chain_lock(text)",
    "kokonut_security.release_eas_indexer_chain_lock(text)",
    "kokonut_security.list_eas_indexer_recipients(text)",
    "kokonut_security.read_eas_indexer_cursor(text,uuid)",
    "kokonut_security.store_eas_indexer_page(text,uuid,jsonb)",
    "kokonut_security.advance_eas_indexer_cursor(text,uuid,bigint)",
    "kokonut_security.finish_eas_indexer_chain(text,text,text,integer,integer,text)",
)
_RPC_INDEXER_FUNCTIONS = (
    "kokonut_security.acquire_rpc_indexer_chain_lock(text)",
    "kokonut_security.release_rpc_indexer_chain_lock(text)",
    "kokonut_security.list_rpc_indexer_wallets(text)",
    "kokonut_security.store_rpc_indexer_snapshot(text,uuid,jsonb,text)",
    "kokonut_security.finish_rpc_indexer_chain(text,text,text,integer,bigint,integer,text)",
)
_SENSOR_INGESTION_FUNCTIONS = (
    "kokonut_security.resolve_sensor_driver_instance(uuid,uuid)",
    "kokonut_security.read_sensor_driver_catalog(uuid)",
    "kokonut_security.store_sensor_driver_batch(uuid,uuid,jsonb)",
    "kokonut_security.update_sensor_driver_status(uuid,uuid,text,integer,integer,integer,text)",
)
_REMOTE_SENSING_FUNCTIONS = (
    "kokonut_security.claim_remote_sensing_job(uuid)",
    "kokonut_security.finish_remote_sensing_job(uuid,uuid,text,jsonb,jsonb)",
)
_SECURITY_DEFINER_OWNERS = (
    (
        "kokonut_security.resolve_mobile_device_token(text)",
        "kokonut_mobile_credential_owner",
    ),
    (
        "kokonut_security.redeem_mobile_enrollment(text,text,text,text,text,text,text,text)",
        "kokonut_mobile_credential_owner",
    ),
    (
        "kokonut_security.set_mobile_device_context(text,text,uuid)",
        "kokonut_mobile_context_owner",
    ),
    ("kokonut_security.current_tenant_context()", "kokonut_mobile_context_owner"),
    (
        "kokonut_security.set_operator_tenant_context(text,uuid,uuid,text,text,jsonb)",
        "kokonut_operator_context_owner",
    ),
    (
        "kokonut_security.create_operator_session(text,text,text,text,text,text,timestamptz)",
        "kokonut_operator_auth_owner",
    ),
    (
        "kokonut_security.authenticate_operator_session(text)",
        "kokonut_operator_auth_owner",
    ),
    (
        "kokonut_security.revoke_operator_session(uuid)",
        "kokonut_operator_auth_owner",
    ),
    (
        "kokonut_security.set_gateway_tenant_context(text,text,uuid,text,text)",
        "kokonut_gateway_context_owner",
    ),
    (_MOBILE_DEVICE_REVOKE_FUNCTION, "kokonut_mobile_device_revoke_owner"),
    (_WORKER_CONTEXT_FUNCTION, "kokonut_worker_context_owner"),
    (_WORKER_SCOPE_FUNCTION, "kokonut_worker_context_owner"),
    (_NOTIFICATION_ENQUEUE_FUNCTION, "kokonut_notification_enqueue_owner"),
    (_MARKET_DATA_FUNCTION, "kokonut_market_data_owner"),
    *((function, "kokonut_eas_indexer_owner") for function in _EAS_INDEXER_FUNCTIONS),
    *((function, "kokonut_rpc_indexer_owner") for function in _RPC_INDEXER_FUNCTIONS),
    *(
        (function, "kokonut_sensor_ingestion_owner")
        for function in _SENSOR_INGESTION_FUNCTIONS
    ),
    *(
        (function, "kokonut_remote_sensing_owner")
        for function in _REMOTE_SENSING_FUNCTIONS
    ),
    ("public.guard_farm_activity_operator_event_insert()", _FARM_ACTIVITY_EVENT_OWNER),
    ("public.record_gateway_farm_activity_create()", _FARM_ACTIVITY_EVENT_OWNER),
    ("public.record_farm_activity_gateway_operation()", _FARM_ACTIVITY_EVENT_OWNER),
)
_PRIVATE_RUNTIME_FUNCTIONS = (
    *_SESSION_FUNCTIONS,
    _GATEWAY_CONTEXT_FUNCTION,
    _OPERATOR_CONTEXT_FUNCTION,
    _MOBILE_DEVICE_REVOKE_FUNCTION,
    *_MOBILE_CREDENTIAL_FUNCTIONS,
    _WORKER_CONTEXT_FUNCTION,
    _WORKER_SCOPE_FUNCTION,
    _NOTIFICATION_ENQUEUE_FUNCTION,
    _MARKET_DATA_FUNCTION,
    *_EAS_INDEXER_FUNCTIONS,
    *_RPC_INDEXER_FUNCTIONS,
    *_SENSOR_INGESTION_FUNCTIONS,
    *_REMOTE_SENSING_FUNCTIONS,
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


def _remove_role_memberships(cur, *, role_name: str, identifier: sql.Identifier) -> None:
    """Make a dedicated login neither inherit nor lend its privileges."""
    cur.execute(
        """
        SELECT granted.rolname
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted ON granted.oid = membership.roleid
          JOIN pg_roles AS member ON member.oid = membership.member
         WHERE member.rolname = %s
        """,
        (role_name,),
    )
    for (granted_role,) in cur.fetchall():
        cur.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                _role_identifier(granted_role, "granted role"), identifier
            )
        )

    cur.execute(
        """
        SELECT member.rolname
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted ON granted.oid = membership.roleid
          JOIN pg_roles AS member ON member.oid = membership.member
         WHERE granted.rolname = %s
        """,
        (role_name,),
    )
    for (member_role,) in cur.fetchall():
        cur.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                identifier, _role_identifier(member_role, "member role")
            )
        )


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


def _revoke_public_function_execute(cur, function: str) -> None:
    cur.execute("SELECT to_regprocedure(%s)", (function,))
    if cur.fetchone()[0] is None:
        return
    cur.execute(
        sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(sql.SQL(function))
    )


def _verify_no_public_function_execute(cur, function: str) -> None:
    cur.execute(
        """SELECT EXISTS (
               SELECT 1
                 FROM pg_proc AS proc
                 CROSS JOIN LATERAL aclexplode(
                     COALESCE(proc.proacl, acldefault('f', proc.proowner))
                 ) AS acl_entry
                WHERE proc.oid = to_regprocedure(%s)
                  AND acl_entry.grantee = 0
                  AND acl_entry.privilege_type = 'EXECUTE'
           )""",
        (function,),
    )
    if cur.fetchone()[0]:
        raise RuntimeError(f"PUBLIC can execute a restricted security function: {function.split('.')[-1]}")


def _verify_security_definer_owners(cur) -> None:
    """Fail closed if restored SECURITY DEFINER functions use elevated owners."""
    for function, expected_owner in _SECURITY_DEFINER_OWNERS:
        cur.execute("SELECT to_regprocedure(%s)", (function,))
        if cur.fetchone()[0] is None:
            continue
        cur.execute(
            """SELECT owner.rolname, owner.rolcanlogin, owner.rolsuper,
                      owner.rolcreatedb, owner.rolcreaterole,
                      owner.rolreplication, owner.rolbypassrls, owner.rolinherit,
                      EXISTS (
                          SELECT 1 FROM pg_auth_members AS membership
                           WHERE membership.member = owner.oid
                              OR membership.roleid = owner.oid
                      )
                 FROM pg_proc AS function_row
                 JOIN pg_roles AS owner ON owner.oid = function_row.proowner
                WHERE function_row.oid = to_regprocedure(%s)""",
            (function,),
        )
        result = cur.fetchone()
        expected = (expected_owner, False, False, False, False, False, False, False, False)
        if result != expected:
            raise RuntimeError(
                f"{function} must be owned by isolated {expected_owner}; "
                "apply migration 400 before provisioning runtime roles"
            )


def _restore_farm_activity_event_owner(cur) -> bool:
    """Rebind the bounded event trigger owner after a database-only restore."""
    cur.execute("SELECT to_regclass('public.farm_activity_operator_event')")
    if cur.fetchone()[0] is None:
        return False
    cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (_FARM_ACTIVITY_EVENT_OWNER,))
    if cur.fetchone() is None:
        cur.execute(
            sql.SQL(
                "CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(_FARM_ACTIVITY_EVENT_OWNER))
        )
    cur.execute(
        """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                  rolreplication, rolbypassrls, rolinherit,
                  EXISTS (SELECT 1 FROM pg_auth_members WHERE member = role.oid OR roleid = role.oid)
             FROM pg_roles AS role WHERE rolname = %s""",
        (_FARM_ACTIVITY_EVENT_OWNER,),
    )
    if cur.fetchone() != (False, False, False, False, False, False, False, False):
        raise RuntimeError("farm activity event function owner has unsafe role attributes")

    owner = sql.Identifier(_FARM_ACTIVITY_EVENT_OWNER)
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(owner))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(owner))
    cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(owner))
    cur.execute(
        sql.SQL("GRANT SELECT, INSERT ON TABLE public.farm_activity_operator_event TO {}").format(owner)
    )
    cur.execute(
        sql.SQL(
            "GRANT SELECT ON TABLE public.farm_activity, public.location, "
            "public.operator_identity TO {}"
        ).format(owner)
    )
    cur.execute(
        sql.SQL(
            "GRANT SELECT ON TABLE public.operator_scope_grant, "
            "public.operator_organization_membership, public.location_tenant_owner_verification, "
            "public.location_organization_share, public.organization TO {}"
        ).format(owner)
    )
    cur.execute(
        sql.SQL(
            "GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID) TO {}"
        ).format(owner)
    )
    cur.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(owner))
    for function in (
        "guard_farm_activity_operator_event_insert()",
        "record_gateway_farm_activity_create()",
        "record_farm_activity_gateway_operation()",
    ):
        function_ident = sql.SQL("public.{}()").format(sql.SQL(function[:-2]))
        cur.execute(sql.SQL("ALTER FUNCTION {} OWNER TO {}").format(function_ident, owner))
        cur.execute(sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(function_ident))
        cur.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(function_ident, owner))
    cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(owner))
    cur.execute("REVOKE ALL ON TABLE public.farm_activity_operator_event FROM PUBLIC")
    return True


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
        ("public.mobile_device", "device_token_hash", "UPDATE", False),
        ("public.mobile_device", "status", "UPDATE", False),
        ("public.mobile_device", "revoked_at", "UPDATE", False),
        ("public.mobile_device", "last_seen_at", "UPDATE", True),
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


def _apply_farm_activity_operator_event_boundary(
    cur, runtime_ident: sql.Identifier
) -> dict[str, object]:
    """Allow event reads/appends while denying mutation of the append-only ledger."""
    cur.execute("SELECT to_regclass('public.farm_activity_operator_event')")
    if cur.fetchone()[0] is None:
        return {"installed": False, "select": False, "insert": False, "update": False, "delete": False}
    table_ident = sql.Identifier("public", "farm_activity_operator_event")
    cur.execute(
        sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
            table_ident, runtime_ident
        )
    )
    cur.execute(
        sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
            table_ident, runtime_ident
        )
    )
    return {"installed": True, "select": True, "insert": False, "update": False, "delete": False}


def _verify_farm_activity_operator_event_boundary(cur, role_name: str) -> None:
    cur.execute("SELECT to_regclass('public.farm_activity_operator_event')")
    if cur.fetchone()[0] is None:
        return
    cur.execute(
        """SELECT has_table_privilege(%s, 'public.farm_activity_operator_event', 'SELECT'),
                  has_table_privilege(%s, 'public.farm_activity_operator_event', 'INSERT'),
                  has_table_privilege(%s, 'public.farm_activity_operator_event', 'UPDATE'),
                  has_table_privilege(%s, 'public.farm_activity_operator_event', 'DELETE')""",
        (role_name, role_name, role_name, role_name),
    )
    if cur.fetchone() != (True, False, False, False):
        raise RuntimeError(
            f"{role_name} does not have append-only farm activity operator event privileges"
        )


def _apply_solution_stage_gate_boundary(
    cur, runtime_ident: sql.Identifier
) -> dict[str, object]:
    """Require bounded security-definer functions for solution stage-gate access."""
    cur.execute("SELECT to_regclass('public.solution_stage_gate')")
    if cur.fetchone()[0] is None:
        return {
            "installed": False,
            "select": False,
            "insert": False,
            "update": False,
            "delete": False,
        }

    table_ident = sql.Identifier("public", "solution_stage_gate")
    cur.execute(
        "SELECT attname FROM pg_attribute "
        "WHERE attrelid = 'public.solution_stage_gate'::regclass "
        "AND attnum > 0 AND NOT attisdropped"
    )
    columns = [row[0] for row in cur.fetchall()]
    if not columns:
        raise RuntimeError("solution_stage_gate has no columns for the runtime boundary")

    cur.execute(
        sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
            table_ident, runtime_ident
        )
    )
    # Column grants survive a table-level REVOKE; clear them before leaving the
    # relation available only through its bounded Gateway projections/actions.
    for column in columns:
        for privilege in ("SELECT", "INSERT", "UPDATE"):
            cur.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE {} FROM {}").format(
                    sql.SQL(privilege),
                    sql.Identifier(column),
                    table_ident,
                    runtime_ident,
                )
            )
    return {
        "installed": True,
        "select": False,
        "insert": False,
        "update": False,
        "delete": False,
        "access": "bounded security-definer functions only",
    }


def _verify_solution_stage_gate_boundary(cur, role_name: str) -> None:
    cur.execute("SELECT to_regclass('public.solution_stage_gate')")
    if cur.fetchone()[0] is None:
        return
    cur.execute(
        "SELECT has_table_privilege(%s, 'public.solution_stage_gate', 'SELECT'), "
        "has_table_privilege(%s, 'public.solution_stage_gate', 'INSERT'), "
        "has_table_privilege(%s, 'public.solution_stage_gate', 'UPDATE'), "
        "has_table_privilege(%s, 'public.solution_stage_gate', 'DELETE'), "
        "EXISTS (SELECT 1 FROM pg_attribute "
        "WHERE attrelid = 'public.solution_stage_gate'::regclass "
        "AND attnum > 0 AND NOT attisdropped "
        "AND (has_column_privilege(%s, 'public.solution_stage_gate', attname, 'SELECT') "
        "OR has_column_privilege(%s, 'public.solution_stage_gate', attname, 'INSERT') "
        "OR has_column_privilege(%s, 'public.solution_stage_gate', attname, 'UPDATE'))) ",
        (role_name, role_name, role_name, role_name, role_name, role_name, role_name),
    )
    if cur.fetchone() != (False, False, False, False, False):
        raise RuntimeError(
            f"{role_name} retains direct solution_stage_gate privileges"
        )


def _apply_solution_experiment_protocol_boundary(
    cur, runtime_ident: sql.Identifier
) -> dict[str, object]:
    """Permit lifecycle-field updates; draft creation stays behind the Gateway."""
    cur.execute("SELECT to_regclass('public.solution_experiment')")
    if cur.fetchone()[0] is None:
        return {
            "installed": False, "insert": False, "delete": False,
            "protocol_update": False,
        }

    table_ident = sql.Identifier("public", "solution_experiment")
    cur.execute(
        "SELECT attname FROM pg_attribute "
        "WHERE attrelid = 'public.solution_experiment'::regclass "
        "AND attnum > 0 AND NOT attisdropped"
    )
    columns = [row[0] for row in cur.fetchall()]
    if not columns:
        raise RuntimeError("solution_experiment has no columns for the runtime boundary")

    cur.execute(
        sql.SQL("REVOKE INSERT, UPDATE, DELETE ON TABLE {} FROM {}").format(
            table_ident, runtime_ident
        )
    )
    for column in columns:
        for privilege in ("INSERT", "UPDATE"):
            cur.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE {} FROM {}").format(
                    sql.SQL(privilege),
                    sql.Identifier(column),
                    table_ident,
                    runtime_ident,
                )
            )
    cur.execute(
        sql.SQL(
            "GRANT UPDATE (status, approved_by_party_id, approved_at, started_at, "
            "completed_at, updated_at) ON TABLE {} TO {}"
        ).format(table_ident, runtime_ident)
    )
    return {
        "installed": True,
        "insert": False,
        "delete": False,
        "protocol_update": False,
        "lifecycle_update_columns": [
            "status", "approved_by_party_id", "approved_at", "started_at",
            "completed_at", "updated_at",
        ],
        "access": "bounded Gateway protocol creation; lifecycle fields remain writable",
    }


def _verify_solution_experiment_protocol_boundary(cur, role_name: str) -> None:
    cur.execute("SELECT to_regclass('public.solution_experiment')")
    if cur.fetchone()[0] is None:
        return
    cur.execute(
        "SELECT has_table_privilege(%s, 'public.solution_experiment', 'INSERT'), "
        "has_table_privilege(%s, 'public.solution_experiment', 'UPDATE'), "
        "has_table_privilege(%s, 'public.solution_experiment', 'DELETE'), "
        "EXISTS (SELECT 1 FROM pg_attribute "
        "WHERE attrelid = 'public.solution_experiment'::regclass "
        "AND attnum > 0 AND NOT attisdropped "
        "AND (has_column_privilege(%s, 'public.solution_experiment', attname, 'INSERT') "
        "OR (attname NOT IN ('status', 'approved_by_party_id', 'approved_at', "
        "'started_at', 'completed_at', 'updated_at') "
        "AND has_column_privilege(%s, 'public.solution_experiment', attname, 'UPDATE')))), "
        "has_column_privilege(%s, 'public.solution_experiment', 'status', 'UPDATE'), "
        "has_column_privilege(%s, 'public.solution_experiment', 'approved_by_party_id', 'UPDATE'), "
        "has_column_privilege(%s, 'public.solution_experiment', 'approved_at', 'UPDATE'), "
        "has_column_privilege(%s, 'public.solution_experiment', 'started_at', 'UPDATE'), "
        "has_column_privilege(%s, 'public.solution_experiment', 'completed_at', 'UPDATE'), "
        "has_column_privilege(%s, 'public.solution_experiment', 'updated_at', 'UPDATE')",
        (role_name,) * 11,
    )
    expected = (False, False, False, False, True, True, True, True, True, True)
    if cur.fetchone() != expected:
        raise RuntimeError(
            f"{role_name} retains direct solution_experiment protocol privileges"
        )


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
    notification_enqueue_user: str | None = None,
    notification_enqueue_password: str | None = None,
    market_data_user: str | None = None,
    market_data_password: str | None = None,
    eas_indexer_user: str | None = None,
    eas_indexer_password: str | None = None,
    rpc_indexer_user: str | None = None,
    rpc_indexer_password: str | None = None,
    sensor_ingestion_user: str | None = None,
    sensor_ingestion_password: str | None = None,
    remote_sensing_user: str | None = None,
    remote_sensing_password: str | None = None,
) -> dict[str, object]:
    """Provision a general runtime role plus a session-only auth principal.

    The runtime role keeps DML compatibility for existing public tables,
    except ``operator_session``, mobile credentials, ``api_key``, and
    ``solution_stage_gate``, which use
    explicit least-privilege grants. New public tables and sequences receive no
    automatic runtime privileges. The dedicated auth role can only execute
    the three bounded functions from migration 395. This is scoped to a
    dedicated Kernel PostgreSQL instance. When configured, the optional
    notification-enqueue login receives only its bounded intent function.
    When configured, the market-data login receives only the bounded global
    World Bank batch function. When configured, the sensor-ingestion login can
    switch to the worker execution role only to call the signed, bounded sensor
    driver functions from migration 431. When configured, the remote-sensing
    login can switch to that role only to call migration 432's signed bounded
    claim and completion functions. When configured, the global EAS login can
    execute only the bounded chain and attestation functions from migration 433.
    When configured, the global RPC-indexer login can execute only the bounded
    snapshot and status functions from migration 436.
    """
    admin_ident = _role_identifier(admin_user, "admin_user")
    runtime_ident = _role_identifier(runtime_user, "runtime_user")
    auth_ident = _role_identifier(operator_auth_user, "operator_auth_user")
    if (notification_enqueue_user is None) != (notification_enqueue_password is None):
        raise ValueError("notification enqueue user and password must be provided together")
    if (market_data_user is None) != (market_data_password is None):
        raise ValueError("market-data user and password must be provided together")
    if (eas_indexer_user is None) != (eas_indexer_password is None):
        raise ValueError("EAS-indexer user and password must be provided together")
    if (rpc_indexer_user is None) != (rpc_indexer_password is None):
        raise ValueError("RPC-indexer user and password must be provided together")
    if (sensor_ingestion_user is None) != (sensor_ingestion_password is None):
        raise ValueError("sensor-ingestion user and password must be provided together")
    if (remote_sensing_user is None) != (remote_sensing_password is None):
        raise ValueError("remote-sensing user and password must be provided together")
    enqueue_ident = (
        _role_identifier(notification_enqueue_user, "notification_enqueue_user")
        if notification_enqueue_user is not None
        else None
    )
    market_data_ident = (
        _role_identifier(market_data_user, "market_data_user")
        if market_data_user is not None
        else None
    )
    eas_indexer_ident = (
        _role_identifier(eas_indexer_user, "eas_indexer_user")
        if eas_indexer_user is not None
        else None
    )
    rpc_indexer_ident = (
        _role_identifier(rpc_indexer_user, "rpc_indexer_user")
        if rpc_indexer_user is not None
        else None
    )
    sensor_ingestion_ident = (
        _role_identifier(sensor_ingestion_user, "sensor_ingestion_user")
        if sensor_ingestion_user is not None
        else None
    )
    remote_sensing_ident = (
        _role_identifier(remote_sensing_user, "remote_sensing_user")
        if remote_sensing_user is not None
        else None
    )
    role_names = [admin_user, runtime_user, operator_auth_user]
    if notification_enqueue_user is not None:
        role_names.append(notification_enqueue_user)
    if market_data_user is not None:
        role_names.append(market_data_user)
    if eas_indexer_user is not None:
        role_names.append(eas_indexer_user)
    if rpc_indexer_user is not None:
        role_names.append(rpc_indexer_user)
    if sensor_ingestion_user is not None:
        role_names.append(sensor_ingestion_user)
    if remote_sensing_user is not None:
        role_names.append(remote_sensing_user)
    if "kokonut_notification_enqueue_owner" in role_names:
        raise ValueError("application logins must differ from the notification function owner")
    if "kokonut_market_data_owner" in role_names:
        raise ValueError("application logins must differ from the market-data function owner")
    if "kokonut_eas_indexer_owner" in role_names:
        raise ValueError("application logins must differ from the EAS-indexer function owner")
    if "kokonut_rpc_indexer_owner" in role_names:
        raise ValueError("application logins must differ from the RPC-indexer function owner")
    if "kokonut_sensor_ingestion_owner" in role_names:
        raise ValueError("application logins must differ from the sensor-ingestion function owner")
    if "kokonut_remote_sensing_owner" in role_names:
        raise ValueError("application logins must differ from the remote-sensing function owner")
    if len(set(role_names)) != len(role_names):
        raise ValueError(
            "admin, runtime, operator-auth, notification-enqueue, market-data, EAS-indexer, RPC-indexer, sensor-ingestion, and remote-sensing roles must be distinct"
        )
    if not admin_password:
        raise ValueError("admin password must be provided")
    credential_pairs = [
        ("runtime_password", runtime_password),
        ("operator_auth_password", operator_auth_password),
    ]
    if notification_enqueue_password is not None:
        credential_pairs.append(("notification_enqueue_password", notification_enqueue_password))
    if market_data_password is not None:
        credential_pairs.append(("market_data_password", market_data_password))
    if eas_indexer_password is not None:
        credential_pairs.append(("eas_indexer_password", eas_indexer_password))
    if rpc_indexer_password is not None:
        credential_pairs.append(("rpc_indexer_password", rpc_indexer_password))
    if sensor_ingestion_password is not None:
        credential_pairs.append(("sensor_ingestion_password", sensor_ingestion_password))
    if remote_sensing_password is not None:
        credential_pairs.append(("remote_sensing_password", remote_sensing_password))
    for label, secret in credential_pairs:
        if len(secret) < 24 or _PLACEHOLDER_SECRET.match(secret):
            raise ValueError(f"{label} must be a non-placeholder secret of at least 24 characters")
    passwords = [admin_password, runtime_password, operator_auth_password]
    if notification_enqueue_password is not None:
        passwords.append(notification_enqueue_password)
    if market_data_password is not None:
        passwords.append(market_data_password)
    if eas_indexer_password is not None:
        passwords.append(eas_indexer_password)
    if rpc_indexer_password is not None:
        passwords.append(rpc_indexer_password)
    if sensor_ingestion_password is not None:
        passwords.append(sensor_ingestion_password)
    if remote_sensing_password is not None:
        passwords.append(remote_sensing_password)
    if len(set(passwords)) != len(passwords):
        raise ValueError("admin and dedicated application-role passwords must be distinct")
    if not database or "\x00" in database:
        raise ValueError("database name is required")

    market_data_database_access: dict[str, bool] = {}
    eas_indexer_database_access: dict[str, bool] = {}
    rpc_indexer_database_access: dict[str, bool] = {}
    sensor_ingestion_database_access: dict[str, bool] = {}
    remote_sensing_database_access: dict[str, bool] = {}
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
        cur.execute(
            "SELECT to_regprocedure(%s), to_regprocedure(%s), to_regprocedure(%s)",
            (
                _GATEWAY_CONTEXT_FUNCTION,
                _OPERATOR_CONTEXT_FUNCTION,
                _MOBILE_DEVICE_REVOKE_FUNCTION,
            ),
        )
        if any(procedure is None for procedure in cur.fetchone()):
            raise RuntimeError(
                "migrations 394/396 tenant-context and 398 bounded device-revocation "
                "functions must be applied before role provisioning"
            )
        cur.execute(
            "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _MOBILE_CREDENTIAL_FUNCTIONS),
            _MOBILE_CREDENTIAL_FUNCTIONS,
        )
        if any(procedure is None for procedure in cur.fetchone()):
            raise RuntimeError(
                "migrations 392/393 mobile credential functions must be applied before role provisioning"
            )
        cur.execute(
            "SELECT to_regprocedure(%s), to_regprocedure(%s)",
            (_WORKER_CONTEXT_FUNCTION, _WORKER_SCOPE_FUNCTION),
        )
        worker_functions = cur.fetchone()
        if (worker_functions[0] is None) != (worker_functions[1] is None):
            raise RuntimeError(
                "worker tenant-context migrations must provide both bounded context functions"
            )
        if notification_enqueue_user is not None:
            cur.execute("SELECT to_regprocedure(%s)", (_NOTIFICATION_ENQUEUE_FUNCTION,))
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "migration 417 notification enqueue function must be applied before "
                    "provisioning its dedicated login"
                )
        if market_data_user is not None:
            cur.execute("SELECT to_regprocedure(%s)", (_MARKET_DATA_FUNCTION,))
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "migration 430 market-data function must be applied before "
                    "provisioning its dedicated login"
                )
        if eas_indexer_user is not None:
            cur.execute(
                "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _EAS_INDEXER_FUNCTIONS),
                _EAS_INDEXER_FUNCTIONS,
            )
            if any(procedure is None for procedure in cur.fetchone()):
                raise RuntimeError(
                    "migration 433 EAS-indexer functions must be applied before "
                    "provisioning its dedicated login"
                )
        if rpc_indexer_user is not None:
            cur.execute(
                "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _RPC_INDEXER_FUNCTIONS),
                _RPC_INDEXER_FUNCTIONS,
            )
            if any(procedure is None for procedure in cur.fetchone()):
                raise RuntimeError(
                    "migration 436 RPC-indexer functions must be applied before "
                    "provisioning its dedicated login"
                )
        if sensor_ingestion_user is not None:
            cur.execute(
                "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _SENSOR_INGESTION_FUNCTIONS),
                _SENSOR_INGESTION_FUNCTIONS,
            )
            if any(procedure is None for procedure in cur.fetchone()):
                raise RuntimeError(
                    "migration 431 sensor-ingestion functions must be applied before "
                    "provisioning the dedicated login"
                )
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution'")
            if cur.fetchone() is None:
                raise RuntimeError(
                    "migration 405 worker execution role must exist before sensor-login provisioning"
                )
        if remote_sensing_user is not None:
            cur.execute(
                "SELECT " + ", ".join("to_regprocedure(%s)" for _ in _REMOTE_SENSING_FUNCTIONS),
                _REMOTE_SENSING_FUNCTIONS,
            )
            if any(procedure is None for procedure in cur.fetchone()):
                raise RuntimeError(
                    "migration 432 remote-sensing functions must be applied before "
                    "provisioning the dedicated login"
                )
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution'")
            if cur.fetchone() is None:
                raise RuntimeError(
                    "migration 405 worker execution role must exist before remote-sensing login provisioning"
                )

        for function in _PRIVATE_RUNTIME_FUNCTIONS:
            _revoke_public_function_execute(cur, function)

        _ensure_login_role(cur, name=runtime_user, identifier=runtime_ident, password=runtime_password)
        for function in _MOBILE_CREDENTIAL_FUNCTIONS:
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(function), runtime_ident
                )
            )
        _ensure_login_role(
            cur,
            name=operator_auth_user,
            identifier=auth_ident,
            password=operator_auth_password,
        )
        if worker_functions[0] is not None:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution'")
            if cur.fetchone() is None:
                raise RuntimeError(
                    "worker tenant-context functions exist without kokonut_worker_execution"
                )
            worker_execution_ident = _role_identifier(
                "kokonut_worker_execution", "worker execution role"
            )
            for function in (
                _MOBILE_CREDENTIAL_FUNCTIONS[-1],
                _WORKER_CONTEXT_FUNCTION,
                _WORKER_SCOPE_FUNCTION,
            ):
                cur.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                        sql.SQL(function), worker_execution_ident
                    )
                )
        if notification_enqueue_user is not None:
            assert enqueue_ident is not None and notification_enqueue_password is not None
            _ensure_login_role(
                cur,
                name=notification_enqueue_user,
                identifier=enqueue_ident,
                password=notification_enqueue_password,
            )
            _remove_role_memberships(
                cur,
                role_name=notification_enqueue_user,
                identifier=enqueue_ident,
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    enqueue_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(enqueue_ident)
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(_NOTIFICATION_ENQUEUE_FUNCTION), enqueue_ident
                )
            )
        if market_data_user is not None:
            assert market_data_ident is not None and market_data_password is not None
            _ensure_login_role(
                cur,
                name=market_data_user,
                identifier=market_data_ident,
                password=market_data_password,
            )
            _remove_role_memberships(
                cur,
                role_name=market_data_user,
                identifier=market_data_ident,
            )
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), market_data_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), market_data_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(market_data_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    market_data_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    market_data_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(_MARKET_DATA_FUNCTION), market_data_ident
                )
            )
        if eas_indexer_user is not None:
            assert eas_indexer_ident is not None and eas_indexer_password is not None
            _ensure_login_role(
                cur,
                name=eas_indexer_user,
                identifier=eas_indexer_ident,
                password=eas_indexer_password,
            )
            _remove_role_memberships(
                cur,
                role_name=eas_indexer_user,
                identifier=eas_indexer_ident,
            )
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), eas_indexer_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), eas_indexer_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(eas_indexer_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    eas_indexer_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    eas_indexer_ident
                )
            )
            for function in _EAS_INDEXER_FUNCTIONS:
                cur.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                        sql.SQL(function), eas_indexer_ident
                    )
                )
        if rpc_indexer_user is not None:
            assert rpc_indexer_ident is not None and rpc_indexer_password is not None
            _ensure_login_role(
                cur,
                name=rpc_indexer_user,
                identifier=rpc_indexer_ident,
                password=rpc_indexer_password,
            )
            _remove_role_memberships(
                cur,
                role_name=rpc_indexer_user,
                identifier=rpc_indexer_ident,
            )
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), rpc_indexer_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), rpc_indexer_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(rpc_indexer_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    rpc_indexer_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    rpc_indexer_ident
                )
            )
            for function in _RPC_INDEXER_FUNCTIONS:
                cur.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                        sql.SQL(function), rpc_indexer_ident
                    )
                )
        if sensor_ingestion_user is not None:
            assert sensor_ingestion_ident is not None and sensor_ingestion_password is not None
            _ensure_login_role(
                cur,
                name=sensor_ingestion_user,
                identifier=sensor_ingestion_ident,
                password=sensor_ingestion_password,
            )
            _remove_role_memberships(
                cur,
                role_name=sensor_ingestion_user,
                identifier=sensor_ingestion_ident,
            )
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), sensor_ingestion_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), sensor_ingestion_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sensor_ingestion_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    sensor_ingestion_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    sensor_ingestion_ident
                )
            )
            cur.execute(
                sql.SQL(
                    "GRANT kokonut_worker_execution TO {} WITH INHERIT FALSE, SET TRUE"
                ).format(sensor_ingestion_ident)
            )
        if remote_sensing_user is not None:
            assert remote_sensing_ident is not None and remote_sensing_password is not None
            _ensure_login_role(
                cur,
                name=remote_sensing_user,
                identifier=remote_sensing_ident,
                password=remote_sensing_password,
            )
            _remove_role_memberships(
                cur,
                role_name=remote_sensing_user,
                identifier=remote_sensing_ident,
            )
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), remote_sensing_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), remote_sensing_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(remote_sensing_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    remote_sensing_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    remote_sensing_ident
                )
            )
            cur.execute(
                sql.SQL(
                    "GRANT kokonut_worker_execution TO {} WITH INHERIT FALSE, SET TRUE"
                ).format(remote_sensing_ident)
            )
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(runtime_ident)
        )
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(auth_ident)
        )
        cur.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                sql.SQL(_GATEWAY_CONTEXT_FUNCTION), runtime_ident
            )
        )
        cur.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                sql.SQL(_OPERATOR_CONTEXT_FUNCTION), runtime_ident
            )
        )
        cur.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                sql.SQL(_MOBILE_DEVICE_REVOKE_FUNCTION), runtime_ident
            )
        )
        cur.execute(
            "SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1'"
        )
        database_names = [row[0] for row in cur.fetchall()]
        protected_login_idents = [runtime_ident, auth_ident]
        if enqueue_ident is not None:
            protected_login_idents.append(enqueue_ident)
        if market_data_ident is not None:
            protected_login_idents.append(market_data_ident)
        if eas_indexer_ident is not None:
            protected_login_idents.append(eas_indexer_ident)
        if sensor_ingestion_ident is not None:
            protected_login_idents.append(sensor_ingestion_ident)
        if remote_sensing_ident is not None:
            protected_login_idents.append(remote_sensing_ident)
        for name in database_names:
            database_ident = sql.Identifier(name)
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(database_ident))
            for login_ident in protected_login_idents:
                cur.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(
                        database_ident, login_ident
                    )
                )

        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        for identifier in protected_login_idents:
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
        farm_activity_event_owner_ready = _restore_farm_activity_event_owner(cur)
        mobile_credential_grants = _apply_mobile_credential_boundary(cur, runtime_ident)
        api_key_grants = _apply_api_key_boundary(cur, runtime_ident)
        farm_activity_event_grants = _apply_farm_activity_operator_event_boundary(cur, runtime_ident)
        solution_stage_gate_grants = _apply_solution_stage_gate_boundary(
            cur, runtime_ident
        )
        solution_experiment_protocol_grants = _apply_solution_experiment_protocol_boundary(
            cur, runtime_ident
        )
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
        if enqueue_ident is not None:
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), enqueue_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), enqueue_ident
                    )
                )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(enqueue_ident)
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    enqueue_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(_NOTIFICATION_ENQUEUE_FUNCTION), enqueue_ident
                )
            )
        if market_data_ident is not None:
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), market_data_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), market_data_ident
                    )
                )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    market_data_ident
                )
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    market_data_ident
                )
            )
            cur.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                    sql.SQL(_MARKET_DATA_FUNCTION), market_data_ident
                )
            )
        if eas_indexer_ident is not None:
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), eas_indexer_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), eas_indexer_ident
                    )
                )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    eas_indexer_ident
                )
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    eas_indexer_ident
                )
            )
            for function in _EAS_INDEXER_FUNCTIONS:
                cur.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                        sql.SQL(function), eas_indexer_ident
                    )
                )
        if sensor_ingestion_ident is not None:
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                        sql.SQL(object_kind), sensor_ingestion_ident
                    )
                )
            for schema in ("public", "kokonut_security"):
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                        sql.Identifier(schema), sensor_ingestion_ident
                    )
                )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA kokonut_security TO {}").format(
                    sensor_ingestion_ident
                )
            )
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA kokonut_security FROM {}").format(
                    sensor_ingestion_ident
                )
            )
            cur.execute(
                sql.SQL(
                    "GRANT kokonut_worker_execution TO {} WITH INHERIT FALSE, SET TRUE"
                ).format(sensor_ingestion_ident)
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
                sql.SQL("REVOKE ALL ON FUNCTION {} FROM PUBLIC").format(
                    sql.SQL(function)
                )
            )
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
        if notification_enqueue_user is not None:
            _verify_role_attributes(cur, notification_enqueue_user)
        if sensor_ingestion_user is not None:
            cur.execute(
                """SELECT role.rolcanlogin, role.rolsuper, role.rolcreatedb,
                          role.rolcreaterole, role.rolreplication, role.rolbypassrls,
                          role.rolinherit, has_schema_privilege(role.oid, 'public', 'CREATE'),
                          (SELECT count(*) FROM pg_auth_members AS membership
                            WHERE membership.member = role.oid),
                          (SELECT bool_and(granted.rolname = 'kokonut_worker_execution'
                                           AND NOT membership.admin_option
                                           AND NOT membership.inherit_option
                                           AND membership.set_option)
                             FROM pg_auth_members AS membership
                             JOIN pg_roles AS granted ON granted.oid = membership.roleid
                            WHERE membership.member = role.oid)
                     FROM pg_roles AS role
                    WHERE role.rolname = %s
                    """,
                (sensor_ingestion_user,),
            )
            sensor_login_state = cur.fetchone()
            if sensor_login_state != (True, False, False, False, False, False, False, False, 1, True):
                raise RuntimeError(
                    "sensor-ingestion login must have only a non-inheriting SET membership in kokonut_worker_execution"
                )
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = "
                "(SELECT oid FROM pg_roles WHERE rolname = %s))",
                (sensor_ingestion_user,),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("sensor-ingestion login must not own database relations")
            cur.execute(
                "SELECT pg_has_role(%s, 'kokonut_worker_execution', 'SET'), "
                "has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (sensor_ingestion_user, sensor_ingestion_user, sensor_ingestion_user),
            )
            if cur.fetchone() != (True, True, False):
                raise RuntimeError(
                    "sensor-ingestion login is missing its restricted worker-role boundary"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = relation.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR EXISTS (
                                SELECT 1 FROM pg_attribute AS attribute
                                 WHERE attribute.attrelid = relation.oid
                                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                                   AND (has_column_privilege(%s, relation.oid, attribute.attname, 'SELECT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'INSERT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'UPDATE')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'REFERENCES'))
                            ))
                   )""",
                (sensor_ingestion_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("sensor-ingestion login retains application relation access")
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM pg_class AS sequence
                       JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public' AND sequence.relkind = 'S'
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = sequence.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (has_sequence_privilege(%s, sequence.oid, 'USAGE')
                            OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                            OR has_sequence_privilege(%s, sequence.oid, 'UPDATE'))
                   )""",
                (sensor_ingestion_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("sensor-ingestion login retains application sequence privileges")
        if remote_sensing_user is not None:
            cur.execute(
                """SELECT role.rolcanlogin, role.rolsuper, role.rolcreatedb,
                          role.rolcreaterole, role.rolreplication, role.rolbypassrls,
                          role.rolinherit, has_schema_privilege(role.oid, 'public', 'CREATE'),
                          (SELECT count(*) FROM pg_auth_members AS membership
                            WHERE membership.member = role.oid),
                          (SELECT bool_and(granted.rolname = 'kokonut_worker_execution'
                                           AND NOT membership.admin_option
                                           AND NOT membership.inherit_option
                                           AND membership.set_option)
                             FROM pg_auth_members AS membership
                             JOIN pg_roles AS granted ON granted.oid = membership.roleid
                            WHERE membership.member = role.oid)
                     FROM pg_roles AS role
                    WHERE role.rolname = %s
                    """,
                (remote_sensing_user,),
            )
            remote_login_state = cur.fetchone()
            if remote_login_state != (True, False, False, False, False, False, False, False, 1, True):
                raise RuntimeError(
                    "remote-sensing login must have only a non-inheriting SET membership in kokonut_worker_execution"
                )
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = "
                "(SELECT oid FROM pg_roles WHERE rolname = %s))",
                (remote_sensing_user,),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("remote-sensing login must not own database relations")
            cur.execute(
                "SELECT pg_has_role(%s, 'kokonut_worker_execution', 'SET'), "
                "has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (remote_sensing_user, remote_sensing_user, remote_sensing_user),
            )
            if cur.fetchone() != (True, True, False):
                raise RuntimeError(
                    "remote-sensing login is missing its restricted worker-role boundary"
                )
            cur.execute(
                "SELECT " + ", ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _REMOTE_SENSING_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _REMOTE_SENSING_FUNCTIONS
                    for value in ("kokonut_worker_execution", function)
                ),
            )
            if cur.fetchone() != (True, True):
                raise RuntimeError(
                    "worker execution role is missing a bounded remote-sensing function grant"
                )
            cur.execute(
                "SELECT " + ", ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _REMOTE_SENSING_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _REMOTE_SENSING_FUNCTIONS
                    for value in (remote_sensing_user, function)
                ),
            )
            if cur.fetchone() != (False, False):
                raise RuntimeError(
                    "remote-sensing login can call bounded functions without entering worker execution"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = relation.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR EXISTS (
                                SELECT 1 FROM pg_attribute AS attribute
                                 WHERE attribute.attrelid = relation.oid
                                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                                   AND (has_column_privilege(%s, relation.oid, attribute.attname, 'SELECT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'INSERT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'UPDATE')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'REFERENCES'))
                            ))
                   )""",
                (remote_sensing_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("remote-sensing login retains application relation access")
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM pg_class AS sequence
                       JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public' AND sequence.relkind = 'S'
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = sequence.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (has_sequence_privilege(%s, sequence.oid, 'USAGE')
                            OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                            OR has_sequence_privilege(%s, sequence.oid, 'UPDATE'))
                   )""",
                (remote_sensing_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("remote-sensing login retains application sequence privileges")
        checked_login_names = [runtime_user, operator_auth_user]
        if notification_enqueue_user is not None:
            checked_login_names.append(notification_enqueue_user)
        for role_name in checked_login_names:
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

        if notification_enqueue_user is not None:
            cur.execute(
                """SELECT has_function_privilege(%s, %s, 'EXECUTE'),
                          has_table_privilege(%s, 'public.platform_event', 'SELECT'),
                          has_table_privilege(%s, 'public.notification_outbox', 'SELECT'),
                          has_table_privilege(%s, 'public.notification_outbox', 'INSERT'),
                          has_table_privilege(%s, 'public.notification_outbox', 'UPDATE'),
                          has_table_privilege(%s, 'public.notification_outbox', 'DELETE')""",
                (
                    notification_enqueue_user, _NOTIFICATION_ENQUEUE_FUNCTION,
                    notification_enqueue_user, notification_enqueue_user,
                    notification_enqueue_user, notification_enqueue_user,
                    notification_enqueue_user,
                ),
            )
            if cur.fetchone() != (True, False, False, False, False, False):
                raise RuntimeError(
                    "notification-enqueue role is missing its bounded function grant "
                    "or has direct source/outbox table access"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = relation.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (
                            has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR EXISTS (
                                SELECT 1
                                  FROM pg_attribute AS attribute
                                 WHERE attribute.attrelid = relation.oid
                                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                                   AND (
                                     has_column_privilege(%s, relation.oid, attribute.attname, 'SELECT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'INSERT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'UPDATE')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'REFERENCES')
                                   )
                            )
                          )
                   )""",
                (notification_enqueue_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError(
                    "notification-enqueue role retains application table or column privileges"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS sequence
                         JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND sequence.relkind = 'S'
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = sequence.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (
                            has_sequence_privilege(%s, sequence.oid, 'USAGE')
                            OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                            OR has_sequence_privilege(%s, sequence.oid, 'UPDATE')
                          )
                   )""",
                (notification_enqueue_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("notification-enqueue role retains application sequence privileges")
            cur.execute(
                """SELECT procedure.oid::regprocedure::text
                     FROM pg_proc AS procedure
                     JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                    WHERE namespace.nspname IN ('public', 'kokonut_security')
                      AND procedure.prosecdef
                      AND procedure.oid <> to_regprocedure(%s)
                      AND has_function_privilege(%s, procedure.oid, 'EXECUTE')
                    LIMIT 1""",
                (_NOTIFICATION_ENQUEUE_FUNCTION, notification_enqueue_user),
            )
            other_security_definer = cur.fetchone()
            if other_security_definer is not None:
                raise RuntimeError(
                    "notification-enqueue role can execute another SECURITY DEFINER function: "
                    f"{other_security_definer[0]}"
                )
            cur.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                (runtime_user, _NOTIFICATION_ENQUEUE_FUNCTION),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role can execute notification-enqueue function")

        if market_data_user is not None:
            cur.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (market_data_user, _MARKET_DATA_FUNCTION, market_data_user, market_data_user),
            )
            if cur.fetchone() != (True, True, False):
                raise RuntimeError(
                    "market-data login is missing its bounded function grant or has unsafe schema access"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = relation.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (
                            has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR EXISTS (
                                SELECT 1
                                  FROM pg_attribute AS attribute
                                 WHERE attribute.attrelid = relation.oid
                                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                                   AND (
                                     has_column_privilege(%s, relation.oid, attribute.attname, 'SELECT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'INSERT')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'UPDATE')
                                     OR has_column_privilege(%s, relation.oid, attribute.attname, 'REFERENCES')
                                   )
                            )
                          )
                   )""",
                (market_data_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("market-data login retains application table or column privileges")
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS sequence
                         JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND sequence.relkind = 'S'
                          AND NOT EXISTS (
                              SELECT 1 FROM pg_depend AS extension_member
                               WHERE extension_member.classid = 'pg_class'::regclass
                                 AND extension_member.objid = sequence.oid
                                 AND extension_member.refclassid = 'pg_extension'::regclass
                                 AND extension_member.deptype = 'e'
                          )
                          AND (
                            has_sequence_privilege(%s, sequence.oid, 'USAGE')
                            OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                            OR has_sequence_privilege(%s, sequence.oid, 'UPDATE')
                          )
                   )""",
                (market_data_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("market-data login retains application sequence privileges")
            cur.execute(
                """SELECT procedure.oid::regprocedure::text
                     FROM pg_proc AS procedure
                     JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                    WHERE namespace.nspname IN ('public', 'kokonut_security')
                      AND procedure.prosecdef
                      AND procedure.oid <> to_regprocedure(%s)
                      AND has_function_privilege(%s, procedure.oid, 'EXECUTE')
                    LIMIT 1""",
                (_MARKET_DATA_FUNCTION, market_data_user),
            )
            other_security_definer = cur.fetchone()
            if other_security_definer is not None:
                raise RuntimeError(
                    "market-data login can execute another SECURITY DEFINER function: "
                    f"{other_security_definer[0]}"
                )
            cur.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                (runtime_user, _MARKET_DATA_FUNCTION),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role can execute market-data worker function")
        if eas_indexer_user is not None:
            _verify_role_attributes(cur, eas_indexer_user)
            cur.execute(
                "SELECT " + ", ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _EAS_INDEXER_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _EAS_INDEXER_FUNCTIONS
                    for value in (eas_indexer_user, function)
                ),
            )
            if cur.fetchone() != (True,) * len(_EAS_INDEXER_FUNCTIONS):
                raise RuntimeError("EAS-indexer login is missing one of its bounded functions")
            cur.execute(
                "SELECT has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (eas_indexer_user, eas_indexer_user),
            )
            if cur.fetchone() != (True, False):
                raise RuntimeError("EAS-indexer login has unsafe security schema privileges")
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND (
                            has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR has_any_column_privilege(%s, relation.oid, 'SELECT')
                            OR has_any_column_privilege(%s, relation.oid, 'INSERT')
                            OR has_any_column_privilege(%s, relation.oid, 'UPDATE')
                            OR has_any_column_privilege(%s, relation.oid, 'REFERENCES')
                          )
                   )""",
                (eas_indexer_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("EAS-indexer login retains direct relation privileges")
            cur.execute(
                """SELECT procedure.oid::regprocedure::text
                     FROM pg_proc AS procedure
                     JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                    WHERE namespace.nspname IN ('public', 'kokonut_security')
                      AND procedure.prosecdef
                      AND procedure.oid <> ALL(ARRAY[
                          to_regprocedure(%s), to_regprocedure(%s), to_regprocedure(%s),
                          to_regprocedure(%s), to_regprocedure(%s), to_regprocedure(%s),
                          to_regprocedure(%s)
                      ])
                      AND has_function_privilege(%s, procedure.oid, 'EXECUTE')
                    LIMIT 1""",
                (*_EAS_INDEXER_FUNCTIONS, eas_indexer_user),
            )
            unexpected_function = cur.fetchone()
            if unexpected_function is not None:
                raise RuntimeError(
                    "EAS-indexer login can execute another SECURITY DEFINER function: "
                    f"{unexpected_function[0]}"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM pg_class AS sequence
                       JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public' AND sequence.relkind = 'S'
                          AND (has_sequence_privilege(%s, sequence.oid, 'USAGE')
                               OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                               OR has_sequence_privilege(%s, sequence.oid, 'UPDATE'))
                   )""",
                (eas_indexer_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("EAS-indexer login retains application sequence privileges")
            cur.execute(
                "SELECT " + " OR ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _EAS_INDEXER_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _EAS_INDEXER_FUNCTIONS
                    for value in (runtime_user, function)
                ),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role can execute EAS-indexer worker functions")
        if rpc_indexer_user is not None:
            _verify_role_attributes(cur, rpc_indexer_user)
            cur.execute(
                "SELECT " + ", ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _RPC_INDEXER_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _RPC_INDEXER_FUNCTIONS
                    for value in (rpc_indexer_user, function)
                ),
            )
            if cur.fetchone() != (True,) * len(_RPC_INDEXER_FUNCTIONS):
                raise RuntimeError("RPC-indexer login is missing one of its bounded functions")
            cur.execute(
                "SELECT has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (rpc_indexer_user, rpc_indexer_user),
            )
            if cur.fetchone() != (True, False):
                raise RuntimeError("RPC-indexer login has unsafe security schema privileges")
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                          AND (
                            has_table_privilege(%s, relation.oid, 'SELECT')
                            OR has_table_privilege(%s, relation.oid, 'INSERT')
                            OR has_table_privilege(%s, relation.oid, 'UPDATE')
                            OR has_table_privilege(%s, relation.oid, 'DELETE')
                            OR has_table_privilege(%s, relation.oid, 'TRUNCATE')
                            OR has_table_privilege(%s, relation.oid, 'REFERENCES')
                            OR has_table_privilege(%s, relation.oid, 'TRIGGER')
                            OR has_any_column_privilege(%s, relation.oid, 'SELECT')
                            OR has_any_column_privilege(%s, relation.oid, 'INSERT')
                            OR has_any_column_privilege(%s, relation.oid, 'UPDATE')
                            OR has_any_column_privilege(%s, relation.oid, 'REFERENCES')
                          )
                   )""",
                (rpc_indexer_user,) * 11,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("RPC-indexer login retains direct relation privileges")
            cur.execute(
                """SELECT procedure.oid::regprocedure::text
                     FROM pg_proc AS procedure
                     JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                    WHERE namespace.nspname IN ('public', 'kokonut_security')
                      AND procedure.prosecdef
                      AND procedure.oid <> ALL(ARRAY[
                          to_regprocedure(%s), to_regprocedure(%s), to_regprocedure(%s),
                          to_regprocedure(%s), to_regprocedure(%s)
                      ])
                      AND has_function_privilege(%s, procedure.oid, 'EXECUTE')
                    LIMIT 1""",
                (*_RPC_INDEXER_FUNCTIONS, rpc_indexer_user),
            )
            if cur.fetchone() is not None:
                raise RuntimeError(
                    "RPC-indexer login can execute another SECURITY DEFINER function"
                )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM pg_class AS sequence
                       JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
                        WHERE namespace.nspname = 'public' AND sequence.relkind = 'S'
                          AND (has_sequence_privilege(%s, sequence.oid, 'USAGE')
                               OR has_sequence_privilege(%s, sequence.oid, 'SELECT')
                               OR has_sequence_privilege(%s, sequence.oid, 'UPDATE'))
                   )""",
                (rpc_indexer_user,) * 3,
            )
            if cur.fetchone()[0]:
                raise RuntimeError("RPC-indexer login retains application sequence privileges")
            cur.execute(
                "SELECT " + " OR ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _RPC_INDEXER_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _RPC_INDEXER_FUNCTIONS
                    for value in (runtime_user, function)
                ),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role can execute RPC-indexer worker functions")

        _verify_mobile_credential_boundary(cur, runtime_user)
        _verify_api_key_boundary(cur, runtime_user)
        _verify_farm_activity_operator_event_boundary(cur, runtime_user)
        _verify_solution_stage_gate_boundary(cur, runtime_user)
        _verify_solution_experiment_protocol_boundary(cur, runtime_user)
        _verify_no_runtime_default_privileges(
            cur, admin_user=admin_user, runtime_user=runtime_user
        )
        cur.execute(
            "SELECT has_function_privilege(%s, %s, 'EXECUTE'), "
            "has_function_privilege(%s, %s, 'EXECUTE'), "
            "has_function_privilege(%s, %s, 'EXECUTE')",
            (
                runtime_user, _GATEWAY_CONTEXT_FUNCTION,
                runtime_user, _OPERATOR_CONTEXT_FUNCTION,
                runtime_user, _MOBILE_DEVICE_REVOKE_FUNCTION,
            ),
        )
        if cur.fetchone() != (True, True, True):
            raise RuntimeError("runtime role is missing a bounded Gateway/mobile-device function")
        cur.execute(
            "SELECT has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
            "has_schema_privilege(%s, 'kokonut_security', 'USAGE')",
            (runtime_user, operator_auth_user),
        )
        if cur.fetchone() != (True, True):
            raise RuntimeError("runtime or operator-auth role is missing usage on kokonut_security")
        if notification_enqueue_user is not None:
            cur.execute(
                "SELECT has_schema_privilege(%s, 'kokonut_security', 'USAGE'), "
                "has_schema_privilege(%s, 'kokonut_security', 'CREATE')",
                (notification_enqueue_user, notification_enqueue_user),
            )
            if cur.fetchone() != (True, False):
                raise RuntimeError(
                    "notification-enqueue login has unsafe security schema privileges"
                )
        for function in (
            *_PRIVATE_RUNTIME_FUNCTIONS,
            *_EAS_INDEXER_FUNCTIONS,
            *_SENSOR_INGESTION_FUNCTIONS,
            *_REMOTE_SENSING_FUNCTIONS,
        ):
            _verify_no_public_function_execute(cur, function)
        _verify_security_definer_owners(cur)
        if remote_sensing_user is not None:
            cur.execute(
                "SELECT " + " OR ".join(
                    "has_function_privilege(%s, %s, 'EXECUTE')"
                    for _ in _REMOTE_SENSING_FUNCTIONS
                ),
                tuple(
                    value
                    for function in _REMOTE_SENSING_FUNCTIONS
                    for value in (runtime_user, function)
                ),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("runtime role can execute remote-sensing worker functions")
        if farm_activity_event_owner_ready:
            for function in (
                "public.guard_farm_activity_operator_event_insert()",
                "public.record_gateway_farm_activity_create()",
                "public.record_farm_activity_gateway_operation()",
            ):
                _verify_no_public_function_execute(cur, function)

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
        if market_data_user is not None:
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (market_data_user,),
            )
            market_data_database_access = {name: allowed for name, allowed in cur.fetchall()}
            if any(allowed != (name == database) for name, allowed in market_data_database_access.items()):
                raise RuntimeError("market-data login must connect only to its configured database")
        if eas_indexer_user is not None:
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (eas_indexer_user,),
            )
            eas_indexer_database_access = {name: allowed for name, allowed in cur.fetchall()}
            if any(allowed != (name == database) for name, allowed in eas_indexer_database_access.items()):
                raise RuntimeError("EAS-indexer login must connect only to its configured database")
        if rpc_indexer_user is not None:
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (rpc_indexer_user,),
            )
            rpc_indexer_database_access = {name: allowed for name, allowed in cur.fetchall()}
            if any(allowed != (name == database) for name, allowed in rpc_indexer_database_access.items()):
                raise RuntimeError("RPC-indexer login must connect only to its configured database")
        if sensor_ingestion_user is not None:
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (sensor_ingestion_user,),
            )
            sensor_ingestion_database_access = {name: allowed for name, allowed in cur.fetchall()}
            if any(allowed != (name == database) for name, allowed in sensor_ingestion_database_access.items()):
                raise RuntimeError("sensor-ingestion login must connect only to its configured database")
        if remote_sensing_user is not None:
            cur.execute(
                """SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                     FROM pg_database
                    WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname""",
                (remote_sensing_user,),
            )
            remote_sensing_database_access = {name: allowed for name, allowed in cur.fetchall()}
            if any(allowed != (name == database) for name, allowed in remote_sensing_database_access.items()):
                raise RuntimeError("remote-sensing login must connect only to its configured database")

    return {
        "status": "provisioned",
        "database": database,
        "runtime_user": runtime_user,
        "operator_auth_user": operator_auth_user,
        "notification_enqueue_user": notification_enqueue_user,
        "market_data_user": market_data_user,
        "eas_indexer_user": eas_indexer_user,
        "rpc_indexer_user": rpc_indexer_user,
        "sensor_ingestion_user": sensor_ingestion_user,
        "remote_sensing_user": remote_sensing_user,
        "public_connect_revoked_from": sorted(database_names),
        "runtime_connect_grants": runtime_database_access,
        "operator_auth_connect_grants": auth_database_access,
        "market_data_connect_grants": market_data_database_access,
        "eas_indexer_connect_grants": eas_indexer_database_access,
        "rpc_indexer_connect_grants": rpc_indexer_database_access,
        "sensor_ingestion_connect_grants": sensor_ingestion_database_access,
        "remote_sensing_connect_grants": remote_sensing_database_access,
        "runtime_table_privileges": ["SELECT", "INSERT", "UPDATE", "DELETE"],
        "runtime_table_privilege_scope": "existing_public_tables_only",
        "runtime_future_object_privileges": [],
        "runtime_table_privilege_exceptions": {
            "api_key": "explicit read-only column allowlist; no insert, update, or delete",
            "mobile_device": "read plus telemetry-only UPDATE columns; revocation uses a bounded function",
            "mobile_device_enrollment": "explicit column allowlist; no table-wide UPDATE or DELETE",
            "operator_session": "bounded functions only",
            "farm_activity_operator_event": "read-only SELECT; trigger owner appends; no direct write",
            "solution_stage_gate": "bounded security-definer functions only; no direct runtime access",
            "solution_experiment": (
                "bounded Gateway protocol creation; lifecycle updates limited to status and timestamps"
            ),
        },
        "runtime_mobile_credential_privileges": mobile_credential_grants,
        "runtime_api_key_privileges": api_key_grants,
        "runtime_farm_activity_operator_event_privileges": farm_activity_event_grants,
        "runtime_solution_stage_gate_privileges": solution_stage_gate_grants,
        "runtime_solution_experiment_protocol_privileges": solution_experiment_protocol_grants,
        "farm_activity_event_owner_restored": farm_activity_event_owner_ready,
        "operator_session_access": "bounded functions only",
        "security_definer_owners_verified": True,
        "operator_auth_functions": ["create", "authenticate", "revoke"],
        "runtime_gateway_function": "set_gateway_tenant_context",
        "runtime_operator_context_function": "set_operator_tenant_context",
        "runtime_mobile_device_revoke_function": "revoke_mobile_device",
        "runtime_owns_relations": False,
        "operator_auth_owns_relations": False,
        "notification_enqueue_owns_relations": False,
        "market_data_owns_relations": False,
        "eas_indexer_owns_relations": False,
        "rpc_indexer_owns_relations": False,
        "sensor_ingestion_owns_relations": False,
        "remote_sensing_owns_relations": False,
    }


def main() -> int:
    database = os.environ.get("PG_DB", "kokonut_intelligence")
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    runtime_user = os.environ.get("KOKONUT_RUNTIME_USER", "kokonut_runtime")
    runtime_password = os.environ.get("KOKONUT_RUNTIME_PASSWORD", "")
    operator_auth_user = os.environ.get("KOKONUT_OPERATOR_AUTH_USER", "kokonut_operator_auth")
    operator_auth_password = os.environ.get("KOKONUT_OPERATOR_AUTH_PASSWORD", "")
    notification_enqueue_user = os.environ.get(
        "KOKONUT_NOTIFICATION_ENQUEUE_USER", "kokonut_notification_enqueue_login"
    )
    notification_enqueue_password = os.environ.get(
        "KOKONUT_NOTIFICATION_ENQUEUE_PASSWORD", ""
    )
    market_data_user = os.environ.get(
        "KOKONUT_MARKET_DATA_USER", "kokonut_market_data_login"
    )
    market_data_password = os.environ.get("KOKONUT_MARKET_DATA_PASSWORD", "")
    eas_indexer_user = os.environ.get(
        "KOKONUT_EAS_INDEXER_USER", "kokonut_eas_indexer_login"
    )
    eas_indexer_password = os.environ.get("KOKONUT_EAS_INDEXER_PASSWORD", "")
    rpc_indexer_user = os.environ.get(
        "KOKONUT_RPC_INDEXER_USER", "kokonut_rpc_indexer_login"
    )
    rpc_indexer_password = os.environ.get("KOKONUT_RPC_INDEXER_PASSWORD", "")
    sensor_ingestion_user = os.environ.get(
        "KOKONUT_SENSOR_INGESTION_USER", "kokonut_sensor_ingestion_login"
    )
    sensor_ingestion_password = os.environ.get("KOKONUT_SENSOR_INGESTION_PASSWORD", "")
    remote_sensing_user = os.environ.get(
        "KOKONUT_REMOTE_SENSING_USER", "kokonut_remote_sensing_login"
    )
    remote_sensing_password = os.environ.get("KOKONUT_REMOTE_SENSING_PASSWORD", "")
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
            notification_enqueue_user=(
                notification_enqueue_user if notification_enqueue_password else None
            ),
            notification_enqueue_password=(
                notification_enqueue_password if notification_enqueue_password else None
            ),
            market_data_user=market_data_user if market_data_password else None,
            market_data_password=market_data_password if market_data_password else None,
            eas_indexer_user=eas_indexer_user if eas_indexer_password else None,
            eas_indexer_password=eas_indexer_password if eas_indexer_password else None,
            rpc_indexer_user=rpc_indexer_user if rpc_indexer_password else None,
            rpc_indexer_password=rpc_indexer_password if rpc_indexer_password else None,
            sensor_ingestion_user=(
                sensor_ingestion_user if sensor_ingestion_password else None
            ),
            sensor_ingestion_password=(
                sensor_ingestion_password if sensor_ingestion_password else None
            ),
            remote_sensing_user=(remote_sensing_user if remote_sensing_password else None),
            remote_sensing_password=(
                remote_sensing_password if remote_sensing_password else None
            ),
        )
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
