from unittest.mock import MagicMock, patch
import uuid

import pytest

from services.graph_projection import evidence_lineage, kernel, policy, query


def test_rebuild_orders_transaction_and_activation():
    generation_id = uuid.uuid4()
    cur = MagicMock()
    cur.fetchone.side_effect = [(generation_id,), (0, 0)]
    cur.rowcount = 1
    conn = MagicMock(); conn.cursor.return_value = cur
    with patch.object(kernel, "load_sources", return_value={}), patch.object(kernel, "build", return_value=([], [])):
        result = kernel.rebuild(conn, "operator")
    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
    assert "pg_advisory_xact_lock" in statements[3]
    assert "status = 'superseded'" in statements[-3]
    assert "status = 'active'" in statements[-2]
    assert "graph_projection" in statements[-1]
    conn.commit.assert_called_once_with()
    assert result["generation_id"] == generation_id


def test_rebuild_rolls_back_and_propagates_without_failed_write():
    conn = MagicMock(); cur = conn.cursor.return_value
    cur.execute.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError, match="database failed"):
        kernel.rebuild(conn, "operator")
    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
    assert not any("failed" in str(call).lower() for call in cur.execute.call_args_list)


def test_public_policy_is_conservative():
    eligible = {"loc"}
    assert policy.metric_value_is_public({"verified": True, "is_public_candidate": True, "location_id": "loc"}, eligible)
    assert not policy.metric_value_is_public({"verified": False, "location_id": "loc"}, eligible)
    base = {"location_id": "loc", "status": "published", "public_claim": True, "evidence_maturity": 4, "claim_category": "social"}
    assert policy.impact_claim_is_public(base, eligible)
    carbon = {**base, "claim_category": "carbon", "evidence_maturity": 6, "claim_type": "third_party_verified_claim", "external_verifier": "V", "methodology_ref": "M"}
    assert policy.impact_claim_is_public(carbon, eligible)
    assert not policy.impact_claim_is_public({**carbon, "external_verifier": ""}, eligible)


def test_iri_lookup_is_exact_read_only_and_allowlisted():
    cur = MagicMock(); cur.description = [("entity_type",), ("entity_id",), ("iri",)]; entity_id = uuid.uuid4(); cur.fetchall.return_value = [("location", entity_id, "kokonut:location:x:v1")]
    result = evidence_lineage.lookup_iris(cur, [("location", entity_id)])
    sql = cur.execute.call_args.args[0].lower()
    assert sql.lstrip().startswith("select")
    assert "insert" not in sql and "update" not in sql
    assert result[("location", str(entity_id))] == "kokonut:location:x:v1"
    with pytest.raises(ValueError): evidence_lineage.lookup_iris(cur, [("not_allowed", entity_id)])


@pytest.mark.parametrize("kwargs", [{"depth": 6}, {"depth": -1}, {"node_cap": 501}, {"node_cap": 0}, {"edge_types": ["arbitrary"]}, {"audience": "private"}])
def test_query_rejects_unbounded_or_unsupported_inputs(kwargs):
    with pytest.raises(ValueError): query.query_graph(MagicMock(), "location:x", **kwargs)


def test_query_filters_every_read_to_active_generation():
    conn = MagicMock(); cur = conn.cursor.return_value
    cur.fetchall.side_effect = [[{"id": uuid.uuid4()}], []]
    query.query_graph(conn, "location:x")
    node_sql = cur.execute.call_args_list[1].args[0]
    edge_sql = cur.execute.call_args_list[2].args[0]
    assert "active_generation_id" in node_sql
    assert "active_generation_id" in edge_sql
    assert "SET LOCAL statement_timeout" in cur.execute.call_args_list[0].args[0]
