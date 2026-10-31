"""Global, read-only Baal Gateway projection and authorization checks."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.governance import (  # noqa: E402
    EXPECTED_GNOSIS_CHAIN_ID,
    GovernanceProposalNotFound,
    GovernanceReadUnavailable,
    read_baal_config,
    read_baal_member,
    read_baal_proposal,
    read_baal_proposals,
)
from services.gateway.router import get_route_policy  # noqa: E402
from services.governance.base import GovernanceConfig, ProposalLifecycle, ProposalState  # noqa: E402


class _Client:
    key = "moloch_v3_baal"
    name = "Kokonut DAO (Moloch v3 / Baal)"
    chain = "gnosis"

    def chain_id(self):
        return EXPECTED_GNOSIS_CHAIN_ID

    def config(self):
        return GovernanceConfig(
            voting_period=10,
            grace_period=20,
            proposal_offering=3,
            quorum_percent=4,
            sponsor_threshold=5,
            min_retention_percent=6,
            raw={
                "baal_version": "1.2.3",
                "total_shares": 1000,
                "total_loot": 25,
                "proposal_count": 2,
                "shares_token": "0x" + "1" * 40,
                "loot_token": "0x" + "2" * 40,
                "avatar": "0x" + "3" * 40,
                "unreviewed_secret": "must not be exposed",
            },
        )

    def proposals(self):
        return [self.proposal("1"), self.proposal("2")]

    def proposal(self, proposal_id):
        return ProposalState(
            proposal_id=proposal_id,
            lifecycle=ProposalLifecycle.VOTING,
            title="Ignored object title",
            details="A" * 5000,
            sponsor="0x" + "4" * 40,
            yes_votes=7,
            no_votes=2,
            voting_starts=100,
            voting_ends=200,
            raw={
                "title": "Public budget proposal",
                "description": "unbounded description is not selected",
                "content_uri": "https://private.example/secret",
                "votes": ["private event details"],
            },
        )

    def member(self, wallet):
        return SimpleNamespace(wallet=wallet.lower(), shares=12, loot=3, delegate=None, raw={"x": 1})


def _factory():
    return _Client()


def test_config_projection_uses_only_allowlisted_fields():
    result = read_baal_config(client_factory=_factory)

    assert result["chain_id"] == 100
    assert result["config"]["total_shares"] == "1000"
    assert result["config"]["baal_version"] == "1.2.3"
    assert "unreviewed_secret" not in repr(result)


def test_incomplete_config_fails_closed_instead_of_returning_fake_zero():
    client = _Client()
    config = client.config()
    config.voting_period = None
    client.config = lambda: config

    with pytest.raises(GovernanceReadUnavailable):
        read_baal_config(client_factory=lambda: client)


def test_wrong_chain_fails_closed_before_data_methods():
    client = _Client()
    client.chain_id = lambda: 1
    client.config = lambda: pytest.fail("wrong-chain config must not be read")

    with pytest.raises(GovernanceReadUnavailable):
        read_baal_config(client_factory=lambda: client)


@pytest.mark.parametrize("limit", [0, 101, True, "5"])
def test_invalid_proposal_limit_fails_before_client_creation(limit):
    created = False

    def factory():
        nonlocal created
        created = True
        return _Client()

    with pytest.raises(ValueError, match="limit must be between"):
        read_baal_proposals(limit, client_factory=factory)
    assert not created


def test_proposal_projection_is_bounded_and_excludes_raw_provider_fields():
    result = read_baal_proposals(1, client_factory=_factory)

    assert result["total_count"] == 2
    assert result["proposals"][0]["proposal_id"] == "2"
    assert result["proposals"][0]["title"] == "Public budget proposal"
    assert len(result["proposals"][0]["details"]) == 4000
    assert result["proposals"][0]["yes_votes"] == "7"
    assert result["proposals"][0]["no_votes"] == "2"
    serialized = repr(result)
    assert "content_uri" not in serialized
    assert "private.example" not in serialized
    assert "sponsor" not in serialized
    assert "private event details" not in serialized


def test_onchain_description_fallback_keeps_the_existing_projection_bound():
    class OnchainDescription(_Client):
        def proposal(self, proposal_id):
            proposal = super().proposal(proposal_id)
            proposal.details = None
            proposal.raw["description"] = "B" * 5000
            return proposal

    result = read_baal_proposal("1", client_factory=OnchainDescription)

    assert len(result["proposal"]["details"]) == 4000
    assert result["proposal"]["details"] == "B" * 4000


def test_member_quantities_are_exact_decimal_strings():
    result = read_baal_member("0x1111111111111111111111111111111111111111", client_factory=_factory)

    assert result["member"]["shares"] == "12"
    assert result["member"]["loot"] == "3"


def test_single_proposal_validates_id_and_maps_missing_to_not_found():
    with pytest.raises(ValueError, match="decimal integer"):
        read_baal_proposal("١", client_factory=_factory)

    class Missing(_Client):
        def proposal(self, _proposal_id):
            raise ValueError("untrusted provider detail")

    with pytest.raises(GovernanceProposalNotFound):
        read_baal_proposal("999", client_factory=Missing)


def test_member_lookup_validates_address_before_client_creation():
    created = False

    def factory():
        nonlocal created
        created = True
        return _Client()

    with pytest.raises(ValueError, match="20-byte hexadecimal"):
        read_baal_member("not-an-address", client_factory=factory)
    assert not created


@pytest.fixture(autouse=True)
def isolated_gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD", "0")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "false")
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")


def test_global_governance_routes_require_explicit_api_key_scope(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_config",
        lambda: read_baal_config(client_factory=_factory),
    )

    with TestClient(create_app()) as client:
        denied = client.get("/api/v1/governance/baal/config")
        allowed = client.get(
            "/api/v1/governance/baal/config",
            headers={"x-api-key": "governance-key"},
        )

    assert denied.status_code == 401
    assert denied.json() == {
        "error": "Unauthorized",
        "reason": "credentials_required",
    }
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store"
    assert allowed.json() == {"data": read_baal_config(client_factory=_factory)}


def test_global_governance_route_uses_global_capability_scope(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(
        "services.gateway.governance.read_baal_config",
        lambda: read_baal_config(client_factory=_factory),
    )
    with patch(
        "services.security.capabilities.CapabilityManager.verify",
        return_value={"holder": "governance-reader", "token_id": "synthetic"},
    ) as verify:
        with TestClient(create_app()) as client:
            response = client.get(
                "/api/v1/governance/baal/config",
                headers={"x-capability-token": "synthetic-token"},
            )

    assert response.status_code == 200
    assert response.json()["data"]["chain_id"] == EXPECTED_GNOSIS_CHAIN_ID
    verify.assert_called_once_with(
        "synthetic-token",
        resource="governance",
        action="read",
        location_id=None,
    )


def test_location_scoped_key_cannot_authorize_global_governance_route(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "location-key:location-reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        "location-reader:governance:read:11111111-1111-4111-8111-111111111111",
    )

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/governance/baal/config",
            headers={"x-api-key": "location-key"},
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Unauthorized",
        "reason": "api_key_scope_denied",
    }


def test_invalid_governance_identifiers_reach_validation_with_global_scope(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")

    with TestClient(create_app()) as client:
        bad_proposal = client.get(
            "/api/v1/governance/baal/proposals/not-a-number",
            headers={"x-api-key": "governance-key"},
        )
        bad_wallet = client.get(
            "/api/v1/governance/baal/members/not-a-wallet",
            headers={"x-api-key": "governance-key"},
        )

    assert bad_proposal.status_code == 400
    assert bad_wallet.status_code == 400


def test_baal_proposal_route_publishes_service_page_bounds():
    parameter = create_app().openapi()["paths"]["/api/v1/governance/baal/proposals"]["get"]["parameters"][0]

    assert parameter["name"] == "limit"
    assert parameter["schema"]["type"] == "integer"
    assert parameter["schema"]["default"] == 50
    assert parameter["schema"]["minimum"] == 1
    assert parameter["schema"]["maximum"] == 100


@pytest.mark.parametrize("limit", ["0", "101", "not-an-integer"])
def test_baal_proposal_route_rejects_invalid_page_before_reader(monkeypatch, limit):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")

    def fail_reader(*_args, **_kwargs):
        pytest.fail("invalid page must be rejected before proposal reader access")

    monkeypatch.setattr("services.gateway.governance.read_baal_proposals", fail_reader)
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/governance/baal/proposals",
            params={"limit": limit},
            headers={"x-api-key": "governance-key"},
        )

    assert response.status_code == 422


def test_baal_proposal_route_forwards_integer_page_limit(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")
    seen = []

    def read(limit):
        seen.append(limit)
        return read_baal_proposals(limit, client_factory=_factory)

    monkeypatch.setattr("services.gateway.governance.read_baal_proposals", read)
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/governance/baal/proposals",
            params={"limit": "4"},
            headers={"x-api-key": "governance-key"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["limit"] == 4
    assert seen == [4]


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/governance/baal/config", "GET"),
        ("/api/v1/governance/baal/proposals", "GET"),
        ("/api/v1/governance/baal/proposals/3", "GET"),
        ("/api/v1/governance/baal/proposals/not-numeric", "GET"),
        ("/api/v1/governance/baal/members/0x1111111111111111111111111111111111111111", "GET"),
        ("/api/v1/governance/baal/members/not-an-address", "GET"),
    ],
)
def test_governance_route_policies_are_global_private_reads(path, method):
    assert get_route_policy(method, path) == {
        "resource": "governance",
        "action": "read",
        "public": False,
        "location_id": None,
    }


def test_baal_governance_routes_publish_strict_models_but_stay_out_of_public_spec():
    from scripts.export_public_api_openapi import build_public_api_spec

    app_spec = create_app().openapi()
    response_refs = {
        "/api/v1/governance/baal/config": "#/components/schemas/BaalConfigEnvelope",
        "/api/v1/governance/baal/proposals": "#/components/schemas/BaalProposalListEnvelope",
        "/api/v1/governance/baal/proposals/{proposal_id}": "#/components/schemas/BaalProposalDetailEnvelope",
        "/api/v1/governance/baal/members/{wallet}": "#/components/schemas/BaalMemberDetailEnvelope",
    }
    error_codes = {
        "/api/v1/governance/baal/config": {"400", "401", "403", "500", "503"},
        "/api/v1/governance/baal/proposals": {"400", "401", "403", "500", "503"},
        "/api/v1/governance/baal/proposals/{proposal_id}": {"400", "401", "403", "404", "500", "503"},
        "/api/v1/governance/baal/members/{wallet}": {"400", "401", "403", "500", "503"},
    }

    for path, expected_ref in response_refs.items():
        route = app_spec["paths"][path]["get"]
        success = route["responses"]["200"]["content"]["application/json"]["schema"]
        assert success["$ref"] == expected_ref
        assert error_codes[path] <= set(route["responses"])
        schema_name = expected_ref.rsplit("/", 1)[1]
        assert app_spec["components"]["schemas"][schema_name]["additionalProperties"] is False
        for status in ("401", "403"):
            auth_schema = route["responses"][status]["content"]["application/json"]["schema"]
            assert auth_schema["$ref"] == "#/components/schemas/BaalAuthorizationError"
    assert set(response_refs).isdisjoint(build_public_api_spec()["paths"])

    auth_error_schema = app_spec["components"]["schemas"]["BaalAuthorizationError"]
    assert auth_error_schema["additionalProperties"] is False
    assert set(auth_error_schema["properties"]) == {"error", "reason"}
    assert auth_error_schema["properties"]["error"]["const"] == "Unauthorized"

    config_schema = app_spec["components"]["schemas"]["BaalGovernanceConfigValues"]
    assert config_schema["additionalProperties"] is False
    assert set(config_schema["properties"]) == {
        "baal_version",
        "total_shares",
        "total_loot",
        "proposal_count",
        "shares_token",
        "loot_token",
        "avatar",
        "voting_period",
        "grace_period",
        "proposal_offering",
        "quorum_percent",
        "sponsor_threshold",
        "min_retention_percent",
    }
    proposal_schema = app_spec["components"]["schemas"]["BaalProposal"]
    assert proposal_schema["additionalProperties"] is False
    assert set(proposal_schema["properties"]) == {
        "proposal_id",
        "lifecycle",
        "title",
        "details",
        "yes_votes",
        "no_votes",
        "voting_starts",
        "voting_ends",
        "grace_ends",
        "expiration",
        "passed",
        "action_failed",
    }
    member_schema = app_spec["components"]["schemas"]["BaalMember"]
    assert member_schema["additionalProperties"] is False
    assert set(member_schema["properties"]) == {"wallet", "shares", "loot", "delegate"}


def test_baal_governance_routes_validate_projected_payloads_and_keep_no_store(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_config",
        lambda: read_baal_config(client_factory=_factory),
    )
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_proposals",
        lambda limit=50: read_baal_proposals(limit, client_factory=_factory),
    )
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_proposal",
        lambda proposal_id: read_baal_proposal(proposal_id, client_factory=_factory),
    )
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_member",
        lambda wallet: read_baal_member(wallet, client_factory=_factory),
    )

    base = "/api/v1/governance/baal"
    headers = {"x-api-key": "governance-key"}
    with TestClient(create_app()) as client:
        responses = [
            client.get(f"{base}/config", headers=headers),
            client.get(f"{base}/proposals?limit=1", headers=headers),
            client.get(f"{base}/proposals/2", headers=headers),
            client.get(
                f"{base}/members/0x1111111111111111111111111111111111111111",
                headers=headers,
            ),
        ]

    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert all(response.headers["cache-control"] == "no-store" for response in responses)
    assert responses[0].json()["data"]["config"]["total_shares"] == "1000"
    assert responses[1].json()["data"]["returned_count"] == 1
    assert responses[1].json()["data"]["proposals"][0]["proposal_id"] == "2"
    assert len(responses[2].json()["data"]["proposal"]["details"]) == 4000
    assert responses[3].json()["data"]["member"]["shares"] == "12"


def test_baal_governance_route_rejects_projection_drift_without_leaking_fields(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "governance-key:governance-reader")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "governance-reader:governance:read")
    bad_projection = read_baal_config(client_factory=_factory)
    bad_projection["config"]["unreviewed_secret"] = "must stay private"
    monkeypatch.setattr(
        "services.gateway.governance.read_baal_config", lambda: bad_projection
    )

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/governance/baal/config",
            headers={"x-api-key": "governance-key"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Gateway request failed"}
    assert "must stay private" not in response.text
