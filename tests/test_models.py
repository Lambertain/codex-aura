import pytest
from datetime import datetime
from pathlib import Path
from pydantic import ValidationError

from codex_aura.models.node import Node
from codex_aura.models.edge import Edge, EdgeType
from codex_aura.models.graph import Graph, Repository, Stats, save_graph, load_graph


class TestNode:
    def test_node_creation(self):
        """Test basic Node creation."""
        node = Node(
            id="test.py",
            type="file",
            name="test.py",
            path="test.py"
        )
        assert node.id == "test.py"
        assert node.type == "file"
        assert node.name == "test.py"
        assert node.path == "test.py"
        assert node.lines is None
        assert node.docstring is None

    def test_node_with_optional_fields(self):
        """Test Node creation with optional fields."""
        node = Node(
            id="MyClass",
            type="class",
            name="MyClass",
            path="models/user.py",
            lines=[10, 25],
            docstring="A user model class."
        )
        assert node.lines == [10, 25]
        assert node.docstring == "A user model class."

    def test_invalid_node(self):
        """Test Node validation errors."""
        # Test with invalid type
        with pytest.raises(ValidationError):
            Node(
                id="test.py",
                type="invalid_type",  # Should be one of: "file", "class", "function"
                name="test.py",
                path="test.py"
            )

        # Test with invalid lines
        with pytest.raises(ValidationError):
            Node(
                id="test.py",
                type="file",
                name="test.py",
                path="test.py",
                lines=[10]  # Should be exactly 2 integers
            )


class TestEdge:
    def test_edge_creation(self):
        """Test basic Edge creation."""
        edge = Edge(
            source="main.py",
            target="utils.py",
            type=EdgeType.IMPORTS,
            line=5
        )
        assert edge.source == "main.py"
        assert edge.target == "utils.py"
        assert edge.type == EdgeType.IMPORTS
        assert edge.line == 5

    def test_edge_without_line(self):
        """Test Edge creation without line number."""
        edge = Edge(
            source="main.py",
            target="utils.py",
            type=EdgeType.IMPORTS
        )
        assert edge.line is None


class TestGraph:
    def test_graph_serialization(self, tmp_path):
        """Test Graph save/load round-trip."""
        # Create a sample graph
        repository = Repository(path="/tmp/test", name="test-repo")
        stats = Stats(total_nodes=3, total_edges=2, node_types={"file": 2, "class": 1})

        nodes = [
            Node(id="main.py", type="file", name="main.py", path="main.py"),
            Node(id="utils.py", type="file", name="utils.py", path="utils.py"),
            Node(id="User", type="class", name="User", path="models/user.py")
        ]

        edges = [
            Edge(source="main.py", target="utils.py", type=EdgeType.IMPORTS, line=1),
            Edge(source="main.py", target="User", type=EdgeType.IMPORTS, line=2)
        ]

        graph = Graph(
            version="0.1",
            generated_at=datetime.now(),
            repository=repository,
            stats=stats,
            nodes=nodes,
            edges=edges
        )

        # Save to file
        output_file = tmp_path / "test_graph.json"
        save_graph(graph, output_file)

        # Load from file
        loaded_graph = load_graph(output_file)

        # Verify round-trip
        assert loaded_graph.version == graph.version
        assert loaded_graph.repository.name == graph.repository.name
        assert loaded_graph.stats.total_nodes == graph.stats.total_nodes
        assert loaded_graph.stats.total_edges == graph.stats.total_edges
        assert len(loaded_graph.nodes) == len(graph.nodes)
        assert len(loaded_graph.edges) == len(graph.edges)

        # Check node data
        loaded_nodes = {node.id: node for node in loaded_graph.nodes}
        assert "main.py" in loaded_nodes
        assert loaded_nodes["main.py"].type == "file"

        # Check edge data
        assert len(loaded_graph.edges) == 2
        assert all(edge.type == EdgeType.IMPORTS for edge in loaded_graph.edges)