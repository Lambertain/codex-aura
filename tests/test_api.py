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


def test_new_endpoints_registered():
    """Test that new endpoints are properly registered."""
    from src.codex_aura.api.server import app

    routes = [route.path for route in app.routes]
    assert "/api/v1/context" in routes
    assert "/api/v1/graph/{graph_id}/impact" in routes
    assert "/api/v1/graph/{graph_id}" in routes  # DELETE endpoint


def test_context_request_model():
    """Test ContextRequest model validation."""
    from src.codex_aura.api.server import ContextRequest
    from pydantic import ValidationError
    import pytest

    # Valid request
    request = ContextRequest(
        graph_id="g_abc123",
        entry_points=["src/services/order.py"],
        depth=2,
        include_code=True,
        max_nodes=50
    )
    assert request.graph_id == "g_abc123"

    # Invalid depth
    with pytest.raises(ValidationError):
        ContextRequest(
            graph_id="g_abc123",
            entry_points=["src/services/order.py"],
            depth=10  # > 5
        )

    # Invalid max_nodes
    with pytest.raises(ValidationError):
        ContextRequest(
            graph_id="g_abc123",
            entry_points=["src/services/order.py"],
            max_nodes=200  # > 100
        )


def test_delete_graph_storage(tmp_path):
    """Test delete graph storage operation."""
    from src.codex_aura.storage.sqlite import SQLiteStorage
    from src.codex_aura.models.graph import Graph, Repository, Stats
    from src.codex_aura.models.node import Node
    from datetime import datetime

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))

    # Create a test graph
    nodes = [Node(id="test.py", type="file", name="test.py", path="test.py")]
    edges = []
    stats = Stats(total_nodes=1, total_edges=0, node_types={"file": 1})
    repository = Repository(path="/test", name="test")

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

    # Verify graph exists
    assert storage.load_graph(graph_id) is not None

    # Delete graph
    deleted = storage.delete_graph(graph_id)
    assert deleted is True

    # Verify graph is gone
    assert storage.load_graph(graph_id) is None

    # Try to delete non-existent graph
    deleted = storage.delete_graph("nonexistent")
    assert deleted is False


def test_capabilities_endpoint():
    """Test capabilities endpoint."""
    from src.codex_aura.plugins.registry import PluginRegistry

    # Test the underlying function directly
    data = PluginRegistry.get_all_capabilities()
    assert "context_plugin" in data
    assert "impact_plugin" in data
    assert "premium_available" in data

    # Check basic plugin capabilities
    if data["context_plugin"]:
        assert data["context_plugin"]["name"] == "basic"
        assert data["context_plugin"]["version"] == "1.0.0"
        assert "capabilities" in data["context_plugin"]

    if data["impact_plugin"]:
        assert data["impact_plugin"]["name"] == "basic"
        assert data["impact_plugin"]["version"] == "1.0.0"
        assert "capabilities" in data["impact_plugin"]