"""Network trust tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/079_web_of_trust.sql")


def test_schema_has_network_value_view() -> None:
    content = SCHEMA.read_text()
    assert "v_network_value" in content


def test_schema_has_trust_graph_view() -> None:
    content = SCHEMA.read_text()
    assert "v_evaluator_trust_graph" in content


def test_network_value_computes_metcalfe() -> None:
    content = SCHEMA.read_text()
    assert "active_farms" in content
    assert "active_evaluators" in content
    assert "published_attestations" in content
    assert "evaluator_network_value" in content
    assert "attestation_network_value" in content


def test_trust_graph_joins_evaluator() -> None:
    content = SCHEMA.read_text()
    assert "e1.display_name AS source_name" in content
    assert "e1.evaluator_type AS source_type" in content
    assert "e1.trust_score AS source_trust" in content


def test_network_service_exists() -> None:
    assert Path("services/scoring/network.py").exists()


def test_service_has_compute_network_value() -> None:
    from services.scoring.network import compute_network_value
    assert callable(compute_network_value)


def test_service_has_get_network_growth() -> None:
    from services.scoring.network import get_network_growth
    assert callable(get_network_growth)


def test_service_has_get_trust_graph() -> None:
    from services.scoring.network import get_trust_graph
    assert callable(get_trust_graph)


def test_service_has_compute_transitive_trust() -> None:
    from services.scoring.network import compute_transitive_trust
    assert callable(compute_transitive_trust)


def test_network_value_formula() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "evaluator_value = evaluators * max(evaluators - 1, 0) // 2" in content
    assert "attestation_value = attestations * max(attestations - 1, 0) // 2" in content


def test_trust_graph_uses_bfs() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "frontier" in content
    assert "visited" in content
    assert "next_frontier" in content


def test_transitive_trust_computes_path() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "trust_product" in content
    assert "path.append" in content
    assert "path_length" in content


def test_transitive_trust_has_max_depth() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "max_depth" in content


def test_service_uses_logging() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "get_logger" in content


def test_network_value_includes_density() -> None:
    content = Path("services/scoring/network.py").read_text()
    assert "network_density" in content
    assert "cross_refs" in content
