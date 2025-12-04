"""Unit tests for SQLite storage backend."""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from src.codex_aura.models.graph import Graph, Repository, Stats
from src.codex_aura.models.node import Node
from src.codex_aura.models.edge import Edge, EdgeType
from src.codex_aura.storage.sqlite import SQLiteStorage


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    db_path = tempfile.mktemp(suffix='.db')
    yield db_path
    # Try to remove file, ignore if locked
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass  # File still in use, will be cleaned up later


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    nodes = [
        Node(id="main.py", type="file", name="main.py", path="main.py"),
        Node(id="utils.py", type="file", name="utils.py", path="utils.py"),
        Node(id="main.py::main", type="function", name="main", path="main.py", lines=[1, 10]),
        Node(id="utils.py::helper", type="function", name="helper", path="utils.py", lines=[1, 5]),
        Node(id="utils.py::Config", type="class", name="Config", path="utils.py", lines=[10, 20]),
    ]

    edges = [
        Edge(source="main.py", target="utils.py", type=EdgeType.IMPORTS),
        Edge(source="main.py::main", target="utils.py::helper", type=EdgeType.CALLS),
        Edge(source="utils.py::Config", target="utils.py::helper", type=EdgeType.EXTENDS),
    ]

    stats = Stats(total_nodes=5, total_edges=3, node_types={"file": 2, "function": 2, "class": 1})
    repository = Repository(path="/test/repo", name="test-repo")

    return Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=repository,
        stats=stats,
        nodes=nodes,
        edges=edges
    )


def test_sqlite_save_load(temp_db, sample_graph):
    """Test saving and loading a graph."""
    storage = SQLiteStorage(db_path=temp_db)

    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)

    loaded_graph = storage.load_graph(graph_id)
    assert loaded_graph is not None
    assert loaded_graph.repository.name == sample_graph.repository.name
    assert len(loaded_graph.nodes) == len(sample_graph.nodes)
    assert len(loaded_graph.edges) == len(sample_graph.edges)

    # Verify node data
    loaded_nodes = {n.id: n for n in loaded_graph.nodes}
    for node in sample_graph.nodes:
        assert node.id in loaded_nodes
        loaded_node = loaded_nodes[node.id]
        assert loaded_node.type == node.type
        assert loaded_node.name == node.name
        assert loaded_node.path == node.path

    # Verify edge data
    loaded_edges = [(e.source, e.target, e.type.value) for e in loaded_graph.edges]
    original_edges = [(e.source, e.target, e.type.value) for e in sample_graph.edges]
    assert set(loaded_edges) == set(original_edges)


def test_sqlite_query_nodes(temp_db, sample_graph):
    """Test querying nodes from storage."""
    storage = SQLiteStorage(db_path=temp_db)

    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)

    # Query all nodes
    nodes = storage.query_nodes(graph_id)
    assert len(nodes) == 5

    # Query by type
    file_nodes = storage.query_nodes(graph_id, node_types=["file"])
    assert len(file_nodes) == 2
    assert all(n.type == "file" for n in file_nodes)

    function_nodes = storage.query_nodes(graph_id, node_types=["function"])
    assert len(function_nodes) == 2
    assert all(n.type == "function" for n in function_nodes)

    # Query by path
    main_nodes = storage.query_nodes(graph_id, path_filter="main.py")
    assert len(main_nodes) == 2
    assert all(n.path == "main.py" for n in main_nodes)


def test_sqlite_query_edges(temp_db, sample_graph):
    """Test querying edges from storage."""
    storage = SQLiteStorage(db_path=temp_db)

    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)

    # Query all edges
    edges = storage.query_edges(graph_id)
    assert len(edges) == 3

    # Query by type
    import_edges = storage.query_edges(graph_id, edge_types=["IMPORTS"])
    assert len(import_edges) == 1
    assert import_edges[0].type == EdgeType.IMPORTS

    call_edges = storage.query_edges(graph_id, edge_types=["CALLS"])
    assert len(call_edges) == 1
    assert call_edges[0].type == EdgeType.CALLS

    # Query by source
    main_edges = storage.query_edges(graph_id, source_filter="main.py")
    assert len(main_edges) == 2  # main.py -> utils.py and main.py::main -> utils.py::helper
    assert all("main.py" in e.source for e in main_edges)

    # Query by target
    helper_edges = storage.query_edges(graph_id, target_filter="utils.py::helper")
    assert len(helper_edges) == 2  # main.py::main -> utils.py::helper and utils.py::Config -> utils.py::helper
    assert all(e.target == "utils.py::helper" for e in helper_edges)


def test_sqlite_query_dependencies(temp_db, sample_graph):
    """Test querying dependencies from storage."""
    storage = SQLiteStorage(db_path=temp_db)

    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)

    # Query outgoing dependencies
    deps = storage.query_dependencies(graph_id, "main.py", direction="outgoing", max_depth=2)
    node_ids, edge_tuples = deps

    assert "main.py" in node_ids
    assert "utils.py" in node_ids
    # Only direct outgoing edges from main.py
    assert len(edge_tuples) == 1  # main.py -> utils.py

    # Query incoming dependencies
    deps = storage.query_dependencies(graph_id, "utils.py::helper", direction="incoming", max_depth=2)
    node_ids, edge_tuples = deps

    assert "utils.py::helper" in node_ids
    assert "main.py::main" in node_ids
    assert "utils.py::Config" in node_ids


def test_sqlite_list_graphs(temp_db, sample_graph):
    """Test listing graphs."""
    storage = SQLiteStorage(db_path=temp_db)

    # Save multiple graphs
    storage.save_graph(sample_graph, "graph1")
    storage.save_graph(sample_graph, "graph2")

    graphs = storage.list_graphs()
    assert len(graphs) == 2

    # Filter by repo path
    graphs = storage.list_graphs(repo_path="/test/repo")
    assert len(graphs) == 2

    graphs = storage.list_graphs(repo_path="/other/repo")
    assert len(graphs) == 0


def test_sqlite_delete_graph(temp_db, sample_graph):
    """Test deleting graphs."""
    storage = SQLiteStorage(db_path=temp_db)

    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)

    # Verify exists
    assert storage.load_graph(graph_id) is not None

    # Delete
    deleted = storage.delete_graph(graph_id)
    assert deleted is True

    # Verify gone
    assert storage.load_graph(graph_id) is None

    # Try to delete again
    deleted = storage.delete_graph(graph_id)
    assert deleted is False


def test_sqlite_migrations(temp_db):
    """Test database migrations."""
    storage = SQLiteStorage(db_path=temp_db)

    # Check that migrations table exists
    with storage._get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'")
        assert cursor.fetchone() is not None

    # Run migrations (should be idempotent)
    storage._run_migrations()

    # Verify current schema version
    version = storage._get_schema_version()
    assert version >= 1

    # Test migration to new version (simulate)
    # This would normally be tested with actual schema changes
    pass


def test_sqlite_nonexistent_graph(temp_db):
    """Test operations on nonexistent graphs."""
    storage = SQLiteStorage(db_path=temp_db)

    assert storage.load_graph("nonexistent") is None
    assert storage.delete_graph("nonexistent") is False

    with pytest.raises(Exception):  # Should raise appropriate exception
        storage.query_nodes("nonexistent")

    with pytest.raises(Exception):
        storage.query_edges("nonexistent")

    with pytest.raises(Exception):
        storage.query_dependencies("nonexistent", "node1")