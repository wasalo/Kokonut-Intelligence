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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

from starlette.requests import Request

from services.mobile.api import (
    EnrollmentCreateRequest,
    ParticipantLinkCreateRequest,
    ParticipantLinkRevokeRequest,
)

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
    operator_auth_user: str = field(repr=False)
    operator_auth_password: str = field(repr=False)
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
            "operator_auth_user": "KOKONUT_OPERATOR_AUTH_USER",
            "operator_auth_password": "KOKONUT_OPERATOR_AUTH_PASSWORD",
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
        if not _IDENTIFIER_RE.fullmatch(values["operator_auth_user"]):
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_AUTH_USER must be a lowercase PostgreSQL role name"
            )
        if (
            len(values["operator_auth_password"]) < 24
            or values["operator_auth_password"].lower().startswith(
                ("replace-with", "your_", "your-", "change_", "change-", "todo", "none", "null")
            )
        ):
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_AUTH_PASSWORD must be a generated secret of at least 24 characters"
            )
        database_secrets = {
            os.environ.get(name, "")
            for name in ("PG_PASSWORD", "POSTGRES_PASSWORD", "KOKONUT_RUNTIME_PASSWORD")
        }
        if values["operator_auth_password"] in database_secrets:
            raise OperatorAuthConfigurationError(
                "KOKONUT_OPERATOR_AUTH_PASSWORD must differ from the app and database-owner passwords"
            )
        for setting, variable in (("issuer", "KOKONUT_OPERATOR_OIDC_ISSUER"),
                                  ("redirect_uri", "KOKONUT_OPERATOR_OIDC_REDIRECT_URI")):
            parsed = urlsplit(values[setting])
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise OperatorAuthConfigurationError(f"{variable} must be an HTTPS URL")
            if parsed.fragment or (setting == "issuer" and parsed.query):
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
    session_token_hash: str = field(repr=False)


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


