"""Exercise real operator logins against a fresh, disposable full-schema database.

The schema replay runner invokes this client inside the database container's
network namespace. Credentials and records are generated solely for that run.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from contextlib import closing

import psycopg2
from psycopg2 import errors, sql

from services.migration.runtime_role import (
    _API_KEY_COLUMNS,
    _RUNTIME_APPEND_ONLY_TABLES,
    _RUNTIME_MUTATION_TABLES,
    _RUNTIME_PRIVATE_TABLES,
    provision_runtime_role,
)

PROBE_STAGE = "target_validation"


def _connection(database: str, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=5432, dbname=database, user=user,
        password=password, connect_timeout=10,
    )


def _expect_session_table_denied(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT session_token_hash FROM public.operator_session LIMIT 1")
    except errors.InsufficientPrivilege:
        conn.rollback()
        return
    raise AssertionError("a restricted login could read the operator session table")


def _context(cur, session_hash: str, operator_id: str, location_id: str):
    cur.execute(
        """SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
             FROM kokonut_security.set_operator_tenant_context(
                 %s, %s::uuid, %s::uuid, 'farm_activity', 'read', '[]'::jsonb
             )""",
        (session_hash, operator_id, location_id),
    )
    return cur.fetchall()


def _assert_scoped_runtime_acl(cur) -> dict[str, int]:
    """Verify migration-installed runtime ACLs, including column grants."""
    mutation_privileges = (
        "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER",
    )
    private_privileges = (
        "SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER",
    )

    def relation_exists(table: str) -> bool:
        cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
        return cur.fetchone()[0] is not None

    def has_table_privilege(table: str, privilege: str) -> bool:
        cur.execute(
            "SELECT has_table_privilege(current_user, %s, %s)",
            (f"public.{table}", privilege),
        )
        return bool(cur.fetchone()[0])

    def has_column_privilege(table: str, privilege: str) -> bool:
        cur.execute(
            """SELECT EXISTS (
                   SELECT 1
                     FROM pg_attribute
                    WHERE attrelid = %s::regclass
                      AND attnum > 0 AND NOT attisdropped
                      AND has_column_privilege(
                          current_user, %s::regclass, attname, %s
                      )
               )""",
            (f"public.{table}", f"public.{table}", privilege),
        )
        return bool(cur.fetchone()[0])

    private_installed = 0
    mutation_installed = 0
    for table in _RUNTIME_PRIVATE_TABLES:
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing private runtime relation {table}")
        private_installed += 1
        if any(has_table_privilege(table, privilege) for privilege in private_privileges):
            raise AssertionError(f"runtime login retains table privilege on {table}")
        column_privileges = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
        if any(has_column_privilege(table, privilege) for privilege in column_privileges):
            raise AssertionError(f"runtime login retains column privilege on {table}")

    for table in _RUNTIME_MUTATION_TABLES:
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing mutation-denied relation {table}")
        mutation_installed += 1
        if any(has_table_privilege(table, privilege) for privilege in mutation_privileges):
            raise AssertionError(f"runtime login retains table mutation privilege on {table}")
        if any(has_column_privilege(table, privilege) for privilege in ("INSERT", "UPDATE", "REFERENCES")):
            raise AssertionError(f"runtime login retains column mutation privilege on {table}")

    if not has_table_privilege("farm_activity_operator_event", "SELECT"):
        raise AssertionError("runtime login lost read access to the farm-activity audit ledger")
    if not relation_exists("advisory_rule") or not has_table_privilege(
        "advisory_rule", "SELECT"
    ):
        raise AssertionError("runtime login lost read access to shared advisory rules")
    if not relation_exists("crop_nutrient_removal_factor"):
        raise AssertionError("full schema is missing crop nutrient removal factors")
    cur.execute("SELECT count(*) FROM public.crop_nutrient_removal_factor")
    if cur.fetchone()[0] < 1:
        raise AssertionError("runtime login cannot read seeded crop nutrient factors")
    if not relation_exists("ghg_emission_factor"):
        raise AssertionError("full schema is missing greenhouse-gas emission factors")
    cur.execute("SELECT count(*) FROM public.ghg_emission_factor")
    cur.fetchone()
    if not relation_exists("operations_protocol"):
        raise AssertionError("full schema is missing operations protocols")
    cur.execute("SELECT count(*) FROM public.operations_protocol")
    cur.fetchone()
    for table, label in (
        ("process_maturity_level", "process maturity levels"),
        ("pollinator_species_reference", "pollinator species references"),
    ):
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing {label}")
        cur.execute(
            sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
        )
        if cur.fetchone()[0] < 1:
            raise AssertionError(f"runtime login cannot read {label}")
    for table, label in (
        ("gri_indicator", "GRI indicator mappings"),
        ("governance_framework", "governance framework registry"),
        ("impact_framework", "impact framework references"),
        ("impact_dimension", "impact framework dimensions"),
        ("expense_category", "expense categories"),
        ("crisp_risk_dimension", "CRISP risk dimension definitions"),
        ("dfs_currency", "currency references"),
        ("crop_gdd_config", "crop GDD configuration"),
    ):
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing {label}")
        # Schema replay deliberately skips seed files. The read itself is the
        # acceptance assertion; this empty fixture does not claim seeded data.
        cur.execute(
            sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
        )
        cur.fetchone()
    if not relation_exists("certification_type"):
        raise AssertionError("full schema is missing certification types")
    cur.execute("SELECT count(*) FROM public.certification_type")
    if cur.fetchone()[0] < 1:
        raise AssertionError("runtime login cannot read seeded certification types")
    if not relation_exists("dfs_currency"):
        raise AssertionError("full schema is missing currency references")
    cur.execute("SELECT 1 FROM public.dfs_currency WHERE code = 'USD'")
    if cur.fetchone() is None:
        raise AssertionError("runtime login cannot read the seeded USD currency")
    for table, label in (
        ("cooperative_type", "cooperative types"),
        ("dfs_insurance_product_type", "insurance product types"),
    ):
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing {label}")
        cur.execute(
            sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
        )
        if cur.fetchone()[0] < 1:
            raise AssertionError(f"runtime login cannot read seeded {label}")

    append_only_verified = 0
    for table in _RUNTIME_APPEND_ONLY_TABLES:
        if not relation_exists(table):
            raise AssertionError(f"full schema is missing append-only runtime relation {table}")
        expected = {
            "SELECT": True,
            "INSERT": True,
            "UPDATE": False,
            "DELETE": False,
            "TRUNCATE": False,
            "REFERENCES": False,
            "TRIGGER": False,
        }
        observed = {privilege: has_table_privilege(table, privilege) for privilege in expected}
        if observed != expected:
            raise AssertionError(f"runtime append-only ACL is unexpected on {table}")
        cur.execute(
            """SELECT EXISTS (
                   SELECT 1
                     FROM pg_attribute AS column_row
                     CROSS JOIN LATERAL aclexplode(column_row.attacl) AS privilege
                    WHERE column_row.attrelid = %s::regclass
                      AND column_row.attnum > 0
                      AND NOT column_row.attisdropped
                      AND privilege.grantee = (SELECT oid FROM pg_roles WHERE rolname = current_user)
                      AND privilege.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES')
               )""",
            (f"public.{table}",),
        )
        if cur.fetchone()[0]:
            raise AssertionError(f"runtime login retains column-level access on {table}")
        append_only_verified += 1

    return {
        "private_relations_verified": private_installed,
        "mutation_denied_relations_verified": mutation_installed,
        "direct_table_privilege_violations": 0,
        "direct_column_privilege_violations": 0,
        "farm_activity_ledger_readable": 1,
        "append_only_relations_expected": len(_RUNTIME_APPEND_ONLY_TABLES),
        "append_only_relations_verified": append_only_verified,
        "append_only_select_insert_verified": append_only_verified,
        "append_only_mutations_denied": append_only_verified,
        "append_only_column_grants_denied": append_only_verified,
    }


def run_probe() -> dict[str, object]:
    global PROBE_STAGE
    database = os.environ.get("SPRINT_DATABASE", "")
    if os.environ.get("SPRINT_DISPOSABLE") != "yes" or not re.fullmatch(
        r"kokonut_bootstrap_[0-9]+", database
    ):
        raise ValueError("probe requires the isolated schema replay target")

    admin_password = os.environ["SPRINT_ADMIN_PASSWORD"]
    runtime_password = os.environ["SPRINT_RUNTIME_PASSWORD"]
    auth_password = os.environ["SPRINT_AUTH_PASSWORD"]
    organizations = [str(uuid.uuid4()), str(uuid.uuid4())]
    locations = [str(uuid.uuid4()), str(uuid.uuid4())]
    operators = [str(uuid.uuid4()), str(uuid.uuid4())]
    subjects = ["sprint-operator-a", "sprint-operator-b"]
    session_hashes = [secrets.token_hex(32), secrets.token_hex(32)]
    csrf_hashes = [secrets.token_hex(32), secrets.token_hex(32)]
    issuer = "https://sprint-identity.example"
    checks: list[str] = []

    PROBE_STAGE = "provision_runtime_and_auth_roles"
    with closing(_connection(database, "kokonut", admin_password)) as admin:
        provisioned = provision_runtime_role(
            admin,
            database=database,
            admin_user="kokonut",
            admin_password=admin_password,
            runtime_user="kokonut_runtime",
            runtime_password=runtime_password,
            operator_auth_user="kokonut_operator_auth",
            operator_auth_password=auth_password,
        )
        if provisioned["status"] != "provisioned":
            raise AssertionError("runtime role provisioning did not complete")
        scoped_write = provisioned.get("runtime_scoped_write_privileges")
        relations = scoped_write.get("relations") if isinstance(scoped_write, dict) else None
        expected_relations = set(_RUNTIME_PRIVATE_TABLES) | set(_RUNTIME_MUTATION_TABLES)
        if not isinstance(relations, dict) or set(relations) != expected_relations:
            raise AssertionError("runtime provisioner returned an incomplete scoped ACL policy")
        if not all(relations.values()):
            raise AssertionError("runtime provisioner did not find every scoped ACL relation")
        api_key_privileges = provisioned.get("runtime_api_key_privileges")
        expected_api_key_privileges = {
            "select": list(_API_KEY_COLUMNS),
            "insert": [],
            "update": [],
            "delete": False,
        }
        if api_key_privileges != expected_api_key_privileges:
            raise AssertionError("runtime provisioner returned an unexpected API-key boundary")
        append_only_privileges = provisioned.get("runtime_append_only_privileges")
        if not isinstance(append_only_privileges, dict) or append_only_privileges.get(
            "relations"
        ) != {table: True for table in _RUNTIME_APPEND_ONLY_TABLES}:
            raise AssertionError("runtime provisioner returned an incomplete append-only policy")
        with admin.cursor() as cur:
            cur.execute(
                """SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolreplication, rolbypassrls
                     FROM pg_roles
                    WHERE rolname IN ('kokonut_runtime', 'kokonut_operator_auth')"""
            )
            roles = cur.fetchall()
            if len(roles) != 2 or any(
                not role[1] or any(role[2:]) for role in roles
            ):
                raise AssertionError("runtime or auth login has unsafe role attributes")
        checks.append("runtime and operator-auth logins cannot bypass RLS or create roles or databases")
        PROBE_STAGE = "seed_synthetic_tenants"
        admin.autocommit = False
        with admin.cursor() as cur:
            for index in range(2):
                cur.execute(
                    "INSERT INTO public.organization (id, org_key, name, status) VALUES (%s, %s, %s, 'active')",
                    (organizations[index], f"sprint-{index}-{uuid.uuid4().hex}", f"Sprint tenant {index}"),
                )
                cur.execute(
                    """INSERT INTO public.location (id, name, slug, organization_id, status)
                       VALUES (%s, %s, %s, %s, 'active')""",
                    (locations[index], f"Sprint location {index}", f"sprint-{index}-{uuid.uuid4().hex}", organizations[index]),
                )
                cur.execute(
                    """INSERT INTO public.location_tenant_owner_verification
                           (location_id, organization_id, decision_reference, confirmed_by)
                       VALUES (%s, %s, %s, 'synthetic sprint fixture')""",
                    (locations[index], organizations[index], f"sprint-{uuid.uuid4()}"),
                )
                cur.execute(
                    """INSERT INTO public.operator_identity (id, issuer, subject, enabled)
                       VALUES (%s, %s, %s, TRUE)""",
                    (operators[index], issuer, subjects[index]),
                )
                cur.execute(
                    """INSERT INTO public.operator_organization_membership
                           (operator_id, organization_id, granted_by)
                       VALUES (%s, %s, 'synthetic sprint fixture')""",
                    (operators[index], organizations[index]),
                )
                cur.execute(
                    """INSERT INTO public.operator_scope_grant
                           (operator_id, resource, action, location_id, organization_id, granted_by)
                       VALUES (%s, 'farm_activity', 'read', %s, %s, 'synthetic sprint fixture')""",
                    (operators[index], locations[index], organizations[index]),
                )
            cur.execute(
                "CREATE TABLE public.sprint_tenant_probe (tenant_id uuid NOT NULL, marker text NOT NULL)"
            )
            cur.executemany(
                "INSERT INTO public.sprint_tenant_probe (tenant_id, marker) VALUES (%s, %s)",
                [(organizations[0], "tenant-a"), (organizations[1], "tenant-b")],
            )
            cur.execute("GRANT SELECT ON public.sprint_tenant_probe TO kokonut_runtime")
            cur.execute("ALTER TABLE public.sprint_tenant_probe ENABLE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE public.sprint_tenant_probe FORCE ROW LEVEL SECURITY")
            cur.execute(
                """CREATE POLICY sprint_tenant_probe_scope ON public.sprint_tenant_probe
                   FOR SELECT TO kokonut_runtime
                   USING (tenant_id = (SELECT tenant_id FROM kokonut_security.current_tenant_context()))"""
            )
        admin.commit()
        checks.append("two synthetic tenant/location/identity/grant sets were created")

        PROBE_STAGE = "restricted_logins"
        with closing(_connection(database, "kokonut_runtime", runtime_password)) as runtime, closing(
            _connection(database, "kokonut_operator_auth", auth_password)
        ) as auth:
            _expect_session_table_denied(runtime)
            _expect_session_table_denied(auth)
            checks.append("both restricted logins are denied direct operator-session reads")

            PROBE_STAGE = "create_sessions"
            session_ids = []
            with auth.cursor() as cur:
                for index in range(2):
                    cur.execute(
                        """SELECT session_id::text, operator_id::text
                             FROM kokonut_security.create_operator_session(
                                 %s, %s, NULL, NULL, %s, %s, now() + interval '1 hour'
                             )""",
                        (issuer, subjects[index], session_hashes[index], csrf_hashes[index]),
                    )
                    row = cur.fetchone()
                    if row is None or row[1] != operators[index]:
                        raise AssertionError("bounded session creation returned the wrong operator")
                    session_ids.append(row[0])
            auth.commit()
            checks.append("operator-auth login created two sessions through the bounded function")

            PROBE_STAGE = "signed_tenant_context"
            with runtime.cursor() as cur:
                scoped_acl = _assert_scoped_runtime_acl(cur)
                for index in range(2):
                    expected = [(organizations[index], locations[index], operators[index], "operator")]
                    if _context(cur, session_hashes[index], operators[index], locations[index]) != expected:
                        raise AssertionError("authorized tenant context did not match its operator")
                    cur.execute("SELECT marker FROM public.sprint_tenant_probe")
                    if cur.fetchall() != [(f"tenant-{'a' if index == 0 else 'b'}",)]:
                        raise AssertionError("forced-RLS probe returned another tenant's data")
                if _context(cur, session_hashes[0], operators[0], locations[1]):
                    raise AssertionError("wrong-location operator context was accepted")
                cur.execute("SELECT marker FROM public.sprint_tenant_probe")
                if cur.fetchall():
                    raise AssertionError("a denied context retained tenant visibility")
            runtime.commit()
            with runtime.cursor() as cur:
                cur.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
                if cur.fetchone()[0] != 0:
                    raise AssertionError("tenant context survived transaction end")
            runtime.rollback()
            checks.extend([
                "runtime provisioner denied direct table and column access to private relations",
                "runtime provisioner denied direct mutations on scoped relations and preserved farm-activity ledger reads",
                "runtime provisioner keeps shared advisory rules readable but immutable",
                "runtime can read seeded crop-nutrient removal factors",
                "runtime can query shared greenhouse-gas emission-factor references",
                "runtime can query shared versioned operations protocols",
                "runtime can read static process maturity levels",
                "runtime can read static pollinator species references",
                "runtime can query shared GRI indicator mappings",
                "runtime can query the governance framework registry",
                "runtime can query shared impact frameworks",
                "runtime can query shared impact framework dimensions",
                "runtime can read governed expense categories",
                "runtime can query shared CRISP risk dimension definitions",
                "runtime can query shared currency references",
                "runtime can read crop GDD configuration",
                "runtime can read seeded certification types",
                "runtime can read seeded cooperative types",
                "runtime can read seeded insurance product types",
                "runtime provisioner limited API-key reads to reviewed columns and denied all writes",
                "runtime can append and read data-access evidence but cannot update, delete, or truncate it",
                "each real runtime login context sees only its synthetic tenant under forced RLS",
                "wrong-location denial clears context and tenant-probe visibility",
                "tenant context is cleared at transaction end",
            ])

            PROBE_STAGE = "revocation"
            with admin.cursor() as cur:
                cur.execute(
                    "UPDATE public.operator_scope_grant SET revoked_at = now() WHERE operator_id = %s",
                    (operators[0],),
                )
            admin.commit()
            with auth.cursor() as cur:
                cur.execute("SELECT kokonut_security.revoke_operator_session(%s::uuid)", (session_ids[1],))
                if cur.fetchone()[0] is not True:
                    raise AssertionError("operator-auth login could not revoke its session")
            auth.commit()
            with runtime.cursor() as cur:
                if _context(cur, session_hashes[0], operators[0], locations[0]):
                    raise AssertionError("revoked grant remained authorized")
                if _context(cur, session_hashes[1], operators[1], locations[1]):
                    raise AssertionError("revoked session remained authorized")
                cur.execute(
                    """SELECT count(*) FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public' AND relation.relkind IN ('r', 'p')
                          AND NOT relation.relrowsecurity
                          AND (has_table_privilege(current_user, relation.oid, 'INSERT')
                            OR has_table_privilege(current_user, relation.oid, 'UPDATE')
                            OR has_table_privilege(current_user, relation.oid, 'DELETE'))"""
                )
                unprotected_dml_tables = cur.fetchone()[0]
                cur.execute(
                    """SELECT namespace.nspname, relation.relname, relation.relkind,
                              has_table_privilege(current_user, relation.oid, 'SELECT'),
                              has_table_privilege(current_user, relation.oid, 'INSERT'),
                              has_table_privilege(current_user, relation.oid, 'UPDATE'),
                              has_table_privilege(current_user, relation.oid, 'DELETE'),
                              has_table_privilege(current_user, relation.oid, 'TRUNCATE'),
                              relation.relrowsecurity, relation.relforcerowsecurity
                         FROM pg_class AS relation
                         JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = 'public'
                          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
                        ORDER BY namespace.nspname, relation.relname"""
                )
                runtime_relation_acl = [
                    {
                        "schema": row[0],
                        "relation": row[1],
                        "kind": row[2],
                        "select": row[3],
                        "insert": row[4],
                        "update": row[5],
                        "delete": row[6],
                        "truncate": row[7],
                        "rls_enabled": row[8],
                        "rls_forced": row[9],
                    }
                    for row in cur.fetchall()
                ]
                cur.execute(
                    """SELECT grantor.rolname, defaults.defaclobjtype,
                              COALESCE(namespace.nspname, '<all schemas>'),
                              bool_or(privilege.grantee IN (
                                  0, (SELECT oid FROM pg_roles WHERE rolname = current_user)
                              ))
                         FROM pg_default_acl AS defaults
                         JOIN pg_roles AS grantor ON grantor.oid = defaults.defaclrole
                         LEFT JOIN pg_namespace AS namespace
                           ON namespace.oid = defaults.defaclnamespace
                         CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS privilege
                        WHERE defaults.defaclnamespace = 0
                           OR namespace.nspname = 'public'
                        GROUP BY grantor.rolname, defaults.defaclobjtype,
                                 COALESCE(namespace.nspname, '<all schemas>')
                        ORDER BY grantor.rolname, defaults.defaclobjtype,
                                 COALESCE(namespace.nspname, '<all schemas>')"""
                )
                default_acl_inventory = [
                    {
                        "grantor": row[0],
                        "object_type": row[1],
                        "schema": row[2],
                        "runtime_or_public_grantee": row[3],
                    }
                    for row in cur.fetchall()
                ]
            runtime.rollback()
            checks.append("revoked grant and revoked session both fail closed")

    return {
        "result": "passed",
        "checks": checks,
        "synthetic_tenant_count": 2,
        "synthetic_location_count": 2,
        "synthetic_operator_count": 2,
        "runtime_public_tables_with_dml_and_rls_disabled": unprotected_dml_tables,
        "runtime_scoped_write_policy": {
            "private_relations_expected": len(_RUNTIME_PRIVATE_TABLES),
            "mutation_denied_relations_expected": len(_RUNTIME_MUTATION_TABLES),
            **scoped_acl,
        },
        "runtime_api_key_policy": {
            "select_columns": list(_API_KEY_COLUMNS),
            "insert_columns": [],
            "update_columns": [],
            "delete": False,
            "verified_by_provisioner": True,
        },
        "runtime_append_only_policy": {
            "relations_expected": scoped_acl["append_only_relations_expected"],
            "relations_verified": scoped_acl["append_only_relations_verified"],
            "select_insert_verified": scoped_acl["append_only_select_insert_verified"],
            "mutations_denied": scoped_acl["append_only_mutations_denied"],
            "column_grants_denied": scoped_acl["append_only_column_grants_denied"],
            "verified_by_provisioner": True,
        },
        "runtime_public_relation_acl": runtime_relation_acl,
        "runtime_default_acl": default_acl_inventory,
        "scope_limit": (
            "The relation inventory reports effective table-level privileges only for "
            "public relations. Forced RLS is enabled only on a synthetic probe table. "
            "This is not a complete column, sequence, view definition, worker, Directus, "
            "function, ownership, or production authorization audit."
        ),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run_probe()))
    except Exception as exc:  # Keep test credentials and fixture values out of output.
        print(json.dumps({"result": "failed", "stage": PROBE_STAGE, "error_type": type(exc).__name__, "sqlstate": getattr(exc, "pgcode", None)}))
        raise SystemExit(1) from None
