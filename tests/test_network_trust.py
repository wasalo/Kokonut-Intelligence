"""Runtime-oriented network trust tests."""

import pytest

from services.scoring.network import compute_network_value, compute_transitive_trust, get_trust_graph


class Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.current = None
        self.sql = []

    def execute(self, query, params=None):
        self.sql.append((" ".join(query.split()), params))
        self.current = next(self.responses)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current

    def close(self):
        pass


class Connection:
    def __init__(self, responses):
        self.cur = Cursor(responses)

    def cursor(self, **_kwargs):
        return self.cur


def test_network_density_uses_distinct_eligible_directed_pairs() -> None:
    conn = Connection([{"count": 1}, {"count": 3}, {"count": 2}, {"count": 0},
                       {"count": 0}, {"count": 4}, {"count": 0}])
    result = compute_network_value(conn)
    assert result["network_density"] == pytest.approx(4 / 6, abs=0.000001)
    density_sql = conn.cur.sql[5][0]
    assert "SELECT DISTINCT g.source_evaluator_id, g.target_evaluator_id" in density_sql
    assert "source.status = 'active'" in density_sql
    assert "g.reference_type IN ('supports', 'validates')" in density_sql


def test_trust_graph_uses_active_positive_directed_edges_and_strength() -> None:
    conn = Connection([
        {"id": "a", "display_name": "A", "evaluator_type": "peer", "trust_score": 0.9},
        [{"target_evaluator_id": "b", "reference_type": "supports", "strength": 0.7,
          "id": "b", "display_name": "B", "evaluator_type": "peer", "trust_score": 0.8}],
    ])
    result = get_trust_graph(conn, "a", depth=1)
    assert result["nodes_found"] == 2
    assert result["edges"] == [{"from": "a", "to": "b", "via": "supports",
                                "reference_type": "supports", "strength": 0.7, "hop": 1}]
    edge_sql = conn.cur.sql[1][0]
    assert "v_evaluator_trust_edges" in edge_sql
    assert "target.status = 'active'" in edge_sql
    assert "g.strength > 0" in edge_sql


def test_transitive_trust_selects_strongest_product_not_first_or_shortest() -> None:
    conn = Connection([
        {"trust_score": 0.9},
        [
            {"source_evaluator_id": "a", "target_evaluator_id": "d", "reference_type": "supports", "strength": 0.4, "target_trust": 1.0},
            {"source_evaluator_id": "a", "target_evaluator_id": "b", "reference_type": "validates", "strength": 0.9, "target_trust": 0.9},
            {"source_evaluator_id": "b", "target_evaluator_id": "d", "reference_type": "supports", "strength": 0.9, "target_trust": 0.9},
        ],
    ])
    result = compute_transitive_trust(conn, "a", "d", max_depth=2)
    assert [node["evaluator_id"] for node in result["path"]] == ["a", "b", "d"]
    assert result["path_length"] == 2
    assert result["transitive_trust"] == 0.59049


def test_transitive_trust_zero_hop_identity() -> None:
    conn = Connection([{"trust_score": 0.73}])
    result = compute_transitive_trust(conn, "a", "a", max_depth=0)
    assert result == {"found": True, "source": "a", "target": "a", "path_length": 0,
                      "transitive_trust": 1.0,
                      "path": [{"evaluator_id": "a", "trust_score": 0.73}]}


def test_transitive_trust_respects_depth_bound() -> None:
    conn = Connection([
        {"trust_score": 1.0},
        [{"source_evaluator_id": "a", "target_evaluator_id": "b", "reference_type": "supports", "strength": 1.0, "target_trust": 1.0},
         {"source_evaluator_id": "b", "target_evaluator_id": "c", "reference_type": "supports", "strength": 1.0, "target_trust": 1.0}],
    ])
    result = compute_transitive_trust(conn, "a", "c", max_depth=1)
    assert result["found"] is False