def _get_operator_auth_db(settings: OIDCSettings):
    """Connect with the session-only database principal, never the app role."""
    import psycopg2

    from services.common.db import PG_DB, PG_HOST, PG_PORT

    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=settings.operator_auth_user,
        password=settings.operator_auth_password,
        connect_timeout=5,
    )


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
        conn = _get_operator_auth_db(self.settings)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT session_id, operator_id, issuer, subject, display_name, email
                         FROM kokonut_security.create_operator_session(
                             %s, %s, %s, %s, %s, %s, %s
                         )""",
                    (
                        issuer,
                        subject,
                        name,
                        email,
                        _digest(session_token),
                        _digest(csrf_token),
                        expires_at,
                    ),
                )
                identity = cur.fetchone()
                if identity is None:
                    conn.rollback()
                    return None
                (
                    _session_id,
                    operator_id,
                    stable_issuer,
                    stable_subject,
                    stable_name,
                    stable_email,
                ) = identity
            conn.commit()
            principal = OperatorPrincipal(
                operator_id=str(operator_id),
                issuer=stable_issuer,
                subject=stable_subject,
                display_name=stable_name,
                email=stable_email,
            )
            return principal, session_token, csrf_token
        finally:
            conn.close()

    def authenticate_request(self, request) -> OperatorSession | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        session_token_hash = _digest(token)
        conn = _get_operator_auth_db(self.settings)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT session_id, csrf_token_hash, operator_id, issuer,
                              subject, display_name, email
                         FROM kokonut_security.authenticate_operator_session(%s)""",
                    (session_token_hash,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                session_id, csrf_hash, operator_id, issuer, subject, name, email = row
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
                session_token_hash=session_token_hash,
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

    def revoke_session(self, session_id: str) -> None:
        conn = _get_operator_auth_db(self.settings)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kokonut_security.revoke_operator_session(%s::uuid)",
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
    delphi_draft_studies_match = re.fullmatch(
        r"/operator/api/delphi/([0-9a-fA-F-]{36})/draft-studies", path
    )
    if delphi_draft_studies_match and method.upper() == "GET" and enabled:
        return {
            "resource": "delphi",
            "action": "draft",
            "public": False,
            "location_id": delphi_draft_studies_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    delphi_recommendation_draft_match = re.fullmatch(
        r"/operator/api/delphi/([0-9a-fA-F-]{36})/studies/([0-9a-fA-F-]{36})/recommendation-drafts",
        path,
    )
    if delphi_recommendation_draft_match and method.upper() == "POST" and enabled:
        return {
            "resource": "delphi",
            "action": "draft",
            "public": False,
            "location_id": delphi_recommendation_draft_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    delphi_consultation_match = re.fullmatch(
        r"/operator/api/delphi/([0-9a-fA-F-]{36})/studies", path
    )
    if delphi_consultation_match and method.upper() == "GET" and enabled:
        return {
            "resource": "delphi",
            "action": "read",
            "public": False,
            "location_id": delphi_consultation_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    delphi_recommendation_review_match = re.fullmatch(
        r"/operator/api/delphi/([0-9a-fA-F-]{36})/recommendations(?:/([0-9a-fA-F-]{36})/decision)?",
        path,
    )
    if delphi_recommendation_review_match and enabled:
        if method.upper() == "GET" and delphi_recommendation_review_match.group(2) is None:
            return {
                "resource": "delphi",
                "action": "review",
                "public": False,
                "location_id": delphi_recommendation_review_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }
        if method.upper() == "POST" and delphi_recommendation_review_match.group(2) is not None:
            return {
                "resource": "delphi",
                "action": "review",
                "public": False,
                "location_id": delphi_recommendation_review_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }

    ai_summary_review_match = re.fullmatch(
        r"/operator/api/ai-summaries/([0-9a-fA-F-]{36})/reviews(?:/([0-9a-fA-F-]{36})/decision)?",
        path,
    )
    ai_summary_draft_match = re.fullmatch(
        r"/operator/api/ai-summaries/([0-9a-fA-F-]{36})/drafts",
        path,
    )
    if ai_summary_draft_match and enabled and method.upper() == "POST":
        return {
            "resource": "ai_summary",
            "action": "draft",
            "public": False,
            "location_id": ai_summary_draft_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }
    if ai_summary_review_match and enabled:
        if method.upper() == "GET" and ai_summary_review_match.group(2) is None:
            return {
                "resource": "ai_summary",
                "action": "review",
                "public": False,
                "location_id": ai_summary_review_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }
        if method.upper() == "POST" and ai_summary_review_match.group(2) is not None:
            return {
                "resource": "ai_summary",
                "action": "review",
                "public": False,
                "location_id": ai_summary_review_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }
    credit_custody_match = re.fullmatch(
        r"/operator/api/credit-custody/([0-9a-fA-F-]{36})/summary", path
    )
    if credit_custody_match and method.upper() == "GET" and enabled:
        return {
            "resource": "carbon_credit",
            "action": "read",
            "additional_scopes": [{"resource": "credit_retirement", "action": "read"}],
            "public": False,
            "location_id": credit_custody_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    ecocredit_match = re.fullmatch(
        r"/operator/api/ecocredits/([0-9a-fA-F-]{36})/batches", path
    )
    if ecocredit_match and method.upper() == "GET" and enabled:
        return {
            "resource": "ecocredit",
            "action": "read",
            "public": False,
            "location_id": ecocredit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    true_cost_match = re.fullmatch(
        r"/operator/api/true-cost/([0-9a-fA-F-]{36})/summary", path
    )
    if true_cost_match and method.upper() == "GET" and enabled:
        return {
            "resource": "true_cost_accounting",
            "action": "read",
            "public": False,
            "location_id": true_cost_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    emergency_response_match = re.fullmatch(
        r"/operator/api/emergency-response/([0-9a-fA-F-]{36})/summary", path
    )
    if emergency_response_match and method.upper() == "GET" and enabled:
        return {
            "resource": "emergency_response",
            "action": "read",
            "public": False,
            "location_id": emergency_response_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    threatcasting_backcast_match = re.fullmatch(
        r"/operator/api/threatcasting/([0-9a-fA-F-]{36})/backcast-plans"
        r"(?:/([0-9a-fA-F-]{36}))?",
        path,
    )
    if threatcasting_backcast_match and method.upper() == "GET" and enabled:
        return {
            "resource": "threatcasting",
            "action": "read",
            "public": False,
            "location_id": threatcasting_backcast_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    strategy_plans_match = re.fullmatch(
        r"/operator/api/strategy/([0-9a-fA-F-]{36})/plans", path
    )
    if strategy_plans_match and method.upper() == "GET" and enabled:
        return {
            "resource": "strategy",
            "action": "read",
            "public": False,
            "location_id": strategy_plans_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    competitive_landscape_match = re.fullmatch(
        r"/operator/api/competitive-landscape/([0-9a-fA-F-]{36})/summaries", path
    )
    if competitive_landscape_match and method.upper() == "GET" and enabled:
        return {
            "resource": "competitive_landscape",
            "action": "read",
            "public": False,
            "location_id": competitive_landscape_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    management_summary_match = re.fullmatch(
        r"/operator/api/management/([0-9a-fA-F-]{36})/summary", path
    )
    if management_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "management_workflow",
            "action": "read",
            "public": False,
            "location_id": management_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    planning_budget_match = re.fullmatch(
        r"/operator/api/planning/([0-9a-fA-F-]{36})/budgets", path
    )
    if planning_budget_match and method.upper() == "GET" and enabled:
        return {
            "resource": "planning_budget",
            "action": "read",
            "public": False,
            "location_id": planning_budget_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    comprehensive_status_match = re.fullmatch(
        r"/operator/api/comprehensive-status/([0-9a-fA-F-]{36})", path
    )
    if comprehensive_status_match and method.upper() == "GET" and enabled:
        return {
            "resource": "comprehensive_status",
            "action": "read",
            "public": False,
            "location_id": comprehensive_status_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    business_canvas_versions_match = re.fullmatch(
        r"/operator/api/business-planning/([0-9a-fA-F-]{36})/canvases/([0-9a-fA-F-]{36})/versions",
        path,
    )
    if business_canvas_versions_match and method.upper() == "GET" and enabled:
        return {
            "resource": "business_planning",
            "action": "read",
            "public": False,
            "location_id": business_canvas_versions_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    business_canvas_block_edit_match = re.fullmatch(
        r"/operator/api/business-planning/([0-9a-fA-F-]{36})/canvases/([0-9a-fA-F-]{36})/blocks/[a-z_]+",
        path,
    )
    if business_canvas_block_edit_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "business_planning",
            "action": "update",
            "public": False,
            "location_id": business_canvas_block_edit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    business_canvas_metadata_edit_match = re.fullmatch(
        r"/operator/api/business-planning/([0-9a-fA-F-]{36})/canvases/([0-9a-fA-F-]{36})/metadata",
        path,
    )
    if business_canvas_metadata_edit_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "business_planning",
            "action": "update",
            "public": False,
            "location_id": business_canvas_metadata_edit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    business_architecture_match = re.fullmatch(
        r"/operator/api/business-architecture/([0-9a-fA-F-]{36})/summary", path
    )
    if business_architecture_match and method.upper() == "GET" and enabled:
        return {
            "resource": "business_architecture",
            "action": "read",
            "public": False,
            "location_id": business_architecture_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    business_canvas_match = re.fullmatch(
        r"/operator/api/business-planning/([0-9a-fA-F-]{36})/canvases(/from-data)?", path
    )
    if business_canvas_match and enabled:
        if method.upper() == "GET" and business_canvas_match.group(2) is None:
            return {
                "resource": "business_planning",
                "action": "read",
                "public": False,
                "location_id": business_canvas_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }
        if method.upper() == "POST":
            return {
                "resource": "business_planning",
                "action": "create",
                "public": False,
                "location_id": business_canvas_match.group(1),
                "scope_required": True,
                "operator_auth": True,
            }

    coordination_summary_match = re.fullmatch(
        r"/operator/api/coordination/([0-9a-fA-F-]{36})/summary", path
    )
    if coordination_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "coordination",
            "action": "read",
            "public": False,
            "location_id": coordination_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_summary_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/summary", path
    )
    if solution_lifecycle_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_create_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions", path
    )
    if solution_lifecycle_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gate_create_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions/([0-9a-fA-F-]{36})/gates",
        path,
    )
    if solution_lifecycle_gate_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_gate_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_create_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions/([0-9a-fA-F-]{36})/experiments",
        path,
    )
    if solution_lifecycle_experiment_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_experiment_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_submit_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if solution_lifecycle_experiment_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_experiment_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_protocol_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/protocol-review",
        path,
    )
    if solution_lifecycle_experiment_protocol_review_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_experiment_protocol_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_start_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/start",
        path,
    )
    if solution_lifecycle_experiment_start_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_experiment_start_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_observations_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/observations",
        path,
    )
    if solution_lifecycle_experiment_observations_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "collect",
            "public": False,
            "location_id": solution_lifecycle_experiment_observations_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_analysis_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/analyze",
        path,
    )
    if solution_lifecycle_experiment_analysis_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "analyze",
            "public": False,
            "location_id": solution_lifecycle_experiment_analysis_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_completion_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/complete",
        path,
    )
    if solution_lifecycle_experiment_completion_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_experiment_completion_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gates_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/gates", path
    )
    if solution_lifecycle_gates_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_gates_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gate_evaluation_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/gates/([0-9a-fA-F-]{36})/evaluations",
        path,
    )
    if solution_lifecycle_gate_evaluation_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_gate_evaluation_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gate_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/gates/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_gate_review_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_gate_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gate_approval_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/gates/([0-9a-fA-F-]{36})/approve",
        path,
    )
    if solution_lifecycle_gate_approval_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_gate_approval_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiment_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_experiment_review_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_experiment_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_gate_transition_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/gates/([0-9a-fA-F-]{36})/transition",
        path,
    )
    if solution_lifecycle_gate_transition_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_gate_transition_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_stage_transition_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions/([0-9a-fA-F-]{36})/stage-transition",
        path,
    )
    if solution_lifecycle_stage_transition_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_stage_transition_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_stage_targets_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/stage-transition-targets",
        path,
    )
    if solution_lifecycle_stage_targets_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_stage_targets_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_experiments_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/experiments", path
    )
    if solution_lifecycle_experiments_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_experiments_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding", path
    )
    if solution_lifecycle_funding_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_funding_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_targets_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/targets", path
    )
    if solution_lifecycle_funding_targets_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_funding_targets_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/review", path
    )
    if solution_lifecycle_funding_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_funding_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_review_detail_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_funding_review_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_funding_review_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_approve_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/([0-9a-fA-F-]{36})/approve",
        path,
    )
    if solution_lifecycle_funding_approve_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_funding_approve_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_tranche_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/([0-9a-fA-F-]{36})/tranches/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_funding_tranche_review_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_funding_tranche_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_tranche_approve_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/([0-9a-fA-F-]{36})/tranches/([0-9a-fA-F-]{36})/approve",
        path,
    )
    if solution_lifecycle_funding_tranche_approve_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_funding_tranche_approve_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_proposal_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions/([0-9a-fA-F-]{36})/funding",
        path,
    )
    if solution_lifecycle_funding_proposal_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_funding_proposal_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_funding_submit_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/funding/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if solution_lifecycle_funding_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_funding_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_create_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs",
        path,
    )
    if solution_lifecycle_adoption_program_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_redesigns_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/redesigns",
        path,
    )
    if solution_lifecycle_adoption_program_redesigns_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_redesigns_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_drafts_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/drafts",
        path,
    )
    if solution_lifecycle_adoption_program_drafts_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_drafts_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_submit_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if solution_lifecycle_adoption_program_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/review-queue",
        path,
    )
    if solution_lifecycle_adoption_program_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_adoption_program_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_program_revise_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/([0-9a-fA-F-]{36})/revise",
        path,
    )
    if solution_lifecycle_adoption_program_revise_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_adoption_program_revise_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_consent_policy_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/([0-9a-fA-F-]{36})/consent-policy",
        path,
    )
    if solution_lifecycle_adoption_consent_policy_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_adoption_consent_policy_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_readiness_submit_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/readiness",
        path,
    )
    if solution_lifecycle_adoption_readiness_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_adoption_readiness_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_readiness_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/readiness/review-queue",
        path,
    )
    if solution_lifecycle_adoption_readiness_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_adoption_readiness_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_readiness_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/readiness/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_adoption_readiness_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_adoption_readiness_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_configuration_create_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/configurations",
        path,
    )
    if solution_lifecycle_configuration_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_configuration_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_configuration_drafts_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/configurations/drafts",
        path,
    )
    if solution_lifecycle_configuration_drafts_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_configuration_drafts_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_configuration_submit_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/configurations/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if solution_lifecycle_configuration_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_configuration_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_configuration_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/configurations/review-queue",
        path,
    )
    if solution_lifecycle_configuration_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_configuration_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_configuration_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/configurations/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_configuration_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_configuration_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption", path
    )
    if solution_lifecycle_adoption_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_adoption_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_events_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/([0-9a-fA-F-]{36})/events",
        path,
    )
    if solution_lifecycle_adoption_events_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_adoption_events_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_adoption_event_capture_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/adoption/programs/([0-9a-fA-F-]{36})/events",
        path,
    )
    if solution_lifecycle_adoption_event_capture_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "collect",
            "public": False,
            "location_id": solution_lifecycle_adoption_event_capture_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_scale_gate_targets_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/scale-gates/assessment-targets",
        path,
    )
    if solution_lifecycle_scale_gate_targets_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_scale_gate_targets_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_scale_gate_evaluation_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/scale-gates/([0-9a-fA-F-]{36})/evaluations",
        path,
    )
    if solution_lifecycle_scale_gate_evaluation_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_scale_gate_evaluation_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_scale_gate_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/scale-gates/review",
        path,
    )
    if solution_lifecycle_scale_gate_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_scale_gate_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_scale_gate_review_detail_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/scale-gates/review/([0-9a-fA-F-]{36})",
        path,
    )
    if solution_lifecycle_scale_gate_review_detail_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_scale_gate_review_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_scale_gates_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/scale-gates", path
    )
    if solution_lifecycle_scale_gates_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_scale_gates_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replications_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications", path
    )
    if solution_lifecycle_replications_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_replications_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    if solution_lifecycle_replications_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_replications_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/review", path
    )
    if solution_lifecycle_replication_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_replication_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_completion_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/completion-review",
        path,
    )
    if (
        solution_lifecycle_replication_completion_review_queue_match
        and method.upper() == "GET"
        and enabled
    ):
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_replication_completion_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/([0-9a-fA-F-]{36})/review",
        path,
    )
    if solution_lifecycle_replication_review_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_replication_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_completion_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/([0-9a-fA-F-]{36})/completion-proposals/([0-9a-fA-F-]{36})/review",
        path,
    )
    if (
        solution_lifecycle_replication_completion_review_match
        and method.upper() in {"GET", "POST"}
        and enabled
    ):
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_replication_completion_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_start_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/([0-9a-fA-F-]{36})/start",
        path,
    )
    if solution_lifecycle_replication_start_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_replication_start_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_replication_completion_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/([0-9a-fA-F-]{36})/completion-proposals",
        path,
    )
    if solution_lifecycle_replication_completion_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "submit",
            "public": False,
            "location_id": solution_lifecycle_replication_completion_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/learning", path
    )
    if solution_lifecycle_learning_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_learning_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/learning/review",
        path,
    )
    if solution_lifecycle_learning_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_learning_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/learning/([0-9a-fA-F-]{36})/review",
        path,
    )
    if (
        solution_lifecycle_learning_review_match
        and method.upper() in {"GET", "POST"}
        and enabled
    ):
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_learning_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_application_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/learning/application",
        path,
    )
    if (
        solution_lifecycle_learning_application_queue_match
        and method.upper() == "GET"
        and enabled
    ):
        return {
            "resource": "solution_lifecycle",
            "action": "apply",
            "public": False,
            "location_id": solution_lifecycle_learning_application_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_application_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/learning/([0-9a-fA-F-]{36})/apply",
        path,
    )
    if (
        solution_lifecycle_learning_application_match
        and method.upper() == "POST"
        and enabled
    ):
        return {
            "resource": "solution_lifecycle",
            "action": "apply",
            "public": False,
            "location_id": solution_lifecycle_learning_application_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_learning_proposal_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/replications/([0-9a-fA-F-]{36})/learning",
        path,
    )
    if solution_lifecycle_learning_proposal_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_learning_proposal_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirements_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements", path
    )
    if solution_lifecycle_retirements_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_retirements_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_candidates_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirement-candidates",
        path,
    )
    if solution_lifecycle_retirement_candidates_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "read",
            "public": False,
            "location_id": solution_lifecycle_retirement_candidates_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_review_queue_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/review",
        path,
    )
    if solution_lifecycle_retirement_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_retirement_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_review_detail_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/review/([0-9a-fA-F-]{36})",
        path,
    )
    if solution_lifecycle_retirement_review_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_retirement_review_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_proposal_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/solutions/([0-9a-fA-F-]{36})/retirements",
        path,
    )
    if solution_lifecycle_retirement_proposal_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "create",
            "public": False,
            "location_id": solution_lifecycle_retirement_proposal_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_approval_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/([0-9a-fA-F-]{36})/approve",
        path,
    )
    if solution_lifecycle_retirement_approval_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_retirement_approval_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_migration_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/([0-9a-fA-F-]{36})/migration",
        path,
    )
    if solution_lifecycle_retirement_migration_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_retirement_migration_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_sunset_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/([0-9a-fA-F-]{36})/sunset",
        path,
    )
    if solution_lifecycle_retirement_sunset_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "transition",
            "public": False,
            "location_id": solution_lifecycle_retirement_sunset_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    solution_lifecycle_retirement_post_review_match = re.fullmatch(
        r"/operator/api/solution-lifecycle/([0-9a-fA-F-]{36})/retirements/([0-9a-fA-F-]{36})/post-retirement-review",
        path,
    )
    if solution_lifecycle_retirement_post_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": solution_lifecycle_retirement_post_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    sequential_evidence_summary_match = re.fullmatch(
        r"/operator/api/sequential-evidence/([0-9a-fA-F-]{36})/summary", path
    )
    if sequential_evidence_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "sequential_evidence",
            "action": "read",
            "public": False,
            "location_id": sequential_evidence_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    sequential_evidence_timeline_match = re.fullmatch(
        r"/operator/api/sequential-evidence/([0-9a-fA-F-]{36})/events", path
    )
    if sequential_evidence_timeline_match and method.upper() == "GET" and enabled:
        return {
            "resource": "sequential_evidence",
            "action": "read",
            "public": False,
            "location_id": sequential_evidence_timeline_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_summary_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/summary", path
    )
    if operating_pilot_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read",
            "public": False,
            "location_id": operating_pilot_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_demand_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/demand-signals", path
    )
    if operating_pilot_demand_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "create",
            "public": False,
            "location_id": operating_pilot_demand_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }
    if operating_pilot_demand_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read",
            "public": False,
            "location_id": operating_pilot_demand_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_demand_revision_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/demand-signals/([0-9a-fA-F-]{36})",
        path,
    )
    if operating_pilot_demand_revision_match and method.upper() == "PUT" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "edit_own",
            "public": False,
            "location_id": operating_pilot_demand_revision_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_demand_submit_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/demand-signals/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if operating_pilot_demand_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "submit_own",
            "public": False,
            "location_id": operating_pilot_demand_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_profile_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-profiles", path
    )
    if operating_pilot_capacity_profile_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "create",
            "public": False,
            "location_id": operating_pilot_capacity_profile_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_revision_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-profiles/([0-9a-fA-F-]{36})",
        path,
    )
    if operating_pilot_capacity_revision_match and method.upper() == "PUT" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "edit_own",
            "public": False,
            "location_id": operating_pilot_capacity_revision_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_submission_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-profiles/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if operating_pilot_capacity_submission_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "submit_own",
            "public": False,
            "location_id": operating_pilot_capacity_submission_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-periods", path
    )
    if operating_pilot_capacity_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read",
            "public": False,
            "location_id": operating_pilot_capacity_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_own_capacity_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/my-capacity-profiles", path
    )
    if operating_pilot_own_capacity_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read_own",
            "public": False,
            "location_id": operating_pilot_own_capacity_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_own_demand_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/my-demand-signals", path
    )
    if operating_pilot_own_demand_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read_own",
            "public": False,
            "location_id": operating_pilot_own_demand_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_review_queue_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-review-queue", path
    )
    if operating_pilot_capacity_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "review",
            "public": False,
            "location_id": operating_pilot_capacity_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_demand_review_queue_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/demand-review-queue", path
    )
    if operating_pilot_demand_review_queue_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "review",
            "public": False,
            "location_id": operating_pilot_demand_review_queue_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_demand_review_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/demand-signals/([0-9a-fA-F-]{36})/review",
        path,
    )
    if operating_pilot_demand_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "review",
            "public": False,
            "location_id": operating_pilot_demand_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_capacity_review_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/capacity-profiles/([0-9a-fA-F-]{36})/review",
        path,
    )
    if operating_pilot_capacity_review_match and method.upper() == "POST" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "review",
            "public": False,
            "location_id": operating_pilot_capacity_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_work_claims_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/work-claims", path
    )
    if operating_pilot_work_claims_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read",
            "public": False,
            "location_id": operating_pilot_work_claims_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    operating_pilot_resource_categories_match = re.fullmatch(
        r"/operator/api/operating-pilot/([0-9a-fA-F-]{36})/resource-categories", path
    )
    if operating_pilot_resource_categories_match and method.upper() == "GET" and enabled:
        return {
            "resource": "operating_pilot",
            "action": "read",
            "public": False,
            "location_id": operating_pilot_resource_categories_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_summary_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/summary", path
    )
    if governance_summary_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "read",
            "public": False,
            "location_id": governance_summary_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_roles_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/roles", path
    )
    if governance_roles_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "read",
            "public": False,
            "location_id": governance_roles_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_role_detail_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/roles/([0-9a-fA-F-]{36})",
        path,
    )
    if governance_role_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "read",
            "public": False,
            "location_id": governance_role_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_role_assignment_proposal_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/roles/([0-9a-fA-F-]{36})/assignments",
        path,
    )
    if governance_role_assignment_proposal_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_roles",
            "action": "create",
            "public": False,
            "location_id": governance_role_assignment_proposal_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_assignment_proposal_read_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/assignment-proposals",
        path,
    )
    if governance_assignment_proposal_read_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "read",
            "public": False,
            "location_id": governance_assignment_proposal_read_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    stakeholder_identity_match = re.fullmatch(
        r"/operator/api/stakeholder-identity/([0-9a-fA-F-]{36})/cases(?:/([0-9a-fA-F-]{36})/decision)?",
        path,
    )
    if stakeholder_identity_match and enabled:
        location_id, case_id = stakeholder_identity_match.groups()
        if method.upper() == "GET" and case_id is None:
            action = "review"
        elif method.upper() == "POST" and case_id is None:
            action = "create"
        elif method.upper() == "POST" and case_id is not None:
            action = "review"
        else:
            return None
        return {
            "resource": "stakeholder_identity",
            "action": action,
            "public": False,
            "location_id": location_id,
            "scope_required": True,
            "operator_auth": True,
        }

    stakeholder_identity_resolution_match = re.fullmatch(
        r"/operator/api/stakeholder-identity/([0-9a-fA-F-]{36})/resolve/([0-9a-fA-F-]{36})",
        path,
    )
    if stakeholder_identity_resolution_match and method.upper() == "GET" and enabled:
        return {
            "resource": "stakeholder_identity",
            "action": "resolve",
            "public": False,
            "location_id": stakeholder_identity_resolution_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    stakeholder_trust_match = re.fullmatch(
        r"/operator/api/stakeholder-trust/([0-9a-fA-F-]{36})/parties/([0-9a-fA-F-]{36})/identity-evidence",
        path,
    )
    if stakeholder_trust_match and method.upper() == "GET" and enabled:
        return {
            "resource": "stakeholder_trust",
            "action": "read",
            "public": False,
            "location_id": stakeholder_trust_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_assignment_review_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/assignment-review-queue",
        path,
    )
    if governance_assignment_review_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "review",
            "public": False,
            "location_id": governance_assignment_review_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_assignment_decision_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/roles/([0-9a-fA-F-]{36})/assignments/([0-9a-fA-F-]{36})/(approve|reject)",
        path,
    )
    if governance_assignment_decision_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_roles",
            "action": governance_assignment_decision_match.group(4),
            "public": False,
            "location_id": governance_assignment_decision_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_definition_create_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/(circles|roles)", path
    )
    if governance_definition_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_roles",
            "action": "create",
            "public": False,
            "location_id": governance_definition_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_circle_detail_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/circles/([0-9a-fA-F-]{36})",
        path,
    )
    if governance_circle_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_roles",
            "action": "read",
            "additional_scopes": [{"resource": "governance_roles", "action": "update"}],
            "public": False,
            "location_id": governance_circle_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_definition_update_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/(circles|roles)/([0-9a-fA-F-]{36})",
        path,
    )
    if governance_definition_update_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "governance_roles",
            "action": "update",
            "public": False,
            "location_id": governance_definition_update_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_circle_action_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/circles/([0-9a-fA-F-]{36})/(submit|reject|activate|suspend|retire)",
        path,
    )
    if governance_circle_action_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_roles",
            "action": governance_circle_action_match.group(3),
            "public": False,
            "location_id": governance_circle_action_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_role_lifecycle_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/roles/([0-9a-fA-F-]{36})/(submit|approve|reject|activate|suspend|retire)",
        path,
    )
    if governance_role_lifecycle_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_roles",
            "action": governance_role_lifecycle_match.group(3),
            "public": False,
            "location_id": governance_role_lifecycle_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tactical_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tactical-items", path
    )
    if governance_tactical_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "governance_tactical",
            "action": "read" if method.upper() == "GET" else "create",
            "public": False,
            "location_id": governance_tactical_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tactical_sessions_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tactical-sessions", path
    )
    if governance_tactical_sessions_match and method.upper() in {"GET", "POST"} and enabled:
        return {
            "resource": "governance_tactical",
            "action": "create" if method.upper() == "POST" else "read",
            "public": False,
            "location_id": governance_tactical_sessions_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tactical_content_update_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tactical-(items|sessions)/([0-9a-fA-F-]{36})",
        path,
    )
    if governance_tactical_content_update_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "governance_tactical",
            "action": "update",
            "public": False,
            "location_id": governance_tactical_content_update_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tactical_action_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tactical-items/([0-9a-fA-F-]{36})/(start|dispose|cancel)",
        path,
    )
    if governance_tactical_action_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_tactical",
            "action": governance_tactical_action_match.group(3),
            "public": False,
            "location_id": governance_tactical_action_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tension_list_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tensions", path
    )
    if governance_tension_list_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_tension",
            "action": "read",
            "public": False,
            "location_id": governance_tension_list_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tension_detail_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tensions/([0-9a-fA-F-]{36})",
        path,
    )
    if governance_tension_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "governance_tension",
            "action": "read",
            "public": False,
            "location_id": governance_tension_detail_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tension_create_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tensions", path
    )
    if governance_tension_create_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_tension",
            "action": "create",
            "public": False,
            "location_id": governance_tension_create_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    governance_tension_submit_match = re.fullmatch(
        r"/operator/api/governance/([0-9a-fA-F-]{36})/tensions/([0-9a-fA-F-]{36})/submit",
        path,
    )
    if governance_tension_submit_match and method.upper() == "POST" and enabled:
        return {
            "resource": "governance_tension",
            "action": "submit",
            "public": False,
            "location_id": governance_tension_submit_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

    attestation_match = re.fullmatch(
        r"/operator/api/attestations/([0-9a-fA-F-]{36})", path
    )
    if attestation_match and method.upper() == "GET" and enabled:
        return {
            "resource": "attestation",
            "action": "read",
            "public": False,
            "location_id": attestation_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }

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
    mobile_inventory_match = re.fullmatch(
        r"/operator/api/mobile/locations/([0-9a-fA-F-]{36})/inventory",
        path,
    )
    if mobile_inventory_match and method.upper() == "GET" and enabled:
        return {
            "resource": "mobile_device",
            "action": "read",
            "additional_scopes": [
                {"resource": "mobile_collection_review", "action": "read"}
            ],
            "public": False,
            "location_id": mobile_inventory_match.group(1),
            "scope_required": True,
            "operator_auth": True,
        }
    participant_match = re.fullmatch(
        r"/operator/api/mobile/locations/([0-9a-fA-F-]{36})/participants(?:/(revoke))?",
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
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_published_match = re.fullmatch(
        r"/operator/api/farm-activities/published(?:/([0-9a-fA-F-]{36}))?", path
    )
    if farm_activity_published_match and method.upper() == "GET" and enabled:
        activity_id = farm_activity_published_match.group(1)
        return {
            "resource": "farm_activity",
            "action": "read_published_detail" if activity_id else "read_published",
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
    farm_activity_record_published_match = re.fullmatch(
        r"/operator/api/farm-activity-records/published(?:/([0-9a-fA-F-]{36}))?",
        path,
    )
    if farm_activity_record_published_match and method.upper() == "GET" and enabled:
        activity_id = farm_activity_record_published_match.group(1)
        return {
            "resource": "farm_activity",
            "action": "read_published_detail" if activity_id else "read_published",
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_record_collection_match = re.fullmatch(
        r"/operator/api/farm-activity-records",
        path,
    )
    if farm_activity_record_collection_match and enabled:
        if method.upper() == "GET":
            action = "read"
            additional_scopes = []
        elif method.upper() == "POST":
            action = "create_draft"
            additional_scopes = [{"resource": "farm_activity", "action": "read_detail"}]
        else:
            return None
        return {
            "resource": "farm_activity",
            "action": action,
            "additional_scopes": additional_scopes,
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_record_edit_match = re.fullmatch(
        r"/operator/api/farm-activity-records/([0-9a-fA-F-]{36})/draft",
        path,
    )
    if farm_activity_record_edit_match and method.upper() == "PATCH" and enabled:
        return {
            "resource": "farm_activity",
            "action": "edit_draft",
            "additional_scopes": [{"resource": "farm_activity", "action": "read_detail"}],
            "public": False,
            "location_id": None,
            "scope_required": True,
            "operator_auth": True,
        }
    farm_activity_record_transition_match = re.fullmatch(
        r"/operator/api/farm-activity-records/([0-9a-fA-F-]{36})/(submit|verify|reject|request-rework|publish|close-exception)",
        path,
    )
    if farm_activity_record_transition_match and method.upper() == "POST" and enabled:
        _, route_action = farm_activity_record_transition_match.groups()
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
    farm_activity_record_detail_match = re.fullmatch(
        r"/operator/api/farm-activity-records/([0-9a-fA-F-]{36})",
        path,
    )
    if farm_activity_record_detail_match and method.upper() == "GET" and enabled:
        return {
            "resource": "farm_activity",
            "action": "read_detail",
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
    session_token_hash = getattr(operator_session, "session_token_hash", None)
    if not isinstance(session_token_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", session_token_hash):
        return {
            "authenticated": False,
            "caller": f"operator:{operator_session.operator.operator_id}",
            "reason": "operator_session_proof_unavailable",
            **policy,
        }
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
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse, RedirectResponse
    from starlette.concurrency import run_in_threadpool

    from services.mobile.api import (
        create_operator_enrollment,
        create_participant_link,
        revoke_operator_device,
        revoke_operator_enrollment,
        revoke_participant_link,
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

    @router.get("/operator/api/farm-activities/published")
    async def published_farm_activity_queue(
        request: Request, location_id: str, limit: int = 50
    ):
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
                grant_action="read_published",
                published_only=True,
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
                "Published farm activity queue unavailable (%s)", type(exc).__name__
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

    @router.get("/operator/api/farm-activities/published/{activity_id}")
    async def published_farm_activity_detail(
        request: Request, activity_id: str, location_id: str
    ):
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
                grant_action="read_published_detail",
                published_only=True,
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
                "Published farm activity detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Farm activity workflow service unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
            )
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Published farm activity not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            {"data": jsonable_encoder(row)},
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

    @router.post("/operator/api/mobile/locations/{location_id}/participants", status_code=201)
    async def operator_create_mobile_participant_link(
        location_id: UUID,
        request: Request,
        body: ParticipantLinkCreateRequest,
    ):
        """Create a reviewer-approved participant reference within one tenant."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        try:
            result = await create_participant_link(location_id, request, body)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result.headers["Vary"] = "Cookie"
        return result

    @router.post("/operator/api/mobile/locations/{location_id}/participants/revoke")
    async def operator_revoke_mobile_participant_link(
        location_id: UUID,
        request: Request,
        body: ParticipantLinkRevokeRequest,
    ):
        """Revoke a participant reference within one tenant."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        try:
            result = await revoke_participant_link(location_id, request, body)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result.headers["Vary"] = "Cookie"
        return result

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
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
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

    @router.get("/operator/api/mobile/locations/{location_id}/inventory")
    async def operator_mobile_inventory(
        location_id: UUID, request: Request, device_limit: int = 50
    ):
        """Read a location-scoped device inventory and collection queue summary."""
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"})
        from services.common.tenant_context import TenantContextDenied
        from services.gateway.operator_mobile_review import get_mobile_operations_inventory

        try:
            result = await run_in_threadpool(
                get_mobile_operations_inventory,
                request.state.operator_session.operator.operator_id,
                str(location_id),
                device_limit,
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
                "Mobile operations inventory unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Mobile operations inventory unavailable"},
                headers={"Retry-After": "30", "Cache-Control": "no-store"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            jsonable_encoder(result),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
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

    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes
    from services.gateway.ai_summary_review_routes import register_ai_summary_review_routes
    from services.gateway.attestation_routes import register_attestation_routes
    from services.gateway.business_architecture_routes import register_business_architecture_routes
    from services.gateway.business_planning_edit_routes import (
        register_business_planning_edit_routes,
    )
    from services.gateway.business_planning_routes import register_business_planning_routes
    from services.gateway.competitive_landscape_routes import (
        register_competitive_landscape_routes,
    )
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes
    from services.gateway.coordination_routes import register_coordination_routes
    from services.gateway.credit_custody_routes import register_credit_custody_routes
    from services.gateway.delphi_consultation_routes import register_delphi_consultation_routes
    from services.gateway.delphi_recommendation_draft_routes import (
        register_delphi_recommendation_draft_routes,
    )
    from services.gateway.delphi_recommendation_review_routes import (
        register_delphi_recommendation_review_routes,
    )
    from services.gateway.ecocredit_routes import register_ecocredit_routes
    from services.gateway.emergency_response_routes import (
        register_emergency_response_routes,
    )
    from services.gateway.farm_activity_routes import register_farm_activity_record_routes
    from services.gateway.governance_role_routes import register_governance_role_routes
    from services.gateway.management_work_routes import register_management_work_routes
    from services.gateway.operating_pilot_routes import (
        register_operating_pilot_routes,
    )
    from services.gateway.planning_budget_routes import register_planning_budget_routes
    from services.gateway.sequential_decision_routes import (
        register_sequential_decision_routes,
    )
    from services.gateway.solution_lifecycle_routes import (
        register_solution_lifecycle_routes,
    )
    from services.gateway.stakeholder_identity_resolution_routes import (
        register_stakeholder_identity_resolution_routes,
    )
    from services.gateway.stakeholder_identity_routes import register_stakeholder_identity_routes
    from services.gateway.stakeholder_trust_routes import register_stakeholder_trust_routes
    from services.gateway.strategy_routes import register_strategy_routes
    from services.gateway.threatcasting_routes import register_threatcasting_routes
    from services.gateway.true_cost_routes import register_true_cost_routes

    register_farm_activity_record_routes(router, provider, run_in_threadpool, psycopg2)
    register_emergency_response_routes(router, provider, run_in_threadpool, psycopg2)
    register_attestation_routes(router, provider, run_in_threadpool, psycopg2)
    register_credit_custody_routes(router, provider, run_in_threadpool, psycopg2)
    register_delphi_consultation_routes(router, provider, run_in_threadpool, psycopg2)
    register_delphi_recommendation_review_routes(router, provider, run_in_threadpool, psycopg2)
    register_ai_summary_draft_routes(router, provider, run_in_threadpool, psycopg2)
    register_ai_summary_review_routes(router, provider, run_in_threadpool, psycopg2)
    register_delphi_recommendation_draft_routes(router, provider, run_in_threadpool, psycopg2)
    register_ecocredit_routes(router, provider, run_in_threadpool, psycopg2)
    register_true_cost_routes(router, provider, run_in_threadpool, psycopg2)
    register_governance_role_routes(router, provider, run_in_threadpool, psycopg2)
    register_threatcasting_routes(router, provider, run_in_threadpool, psycopg2)
    register_strategy_routes(router, provider, run_in_threadpool, psycopg2)
    register_competitive_landscape_routes(router, provider, run_in_threadpool, psycopg2)
    register_management_work_routes(router, provider, run_in_threadpool, psycopg2)
    register_planning_budget_routes(router, provider, run_in_threadpool, psycopg2)
    register_business_architecture_routes(router, provider, run_in_threadpool, psycopg2)
    register_comprehensive_status_routes(router, provider, run_in_threadpool, psycopg2)
    register_business_planning_routes(router, provider, run_in_threadpool, psycopg2)
    register_business_planning_edit_routes(router, provider, run_in_threadpool, psycopg2)
    register_coordination_routes(router, provider, run_in_threadpool, psycopg2)
    register_solution_lifecycle_routes(router, provider, run_in_threadpool, psycopg2)
    register_sequential_decision_routes(router, provider, run_in_threadpool, psycopg2)
    register_operating_pilot_routes(router, provider, run_in_threadpool, psycopg2)
    register_stakeholder_identity_routes(router, provider, run_in_threadpool, psycopg2)
    register_stakeholder_trust_routes(router, provider, run_in_threadpool, psycopg2)
    register_stakeholder_identity_resolution_routes(
        router, provider, run_in_threadpool, psycopg2
    )
    return router
