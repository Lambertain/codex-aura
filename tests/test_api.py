"""Tests for API endpoints."""

import pytest
from datetime import datetime
from pathlib import Path

from src.codex_aura.models.graph import Graph, Repository, Stats
from src.codex_aura.models.node import Node
from src.codex_aura.models.edge import Edge, EdgeType
from src.codex_aura.storage.sqlite import SQLiteStorage
from src.codex_aura.api.server import traverse_dependencies


def test_traverse_dependencies_basic():
    """Test basic dependency traversal."""
    nodes = [
        Node(id="a", type="file", name="a.py", path="a.py"),
        Node(id="b", type="file", name="b.py", path="b.py"),
        Node(id="c", type="file", name="c.py", path="c.py"),
    ]

    edges = [
        Edge(source="a", target="b", type=EdgeType.IMPORTS),
        Edge(source="b", target="c", type=EdgeType.IMPORTS),
    ]

    stats = Stats(total_nodes=3, total_edges=2, node_types={"file": 3})
    repository = Repository(path="/test", name="test")

    graph = Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=repository,
        stats=stats,
        nodes=nodes,
        edges=edges
    )

    # Test outgoing traversal
    node_ids, edge_tuples = traverse_dependencies(graph, "a", 2, "outgoing")
    assert "a" in node_ids
    assert "b" in node_ids
    assert "c" in node_ids
    assert len(edge_tuples) == 2

    # Test incoming traversal
    node_ids, edge_tuples = traverse_dependencies(graph, "c", 2, "incoming")
    assert "c" in node_ids
    assert "b" in node_ids
    assert "a" in node_ids
    assert len(edge_tuples) == 2

    # Test depth limit
    node_ids, edge_tuples = traverse_dependencies(graph, "a", 1, "outgoing")
    assert "a" in node_ids
    assert "b" in node_ids
    assert "c" not in node_ids  # Should not reach c due to depth limit
    assert len(edge_tuples) == 1


def test_traverse_dependencies_cycle():
    """Test dependency traversal with cycles."""
    nodes = [
        Node(id="a", type="file", name="a.py", path="a.py"),
        Node(id="b", type="file", name="b.py", path="b.py"),
    ]

    edges = [
        Edge(source="a", target="b", type=EdgeType.IMPORTS),
        Edge(source="b", target="a", type=EdgeType.IMPORTS),  # Cycle
    ]

    stats = Stats(total_nodes=2, total_edges=2, node_types={"file": 2})
    repository = Repository(path="/test", name="test")

    graph = Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=repository,
        stats=stats,
        nodes=nodes,
        edges=edges
    )

    # Should handle cycles without infinite loops
    node_ids, edge_tuples = traverse_dependencies(graph, "a", 5, "both")
    assert "a" in node_ids
    assert "b" in node_ids
    assert len(edge_tuples) == 2  # Both edges should be included


def test_storage_operations(tmp_path):
    """Test storage save/load operations."""
    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))

    nodes = [
        Node(id="test.py", type="file", name="test.py", path="test.py"),
        Node(id="test.py::func", type="function", name="func", path="test.py", lines=[1, 5]),
    ]

    edges = [
        Edge(source="test.py", target="test.py::func", type=EdgeType.IMPORTS),
    ]

    stats = Stats(total_nodes=2, total_edges=1, node_types={"file": 1, "function": 1})
    repository = Repository(path="/test", name="test-repo")

    graph = Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=repository,
        stats=stats,
        nodes=nodes,
        edges=edges
    )

    graph_id = "test_graph_123"
    storage.save_graph(graph, graph_id)

    loaded_graph = storage.load_graph(graph_id)
    assert loaded_graph is not None
    assert loaded_graph.repository.name == "test-repo"
    assert len(loaded_graph.nodes) == 2
    assert len(loaded_graph.edges) == 1

    # Test non-existent graph
    assert storage.load_graph("nonexistent") is None