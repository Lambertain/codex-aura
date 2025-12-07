import pytest
import time
from codex_aura.graph_diff import calculate_graph_diff
from codex_aura.models.graph import Graph, Repository, Stats
from codex_aura.models.node import Node
from codex_aura.models.edge import Edge, EdgeType
from datetime import datetime


@pytest.fixture
def sample_repo():
    """Sample repository for testing."""
    return Repository(
        path="/tmp/test-repo",
        name="test-repo",
        user_id="user123"
    )


@pytest.fixture
def base_graph(sample_repo):
    """Base graph with common nodes and edges."""
    return Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=3, total_edges=2, node_types={"file": 1, "function": 2}),
        nodes=[
            Node(id="main.py", type="file", name="main.py", path="main.py", content="print('hello')"),
            Node(id="func1", type="function", name="func1", path="main.py", lines=[1, 3]),
            Node(id="func2", type="function", name="func2", path="main.py", lines=[5, 7])
        ],
        edges=[
            Edge(source="main.py", target="func1", type=EdgeType.IMPORTS),
            Edge(source="func1", target="func2", type=EdgeType.CALLS)
        ],
        sha="abc123"
    )


def test_no_changes(base_graph):
    """Test diff when graphs are identical."""
    result = calculate_graph_diff(base_graph, base_graph)

    assert len(result["added_nodes"]) == 0
    assert len(result["removed_nodes"]) == 0
    assert len(result["changed_nodes"]) == 0
    assert len(result["added_edges"]) == 0
    assert len(result["removed_edges"]) == 0


def test_added_nodes(base_graph, sample_repo):
    """Test detection of added nodes."""
    # Create new graph with additional node
    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=4, total_edges=2, node_types={"file": 1, "function": 3}),
        nodes=base_graph.nodes + [
            Node(id="func3", type="function", name="func3", path="main.py", lines=[9, 11])
        ],
        edges=base_graph.edges,
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["added_nodes"]) == 1
    assert result["added_nodes"][0]["id"] == "func3"
    assert len(result["removed_nodes"]) == 0
    assert len(result["changed_nodes"]) == 0


def test_removed_nodes(base_graph, sample_repo):
    """Test detection of removed nodes."""
    # Create new graph with one node removed
    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=2, total_edges=1, node_types={"file": 1, "function": 1}),
        nodes=[base_graph.nodes[0], base_graph.nodes[1]],  # Remove func2
        edges=[base_graph.edges[0]],  # Remove edge to func2
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["removed_nodes"]) == 1
    assert result["removed_nodes"][0]["id"] == "func2"
    assert len(result["added_nodes"]) == 0
    assert len(result["changed_nodes"]) == 0


def test_changed_nodes(base_graph, sample_repo):
    """Test detection of changed nodes."""
    # Create new graph with modified node
    modified_nodes = base_graph.nodes.copy()
    modified_nodes[1] = Node(
        id="func1",
        type="function",
        name="func1",
        path="main.py",
        lines=[1, 5],  # Changed line range
        content="def func1():\n    return 'changed'"  # Changed content
    )

    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=base_graph.stats,
        nodes=modified_nodes,
        edges=base_graph.edges,
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["changed_nodes"]) == 1
    assert result["changed_nodes"][0]["id"] == "func1"
    assert len(result["added_nodes"]) == 0
    assert len(result["removed_nodes"]) == 0


def test_added_edges(base_graph, sample_repo):
    """Test detection of added edges."""
    # Create new graph with additional edge
    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=3, total_edges=3, node_types={"file": 1, "function": 2}),
        nodes=base_graph.nodes,
        edges=base_graph.edges + [
            Edge(source="main.py", target="func2", type=EdgeType.IMPORTS)
        ],
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["added_edges"]) == 1
    assert result["added_edges"][0]["source"] == "main.py"
    assert result["added_edges"][0]["target"] == "func2"
    assert len(result["removed_edges"]) == 0


def test_removed_edges(base_graph, sample_repo):
    """Test detection of removed edges."""
    # Create new graph with one edge removed
    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=3, total_edges=1, node_types={"file": 1, "function": 2}),
        nodes=base_graph.nodes,
        edges=[base_graph.edges[0]],  # Remove the CALLS edge
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["removed_edges"]) == 1
    assert result["removed_edges"][0]["source"] == "func1"
    assert result["removed_edges"][0]["target"] == "func2"
    assert len(result["added_edges"]) == 0


