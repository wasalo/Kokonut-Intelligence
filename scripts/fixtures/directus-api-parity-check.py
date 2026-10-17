#!/usr/bin/env python3
"""Exercise Directus API location permissions on a disposable populated clone.

The runner uses two verified same-owner locations when available, otherwise
creates a synthetic organization and locations only inside the clone. It never
changes existing organization ownership or enables tenant RLS. All inserted
rows and temporary Directus users are removed in a finally block.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date

import psycopg2

DIRECTUS_URL = os.environ.get("DIRECTUS_BASE_URL", "http://directus-runtime:8055").rstrip("/")
ADMIN_EMAIL = os.environ.get("DIRECTUS_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("DIRECTUS_ADMIN_PASSWORD", "")
PG_HOST = os.environ.get("PG_HOST", "database")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
PG_PASSWORD = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
DIRECTUS_RUNTIME_PASSWORD = os.environ.get("DIRECTUS_ROLE_PASSWORD", "")
FIELD_WORKER_ROLE = "a1000000-0000-0000-0000-000000000001"
OPERATOR_OIDC_ISSUER = os.environ.get(
    "KOKONUT_OPERATOR_OIDC_ISSUER", "https://directus-parity.invalid/issuer"
)


class StopCheck(Exception):
    """Exit the acceptance run after recording a sanitized blocking reason."""


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    query: dict[str, str] | None = None,
) -> tuple[int, dict | None]:
    url = f"{DIRECTUS_URL}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read()
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None
            return response.status, parsed
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return error.code, parsed


def connect_db():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        connect_timeout=8,
        application_name="directus-api-parity-check",
    )


def connect_directus_runtime_db():
    if not DIRECTUS_RUNTIME_PASSWORD:
        raise RuntimeError("the isolated Directus runtime password is missing")
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user="kokonut_directus_runtime",
        password=DIRECTUS_RUNTIME_PASSWORD,
        connect_timeout=8,
        application_name="directus-api-parity-runtime-check",
    )


def main() -> int:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD or not PG_PASSWORD:
        print(json.dumps({"result": "blocked", "reason": "required isolated credentials are missing"}))
        return 2

    evidence: dict[str, object] = {
        "scope": "isolated populated clone; synthetic Directus identities and rows",
        "candidate_or_legacy_modified": False,
    }
    users: list[str] = []
    row_ids: list[uuid.UUID] = []
    field_note_ids: list[uuid.UUID] = []
    synthetic_location_ids: list[str] = []
    synthetic_owner_verification_ids: list[str] = []
    synthetic_organization_id: str | None = None
    operator_id: str | None = None
    test_subject: str | None = None
    admin_token: str | None = None
    conn = None
    runtime_conn = None
    exit_code = 0

    try:
        health_status, _ = api_request("GET", "/server/ping")
        evidence["directus_health_status"] = health_status
        if health_status != 200:
            evidence["result"] = "blocked"
            evidence["reason"] = "pinned Directus runtime is not healthy"
            exit_code = 2
            raise StopCheck

        login_status, login_body = api_request(
            "POST",
            "/auth/login",
            payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        admin_token = ((login_body or {}).get("data") or {}).get("access_token")
        evidence["admin_login_status"] = login_status
        if login_status != 200 or not admin_token:
            evidence["result"] = "blocked"
            evidence["reason"] = "configured local admin credentials did not authenticate against the isolated copy"
            exit_code = 2
            raise StopCheck

        collection_status, collection_body = api_request(
            "GET", "/collections/farm_activity", token=admin_token
        )
        collection_data = (collection_body or {}).get("data") or {}
        evidence["admin_farm_activity_collection_status"] = collection_status
        evidence["admin_farm_activity_collection_registered"] = (
            collection_data.get("collection") == "farm_activity"
        )
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT
                       EXISTS (
                           SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'directus_users'
                              AND column_name = 'external_identifier'
                       ),
                       EXISTS (
                           SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'operator_scope_grant'
                              AND column_name = 'organization_id'
                       ),
                       to_regprocedure('public.operator_scope_grant_allows(uuid,text,text,uuid)') IS NOT NULL,
                       to_regclass('public.location_tenant_owner_verification') IS NOT NULL,
                       to_regclass('public.operator_organization_membership') IS NOT NULL"""
            )
            identity_schema = cur.fetchone()
            tenant_schema_available = all(bool(value) for value in identity_schema)
            evidence["tenant_grant_schema_available"] = tenant_schema_available
            if not tenant_schema_available:
                evidence["tenant_scope_testable"] = False
                evidence["result"] = "blocked"
                evidence["reason"] = "organization/location grant schema is not fully migrated on the isolated copy"
                evidence["probe_skipped"] = [
                    "synthetic operator and Directus user creation",
                    "synthetic farm-activity row insertion",
                    "user-scoped API reads and writes",
                ]
                exit_code = 2
                raise StopCheck

            cur.execute("SELECT id::text FROM public.location ORDER BY id LIMIT 2")
            available_locations = [row[0] for row in cur.fetchall()]
            cur.execute(
                """WITH verified AS (
                       SELECT loc.id AS location_id, owner_row.organization_id
                         FROM public.location AS loc
                         JOIN public.location_tenant_owner_verification AS owner_row
                           ON owner_row.location_id = loc.id
                          AND owner_row.organization_id = loc.organization_id
                          AND owner_row.revoked_at IS NULL
                         JOIN public.organization AS org
                           ON org.id = owner_row.organization_id
                          AND org.status = 'active'
                   ), eligible_organization AS (
                       SELECT organization_id
                         FROM verified
                        GROUP BY organization_id
                       HAVING COUNT(*) >= 2
                        ORDER BY organization_id
                        LIMIT 1
                   )
                   SELECT verified.location_id::text, verified.organization_id::text
                     FROM verified
                     JOIN eligible_organization USING (organization_id)
                    ORDER BY verified.location_id
                    LIMIT 2"""
            )
            owned_locations = cur.fetchall()
            locations = [row[0] for row in owned_locations]
            organization_ids = {row[1] for row in owned_locations}
            if len(locations) < 2 or len(organization_ids) != 1:
                # A recovered candidate checkpoint may intentionally contain
                # no farm rows. Keep this API check deterministic by creating
                # a minimal, explicitly synthetic tenant inside the isolated
                # copy rather than borrowing or changing real farm ownership.
                cur.execute(
                    """INSERT INTO public.organization (
                           org_key, name, org_type, status, metadata
                       ) VALUES (%s, 'Synthetic Directus parity organization',
                                 'enterprise', 'active', '{"fixture":true}'::jsonb)
                       RETURNING id::text""",
                    (f"kernel-directus-parity-{uuid.uuid4().hex}",),
                )
                synthetic_organization_id = cur.fetchone()[0]
                locations = []
                for index in range(2):
                    slug = f"kernel-directus-parity-{uuid.uuid4().hex}"
                    cur.execute(
                        """INSERT INTO public.location (
                               name, slug, country, status, organization_id, metadata
                           ) VALUES (%s, %s, 'Synthetic fixture', 'active', %s::uuid,
                                     '{"fixture":true}'::jsonb)
                           RETURNING id::text""",
                        (
                            f"Synthetic Directus parity location {index + 1}",
                            slug,
                            synthetic_organization_id,
                        ),
                    )
                    location_id = cur.fetchone()[0]
                    locations.append(location_id)
                    synthetic_location_ids.append(location_id)
                    cur.execute(
                        """INSERT INTO public.organization_member (
                               organization_id, location_id, membership_type,
                               role, status, metadata
                           ) VALUES (%s::uuid, %s::uuid, 'owned', 'primary', 'active',
                                     '{"ownership_reconciliation":"owner_confirmed", "fixture":true}'::jsonb)""",
                        (synthetic_organization_id, location_id),
                    )
                    cur.execute(
                        """INSERT INTO public.location_tenant_owner_verification (
                               location_id, organization_id, decision_reference, confirmed_by
                           ) VALUES (%s::uuid, %s::uuid, %s, 'isolated Directus parity fixture')
                           RETURNING id::text""",
                        (
                            location_id,
                            synthetic_organization_id,
                            f"directus-parity:{uuid.uuid4().hex}",
                        ),
                    )
                    synthetic_owner_verification_ids.append(cur.fetchone()[0])
                organization_ids = {synthetic_organization_id}
                evidence["tenant_locations"] = "two synthetic locations in isolated copy"
            else:
                evidence["tenant_locations"] = "existing verified owner locations in isolated copy"
            evidence["verified_owned_location_count_available"] = len(locations)
            evidence["two_general_locations_available"] = len(available_locations) >= 2
            if len(locations) < 2 or len(organization_ids) != 1:
                evidence["result"] = "blocked"
                evidence["reason"] = "two locations with the same active verified owner are required for the scoped API probe"
                exit_code = 2
                raise StopCheck
            cur.execute(
                "SELECT id::text FROM public.directus_roles WHERE id = %s::uuid AND name = 'Field Worker'",
                (FIELD_WORKER_ROLE,),
            )
            if not cur.fetchone():
                evidence["result"] = "blocked"
                evidence["reason"] = "the seeded Field Worker role is absent from the isolated copy"
                exit_code = 2
                raise StopCheck
            organization_id = next(iter(organization_ids))
            test_subject = f"directus-parity:{uuid.uuid4().hex}"
            cur.execute(
                """INSERT INTO public.operator_identity (
                       issuer, subject, display_name, enabled
                   ) VALUES (%s, %s, 'Synthetic Directus parity operator', TRUE)
                   RETURNING id::text""",
                (OPERATOR_OIDC_ISSUER, test_subject),
            )
            operator_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.operator_organization_membership (
                       operator_id, organization_id, membership_role, granted_by
                   ) VALUES (%s::uuid, %s::uuid, 'operator', 'isolated Directus parity fixture')""",
                (operator_id, organization_id),
            )
            cur.execute(
                """INSERT INTO public.operator_scope_grant (
                       operator_id, organization_id, resource, action, location_id, granted_by
                   ) VALUES (%s::uuid, %s::uuid, 'farm_activity', 'read', %s::uuid, 'isolated Directus parity fixture'),
                            (%s::uuid, %s::uuid, 'farm_activity', 'create', %s::uuid, 'isolated Directus parity fixture'),
                            (%s::uuid, %s::uuid, 'farm_activity', 'update', %s::uuid, 'isolated Directus parity fixture'),
                            (%s::uuid, %s::uuid, 'field_note', 'read', %s::uuid, 'isolated Directus parity fixture')""",
                (
                    operator_id, organization_id, locations[0],
                    operator_id, organization_id, locations[0],
                    operator_id, organization_id, locations[0],
                    operator_id, organization_id, locations[0],
                ),
            )
            cur.execute(
                """SELECT
                       public.operator_scope_grant_allows(%s::uuid, 'farm_activity', 'read', %s::uuid),
                       public.operator_scope_grant_allows(%s::uuid, 'farm_activity', 'create', %s::uuid),
                       EXISTS (
                           SELECT 1 FROM public.directus_access AS access_row
                           WHERE access_row.role = %s::uuid
                       ),
                       EXISTS (
                           SELECT 1 FROM public.directus_permissions AS permission_row
                           JOIN public.directus_access AS access_row
                             ON access_row.policy = permission_row.policy
                           WHERE access_row.role = %s::uuid
                             AND permission_row.collection = 'farm_activity'
                             AND permission_row.action = 'read'
                       ),
                       COALESCE((
                           SELECT bool_or(
                               permission_row.fields <> '*'
                               OR COALESCE(permission_row.permissions::jsonb, '{}'::jsonb) <> '{}'::jsonb
                               OR COALESCE(permission_row.validation::jsonb, '{}'::jsonb) <> '{}'::jsonb
                               OR COALESCE(permission_row.presets::jsonb, '{}'::jsonb) <> '{}'::jsonb
                           )
                             FROM public.directus_permissions AS permission_row
                             JOIN public.directus_access AS access_row
                               ON access_row.policy = permission_row.policy
                            WHERE access_row.role = %s::uuid
                              AND permission_row.collection = 'farm_activity'
                       ), FALSE)""",
                (
                    operator_id, locations[0], operator_id, locations[0],
                    FIELD_WORKER_ROLE, FIELD_WORKER_ROLE, FIELD_WORKER_ROLE,
                ),
            )
            grant_preflight = cur.fetchone()
            evidence["database_read_grant_allows"] = bool(grant_preflight[0])
            evidence["database_create_grant_allows"] = bool(grant_preflight[1])
            evidence["field_worker_role_has_policy_link"] = bool(grant_preflight[2])
            evidence["field_worker_read_permission_exists"] = bool(grant_preflight[3])
            evidence["field_worker_farm_activity_has_custom_permission_rules"] = bool(
                grant_preflight[4]
            )
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'farm_activity'
                          AND column_name = 'source_raw'
                   )"""
            )
            evidence["farm_activity_source_raw_available"] = bool(cur.fetchone()[0])
        conn.commit()

        runtime_conn = connect_directus_runtime_db()
        with runtime_conn.cursor() as cur:
            cur.execute(
                """SELECT
                       public.operator_scope_grant_allows(%s::uuid, 'farm_activity', 'read', %s::uuid),
                       (SELECT count(*) FROM public.operator_scope_grant WHERE operator_id = %s::uuid),
                       (SELECT count(*) FROM public.operator_organization_membership WHERE operator_id = %s::uuid)""",
                (operator_id, locations[0], operator_id, operator_id),
            )
            runtime_grant_preflight = cur.fetchone()
        evidence["runtime_role_read_grant_allows"] = bool(runtime_grant_preflight[0])
        evidence["runtime_role_visible_grant_count"] = int(runtime_grant_preflight[1])
        evidence["runtime_role_visible_membership_count"] = int(runtime_grant_preflight[2])

        user_password = secrets.token_urlsafe(32)
        email = f"kernel-directus-parity-{uuid.uuid4().hex}@example.com"
        status, body = api_request(
            "POST",
            "/users",
            token=admin_token,
            payload={
                "email": email,
                "password": user_password,
                "first_name": "Kernel",
                "last_name": "Parity",
                "role": FIELD_WORKER_ROLE,
                "status": "active",
                "external_identifier": test_subject,
            },
        )
        user_id = ((body or {}).get("data") or {}).get("id")
        if status not in (200, 201) or not user_id:
            evidence["result"] = "blocked"
            evidence["reason"] = "Directus admin API could not create a disposable mapped Field Worker identity"
            evidence["disposable_user_create_status"] = status
            errors = (body or {}).get("errors") or []
            evidence["disposable_user_create_error_codes"] = [
                (error.get("extensions") or {}).get("code", "unknown")
                for error in errors
                if isinstance(error, dict)
            ]
            evidence["disposable_user_create_error_fields"] = [
                (error.get("extensions") or {}).get("field")
                for error in errors
                if isinstance(error, dict)
                and (error.get("extensions") or {}).get("field")
            ]
            exit_code = 2
            raise StopCheck
        users.append(user_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT external_identifier, status, role::text "
                "FROM public.directus_users WHERE id = %s::uuid",
                (user_id,),
            )
            mapped_user = cur.fetchone()
        evidence["directus_user_operator_mapping_matches"] = bool(
            mapped_user and mapped_user[0] == test_subject and mapped_user[1] == "active"
        )
        evidence["directus_user_role_matches_field_worker"] = bool(
            mapped_user and mapped_user[2] == FIELD_WORKER_ROLE
        )
        with runtime_conn.cursor() as cur:
            cur.execute(
                "SELECT external_identifier, status, role::text "
                "FROM public.directus_users WHERE id = %s::uuid",
                (user_id,),
            )
            runtime_mapped_user = cur.fetchone()
        evidence["runtime_role_user_mapping_matches"] = bool(
            runtime_mapped_user
            and runtime_mapped_user[0] == test_subject
            and runtime_mapped_user[1] == "active"
        )
        evidence["runtime_role_user_role_matches_field_worker"] = bool(
            runtime_mapped_user and runtime_mapped_user[2] == FIELD_WORKER_ROLE
        )

        worker_tokens: list[str] = []
        # Log in by IDs using the local admin endpoint so no synthetic email is
        # stored in the evidence artifact.
        for user_id in users:
            status, body = api_request(
                "GET", f"/users/{user_id}?fields=email,role", token=admin_token
            )
            user_data = (body or {}).get("data") or {}
            email = user_data.get("email")
            evidence["directus_api_user_role_matches_field_worker"] = (
                user_data.get("role") == FIELD_WORKER_ROLE
            )
            if status != 200 or not email:
                raise RuntimeError("could not resolve a synthetic Directus identity")
            login_status, login_body = api_request(
                "POST",
                "/auth/login",
                payload={"email": email, "password": user_password},
            )
            token = ((login_body or {}).get("data") or {}).get("access_token")
            if login_status != 200 or not token:
                raise RuntimeError("synthetic Field Worker login failed")
            worker_tokens.append(token)

        self_status, self_body = api_request(
            "GET", "/users/me", token=worker_tokens[0], query={"fields": "id,role"}
        )
        self_data = (self_body or {}).get("data") or {}
        self_role = self_data.get("role")
        evidence["field_worker_self_http_status"] = self_status
        evidence["field_worker_self_role_matches"] = (
            self_role == FIELD_WORKER_ROLE
            or (isinstance(self_role, dict) and self_role.get("id") == FIELD_WORKER_ROLE)
        )

        permissions_status, permissions_body = api_request(
            "GET", "/permissions/me", token=worker_tokens[0]
        )
        effective_data = (permissions_body or {}).get("data")
        effective = (
            effective_data.get("farm_activity") or {}
            if isinstance(effective_data, dict)
            else {}
        )
        evidence["effective_permissions_http_status"] = permissions_status
        evidence["effective_permissions_data_is_object"] = isinstance(effective_data, dict)
        evidence["effective_permissions_collection_count"] = (
            len(effective_data) if isinstance(effective_data, dict) else 0
        )
        evidence["effective_permissions_collection_names"] = (
            sorted(effective_data) if isinstance(effective_data, dict) else []
        )
        evidence["field_worker_effective_collection_present"] = (
            "farm_activity" in effective_data if isinstance(effective_data, dict) else False
        )
        evidence["field_worker_effective_actions"] = sorted(
            action for action, detail in effective.items() if isinstance(detail, dict)
        )
        evidence["field_worker_effective_read_access"] = (
            (effective.get("read") or {}).get("access")
            if isinstance(effective.get("read"), dict)
            else None
        )
        evidence["field_worker_effective_create_access"] = (
            (effective.get("create") or {}).get("access")
            if isinstance(effective.get("create"), dict)
            else None
        )

        markers = [f"kernel-directus-parity-{uuid.uuid4().hex}" for _ in locations]
        location_ids = locations
        with conn.cursor() as cur:
            for location_id, marker in zip(location_ids, markers, strict=True):
                cur.execute(
                    """INSERT INTO public.farm_activity (
                           location_id, activity_type, activity_date, description,
                           status, source_system, source_id, source_raw
                       ) VALUES (
                           %s::uuid, 'kernel_directus_parity', %s, %s, 'draft',
                           NULL, NULL, %s::jsonb
                       ) RETURNING id""",
                    (
                        location_id,
                        date.today(),
                        marker,
                        json.dumps({"synthetic_secret_probe": marker}),
                    ),
                )
                row_ids.append(cur.fetchone()[0])
            for location_id, marker in zip(location_ids, markers, strict=True):
                cur.execute(
                    """INSERT INTO public.field_note (
                           location_id, note_date, note_type, title, content, status
                       ) VALUES (%s::uuid, %s, 'kernel_directus_parity', %s, %s, 'draft')
                       RETURNING id""",
                    (location_id, date.today(), marker, marker),
                )
                field_note_ids.append(cur.fetchone()[0])
        conn.commit()

        anonymous_status, _ = api_request(
            "GET", "/items/farm_activity", query={"limit": "1"}
        )
        evidence["anonymous_collection_denied"] = anonymous_status in (401, 403)

        def query_activity(
            token: str, activity_id: uuid.UUID
        ) -> tuple[int, list[dict], list[str], bool]:
            status, body = api_request(
                "GET",
                "/items/farm_activity",
                token=token,
                query={
                    "filter[id][_eq]": str(activity_id),
                    "fields": "id,location_id,description,source_raw",
                    "limit": "-1",
                },
            )
            errors = (body or {}).get("errors") or []
            error_codes = [
                (error.get("extensions") or {}).get("code", "unknown")
                for error in errors
                if isinstance(error, dict)
            ]
            hook_denied = any(
                error.get("message") == "Directus tenant access denied"
                for error in errors
                if isinstance(error, dict)
            )
            return status, (((body or {}).get("data")) or []), error_codes, hook_denied

        own_status, own_rows, own_errors, own_hook_denied = query_activity(worker_tokens[0], row_ids[0])
        cross_status, cross_rows, cross_errors, cross_hook_denied = query_activity(worker_tokens[0], row_ids[1])
        evidence["tenant_scope_testable"] = True
        evidence["own_location_read_http_status"] = own_status
        evidence["cross_location_read_http_status"] = cross_status
        evidence["own_location_read_error_codes"] = own_errors
        evidence["cross_location_read_error_codes"] = cross_errors
        evidence["own_location_read_hook_denied"] = own_hook_denied
        evidence["cross_location_read_hook_denied"] = cross_hook_denied
        evidence["own_location_read"] = own_status == 200 and len(own_rows) == 1
        evidence["cross_location_read_hidden"] = cross_status == 200 and len(cross_rows) == 0
        evidence["cross_location_row_count"] = len(cross_rows)
        own_raw = own_rows[0].get("source_raw") if own_rows else None
        evidence["source_raw_probe_visible"] = bool(
            isinstance(own_raw, dict)
            and own_raw.get("synthetic_secret_probe") == markers[0]
        )

        def query_field_note(
            token: str, note_id: uuid.UUID
        ) -> tuple[int, list[dict], list[str], bool]:
            status, body = api_request(
                "GET",
                "/items/field_note",
                token=token,
                query={
                    "filter[id][_eq]": str(note_id),
                    "fields": "id,location_id,title,content",
                    "limit": "-1",
                },
            )
            errors = (body or {}).get("errors") or []
            error_codes = [
                (error.get("extensions") or {}).get("code", "unknown")
                for error in errors
                if isinstance(error, dict)
            ]
            hook_denied = any(
                error.get("message") == "Directus tenant access denied"
                for error in errors
                if isinstance(error, dict)
            )
            return status, (((body or {}).get("data")) or []), error_codes, hook_denied

        note_own_status, note_own_rows, note_own_errors, note_own_hook_denied = (
            query_field_note(worker_tokens[0], field_note_ids[0])
        )
        note_cross_status, note_cross_rows, note_cross_errors, note_cross_hook_denied = (
            query_field_note(worker_tokens[0], field_note_ids[1])
        )
        evidence["field_note_own_read_http_status"] = note_own_status
        evidence["field_note_cross_read_http_status"] = note_cross_status
        evidence["field_note_own_read_error_codes"] = note_own_errors
        evidence["field_note_cross_read_error_codes"] = note_cross_errors
        evidence["field_note_own_read_hook_denied"] = note_own_hook_denied
        evidence["field_note_cross_read_hook_denied"] = note_cross_hook_denied
        evidence["field_note_own_location_read"] = (
            note_own_status == 200
            and len(note_own_rows) == 1
            and note_own_rows[0].get("location_id") == location_ids[0]
        )
        evidence["field_note_cross_location_read_hidden"] = (
            note_cross_status == 200 and len(note_cross_rows) == 0
        )
        evidence["field_note_cross_location_row_count"] = len(note_cross_rows)
        evidence["tenant_hook_read_runtime_pass"] = all(
            evidence.get(key) is True
            for key in (
                "field_note_own_location_read",
                "field_note_cross_location_read_hidden",
            )
        )

        patch_status, patch_body = api_request(
            "PATCH",
            f"/items/farm_activity/{row_ids[1]}",
            token=worker_tokens[0],
            payload={"description": markers[0]},
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT description FROM public.farm_activity WHERE id = %s",
                (row_ids[1],),
            )
            other_description = cur.fetchone()[0]
        evidence["cross_location_patch_http_status"] = patch_status
        evidence["cross_location_write_unchanged"] = other_description == markers[1]
        evidence["cross_location_patch_returned_data"] = bool(
            ((patch_body or {}).get("data"))
        )

        create_status, create_body = api_request(
            "POST",
            "/items/farm_activity",
            token=worker_tokens[0],
            payload={
                "location_id": location_ids[1],
                "activity_type": "kernel_directus_parity",
                "activity_date": date.today().isoformat(),
                "description": markers[0],
                "source_raw": {"synthetic_secret_probe": markers[0]},
            },
        )
        created_id = ((create_body or {}).get("data") or {}).get("id")
        if create_status in (200, 201) and created_id:
            try:
                created_uuid = uuid.UUID(str(created_id))
            except ValueError:
                created_uuid = None
            if created_uuid:
                row_ids.append(created_uuid)
        evidence["cross_location_create_denied"] = create_status in (400, 403, 404)
        evidence["cross_location_create_http_status"] = create_status
        evidence["cross_location_create_error_codes"] = [
            (error.get("extensions") or {}).get("code", "unknown")
            for error in ((create_body or {}).get("errors") or [])
            if isinstance(error, dict)
        ]

        own_create_status, own_create_body = api_request(
            "POST",
            "/items/farm_activity",
            token=worker_tokens[0],
            payload={
                "location_id": location_ids[0],
                "activity_type": "kernel_directus_parity",
                "activity_date": date.today().isoformat(),
                "description": markers[0],
                "source_raw": {"synthetic_secret_probe": markers[0]},
            },
        )
        own_created_id = ((own_create_body or {}).get("data") or {}).get("id")
        if own_create_status in (200, 201) and own_created_id:
            try:
                row_ids.append(uuid.UUID(str(own_created_id)))
            except ValueError:
                pass
        evidence["own_location_create"] = own_create_status in (200, 201) and bool(own_created_id)
        evidence["own_location_create_http_status"] = own_create_status
        evidence["own_location_create_error_codes"] = [
            (error.get("extensions") or {}).get("code", "unknown")
            for error in ((own_create_body or {}).get("errors") or [])
            if isinstance(error, dict)
        ]
        evidence["own_location_create_hook_denied"] = any(
            error.get("message") == "Directus tenant access denied"
            for error in ((own_create_body or {}).get("errors") or [])
            if isinstance(error, dict)
        )

        location_scope_pass = all(
            evidence.get(key) is True
            for key in (
                "anonymous_collection_denied",
                "own_location_read",
                "cross_location_read_hidden",
                "cross_location_write_unchanged",
                "cross_location_create_denied",
                "own_location_create",
            )
        )
        evidence["row_authorization_pass"] = location_scope_pass
        evidence["result"] = "passed" if location_scope_pass else "failed"
        exit_code = 0 if location_scope_pass else 1
    except StopCheck:
        pass
    except Exception as error:  # sanitized; never emit credentials or payloads
        evidence["result"] = "error"
        evidence["reason"] = type(error).__name__
        exit_code = 2
    finally:
        if conn is not None:
            cleanup_ok = True
            try:
                with conn.cursor() as cur:
                    if row_ids:
                        cur.execute(
                            "DELETE FROM public.farm_activity WHERE id = ANY(%s::uuid[])",
                            (row_ids,),
                        )
                    if field_note_ids:
                        cur.execute(
                            "DELETE FROM public.field_note WHERE id = ANY(%s::uuid[])",
                            (field_note_ids,),
                        )
                conn.commit()
            except Exception as error:
                conn.rollback()
                cleanup_ok = False
                evidence["row_cleanup_error_code"] = getattr(error, "pgcode", None)
            if admin_token:
                for user_id in users:
                    status, _ = api_request(
                        "DELETE", f"/users/{user_id}", token=admin_token
                    )
                    if status in (200, 204):
                        continue
                    evidence["user_cleanup_http_status"] = status
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                "DELETE FROM public.directus_users WHERE id = %s::uuid",
                                (user_id,),
                            )
                            deleted = cur.rowcount == 1
                        conn.commit()
                        cleanup_ok = cleanup_ok and deleted
                    except Exception as error:
                        conn.rollback()
                        cleanup_ok = False
                        evidence["user_cleanup_error_code"] = getattr(error, "pgcode", None)
            elif users:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM public.directus_users WHERE id = ANY(%s::uuid[])",
                            (users,),
                        )
                    conn.commit()
                except Exception as error:
                    conn.rollback()
                    cleanup_ok = False
                    evidence["user_cleanup_error_code"] = getattr(error, "pgcode", None)
            try:
                with conn.cursor() as cur:
                    if operator_id:
                        cur.execute(
                            "DELETE FROM public.operator_scope_grant WHERE operator_id = %s::uuid",
                            (operator_id,),
                        )
                        cur.execute(
                            "DELETE FROM public.operator_organization_membership WHERE operator_id = %s::uuid",
                            (operator_id,),
                        )
                        cur.execute(
                            "DELETE FROM public.operator_identity WHERE id = %s::uuid",
                            (operator_id,),
                        )
                conn.commit()
            except Exception as error:
                conn.rollback()
                cleanup_ok = False
                evidence["operator_cleanup_error_code"] = getattr(error, "pgcode", None)
            if synthetic_location_ids or synthetic_organization_id:
                try:
                    with conn.cursor() as cur:
                        if synthetic_owner_verification_ids:
                            cur.execute(
                                "DELETE FROM public.location_tenant_owner_verification WHERE id = ANY(%s::uuid[])",
                                (synthetic_owner_verification_ids,),
                            )
                        if synthetic_location_ids:
                            cur.execute(
                                "DELETE FROM public.organization_member WHERE location_id = ANY(%s::uuid[])",
                                (synthetic_location_ids,),
                            )
                            cur.execute(
                                "DELETE FROM public.location WHERE id = ANY(%s::uuid[])",
                                (synthetic_location_ids,),
                            )
                        if synthetic_organization_id:
                            cur.execute(
                                "DELETE FROM public.organization WHERE id = %s::uuid",
                                (synthetic_organization_id,),
                            )
                    conn.commit()
                except Exception as error:
                    conn.rollback()
                    cleanup_ok = False
                    evidence["synthetic_scope_cleanup_error_code"] = getattr(error, "pgcode", None)
            evidence["cleanup_complete"] = cleanup_ok
            conn.close()
    if runtime_conn is not None:
        runtime_conn.close()
    if evidence.get("cleanup_complete") is False:
        evidence["result"] = "cleanup_failed"
        exit_code = 2
    print(json.dumps(evidence, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
