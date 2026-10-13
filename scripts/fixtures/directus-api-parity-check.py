#!/usr/bin/env python3
"""Exercise Directus API location permissions on a disposable populated clone.

The runner uses two existing locations only as synthetic scopes. It never
changes organization ownership or enables tenant RLS. All inserted rows and
temporary Directus users are removed in a finally block.
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
FIELD_WORKER_ROLE = "a1000000-0000-0000-0000-000000000001"


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
    admin_token: str | None = None
    conn = None
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

        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'directus_users'
                          AND column_name = 'location_id'
                   )"""
            )
            location_column_present = bool(cur.fetchone()[0])
            evidence["directus_user_location_column"] = location_column_present
            cur.execute("SELECT id::text FROM public.location ORDER BY id LIMIT 2")
            locations = [row[0] for row in cur.fetchall()]
            evidence["synthetic_location_count_available"] = len(locations)
            if len(locations) < 2:
                evidence["result"] = "blocked"
                evidence["reason"] = "two populated locations are required for the scoped API probe"
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
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'farm_activity'
                          AND column_name = 'source_raw'
                   )"""
            )
            evidence["farm_activity_source_raw_available"] = bool(cur.fetchone()[0])

        user_passwords = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
        location_ids = locations
        for index, location_id in enumerate(location_ids):
            email = f"kernel-directus-parity-{uuid.uuid4().hex}@example.com"
            status, body = api_request(
                "POST",
                "/users",
                token=admin_token,
                payload={
                    "email": email,
                    "password": user_passwords[index],
                    "first_name": "Kernel",
                    "last_name": f"Parity {index + 1}",
                    "role": FIELD_WORKER_ROLE,
                    "status": "active",
                },
            )
            user_id = ((body or {}).get("data") or {}).get("id")
            if status not in (200, 201) or not user_id:
                evidence["result"] = "blocked"
                evidence["reason"] = "Directus admin API could not create a disposable Field Worker identity"
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
            if location_column_present:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.directus_users SET location_id = %s::uuid WHERE id = %s::uuid",
                        (location_id, user_id),
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError("synthetic Directus user location assignment did not update one row")
                conn.commit()

        worker_tokens: list[str] = []
        # Log in by IDs using the local admin endpoint so no synthetic email is
        # stored in the evidence artifact.
        for user_id, password in zip(users, user_passwords, strict=True):
            status, body = api_request(
                "GET", f"/users/{user_id}?fields=email", token=admin_token
            )
            email = (((body or {}).get("data") or {}).get("email"))
            if status != 200 or not email:
                raise RuntimeError("could not resolve a synthetic Directus identity")
            login_status, login_body = api_request(
                "POST",
                "/auth/login",
                payload={"email": email, "password": password},
            )
            token = ((login_body or {}).get("data") or {}).get("access_token")
            if login_status != 200 or not token:
                raise RuntimeError("synthetic Field Worker login failed")
            worker_tokens.append(token)

        markers = [f"kernel-directus-parity-{uuid.uuid4().hex}" for _ in locations]
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
        conn.commit()

        anonymous_status, _ = api_request(
            "GET", "/items/farm_activity", query={"limit": "1"}
        )
        evidence["anonymous_collection_denied"] = anonymous_status in (401, 403)

        def query_activity(token: str, activity_id: uuid.UUID) -> tuple[int, list[dict]]:
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
            return status, (((body or {}).get("data")) or [])

        own_status, own_rows = query_activity(worker_tokens[0], row_ids[0])
        cross_status, cross_rows = query_activity(worker_tokens[0], row_ids[1])
        evidence["tenant_scope_testable"] = location_column_present
        if not location_column_present:
            visible_rows = len(own_rows) + len(cross_rows)
            evidence["user_scoped_request_statuses"] = [own_status, cross_status]
            evidence["synthetic_rows_visible_without_user_location"] = visible_rows
            if visible_rows:
                evidence["result"] = "failed"
                evidence["reason"] = "synthetic location rows were visible without a Directus user location attribute"
                exit_code = 1
            else:
                evidence["result"] = "blocked"
                evidence["reason"] = "Directus user schema has no location_id field for the configured row filters"
                exit_code = 2
        else:
            evidence["own_location_read"] = own_status == 200 and len(own_rows) == 1
            evidence["cross_location_read_hidden"] = cross_status == 200 and len(cross_rows) == 0
            evidence["cross_location_row_count"] = len(cross_rows)
        own_raw = own_rows[0].get("source_raw") if own_rows else None
        evidence["source_raw_probe_visible"] = bool(
            isinstance(own_raw, dict)
            and own_raw.get("synthetic_secret_probe") == markers[0]
        )

        if location_column_present:
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
                    "status": "draft",
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

            location_scope_pass = all(
                evidence.get(key) is True
                for key in (
                    "anonymous_collection_denied",
                    "own_location_read",
                    "cross_location_read_hidden",
                    "cross_location_write_unchanged",
                    "cross_location_create_denied",
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
                            "DELETE FROM public.farm_activity WHERE id = ANY(%s)",
                            (row_ids,),
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
            evidence["cleanup_complete"] = cleanup_ok
            conn.close()
    if evidence.get("cleanup_complete") is False:
        evidence["result"] = "cleanup_failed"
        exit_code = 2
    print(json.dumps(evidence, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