def test_complex_changes(base_graph, sample_repo):
    """Test complex scenario with multiple types of changes."""
    # Create new graph with various changes
    new_nodes = base_graph.nodes + [
        Node(id="utils.py", type="file", name="utils.py", path="utils.py"),
        Node(id="helper", type="function", name="helper", path="utils.py")
    ]

    # Modify existing node
    modified_nodes = new_nodes.copy()
    modified_nodes[1] = Node(
        id="func1",
        type="function",
        name="func1",
        path="main.py",
        lines=[1, 4],
        content="def func1():\n    return helper()"
    )

    new_edges = base_graph.edges + [
        Edge(source="utils.py", target="helper", type=EdgeType.IMPORTS),
        Edge(source="func1", target="helper", type=EdgeType.CALLS)
    ]

    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=5, total_edges=4, node_types={"file": 2, "function": 3}),
        nodes=modified_nodes,
        edges=new_edges,
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    assert len(result["added_nodes"]) == 2  # utils.py and helper
    assert len(result["removed_nodes"]) == 0
    assert len(result["changed_nodes"]) == 1  # func1 modified
    assert len(result["added_edges"]) == 2  # new edges
    assert len(result["removed_edges"]) == 0


def test_performance_large_graph():
    """Test performance with larger graphs."""
    # Create larger graphs for performance testing
    sample_repo = Repository(path="/tmp/large-repo", name="large-repo", user_id="user123")

    # Create 1000 nodes
    nodes_old = []
    nodes_new = []

    for i in range(1000):
        node = Node(
            id=f"func_{i}",
            type="function",
            name=f"func_{i}",
            path=f"module_{i//100}.py",
            lines=[i*2, i*2+1],
            content=f"def func_{i}(): pass"
        )
        nodes_old.append(node)
        # Modify some nodes for new graph
        if i % 100 == 0:
            modified_node = Node(
                id=f"func_{i}",
                type="function",
                name=f"func_{i}",
                path=f"module_{i//100}.py",
                lines=[i*2, i*2+2],  # Changed
                content=f"def func_{i}(): return {i}"  # Changed
            )
            nodes_new.append(modified_node)
        else:
            nodes_new.append(node)

    # Add some new nodes
    for i in range(1000, 1050):
        nodes_new.append(Node(
            id=f"func_{i}",
            type="function",
            name=f"func_{i}",
            path=f"module_{i//100}.py",
            lines=[i*2, i*2+1],
            content=f"def func_{i}(): pass"
        ))

    # Create edges (simplified)
    edges_old = []
    edges_new = []

    for i in range(0, 999, 2):
        edges_old.append(Edge(source=f"func_{i}", target=f"func_{i+1}", type=EdgeType.CALLS))
        edges_new.append(Edge(source=f"func_{i}", target=f"func_{i+1}", type=EdgeType.CALLS))

    # Add new edges
    for i in range(1000, 1049):
        edges_new.append(Edge(source=f"func_{i}", target=f"func_{(i+1)%1000}", type=EdgeType.CALLS))

    graph_old = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=len(nodes_old), total_edges=len(edges_old), node_types={"function": len(nodes_old)}),
        nodes=nodes_old,
        edges=edges_old,
        sha="old_sha"
    )

    graph_new = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=Stats(total_nodes=len(nodes_new), total_edges=len(edges_new), node_types={"function": len(nodes_new)}),
        nodes=nodes_new,
        edges=edges_new,
        sha="new_sha"
    )

    start_time = time.time()
    result = calculate_graph_diff(graph_old, graph_new)
    duration = time.time() - start_time

    # Should complete in less than 1 second for mid-size repo
    assert duration < 1.0, f"Graph diff took {duration:.2f}s, should be < 1.0s"

    # Verify results
    assert len(result["added_nodes"]) == 50  # 50 new nodes
    assert len(result["changed_nodes"]) == 10  # 10 modified nodes (every 100th)
    assert len(result["removed_nodes"]) == 0
    assert len(result["added_edges"]) == 49  # 49 new edges
    assert len(result["removed_edges"]) == 0


def test_properties_hash_changed_nodes(base_graph, sample_repo):
    """Test that changed nodes are detected based on properties hash."""
    # Create new graph with same structure but different properties
    new_nodes = []
    for node in base_graph.nodes:
        if node.type == "function":
            # Change a property that affects hash
            new_node = Node(
                id=node.id,
                type=node.type,
                name=node.name,
                path=node.path,
                lines=node.lines,
                content=node.content + " # modified",  # This changes the hash
                docstring=node.docstring
            )
            new_nodes.append(new_node)
        else:
            new_nodes.append(node)

    new_graph = Graph(
        version="1.0",
        generated_at=datetime.now(),
        repository=sample_repo,
        stats=base_graph.stats,
        nodes=new_nodes,
        edges=base_graph.edges,
        sha="def456"
    )

    result = calculate_graph_diff(base_graph, new_graph)

    # Should detect 2 changed function nodes
    assert len(result["changed_nodes"]) == 2
    assert all(node["type"] == "function" for node in result["changed_nodes"])