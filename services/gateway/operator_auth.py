"""Optional OIDC login and database-backed browser operator sessions.

The OIDC client is loaded only when explicitly enabled. Provider tokens are
used for identity verification and immediately discarded; browser sessions
are opaque random values whose hashes alone are persisted in PostgreSQL.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

from starlette.requests import Request

from services.mobile.api import EnrollmentCreateRequest

SESSION_COOKIE = "kokonut_operator_session"
CSRF_COOKIE = "kokonut_operator_csrf"
SESSION_COOKIE_PATH = "/operator"
_TOKEN_BYTES = 32
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class OperatorAuthConfigurationError(RuntimeError):
    """Raised when OIDC is enabled without a complete safe configuration."""


@dataclass(frozen=True)
class OIDCSettings:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    state_secret: str
    session_ttl_seconds: int = 1800

    @classmethod
    def from_env(cls) -> OIDCSettings | None:
        enabled = os.environ.get("KOKONUT_OPERATOR_OIDC_ENABLED", "false").strip().lower()
        if enabled not in {"true", "false"}:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_OIDC_ENABLED must be true or false"
            )
        if enabled == "false":
            return None

        required = {
            "issuer": "KOKONUT_OPERATOR_OIDC_ISSUER",
            "client_id": "KOKONUT_OPERATOR_OIDC_CLIENT_ID",
            "client_secret": "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET",
            "redirect_uri": "KOKONUT_OPERATOR_OIDC_REDIRECT_URI",
            "state_secret": "KOKONUT_OPERATOR_OIDC_STATE_SECRET",
        }
        values = {field: os.environ.get(variable, "").strip() for field, variable in required.items()}
        missing = [variable for field, variable in required.items() if not values[field]]
        if missing:
            raise OperatorAuthConfigurationError(
                "OIDC is enabled but required settings are missing: " + ", ".join(missing)
            )
        if len(values["state_secret"].encode("utf-8")) < 32:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_OIDC_STATE_SECRET must be at least 32 bytes"
            )
        for field, variable in (("issuer", "KOKONUT_OPERATOR_OIDC_ISSUER"),
                                ("redirect_uri", "KOKONUT_OPERATOR_OIDC_REDIRECT_URI")):
            parsed = urlsplit(values[field])
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise OperatorAuthConfigurationError(f"{variable} must be an HTTPS URL")
            if parsed.fragment or (field == "issuer" and parsed.query):
                raise OperatorAuthConfigurationError(f"{variable} must not include a query or fragment")
        redirect = urlsplit(values["redirect_uri"])
        if redirect.path != "/operator/auth/callback" or redirect.query:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_OIDC_REDIRECT_URI must end at /operator/auth/callback"
            )
        try:
            ttl = int(os.environ.get("KOKONUT_OPERATOR_SESSION_TTL_SECONDS", "1800"))
        except ValueError as exc:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_SESSION_TTL_SECONDS must be an integer"
            ) from exc
        if not 300 <= ttl <= 43200:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_SESSION_TTL_SECONDS must be between 300 and 43200"
            )
        return cls(**values, session_ttl_seconds=ttl)


@dataclass(frozen=True)
class OperatorPrincipal:
    operator_id: str
    issuer: str
    subject: str
    display_name: str | None
    email: str | None = None


@dataclass(frozen=True)
class OperatorSession:
    session_id: str
    csrf_token_hash: str
    operator: OperatorPrincipal


class OperatorIdentityProvider(Protocol):
    """Replaceable provider contract consumed by the Gateway."""

    def authenticate_request(self, request) -> OperatorSession | None: ...

    def csrf_valid(self, request, session: OperatorSession) -> bool: ...

    def has_scope(self, operator_id: str, resource: str, action: str, location_id: str) -> bool: ...

    def list_scopes(self, operator_id: str) -> list[dict]: ...

    def revoke_session(self, session_id: str) -> None: ...


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_db():
    # Keep importing the optional provider module from loading database config
    # or SOPS secrets until an operator actually uses a database-backed route.
    from services.common.database import get_db

    return get_db(connect_timeout=5)


def _bounded_claim(value, limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


class OIDCOperatorProvider:
    """OIDC identity adapter with explicitly provisioned location grants."""

    def __init__(self, settings: OIDCSettings):
        try:
            from authlib.integrations.starlette_client import OAuth
        except ImportError as exc:
            raise OperatorAuthConfigurationError(
                "OIDC is enabled but the optional requirements/oidc.txt dependencies are absent"
            ) from exc
        self.settings = settings
        oauth = OAuth()
        oauth.register(
            name="operator",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            server_metadata_url=(settings.issuer.rstrip("/") + "/.well-known/openid-configuration"),
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )
        self.client = oauth.create_client("operator")

    def create_session(self, claims: dict) -> tuple[OperatorPrincipal, str, str] | None:
        issuer = claims.get("iss")
        subject = claims.get("sub")
        if (
            issuer != self.settings.issuer
            or not isinstance(subject, str)
            or not subject
            or len(subject) > 255
        ):
            return None
        name = _bounded_claim(claims.get("name") or claims.get("preferred_username"))
        email = _bounded_claim(claims.get("email")) if claims.get("email_verified") is True else None
        session_token = secrets.token_urlsafe(_TOKEN_BYTES)
        csrf_token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.settings.session_ttl_seconds)
        conn = _get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, issuer, subject, display_name
                         FROM operator_identity
                        WHERE issuer = %s AND subject = %s AND enabled = TRUE""",
                    (issuer, subject),
                )
                identity = cur.fetchone()
                if identity is None:
                    conn.rollback()
                    return None
                operator_id, stable_issuer, stable_subject, existing_name = identity
                cur.execute(
                    """UPDATE operator_identity
                          SET display_name = COALESCE(%s, display_name),
                              email = COALESCE(%s, email), updated_at = NOW()
                        WHERE id = %s""",
                    (name, email, operator_id),
                )
                cur.execute(
                    """INSERT INTO operator_session
                       (operator_id, session_token_hash, csrf_token_hash, expires_at)
                       VALUES (%s, %s, %s, %s)""",
                    (operator_id, _digest(session_token), _digest(csrf_token), expires_at),
                )
            conn.commit()
            principal = OperatorPrincipal(
                operator_id=str(operator_id),
                issuer=stable_issuer,
                subject=stable_subject,
                display_name=name or existing_name,
                email=email,
            )
            return principal, session_token, csrf_token
        finally:
            conn.close()

    def authenticate_request(self, request) -> OperatorSession | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        conn = _get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT s.id, s.csrf_token_hash, o.id, o.issuer, o.subject,
                              o.display_name, o.email
                         FROM operator_session AS s
                         JOIN operator_identity AS o ON o.id = s.operator_id
                        WHERE s.session_token_hash = %s
                          AND s.revoked_at IS NULL AND s.expires_at > NOW()
                          AND o.enabled = TRUE""",
                    (_digest(token),),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                session_id, csrf_hash, operator_id, issuer, subject, name, email = row
                cur.execute(
                    "UPDATE operator_session SET last_seen_at = NOW() WHERE id = %s",
                    (session_id,),
                )
            conn.commit()
            principal = OperatorPrincipal(
                operator_id=str(operator_id),
                issuer=issuer,
                subject=subject,
                display_name=name,
                email=email,
            )
            return OperatorSession(
                session_id=str(session_id),
                csrf_token_hash=csrf_hash.strip(),
                operator=principal,
            )
        finally:
            conn.close()

    @staticmethod
    def csrf_valid(request, session: OperatorSession) -> bool:
        header = request.headers.get("x-csrf-token", "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not header or not cookie or not hmac.compare_digest(header, cookie):
            return False
        return hmac.compare_digest(_digest(header), session.csrf_token_hash)

    @staticmethod
    def has_scope(operator_id: str, resource: str, action: str, location_id: str) -> bool:
        if not all(_IDENTIFIER_RE.fullmatch(value) for value in (resource, action)):
            return False
        try:
            location_id = str(UUID(location_id))
            operator_id = str(UUID(operator_id))
        except ValueError:
            return False
        conn = _get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT operator_scope_grant_allows(
                           %s::uuid, %s, %s, %s::uuid
                       )""",
                    (operator_id, resource, action, location_id),
                )
                return bool(cur.fetchone()[0])
        finally:
            conn.close()

    @staticmethod
    def list_scopes(operator_id: str) -> list[dict]:
        try:
            operator_id = str(UUID(operator_id))
        except ValueError:
            return []
        conn = _get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute("SET LOCAL lock_timeout = '2s'")
                cur.execute(
                    """SELECT resource, action, location_id
                         FROM operator_scope_grant
                        WHERE operator_id = %s AND revoked_at IS NULL
                          AND operator_scope_grant_allows(
                              operator_id, resource, action, location_id
                          )
                        ORDER BY resource, action, location_id""",
                    (operator_id,),
                )
                return [
                    {"resource": row[0], "action": row[1], "location_id": str(row[2])}
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()

    @staticmethod
    def revoke_session(session_id: str) -> None:
        conn = _get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE operator_session SET revoked_at = NOW()
                        WHERE id = %s AND revoked_at IS NULL""",
                    (session_id,),
                )
            conn.commit()
        finally:
            conn.close()


def create_provider() -> OIDCOperatorProvider | None:
    settings = OIDCSettings.from_env()
    return OIDCOperatorProvider(settings) if settings is not None else None


def auth_route_policy(method: str, path: str, *, enabled: bool) -> dict | None:
    """Return middleware policy only for the small, explicit OIDC endpoint set."""
    mobile_enrollment_match = re.fullmatch(
        r"/operator/api/mobile/locations/([0-9a-fA-F-]{36})/enrollments(?:/([0-9a-fA-F-]{36}))?",
        path,
    )
    if mobile_enrollment_match and enabled:
        location_id, enrollment_id = mobile_enrollment_match.groups()
        if method.upper() == "POST" and enrollment_id is None:
            action = "enroll"
        elif method.upper() == "DELETE" and enrollment_id is not None:
            action = "revoke"
        else:
            return None
        return {
            "resource": "mobile_device",
            "action": action,
            "public": False,
            "location_id": location_id,
            "scope_required": True,
            "operator_auth": True,
        }
    mobile_device_match = re.fullmatch(
        r"/operator/api/mobile/locations/([0-9a-fA-F-]{36})/devices/([^/]+)/revoke",
        path,
    )
    if mobile_device_match and method.upper() == "POST" and enabled:
        return {
            "resource": "mobile_device",
            "action": "revoke",
            "public": False,
            "location_id": mobile_device_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }
    participant_match = re.fullmatch(
        r"/api/mobile/locations/([0-9a-fA-F-]{36})/participants(?:/(revoke))?",
        path,
    )
    if participant_match and method.upper() == "POST" and enabled:
        return {
            "resource": "mobile_participant",
            "action": "revoke" if participant_match.group(2) else "create",
            "public": False,
            "location_id": participant_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }
    mobile_disposition_inventory_match = re.fullmatch(
        r"/operator/api/mobile-collection-review-queue/([0-9a-fA-F-]{36})/disposition-inventory",
        path,
    )
    if mobile_disposition_inventory_match and method.upper() == "GET" and enabled:
        return {
            "resource": "mobile_collection_retention",
            "action": "inventory",
            "additional_scopes": [
                {"resource": "mobile_collection_review", "action": "read"}
            ],
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    mobile_review_match = re.fullmatch(
        r"/operator/api/mobile-collection-review-queue(?:/([0-9a-fA-F-]{36})(?:/(events))?)?",
        path,
    )
    if mobile_review_match and enabled:
        collection_id, event_suffix = mobile_review_match.groups()
        if method.upper() == "GET" and collection_id is None:
            action = "read"
        elif method.upper() == "GET" and collection_id is not None and event_suffix is None:
            action = "read_detail"
        elif method.upper() == "POST" and collection_id is not None and event_suffix == "events":
            action = "review"
        else:
            return None
        return {
            "resource": "mobile_collection_review",
            "action": action,
            **(
                {"additional_scopes": [{"resource": "mobile_collection_review", "action": "read_detail"}]}
                if action == "review"
                else {}
            ),
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_intake_match = re.fullmatch(
        r"/operator/api/farm-activity-intake-queue(?:/([0-9a-fA-F-]{36})(?:/(draft))?)?",
        path,
    )
    if farm_activity_intake_match and enabled:
        collection_id, suffix = farm_activity_intake_match.groups()
        if method.upper() == "GET" and collection_id is None:
            action = "read"
        elif method.upper() == "GET" and collection_id is not None and suffix is None:
            action = "read_detail"
        elif method.upper() == "POST" and collection_id is not None and suffix == "draft":
            action = "create_draft"
        else:
            return None
        return {
            "resource": "farm_activity",
            "action": action,
            **(
                {
                    "additional_scopes": [
                        {"resource": "mobile_collection_review", "action": "read_detail"}
                    ]
                }
                if action == "read_detail"
                else {
                    "additional_scopes": [
                        {"resource": "farm_activity", "action": "read_detail"},
                        {"resource": "mobile_collection_review", "action": "read_detail"},
                    ]
                }
                if action == "create_draft"
                else {}
            ),
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_read_match = re.fullmatch(
        r"/operator/api/farm-activities(?:/([0-9a-fA-F-]{36}))?", path
    )
    if farm_activity_read_match and enabled:
        activity_id = farm_activity_read_match.group(1)
        if method.upper() != "GET":
            return None
        action = "read_detail" if activity_id else "read"
        return {
            "resource": "farm_activity",
            "action": action,
            **(
                {"additional_scopes": [{"resource": "mobile_collection_review", "action": "read_detail"}]}
                if activity_id
                else {}
            ),
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_edit_match = re.fullmatch(
        r"/operator/api/farm-activities/([0-9a-fA-F-]{36})/draft", path
    )
    if farm_activity_edit_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "farm_activity",
            "action": "edit_draft",
            "additional_scopes": [
                {"resource": "farm_activity", "action": "read_detail"},
                {"resource": "mobile_collection_review", "action": "read_detail"},
            ],
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_transition_match = re.fullmatch(
        r"/operator/api/farm-activities/([0-9a-fA-F-]{36})/(submit|verify|reject|request-rework|publish|close-exception)",
        path,
    )
    if farm_activity_transition_match and method.upper() == "POST" and enabled:
        _, route_action = farm_activity_transition_match.groups()
        action = {
            "submit": "submit",
            "verify": "verify",
            "reject": "reject",
            "request-rework": "rework",
            "publish": "publish",
            "close-exception": "close_exception",
        }[route_action]
        return {
            "resource": "farm_activity",
            "action": action,
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    routes = {
        ("GET", "/operator/"): ("console", True, False),
        ("GET", "/operator/auth/login"): ("login", True, False),
        ("GET", "/operator/auth/callback"): ("callback", True, False),
        ("GET", "/operator/auth/session"): ("read", False, False),
        ("POST", "/operator/auth/logout"): ("logout", False, False),
        ("GET", "/operator/api/report-review-queue"): ("read", False, True),
    }
    item = routes.get((method.upper(), path))
    if item is None and method.upper() == "GET" and re.fullmatch(
        r"/operator/api/report-review-queue/[0-9a-fA-F-]{36}", path
    ):
        item = ("read", False, True)
    if item is None:
        return None
    action, public, scope_required = item
    return {
        "resource": "report_snapshot_review" if scope_required else "operator_auth",
        "action": action,
        "public": public or not enabled,
        "location_id": None,
        "scope_required": scope_required,
        "operator_auth": True,
    }


def authorize_auth_request(
    request,
    provider: OIDCOperatorProvider | None,
    policy: dict,
    *,
    location_id: str | None = None,
) -> dict:
    if provider is None:
        return {
            "authenticated": bool(policy["public"]),
            "caller": "oidc-disabled",
            "reason": "operator_identity_disabled",
            **policy,
        }
    if policy["public"]:
        return {"authenticated": True, "caller": "anonymous", **policy}
    operator_session = provider.authenticate_request(request)
    if operator_session is None:
        return {"authenticated": False, "reason": "operator_session_required", **policy}
    request.state.operator_session = operator_session
    scope_checked = False
    if policy.get("scope_required"):
        try:
            normalized_location_id = str(UUID(location_id or ""))
        except ValueError:
            return {
                "authenticated": False,
                "caller": f"operator:{operator_session.operator.operator_id}",
                "reason": "operator_scope_denied",
                "scope_checked": False,
                **policy,
            }
        scope_checked = True
        required_scopes = [
            (policy["resource"], policy["action"]),
            *[
                (scope["resource"], scope["action"])
                for scope in policy.get("additional_scopes", ())
            ],
        ]
        if any(
            not provider.has_scope(
                operator_session.operator.operator_id,
                resource,
                action,
                normalized_location_id,
            )
            for resource, action in required_scopes
        ):
            return {
                "authenticated": False,
                "caller": f"operator:{operator_session.operator.operator_id}",
                "reason": "operator_scope_denied",
                "scope_checked": True,
                **policy,
            }
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and not provider.csrf_valid(
        request, operator_session
    ):
        return {
            "authenticated": False,
            "caller": f"operator:{operator_session.operator.operator_id}",
            "reason": "csrf_validation_failed",
            "scope_checked": scope_checked,
            **policy,
        }
    return {
        "authenticated": True,
        "caller": f"operator:{operator_session.operator.operator_id}",
        "scope_checked": scope_checked,
        **policy,
    }


def create_auth_router(provider: OIDCOperatorProvider | None):
    from collections.abc import Mapping

    import psycopg2
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse, RedirectResponse
    from starlette.concurrency import run_in_threadpool

    from services.mobile.api import (
        create_operator_enrollment,
        revoke_operator_device,
        revoke_operator_enrollment,
    )

    router = APIRouter()

    @router.get("/operator/")
    async def operator_console():
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from pathlib import Path

        from fastapi.responses import FileResponse

        console_file = Path(__file__).resolve().parents[2] / "apps/operator-console/index.html"
        return FileResponse(
            console_file,
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/operator/auth/login")
    async def login(request: Request):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        request.session.clear()
        return await provider.client.authorize_redirect(
            request, redirect_uri=provider.settings.redirect_uri
        )

    @router.get("/operator/auth/callback")
    async def callback(request: Request):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        try:
            token = await provider.client.authorize_access_token(request)
            claims = token.get("userinfo")
            if not isinstance(claims, Mapping):
                request.session.clear()
                return JSONResponse(status_code=401, content={"error": "OIDC identity was not verified"})
            created = provider.create_session(dict(claims))
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_auth").warning(
                "OIDC session persistence unavailable (%s)", type(exc).__name__
            )
            request.session.clear()
            return JSONResponse(
                status_code=503,
                content={"error": "Operator session service unavailable"},
                headers={"Retry-After": "30"},
            )
        except Exception as exc:
            # Do not expose provider diagnostics, callback parameters, or tokens.
            from services.common.logging import get_logger

            get_logger("gateway.operator_auth").warning(
                "OIDC callback failed (%s)", type(exc).__name__
            )
            request.session.clear()
            return JSONResponse(status_code=401, content={"error": "OIDC login failed"})
        request.session.clear()
        if created is None:
            return JSONResponse(status_code=403, content={"error": "Operator identity is not provisioned"})
        _, session_token, csrf_token = created
        request.state.operator_audit_caller = f"operator:{created[0].operator_id}"
        response = RedirectResponse(url="/operator/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            max_age=provider.settings.session_ttl_seconds,
            httponly=True,
            secure=True,
            samesite="lax",
            path=SESSION_COOKIE_PATH,
        )
        response.set_cookie(
            CSRF_COOKIE,
            csrf_token,
            max_age=provider.settings.session_ttl_seconds,
            httponly=False,
            secure=True,
            samesite="strict",
            path=SESSION_COOKIE_PATH,
        )
        return response

    @router.get("/operator/auth/session")
    async def current_session(request: Request):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from dataclasses import asdict

        session = request.state.operator_session
        try:
            scopes = await run_in_threadpool(provider.list_scopes, session.operator.operator_id)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_auth").warning(
                "Operator grant list unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operator session service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        return JSONResponse(
            {
                "operator": asdict(session.operator),
                "scopes": scopes,
            },
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/report-review-queue")
    async def report_review_queue(request: Request, location_id: str, limit: int = 50):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_review import list_submitted_reports

        try:
            rows = await run_in_threadpool(
                list_submitted_reports,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_review").warning(
                "Report review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Report review service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(rows), "location_id": str(UUID(location_id))},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/report-review-queue/{report_id}")
    async def submitted_report_detail(request: Request, report_id: str, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_review import (
            ReportPayloadTooLarge,
            get_submitted_report,
        )

        try:
            row = await run_in_threadpool(
                get_submitted_report,
                request.state.operator_session.operator.operator_id,
                report_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ReportPayloadTooLarge:
            return JSONResponse(
                status_code=413,
                content={"error": "Report exceeds the console read limit"},
                headers={"Cache-Control": "no-store"},
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_review").warning(
                "Submitted report unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Report review service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        if row is None:
            return JSONResponse(status_code=404, content={"error": "Submitted report not found"})
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/mobile-collection-review-queue")
    async def mobile_collection_review_queue(request: Request, location_id: str, limit: int = 50):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_mobile_review import list_mobile_collections

        try:
            rows = await run_in_threadpool(
                list_mobile_collections,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_mobile_review").warning(
                "Mobile collection review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Mobile collection review service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(rows), "location_id": str(UUID(location_id))},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/mobile-collection-review-queue/{collection_id}")
    async def mobile_collection_review_detail(
        request: Request, collection_id: str, location_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_mobile_review import (
            MobileCollectionPayloadTooLarge,
            get_mobile_collection,
        )

        try:
            row = await run_in_threadpool(
                get_mobile_collection,
                request.state.operator_session.operator.operator_id,
                collection_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except MobileCollectionPayloadTooLarge:
            return JSONResponse(
                status_code=413,
                content={"error": "Collection exceeds the console read limit"},
                headers={"Cache-Control": "no-store"},
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_mobile_review").warning(
                "Mobile collection unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Mobile collection review service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        if row is None:
            return JSONResponse(status_code=404, content={"error": "Mobile collection not found"})
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/mobile-collection-review-queue/{collection_id}/disposition-inventory"
    )
    async def mobile_collection_disposition_inventory(
        request: Request, collection_id: str, location_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store"},
            )
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_mobile_review import (
            get_mobile_collection_disposition_inventory,
        )

        try:
            row = await run_in_threadpool(
                get_mobile_collection_disposition_inventory,
                request.state.operator_session.operator.operator_id,
                collection_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_mobile_review").warning(
                "Mobile disposition inventory unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Mobile disposition inventory unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Disposition inventory not found or not authorized"},
                headers={"Cache-Control": "no-store"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post(
        "/operator/api/mobile-collection-review-queue/{collection_id}/events",
        status_code=201,
    )
    async def mobile_collection_review_event(
        request: Request,
        collection_id: str,
        location_id: str,
        body: dict,
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_mobile_review import record_mobile_review_event

        try:
            event = await run_in_threadpool(
                record_mobile_review_event,
                request.state.operator_session.operator.operator_id,
                collection_id,
                location_id,
                body,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operator_mobile_review").warning(
                "Mobile collection review event unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Mobile collection review service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        if event is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Reviewable mobile collection not found"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=201,
            content={"data": jsonable_encoder(event)},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activity-intake-queue")
    async def farm_activity_intake_queue(request: Request, location_id: str, limit: int = 50):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_workflow import list_farm_activity_intake

        try:
            rows = await run_in_threadpool(
                list_farm_activity_intake,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity intake queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity intake service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(rows), "location_id": str(UUID(location_id))},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activity-intake-queue/{collection_id}")
    async def farm_activity_intake_detail(
        request: Request, collection_id: str, location_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_workflow import (
            FarmActivityPayloadTooLarge,
            get_farm_activity_intake,
        )

        try:
            row = await run_in_threadpool(
                get_farm_activity_intake,
                request.state.operator_session.operator.operator_id,
                collection_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityPayloadTooLarge:
            return JSONResponse(
                status_code=413,
                content={"error": "Farm activity intake exceeds the review limit"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity intake detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity intake service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Eligible farm activity not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post(
        "/operator/api/farm-activity-intake-queue/{collection_id}/draft",
        status_code=201,
    )
    async def promote_farm_activity_draft(
        request: Request, collection_id: str, location_id: str, body: dict
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.gateway.farm_activity_workflow import (
            FarmActivityIntakeInvalid,
            create_farm_activity_draft,
        )

        if set(body) != {"content_reviewed"} or body.get("content_reviewed") is not True:
            return JSONResponse(
                status_code=422,
                content={"error": "Explicit content review is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from services.common.tenant_context import TenantContextDenied
        try:
            row = await run_in_threadpool(
                create_farm_activity_draft,
                request.state.operator_session.operator.operator_id,
                collection_id,
                location_id,
                content_reviewed=True,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityIntakeInvalid as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except RuntimeError as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity source conflict (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=409,
                content={"error": "Farm activity source conflict"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity draft creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity workflow service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Eligible farm activity not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=201 if row["created"] else 200,
            content={"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post("/operator/api/farm-activities/{activity_id}/{action}")
    async def transition_farm_activity_route(
        request: Request,
        activity_id: str,
        action: str,
        location_id: str,
        body: dict,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if set(body) - {"reason"} or ("reason" in body and body["reason"] is not None and not isinstance(body["reason"], str)):
            return JSONResponse(
                status_code=422,
                content={"error": "Transition body accepts only an optional text reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_lifecycle import (
            FarmActivityTransitionConflict,
            FarmActivityTransitionInvalid,
            transition_farm_activity,
        )

        try:
            result = await run_in_threadpool(
                transition_farm_activity,
                request.state.operator_session.operator.operator_id,
                activity_id,
                location_id,
                action,
                body.get("reason"),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityTransitionInvalid as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityTransitionConflict as exc:
            return JSONResponse(
                status_code=409,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            if exc.pgcode == "P0001":
                get_logger("gateway.farm_activity").info(
                    "Farm activity lifecycle decision rejected by database guard"
                )
                return JSONResponse(
                    status_code=409,
                    content={"error": "Farm activity lifecycle decision is not permitted"},
                    headers={"Cache-Control": "no-store", "Vary": "Cookie"},
                )
            get_logger("gateway.farm_activity").warning(
                "Farm activity lifecycle service unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity lifecycle service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity not found or transition grant unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activities")
    async def farm_activity_queue(request: Request, location_id: str, limit: int = 50):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_lifecycle import list_farm_activities

        try:
            rows = await run_in_threadpool(
                list_farm_activities,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity workflow service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(rows), "location_id": str(UUID(location_id))},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activities/{activity_id}")
    async def farm_activity_detail(request: Request, activity_id: str, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_lifecycle import get_farm_activity

        try:
            row = await run_in_threadpool(
                get_farm_activity,
                request.state.operator_session.operator.operator_id,
                activity_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.farm_activity").warning(
                "Farm activity detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity workflow service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.patch("/operator/api/farm-activities/{activity_id}/draft")
    async def edit_farm_activity_draft_route(
        request: Request, activity_id: str, location_id: str, body: dict
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if set(body) != {"content", "reason"} or not isinstance(body.get("content"), dict):
            return JSONResponse(
                status_code=422,
                content={"error": "Draft edit body requires content and a correction reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.farm_activity_lifecycle import (
            FarmActivityDraftEditConflict,
            FarmActivityDraftEditInvalid,
            edit_farm_activity_draft,
        )

        try:
            result = await run_in_threadpool(
                edit_farm_activity_draft,
                request.state.operator_session.operator.operator_id,
                activity_id,
                location_id,
                body["content"],
                body["reason"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityDraftEditInvalid as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityDraftEditConflict as exc:
            return JSONResponse(
                status_code=409,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            if exc.pgcode == "P0001":
                get_logger("gateway.farm_activity").info(
                    "Farm activity draft edit rejected by database guard"
                )
                return JSONResponse(
                    status_code=409,
                    content={"error": "Farm activity draft edit is not permitted"},
                    headers={"Cache-Control": "no-store", "Vary": "Cookie"},
                )
            get_logger("gateway.farm_activity").warning(
                "Farm activity draft edit unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity workflow service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity not found or draft-edit grants unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post("/operator/api/mobile/locations/{location_id}/enrollments", status_code=201)
    async def operator_create_mobile_enrollment(
        location_id: UUID,
        request: Request,
        body: EnrollmentCreateRequest,
    ):
        """Issue a one-time collector code to an authorized OIDC operator."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied

        try:
            result = await create_operator_enrollment(
                location_id,
                request,
                body,
                operator_id=request.state.operator_session.operator.operator_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            status_code=201,
            content=result,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.delete(
        "/operator/api/mobile/locations/{location_id}/enrollments/{enrollment_id}"
    )
    async def operator_revoke_mobile_enrollment(
        location_id: UUID, enrollment_id: UUID, request: Request
    ):
        """Revoke an unused collector code within an authorized location."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied

        try:
            result = await revoke_operator_enrollment(
                location_id,
                enrollment_id,
                operator_id=request.state.operator_session.operator.operator_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            content=result,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.post(
        "/operator/api/mobile/locations/{location_id}/devices/{device_id}/revoke"
    )
    async def operator_revoke_mobile_device(
        location_id: UUID, device_id: str, request: Request
    ):
        """Revoke an active collector device within an authorized location."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied

        try:
            result = await revoke_operator_device(
                location_id,
                device_id,
                operator_id=request.state.operator_session.operator.operator_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            content=result,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.post("/operator/auth/logout")
    async def logout(request: Request):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        provider.revoke_session(request.state.operator_session.session_id)
        response = JSONResponse(status_code=200, content={"status": "signed_out"})
        response.delete_cookie(SESSION_COOKIE, path=SESSION_COOKIE_PATH, secure=True, httponly=True,
                               samesite="lax")
        response.delete_cookie(CSRF_COOKIE, path=SESSION_COOKIE_PATH, secure=True, httponly=False,
                               samesite="strict")
        return response

    return router
