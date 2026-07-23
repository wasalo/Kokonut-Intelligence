"""EBF trust graph export tests."""

from services.scoring.trust_graph import trust_graph_to_mermaid


def test_trust_graph_mermaid_export() -> None:
    graph = {
        "nodes": [
            {"id": "a0000000-0000-0000-0000-000000000001", "node_type": "scorecard", "label": "Scorecard"},
            {"id": "a0000000-0000-0000-0000-000000000002", "node_type": "evidence", "label": "Evidence"},
        ],
        "edges": [
            {
                "source_node_id": "a0000000-0000-0000-0000-000000000002",
                "target_node_id": "a0000000-0000-0000-0000-000000000001",
                "edge_type": "supports",
            }
        ],
    }
    rendered = trust_graph_to_mermaid(graph)
    assert rendered.startswith("graph TD")
    assert "Scorecard" in rendered
    assert "supports" in rendered


def test_trust_graph_mermaid_empty_graph() -> None:
    graph = {"nodes": [], "edges": []}
    rendered = trust_graph_to_mermaid(graph)
    assert "empty" in rendered.lower() or "No trust graph" in rendered


def test_trust_graph_mermaid_multiple_edges() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "node_type": "scorecard", "label": "S1"},
            {"id": "n2", "node_type": "evidence", "label": "E1"},
            {"id": "n3", "node_type": "reviewer", "label": "R1"},
        ],
        "edges": [
            {"source_node_id": "n2", "target_node_id": "n1", "edge_type": "supports"},
            {"source_node_id": "n3", "target_node_id": "n1", "edge_type": "reviewed_by"},
        ],
    }
    rendered = trust_graph_to_mermaid(graph)
    assert rendered.count("-->") == 2
    assert "reviewed_by" in rendered


def test_trust_graph_mermaid_escapes_quotes_in_labels() -> None:
    graph = {
        "nodes": [{"id": "n1", "node_type": "test", "label": 'He said "hello"'}],
        "edges": [],
    }
    rendered = trust_graph_to_mermaid(graph)
    assert "'" in rendered


if __name__ == "__main__":
    test_trust_graph_mermaid_export()
