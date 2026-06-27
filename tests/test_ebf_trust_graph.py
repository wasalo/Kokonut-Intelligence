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


if __name__ == "__main__":
    test_trust_graph_mermaid_export()
