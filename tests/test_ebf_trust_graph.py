"""EBF trust graph export tests."""

from services.scoring.trust_graph import export_trust_graph, trust_graph_to_mermaid


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


def test_public_safe_export_filters_private_connected_nodes() -> None:
    nodes = [
        {"id": "public-seed", "node_type": "scorecard", "label": "Public", "public_safe": True},
        {"id": "private-neighbor", "node_type": "reviewer", "label": "Private", "public_safe": False},
    ]
    edges = [
        {
            "id": "edge-1",
            "source_node_id": "public-seed",
            "target_node_id": "private-neighbor",
            "edge_type": "supports",
            "public_safe": True,
        }
    ]

    class Cursor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple]] = []

        def execute(self, query: str, parameters: tuple) -> None:
            self.calls.append((query, parameters))

        def fetchall(self) -> list[dict[str, object]]:
            query, parameters = self.calls[-1]
            if "SELECT n.*" in query:
                final_select = query.split("SELECT n.*", 1)[1]
                if "WHERE n.public_safe = TRUE" in final_select:
                    return [nodes[0]]
                return nodes

            source_ids, target_ids = parameters
            return [
                edge
                for edge in edges
                if edge["source_node_id"] in source_ids
                and edge["target_node_id"] in target_ids
                and ("AND e.public_safe = TRUE" not in query or edge["public_safe"])
            ]

        def close(self) -> None:
            return None

    class Connection:
        def __init__(self) -> None:
            self.cursor_instance = Cursor()

        def cursor(self, **kwargs):
            return self.cursor_instance

    connection = Connection()
    graph = export_trust_graph(connection, "reference-1", public_safe=True)

    assert [node["id"] for node in graph["nodes"]] == ["public-seed"]
    assert graph["edges"] == []
    node_query, node_parameters = connection.cursor_instance.calls[0]
    assert node_parameters == ("reference-1",)
    assert "WHERE n.public_safe = TRUE" in node_query.split("SELECT n.*", 1)[1]
    edge_query, edge_parameters = connection.cursor_instance.calls[1]
    assert "AND e.public_safe = TRUE" in edge_query
    assert edge_parameters == (["public-seed"], ["public-seed"])


if __name__ == "__main__":
    test_trust_graph_mermaid_export()
